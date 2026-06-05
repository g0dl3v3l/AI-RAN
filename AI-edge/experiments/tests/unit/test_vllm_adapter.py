from __future__ import annotations

from ai_runtime_experiments.schemas import ProbeStatus, SmokeClassification
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


DEFAULT_IMAGE = "vllm/vllm-openai:latest"
DEFAULT_MODEL = "meta-llama/Llama-3-8B-Instruct"


def test_runtime_disabled_is_skipped():
    from ai_runtime_experiments.runtime_adapters.vllm import VLLMRuntimeAdapter

    runner = RecordingRunner({})
    adapter = VLLMRuntimeAdapter(config={}, runner=runner)

    session = adapter.start(run_id="task-7")

    assert session.runtime == "vllm"
    assert session.mode == "skipped"
    assert session.status == ProbeStatus.SKIPPED
    assert session.base_url is None
    assert session.runtime_check["component"] == "runtime_check"
    assert session.runtime_check["status"] == "skipped"
    assert session.runtime_check["details"]["runtime"] == "vllm"
    assert session.smoke_validation is not None
    assert session.smoke_validation["status"] == "skipped"
    assert (
        session.smoke_validation["classification"]
        == SmokeClassification.SMOKE_NOT_ATTEMPTED.value
    )
    assert runner.calls == []


def test_external_server_uses_configured_base_url_after_models_readiness_probe():
    from ai_runtime_experiments.runtime_adapters.vllm import VLLMRuntimeAdapter

    probe_calls: list[dict[str, object]] = []

    def readiness_probe(*, base_url: str, timeout_s: float):
        probe_calls.append({"base_url": base_url, "timeout_s": timeout_s})
        return ProbeStatus.OK, {
            "models_url": f"{base_url}/models",
            "attempts": 2,
        }

    runner = RecordingRunner({})
    adapter = VLLMRuntimeAdapter(
        config={
            "external_server": {
                "enabled": True,
                "base_url": "http://localhost:8000/v1/",
            }
        },
        runner=runner,
        timeout_s=12.0,
        readiness_probe=readiness_probe,
    )

    session = adapter.start(run_id="task-7")

    assert session.mode == "external_server"
    assert session.status == ProbeStatus.OK
    assert session.base_url == "http://localhost:8000/v1"
    assert session.runtime_check["status"] == "ok"
    assert session.runtime_check["details"]["base_url"] == "http://localhost:8000/v1"
    assert session.runtime_check["details"]["models_url"] == "http://localhost:8000/v1/models"
    assert session.runtime_check["details"]["attempts"] == 2
    assert session.smoke_validation is None
    assert runner.calls == []
    assert probe_calls == [{"base_url": "http://localhost:8000/v1", "timeout_s": 12.0}]



def test_external_server_returns_timeout_when_models_endpoint_never_becomes_ready():
    from ai_runtime_experiments.runtime_adapters.vllm import VLLMRuntimeAdapter

    probe_calls: list[dict[str, object]] = []

    def readiness_probe(*, base_url: str, timeout_s: float):
        probe_calls.append({"base_url": base_url, "timeout_s": timeout_s})
        return ProbeStatus.TIMEOUT, {
            "models_url": f"{base_url}/models",
            "attempts": 3,
            "reason": "timed out waiting for /v1/models",
        }

    runner = RecordingRunner({})
    adapter = VLLMRuntimeAdapter(
        config={
            "external_server": {
                "enabled": True,
                "base_url": "http://localhost:8000/v1/",
            }
        },
        runner=runner,
        timeout_s=5.0,
        readiness_probe=readiness_probe,
    )

    session = adapter.start(run_id="task-7")

    assert session.mode == "external_server"
    assert session.status == ProbeStatus.TIMEOUT
    assert session.base_url is None
    assert session.runtime_check["status"] == "timeout"
    assert session.runtime_check["details"]["models_url"] == "http://localhost:8000/v1/models"
    assert session.runtime_check["details"]["attempts"] == 3
    assert session.runtime_check["details"]["reason"] == "timed out waiting for /v1/models"
    assert session.smoke_validation is not None
    assert session.smoke_validation["status"] == "timeout"
    assert (
        session.smoke_validation["classification"]
        == SmokeClassification.SMOKE_HUNG.value
    )
    assert runner.calls == []
    assert probe_calls == [{"base_url": "http://localhost:8000/v1", "timeout_s": 5.0}]


