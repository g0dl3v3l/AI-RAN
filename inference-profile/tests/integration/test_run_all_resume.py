"""Test run-all stage ordering and resumable execution."""

import json
import tempfile
from pathlib import Path

import pytest

from inference_profile.run_orchestrator import (
    STAGE_ORDER,
    get_resume_start_index,
    load_or_create_manifest,
    save_manifest,
)


def test_stage_order_is_correct():
    """Verify stage order is immutable and correct."""
    expected = [
        "bootstrap-env",
        "validate-traces",
        "profile",
        "simulate",
        "report",
        "verify-bundle",
    ]
    assert STAGE_ORDER == expected


def test_load_or_create_manifest_new():
    """Verify manifest creation for new run."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_root = Path(tmpdir) / "run-001"
        
        manifest = load_or_create_manifest(run_root)
        
        assert manifest["run_id"] == "run-001"
        assert manifest["status"] == "running"
        assert all(v == "pending" for v in manifest["stage_status"].values())
        assert list(manifest["stage_status"].keys()) == STAGE_ORDER


def test_load_or_create_manifest_existing():
    """Verify existing manifest is loaded correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_root = Path(tmpdir) / "run-002"
        run_root.mkdir(parents=True)
        
        # Write a custom manifest
        original_manifest = {
            "run_id": "run-002",
            "status": "partial",
            "stage_status": {
                "bootstrap-env": "success",
                "validate-traces": "success",
                "profile": "running",
                "simulate": "pending",
                "report": "pending",
                "verify-bundle": "pending",
            },
        }
        manifest_path = run_root / "run_manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(original_manifest, f)
        
        # Load it back
        loaded = load_or_create_manifest(run_root)
        assert loaded == original_manifest


def test_save_manifest():
    """Verify manifest is saved correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_root = Path(tmpdir) / "run-003"
        
        manifest = {
            "run_id": "run-003",
            "status": "success",
            "stage_status": {stage: "success" for stage in STAGE_ORDER},
        }
        
        save_manifest(run_root, manifest)
        
        manifest_path = run_root / "run_manifest.json"
        assert manifest_path.exists()
        
        with open(manifest_path) as f:
            loaded = json.load(f)
        assert loaded == manifest


def test_get_resume_start_index_none():
    """Verify resume_from=None starts at index 0."""
    manifest = {}  # not used
    idx = get_resume_start_index(None, manifest)
    assert idx == 0


def test_get_resume_start_index_valid():
    """Verify valid resume stages return correct index."""
    manifest = {}
    
    for stage in STAGE_ORDER:
        idx = get_resume_start_index(stage, manifest)
        assert idx == STAGE_ORDER.index(stage)


def test_get_resume_start_index_invalid():
    """Verify invalid stage raises ValueError."""
    manifest = {}
    
    with pytest.raises(ValueError, match="Invalid resume stage"):
        get_resume_start_index("invalid-stage", manifest)


def test_resume_skips_successful_stages():
    """Verify resumable runs skip already-successful stages."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_root = Path(tmpdir) / "run-resume"
        
        # Create manifest with some stages already successful
        manifest = {
            "run_id": "run-resume",
            "status": "partial",
            "stage_status": {
                "bootstrap-env": "success",
                "validate-traces": "success",
                "profile": "failed",
                "simulate": "pending",
                "report": "pending",
                "verify-bundle": "pending",
            },
        }
        
        # When resuming from "profile", earlier stages should be skipped
        start_idx = get_resume_start_index("profile", manifest)
        assert start_idx == STAGE_ORDER.index("profile")
        
        # Verify no stages before "profile" would be executed
        for i in range(start_idx):
            assert manifest["stage_status"][STAGE_ORDER[i]] == "success"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
