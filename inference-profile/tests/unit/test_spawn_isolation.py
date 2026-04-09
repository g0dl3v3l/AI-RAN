from __future__ import annotations

import multiprocessing
import os
from pathlib import Path

from inference_profile import paths, worker_profile_point


def _spawn_probe_worker(_point_spec, raw_writer) -> dict[str, object]:
    raw_writer.write_row({"phase": "probe", "duration_us": "1.0"})
    return {
        "observed_pid": os.getpid(),
        "observed_parent_pid": os.getppid(),
        "observed_start_method": multiprocessing.get_start_method(allow_none=True),
    }


def test_run_profile_point_uses_spawned_process_instead_of_inline_execution(
    tmp_path: Path,
) -> None:
    run_root = paths.init_run_bundle(tmp_path, run_id="spawn-proof").run_root

    result = worker_profile_point.run_profile_point(
        {
            "point_id": "spawn-proof-point",
            "callable_path": f"{__name__}._spawn_probe_worker",
            "raw_fieldnames": ["phase", "duration_us"],
        },
        run_root=run_root,
        timeout_seconds=5,
    )

    assert result["success"] is True
    assert result["public_status"] == "success"
    assert result["worker_start_method"] == "spawn"
    assert result["worker_pid"] != os.getpid()
    assert result["worker_parent_pid"] == os.getpid()
    assert result["result_payload"] == {
        "observed_pid": result["worker_pid"],
        "observed_parent_pid": os.getpid(),
        "observed_start_method": "spawn",
    }
