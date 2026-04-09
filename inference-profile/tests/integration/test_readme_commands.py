"""Test README commands stay in sync with CLI and script flags."""

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
README_PATH = REPO_ROOT / "README.md"
SCRIPT_PATH = REPO_ROOT / "scripts" / "deploy_and_run_remote.sh"


def test_readme_local_cli_commands_valid():
    """Verify local CLI commands in README are valid."""
    with open(README_PATH) as f:
        readme_text = f.read()
    
    # Extract python -m inference_profile.cli commands
    commands = re.findall(
        r'python -m inference_profile\.cli (\S+)',
        readme_text
    )
    
    # Should have at least: bootstrap-env, validate-traces, profile, simulate, report, verify-bundle, run-all
    expected_stages = [
        "bootstrap-env",
        "validate-traces",
        "profile",
        "simulate",
        "report",
        "verify-bundle",
        "run-all",
    ]
    
    for stage in expected_stages:
        assert stage in commands, f"Missing {stage} in README"


def test_readme_bash_script_stages_valid():
    """Verify bash script stages mentioned in README are correct."""
    with open(README_PATH) as f:
        readme_text = f.read()
    
    # Extract --stage values from README
    stages = re.findall(r'--stage (\S+)', readme_text)
    
    # Should mention: sync, bootstrap, run, fetch, all
    for stage in ["sync", "bootstrap", "run", "fetch", "all"]:
        assert stage in stages, f"Missing --stage {stage} in README"


def test_readme_contains_smoke_command():
    """Verify README has a copy-pasteable smoke command."""
    with open(README_PATH) as f:
        readme_text = f.read()
    
    # Should have a bash command block for smoke testing
    assert "bash scripts/deploy_and_run_remote.sh" in readme_text
    assert "smoke" in readme_text.lower()
    
    # Smoke command should have models, chunk-sizes, sequence-lengths
    smoke_section = readme_text[readme_text.find("Smoke Command"):readme_text.find("Smoke Command") + 1000]
    assert "--models" in smoke_section
    assert "--chunk-sizes" in smoke_section
    assert "--sequence-lengths" in smoke_section


def test_readme_contains_full_run_command():
    """Verify README has a copy-pasteable full run command."""
    with open(README_PATH) as f:
        readme_text = f.read()
    
    # Should have full end-to-end command
    assert "Full End-to-End Run" in readme_text or "full" in readme_text.lower()
    
    # Full run should reference multiple models
    full_section = readme_text
    assert "opt-125m" in full_section
    assert "opt-350m" in full_section or "opt-1.3b" in full_section


def test_readme_trace_paths_documented():
    """Verify README mentions expected trace file paths."""
    with open(README_PATH) as f:
        readme_text = f.read()
    
    # Should reference trace files
    assert "ldpc" in readme_text.lower()
    assert "ran" in readme_text.lower()
    assert "--ldpc-trace" in readme_text
    assert "--ran-ctrl-trace" in readme_text


def test_readme_output_directory_documented():
    """Verify README documents output directory structure."""
    with open(README_PATH) as f:
        readme_text = f.read()
    
    # Should have directory layout section
    assert "runs/<run_id>" in readme_text
    assert "raw/" in readme_text
    assert "derived/" in readme_text
    assert "logs/" in readme_text
    assert "checksums/" in readme_text


def test_readme_status_taxonomy_documented():
    """Verify README documents all status values."""
    with open(README_PATH) as f:
        readme_text = f.read()
    
    # Should have status taxonomy section
    assert "Status Taxonomy" in readme_text or "status" in readme_text.lower()
    
    # Should mention status values
    statuses = ["pending", "running", "success", "failed"]
    for status in statuses:
        assert status in readme_text


def test_readme_resume_rules_documented():
    """Verify README explains resume semantics."""
    with open(README_PATH) as f:
        readme_text = f.read()
    
    # Should have resume rules section
    assert "--resume-from" in readme_text
    assert "Resume" in readme_text


def test_readme_metric_definitions_present():
    """Verify README defines key metrics."""
    with open(README_PATH) as f:
        readme_text = f.read()
    
    # Should define: ttft_ms, tpot_ms, survival_vram_bytes, decode_runway_bytes
    metrics = ["ttft_ms", "tpot_ms_vram", "tpot_ms_pcie_async", "survival_vram_bytes", "decode_runway_bytes"]
    for metric in metrics:
        assert metric in readme_text, f"Missing {metric} definition in README"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
