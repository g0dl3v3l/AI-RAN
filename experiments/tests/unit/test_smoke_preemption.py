from __future__ import annotations

from ai_runtime_experiments.runtime_adapters import RuntimeSession
from ai_runtime_experiments.schemas import ProbeStatus, make_probe_result
from ai_runtime_experiments.utils.command import CommandResult


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


def _runtime_session(
    *,
    runtime: str = "vllm",
    mode: str = "docker_server",
    status: ProbeStatus = ProbeStatus.OK,
    container_name: str | None = "ai-edge-v0-vllm-fixed",
    container_id: str | None = "container-123",
) -> RuntimeSession:
    return RuntimeSession(
        runtime=runtime,
        mode=mode,
        status=status,
        runtime_check=make_probe_result(
            run_id="task-8",
            component="runtime_check",
            status=status,
            details={"runtime": runtime, "mode": mode},
        ),
        base_url="http://127.0.0.1:8000/v1",
        container_name=container_name,
        container_id=container_id,
    )


def _docker_criu_probe(
    *, status: ProbeStatus = ProbeStatus.OK, reason: str | None = None
):
    details: dict[str, object] = {"commands": {}}
    if reason is not None:
        details["reason"] = reason
    return make_probe_result(
        run_id="task-8",
        component="docker_criu_integration",
        status=status,
        details=details,
    )


def test_no_container_skips_preemption():
    from ai_runtime_experiments.preemption import collect_smoke_preemption

    runner = RecordingRunner({})
    session = _runtime_session(
        mode="external_server", container_name=None, container_id=None
    )

    record = collect_smoke_preemption(
        run_id="task-8",
        runtime_session=session,
        docker_criu_integration=_docker_criu_probe(),
        runner=runner,
    )

    assert record["component"] == "smoke_preemption"
    assert record["status"] == "skipped"
    assert record["details"]["smoke"]["attempted"] is False
    assert record["details"]["checkpoint"]["attempted"] is False
    assert record["details"]["restore"]["attempted"] is False
    assert record["details"]["outcome"] == "not_attempted"
    assert "container" in record["details"]["reason"]
    assert runner.calls == []


def test_unsupported_prerequisite_does_not_attempt_preemption():
    from ai_runtime_experiments.preemption import collect_smoke_preemption

    runner = RecordingRunner({})
    session = _runtime_session()

    record = collect_smoke_preemption(
        run_id="task-8",
        runtime_session=session,
        docker_criu_integration=_docker_criu_probe(
            status=ProbeStatus.UNSUPPORTED,
            reason="unsupported capability: docker checkpoint create",
        ),
        runner=runner,
    )

    assert record["status"] == "unsupported"
    assert record["details"]["smoke"]["attempted"] is False
    assert record["details"]["outcome"] == "not_supported"
    assert "docker checkpoint create" in record["details"]["reason"]
    assert runner.calls == []


def test_non_experiment_owned_container_fails_before_checkpoint_or_restore():
    from ai_runtime_experiments.preemption import collect_smoke_preemption

    inspect_command = [
        "docker",
        "inspect",
        "--format",
        "{{json .Config.Labels}}",
        "ai-edge-v0-vllm-fixed",
    ]
    runner = RecordingRunner(
        {
            tuple(inspect_command): _result(
                inspect_command,
                status=ProbeStatus.OK,
                stdout='{"ai-edge-experiment":"someone-else"}\n',
            )
        }
    )
    session = _runtime_session()

    record = collect_smoke_preemption(
        run_id="task-8",
        runtime_session=session,
        docker_criu_integration=_docker_criu_probe(),
        runner=runner,
    )

    assert record["status"] == "error"
    assert record["details"]["smoke"]["attempted"] is False
    assert record["details"]["outcome"] == "not_attempted"
    assert "experiment-owned" in record["details"]["reason"]
    assert record["details"]["commands"]["docker_inspect_labels"]["status"] == "ok"
    assert runner.calls == [inspect_command]


def test_llama_cpp_experiment_owned_container_can_attempt_preemption():
    from ai_runtime_experiments.preemption import collect_smoke_preemption

    container_name = "ai-edge-v0-llama-cpp-fixed"
    inspect_command = [
        "docker",
        "inspect",
        "--format",
        "{{json .Config.Labels}}",
        container_name,
    ]
    checkpoint_command = ["docker", "checkpoint", "create", container_name, "cp1"]
    start_command = ["docker", "start", "--checkpoint", "cp1", container_name]
    state_command = [
        "docker",
        "inspect",
        "--format",
        "{{.State.Status}}",
        container_name,
    ]
    runner = RecordingRunner(
        {
            tuple(inspect_command): _result(
                inspect_command,
                status=ProbeStatus.OK,
                stdout=(
                    '{"ai-edge-experiment":"v0",'
                    '"ai-edge-component":"llama-cpp-runtime",'
                    '"ai-edge-run-id":"task-8"}\n'
                ),
            ),
            tuple(checkpoint_command): _result(
                checkpoint_command, status=ProbeStatus.OK, stdout="cp1\n"
            ),
            tuple(start_command): _result(
                start_command, status=ProbeStatus.OK, stdout=container_name + "\n"
            ),
            tuple(state_command): _result(
                state_command, status=ProbeStatus.OK, stdout="running\n"
            ),
        }
    )
    session = _runtime_session(
        runtime="llama_cpp",
        container_name=container_name,
    )

    record = collect_smoke_preemption(
        run_id="task-8",
        runtime_session=session,
        docker_criu_integration=_docker_criu_probe(),
        runner=runner,
        checkpoint_name="cp1",
        post_checkpoint_delay_s=0,
    )

    assert record["status"] == "ok"
    assert record["details"]["outcome"] == "restored"
    assert (
        record["details"]["container"]["inspected_labels"]["ai-edge-component"]
        == "llama-cpp-runtime"
    )
    assert runner.calls == [
        inspect_command,
        checkpoint_command,
        start_command,
        state_command,
    ]
