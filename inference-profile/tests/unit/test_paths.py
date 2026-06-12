from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from inference_profile import experiments, paths


def test_build_run_bundle_paths_uses_fixed_layout() -> None:
    bundle_paths = paths.build_run_bundle_paths(
        output_root=Path("/tmp/inference-profile"),
        run_id="manual-run",
    )

    assert bundle_paths.run_id == "manual-run"
    assert bundle_paths.run_root.as_posix() == "/tmp/inference-profile/runs/manual-run"
    assert bundle_paths.logs_dir == bundle_paths.run_root / "logs"
    assert bundle_paths.raw_dir == bundle_paths.run_root / "raw"
    assert bundle_paths.derived_dir == bundle_paths.run_root / "derived"
    assert bundle_paths.plots_dir == bundle_paths.run_root / "plots"
    assert bundle_paths.checksums_dir == bundle_paths.run_root / "checksums"
    assert bundle_paths.run_manifest_path == bundle_paths.run_root / "run_manifest.json"
    assert bundle_paths.environment_path == bundle_paths.run_root / "environment.json"
    assert (
        bundle_paths.report_path
        == bundle_paths.run_root / "ran_inference_profiling_report.md"
    )
    assert (
        bundle_paths.checksum_manifest_path
        == bundle_paths.run_root / "checksums" / "sha256sums.txt"
    )


def test_init_run_bundle_creates_timestamped_tree_and_placeholders(tmp_path) -> None:
    fixed_now = datetime(2026, 4, 9, 21, 5, 0, tzinfo=timezone.utc)

    bundle_paths = paths.init_run_bundle(tmp_path, now=fixed_now)

    assert bundle_paths.run_id == "20260409_210500"
    for directory in bundle_paths.directories:
        assert directory.is_dir()

    assert bundle_paths.run_manifest_path.read_text(encoding="utf-8") == "{}\n"
    assert bundle_paths.environment_path.read_text(encoding="utf-8") == "{}\n"
    assert bundle_paths.report_path.exists()
    assert bundle_paths.report_path.read_text(encoding="utf-8") == ""
    assert bundle_paths.checksum_manifest_path.exists()
    assert bundle_paths.checksum_manifest_path.read_text(encoding="utf-8") == ""


def test_init_experiment_run_bundle_uses_revised_prefix(tmp_path) -> None:
    fixed_now = datetime(2026, 4, 13, 19, 0, 0, tzinfo=timezone.utc)

    bundle_paths = paths.init_experiment_run_bundle(
        tmp_path,
        experiment_type=experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE,
        now=fixed_now,
    )

    assert bundle_paths.run_id == "revised-ran-dgxspark-20260413_190000"
    assert bundle_paths.run_root == (
        tmp_path / "runs" / "revised-ran-dgxspark-20260413_190000"
    )
