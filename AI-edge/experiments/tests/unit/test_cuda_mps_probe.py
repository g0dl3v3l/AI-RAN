import importlib.util
import json
from pathlib import Path

import pytest

from ai_runtime_experiments.schemas import ProbeStatus, make_probe_result
from ai_runtime_experiments.utils.command import CommandResult  # pyright: ignore[reportMissingImports]


DEFAULT_CUDA_IMAGE = "nvidia/cuda:12.4.1-base-ubuntu22.04"


def _result(
    argv: list[str],
    *,
    status: ProbeStatus,
    stdout: str = "",
    stderr: str = "",
    returncode: int | None = None,
    timed_out: bool = False,
    duration_s: float = 0.01,
    error_type: str | None = None,
    error_message: str | None = None,
) -> CommandResult:
    inferred_returncode = 0 if status == ProbeStatus.OK else returncode
    return CommandResult(
        argv=argv,
        status=status,
        returncode=inferred_returncode,
        stdout=stdout,
        stderr=stderr,
        timed_out=timed_out,
        duration_s=duration_s,
        error_type=error_type,
        error_message=error_message,
    )


class RecordingRunner:
    def __init__(self, mapping: dict[tuple[str, ...], CommandResult]):
        self._mapping = mapping
        self.calls: list[list[str]] = []

    def __call__(self, argv, *, timeout_s=None, cwd=None, env=None, shell=False):
        del timeout_s, cwd, env, shell
        argv_list = list(argv)
        self.calls.append(argv_list)
        key = tuple(argv_list)
        if key not in self._mapping:
            raise AssertionError(f"unexpected command: {argv_list}")
        return self._mapping[key]


class RecordingControlRunner:
    def __init__(self, result: CommandResult):
        self.result = result
        self.calls: list[tuple[str, str, float | None]] = []

    def __call__(self, *, binary_path: str, command: str, timeout_s: float | None = None):
        self.calls.append((binary_path, command, timeout_s))
        return self.result


class StubPath:
    def __init__(self, path: str, *, exists_value: bool):
        self._path = path
        self._exists_value = exists_value

    def exists(self) -> bool:
        return self._exists_value

    def __str__(self) -> str:
        return self._path



def _load_probe_functions():
    from ai_runtime_experiments.env_probe.cuda import (  # pyright: ignore[reportMissingImports]
        collect_cuda_container_probe,
    )
    from ai_runtime_experiments.env_probe.mps import collect_mps_probe  # pyright: ignore[reportMissingImports]

    return collect_cuda_container_probe, collect_mps_probe



