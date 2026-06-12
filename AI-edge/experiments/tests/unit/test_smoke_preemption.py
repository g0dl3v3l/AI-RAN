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
    def __init__(
        self,
        mapping: dict[tuple[str, ...], CommandResult | list[CommandResult]],
    ):
        self._mapping: dict[tuple[str, ...], list[CommandResult]] = {}
        for key, value in mapping.items():
            if isinstance(value, list):
                self._mapping[key] = list(value)
            else:
                self._mapping[key] = [value]
        self.calls: list[list[str]] = []
        self.call_details: list[dict[str, object]] = []

    def __call__(self, argv, *, timeout_s=None, cwd=None, env=None, shell=False, input_text=None):
        del cwd, env, shell
        argv_list = list(argv)
        self.calls.append(argv_list)
        self.call_details.append(
            {
                "argv": argv_list,
                "timeout_s": timeout_s,
                "input_text": input_text,
            }
        )
        key = tuple(argv_list)
        if key not in self._mapping or not self._mapping[key]:
            raise AssertionError(f"unexpected command: {argv_list}")
        return self._mapping[key].pop(0)


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


def test_custom_checkpoint_dir_restore_falls_back_to_default_checkpoint_storage():
    from ai_runtime_experiments.preemption import collect_smoke_preemption

    container_name = "ai-edge-v0-vllm-fixed"
    checkpoint_dir = "/dev/shm/ai-edge-v0"
    inspect_command = [
        "docker",
        "inspect",
        "--format",
        "{{json .Config.Labels}}",
        container_name,
    ]
    checkpoint_command = [
        "docker",
        "checkpoint",
        "create",
        "--checkpoint-dir",
        checkpoint_dir,
        container_name,
        "cp1",
    ]
    start_with_dir_command = [
        "docker",
        "start",
        "--checkpoint-dir",
        checkpoint_dir,
        "--checkpoint",
        "cp1",
        container_name,
    ]
    recover_start_command = ["docker", "start", container_name]
    fallback_checkpoint_command = [
        "docker",
        "checkpoint",
        "create",
        container_name,
        "cp1-default-fallback",
    ]
    fallback_start_command = [
        "docker",
        "start",
        "--checkpoint",
        "cp1-default-fallback",
        container_name,
    ]
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
                    '"ai-edge-component":"vllm-runtime",'
                    '"ai-edge-run-id":"task-8"}\n'
                ),
            ),
            tuple(checkpoint_command): _result(
                checkpoint_command,
                status=ProbeStatus.OK,
                stdout="cp1\n",
            ),
            tuple(start_with_dir_command): _result(
                start_with_dir_command,
                status=ProbeStatus.ERROR,
                returncode=1,
                stderr="Error response from daemon: custom checkpointdir is not supported\n",
            ),
            tuple(recover_start_command): _result(
                recover_start_command,
                status=ProbeStatus.OK,
                stdout=container_name + "\n",
            ),
            tuple(fallback_checkpoint_command): _result(
                fallback_checkpoint_command,
                status=ProbeStatus.OK,
                stdout="cp1-default-fallback\n",
            ),
            tuple(fallback_start_command): _result(
                fallback_start_command,
                status=ProbeStatus.OK,
                stdout=container_name + "\n",
            ),
            tuple(state_command): _result(
                state_command,
                status=ProbeStatus.OK,
                stdout="running\n",
            ),
        }
    )

    record = collect_smoke_preemption(
        run_id="task-8",
        runtime_session=_runtime_session(container_name=container_name),
        docker_criu_integration=_docker_criu_probe(),
        runner=runner,
        checkpoint_name="cp1",
        checkpoint_dir=checkpoint_dir,
        post_checkpoint_delay_s=0,
    )

    assert record["status"] == "ok"
    assert record["details"]["outcome"] == "restored"
    assert record["details"]["fallback"]["used"] is True
    assert record["details"]["fallback"]["original_checkpoint_dir"] == checkpoint_dir
    assert runner.calls == [
        inspect_command,
        checkpoint_command,
        start_with_dir_command,
        recover_start_command,
        fallback_checkpoint_command,
        fallback_start_command,
        state_command,
    ]


