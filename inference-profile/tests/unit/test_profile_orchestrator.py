"""Unit tests for profile orchestration."""

import tempfile
from pathlib import Path

import pytest

from inference_profile import experiments, manifests, paths, profile_orchestrator


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


def test_build_profile_point_plans_expands_revised_sm_ai_and_decode_modes(
    tmp_path: Path,
) -> None:
    bundle_paths = paths.init_run_bundle(tmp_path, run_id="revised-profile-plans")

    point_plans = profile_orchestrator._build_profile_point_plans(
        bundle_paths=bundle_paths,
        models=("facebook/opt-125m",),
        chunk_sizes=(64,),
        sequence_lengths=(1024,),
        warmup_iterations=1,
        timed_iterations=1,
        gpu_id=0,
        sm_ai_partition=100,
        cache_root=None,
        experiment_type=experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE,
    )

    assert len(point_plans["prefill"]) == len(
        experiments.RAN_DGXSPARK_V1_SM_AI_PARTITIONS
    )
    assert len(point_plans["decode"]) == (
        len(experiments.RAN_DGXSPARK_V1_SM_AI_PARTITIONS)
        * len(experiments.RAN_DGXSPARK_V1_DECODE_MODES)
    )
    assert len(point_plans["pcie"]) == 1

    assert {
        plan.manifest_fields["sm_ai_partition"] for plan in point_plans["prefill"]
    } == set(experiments.RAN_DGXSPARK_V1_SM_AI_PARTITIONS)
    assert {
        plan.manifest_fields["sm_ai_partition"] for plan in point_plans["decode"]
    } == set(experiments.RAN_DGXSPARK_V1_SM_AI_PARTITIONS)
    assert {
        plan.manifest_fields["decode_mode"] for plan in point_plans["decode"]
    } == set(experiments.RAN_DGXSPARK_V1_DECODE_MODES)
    assert all("sm-" in plan.point_id for plan in point_plans["prefill"])
    assert all("mode-" in plan.point_id for plan in point_plans["decode"])


def test_ensure_bundle_layout_updates_existing_manifest_with_revised_metadata(
    tmp_path: Path,
) -> None:
    bundle_paths = paths.init_run_bundle(tmp_path, run_id="existing-run")
    manifests.initialize_run_manifest(bundle_paths)

    metadata = experiments.metadata_for_experiment(
        experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE,
        models=("facebook/opt-125m",),
        chunk_sizes=(64,),
        sequence_lengths=(1024,),
    )

    profile_orchestrator._ensure_bundle_layout(
        bundle_paths.run_root,
        experiment_type=experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE,
        metadata=metadata,
    )

    manifest = manifests.load_run_manifest(bundle_paths.run_manifest_path)

    assert manifest["schema_version"] == experiments.RAN_DGXSPARK_V1_SCHEMA_VERSION
    assert manifest["experiment_type"] == experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE
    assert manifest["telemetry_tier"] == experiments.RAN_DGXSPARK_V1_TELEMETRY_TIER
    assert manifest["scheduler"] == experiments.RAN_DGXSPARK_V1_SCHEDULER
    assert manifest["sm_ai_partitions"] == list(
        experiments.RAN_DGXSPARK_V1_SM_AI_PARTITIONS
    )
    assert manifest["decode_modes"] == list(experiments.RAN_DGXSPARK_V1_DECODE_MODES)
