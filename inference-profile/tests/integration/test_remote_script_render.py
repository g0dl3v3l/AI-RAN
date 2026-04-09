"""Test remote script rendering, option parsing, and redacted output."""

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "deploy_and_run_remote.sh"


def test_script_syntax_valid():
    """Verify bash syntax is valid."""
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT_PATH)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Syntax error: {result.stderr}"


def test_help_option():
    """Verify --help produces usage output."""
    result = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Usage:" in result.stdout
    assert "--stage" in result.stdout
    assert "--run-id" in result.stdout


def test_dry_run_redacts_password():
    """Verify --dry-run does not expose sshpass file path."""
    result = subprocess.run(
        [
            "bash",
            str(SCRIPT_PATH),
            "--stage", "sync",
            "--run-id", "test-001",
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
    # Check that password file is NOT exposed in logs
    assert ".ssh_pass" not in result.stdout
    assert ".ssh_pass" not in result.stderr
    # Check that redacted version IS present
    assert "<redacted>" in result.stdout


def test_dry_run_all_stages():
    """Verify --dry-run with 'all' stage prints all stage actions."""
    result = subprocess.run(
        [
            "bash",
            str(SCRIPT_PATH),
            "--stage", "all",
            "--run-id", "test-all",
            "--models", "opt-125m", "opt-350m",
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
    # Should have actions for sync, bootstrap, run, fetch
    output = result.stdout + result.stderr
    assert "Starting sync stage" in output
    assert "Starting bootstrap stage" in output
    assert "Starting run stage" in output
    assert "Starting fetch stage" in output


def test_models_argument_parsing():
    """Verify multiple models are parsed correctly."""
    result = subprocess.run(
        [
            "bash",
            str(SCRIPT_PATH),
            "--stage", "run",
            "--run-id", "test-models",
            "--models", "opt-125m", "opt-350m", "opt-1.3b",
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
    # Verify models appear in command
    assert "opt-125m" in output
    assert "opt-350m" in output
    assert "opt-1.3b" in output


def test_gpu_id_option():
    """Verify --gpu-id is passed through."""
    result = subprocess.run(
        [
            "bash",
            str(SCRIPT_PATH),
            "--stage", "run",
            "--run-id", "test-gpu",
            "--models", "opt-125m",
            "--chunk-sizes", "32",
            "--sequence-lengths", "128",
            "--ldpc-trace", "/tmp/ldpc.csv",
            "--ran-ctrl-trace", "/tmp/ran.csv",
            "--gpu-id", "3",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    output = result.stdout + result.stderr
    assert "--gpu-id 3" in output


def test_invalid_stage_error():
    """Verify invalid stage produces error."""
    result = subprocess.run(
        [
            "bash",
            str(SCRIPT_PATH),
            "--stage", "invalid-stage",
            "--run-id", "test-err",
            "--models", "opt-125m",
            "--chunk-sizes", "32",
            "--sequence-lengths", "128",
            "--ldpc-trace", "/tmp/ldpc.csv",
            "--ran-ctrl-trace", "/tmp/ran.csv",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "Unknown stage" in result.stderr or "Unknown stage" in result.stdout


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
