from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from contextlib import redirect_stderr, redirect_stdout
import csv
import importlib
import json
import multiprocessing
import os
from pathlib import Path
import signal
from tempfile import NamedTemporaryFile
import traceback
from typing import Any, cast

from inference_profile.paths import bundle_paths_from_run_root

_WORKER_STDOUT_SUFFIX = ".stdout.log"
_WORKER_STDERR_SUFFIX = ".stderr.log"
_WORKER_SPEC_SUFFIX = ".worker-spec.json"
_WORKER_RESULT_SUFFIX = ".worker-result.json"
_WORKER_RAW_SUFFIX = ".raw.csv"
_TIMEOUT_TERMINATION_GRACE_SECONDS = 5.0
_OOM_MESSAGE_FRAGMENT = "out of memory"

WorkerCallable = Callable[
    [Mapping[str, Any], "RawCsvWriter"],
    Mapping[str, Any] | None,
]


class RawCsvWriter:
    def __init__(
        self,
        path: str | Path | None,
        *,
        fieldnames: Sequence[str] | None = None,
    ) -> None:
        self.path = Path(path) if path is not None else None
        self.fieldnames = (
            tuple(str(fieldname) for fieldname in fieldnames)
            if fieldnames is not None
            else None
        )
        self.row_count = 0
        self._handle = None
        self._writer = None

    def write_row(self, row: Mapping[str, object]) -> None:
        normalized_row = {str(key): row[key] for key in row}
        if self._writer is None:
            self._open_writer(tuple(normalized_row))

        assert self._writer is not None
        assert self._handle is not None
        self._writer.writerow(normalized_row)
        self._handle.flush()
        self.row_count += 1

    def flush(self) -> None:
        if self._handle is not None:
            self._handle.flush()

    def close(self) -> None:
        if self._handle is None:
            return
        self._handle.flush()
        self._handle.close()
        self._handle = None
        self._writer = None

    def _open_writer(self, inferred_fieldnames: Sequence[str]) -> None:
        if self.path is None:
            raise ValueError("raw_output_path must be configured before writing rows")

        resolved_fieldnames = self.fieldnames or tuple(
            str(name) for name in inferred_fieldnames
        )
        if not resolved_fieldnames:
            raise ValueError("raw CSV writer requires at least one field name")

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("w", encoding="utf-8", newline="")
        self._writer = csv.DictWriter(
            self._handle,
            fieldnames=list(resolved_fieldnames),
            extrasaction="raise",
        )
        self._writer.writeheader()
        self._handle.flush()
        self.fieldnames = tuple(resolved_fieldnames)


def run_profile_point(
    point_spec: Mapping[str, Any],
    *,
    run_root: str | Path,
    timeout_seconds: float,
) -> dict[str, Any]:
    resolved_timeout_seconds = float(timeout_seconds)
    if resolved_timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be > 0")

    resolved_run_root = Path(run_root)
    point_id = _require_non_empty_string(point_spec.get("point_id"), name="point_id")
    artifact_paths = _build_artifact_paths(resolved_run_root, point_id)
    normalized_spec = _normalize_point_spec(
        point_spec,
        default_raw_output_path=artifact_paths["raw_output_path"],
    )

    artifact_paths["logs_dir"].mkdir(parents=True, exist_ok=True)
    artifact_paths["raw_dir"].mkdir(parents=True, exist_ok=True)
    artifact_paths["stdout_log_path"].touch()
    artifact_paths["stderr_log_path"].touch()
    _write_json_file(artifact_paths["spec_path"], normalized_spec)

    spawn_context = multiprocessing.get_context("spawn")
    process = spawn_context.Process(
        target=_worker_process_entry,
        args=(
            str(artifact_paths["spec_path"]),
            str(artifact_paths["worker_result_path"]),
            str(artifact_paths["stdout_log_path"]),
            str(artifact_paths["stderr_log_path"]),
        ),
        name=f"profile-point-{_slugify(point_id)}",
    )
    process.start()

    timed_out = False
    process.join(resolved_timeout_seconds)
    if process.is_alive():
        timed_out = True
        process.terminate()
        process.join(_TIMEOUT_TERMINATION_GRACE_SECONDS)
        if process.is_alive():
            process.kill()
            process.join()

    worker_result, worker_result_error = _read_worker_result(
        artifact_paths["worker_result_path"]
    )
    return _build_parent_payload(
        point_id=point_id,
        timeout_seconds=resolved_timeout_seconds,
        normalized_spec=normalized_spec,
        artifact_paths=artifact_paths,
        timed_out=timed_out,
        exit_code=process.exitcode,
        worker_result=worker_result,
        worker_result_error=worker_result_error,
    )


