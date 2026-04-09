"""Test fetch verification on checksum failure."""

import json
import tempfile
from pathlib import Path

import pytest

from inference_profile.verify_bundle import (
    verify_bundle,
    REQUIRED_BUNDLE_FILES,
    compute_file_checksum,
)


def test_verify_bundle_checksum_mismatch():
    """Verify checksum mismatch produces fetch_failed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_root = Path(tmpdir)
        
        # Create all required files
        for rel_path in REQUIRED_BUNDLE_FILES:
            file_path = run_root / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("dummy content")
        
        # Create checksums directory and file with WRONG checksums
        checksums_dir = run_root / "checksums"
        checksums_dir.mkdir()
        
        wrong_checksums = {
            "raw/prefill_events.csv": "wrong_checksum_value_123",
            "raw/decode_events.csv": "another_wrong_value_456",
            "raw/pcie_events.csv": "yet_another_wrong_789",
        }
        
        with open(checksums_dir / "checksums.json", "w") as f:
            json.dump(wrong_checksums, f)
        
        result = verify_bundle(run_root)
        
        assert result["status"] == "fetch_failed"
        assert result["checksums_valid"] is False
        assert not result["checksum_results"]["raw/prefill_events.csv"]["match"]


def test_verify_bundle_correct_checksums():
    """Verify correct checksums produce success."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_root = Path(tmpdir)
        
        # Create all required files
        for rel_path in REQUIRED_BUNDLE_FILES:
            file_path = run_root / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("dummy content")
        
        # Compute actual checksums
        checksums_dir = run_root / "checksums"
        checksums_dir.mkdir()
        
        actual_checksums = {}
        for rel_path in REQUIRED_BUNDLE_FILES:
            file_path = run_root / rel_path
            actual_checksums[rel_path] = compute_file_checksum(file_path)
        
        with open(checksums_dir / "checksums.json", "w") as f:
            json.dump(actual_checksums, f)
        
        result = verify_bundle(run_root)
        
        assert result["status"] == "success"
        assert result["checksums_valid"] is True
        assert all(r["match"] for r in result["checksum_results"].values())


def test_verify_bundle_partial_checksum_mismatch():
    """Verify partial checksum mismatch still fails."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_root = Path(tmpdir)
        
        # Create all required files
        for rel_path in REQUIRED_BUNDLE_FILES:
            file_path = run_root / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("dummy content")
        
        # Create checksums with one correct and others wrong
        checksums_dir = run_root / "checksums"
        checksums_dir.mkdir()
        
        prefill_path = run_root / "raw" / "prefill_events.csv"
        correct_checksum = compute_file_checksum(prefill_path)
        
        checksums = {
            "raw/prefill_events.csv": correct_checksum,  # Correct
            "raw/decode_events.csv": "wrong_value",  # Wrong
            "raw/pcie_events.csv": "also_wrong",  # Wrong
        }
        
        with open(checksums_dir / "checksums.json", "w") as f:
            json.dump(checksums, f)
        
        result = verify_bundle(run_root)
        
        assert result["status"] == "fetch_failed"
        assert result["checksums_valid"] is False
        assert result["checksum_results"]["raw/prefill_events.csv"]["match"] is True
        assert result["checksum_results"]["raw/decode_events.csv"]["match"] is False


def test_verify_bundle_no_checksums():
    """Verify bundle succeeds when no checksums file exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_root = Path(tmpdir)
        
        # Create all required files
        for rel_path in REQUIRED_BUNDLE_FILES:
            file_path = run_root / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("dummy content")
        
        # Do NOT create checksums directory
        
        result = verify_bundle(run_root)
        
        # Should succeed if completeness is satisfied
        assert result["status"] == "success"
        assert result["complete"] is True


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
