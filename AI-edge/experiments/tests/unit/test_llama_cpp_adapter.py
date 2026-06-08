from __future__ import annotations

from ai_runtime_experiments.schemas import ProbeStatus, SmokeClassification
from ai_runtime_experiments.utils.command import CommandResult


DEFAULT_IMAGE = "ghcr.io/ggml-org/llama.cpp:server"
DEFAULT_MODEL_FILE = "gemma-3-1b-it-f16.gguf"
DEFAULT_MODEL_DIR = "/home/netsys/llama-models"


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


def test_runtime_disabled_is_skipped():
    from ai_runtime_experiments.runtime_adapters.llama_cpp import LlamaCppRuntimeAdapter

    runner = RecordingRunner({})
    adapter = LlamaCppRuntimeAdapter(config={}, runner=runner)

    session = adapter.start(run_id="llama-task")

    assert session.runtime == "llama_cpp"
    assert session.mode == "skipped"
    assert session.status == ProbeStatus.SKIPPED
    assert session.runtime_check["status"] == "skipped"
    assert session.smoke_validation is not None
    assert session.smoke_validation["classification"] == SmokeClassification.SMOKE_NOT_ATTEMPTED.value
    assert runner.calls == []


def test_external_server_uses_configured_base_url_after_models_readiness_probe():
    from ai_runtime_experiments.runtime_adapters.llama_cpp import LlamaCppRuntimeAdapter

    probe_calls: list[dict[str, object]] = []

    def readiness_probe(*, base_url: str, timeout_s: float):
        probe_calls.append({"base_url": base_url, "timeout_s": timeout_s})
        return ProbeStatus.OK, {"models_url": f"{base_url}/models", "attempts": 1}

    adapter = LlamaCppRuntimeAdapter(
        config={"external_server": {"enabled": True, "base_url": "http://localhost:8080/v1/"}},
        runner=RecordingRunner({}),
        timeout_s=11.0,
        readiness_probe=readiness_probe,
    )

    session = adapter.start(run_id="llama-task")

    assert session.mode == "external_server"
    assert session.status == ProbeStatus.OK
    assert session.base_url == "http://localhost:8080/v1"
    assert session.runtime_check["details"]["models_url"] == "http://localhost:8080/v1/models"
    assert probe_calls == [{"base_url": "http://localhost:8080/v1", "timeout_s": 11.0}]


def test_docker_server_start_returns_localhost_session_after_models_readiness_probe():
    from ai_runtime_experiments.runtime_adapters.llama_cpp import LlamaCppRuntimeAdapter

    image_inspect = ["docker", "image", "inspect", DEFAULT_IMAGE]
    command = [
        "docker",
        "run",
        "-d",
        "--name",
        "ai-edge-v0-llama-cpp-fixed",
        "--label",
        "ai-edge-experiment=v0",
        "--label",
        "ai-edge-component=llama-cpp-runtime",
        "--label",
        "ai-edge-run-id=llama-task",
        "--network",
        "host",
        "-v",
        f"{DEFAULT_MODEL_DIR}:/models:ro",
        DEFAULT_IMAGE,
        "-m",
        f"/models/{DEFAULT_MODEL_FILE}",
        "--host",
        "0.0.0.0",
        "--port",
        "8080",
        "--threads",
        "4",
        "--ctx-size",
        "2048",
    ]
    probe_calls: list[dict[str, object]] = []

    def readiness_probe(*, base_url: str, timeout_s: float):
        probe_calls.append({"base_url": base_url, "timeout_s": timeout_s})
        return ProbeStatus.OK, {"models_url": f"{base_url}/models", "attempts": 2}

    runner = RecordingRunner(
        {
            tuple(image_inspect): _result(image_inspect, status=ProbeStatus.OK, stdout="[]\n"),
            tuple(command): _result(command, status=ProbeStatus.OK, stdout="container-llama\n"),
        }
    )
    adapter = LlamaCppRuntimeAdapter(
        config={
            "docker_server": {
                "enabled": True,
                "image": DEFAULT_IMAGE,
                "port": 8081,
                "container_name": "ai-edge-v0-llama-cpp-fixed",
                "host_model_dir": DEFAULT_MODEL_DIR,
                "model_file": DEFAULT_MODEL_FILE,
                "threads": 4,
                "ctx_size": 2048,
                "network_mode": "host",
            }
        },
        runner=runner,
        timeout_s=9.0,
        readiness_probe=readiness_probe,
    )

    session = adapter.start(run_id="llama-task")

    assert session.mode == "docker_server"
    assert session.status == ProbeStatus.OK
    assert session.base_url == "http://127.0.0.1:8081/v1"
    assert session.container_name == "ai-edge-v0-llama-cpp-fixed"
    assert session.container_id == "container-llama"
    assert session.runtime_check["details"]["container"]["model_file"] == DEFAULT_MODEL_FILE
    assert session.runtime_check["details"]["container"]["network_mode"] == "host"
    assert runner.calls == [image_inspect, command]
    assert probe_calls == [{"base_url": "http://127.0.0.1:8081/v1", "timeout_s": 9.0}]


def test_docker_server_requires_model_file_and_host_model_dir():
    from ai_runtime_experiments.runtime_adapters.llama_cpp import LlamaCppRuntimeAdapter

    adapter = LlamaCppRuntimeAdapter(
        config={"docker_server": {"enabled": True, "model_file": DEFAULT_MODEL_FILE}},
        runner=RecordingRunner({}),
    )

    session = adapter.start(run_id="llama-task")

    assert session.status == ProbeStatus.ERROR
    assert session.runtime_check["status"] == "error"
    assert "host_model_dir and model_file" in session.runtime_check["details"]["reason"]
    assert session.smoke_validation is not None
    assert session.smoke_validation["classification"] == SmokeClassification.SMOKE_NOT_ATTEMPTED.value


def test_docker_server_stop_refuses_non_experiment_owned_container():
    from ai_runtime_experiments.runtime_adapters import RuntimeSession
    from ai_runtime_experiments.runtime_adapters.llama_cpp import LlamaCppRuntimeAdapter
    from ai_runtime_experiments.schemas import make_probe_result

    inspect_command = [
        "docker",
        "inspect",
        "--format",
        "{{json .Config.Labels}}",
        "ai-edge-v0-llama-cpp-fixed",
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
    adapter = LlamaCppRuntimeAdapter(config={}, runner=runner)
    session = RuntimeSession(
        runtime="llama_cpp",
        mode="docker_server",
        status=ProbeStatus.OK,
        runtime_check=make_probe_result(
            run_id="llama-task",
            component="runtime_check",
            status=ProbeStatus.OK,
            details={"runtime": "llama_cpp", "mode": "docker_server"},
        ),
        base_url="http://127.0.0.1:8080/v1",
        container_name="ai-edge-v0-llama-cpp-fixed",
        container_id="container-llama",
    )

    record = adapter.stop(session)

    assert record is not None
    assert record["component"] == "runtime_teardown"
    assert record["status"] == "error"
    assert "experiment-owned" in record["details"]["reason"]
    assert "docker_rm_force" not in record["details"]["commands"]
