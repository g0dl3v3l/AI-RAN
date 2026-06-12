from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pytest

from inference_profile import experiments, manifests, paths


EXPECTED_FINAL_STATUSES = (
    "bootstrap_failed",
    "validation_failed",
    "profile_oom",
    "profile_failed",
    "simulate_failed",
    "report_failed",
    "ssh_failed",
    "fetch_failed",
    "success",
)


def _read_json(path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_final_status_taxonomy_is_fixed() -> None:
    assert manifests.FINAL_STATUSES == EXPECTED_FINAL_STATUSES


def test_initialize_run_manifest_writes_minimal_honest_schema(tmp_path) -> None:
    bundle_paths = paths.init_run_bundle(tmp_path, run_id="run-001")
    created_at = datetime(2026, 4, 9, 21, 6, 0, tzinfo=timezone.utc)

    manifest = manifests.initialize_run_manifest(bundle_paths, created_at=created_at)
    written = _read_json(bundle_paths.run_manifest_path)

    assert written == manifest
    assert written["schema_version"] == manifests.MANIFEST_SCHEMA_VERSION
    assert written["run_id"] == "run-001"
    assert written["created_at"] == "2026-04-09T21:06:00Z"
    assert written["updated_at"] == "2026-04-09T21:06:00Z"
    assert written["final_status"] is None
    assert written["final_status_history"] == []
    assert written["stages"] == {}
    assert written["bundle_layout"] == {
        "logs": "logs",
        "raw": "raw",
        "derived": "derived",
        "plots": "plots",
        "checksums": "checksums",
        "run_manifest": "run_manifest.json",
        "environment": "environment.json",
        "report": "ran_inference_profiling_report.md",
        "checksum_manifest": "checksums/sha256sums.txt",
    }


def test_initialize_run_manifest_accepts_revised_schema_and_metadata(tmp_path) -> None:
    bundle_paths = paths.init_run_bundle(tmp_path, run_id="revised-run-001")

    manifest = manifests.initialize_run_manifest(
        bundle_paths,
        schema_version=experiments.RAN_DGXSPARK_V1_SCHEMA_VERSION,
        metadata={
            "experiment_type": experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE,
            "telemetry_tier": experiments.RAN_DGXSPARK_V1_TELEMETRY_TIER,
            "scheduler": experiments.RAN_DGXSPARK_V1_SCHEDULER,
        },
    )

    assert manifest["schema_version"] == experiments.RAN_DGXSPARK_V1_SCHEMA_VERSION
    assert manifest["experiment_type"] == experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE
    assert manifest["telemetry_tier"] == experiments.RAN_DGXSPARK_V1_TELEMETRY_TIER
    assert manifest["scheduler"] == experiments.RAN_DGXSPARK_V1_SCHEDULER


def test_update_stage_status_appends_stage_history_without_clobbering_prior_entries(
    tmp_path,
) -> None:
    bundle_paths = paths.init_run_bundle(tmp_path, run_id="run-002")
    manifests.initialize_run_manifest(bundle_paths)

    manifests.update_stage_status(
        bundle_paths.run_manifest_path,
        stage="profile",
        status="profile_failed",
        timestamp=datetime(2026, 4, 9, 21, 7, 0, tzinfo=timezone.utc),
        details={"attempt": 1, "reason": "worker exit 9"},
    )
    manifests.update_stage_status(
        bundle_paths.run_manifest_path,
        stage="profile",
        status="success",
        timestamp=datetime(2026, 4, 9, 21, 8, 0, tzinfo=timezone.utc),
        details={"attempt": 2, "points_completed": 15},
    )
    manifests.update_stage_status(
        bundle_paths.run_manifest_path,
        stage="report",
        status="success",
        timestamp=datetime(2026, 4, 9, 21, 9, 0, tzinfo=timezone.utc),
        details={"artifact": "ran_inference_profiling_report.md"},
    )

    written = _read_json(bundle_paths.run_manifest_path)
    assert written["final_status"] is None

    profile_stage = written["stages"]["profile"]
    assert profile_stage["latest_status"] == "success"
    assert profile_stage["updated_at"] == "2026-04-09T21:08:00Z"
    assert profile_stage["details"] == {"attempt": 2, "points_completed": 15}
    assert profile_stage["history"] == [
        {
            "status": "profile_failed",
            "timestamp": "2026-04-09T21:07:00Z",
            "details": {"attempt": 1, "reason": "worker exit 9"},
        },
        {
            "status": "success",
            "timestamp": "2026-04-09T21:08:00Z",
            "details": {"attempt": 2, "points_completed": 15},
        },
    ]

    report_stage = written["stages"]["report"]
    assert report_stage["history"] == [
        {
            "status": "success",
            "timestamp": "2026-04-09T21:09:00Z",
            "details": {"artifact": "ran_inference_profiling_report.md"},
        }
    ]


def test_update_stage_status_rejects_unknown_public_status(tmp_path) -> None:
    bundle_paths = paths.init_run_bundle(tmp_path, run_id="run-003")
    manifests.initialize_run_manifest(bundle_paths)

    with pytest.raises(ValueError, match="Unsupported final status"):
        manifests.update_stage_status(
            bundle_paths.run_manifest_path,
            stage="bootstrap",
            status="running",
        )