def test_smoke_preemption_switches_criu_config_before_dump_and_restore_and_restores_original():
    from ai_runtime_experiments.preemption import collect_smoke_preemption

    container_name = "ai-edge-v0-vllm-fixed"
    inspect_command = ["docker", "inspect", "--format", "{{json .Config.Labels}}", container_name]
    capture_original_command = ["sudo", "-n", "cat", "/etc/criu/runc.conf"]
    write_command = ["sudo", "-n", "tee", "/etc/criu/runc.conf"]
    checkpoint_command = ["docker", "checkpoint", "create", container_name, "cp1"]
    start_command = ["docker", "start", "--checkpoint", "cp1", container_name]
    state_command = ["docker", "inspect", "--format", "{{.State.Status}}", container_name]

    runner = RecordingRunner(
        {
            tuple(inspect_command): _result(
                inspect_command,
                status=ProbeStatus.OK,
                stdout=(
                    '{"ai-edge-experiment":"v0",'
                    '"ai-edge-component":"vllm-runtime",'
                    '"ai-edge-run-id":"task-8"}\n'
                ),
            ),
            tuple(capture_original_command): _result(
                capture_original_command,
                status=ProbeStatus.OK,
                stdout="original\n",
            ),
            tuple(write_command): [
                _result(write_command, status=ProbeStatus.OK, stdout="ok\n"),
                _result(write_command, status=ProbeStatus.OK, stdout="ok\n"),
                _result(write_command, status=ProbeStatus.OK, stdout="ok\n"),
            ],
            tuple(checkpoint_command): _result(
                checkpoint_command,
                status=ProbeStatus.OK,
                stdout="cp1\n",
            ),
            tuple(start_command): _result(
                start_command,
                status=ProbeStatus.OK,
                stdout=container_name + "\n",
            ),
            tuple(state_command): _result(
                state_command,
                status=ProbeStatus.OK,
                stdout="running\n",
            ),
        }
    )

    record = collect_smoke_preemption(
        run_id="task-8",
        runtime_session=_runtime_session(container_name=container_name),
        docker_criu_integration=_docker_criu_probe(),
        runner=runner,
        checkpoint_name="cp1",
        post_checkpoint_delay_s=0,
        criu_config_mode="cdi_restore_compat",
        criu_config_allow_sudo=True,
    )

    assert record["status"] == "ok"
    assert runner.calls == [
        inspect_command,
        capture_original_command,
        write_command,
        checkpoint_command,
        write_command,
        start_command,
        state_command,
        write_command,
    ]
    assert (
        "mntns-compat-mode"
        not in record["details"]["commands"]["write_criu_runc_conf_dump"]["stdin"]
    )
    assert (
        "mntns-compat-mode"
        in record["details"]["commands"]["write_criu_runc_conf_restore"]["stdin"]
    )
    assert record["details"]["commands"]["restore_criu_runc_conf_original"]["stdin"] == "original\n"
    assert record["details"]["diagnostics"]["criu_config"]["lock"]["status"] == "ok"



