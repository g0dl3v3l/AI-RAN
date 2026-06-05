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
    from ai_runtime_experiments.runtime_adapters import VLLMRuntimeAdapter

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


def test_external_server_uses_configured_base_url():
    from ai_runtime_experiments.runtime_adapters import VLLMRuntimeAdapter

    runner = RecordingRunner({})
    adapter = VLLMRuntimeAdapter(
        config={
            "external_server": {
                "enabled": True,
                "base_url": "http://localhost:8000/v1/",
            }
        },
        runner=runner,
    )

    session = adapter.start(run_id="task-7")

    assert session.mode == "external_server"
    assert session.status == ProbeStatus.OK
    assert session.base_url == "http://localhost:8000/v1"
    assert session.runtime_check["status"] == "ok"
    assert session.runtime_check["details"]["base_url"] == "http://localhost:8000/v1"
    assert session.smoke_validation is None
    assert runner.calls == []


def test_docker_server_start_returns_localhost_session():
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
    )

    session = adapter.start(run_id="task-7")

    assert session.mode == "docker_server"
    assert session.status == ProbeStatus.OK
    assert session.base_url == "http://127.0.0.1:8012/v1"
    assert session.container_name == "ai-edge-v0-vllm-fixed"
    assert session.container_id == "container-123"
    assert session.runtime_check["details"]["container"]["image"] == DEFAULT_IMAGE
    assert session.runtime_check["details"]["container"]["id"] == "container-123"
    assert runner.calls == [command]


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
