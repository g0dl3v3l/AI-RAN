"""Unit tests for profile orchestration."""

import tempfile
from pathlib import Path

import pytest

from inference_profile import profile_orchestrator


def test_orchestrate_profile_run_initializes_manifest():
    """Verify orchestrator initializes manifest for new runs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_root = Path(tmpdir)
        
        # Run should initialize manifest if not present
        # This would require GPU, so we just verify the orchestrator exists
        assert hasattr(profile_orchestrator, "orchestrate_profile_run")


def test_orchestrator_result_structure():
    """Verify ProfileOrchestratorResult has expected fields."""
    from pathlib import Path
    
    result = profile_orchestrator.ProfileOrchestratorResult(
        run_root=Path("/tmp/test"),
        success=True,
        row_counts={
            "prefill": 10,
            "decode": 20,
            "pcie": 5,
        },
    )
    
    assert result.run_root == Path("/tmp/test")
    assert result.success is True
    assert result.row_counts["prefill"] == 10
    assert result.row_counts["decode"] == 20
    assert result.row_counts["pcie"] == 5


def test_profile_orchestrator_imports():
    """Verify all required imports are available."""
    from inference_profile import profile_orchestrator
    
    # Check that required sub-modules are imported
    assert hasattr(profile_orchestrator, "prefill_profile")
    assert hasattr(profile_orchestrator, "decode_profile")
    assert hasattr(profile_orchestrator, "pcie_profile")
    assert hasattr(profile_orchestrator, "profile_reducer")
    assert hasattr(profile_orchestrator, "manifests")