def test_smoke_preemption_restores_original_criu_config_when_restore_start_fails():
    from ai_runtime_experiments.preemption import collect_smoke_preemption

    container_name = "ai-edge-v0-vllm-fixed"
    inspect_command = ["docker", "inspect", "--format", "{{json .Config.Labels}}", container_name]
    capture_original_command = ["sudo", "-n", "cat", "/etc/criu/runc.conf"]
    write_command = ["sudo", "-n", "tee", "/etc/criu/runc.conf"]
    checkpoint_command = ["docker", "checkpoint", "create", container_name, "cp1"]
    start_command = ["docker", "start", "--checkpoint", "cp1", container_name]

    runner = RecordingRunner(
        {
            tuple(inspect_command): _result(
                inspect_command,
                status=ProbeStatus.OK,
                stdout=(
                    '{"ai-edge-experiment":"v0",'
                    '"ai-edge-component":"vllm-runtime",'
                    '"ai-edge-run-id":"task-8"}\n'
                ),
            ),
            tuple(capture_original_command): _result(
                capture_original_command,
                status=ProbeStatus.OK,
                stdout="original\n",
            ),
            tuple(write_command): [
                _result(write_command, status=ProbeStatus.OK, stdout="ok\n"),
                _result(write_command, status=ProbeStatus.OK, stdout="ok\n"),
                _result(write_command, status=ProbeStatus.OK, stdout="ok\n"),
            ],
            tuple(checkpoint_command): _result(
                checkpoint_command,
                status=ProbeStatus.OK,
                stdout="cp1\n",
            ),
            tuple(start_command): _result(
                start_command,
                status=ProbeStatus.ERROR,
                returncode=1,
                stderr="restore failed\n",
            ),
        }
    )

    record = collect_smoke_preemption(
        run_id="task-8",
        runtime_session=_runtime_session(container_name=container_name),
        docker_criu_integration=_docker_criu_probe(),
        runner=runner,
        checkpoint_name="cp1",
        post_checkpoint_delay_s=0,
        criu_config_mode="cdi_restore_compat",
        criu_config_allow_sudo=True,
    )

    assert record["status"] == "error"
    assert record["details"]["outcome"] == "restore_failed"
    assert runner.calls == [
        inspect_command,
        capture_original_command,
        write_command,
        checkpoint_command,
        write_command,
        start_command,
        write_command,
    ]
    assert record["details"]["commands"]["restore_criu_runc_conf_original"]["stdin"] == "original\n"



def test_smoke_preemption_reports_cleanup_failed_when_original_restore_fails():
    from ai_runtime_experiments.preemption import collect_smoke_preemption

    container_name = "ai-edge-v0-vllm-fixed"
    inspect_command = ["docker", "inspect", "--format", "{{json .Config.Labels}}", container_name]
    capture_original_command = ["sudo", "-n", "cat", "/etc/criu/runc.conf"]
    write_command = ["sudo", "-n", "tee", "/etc/criu/runc.conf"]
    checkpoint_command = ["docker", "checkpoint", "create", container_name, "cp1"]
    start_command = ["docker", "start", "--checkpoint", "cp1", container_name]
    state_command = ["docker", "inspect", "--format", "{{.State.Status}}", container_name]

    runner = RecordingRunner(
        {
            tuple(inspect_command): _result(
                inspect_command,
                status=ProbeStatus.OK,
                stdout=(
                    '{"ai-edge-experiment":"v0",'
                    '"ai-edge-component":"vllm-runtime",'
                    '"ai-edge-run-id":"task-8"}\n'
                ),
            ),
            tuple(capture_original_command): _result(
                capture_original_command,
                status=ProbeStatus.OK,
                stdout="original\n",
            ),
            tuple(write_command): [
                _result(write_command, status=ProbeStatus.OK, stdout="ok\n"),
                _result(write_command, status=ProbeStatus.OK, stdout="ok\n"),
                _result(
                    write_command,
                    status=ProbeStatus.ERROR,
                    returncode=1,
                    stderr="restore original failed\n",
                    error_type="RuntimeError",
                    error_message="restore original failed",
                ),
            ],
            tuple(checkpoint_command): _result(
                checkpoint_command,
                status=ProbeStatus.OK,
                stdout="cp1\n",
            ),
            tuple(start_command): _result(
                start_command,
                status=ProbeStatus.OK,
                stdout=container_name + "\n",
            ),
            tuple(state_command): _result(
                state_command,
                status=ProbeStatus.OK,
                stdout="running\n",
            ),
        }
    )

    record = collect_smoke_preemption(
        run_id="task-8",
        runtime_session=_runtime_session(container_name=container_name),
        docker_criu_integration=_docker_criu_probe(),
        runner=runner,
        checkpoint_name="cp1",
        post_checkpoint_delay_s=0,
        criu_config_mode="cdi_restore_compat",
        criu_config_allow_sudo=True,
    )

    assert record["status"] == "error"
    assert record["details"]["outcome"] == "cleanup_failed"
    assert "restore_original" in record["details"]["reason"]
    assert (
        record["details"]["commands"]["restore_criu_runc_conf_original"]["status"]
        == "error"
    )
    assert (
        record["details"]["diagnostics"]["criu_config"]["restore_original"]["status"]
        == "error"
    )



