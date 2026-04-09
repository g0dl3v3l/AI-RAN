from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import signal
import sys
import time

import torch

from inference_profile import paths, worker_profile_point


def _success_worker(point_spec, raw_writer) -> dict[str, object]:
    print("success stdout", flush=True)
    print("success stderr", file=sys.stderr, flush=True)
    raw_writer.write_row({"phase": "prefill", "duration_us": "12.5"})
    return {
        "note": point_spec.get("note", "ok"),
        "worker_pid": os.getpid(),
    }


def _runtime_error_worker(point_spec, raw_writer) -> dict[str, object]:
    del point_spec
    print("runtime failure stdout", flush=True)
    print("runtime failure stderr", file=sys.stderr, flush=True)
    raw_writer.write_row({"phase": "prefill", "duration_us": "21.0"})
    raise RuntimeError("synthetic runtime failure")


def _oom_worker(point_spec, raw_writer) -> dict[str, object]:
    del point_spec
    print("oom stdout", flush=True)
    print("oom stderr", file=sys.stderr, flush=True)
    raw_writer.write_row({"phase": "decode", "duration_us": "33.0"})
    raise torch.OutOfMemoryError("CUDA out of memory during test worker run")


def _sleeping_worker(point_spec, raw_writer) -> dict[str, object]:
    print("timeout stdout", flush=True)
    print("timeout stderr", file=sys.stderr, flush=True)
    raw_writer.write_row({"phase": "decode", "duration_us": "44.0"})
    time.sleep(float(point_spec.get("sleep_seconds", 5.0)))
    return {"slept": True}


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _run_root(tmp_path: Path, run_id: str) -> Path:
    return paths.init_run_bundle(tmp_path, run_id=run_id).run_root


def _point_spec(worker_name: str, **overrides: object) -> dict[str, object]:
    point_id = str(overrides.pop("point_id", worker_name.replace("_", "-")))
    spec: dict[str, object] = {
        "point_id": point_id,
        "callable_path": f"{__name__}.{worker_name}",
        "raw_fieldnames": ["phase", "duration_us"],
    }
    spec.update(overrides)
    return spec


def test_run_profile_point_returns_success_payload_and_artifacts(
    tmp_path: Path,
) -> None:
    run_root = _run_root(tmp_path, "worker-success")

    result = worker_profile_point.run_profile_point(
        _point_spec("_success_worker", point_id="success-point", note="hello"),
        run_root=run_root,
        timeout_seconds=5,
    )

    assert result["success"] is True
    assert result["public_status"] == "success"
    assert result["failure_kind"] is None
    assert result["failure_cause"] is None
    assert result["timed_out"] is False
    assert result["exit_code"] == 0
    assert result["worker_pid"] != os.getpid()
    assert result["worker_parent_pid"] == os.getpid()
    assert result["worker_start_method"] == "spawn"
    assert result["result_payload"] == {
        "note": "hello",
        "worker_pid": result["worker_pid"],
    }
    assert result["raw_output_exists"] is True
    assert result["raw_row_count"] == 1
    assert result["error_class"] is None
    assert result["error_message"] is None

    spec_path = Path(result["spec_path"])
    stdout_log_path = Path(result["stdout_log_path"])
    stderr_log_path = Path(result["stderr_log_path"])
    raw_output_path = Path(result["raw_output_path"])

    assert spec_path.exists()
    assert stdout_log_path.exists()
    assert stderr_log_path.exists()
    assert raw_output_path.exists()

    serialized_spec = json.loads(spec_path.read_text(encoding="utf-8"))
    assert serialized_spec["point_id"] == "success-point"
    assert serialized_spec["callable_path"] == f"{__name__}._success_worker"
    assert serialized_spec["raw_fieldnames"] == ["phase", "duration_us"]
    assert serialized_spec["raw_output_path"] == str(raw_output_path)

    assert stdout_log_path.read_text(encoding="utf-8") == "success stdout\n"
    assert stderr_log_path.read_text(encoding="utf-8") == "success stderr\n"
    assert _read_csv_rows(raw_output_path) == [
        {"phase": "prefill", "duration_us": "12.5"}
    ]

    cleanup = result["cuda_cleanup"]
    assert cleanup["synchronize_attempted"] is True
    assert cleanup["raw_flush_attempted"] is True
    assert cleanup["empty_cache_attempted"] is True


def test_child_runtime_error_becomes_profile_failed(tmp_path: Path) -> None:
    run_root = _run_root(tmp_path, "worker-runtime-fail")

    result = worker_profile_point.run_profile_point(
        _point_spec("_runtime_error_worker", point_id="runtime-fail-point"),
        run_root=run_root,
        timeout_seconds=5,
    )

    assert result["success"] is False
    assert result["public_status"] == "profile_failed"
    assert result["failure_kind"] == "exception"
    assert result["failure_cause"] == "synthetic runtime failure"
    assert result["timed_out"] is False
    assert result["exit_code"] == 1
    assert result["error_class"] == "RuntimeError"
    assert result["error_message"] == "synthetic runtime failure"
    assert result["raw_output_exists"] is True
    assert result["raw_row_count"] == 1
    assert (
        Path(result["stdout_log_path"])
        .read_text(encoding="utf-8")
        .startswith("runtime failure stdout\n")
    )
    stderr_text = Path(result["stderr_log_path"]).read_text(encoding="utf-8")
    assert "runtime failure stderr" in stderr_text
    assert "synthetic runtime failure" in stderr_text


def test_child_torch_oom_becomes_profile_oom(tmp_path: Path) -> None:
    run_root = _run_root(tmp_path, "worker-oom")

    result = worker_profile_point.run_profile_point(
        _point_spec("_oom_worker", point_id="oom-point"),
        run_root=run_root,
        timeout_seconds=5,
    )

    assert result["success"] is False
    assert result["public_status"] == "profile_oom"
    assert result["failure_kind"] == "cuda_oom"
    assert result["failure_cause"] == "CUDA out of memory during test worker run"
    assert result["timed_out"] is False
    assert result["exit_code"] == 1
    assert result["error_class"] == "OutOfMemoryError"
    assert result["raw_output_exists"] is True
    assert result["raw_row_count"] == 1
    stderr_text = Path(result["stderr_log_path"]).read_text(encoding="utf-8")
    assert "oom stderr" in stderr_text
    assert "CUDA out of memory during test worker run" in stderr_text


def test_sleeping_child_timeout_becomes_profile_failed(tmp_path: Path) -> None:
    run_root = _run_root(tmp_path, "worker-timeout")

    result = worker_profile_point.run_profile_point(
        _point_spec(
            "_sleeping_worker",
            point_id="timeout-point",
            sleep_seconds=5.0,
        ),
        run_root=run_root,
        timeout_seconds=2,
    )

    assert result["success"] is False
    assert result["public_status"] == "profile_failed"
    assert result["failure_kind"] == "timeout"
    assert result["failure_cause"] == "Worker timed out after 2 second(s)"
    assert result["timed_out"] is True
    assert result["exit_code"] is not None
    assert result["exit_signal"] in {
        signal.SIGTERM.value,
        signal.SIGKILL.value,
    }
    assert result["exit_signal_name"] in {"SIGTERM", "SIGKILL"}
    assert result["raw_output_path"] is not None
    assert result["raw_output_exists"] is True
    assert result["raw_row_count"] == 1
    assert Path(result["worker_result_path"]).exists() is False
    assert "timeout stdout" in Path(result["stdout_log_path"]).read_text(
        encoding="utf-8"
    )
    assert "timeout stderr" in Path(result["stderr_log_path"]).read_text(
        encoding="utf-8"
    )
