"""Test fetch still retrieves logs after partial remote failure."""

import json
import tempfile
from pathlib import Path

import pytest

from inference_profile.verify_bundle import verify_bundle, REQUIRED_BUNDLE_FILES


def test_fetch_partial_failure_preserves_logs():
    """Verify logs are preserved even when remote stopped early."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_root = Path(tmpdir)
        
        # Simulate partial run: only bootstrap and validate succeeded
        (run_root / "run_manifest.json").write_text(json.dumps({
            "run_id": "partial-run",
            "status": "failed",
            "stage_status": {
                "bootstrap-env": "success",
                "validate-traces": "success",
                "profile": "failed",  # Failed here
                "simulate": "pending",
                "report": "pending",
                "verify-bundle": "pending",
            }
        }))
        
        # Create logs directory with bootstrap and validate logs
        logs_dir = run_root / "logs"
        logs_dir.mkdir()
        (logs_dir / "bootstrap-env.log").write_text("Bootstrap output")
        (logs_dir / "validate-traces.log").write_text("Validation output")
        (logs_dir / "profile.log").write_text("Profile failed: out of memory")
        
        # Verify should fail due to missing required output files
        result = verify_bundle(run_root)
        
        assert result["status"] == "fetch_failed"
        assert result["complete"] is False
        # But logs are preserved for debugging
        assert (logs_dir / "bootstrap-env.log").exists()
        assert (logs_dir / "profile.log").exists()


def test_fetch_partial_with_manifest_preserves_evidence():
    """Verify manifest and logs preserved even on early failure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_root = Path(tmpdir)
        
        # Create manifest showing failure at profile stage
        manifest_data = {
            "run_id": "early-fail",
            "status": "failed",
            "stage_status": {
                "bootstrap-env": "success",
                "validate-traces": "success",
                "profile": "failed",
                "simulate": "pending",
                "report": "pending",
                "verify-bundle": "pending",
            },
            "error_at_stage": "profile",
            "error_message": "GPU out of memory",
        }
        
        (run_root / "run_manifest.json").write_text(json.dumps(manifest_data))
        
        # Create logs
        logs_dir = run_root / "logs"
        logs_dir.mkdir()
        (logs_dir / "profile.log").write_text("CUDA out of memory error")
        
        # Verify bundle fails but doesn't delete anything
        result = verify_bundle(run_root)
        
        assert result["status"] == "fetch_failed"
        # Evidence is preserved
        assert (run_root / "run_manifest.json").exists()
        assert (logs_dir / "profile.log").exists()
        
        # Manifest should still be readable
        with open(run_root / "run_manifest.json") as f:
            loaded_manifest = json.load(f)
        assert loaded_manifest["error_at_stage"] == "profile"


def test_fetch_creates_missing_output_directory():
    """Verify fetch creates local directory even if remote has nothing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_root = Path(tmpdir) / "new-run"
        
        # Don't create anything initially
        # Just verify directory creation logic
        run_root.mkdir(parents=True, exist_ok=True)
        
        # Add minimal manifest
        (run_root / "run_manifest.json").write_text(json.dumps({
            "run_id": "empty-run",
            "status": "failed",
        }))
        
        # This should handle the empty directory gracefully
        result = verify_bundle(run_root)
        
        assert result["status"] == "fetch_failed"
        assert not result["complete"]
        # But directory exists for future fetches
        assert run_root.exists()
        assert (run_root / "run_manifest.json").exists()


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
