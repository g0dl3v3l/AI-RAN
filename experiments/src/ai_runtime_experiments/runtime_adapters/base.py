from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Mapping

from ai_runtime_experiments.schemas import SCHEMA_VERSION, ProbeStatus, SmokeClassification
from ai_runtime_experiments.utils.time import monotonic_ns, utc_now_iso_z


@dataclass(frozen=True)
class RuntimeSession:
    runtime: str
    mode: str
    status: ProbeStatus
    runtime_check: dict[str, Any]
    base_url: str | None = None
    smoke_validation: dict[str, Any] | None = None
    container_name: str | None = None
    container_id: str | None = None


class BaseRuntimeAdapter(ABC):
    @abstractmethod
    def start(self, *, run_id: str) -> RuntimeSession:
        """Start or resolve the runtime session for a single experiment run."""

    @abstractmethod
    def stop(self, session: RuntimeSession) -> dict[str, Any] | None:
        """Stop runtime resources if this adapter created them."""


_UNAVAILABLE_CLASSIFICATION = {
    ProbeStatus.SKIPPED: SmokeClassification.SMOKE_NOT_ATTEMPTED,
    ProbeStatus.UNSUPPORTED: SmokeClassification.SMOKE_NOT_SUPPORTED,
    ProbeStatus.ERROR: SmokeClassification.SMOKE_NOT_ATTEMPTED,
    ProbeStatus.TIMEOUT: SmokeClassification.SMOKE_NOT_ATTEMPTED,
}



def make_smoke_validation_record(
    *,
    run_id: str,
    classification: SmokeClassification,
    status: ProbeStatus,
    details: Mapping[str, Any] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "request_id": request_id,
        "status": status.value,
        "classification": classification.value,
        "timestamp_utc": utc_now_iso_z(),
        "monotonic_ns": monotonic_ns(),
        "details": dict(details or {}),
    }
    return record



def make_unavailable_smoke_validation(
    *,
    run_id: str,
    status: ProbeStatus,
    reason: str,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    classification = _UNAVAILABLE_CLASSIFICATION.get(status)
    if classification is None:
        raise ValueError(f"status does not imply unavailable runtime: {status!r}")

    merged_details = dict(details or {})
    merged_details.setdefault("reason", reason)
    return make_smoke_validation_record(
        run_id=run_id,
        classification=classification,
        status=status,
        details=merged_details,
    )
