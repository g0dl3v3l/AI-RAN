import importlib.util
import json
from pathlib import Path
from typing import Any

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



def _load_docker_criu_functions():
    from ai_runtime_experiments.docker_criu import (  # pyright: ignore[reportMissingImports]
        build_experiment_container_name,
        build_experiment_labels,
        collect_criu_probe,
        collect_docker_criu_integration,
        ensure_experiment_owned_container,
    )

    return (
        collect_criu_probe,
        collect_docker_criu_integration,
        build_experiment_container_name,
        build_experiment_labels,
        ensure_experiment_owned_container,
    )



def _load_check_docker_criu_script():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "check_docker_criu.py"
    spec = importlib.util.spec_from_file_location("check_docker_criu_script", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module



def _ok_criu_probe() -> dict[str, object]:
    return make_probe_result(
        run_id="task-5",
        component="criu_check",
        status=ProbeStatus.OK,
        details={"commands": {}, "extracted": {"criu_version": "3.19"}},
    )



def test_criu_probe_success_shape():
    collect_criu_probe, _, _, _, _ = _load_docker_criu_functions()

    runner = RecordingRunner(
        {
            ("criu", "--version"): _result(
                ["criu", "--version"],
                status=ProbeStatus.OK,
                stdout="Version: 3.19\n",
            )
        }
    )

    record = collect_criu_probe(run_id="task-5", runner=runner)

    assert record["component"] == "criu_check"
    assert record["status"] == "ok"
    assert record["details"]["commands"]["criu_version"]["status"] == "ok"
    assert record["details"]["extracted"]["criu_version"] == "3.19"



def test_criu_probe_missing_binary_is_unsupported():
    collect_criu_probe, _, _, _, _ = _load_docker_criu_functions()

    runner = RecordingRunner(
        {
            ("criu", "--version"): _result(
                ["criu", "--version"],
                status=ProbeStatus.UNSUPPORTED,
                error_type="FileNotFoundError",
                error_message="[Errno 2] No such file or directory: 'criu'",
            )
        }
    )

    record = collect_criu_probe(run_id="task-5", runner=runner)

    assert record["status"] == "unsupported"
    assert "criu" in record["details"]["reason"]
    assert record["details"]["commands"]["criu_version"]["status"] == "unsupported"



def test_missing_docker_checkpoint_is_unsupported():
    _, collect_docker_criu_integration, _, _, _ = _load_docker_criu_functions()

    runner = RecordingRunner(
        {
            ("docker", "checkpoint", "--help"): _result(
                ["docker", "checkpoint", "--help"],
                status=ProbeStatus.ERROR,
                returncode=125,
                stderr="docker: 'checkpoint' is not a docker command.\nSee 'docker --help'.\n",
            )
        }
    )

    record = collect_docker_criu_integration(
        run_id="task-5",
        runner=runner,
        criu_probe=_ok_criu_probe(),
        container_name="ai-edge-v0-criu-fixed",
    )

    assert record["component"] == "docker_criu_integration"
    assert record["status"] == "unsupported"
    assert record["details"]["smoke"]["attempted"] is False
    assert "checkpoint" in record["details"]["reason"]



def test_refuses_unlabelled_container():
    _, collect_docker_criu_integration, _, _, _ = _load_docker_criu_functions()

    runner = RecordingRunner(
        {
            ("docker", "checkpoint", "--help"): _result(
                ["docker", "checkpoint", "--help"],
                status=ProbeStatus.OK,
                stdout="Usage: docker checkpoint COMMAND\n",
            ),
            (
                "docker",
                "run",
                "-d",
                "--runtime",
                "runc",
                "--network",
                "host",
                "--name",
                "ai-edge-v0-criu-fixed",
                "--label",
                "ai-edge-experiment=v0",
                "--label",
                "ai-edge-component=docker-criu",
                "--label",
                "ai-edge-run-id=task-5",
                "busybox:1.36",
                "sh",
                "-c",
                "while true; do sleep 1; done",
            ): _result(
                [
                    "docker",
                    "run",
                    "-d",
                    "--runtime",
                    "runc",
                    "--network",
                    "host",
                    "--name",
                    "ai-edge-v0-criu-fixed",
                    "--label",
                    "ai-edge-experiment=v0",
                    "--label",
                    "ai-edge-component=docker-criu",
                    "--label",
                    "ai-edge-run-id=task-5",
                    "busybox:1.36",
                    "sh",
                    "-c",
                    "while true; do sleep 1; done",
                ],
                status=ProbeStatus.OK,
                stdout="container-id\n",
            ),
            (
                "docker",
                "inspect",
                "--format",
                "{{json .Config.Labels}}",
                "ai-edge-v0-criu-fixed",
            ): _result(
                [
                    "docker",
                    "inspect",
                    "--format",
                    "{{json .Config.Labels}}",
                    "ai-edge-v0-criu-fixed",
                ],
                status=ProbeStatus.OK,
                stdout='{"ai-edge-experiment":"someone-else"}\n',
            ),
        }
    )

    record = collect_docker_criu_integration(
        run_id="task-5",
        runner=runner,
        criu_probe=_ok_criu_probe(),
        container_name="ai-edge-v0-criu-fixed",
    )

    assert record["status"] == "error"
    assert "experiment-owned" in record["details"]["reason"]
    assert not any(call[:3] == ["docker", "checkpoint", "create"] for call in runner.calls)
    assert not any(call[:3] == ["docker", "rm", "-f"] for call in runner.calls)



def test_docker_run_uses_expected_labels_and_prefix():
    (
        _,
        collect_docker_criu_integration,
        build_experiment_container_name,
        build_experiment_labels,
        _,
    ) = _load_docker_criu_functions()

    container_name = build_experiment_container_name("task-5", token="fixed")
    labels = build_experiment_labels("task-5")

    runner = RecordingRunner(
        {
            ("docker", "checkpoint", "--help"): _result(
                ["docker", "checkpoint", "--help"],
                status=ProbeStatus.OK,
                stdout="Usage: docker checkpoint COMMAND\n",
            ),
            (
                "docker",
                "run",
                "-d",
                "--runtime",
                "runc",
                "--network",
                "host",
                "--name",
                container_name,
                "--label",
                f"ai-edge-experiment={labels['ai-edge-experiment']}",
                "--label",
                f"ai-edge-component={labels['ai-edge-component']}",
                "--label",
                f"ai-edge-run-id={labels['ai-edge-run-id']}",
                "busybox:1.36",
                "sh",
                "-c",
                "while true; do sleep 1; done",
            ): _result(
                [
                    "docker",
                    "run",
                    "-d",
                    "--runtime",
                    "runc",
                    "--network",
                    "host",
                    "--name",
                    container_name,
                    "--label",
                    f"ai-edge-experiment={labels['ai-edge-experiment']}",
                    "--label",
                    f"ai-edge-component={labels['ai-edge-component']}",
                    "--label",
                    f"ai-edge-run-id={labels['ai-edge-run-id']}",
                    "busybox:1.36",
                    "sh",
                    "-c",
                    "while true; do sleep 1; done",
                ],
                status=ProbeStatus.OK,
                stdout="container-id\n",
            ),
            (
                "docker",
                "inspect",
                "--format",
                "{{json .Config.Labels}}",
                container_name,
            ): _result(
                ["docker", "inspect", "--format", "{{json .Config.Labels}}", container_name],
                status=ProbeStatus.OK,
                stdout=json.dumps(labels) + "\n",
            ),
            ("docker", "checkpoint", "create", container_name, "ai-edge-v0-criu-checkpoint"): _result(
                ["docker", "checkpoint", "create", container_name, "ai-edge-v0-criu-checkpoint"],
                status=ProbeStatus.OK,
                stdout="ai-edge-v0-criu-checkpoint\n",
            ),
            ("docker", "start", "--checkpoint", "ai-edge-v0-criu-checkpoint", container_name): _result(
                ["docker", "start", "--checkpoint", "ai-edge-v0-criu-checkpoint", container_name],
                status=ProbeStatus.OK,
                stdout=container_name + "\n",
            ),
            ("docker", "inspect", "--format", "{{.State.Status}}", container_name): _result(
                ["docker", "inspect", "--format", "{{.State.Status}}", container_name],
                status=ProbeStatus.OK,
                stdout="running\n",
            ),
            ("docker", "rm", "-f", container_name): _result(
                ["docker", "rm", "-f", container_name],
                status=ProbeStatus.OK,
                stdout=container_name + "\n",
            ),
        }
    )

    record = collect_docker_criu_integration(
        run_id="task-5",
        runner=runner,
        criu_probe=_ok_criu_probe(),
        container_name=container_name,
        post_checkpoint_delay_s=0,
    )

    assert record["status"] == "ok"
    assert container_name.startswith("ai-edge-v0-criu-")
    docker_run_call = next(call for call in runner.calls if call[:2] == ["docker", "run"])
    assert "--runtime" in docker_run_call
    assert "runc" in docker_run_call
    assert "--network" in docker_run_call
    assert "host" in docker_run_call
    assert "--name" in docker_run_call
    assert container_name in docker_run_call
    assert f"ai-edge-experiment={labels['ai-edge-experiment']}" in docker_run_call

    checkpoint_index = runner.calls.index(
        ["docker", "checkpoint", "create", container_name, "ai-edge-v0-criu-checkpoint"]
    )
    start_index = runner.calls.index(
        ["docker", "start", "--checkpoint", "ai-edge-v0-criu-checkpoint", container_name]
    )
    assert checkpoint_index < start_index
    assert not any(call[:2] == ["docker", "stop"] for call in runner.calls)



def test_docker_criu_falls_back_when_custom_checkpoint_dir_is_unsupported_on_start():
    (
        _,
        collect_docker_criu_integration,
        build_experiment_container_name,
        build_experiment_labels,
        _,
    ) = _load_docker_criu_functions()

    container_name = build_experiment_container_name("task-5", token="fixed")
    labels = build_experiment_labels("task-5")
    checkpoint_dir = "/dev/shm/ai-edge-v0"

    runner = RecordingRunner(
        {
            ("docker", "checkpoint", "--help"): _result(
                ["docker", "checkpoint", "--help"],
                status=ProbeStatus.OK,
                stdout="Usage: docker checkpoint COMMAND\n",
            ),
            (
                "docker",
                "run",
                "-d",
                "--runtime",
                "runc",
                "--network",
                "host",
                "--name",
                container_name,
                "--label",
                f"ai-edge-experiment={labels['ai-edge-experiment']}",
                "--label",
                f"ai-edge-component={labels['ai-edge-component']}",
                "--label",
                f"ai-edge-run-id={labels['ai-edge-run-id']}",
                "busybox:1.36",
                "sh",
                "-c",
                "while true; do sleep 1; done",
            ): _result(
                [
                    "docker",
                    "run",
                    "-d",
                    "--runtime",
                    "runc",
                    "--network",
                    "host",
                    "--name",
                    container_name,
                    "--label",
                    f"ai-edge-experiment={labels['ai-edge-experiment']}",
                    "--label",
                    f"ai-edge-component={labels['ai-edge-component']}",
                    "--label",
                    f"ai-edge-run-id={labels['ai-edge-run-id']}",
                    "busybox:1.36",
                    "sh",
                    "-c",
                    "while true; do sleep 1; done",
                ],
                status=ProbeStatus.OK,
                stdout="container-id\n",
            ),
            (
                "docker",
                "inspect",
                "--format",
                "{{json .Config.Labels}}",
                container_name,
            ): _result(
                ["docker", "inspect", "--format", "{{json .Config.Labels}}", container_name],
                status=ProbeStatus.OK,
                stdout=json.dumps(labels) + "\n",
            ),
            (
                "docker",
                "checkpoint",
                "create",
                "--checkpoint-dir",
                checkpoint_dir,
                container_name,
                "ai-edge-v0-criu-checkpoint",
            ): _result(
                [
                    "docker",
                    "checkpoint",
                    "create",
                    "--checkpoint-dir",
                    checkpoint_dir,
                    container_name,
                    "ai-edge-v0-criu-checkpoint",
                ],
                status=ProbeStatus.OK,
                stdout="ai-edge-v0-criu-checkpoint\n",
            ),
            (
                "docker",
                "start",
                "--checkpoint-dir",
                checkpoint_dir,
                "--checkpoint",
                "ai-edge-v0-criu-checkpoint",
                container_name,
            ): _result(
                [
                    "docker",
                    "start",
                    "--checkpoint-dir",
                    checkpoint_dir,
                    "--checkpoint",
                    "ai-edge-v0-criu-checkpoint",
                    container_name,
                ],
                status=ProbeStatus.ERROR,
                returncode=1,
                stderr="Error response from daemon: custom checkpointdir is not supported\n",
            ),
            ("docker", "start", container_name): _result(
                ["docker", "start", container_name],
                status=ProbeStatus.OK,
                stdout=container_name + "\n",
            ),
            (
                "docker",
                "checkpoint",
                "create",
                container_name,
                "ai-edge-v0-criu-checkpoint-default-fallback",
            ): _result(
                [
                    "docker",
                    "checkpoint",
                    "create",
                    container_name,
                    "ai-edge-v0-criu-checkpoint-default-fallback",
                ],
                status=ProbeStatus.OK,
                stdout="ai-edge-v0-criu-checkpoint-default-fallback\n",
            ),
            (
                "docker",
                "start",
                "--checkpoint",
                "ai-edge-v0-criu-checkpoint-default-fallback",
                container_name,
            ): _result(
                [
                    "docker",
                    "start",
                    "--checkpoint",
                    "ai-edge-v0-criu-checkpoint-default-fallback",
                    container_name,
                ],
                status=ProbeStatus.OK,
                stdout=container_name + "\n",
            ),
            ("docker", "inspect", "--format", "{{.State.Status}}", container_name): _result(
                ["docker", "inspect", "--format", "{{.State.Status}}", container_name],
                status=ProbeStatus.OK,
                stdout="running\n",
            ),
            ("docker", "rm", "-f", container_name): _result(
                ["docker", "rm", "-f", container_name],
                status=ProbeStatus.OK,
                stdout=container_name + "\n",
            ),
        }
    )

    record = collect_docker_criu_integration(
        run_id="task-5",
        runner=runner,
        criu_probe=_ok_criu_probe(),
        container_name=container_name,
        checkpoint_dir=checkpoint_dir,
        post_checkpoint_delay_s=0,
    )

    assert record["status"] == "ok"
    assert record["details"]["fallback"]["used"] is True
    assert record["details"]["fallback"]["original_checkpoint_dir"] == checkpoint_dir


def test_ensure_experiment_owned_container_accepts_expected_label_and_name():
    _, _, build_experiment_container_name, build_experiment_labels, ensure_experiment_owned_container = (
        _load_docker_criu_functions()
    )

    container_name = build_experiment_container_name("task-5", token="fixed")
    labels = build_experiment_labels("task-5")

    ensure_experiment_owned_container(container_name=container_name, labels=labels)



def test_docker_criu_captures_checkpoint_log_before_cleanup(tmp_path: Path):
    (
        _,
        collect_docker_criu_integration,
        build_experiment_container_name,
        build_experiment_labels,
        _,
    ) = _load_docker_criu_functions()

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    source_log = tmp_path / "criu-dump.log"
    source_log.write_text("dump failed before cleanup\n", encoding="utf-8")
    container_name = build_experiment_container_name("task-5", token="fixed")
    labels = build_experiment_labels("task-5")

    mapping = {
        ("docker", "checkpoint", "--help"): _result(
            ["docker", "checkpoint", "--help"],
            status=ProbeStatus.OK,
            stdout="Usage: docker checkpoint COMMAND\n",
        ),
        (
            "docker",
            "run",
            "-d",
            "--runtime",
            "runc",
            "--network",
            "host",
            "--name",
            container_name,
            "--label",
            f"ai-edge-experiment={labels['ai-edge-experiment']}",
            "--label",
            f"ai-edge-component={labels['ai-edge-component']}",
            "--label",
            f"ai-edge-run-id={labels['ai-edge-run-id']}",
            "busybox:1.36",
            "sh",
            "-c",
            "while true; do sleep 1; done",
        ): _result(
            [
                "docker",
                "run",
                "-d",
                "--runtime",
                "runc",
                "--network",
                "host",
                "--name",
                container_name,
                "--label",
                f"ai-edge-experiment={labels['ai-edge-experiment']}",
                "--label",
                f"ai-edge-component={labels['ai-edge-component']}",
                "--label",
                f"ai-edge-run-id={labels['ai-edge-run-id']}",
                "busybox:1.36",
                "sh",
                "-c",
                "while true; do sleep 1; done",
            ],
            status=ProbeStatus.OK,
            stdout="container-id\n",
        ),
        (
            "docker",
            "inspect",
            "--format",
            "{{json .Config.Labels}}",
            container_name,
        ): _result(
            ["docker", "inspect", "--format", "{{json .Config.Labels}}", container_name],
            status=ProbeStatus.OK,
            stdout=json.dumps(labels) + "\n",
        ),
        (
            "docker",
            "checkpoint",
            "create",
            container_name,
            "ai-edge-v0-criu-checkpoint",
        ): _result(
            [
                "docker",
                "checkpoint",
                "create",
                container_name,
                "ai-edge-v0-criu-checkpoint",
            ],
            status=ProbeStatus.ERROR,
            returncode=1,
            stderr=f"criu failed: type DUMP errno 0 path= {source_log}\n",
        ),
        ("docker", "rm", "-f", container_name): _result(
            ["docker", "rm", "-f", container_name],
            status=ProbeStatus.OK,
            stdout=container_name + "\n",
        ),
    }

    events: list[object] = []

    def runner(argv, *, timeout_s=None, cwd=None, env=None, shell=False):
        del timeout_s, cwd, env, shell
        argv_list = list(argv)
        events.append(tuple(argv_list))
        if argv_list[:3] == ["docker", "rm", "-f"]:
            source_log.unlink(missing_ok=True)
        key = tuple(argv_list)
        if key not in mapping:
            raise AssertionError(f"unexpected command: {argv_list}")
        return mapping[key]

    captured: dict[str, Any] = {}

    def hook(record: dict[str, Any]):
        events.append("hook")
        copied = run_dir / "captured.log"
        copied.write_text(source_log.read_text(encoding="utf-8"), encoding="utf-8")
        captured["record"] = record
        captured["copied"] = copied

    record = collect_docker_criu_integration(
        run_id="task-5",
        runner=runner,
        criu_probe=_ok_criu_probe(),
        container_name=container_name,
        post_checkpoint_delay_s=0,
        debug_capture_hook=hook,
    )

    assert record["status"] == "error"
    assert events.index("hook") < events.index(("docker", "rm", "-f", container_name))
    assert not source_log.exists()
    assert captured["record"]["details"]["commands"]["docker_checkpoint_create"]["status"] == "error"
    assert captured["copied"].read_text(encoding="utf-8") == "dump failed before cleanup\n"



def test_check_docker_criu_cli_writes_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    module = _load_check_docker_criu_script()

    source_log = tmp_path / "criu-dump.log"
    source_log.write_text("captured before cleanup\n", encoding="utf-8")
    criu_record = make_probe_result(
        run_id="cli-test",
        component="criu_check",
        status=ProbeStatus.OK,
        details={"commands": {}, "extracted": {"criu_version": "3.19"}},
    )
    integration_record = make_probe_result(
        run_id="cli-test",
        component="docker_criu_integration",
        status=ProbeStatus.ERROR,
        details={
            "reason": "docker checkpoint failed",
            "commands": {
                "docker_checkpoint_create": {
                    "stderr": f"criu failed: type DUMP errno 0 path= {source_log}\n"
                }
            },
            "smoke": {"attempted": True},
        },
    )

    monkeypatch.setattr(module, "collect_criu_probe", lambda run_id: criu_record)

    callback_seen: dict[str, object] = {"called": False}

    def _collect_docker_criu_integration(run_id, criu_probe=None, debug_capture_hook=None):
        del run_id, criu_probe
        callback_seen["called"] = callable(debug_capture_hook)
        if debug_capture_hook is not None:
            debug_capture_hook(integration_record)
        return integration_record

    monkeypatch.setattr(
        module,
        "collect_docker_criu_integration",
        _collect_docker_criu_integration,
    )

    exit_code = module.main(["--output-dir", str(tmp_path), "--run-id", "cli-test"])

    assert exit_code == 0
    assert callback_seen["called"] is True
    assert json.loads((tmp_path / "criu_check.json").read_text(encoding="utf-8"))["component"] == "criu_check"
    assert (
        json.loads((tmp_path / "docker_criu_integration.json").read_text(encoding="utf-8"))["status"]
        == "error"
    )
    assert (
        tmp_path / "criu_logs" / "docker_criu_integration" / "01-criu-dump.log"
    ).read_text(encoding="utf-8") == "captured before cleanup\n"