def _load_check_cuda_script():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "check_cuda_container.py"
    spec = importlib.util.spec_from_file_location("check_cuda_container_script", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module



def _load_check_mps_script():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "check_mps.py"
    spec = importlib.util.spec_from_file_location("check_mps_script", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module



def test_cuda_probe_uses_configured_image():
    collect_cuda_container_probe, _ = _load_probe_functions()

    image = "nvidia/cuda:12.5.0-base-ubuntu22.04"
    command = ["docker", "run", "--gpus", "all", "--rm", image, "nvidia-smi"]
    runner = RecordingRunner(
        {
            tuple(command): _result(
                command,
                status=ProbeStatus.OK,
                stdout=(
                    "Fri Jun  5 12:00:00 2026\n"
                    "| NVIDIA-SMI 550.54.14    Driver Version: 550.54.14    CUDA Version: 12.4 |\n"
                ),
            )
        }
    )

    record = collect_cuda_container_probe(run_id="task-6", runner=runner, image=image)

    assert record["component"] == "cuda_check"
    assert record["status"] == "ok"
    assert record["details"]["container"]["image"] == image
    assert record["details"]["commands"]["docker_run_nvidia_smi"]["argv"] == command
    assert record["details"]["extracted"]["driver_version"] == "550.54.14"
    assert record["details"]["extracted"]["cuda_version"] == "12.4"



def test_cuda_probe_missing_docker_binary_is_unsupported():
    collect_cuda_container_probe, _ = _load_probe_functions()

    command = ["docker", "run", "--gpus", "all", "--rm", DEFAULT_CUDA_IMAGE, "nvidia-smi"]
    runner = RecordingRunner(
        {
            tuple(command): _result(
                command,
                status=ProbeStatus.UNSUPPORTED,
                error_type="FileNotFoundError",
                error_message="[Errno 2] No such file or directory: 'docker'",
            )
        }
    )

    record = collect_cuda_container_probe(run_id="task-6", runner=runner)

    assert record["status"] == "unsupported"
    assert "docker run --gpus all" in record["details"]["reason"]
    assert record["details"]["container"]["image"] == DEFAULT_CUDA_IMAGE



def test_mps_missing_is_unsupported():
    _, collect_mps_probe = _load_probe_functions()

    runner = RecordingRunner({})
    control_runner = RecordingControlRunner(
        _result(["nvidia-cuda-mps-control"], status=ProbeStatus.OK, stdout="quit\n")
    )

    record = collect_mps_probe(
        run_id="task-6",
        runner=runner,
        control_command_runner=control_runner,
        which=lambda _: None,
    )

    assert record["component"] == "mps_check"
    assert record["status"] == "unsupported"
    assert record["details"]["mode"] == "read_only"
    assert record["details"]["start_stop"]["attempted"] is False
    assert runner.calls == []
    assert control_runner.calls == []



def test_mps_opt_in_attempts_start_stop_only_when_allowed():
    _, collect_mps_probe = _load_probe_functions()

    start_runner = RecordingRunner(
        {
            ("/usr/bin/nvidia-cuda-mps-control", "-d"): _result(
                ["/usr/bin/nvidia-cuda-mps-control", "-d"],
                status=ProbeStatus.OK,
                stdout="daemon started\n",
            )
        }
    )
    stop_runner = RecordingControlRunner(
        _result(
            ["/usr/bin/nvidia-cuda-mps-control"],
            status=ProbeStatus.OK,
            stdout="quit\n",
        )
    )

    record = collect_mps_probe(
        run_id="task-6",
        runner=start_runner,
        control_command_runner=stop_runner,
        allow_start_stop=True,
        which=lambda _: "/usr/bin/nvidia-cuda-mps-control",
        control_pipe_path=StubPath("/tmp/nvidia-mps/control", exists_value=False),
    )

    assert record["status"] == "ok"
    assert record["details"]["mode"] == "start_stop"
    assert record["details"]["start_stop"]["attempted"] is True
    assert record["details"]["start_stop"]["started_by_probe"] is True
    assert start_runner.calls == [["/usr/bin/nvidia-cuda-mps-control", "-d"]]
    assert stop_runner.calls == [("/usr/bin/nvidia-cuda-mps-control", "quit", pytest.approx(5.0, rel=0, abs=5.0))]



def test_check_cuda_cli_writes_artifact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    module = _load_check_cuda_script()

    cuda_record = make_probe_result(
        run_id="cli-test",
        component="cuda_check",
        status=ProbeStatus.UNSUPPORTED,
        details={"reason": "docker runtime unavailable", "commands": {}, "container": {"image": DEFAULT_CUDA_IMAGE}},
    )
    seen: dict[str, object] = {}

    def fake_collect(*, run_id: str, image: str = DEFAULT_CUDA_IMAGE):
        seen["run_id"] = run_id
        seen["image"] = image
        return cuda_record

    monkeypatch.setattr(module, "collect_cuda_container_probe", fake_collect)

    exit_code = module.main(["--output-dir", str(tmp_path), "--run-id", "cli-test"])

    assert exit_code == 0
    assert seen == {"run_id": "cli-test", "image": DEFAULT_CUDA_IMAGE}
    written = json.loads((tmp_path / "cuda_check.json").read_text(encoding="utf-8"))
    assert written["component"] == "cuda_check"
    assert written["status"] == "unsupported"



def test_check_mps_cli_defaults_to_read_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    module = _load_check_mps_script()

    mps_record = make_probe_result(
        run_id="cli-test",
        component="mps_check",
        status=ProbeStatus.OK,
        details={"commands": {}, "mode": "read_only", "start_stop": {"attempted": False}},
    )
    seen: dict[str, object] = {}

    def fake_collect(*, run_id: str, allow_start_stop: bool = False):
        seen["run_id"] = run_id
        seen["allow_start_stop"] = allow_start_stop
        return mps_record

    monkeypatch.setattr(module, "collect_mps_probe", fake_collect)

    exit_code = module.main(["--output-dir", str(tmp_path), "--run-id", "cli-test"])

    assert exit_code == 0
    assert seen == {"run_id": "cli-test", "allow_start_stop": False}
    written = json.loads((tmp_path / "mps_check.json").read_text(encoding="utf-8"))
    assert written["component"] == "mps_check"
    assert written["details"]["mode"] == "read_only"