def _worker_process_entry(
    spec_path: str,
    worker_result_path: str,
    stdout_log_path: str,
    stderr_log_path: str,
) -> None:
    exit_code = 1
    resolved_worker_result: dict[str, Any] | None = None

    stdout_path = Path(stdout_log_path)
    stderr_path = Path(stderr_log_path)
    with stdout_path.open("a", encoding="utf-8", buffering=1) as stdout_handle:
        with stderr_path.open("a", encoding="utf-8", buffering=1) as stderr_handle:
            with redirect_stdout(stdout_handle), redirect_stderr(stderr_handle):
                resolved_worker_result, exit_code = _execute_worker_spec(
                    Path(spec_path)
                )
                try:
                    _write_json_file(Path(worker_result_path), resolved_worker_result)
                except Exception:
                    traceback.print_exc()
                    exit_code = 1

    raise SystemExit(exit_code)


def _execute_worker_spec(spec_path: Path) -> tuple[dict[str, Any], int]:
    point_id = spec_path.stem.replace(".worker-spec", "") or "unknown-point"
    raw_output_path: str | None = None
    raw_writer: RawCsvWriter | None = None
    result_payload: dict[str, Any] = {}
    error_class: str | None = None
    error_message: str | None = None
    failure_kind: str | None = None

    try:
        spec = _read_json_object(spec_path)
        point_id = _require_non_empty_string(spec.get("point_id"), name="point_id")
        callable_path = _require_non_empty_string(
            spec.get("callable_path"),
            name="callable_path",
        )
        raw_output_path = _optional_string(spec.get("raw_output_path"))
        raw_fieldnames = _normalize_fieldnames(spec.get("raw_fieldnames"))
        raw_writer = RawCsvWriter(raw_output_path, fieldnames=raw_fieldnames)
        worker_callable = _load_worker_callable(callable_path)
        result_payload = _normalize_result_payload(worker_callable(spec, raw_writer))
        success = True
        exit_code = 0
    except BaseException as exc:
        traceback.print_exc()
        success = False
        exit_code = 1
        failure_kind = "cuda_oom" if _is_cuda_oom_error(exc) else "exception"
        error_class = exc.__class__.__name__
        error_message = _exception_message(exc)
    finally:
        synchronize_error = _attempt_torch_cuda_synchronize()
        raw_flush_error = _flush_raw_writer(raw_writer)
        raw_row_count = raw_writer.row_count if raw_writer is not None else None
        raw_close_error = _close_raw_writer(raw_writer)
        empty_cache_error = _attempt_torch_cuda_empty_cache()

    worker_result = {
        "point_id": point_id,
        "success": success,
        "failure_kind": failure_kind,
        "error_class": error_class,
        "error_message": error_message,
        "raw_output_path": raw_output_path,
        "raw_output_exists": bool(raw_output_path and Path(raw_output_path).exists()),
        "raw_row_count": raw_row_count,
        "result_payload": result_payload,
        "worker_pid": os.getpid(),
        "worker_parent_pid": os.getppid(),
        "worker_start_method": multiprocessing.get_start_method(allow_none=True),
        "cuda_cleanup": {
            "synchronize_attempted": True,
            "synchronize_error": synchronize_error,
            "raw_flush_attempted": True,
            "raw_flush_error": raw_flush_error,
            "raw_close_error": raw_close_error,
            "empty_cache_attempted": True,
            "empty_cache_error": empty_cache_error,
        },
    }
    _ensure_json_serializable(worker_result)
    return worker_result, exit_code


