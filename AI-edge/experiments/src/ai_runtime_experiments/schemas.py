from __future__ import annotations

import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping

SCHEMA_VERSION = "0.1.0"


class ProbeStatus(str, Enum):
    OK = "ok"
    UNSUPPORTED = "unsupported"
    ERROR = "error"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"


class SmokeClassification(str, Enum):
    SMOKE_COMPLETED_AFTER_RESTORE = "smoke_completed_after_restore"
    SMOKE_REPLAYED = "smoke_replayed"
    SMOKE_FAILED_RESTORE = "smoke_failed_restore"
    SMOKE_RUNTIME_FAILED = "smoke_runtime_failed"
    SMOKE_HUNG = "smoke_hung"
    SMOKE_NOT_SUPPORTED = "smoke_not_supported"
    SMOKE_NOT_ATTEMPTED = "smoke_not_attempted"


def _utc_now_iso_z() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def make_probe_result(
    *,
    run_id: str,
    component: str,
    status: ProbeStatus,
    details: Mapping[str, Any] | None = None,
    timestamp_utc: str | None = None,
    monotonic_ns: int | None = None,
    schema_version: str = SCHEMA_VERSION,
) -> dict[str, Any]:
    """Construct a structured probe result record.

    This is the minimal V0 record shape shared by all probe artifacts.
    """

    record: dict[str, Any] = {
        "schema_version": schema_version,
        "run_id": run_id,
        "status": status.value,
        "component": component,
        "timestamp_utc": timestamp_utc or _utc_now_iso_z(),
        "monotonic_ns": int(monotonic_ns if monotonic_ns is not None else time.monotonic_ns()),
        "details": dict(details or {}),
    }

    return record


def validate_probe_result(record: Mapping[str, Any]) -> None:
    """Validate minimal probe record shape.

    Raises ValueError if required keys are missing or have invalid types.
    """

    required_keys = (
        "schema_version",
        "run_id",
        "status",
        "component",
        "timestamp_utc",
        "monotonic_ns",
        "details",
    )

    missing = [k for k in required_keys if k not in record]
    if missing:
        raise ValueError(f"Missing required keys: {missing}")

    if not isinstance(record["schema_version"], str):
        raise ValueError("schema_version must be a string")
    if not isinstance(record["run_id"], str):
        raise ValueError("run_id must be a string")
    if not isinstance(record["component"], str):
        raise ValueError("component must be a string")
    if not isinstance(record["timestamp_utc"], str):
        raise ValueError("timestamp_utc must be a string")
    if not isinstance(record["monotonic_ns"], int):
        raise ValueError("monotonic_ns must be an int")
    if not isinstance(record["details"], Mapping):
        raise ValueError("details must be a mapping")

    status = record["status"]
    if not isinstance(status, str):
        raise ValueError("status must be a string")

    allowed = {s.value for s in ProbeStatus}
    if status not in allowed:
        raise ValueError(f"status must be one of {sorted(allowed)}")
