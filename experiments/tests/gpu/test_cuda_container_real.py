from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.gpu

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "experiments" / "scripts" / "check_cuda_container.py"
EXPERIMENTS_SRC = REPO_ROOT / "experiments" / "src"


def _run_check_cuda_container(*, output_dir: Path, run_id: str) -> subprocess.CompletedProcess[str]:
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
        timeout=240,
    )


def test_real_cuda_container_cli_writes_artifact(tmp_path: Path) -> None:
    output_dir = tmp_path / "cuda"
    run_id = "task-10-cuda-real"

    result = _run_check_cuda_container(output_dir=output_dir, run_id=run_id)

    assert result.returncode == 0, (
        f"check_cuda_container.py failed with code {result.returncode}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    cuda_check = json.loads((output_dir / "cuda_check.json").read_text(encoding="utf-8"))

    assert cuda_check["component"] == "cuda_check"
    assert cuda_check["run_id"] == run_id
    assert cuda_check["details"]["commands"]["docker_run_nvidia_smi"]["argv"][:4] == [
        "docker",
        "run",
        "--gpus",
        "all",
    ]
    assert cuda_check["status"] in {"ok", "unsupported"}

    if cuda_check["status"] == "ok":
        assert "driver_version" in cuda_check["details"]["extracted"]
        assert "cuda_version" in cuda_check["details"]["extracted"]
    else:
        assert "docker run --gpus all" in cuda_check["details"]["reason"]
