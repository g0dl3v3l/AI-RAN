"""Test remote run command rendering via deploy_and_run_remote.sh."""

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "deploy_and_run_remote.sh"


def test_run_stage_renders_trace_paths():
    """Verify run stage passes trace paths to remote CLI."""
    result = subprocess.run(
        [
            "bash",
            str(SCRIPT_PATH),
            "--stage", "run",
            "--run-id", "test-run",
            "--models", "opt-125m",
            "--chunk-sizes", "32",
            "--sequence-lengths", "128",
            "--ldpc-trace", "/remote/path/ldpc.csv",
            "--ran-ctrl-trace", "/remote/path/ran.csv",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    output = result.stdout + result.stderr
    
    # Verify trace paths are in command
    assert "/remote/path/ldpc.csv" in output
    assert "/remote/path/ran.csv" in output
    # Verify run-all is called
    assert "run-all" in output


def test_run_stage_passes_run_root():
    """Verify run stage passes correct run root to remote CLI."""
    result = subprocess.run(
        [
            "bash",
            str(SCRIPT_PATH),
            "--stage", "run",
            "--run-id", "exp-001",
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
    
    # Verify run root is passed
    assert "exp-001" in output or "runs" in output


def test_run_stage_includes_model_list():
    """Verify multiple models are passed to run-all."""
    result = subprocess.run(
        [
            "bash",
            str(SCRIPT_PATH),
            "--stage", "run",
            "--run-id", "test-models",
            "--models", "opt-125m", "opt-350m", "opt-1.3b",
            "--chunk-sizes", "32", "64",
            "--sequence-lengths", "128", "256",
            "--ldpc-trace", "/tmp/ldpc.csv",
            "--ran-ctrl-trace", "/tmp/ran.csv",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    output = result.stdout + result.stderr
    
    # Verify all models are in output
    assert "opt-125m" in output
    assert "opt-350m" in output
    assert "opt-1.3b" in output


def test_all_stage_calls_run():
    """Verify 'all' stage includes run stage with correct paths."""
    result = subprocess.run(
        [
            "bash",
            str(SCRIPT_PATH),
            "--stage", "all",
            "--run-id", "test-all-run",
            "--models", "opt-125m",
            "--chunk-sizes", "32",
            "--sequence-lengths", "128",
            "--ldpc-trace", "/path/ldpc.csv",
            "--ran-ctrl-trace", "/path/ran.csv",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    output = result.stdout + result.stderr
    
    # Should have all stages
    assert "Starting sync stage" in output
    assert "Starting bootstrap stage" in output
    assert "Starting run stage" in output
    assert "Starting fetch stage" in output


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