def test_smoke_preemption_reports_cleanup_failed_when_lock_release_fails(monkeypatch):
    import ai_runtime_experiments.preemption.smoke as smoke_module

    container_name = "ai-edge-v0-vllm-fixed"
    inspect_command = ["docker", "inspect", "--format", "{{json .Config.Labels}}", container_name]
    checkpoint_command = ["docker", "checkpoint", "create", container_name, "cp1"]
    start_command = ["docker", "start", "--checkpoint", "cp1", container_name]
    state_command = ["docker", "inspect", "--format", "{{.State.Status}}", container_name]

    runner = RecordingRunner(
        {
            tuple(inspect_command): _result(
                inspect_command,
                status=ProbeStatus.OK,
                stdout=(
                    '{"ai-edge-experiment":"v0",'
                    '"ai-edge-component":"vllm-runtime",'
                    '"ai-edge-run-id":"task-8"}\n'
                ),
            ),
            tuple(checkpoint_command): _result(
                checkpoint_command,
                status=ProbeStatus.OK,
                stdout="cp1\n",
            ),
            tuple(start_command): _result(
                start_command,
                status=ProbeStatus.OK,
                stdout=container_name + "\n",
            ),
            tuple(state_command): _result(
                state_command,
                status=ProbeStatus.OK,
                stdout="running\n",
            ),
        }
    )

    class FakeSwitcher:
        def __init__(self, *, runner, timeout_s, use_sudo):
            del runner, timeout_s, use_sudo
            self.lock_result = _result(["flock", "/tmp/mock.lock"], status=ProbeStatus.OK)
            self.capture_original_result = _result(
                ["cat", "/etc/criu/runc.conf"], status=ProbeStatus.OK, stdout="original\n"
            )
            self.restore_original_result = None
            self.release_result = None
            self.original_text = "original\n"
            self.original_exists = True
            self.diagnostics = {
                "lock": {
                    "path": "/tmp/mock.lock",
                    "status": "ok",
                    "acquired": True,
                },
                "original": {
                    "path": "/etc/criu/runc.conf",
                    "status": "ok",
                    "exists": True,
                },
                "restore_original": {
                    "path": "/etc/criu/runc.conf",
                    "status": "not_attempted",
                },
            }

        def acquire(self):
            return self.lock_result

        def write_phase(self, phase):
            return _result(
                ["tee", "/etc/criu/runc.conf", phase],
                status=ProbeStatus.OK,
                stdout="ok\n",
            )

        def restore_original(self):
            self.restore_original_result = _result(
                ["tee", "/etc/criu/runc.conf"],
                status=ProbeStatus.OK,
                stdout="ok\n",
            )
            self.diagnostics["restore_original"].update({
                "status": "ok",
                "exists": True,
            })
            return self.restore_original_result

        def release(self):
            self.release_result = _result(
                ["funlock", "/tmp/mock.lock"],
                status=ProbeStatus.ERROR,
                returncode=1,
                stderr="release failed\n",
                error_type="RuntimeError",
                error_message="release failed",
            )
            self.diagnostics["lock"].update({
                "released": False,
                "release_error": "release failed",
            })
            return self.release_result

    monkeypatch.setattr(smoke_module, "CriuRuncConfigPhaseSwitcher", FakeSwitcher)

    record = smoke_module.collect_smoke_preemption(
        run_id="task-8",
        runtime_session=_runtime_session(container_name=container_name),
        docker_criu_integration=_docker_criu_probe(),
        runner=runner,
        checkpoint_name="cp1",
        post_checkpoint_delay_s=0,
        criu_config_mode="cdi_restore_compat",
        criu_config_allow_sudo=True,
    )

    assert record["status"] == "error"
    assert record["details"]["outcome"] == "cleanup_failed"
    assert "release_lock" in record["details"]["reason"]
    assert (
        record["details"]["commands"]["release_criu_runc_conf_lock"]["status"]
        == "error"
    )
