from __future__ import annotations

from hashlib import sha256

from inference_profile import manifests, paths


def _sha256_line(path, run_root) -> str:
    digest = sha256(path.read_bytes()).hexdigest()
    return f"{digest}  {path.relative_to(run_root).as_posix()}"


def test_write_checksum_manifest_is_deterministic_and_self_excluding(tmp_path) -> None:
    bundle_paths = paths.init_run_bundle(tmp_path, run_id="run-001")

    bundle_paths.run_manifest_path.write_text(
        '{"run_id":"run-001"}\n', encoding="utf-8"
    )
    bundle_paths.environment_path.write_text('{"gpu":"spark"}\n', encoding="utf-8")
    bundle_paths.report_path.write_text("# report\n", encoding="utf-8")
    (bundle_paths.raw_dir / "z-last.csv").write_text("z\n", encoding="utf-8")
    (bundle_paths.raw_dir / "a-first.csv").write_text("a\n", encoding="utf-8")
    (bundle_paths.derived_dir / "summary.json").write_text("{}\n", encoding="utf-8")
    (bundle_paths.plots_dir / "plot-b.png").write_bytes(b"plot-b")
    (bundle_paths.plots_dir / "plot-a.png").write_bytes(b"plot-a")
    bundle_paths.checksum_manifest_path.write_text(
        "this should not be checksummed\n",
        encoding="utf-8",
    )

    required_paths = manifests.required_checksum_paths(
        bundle_paths,
        bundle_paths.raw_dir,
        bundle_paths.derived_dir,
        bundle_paths.plots_dir,
        bundle_paths.checksum_manifest_path,
    )
    checksum_path = manifests.write_checksum_manifest(
        bundle_paths.run_root,
        required_paths=required_paths,
    )

    first_render = checksum_path.read_text(encoding="utf-8")
    second_render = manifests.write_checksum_manifest(
        bundle_paths.run_root,
        required_paths=required_paths,
    ).read_text(encoding="utf-8")

    assert first_render == second_render
    assert "checksums/sha256sums.txt" not in first_render

    expected_files = [
        bundle_paths.derived_dir / "summary.json",
        bundle_paths.environment_path,
        bundle_paths.plots_dir / "plot-a.png",
        bundle_paths.plots_dir / "plot-b.png",
        bundle_paths.raw_dir / "a-first.csv",
        bundle_paths.raw_dir / "z-last.csv",
        bundle_paths.report_path,
        bundle_paths.run_manifest_path,
    ]
    expected_lines = [
        _sha256_line(path, bundle_paths.run_root)
        for path in sorted(
            expected_files,
            key=lambda path: path.relative_to(bundle_paths.run_root).as_posix(),
        )
    ]

    assert first_render.splitlines() == expected_lines
