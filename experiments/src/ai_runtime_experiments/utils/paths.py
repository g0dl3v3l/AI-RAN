from __future__ import annotations

import shutil
from pathlib import Path


def ensure_run_dir(*, output_root: str | Path, run_id: str, overwrite: bool = False) -> Path:
    """Create (or reuse) the run directory under the output root.

    The run directory path is deterministic: `Path(output_root) / run_id`.

    Safety:
    - refuses to overwrite an existing directory unless `overwrite=True`.
    """

    if not run_id:
        raise ValueError("run_id must be non-empty")
    if any(sep in run_id for sep in ("/", "\\")):
        raise ValueError("run_id must not contain path separators")

    root = Path(output_root)
    run_dir = root / run_id

    if run_dir.exists():
        if overwrite:
            shutil.rmtree(run_dir)
        else:
            raise FileExistsError(f"Run directory already exists: {run_dir}")

    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir
