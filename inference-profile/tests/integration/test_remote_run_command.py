from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "deploy_and_run_remote.sh"


def _run_dry_run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT_PATH), *args, "--dry-run"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_run_stage_renders_run_all_command_with_run_root_trace_paths_and_manifest_check() -> (
    None
):
    result = _run_dry_run(
        "--stage",
        "run",
        "--run-id",
        "exp-001",
        "--models",
        "opt-125m",
        "opt-350m",
        "opt-1.3b",
        "--chunk-sizes",
        "32",
        "64",
        "--sequence-lengths",
        "128",
        "256",
        "--ldpc-trace",
        "/remote/path/ldpc.csv",
        "--ran-ctrl-trace",
        "/remote/path/ran.csv",
    )
    output = result.stdout + result.stderr

    assert result.returncode == 0
    assert "python -m inference_profile.cli run-all" in output
    assert ".venv/bin/python" in output
    assert "--resume-from validate-traces" in output
    assert "/home/netsys/dheeraj/inference-profile/runs/exp-001" in output
    assert "/remote/path/ldpc.csv" in output
    assert "/remote/path/ran.csv" in output
    assert "opt-125m" in output
    assert "opt-350m" in output
    assert "opt-1.3b" in output
    assert "32" in output
    assert "64" in output
    assert "128" in output
    assert "256" in output
    assert "run_manifest.json" in output
    assert "final_status" in output


def test_all_stage_dry_run_includes_run_stage_and_manifest_success_check() -> None:
    result = _run_dry_run(
        "--stage",
        "all",
        "--run-id",
        "test-all-run",
        "--models",
        "opt-125m",
        "--chunk-sizes",
        "32",
        "--sequence-lengths",
        "128",
        "--ldpc-trace",
        "/path/ldpc.csv",
        "--ran-ctrl-trace",
        "/path/ran.csv",
    )
    output = result.stdout + result.stderr

    assert result.returncode == 0
    assert "Starting sync stage" in output
    assert "Starting bootstrap stage" in output
    assert "Starting run stage" in output
    assert "Starting fetch stage" in output
    assert "python -m inference_profile.cli run-all" in output
    assert "--resume-from validate-traces" in output
    assert "run_manifest.json" in output
    assert "final_status" in output