def _build_parent_payload(
    *,
    point_id: str,
    timeout_seconds: float,
    normalized_spec: Mapping[str, Any],
    artifact_paths: Mapping[str, Path],
    timed_out: bool,
    exit_code: int | None,
    worker_result: Mapping[str, Any] | None,
    worker_result_error: str | None,
) -> dict[str, Any]:
    raw_output_path = None
    if worker_result is not None:
        raw_output_path = _optional_string(worker_result.get("raw_output_path"))
    if raw_output_path is None:
        raw_output_path = _optional_string(normalized_spec.get("raw_output_path"))
    raw_output_exists = bool(raw_output_path and Path(raw_output_path).exists())
    raw_row_count = _resolve_raw_row_count(worker_result, raw_output_path)

    base_payload: dict[str, Any] = {
        "point_id": point_id,
        "success": False,
        "public_status": "profile_failed",
        "failure_kind": None,
        "failure_cause": None,
        "timed_out": timed_out,
        "timeout_seconds": timeout_seconds,
        "exit_code": exit_code,
        "exit_signal": _exit_signal(exit_code),
        "exit_signal_name": _exit_signal_name(exit_code),
        "stdout_log_path": str(artifact_paths["stdout_log_path"]),
        "stderr_log_path": str(artifact_paths["stderr_log_path"]),
        "spec_path": str(artifact_paths["spec_path"]),
        "worker_result_path": str(artifact_paths["worker_result_path"]),
        "raw_output_path": raw_output_path,
        "raw_output_exists": raw_output_exists,
        "raw_row_count": raw_row_count,
        "worker_pid": None,
        "worker_parent_pid": None,
        "worker_start_method": None,
        "error_class": None,
        "error_message": None,
        "result_payload": {},
        "cuda_cleanup": None,
    }

    if worker_result is not None:
        base_payload["worker_pid"] = _optional_int(worker_result.get("worker_pid"))
        base_payload["worker_parent_pid"] = _optional_int(
            worker_result.get("worker_parent_pid")
        )
        base_payload["worker_start_method"] = _optional_string(
            worker_result.get("worker_start_method")
        )
        base_payload["error_class"] = _optional_string(worker_result.get("error_class"))
        base_payload["error_message"] = _optional_string(
            worker_result.get("error_message")
        )
        base_payload["cuda_cleanup"] = _optional_mapping(
            worker_result.get("cuda_cleanup")
        )
        base_payload["result_payload"] = (
            _optional_mapping(worker_result.get("result_payload")) or {}
        )

    if timed_out:
        base_payload["failure_kind"] = "timeout"
        base_payload["failure_cause"] = (
            f"Worker timed out after {timeout_seconds:g} second(s)"
        )
        return base_payload

    if worker_result_error is not None:
        base_payload["failure_kind"] = "worker_result_unreadable"
        base_payload["failure_cause"] = worker_result_error
        return base_payload

    if worker_result is None:
        base_payload["failure_kind"] = "worker_exit"
        base_payload["failure_cause"] = _missing_result_message(exit_code)
        return base_payload

    if bool(worker_result.get("success")):
        base_payload["success"] = True
        base_payload["public_status"] = "success"
        return base_payload

    failure_kind = _optional_string(worker_result.get("failure_kind")) or "exception"
    base_payload["failure_kind"] = failure_kind
    base_payload["failure_cause"] = (
        _optional_string(worker_result.get("error_message"))
        or "Worker failed without recording an error message"
    )
    if failure_kind == "cuda_oom":
        base_payload["public_status"] = "profile_oom"
    return base_payload


def _build_artifact_paths(run_root: Path, point_id: str) -> dict[str, Path]:
    bundle_paths = bundle_paths_from_run_root(run_root)
    stem = _slugify(point_id)
    return {
        "logs_dir": bundle_paths.logs_dir,
        "raw_dir": bundle_paths.raw_dir,
        "spec_path": bundle_paths.logs_dir / f"{stem}{_WORKER_SPEC_SUFFIX}",
        "worker_result_path": bundle_paths.logs_dir / f"{stem}{_WORKER_RESULT_SUFFIX}",
        "stdout_log_path": bundle_paths.logs_dir / f"{stem}{_WORKER_STDOUT_SUFFIX}",
        "stderr_log_path": bundle_paths.logs_dir / f"{stem}{_WORKER_STDERR_SUFFIX}",
        "raw_output_path": bundle_paths.raw_dir / f"{stem}{_WORKER_RAW_SUFFIX}",
    }


def _normalize_point_spec(
    point_spec: Mapping[str, Any],
    *,
    default_raw_output_path: Path,
) -> dict[str, Any]:
    normalized_spec = dict(point_spec)
    normalized_spec["point_id"] = _require_non_empty_string(
        point_spec.get("point_id"),
        name="point_id",
    )
    normalized_spec["callable_path"] = _require_non_empty_string(
        point_spec.get("callable_path"),
        name="callable_path",
    )

    raw_output_value = point_spec.get("raw_output_path")
    if raw_output_value is None:
        resolved_raw_output_path = default_raw_output_path
    else:
        resolved_raw_output_path = Path(raw_output_value)
        if not resolved_raw_output_path.is_absolute():
            resolved_raw_output_path = (
                default_raw_output_path.parent.parent / resolved_raw_output_path
            )
    normalized_spec["raw_output_path"] = str(resolved_raw_output_path)

    raw_fieldnames = _normalize_fieldnames(point_spec.get("raw_fieldnames"))
    if raw_fieldnames is not None:
        normalized_spec["raw_fieldnames"] = list(raw_fieldnames)

    _ensure_json_serializable(normalized_spec)
    return normalized_spec


def _normalize_fieldnames(value: object) -> tuple[str, ...] | None:
    if value is None:
        return None
    if isinstance(value, str):
        raise ValueError("raw_fieldnames must be a sequence of strings")
    if not isinstance(value, Sequence):
        raise ValueError("raw_fieldnames must be a sequence of strings")

    fieldnames = tuple(
        _require_non_empty_string(item, name="raw_fieldname") for item in value
    )
    return fieldnames or None


