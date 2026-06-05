from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "experiments" / "scripts" / "collect_hardware.py"
EXPERIMENTS_SRC = REPO_ROOT / "experiments" / "src"


def _run_collect_hardware(*, output_dir: Path, run_id: str) -> subprocess.CompletedProcess[str]:
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
        timeout=120,
    )


def test_real_host_probe_cli_writes_artifacts(tmp_path: Path) -> None:
    output_dir = tmp_path / "host-probe"
    run_id = "task-10-host-real"

    result = _run_collect_hardware(output_dir=output_dir, run_id=run_id)

    assert result.returncode == 0, (
        f"collect_hardware.py failed with code {result.returncode}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    hardware = json.loads((output_dir / "hardware.json").read_text(encoding="utf-8"))
    docker = json.loads((output_dir / "docker.json").read_text(encoding="utf-8"))

    assert hardware["component"] == "hardware"
    assert hardware["run_id"] == run_id
    assert hardware["details"]["commands"]["uname_a"]["argv"] == ["uname", "-a"]
    assert hardware["details"]["commands"]["uname_a"]["status"] == "ok"
    assert hardware["details"]["commands"]["python_version"]["argv"] == ["python", "--version"]
    assert "python_version" in hardware["details"]["extracted"]

    assert docker["component"] == "docker"
    assert docker["run_id"] == run_id
    assert docker["details"]["commands"]["docker_version"]["argv"] == ["docker", "version"]
    assert docker["status"] in {"ok", "unsupported", "error", "timeout"}
    if docker["status"] != "ok":
        assert "reason" in docker["details"]
