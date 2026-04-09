"""Test fetch verification contract: success on complete bundles."""

import json
import tempfile
from pathlib import Path

import pytest

from inference_profile.verify_bundle import verify_bundle, REQUIRED_BUNDLE_FILES


def test_verify_complete_bundle():
    """Verify successful bundle has status 'success'."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_root = Path(tmpdir)
        
        # Create all required files
        for rel_path in REQUIRED_BUNDLE_FILES:
            file_path = run_root / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("dummy content")
        
        result = verify_bundle(run_root)
        
        assert result["status"] == "success"
        assert result["complete"] is True
        assert all(result["completeness_results"].values())


def test_verify_bundle_missing_files():
    """Verify bundle with missing files has status 'fetch_failed'."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_root = Path(tmpdir)
        
        # Create only some files
        (run_root / "run_manifest.json").write_text("{}")
        (run_root / "raw").mkdir()
        (run_root / "raw" / "prefill_events.csv").write_text("data")
        
        result = verify_bundle(run_root)
        
        assert result["status"] == "fetch_failed"
        assert result["complete"] is False
        assert not all(result["completeness_results"].values())


def test_verify_bundle_missing_one_file():
    """Verify missing single file triggers fetch_failed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_root = Path(tmpdir)
        
        # Create all but one file
        for rel_path in REQUIRED_BUNDLE_FILES:
            if rel_path == "derived/pcie_summary.csv":
                continue  # Skip this one
            file_path = run_root / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("dummy")
        
        result = verify_bundle(run_root)
        
        assert result["status"] == "fetch_failed"
        assert result["complete"] is False
        assert result["completeness_results"]["derived/pcie_summary.csv"] is False


def test_verify_bundle_completeness_detail():
    """Verify completeness_results matches actual file presence."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_root = Path(tmpdir)
        
        # Create a few files
        (run_root / "run_manifest.json").write_text("{}")
        (run_root / "raw").mkdir()
        (run_root / "raw" / "prefill_events.csv").write_text("data")
        (run_root / "raw" / "decode_events.csv").write_text("data")
        (run_root / "derived").mkdir()
        (run_root / "derived" / "prefill_summary.csv").write_text("summary")
        
        result = verify_bundle(run_root)
        
        assert result["completeness_results"]["run_manifest.json"] is True
        assert result["completeness_results"]["raw/prefill_events.csv"] is True
        assert result["completeness_results"]["raw/decode_events.csv"] is True
        assert result["completeness_results"]["derived/prefill_summary.csv"] is True
        assert result["completeness_results"]["derived/pcie_summary.csv"] is False


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
