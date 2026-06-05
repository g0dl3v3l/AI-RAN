from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any

from ai_runtime_experiments.runtime_adapters import RuntimeSession
from ai_runtime_experiments.schemas import ProbeStatus, SmokeClassification, make_probe_result
from ai_runtime_experiments.workload.llm_client import LLMSmokeClient


def _write_config(path: Path, *, output_dir: Path, external_base_url: str | None = None) -> Path:
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
              base_url: {external_base_url or 'null'}
            docker_server:
              enabled: false
        """
    ).strip()
    path.write_text(rendered + "\n", encoding="utf-8")
    return path



def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))



def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]



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
    from ai_runtime_experiments.v0_orchestrator import REQUIRED_V0_ARTIFACTS, run_v0_orchestrator

    run_dir = tmp_path / "dry-run"
    config_path = _write_config(tmp_path / "config.yaml", output_dir=run_dir)
    config = load_config(config_path, dry_run=True)

    result = run_v0_orchestrator(config, git_metadata_getter=lambda **_: _git_metadata())

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
    assert smoke_validation["classification"] == SmokeClassification.SMOKE_NOT_ATTEMPTED.value

    smoke_request = _read_jsonl(run_dir / "smoke_request.jsonl")
    smoke_response = _read_jsonl(run_dir / "smoke_response.jsonl")
    assert len(smoke_request) == 1
    assert len(smoke_response) == 1
    assert smoke_response[0]["status"] == ProbeStatus.SKIPPED.value

    run_metadata = _read_json(run_dir / "run_metadata.json")
    assert run_metadata["status"] == "completed"
    assert run_metadata["dry_run"] is True
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

    monkeypatch.setattr(orchestrator, "collect_hardware_probe", lambda **_: _probe("hardware", ProbeStatus.OK))
    monkeypatch.setattr(orchestrator, "collect_docker_probe", lambda **_: _probe("docker", ProbeStatus.OK))
    monkeypatch.setattr(orchestrator, "collect_criu_probe", lambda **_: _probe("criu_check", ProbeStatus.OK))
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
    monkeypatch.setattr(orchestrator, "collect_mps_probe", lambda **_: _probe("mps_check", ProbeStatus.OK))

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

    def _transport(*, url: str, payload: dict[str, object], timeout_s: float, api_key: str):
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
    assert _read_json(run_dir / "cuda_check.json")["status"] == ProbeStatus.UNSUPPORTED.value
    assert _read_json(run_dir / "runtime_check.json")["status"] == ProbeStatus.OK.value
    assert _read_json(run_dir / "smoke_validation.json")["classification"] == (
        SmokeClassification.SMOKE_NOT_ATTEMPTED.value
    )
    assert len(_read_jsonl(run_dir / "smoke_request.jsonl")) == 1
    assert len(_read_jsonl(run_dir / "smoke_response.jsonl")) == 1
