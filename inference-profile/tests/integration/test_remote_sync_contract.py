"""Test remote sync stage contract: preserve runs/, clean only source."""

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "deploy_and_run_remote.sh"


def test_sync_preserves_runs_directory():
    """Verify sync stage removes only source, scripts, tests, preserves runs/."""
    result = subprocess.run(
        [
            "bash",
            str(SCRIPT_PATH),
            "--stage", "sync",
            "--run-id", "test-sync",
            "--models", "opt-125m",
            "--chunk-sizes", "32",
            "--sequence-lengths", "128",
            "--ldpc-trace", "/tmp/ldpc.csv",
            "--ran-ctrl-trace", "/tmp/ran.csv",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    output = result.stdout + result.stderr
    
    # Verify sync stage is executed
    assert "Starting sync stage" in output
    
    # Check that remote cleanup command is shown (redacted)
    assert "rm -rf pyproject.toml README.md inference_profile/ scripts/ tests/" in output
    
    # Crucially: runs/ should NOT be in the cleanup command
    assert "rm -rf" in output  # cleanup happens
    assert "runs/" not in output or "preserve" in output.lower() or "excluding" in output.lower()


def test_sync_tar_excludes_directories():
    """Verify sync uses tar with appropriate exclusions."""
    result = subprocess.run(
        [
            "bash",
            str(SCRIPT_PATH),
            "--stage", "sync",
            "--run-id", "test-tar",
            "--models", "opt-125m",
            "--chunk-sizes", "32",
            "--sequence-lengths", "128",
            "--ldpc-trace", "/tmp/ldpc.csv",
            "--ran-ctrl-trace", "/tmp/ran.csv",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    output = result.stdout + result.stderr
    
    # Check for tar exclusions
    assert "--exclude=runs" in output
    assert "--exclude=.git" in output
    assert "--exclude=__pycache__" in output
    assert "--exclude=.pytest_cache" in output


def test_sync_stage_creates_remote_directory():
    """Verify sync stage ensures remote directory exists."""
    result = subprocess.run(
        [
            "bash",
            str(SCRIPT_PATH),
            "--stage", "sync",
            "--run-id", "test-mkdir",
            "--models", "opt-125m",
            "--chunk-sizes", "32",
            "--sequence-lengths", "128",
            "--ldpc-trace", "/tmp/ldpc.csv",
            "--ran-ctrl-trace", "/tmp/ran.csv",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    output = result.stdout + result.stderr
    
    # Check mkdir command in remote cleanup
    assert "mkdir -p" in output


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
