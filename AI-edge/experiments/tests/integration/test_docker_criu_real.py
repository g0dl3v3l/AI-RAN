from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "experiments" / "scripts" / "check_docker_criu.py"
EXPERIMENTS_SRC = REPO_ROOT / "experiments" / "src"


def _run_check_docker_criu(*, output_dir: Path, run_id: str) -> subprocess.CompletedProcess[str]:
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
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )


def test_real_docker_criu_cli_writes_artifacts(tmp_path: Path) -> None:
    output_dir = tmp_path / "docker-criu"
    run_id = "task-10-docker-criu-real"

    result = _run_check_docker_criu(output_dir=output_dir, run_id=run_id)

    assert result.returncode == 0, (
        f"check_docker_criu.py failed with code {result.returncode}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    criu_check = json.loads((output_dir / "criu_check.json").read_text(encoding="utf-8"))
    integration = json.loads(
        (output_dir / "docker_criu_integration.json").read_text(encoding="utf-8")
    )

    assert criu_check["component"] == "criu_check"
    assert criu_check["run_id"] == run_id
    assert criu_check["details"]["commands"]["criu_version"]["argv"] == ["criu", "--version"]

    assert integration["component"] == "docker_criu_integration"
    assert integration["run_id"] == run_id
    assert integration["details"]["container"]["name"].startswith("ai-edge-v0-criu-")
    assert integration["details"]["container"]["checkpoint_name"] == "ai-edge-v0-criu-checkpoint"
    assert integration["status"] in {"ok", "unsupported"}

    if integration["status"] == "ok":
        assert integration["details"]["commands"]["docker_checkpoint_help"]["status"] == "ok"
        assert integration["details"]["commands"]["docker_rm_force"]["status"] == "ok"
        assert integration["details"]["extracted"]["container_state"] == "running"
    else:
        assert "reason" in integration["details"]