def test_docker_server_start_returns_localhost_session_after_models_readiness_probe():
    from ai_runtime_experiments.runtime_adapters.vllm import VLLMRuntimeAdapter

    command = [
        "docker",
        "run",
        "-d",
        "--name",
        "ai-edge-v0-vllm-fixed",
        "--label",
        "ai-edge-experiment=v0",
        "--label",
        "ai-edge-component=vllm-runtime",
        "--label",
        "ai-edge-run-id=task-7",
        "-p",
        "127.0.0.1:8012:8000",
        "--gpus",
        "all",
        DEFAULT_IMAGE,
        "vllm",
        "serve",
        DEFAULT_MODEL,
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
    ]
    probe_calls: list[dict[str, object]] = []

    def readiness_probe(*, base_url: str, timeout_s: float):
        probe_calls.append({"base_url": base_url, "timeout_s": timeout_s})
        return ProbeStatus.OK, {
            "models_url": f"{base_url}/models",
            "attempts": 2,
        }

    runner = RecordingRunner(
        {
            tuple(command): _result(
                command,
                status=ProbeStatus.OK,
                stdout="container-123\n",
            )
        }
    )
    adapter = VLLMRuntimeAdapter(
        config={
            "docker_server": {
                "enabled": True,
                "image": DEFAULT_IMAGE,
                "model": DEFAULT_MODEL,
                "port": 8012,
                "container_name": "ai-edge-v0-vllm-fixed",
            }
        },
        runner=runner,
        timeout_s=9.0,
        readiness_probe=readiness_probe,
    )

    session = adapter.start(run_id="task-7")

    assert session.mode == "docker_server"
    assert session.status == ProbeStatus.OK
    assert session.base_url == "http://127.0.0.1:8012/v1"
    assert session.container_name == "ai-edge-v0-vllm-fixed"
    assert session.container_id == "container-123"
    assert session.runtime_check["details"]["container"]["image"] == DEFAULT_IMAGE
    assert session.runtime_check["details"]["container"]["id"] == "container-123"
    assert session.runtime_check["details"]["models_url"] == "http://127.0.0.1:8012/v1/models"
    assert session.runtime_check["details"]["attempts"] == 2
    assert runner.calls == [command]
    assert probe_calls == [{"base_url": "http://127.0.0.1:8012/v1", "timeout_s": 9.0}]



