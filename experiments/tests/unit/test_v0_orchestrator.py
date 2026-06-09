from __future__ import annotations

import json
import threading
import time
import textwrap
from pathlib import Path
from typing import Any

from ai_runtime_experiments.runtime_adapters import RuntimeSession
from ai_runtime_experiments.schemas import (
    ProbeStatus,
    SmokeClassification,
    make_probe_result,
)
from ai_runtime_experiments.workload.llm_client import LLMSmokeClient


def _write_config(
    path: Path, *, output_dir: Path, external_base_url: str | None = None
) -> Path:
    rendered = textwrap.dedent(
        f"""
        experiment_id: v0_env_probe
        version: v0
        runtime: vllm
        model: meta-llama/Meta-Llama-3-8B-Instruct
        arm: env_probe
        workload:
          prompt: Respond with the exact text 'smoke ok'.
        preemption_policy:
          mode: auto
        resource_delta: {{}}
        telemetry: {{}}
        output_dir: {output_dir}
        seed: 0
        runtime_options:
          vllm:
            external_server:
              enabled: {"true" if external_base_url else "false"}
              base_url: {external_base_url or "null"}
            docker_server:
              enabled: false
        """
    ).strip()
    path.write_text(rendered + "\n", encoding="utf-8")
    return path


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _git_metadata() -> dict[str, object]:
    return {
        "git_available": True,
        "is_repo": True,
        "toplevel": "/repo",
        "commit": "abc123",
        "branch": "main",
        "dirty": False,
        "describe": "abc123",
        "remote_origin_url": "git@example.com:repo.git",
        "errors": [],
    }


def test_dry_run_creates_all_required_v0_artifacts(tmp_path: Path):
    from ai_runtime_experiments.config import load_config
    from ai_runtime_experiments.v0_orchestrator import (
        REQUIRED_V0_ARTIFACTS,
        run_v0_orchestrator,
    )

    run_dir = tmp_path / "dry-run"
    config_path = _write_config(tmp_path / "config.yaml", output_dir=run_dir)
    config = load_config(config_path, dry_run=True)

    result = run_v0_orchestrator(
        config, git_metadata_getter=lambda **_: _git_metadata()
    )

    assert result.run_dir == run_dir.resolve()
    found = {path.name for path in run_dir.iterdir() if path.is_file()}
    assert found == REQUIRED_V0_ARTIFACTS

    runtime_check = _read_json(run_dir / "runtime_check.json")
    assert runtime_check["status"] == ProbeStatus.SKIPPED.value
    assert runtime_check["component"] == "runtime_check"

    smoke_preemption = _read_json(run_dir / "smoke_preemption.json")
    assert smoke_preemption["status"] == ProbeStatus.SKIPPED.value
    assert smoke_preemption["details"]["outcome"] == "not_attempted"

    smoke_validation = _read_json(run_dir / "smoke_validation.json")
    assert smoke_validation["status"] == ProbeStatus.SKIPPED.value
    assert (
        smoke_validation["classification"]
        == SmokeClassification.SMOKE_NOT_ATTEMPTED.value
    )

    smoke_request = _read_jsonl(run_dir / "smoke_request.jsonl")
    smoke_response = _read_jsonl(run_dir / "smoke_response.jsonl")
    assert len(smoke_request) == 1
    assert len(smoke_response) == 1
    assert smoke_response[0]["status"] == ProbeStatus.SKIPPED.value

    run_metadata = _read_json(run_dir / "run_metadata.json")
    assert run_metadata["status"] == "completed"
    assert run_metadata["dry_run"] is True
    assert run_metadata["model"] == "meta-llama/Meta-Llama-3-8B-Instruct"
    assert run_metadata["git"]["commit"] == "abc123"


