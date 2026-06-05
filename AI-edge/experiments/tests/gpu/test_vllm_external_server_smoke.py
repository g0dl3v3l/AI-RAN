from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from urllib import request

import pytest

pytestmark = pytest.mark.gpu

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "experiments" / "scripts" / "run_smoke_request.py"
EXPERIMENTS_SRC = REPO_ROOT / "experiments" / "src"


def _load_first_model_id(base_url: str) -> str:
    with request.urlopen(f"{base_url}/models", timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))

    models = payload.get("data")
    assert isinstance(models, list) and models, payload
    model_id = models[0].get("id")
    assert isinstance(model_id, str) and model_id, payload
    return model_id


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _run_smoke_request(*, output_dir: Path, run_id: str, base_url: str, model: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(EXPERIMENTS_SRC)
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--output-dir",
            str(output_dir),
            "--run-id",
            run_id,
            "--base-url",
            base_url,
            "--model",
            model,
            "--prompt",
            "Say pong.",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )


def test_external_vllm_smoke_uses_configured_base_url(
    tmp_path: Path, external_vllm_base_url: str
) -> None:
    output_dir = tmp_path / "vllm-external"
    run_id = "task-10-vllm-external"
    model_id = _load_first_model_id(external_vllm_base_url)

    result = _run_smoke_request(
        output_dir=output_dir,
        run_id=run_id,
        base_url=external_vllm_base_url,
        model=model_id,
    )

    assert result.returncode == 0, (
        f"run_smoke_request.py failed with code {result.returncode}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    runtime_check = json.loads((output_dir / "runtime_check.json").read_text(encoding="utf-8"))
    smoke_requests = _read_jsonl(output_dir / "smoke_request.jsonl")
    smoke_responses = _read_jsonl(output_dir / "smoke_response.jsonl")

    assert runtime_check["component"] == "runtime_check"
    assert runtime_check["status"] == "ok"
    assert runtime_check["details"]["mode"] == "external_server"
    assert runtime_check["details"]["base_url"] == external_vllm_base_url.rstrip("/")
    assert not (output_dir / "smoke_validation.json").exists()

    assert len(smoke_requests) == 1
    assert smoke_requests[0]["run_id"] == run_id
    request_payload = smoke_requests[0]["payload"]
    assert isinstance(request_payload, dict)
    assert request_payload["model"] == model_id

    assert len(smoke_responses) == 1
    assert smoke_responses[0]["run_id"] == run_id
    assert smoke_responses[0]["status"] == "ok"
    response_payload = smoke_responses[0]["response"]
    assert isinstance(response_payload, dict)
    assert response_payload["choices"]