def test_docker_server_returns_timeout_when_models_endpoint_never_becomes_ready():
    from ai_runtime_experiments.runtime_adapters.vllm import VLLMRuntimeAdapter

    command = [
        "docker",
        "run",
        "-d",
        "--name",
        "ai-edge-v0-vllm-fixed",
        "--label",
        "ai-edge-experiment=v0",
        "--label",
        "ai-edge-component=vllm-runtime",
        "--label",
        "ai-edge-run-id=task-7",
        "-p",
        "127.0.0.1:8012:8000",
        "--gpus",
        "all",
        DEFAULT_IMAGE,
        "vllm",
        "serve",
        DEFAULT_MODEL,
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
    ]
    probe_calls: list[dict[str, object]] = []

    def readiness_probe(*, base_url: str, timeout_s: float):
        probe_calls.append({"base_url": base_url, "timeout_s": timeout_s})
        return ProbeStatus.TIMEOUT, {
            "models_url": f"{base_url}/models",
            "attempts": 4,
            "reason": "timed out waiting for /v1/models",
        }

    runner = RecordingRunner(
        {
            tuple(command): _result(
                command,
                status=ProbeStatus.OK,
                stdout="container-123\n",
            )
        }
    )
    adapter = VLLMRuntimeAdapter(
        config={
            "docker_server": {
                "enabled": True,
                "image": DEFAULT_IMAGE,
                "model": DEFAULT_MODEL,
                "port": 8012,
                "container_name": "ai-edge-v0-vllm-fixed",
            }
        },
        runner=runner,
        timeout_s=6.0,
        readiness_probe=readiness_probe,
    )

    session = adapter.start(run_id="task-7")

    assert session.mode == "docker_server"
    assert session.status == ProbeStatus.TIMEOUT
    assert session.base_url is None
    assert session.container_name == "ai-edge-v0-vllm-fixed"
    assert session.container_id == "container-123"
    assert session.runtime_check["status"] == "timeout"
    assert session.runtime_check["details"]["models_url"] == "http://127.0.0.1:8012/v1/models"
    assert session.runtime_check["details"]["attempts"] == 4
    assert session.runtime_check["details"]["reason"] == "timed out waiting for /v1/models"
    assert session.smoke_validation is not None
    assert session.smoke_validation["status"] == "timeout"
    assert (
        session.smoke_validation["classification"]
        == SmokeClassification.SMOKE_HUNG.value
    )
    assert runner.calls == [command]
    assert probe_calls == [{"base_url": "http://127.0.0.1:8012/v1", "timeout_s": 6.0}]


def test_docker_server_missing_binary_is_unsupported():
    from ai_runtime_experiments.runtime_adapters import VLLMRuntimeAdapter

    command = [
        "docker",
        "run",
        "-d",
        "--name",
        "ai-edge-v0-vllm-fixed",
        "--label",
        "ai-edge-experiment=v0",
        "--label",
        "ai-edge-component=vllm-runtime",
        "--label",
        "ai-edge-run-id=task-7",
        "-p",
        "127.0.0.1:8000:8000",
        "--gpus",
        "all",
        DEFAULT_IMAGE,
        "vllm",
        "serve",
        DEFAULT_MODEL,
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
    ]
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
    adapter = VLLMRuntimeAdapter(
        config={
            "docker_server": {
                "enabled": True,
                "image": DEFAULT_IMAGE,
                "model": DEFAULT_MODEL,
                "container_name": "ai-edge-v0-vllm-fixed",
            }
        },
        runner=runner,
    )

    session = adapter.start(run_id="task-7")

    assert session.status == ProbeStatus.UNSUPPORTED
    assert session.base_url is None
    assert session.runtime_check["status"] == "unsupported"
    assert session.smoke_validation is not None
    assert (
        session.smoke_validation["classification"]
        == SmokeClassification.SMOKE_NOT_SUPPORTED.value
    )



def test_docker_server_stop_refuses_non_experiment_owned_container():
    from ai_runtime_experiments.runtime_adapters import RuntimeSession
    from ai_runtime_experiments.runtime_adapters.vllm import VLLMRuntimeAdapter
    from ai_runtime_experiments.schemas import make_probe_result

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
    adapter = VLLMRuntimeAdapter(config={}, runner=runner)
    session = RuntimeSession(
        runtime="vllm",
        mode="docker_server",
        status=ProbeStatus.OK,
        runtime_check=make_probe_result(
            run_id="task-7",
            component="runtime_check",
            status=ProbeStatus.OK,
            details={"runtime": "vllm", "mode": "docker_server"},
        ),
        base_url="http://127.0.0.1:8000/v1",
        container_name="ai-edge-v0-vllm-fixed",
        container_id="container-123",
    )

    record = adapter.stop(session)

    assert record is not None
    assert record["component"] == "runtime_teardown"
    assert record["status"] == "error"
    assert "experiment-owned" in record["details"]["reason"]
    assert record["details"]["commands"]["docker_inspect_labels"]["status"] == "ok"
    assert "docker_rm_force" not in record["details"]["commands"]
    assert runner.calls == [inspect_command]
