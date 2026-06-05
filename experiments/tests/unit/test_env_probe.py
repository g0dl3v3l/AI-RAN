import importlib.util
import json
from pathlib import Path

import pytest

from ai_runtime_experiments.schemas import ProbeStatus, make_probe_result
from ai_runtime_experiments.utils.command import CommandResult  # pyright: ignore[reportMissingImports]


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


def _runner_factory(mapping: dict[tuple[str, ...], CommandResult]):
    def fake_runner(argv, *, timeout_s=None, cwd=None, env=None, shell=False):
        del timeout_s, cwd, env, shell
        key = tuple(argv)
        if key not in mapping:
            raise AssertionError(f"unexpected command: {argv}")
        return mapping[key]

    return fake_runner


def _load_probe_functions():
    from ai_runtime_experiments.env_probe import (  # pyright: ignore[reportMissingImports]
        collect_docker_probe,
        collect_hardware_probe,
    )

    return collect_hardware_probe, collect_docker_probe


def _load_collect_hardware_script():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "collect_hardware.py"
    spec = importlib.util.spec_from_file_location("collect_hardware_script", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_host_probe_success_shape():
    collect_hardware_probe, _ = _load_probe_functions()

    runner = _runner_factory(
        {
            ("uname", "-a"): _result(
                ["uname", "-a"],
                status=ProbeStatus.OK,
                stdout="Linux ai-edge 6.8.0-31-generic #31-Ubuntu SMP x86_64 GNU/Linux\n",
            ),
            ("python", "--version"): _result(
                ["python", "--version"],
                status=ProbeStatus.OK,
                stdout="Python 3.12.3\n",
            ),
            ("nvidia-smi",): _result(
                ["nvidia-smi"],
                status=ProbeStatus.OK,
                stdout=(
                    "Fri Jun  5 12:00:00 2026\n"
                    "| NVIDIA-SMI 550.54.14    Driver Version: 550.54.14    CUDA Version: 12.4 |\n"
                    "| 0  NVIDIA RTX A5000                                                |\n"
                ),
            ),
            ("nvidia-smi", "-q"): _result(
                ["nvidia-smi", "-q"],
                status=ProbeStatus.OK,
                stdout=(
                    "Driver Version                      : 550.54.14\n"
                    "CUDA Version                        : 12.4\n"
                    "Attached GPUs                       : 1\n"
                    "Product Name                        : NVIDIA RTX A5000\n"
                    "FB Memory Usage\n"
                    "    Total                           : 24564 MiB\n"
                ),
            ),
        }
    )

    record = collect_hardware_probe(
        run_id="task-4",
        runner=runner,
        host_facts_getter=lambda: {
            "cpu_model": "AMD EPYC 7502 32-Core Processor",
            "cpu_core_count": 32,
            "system_memory_total_bytes": 137438953472,
        },
    )

    assert record["component"] == "hardware"
    assert record["status"] == "ok"
    assert record["run_id"] == "task-4"
    assert record["details"]["commands"]["uname_a"]["stdout"].startswith("Linux ai-edge")
    assert record["details"]["commands"]["nvidia_smi"]["status"] == "ok"
    assert record["details"]["commands"]["nvidia_smi_q"]["stdout"].startswith("Driver Version")
    assert record["details"]["extracted"]["python_version"] == "Python 3.12.3"
    assert record["details"]["extracted"]["driver_version"] == "550.54.14"
    assert record["details"]["extracted"]["cuda_version"] == "12.4"
    assert record["details"]["extracted"]["gpu_count"] == 1
    assert record["details"]["extracted"]["gpu_names"] == ["NVIDIA RTX A5000"]
    assert record["details"]["extracted"]["vram_total_mib"] == 24564
    assert record["details"]["extracted"]["cpu_model"] == "AMD EPYC 7502 32-Core Processor"
    assert record["details"]["extracted"]["cpu_core_count"] == 32
    assert record["details"]["extracted"]["system_memory_total_bytes"] == 137438953472



def test_missing_nvidia_smi_is_unsupported():
    collect_hardware_probe, _ = _load_probe_functions()

    runner = _runner_factory(
        {
            ("uname", "-a"): _result(
                ["uname", "-a"],
                status=ProbeStatus.OK,
                stdout="Linux ai-edge 6.8.0-31-generic #31-Ubuntu SMP x86_64 GNU/Linux\n",
            ),
            ("python", "--version"): _result(
                ["python", "--version"],
                status=ProbeStatus.OK,
                stdout="Python 3.12.3\n",
            ),
            ("nvidia-smi",): _result(
                ["nvidia-smi"],
                status=ProbeStatus.UNSUPPORTED,
                error_type="FileNotFoundError",
                error_message="[Errno 2] No such file or directory: 'nvidia-smi'",
            ),
            ("nvidia-smi", "-q"): _result(
                ["nvidia-smi", "-q"],
                status=ProbeStatus.UNSUPPORTED,
                error_type="FileNotFoundError",
                error_message="[Errno 2] No such file or directory: 'nvidia-smi'",
            ),
        }
    )

    record = collect_hardware_probe(
        run_id="task-4",
        runner=runner,
        host_facts_getter=lambda: {"cpu_core_count": 16},
    )

    assert record["status"] == "unsupported"
    assert "nvidia-smi" in record["details"]["reason"]
    assert record["details"]["commands"]["nvidia_smi"]["status"] == "unsupported"
    assert record["details"]["extracted"]["python_version"] == "Python 3.12.3"
    assert record["details"]["extracted"]["cpu_core_count"] == 16



def test_host_probe_ignores_best_effort_host_fact_failures():
    collect_hardware_probe, _ = _load_probe_functions()

    runner = _runner_factory(
        {
            ("uname", "-a"): _result(
                ["uname", "-a"],
                status=ProbeStatus.OK,
                stdout="Linux ai-edge 6.8.0-31-generic #31-Ubuntu SMP x86_64 GNU/Linux\n",
            ),
            ("python", "--version"): _result(
                ["python", "--version"],
                status=ProbeStatus.OK,
                stdout="Python 3.12.3\n",
            ),
            ("nvidia-smi",): _result(
                ["nvidia-smi"],
                status=ProbeStatus.OK,
                stdout="",
            ),
            ("nvidia-smi", "-q"): _result(
                ["nvidia-smi", "-q"],
                status=ProbeStatus.OK,
                stdout="",
            ),
        }
    )

    def broken_host_facts_getter():
        raise OSError("procfs unavailable")

    record = collect_hardware_probe(
        run_id="task-4",
        runner=runner,
        host_facts_getter=broken_host_facts_getter,
    )

    assert record["status"] == "ok"
    assert record["details"]["extracted"]["python_version"] == "Python 3.12.3"
    assert "cpu_model" not in record["details"]["extracted"]
    assert "system_memory_total_bytes" not in record["details"]["extracted"]



def test_docker_probe_success_shape():
    _, collect_docker_probe = _load_probe_functions()

    runner = _runner_factory(
        {
            ("docker", "version"): _result(
                ["docker", "version"],
                status=ProbeStatus.OK,
                stdout=(
                    "Client:\n"
                    " Version:           27.0.1\n"
                    " API version:       1.46\n"
                    "Server:\n"
                    " Engine:\n"
                    "  Version:          27.0.1\n"
                ),
            )
        }
    )

    record = collect_docker_probe(run_id="task-4", runner=runner)

    assert record["component"] == "docker"
    assert record["status"] == "ok"
    assert record["details"]["commands"]["docker_version"]["status"] == "ok"
    assert record["details"]["commands"]["docker_version"]["stdout"].startswith("Client:")
    assert record["details"]["extracted"]["client_version"] == "27.0.1"
    assert record["details"]["extracted"]["server_version"] == "27.0.1"



def test_docker_probe_missing_binary_is_unsupported():
    _, collect_docker_probe = _load_probe_functions()

    runner = _runner_factory(
        {
            ("docker", "version"): _result(
                ["docker", "version"],
                status=ProbeStatus.UNSUPPORTED,
                error_type="FileNotFoundError",
                error_message="[Errno 2] No such file or directory: 'docker'",
            )
        }
    )

    record = collect_docker_probe(run_id="task-4", runner=runner)

    assert record["status"] == "unsupported"
    assert "docker" in record["details"]["reason"]
    assert record["details"]["commands"]["docker_version"]["status"] == "unsupported"



def test_docker_probe_ignores_empty_version_lines():
    _, collect_docker_probe = _load_probe_functions()

    runner = _runner_factory(
        {
            ("docker", "version"): _result(
                ["docker", "version"],
                status=ProbeStatus.OK,
                stdout=(
                    "Client:\n"
                    " Version:\n"
                    "Server:\n"
                    " Version:          27.0.1\n"
                ),
            )
        }
    )

    record = collect_docker_probe(run_id="task-4", runner=runner)

    assert record["status"] == "ok"
    assert "client_version" not in record["details"]["extracted"]
    assert record["details"]["extracted"]["server_version"] == "27.0.1"



def test_collect_hardware_cli_writes_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    module = _load_collect_hardware_script()

    hardware_record = make_probe_result(
        run_id="cli-test",
        component="hardware",
        status=ProbeStatus.OK,
        details={"commands": {}, "extracted": {"python_version": "Python 3.12.3"}},
    )
    docker_record = make_probe_result(
        run_id="cli-test",
        component="docker",
        status=ProbeStatus.UNSUPPORTED,
        details={"reason": "docker is unavailable", "commands": {}},
    )

    monkeypatch.setattr(module, "collect_hardware_probe", lambda run_id: hardware_record)
    monkeypatch.setattr(module, "collect_docker_probe", lambda run_id: docker_record)

    exit_code = module.main(
        ["--output-dir", str(tmp_path), "--run-id", "cli-test"]
    )

    assert exit_code == 0
    assert json.loads((tmp_path / "hardware.json").read_text(encoding="utf-8"))["component"] == "hardware"
    assert json.loads((tmp_path / "docker.json").read_text(encoding="utf-8"))["status"] == "unsupported"
