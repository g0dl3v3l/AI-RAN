from pathlib import Path

import pytest

from ai_runtime_experiments.utils.paths import ensure_run_dir  # pyright: ignore[reportMissingImports]


def test_run_dir_creates_deterministic_directory(tmp_path: Path):
    output_root = tmp_path / "results"

    run_dir = ensure_run_dir(output_root=output_root, run_id="run_001")

    assert run_dir == output_root / "run_001"
    assert run_dir.is_dir()


def test_run_dir_refuses_existing_without_overwrite(tmp_path: Path):
    output_root = tmp_path / "results"

    ensure_run_dir(output_root=output_root, run_id="run_001")

    with pytest.raises(FileExistsError):
        ensure_run_dir(output_root=output_root, run_id="run_001", overwrite=False)


def test_run_dir_overwrite_removes_existing_contents(tmp_path: Path):
    output_root = tmp_path / "results"

    run_dir = ensure_run_dir(output_root=output_root, run_id="run_001")
    (run_dir / "old.txt").write_text("old", encoding="utf-8")

    run_dir_2 = ensure_run_dir(output_root=output_root, run_id="run_001", overwrite=True)

    assert run_dir_2 == run_dir
    assert not (run_dir / "old.txt").exists()