def test_unsupported_probe_does_not_abort_orchestration(tmp_path: Path, monkeypatch):
    from ai_runtime_experiments.config import load_config
    import ai_runtime_experiments.v0_orchestrator as orchestrator

    run_dir = tmp_path / "unsupported-run"
    config_path = _write_config(
        tmp_path / "config.yaml",
        output_dir=run_dir,
        external_base_url="http://127.0.0.1:8000/v1",
    )
    config = load_config(config_path)

    def _probe(component: str, status: ProbeStatus) -> dict[str, object]:
        return make_probe_result(
            run_id=config.run_id,
            component=component,
            status=status,
            details={"reason": f"{component} -> {status.value}"},
        )

    hardware_record = make_probe_result(
        run_id=config.run_id,
        component="hardware",
        status=ProbeStatus.OK,
        details={
            "extracted": {
                "cpu_model": "AMD EPYC 7502 32-Core Processor",
                "cpu_core_count": 32,
                "system_memory_total_bytes": 137438953472,
                "vram_total_mib": 24564,
                "gpu_count": 1,
                "gpu_names": ["NVIDIA RTX A5000"],
                "driver_version": "550.54.14",
                "cuda_version": "12.4",
            }
        },
    )
    docker_record = make_probe_result(
        run_id=config.run_id,
        component="docker",
        status=ProbeStatus.OK,
        details={"extracted": {"client_version": "27.0.1", "server_version": "27.0.1"}},
    )
    mps_record = make_probe_result(
        run_id=config.run_id,
        component="mps_check",
        status=ProbeStatus.OK,
        details={
            "mode": "read_only",
            "daemon": {
                "control_binary": "nvidia-cuda-mps-control",
                "control_pipe_path": "/tmp/nvidia-mps/control",
                "control_pipe_exists": False,
            },
            "start_stop": {
                "allowed": False,
                "attempted": False,
                "started_by_probe": False,
            },
        },
    )

    monkeypatch.setattr(
        orchestrator, "collect_hardware_probe", lambda **_: hardware_record
    )
    monkeypatch.setattr(orchestrator, "collect_docker_probe", lambda **_: docker_record)
    monkeypatch.setattr(
        orchestrator,
        "collect_criu_probe",
        lambda **_: _probe("criu_check", ProbeStatus.OK),
    )
    monkeypatch.setattr(
        orchestrator,
        "collect_docker_criu_integration",
        lambda **_: _probe("docker_criu_integration", ProbeStatus.OK),
    )
    monkeypatch.setattr(
        orchestrator,
        "collect_cuda_container_probe",
        lambda **_: _probe("cuda_check", ProbeStatus.UNSUPPORTED),
    )
    monkeypatch.setattr(orchestrator, "collect_mps_probe", lambda **_: mps_record)

    class FakeRuntimeAdapter:
        def __init__(self, *, config, runner=None, timeout_s=30.0):
            del config, runner, timeout_s

        def start(self, *, run_id: str) -> RuntimeSession:
            return RuntimeSession(
                runtime="vllm",
                mode="external_server",
                status=ProbeStatus.OK,
                base_url="http://127.0.0.1:8000/v1",
                runtime_check=make_probe_result(
                    run_id=run_id,
                    component="runtime_check",
                    status=ProbeStatus.OK,
                    details={"runtime": "vllm", "mode": "external_server"},
                ),
            )

        def stop(self, session: RuntimeSession):
            del session
            return None

    monkeypatch.setattr(orchestrator, "VLLMRuntimeAdapter", FakeRuntimeAdapter)

    def _transport(
        *, url: str, payload: dict[str, object], timeout_s: float, api_key: str
    ):
        del url, payload, timeout_s, api_key
        return {"choices": [{"message": {"content": "smoke ok"}}]}

    monkeypatch.setattr(
        orchestrator,
        "LLMSmokeClient",
        lambda *args, **kwargs: LLMSmokeClient(transport=_transport),
    )
    monkeypatch.setattr(
        orchestrator,
        "collect_smoke_preemption",
        lambda **_: make_probe_result(
            run_id=config.run_id,
            component="smoke_preemption",
            status=ProbeStatus.SKIPPED,
            details={
                "reason": "runtime session has no experiment-owned container",
                "outcome": "not_attempted",
                "smoke": {"attempted": False},
                "checkpoint": {"attempted": False},
                "restore": {"attempted": False},
            },
        ),
    )

    result = orchestrator.run_v0_orchestrator(
        config,
        git_metadata_getter=lambda **_: _git_metadata(),
    )

    assert result.metadata["status"] == "completed"
    assert (
        _read_json(run_dir / "cuda_check.json")["status"]
        == ProbeStatus.UNSUPPORTED.value
    )
    assert _read_json(run_dir / "runtime_check.json")["status"] == ProbeStatus.OK.value
    assert _read_json(run_dir / "smoke_validation.json")["classification"] == (
        SmokeClassification.SMOKE_NOT_ATTEMPTED.value
    )
    assert len(_read_jsonl(run_dir / "smoke_request.jsonl")) == 1
    assert len(_read_jsonl(run_dir / "smoke_response.jsonl")) == 1

    run_metadata = _read_json(run_dir / "run_metadata.json")
    assert run_metadata["model"] == config.model
    assert run_metadata["gpu_names"] == ["NVIDIA RTX A5000"]
    assert run_metadata["driver_version"] == "550.54.14"
    assert run_metadata["cuda_version"] == "12.4"
    assert run_metadata["docker_version"] == "27.0.1"
    assert run_metadata["mps_summary"]["status"] == ProbeStatus.OK.value
    assert run_metadata["mps_summary"]["mode"] == "read_only"
    assert run_metadata["mps_summary"]["allow_start_stop"] is False
    assert run_metadata["mps_summary"]["control_binary"] == "nvidia-cuda-mps-control"
    assert run_metadata["mps_summary"]["control_pipe_path"] == "/tmp/nvidia-mps/control"
    assert run_metadata["mps_summary"]["control_pipe_exists"] is False
    assert (
        run_metadata["hardware_summary"]["cpu_model"]
        == "AMD EPYC 7502 32-Core Processor"
    )
    assert run_metadata["hardware_summary"]["cpu_core_count"] == 32
    assert run_metadata["hardware_summary"]["system_memory_total_bytes"] == 137438953472
    assert run_metadata["hardware_summary"]["vram_total_mib"] == 24564