def _normalize_result_payload(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {}
    if not isinstance(payload, Mapping):
        raise TypeError("worker callable must return a mapping or None")
    normalized_payload = dict(payload)
    _ensure_json_serializable(normalized_payload)
    return normalized_payload


def _load_worker_callable(callable_path: str) -> WorkerCallable:
    module_path, _, attr_name = callable_path.rpartition(".")
    if not module_path or not attr_name:
        raise ValueError("callable_path must use the form 'package.module.function'")

    module = importlib.import_module(module_path)
    resolved = getattr(module, attr_name)
    if not callable(resolved):
        raise TypeError(f"Resolved worker target is not callable: {callable_path}")
    return cast(WorkerCallable, resolved)


def _read_worker_result(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, None

    try:
        payload = _read_json_object(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return None, _exception_message(exc)

    return payload, None


def _read_json_object(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return dict(payload)


def _write_json_file(path: Path, payload: Mapping[str, Any]) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
        ) as handle:
            handle.write(rendered)
            temp_path = Path(handle.name)
        temp_path.replace(path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def _ensure_json_serializable(payload: Mapping[str, Any]) -> None:
    try:
        json.dumps(payload, sort_keys=True)
    except TypeError as exc:
        raise TypeError(f"Worker payload must stay JSON-serializable: {exc}") from exc


def _resolve_raw_row_count(
    worker_result: Mapping[str, Any] | None,
    raw_output_path: str | None,
) -> int | None:
    if worker_result is not None and worker_result.get("raw_row_count") is not None:
        return _optional_int(worker_result.get("raw_row_count"))
    if raw_output_path is None:
        return None
    return _count_csv_rows(Path(raw_output_path))


def _count_csv_rows(path: Path) -> int | None:
    if not path.exists():
        return None

    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return sum(1 for _ in csv.DictReader(handle))
    except (OSError, UnicodeDecodeError, csv.Error):
        return None


def _flush_raw_writer(raw_writer: RawCsvWriter | None) -> str | None:
    if raw_writer is None:
        return None
    try:
        raw_writer.flush()
    except Exception as exc:
        return _exception_message(exc)
    return None


def _close_raw_writer(raw_writer: RawCsvWriter | None) -> str | None:
    if raw_writer is None:
        return None
    try:
        raw_writer.close()
    except Exception as exc:
        return _exception_message(exc)
    return None


def _attempt_torch_cuda_synchronize() -> str | None:
    try:
        import torch
    except Exception as exc:
        return _exception_message(exc)

    try:
        torch.cuda.synchronize()
    except Exception as exc:
        return _exception_message(exc)
    return None


def _attempt_torch_cuda_empty_cache() -> str | None:
    try:
        import torch
    except Exception as exc:
        return _exception_message(exc)

    try:
        torch.cuda.empty_cache()
    except Exception as exc:
        return _exception_message(exc)
    return None


def _is_cuda_oom_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    if _OOM_MESSAGE_FRAGMENT in message:
        return True

    if exc.__class__.__name__ == "OutOfMemoryError":
        return True

    try:
        import torch
    except Exception:
        return False

    torch_oom = getattr(torch, "OutOfMemoryError", None)
    if torch_oom is not None and isinstance(exc, torch_oom):
        return True

    cuda_oom = getattr(getattr(torch, "cuda", None), "OutOfMemoryError", None)
    if cuda_oom is not None and isinstance(exc, cuda_oom):
        return True
    return False


def _missing_result_message(exit_code: int | None) -> str:
    if exit_code is None:
        return "Worker exited before recording result metadata"
    signal_name = _exit_signal_name(exit_code)
    if signal_name is not None:
        return f"Worker exited before recording result metadata ({signal_name})"
    return f"Worker exited before recording result metadata (exit_code={exit_code})"


def _exit_signal(exit_code: int | None) -> int | None:
    if exit_code is None or exit_code >= 0:
        return None
    return abs(int(exit_code))


def _exit_signal_name(exit_code: int | None) -> str | None:
    resolved_signal = _exit_signal(exit_code)
    if resolved_signal is None:
        return None
    try:
        return signal.Signals(resolved_signal).name
    except ValueError:
        return str(resolved_signal)


def _require_non_empty_string(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a non-empty string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} must be a non-empty string")
    return normalized


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _optional_mapping(value: object) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    return dict(value)


def _exception_message(exc: BaseException) -> str:
    message = str(exc)
    if message:
        return message
    return f"{exc.__class__.__name__} raised without an error message"


def _slugify(point_id: str) -> str:
    slug = "".join(
        character if character.isalnum() or character in {"-", "_"} else "-"
        for character in point_id
    ).strip("-")
    return slug or "point"


__all__ = ["RawCsvWriter", "run_profile_point"]