def test_missing_top_level_model_writes_skipped_smoke_placeholders(
    tmp_path: Path, monkeypatch
):
    from ai_runtime_experiments.config import load_config
    import ai_runtime_experiments.v0_orchestrator as orchestrator

    run_dir = tmp_path / "missing-model-run"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        textwrap.dedent(
            f"""
            experiment_id: v0_env_probe
            version: v0
            runtime: vllm
            model: null
            arm: env_probe
            workload:
              prompt: Respond with the exact text 'smoke ok'.
            preemption_policy:
              mode: auto
            resource_delta: {{}}
            telemetry: {{}}
            output_dir: {run_dir}
            seed: 0
            runtime_options:
              vllm:
                external_server:
                  enabled: true
                  base_url: http://127.0.0.1:8000/v1
                docker_server:
                  enabled: false
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    config = load_config(config_path)

    def _probe(component: str, status: ProbeStatus) -> dict[str, object]:
        return make_probe_result(
            run_id=config.run_id,
            component=component,
            status=status,
            details={"reason": f"{component} -> {status.value}"},
        )

    monkeypatch.setattr(
        orchestrator,
        "collect_hardware_probe",
        lambda **_: _probe("hardware", ProbeStatus.OK),
    )
    monkeypatch.setattr(
        orchestrator,
        "collect_docker_probe",
        lambda **_: _probe("docker", ProbeStatus.OK),
    )
    monkeypatch.setattr(
        orchestrator,
        "collect_criu_probe",
        lambda **_: _probe("criu_check", ProbeStatus.OK),
    )
    monkeypatch.setattr(
        orchestrator,
        "collect_docker_criu_integration",
        lambda **_: _probe("docker_criu_integration", ProbeStatus.OK),
    )
    monkeypatch.setattr(
        orchestrator,
        "collect_cuda_container_probe",
        lambda **_: _probe("cuda_check", ProbeStatus.OK),
    )
    monkeypatch.setattr(
        orchestrator,
        "collect_mps_probe",
        lambda **_: _probe("mps_check", ProbeStatus.OK),
    )

    class FakeRuntimeAdapter:
        def __init__(self, *, config, runner=None, timeout_s=30.0):
            del config, runner, timeout_s

        def start(self, *, run_id: str) -> RuntimeSession:
            return RuntimeSession(
                runtime="vllm",
                mode="external_server",
                status=ProbeStatus.OK,
                base_url="http://127.0.0.1:8000/v1",
                runtime_check=make_probe_result(
                    run_id=run_id,
                    component="runtime_check",
                    status=ProbeStatus.OK,
                    details={"runtime": "vllm", "mode": "external_server"},
                ),
            )

        def stop(self, session: RuntimeSession):
            del session
            return None

    monkeypatch.setattr(orchestrator, "VLLMRuntimeAdapter", FakeRuntimeAdapter)
    monkeypatch.setattr(
        orchestrator,
        "collect_smoke_preemption",
        lambda **_: make_probe_result(
            run_id=config.run_id,
            component="smoke_preemption",
            status=ProbeStatus.SKIPPED,
            details={
                "reason": "runtime session has no experiment-owned container",
                "outcome": "not_attempted",
                "smoke": {"attempted": False},
                "checkpoint": {"attempted": False},
                "restore": {"attempted": False},
            },
        ),
    )

    result = orchestrator.run_v0_orchestrator(
        config,
        git_metadata_getter=lambda **_: _git_metadata(),
    )

    assert result.metadata["status"] == "completed"
    assert _read_json(run_dir / "runtime_check.json")["status"] == ProbeStatus.OK.value
    smoke_request = _read_jsonl(run_dir / "smoke_request.jsonl")
    smoke_response = _read_jsonl(run_dir / "smoke_response.jsonl")
    assert smoke_request[0]["status"] == ProbeStatus.SKIPPED.value
    assert smoke_response[0]["status"] == ProbeStatus.SKIPPED.value
    assert "model is not configured" in smoke_request[0]["details"]["reason"]
    assert "model is not configured" in smoke_response[0]["details"]["reason"]


def test_preemption_is_attempted_while_smoke_request_is_in_flight(
    tmp_path: Path, monkeypatch
):
    from ai_runtime_experiments.config import load_config
    import ai_runtime_experiments.v0_orchestrator as orchestrator

    run_dir = tmp_path / "in-flight-preemption-run"
    config_path = _write_config(
        tmp_path / "config.yaml",
        output_dir=run_dir,
        external_base_url="http://127.0.0.1:8000/v1",
    )
    config = load_config(config_path)

    def _probe(component: str, status: ProbeStatus) -> dict[str, object]:
        return make_probe_result(
            run_id=config.run_id,
            component=component,
            status=status,
            details={"reason": f"{component} -> {status.value}"},
        )

    monkeypatch.setattr(
        orchestrator,
        "collect_hardware_probe",
        lambda **_: _probe("hardware", ProbeStatus.OK),
    )
    monkeypatch.setattr(
        orchestrator,
        "collect_docker_probe",
        lambda **_: _probe("docker", ProbeStatus.OK),
    )
    monkeypatch.setattr(
        orchestrator,
        "collect_criu_probe",
        lambda **_: _probe("criu_check", ProbeStatus.OK),
    )
    monkeypatch.setattr(
        orchestrator,
        "collect_docker_criu_integration",
        lambda **_: _probe("docker_criu_integration", ProbeStatus.OK),
    )
    monkeypatch.setattr(
        orchestrator,
        "collect_cuda_container_probe",
        lambda **_: _probe("cuda_check", ProbeStatus.OK),
    )
    monkeypatch.setattr(
        orchestrator,
        "collect_mps_probe",
        lambda **_: _probe("mps_check", ProbeStatus.OK),
    )

    class FakeRuntimeAdapter:
        def __init__(self, *, config, runner=None, timeout_s=30.0):
            del config, runner, timeout_s

        def start(self, *, run_id: str) -> RuntimeSession:
            return RuntimeSession(
                runtime="vllm",
                mode="docker_server",
                status=ProbeStatus.OK,
                base_url="http://127.0.0.1:8000/v1",
                container_name="owned-runtime",
                container_id="container-id",
                runtime_check=make_probe_result(
                    run_id=run_id,
                    component="runtime_check",
                    status=ProbeStatus.OK,
                    details={"runtime": "vllm", "mode": "docker_server"},
                ),
            )

        def stop(self, session: RuntimeSession):
            del session
            return None

    monkeypatch.setattr(orchestrator, "VLLMRuntimeAdapter", FakeRuntimeAdapter)

    request_in_flight = threading.Event()
    release_response = threading.Event()
    events: list[str] = []

    def _transport(
        *, url: str, payload: dict[str, object], timeout_s: float, api_key: str
    ):
        del url, payload, timeout_s, api_key
        events.append("transport_started")
        request_in_flight.set()
        release_response.wait(timeout=0.2)
        events.append("transport_finished")
        return {"choices": [{"message": {"content": "smoke ok"}}]}

    monkeypatch.setattr(
        orchestrator,
        "LLMSmokeClient",
        lambda *args, **kwargs: LLMSmokeClient(transport=_transport),
    )

    def _smoke_preemption(**kwargs):
        del kwargs
        assert request_in_flight.wait(timeout=1.0)
        events.append("preemption_attempted")
        assert len(_read_jsonl(run_dir / "smoke_request.jsonl")) == 1
        response_path = run_dir / "smoke_response.jsonl"
        response_text = (
            response_path.read_text(encoding="utf-8") if response_path.exists() else ""
        )
        assert response_text.strip() == ""
        release_response.set()
        return make_probe_result(
            run_id=config.run_id,
            component="smoke_preemption",
            status=ProbeStatus.SKIPPED,
            details={
                "reason": "checkpoint and restore not exercised in this test",
                "outcome": "not_attempted",
                "smoke": {"attempted": True},
                "checkpoint": {"attempted": False},
                "restore": {"attempted": False},
            },
        )

    monkeypatch.setattr(orchestrator, "collect_smoke_preemption", _smoke_preemption)

    result = orchestrator.run_v0_orchestrator(
        config,
        git_metadata_getter=lambda **_: _git_metadata(),
    )

    assert result.metadata["status"] == "completed"
    assert events == ["transport_started", "preemption_attempted", "transport_finished"]
    assert len(_read_jsonl(run_dir / "smoke_response.jsonl")) == 1


def test_response_completed_before_restore_is_not_classified_as_post_restore_completion(
    tmp_path: Path, monkeypatch
):
    from ai_runtime_experiments.config import load_config
    import ai_runtime_experiments.v0_orchestrator as orchestrator

    run_dir = tmp_path / "restore-ordering-run"
    config_path = _write_config(
        tmp_path / "config.yaml",
        output_dir=run_dir,
        external_base_url="http://127.0.0.1:8000/v1",
    )
    config = load_config(config_path)

    def _probe(component: str, status: ProbeStatus) -> dict[str, object]:
        return make_probe_result(
            run_id=config.run_id,
            component=component,
            status=status,
            details={"reason": f"{component} -> {status.value}"},
        )

    monkeypatch.setattr(
        orchestrator,
        "collect_hardware_probe",
        lambda **_: _probe("hardware", ProbeStatus.OK),
    )
    monkeypatch.setattr(
        orchestrator,
        "collect_docker_probe",
        lambda **_: _probe("docker", ProbeStatus.OK),
    )
    monkeypatch.setattr(
        orchestrator,
        "collect_criu_probe",
        lambda **_: _probe("criu_check", ProbeStatus.OK),
    )
    monkeypatch.setattr(
        orchestrator,
        "collect_docker_criu_integration",
        lambda **_: _probe("docker_criu_integration", ProbeStatus.OK),
    )
    monkeypatch.setattr(
        orchestrator,
        "collect_cuda_container_probe",
        lambda **_: _probe("cuda_check", ProbeStatus.OK),
    )
    monkeypatch.setattr(
        orchestrator,
        "collect_mps_probe",
        lambda **_: _probe("mps_check", ProbeStatus.OK),
    )

    class FakeRuntimeAdapter:
        def __init__(self, *, config, runner=None, timeout_s=30.0):
            del config, runner, timeout_s

        def start(self, *, run_id: str) -> RuntimeSession:
            return RuntimeSession(
                runtime="vllm",
                mode="docker_server",
                status=ProbeStatus.OK,
                base_url="http://127.0.0.1:8000/v1",
                container_name="owned-runtime",
                container_id="container-id",
                runtime_check=make_probe_result(
                    run_id=run_id,
                    component="runtime_check",
                    status=ProbeStatus.OK,
                    details={"runtime": "vllm", "mode": "docker_server"},
                ),
            )

        def stop(self, session: RuntimeSession):
            del session
            return None

    monkeypatch.setattr(orchestrator, "VLLMRuntimeAdapter", FakeRuntimeAdapter)

    response_started = threading.Event()

    def _transport(
        *, url: str, payload: dict[str, object], timeout_s: float, api_key: str
    ):
        del url, payload, timeout_s, api_key
        response_started.set()
        return {"choices": [{"message": {"content": "smoke ok"}}]}

    monkeypatch.setattr(
        orchestrator,
        "LLMSmokeClient",
        lambda *args, **kwargs: LLMSmokeClient(transport=_transport),
    )

    def _wait_for_response_record() -> dict[str, Any]:
        deadline = time.monotonic() + 1.0
        response_path = run_dir / "smoke_response.jsonl"
        while time.monotonic() < deadline:
            if response_path.exists():
                records = _read_jsonl(response_path)
                if records:
                    return records[0]
            time.sleep(0.01)
        raise AssertionError(
            "smoke response record was not written before restore timing was evaluated"
        )

    def _smoke_preemption(**kwargs):
        del kwargs
        assert response_started.wait(timeout=1.0)
        response_record = _wait_for_response_record()
        response_monotonic_ns = int(response_record["monotonic_ns"])
        return make_probe_result(
            run_id=config.run_id,
            component="smoke_preemption",
            status=ProbeStatus.OK,
            details={
                "reason": "checkpoint and restore completed",
                "outcome": "restored",
                "smoke": {"attempted": True},
                "checkpoint": {"attempted": True},
                "restore": {
                    "attempted": True,
                    "start_monotonic_ns": response_monotonic_ns + 1,
                },
            },
        )

    monkeypatch.setattr(orchestrator, "collect_smoke_preemption", _smoke_preemption)

    result = orchestrator.run_v0_orchestrator(
        config,
        git_metadata_getter=lambda **_: _git_metadata(),
    )

    assert result.metadata["status"] == "completed"
    smoke_validation = _read_json(run_dir / "smoke_validation.json")
    assert smoke_validation["status"] == ProbeStatus.SKIPPED.value
    assert (
        smoke_validation["classification"]
        == SmokeClassification.SMOKE_NOT_ATTEMPTED.value
    )
    assert "before restore" in smoke_validation["details"]["reason"]


def test_response_completed_during_restore_is_not_classified_as_post_restore_completion(
    tmp_path: Path, monkeypatch
):
    from ai_runtime_experiments.config import load_config
    import ai_runtime_experiments.v0_orchestrator as orchestrator

    run_dir = tmp_path / "during-restore-ordering-run"
    config_path = _write_config(
        tmp_path / "config.yaml",
        output_dir=run_dir,
        external_base_url="http://127.0.0.1:8000/v1",
    )
    config = load_config(config_path)

    def _probe(component: str, status: ProbeStatus) -> dict[str, object]:
        return make_probe_result(
            run_id=config.run_id,
            component=component,
            status=status,
            details={"reason": f"{component} -> {status.value}"},
        )

    monkeypatch.setattr(
        orchestrator,
        "collect_hardware_probe",
        lambda **_: _probe("hardware", ProbeStatus.OK),
    )
    monkeypatch.setattr(
        orchestrator,
        "collect_docker_probe",
        lambda **_: _probe("docker", ProbeStatus.OK),
    )
    monkeypatch.setattr(
        orchestrator,
        "collect_criu_probe",
        lambda **_: _probe("criu_check", ProbeStatus.OK),
    )
    monkeypatch.setattr(
        orchestrator,
        "collect_docker_criu_integration",
        lambda **_: _probe("docker_criu_integration", ProbeStatus.OK),
    )
    monkeypatch.setattr(
        orchestrator,
        "collect_cuda_container_probe",
        lambda **_: _probe("cuda_check", ProbeStatus.OK),
    )
    monkeypatch.setattr(
        orchestrator,
        "collect_mps_probe",
        lambda **_: _probe("mps_check", ProbeStatus.OK),
    )

    class FakeRuntimeAdapter:
        def __init__(self, *, config, runner=None, timeout_s=30.0):
            del config, runner, timeout_s

        def start(self, *, run_id: str) -> RuntimeSession:
            return RuntimeSession(
                runtime="vllm",
                mode="docker_server",
                status=ProbeStatus.OK,
                base_url="http://127.0.0.1:8000/v1",
                container_name="owned-runtime",
                container_id="container-id",
                runtime_check=make_probe_result(
                    run_id=run_id,
                    component="runtime_check",
                    status=ProbeStatus.OK,
                    details={"runtime": "vllm", "mode": "docker_server"},
                ),
            )

        def stop(self, session: RuntimeSession):
            del session
            return None

    monkeypatch.setattr(orchestrator, "VLLMRuntimeAdapter", FakeRuntimeAdapter)

    response_started = threading.Event()

    def _transport(
        *, url: str, payload: dict[str, object], timeout_s: float, api_key: str
    ):
        del url, payload, timeout_s, api_key
        response_started.set()
        return {"choices": [{"message": {"content": "smoke ok"}}]}

    monkeypatch.setattr(
        orchestrator,
        "LLMSmokeClient",
        lambda *args, **kwargs: LLMSmokeClient(transport=_transport),
    )

    def _wait_for_response_record() -> dict[str, Any]:
        deadline = time.monotonic() + 1.0
        response_path = run_dir / "smoke_response.jsonl"
        while time.monotonic() < deadline:
            if response_path.exists():
                records = _read_jsonl(response_path)
                if records:
                    return records[0]
            time.sleep(0.01)
        raise AssertionError(
            "smoke response record was not written before restore timing was evaluated"
        )

    def _smoke_preemption(**kwargs):
        del kwargs
        assert response_started.wait(timeout=1.0)
        response_record = _wait_for_response_record()
        response_monotonic_ns = int(response_record["monotonic_ns"])
        return make_probe_result(
            run_id=config.run_id,
            component="smoke_preemption",
            status=ProbeStatus.OK,
            details={
                "reason": "checkpoint and restore completed",
                "outcome": "restored",
                "smoke": {"attempted": True},
                "checkpoint": {"attempted": True},
                "restore": {
                    "attempted": True,
                    "start_monotonic_ns": response_monotonic_ns - 1,
                    "end_monotonic_ns": response_monotonic_ns + 1,
                },
            },
        )

    monkeypatch.setattr(orchestrator, "collect_smoke_preemption", _smoke_preemption)

    result = orchestrator.run_v0_orchestrator(
        config,
        git_metadata_getter=lambda **_: _git_metadata(),
    )

    assert result.metadata["status"] == "completed"
    smoke_validation = _read_json(run_dir / "smoke_validation.json")
    assert smoke_validation["status"] == ProbeStatus.SKIPPED.value
    assert (
        smoke_validation["classification"]
        == SmokeClassification.SMOKE_NOT_ATTEMPTED.value
    )
    assert "after restore completion" in smoke_validation["details"]["reason"]


def test_orchestrator_uses_request_jsonl_to_prove_request_started_before_checkpoint(
    tmp_path: Path, monkeypatch
):
    from ai_runtime_experiments.config import load_config
    import ai_runtime_experiments.v0_orchestrator as orchestrator

    run_dir = tmp_path / "request-evidence-run"
    config_path = _write_config(
        tmp_path / "config.yaml",
        output_dir=run_dir,
        external_base_url="http://127.0.0.1:8000/v1",
    )
    config = load_config(config_path)

    def _probe(component: str, status: ProbeStatus) -> dict[str, object]:
        return make_probe_result(
            run_id=config.run_id,
            component=component,
            status=status,
            details={"reason": f"{component} -> {status.value}"},
        )

    monkeypatch.setattr(
        orchestrator,
        "collect_hardware_probe",
        lambda **_: _probe("hardware", ProbeStatus.OK),
    )
    monkeypatch.setattr(
        orchestrator,
        "collect_docker_probe",
        lambda **_: _probe("docker", ProbeStatus.OK),
    )
    monkeypatch.setattr(
        orchestrator,
        "collect_criu_probe",
        lambda **_: _probe("criu_check", ProbeStatus.OK),
    )
    monkeypatch.setattr(
        orchestrator,
        "collect_docker_criu_integration",
        lambda **_: _probe("docker_criu_integration", ProbeStatus.OK),
    )
    monkeypatch.setattr(
        orchestrator,
        "collect_cuda_container_probe",
        lambda **_: _probe("cuda_check", ProbeStatus.OK),
    )
    monkeypatch.setattr(
        orchestrator,
        "collect_mps_probe",
        lambda **_: _probe("mps_check", ProbeStatus.OK),
    )

    class FakeRuntimeAdapter:
        def __init__(self, *, config, runner=None, timeout_s=30.0):
            del config, runner, timeout_s

        def start(self, *, run_id: str) -> RuntimeSession:
            return RuntimeSession(
                runtime="vllm",
                mode="docker_server",
                status=ProbeStatus.OK,
                base_url="http://127.0.0.1:8000/v1",
                container_name="owned-runtime",
                container_id="container-id",
                runtime_check=make_probe_result(
                    run_id=run_id,
                    component="runtime_check",
                    status=ProbeStatus.OK,
                    details={"runtime": "vllm", "mode": "docker_server"},
                ),
            )

        def stop(self, session: RuntimeSession):
            del session
            return None

    monkeypatch.setattr(orchestrator, "VLLMRuntimeAdapter", FakeRuntimeAdapter)

    release_response = threading.Event()

    def _transport(
        *, url: str, payload: dict[str, object], timeout_s: float, api_key: str
    ):
        del url, payload, timeout_s, api_key
        release_response.wait(timeout=1.0)
        return {"choices": [{"message": {"content": "smoke ok"}}]}

    monkeypatch.setattr(
        orchestrator,
        "LLMSmokeClient",
        lambda *args, **kwargs: LLMSmokeClient(transport=_transport),
    )

    def _wait_for_request_record() -> dict[str, Any]:
        deadline = time.monotonic() + 1.0
        request_path = run_dir / "smoke_request.jsonl"
        while time.monotonic() < deadline:
            if request_path.exists():
                records = _read_jsonl(request_path)
                if records:
                    return records[0]
            time.sleep(0.01)
        raise AssertionError(
            "smoke request record was not written before checkpoint timing"
        )

    def _smoke_preemption(**kwargs):
        del kwargs
        request_record = _wait_for_request_record()
        request_monotonic_ns = int(request_record["monotonic_ns"])
        release_response.set()
        return make_probe_result(
            run_id=config.run_id,
            component="smoke_preemption",
            status=ProbeStatus.OK,
            details={
                "reason": "checkpoint and restore completed",
                "outcome": "restored",
                "smoke": {"attempted": True},
                "checkpoint": {
                    "attempted": True,
                    "start_monotonic_ns": request_monotonic_ns + 1,
                },
                "restore": {
                    "attempted": True,
                    "end_monotonic_ns": request_monotonic_ns + 2,
                },
            },
        )

    monkeypatch.setattr(orchestrator, "collect_smoke_preemption", _smoke_preemption)

    result = orchestrator.run_v0_orchestrator(
        config,
        git_metadata_getter=lambda **_: _git_metadata(),
    )

    assert result.metadata["status"] == "completed"
    smoke_preemption = _read_json(run_dir / "smoke_preemption.json")
    assert (
        smoke_preemption["details"]["smoke"]["request_started_before_checkpoint"]
        is True
    )
    smoke_validation = _read_json(run_dir / "smoke_validation.json")
    assert smoke_validation["status"] == ProbeStatus.OK.value
    assert (
        smoke_validation["classification"]
        == SmokeClassification.SMOKE_COMPLETED_AFTER_RESTORE.value
    )


def test_orchestrator_uses_llama_cpp_runtime_adapter(tmp_path: Path, monkeypatch):
    from ai_runtime_experiments.config import load_config
    import ai_runtime_experiments.v0_orchestrator as orchestrator

    run_dir = tmp_path / "llama-run"
    config_path = _write_config(tmp_path / "config.yaml", output_dir=run_dir)
    text = config_path.read_text(encoding="utf-8")
    text = text.replace("runtime: vllm", "runtime: llama_cpp")
    text = text.replace(
        "model: meta-llama/Meta-Llama-3-8B-Instruct",
        "model: gemma-3-1b-it-f16.gguf",
    )
    text += """
runtime_options:
  llama_cpp:
    external_server:
      enabled: true
      base_url: http://127.0.0.1:8080/v1
"""
    config_path.write_text(text, encoding="utf-8")
    config = load_config(config_path)

    def _probe(component: str, status: ProbeStatus) -> dict[str, object]:
        return make_probe_result(
            run_id=config.run_id,
            component=component,
            status=status,
            details={"reason": f"{component} -> {status.value}"},
        )

    monkeypatch.setattr(
        orchestrator,
        "collect_hardware_probe",
        lambda **_: _probe("hardware", ProbeStatus.OK),
    )
    monkeypatch.setattr(
        orchestrator,
        "collect_docker_probe",
        lambda **_: _probe("docker", ProbeStatus.OK),
    )
    monkeypatch.setattr(
        orchestrator,
        "collect_criu_probe",
        lambda **_: _probe("criu_check", ProbeStatus.OK),
    )
    monkeypatch.setattr(
        orchestrator,
        "collect_docker_criu_integration",
        lambda **_: _probe("docker_criu_integration", ProbeStatus.UNSUPPORTED),
    )
    monkeypatch.setattr(
        orchestrator,
        "collect_cuda_container_probe",
        lambda **_: _probe("cuda_check", ProbeStatus.OK),
    )
    monkeypatch.setattr(
        orchestrator,
        "collect_mps_probe",
        lambda **_: _probe("mps_check", ProbeStatus.OK),
    )

    class FakeLlamaCppRuntimeAdapter:
        def __init__(self, *, config, runner=None, timeout_s=30.0):
            del runner, timeout_s
            assert config["external_server"]["base_url"] == "http://127.0.0.1:8080/v1"

        def start(self, *, run_id: str) -> RuntimeSession:
            return RuntimeSession(
                runtime="llama_cpp",
                mode="external_server",
                status=ProbeStatus.OK,
                base_url="http://127.0.0.1:8080/v1",
                runtime_check=make_probe_result(
                    run_id=run_id,
                    component="runtime_check",
                    status=ProbeStatus.OK,
                    details={"runtime": "llama_cpp", "mode": "external_server"},
                ),
            )

        def stop(self, session: RuntimeSession):
            del session
            return None

    monkeypatch.setattr(
        orchestrator, "LlamaCppRuntimeAdapter", FakeLlamaCppRuntimeAdapter
    )
    monkeypatch.setattr(
        orchestrator,
        "collect_smoke_preemption",
        lambda **_: make_probe_result(
            run_id=config.run_id,
            component="smoke_preemption",
            status=ProbeStatus.SKIPPED,
            details={"outcome": "not_attempted"},
        ),
    )

    def _transport(
        *, url: str, payload: dict[str, object], timeout_s: float, api_key: str
    ):
        del url, payload, timeout_s, api_key
        return {"choices": [{"message": {"content": "smoke ok"}}]}

    monkeypatch.setattr(
        orchestrator,
        "LLMSmokeClient",
        lambda *args, **kwargs: LLMSmokeClient(transport=_transport),
    )

    result = orchestrator.run_v0_orchestrator(
        config, git_metadata_getter=lambda **_: _git_metadata()
    )

    assert result.metadata["runtime"] == "llama_cpp"
    assert (
        _read_json(run_dir / "runtime_check.json")["details"]["runtime"] == "llama_cpp"
    )
    assert _read_jsonl(run_dir / "smoke_request.jsonl")[0]["runtime"] == "llama_cpp"


def test_capture_criu_logs_copies_paths_from_failed_command_stderr(tmp_path: Path):
    from ai_runtime_experiments.v0_orchestrator import _capture_criu_logs

    source_log = tmp_path / "criu-dump.log"
    source_log.write_text("root cause from criu\n", encoding="utf-8")
    record = make_probe_result(
        run_id="run-with-criu-log",
        component="smoke_preemption",
        status=ProbeStatus.ERROR,
        details={
            "commands": {
                "docker_checkpoint_create": {
                    "stderr": (
                        "runc did not terminate successfully: criu failed: "
                        f"type DUMP errno 0 path= {source_log}\n"
                    )
                }
            }
        },
    )
    records = {"smoke_preemption.json": record}
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    _capture_criu_logs(run_dir=run_dir, records=records)

    copied = run_dir / "criu_logs" / "smoke_preemption" / "01-criu-dump.log"
    assert copied.read_text(encoding="utf-8") == "root cause from criu\n"
    assert record["details"]["diagnostics"]["criu_logs"] == [
        {
            "source_path": str(source_log),
            "destination_path": str(copied),
            "status": ProbeStatus.OK.value,
        }
    ]
