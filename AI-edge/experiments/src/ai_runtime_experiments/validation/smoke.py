from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ai_runtime_experiments.runtime_adapters import (
    RuntimeSession,
    make_smoke_validation_record,
    make_unavailable_smoke_validation,
)
from ai_runtime_experiments.schemas import ProbeStatus, SmokeClassification



def _merge_details(*, reason: str, details: Mapping[str, Any] | None = None) -> dict[str, Any]:
    merged = dict(details or {})
    merged.setdefault("reason", reason)
    return merged



def _with_request_id(record: Mapping[str, Any], *, request_id: str | None) -> dict[str, Any]:
    copied = dict(record)
    copied["details"] = dict(record.get("details") or {})
    if request_id is not None:
        copied["request_id"] = request_id
    return copied



def _status_from_record(record: Mapping[str, Any] | None) -> ProbeStatus | None:
    if record is None:
        return None
    raw_status = record.get("status")
    if isinstance(raw_status, ProbeStatus):
        return raw_status
    if isinstance(raw_status, str):
        try:
            return ProbeStatus(raw_status)
        except ValueError:
            return None
    return None



def make_smoke_completed_after_restore_validation(
    *,
    run_id: str,
    request_id: str | None = None,
    reason: str = "smoke request completed after restore",
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return make_smoke_validation_record(
        run_id=run_id,
        request_id=request_id,
        classification=SmokeClassification.SMOKE_COMPLETED_AFTER_RESTORE,
        status=ProbeStatus.OK,
        details=_merge_details(reason=reason, details=details),
    )



def make_smoke_replayed_validation(
    *,
    run_id: str,
    request_id: str | None = None,
    reason: str = "smoke request replayed after restore",
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return make_smoke_validation_record(
        run_id=run_id,
        request_id=request_id,
        classification=SmokeClassification.SMOKE_REPLAYED,
        status=ProbeStatus.OK,
        details=_merge_details(reason=reason, details=details),
    )



def make_smoke_failed_restore_validation(
    *,
    run_id: str,
    request_id: str | None = None,
    reason: str,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return make_smoke_validation_record(
        run_id=run_id,
        request_id=request_id,
        classification=SmokeClassification.SMOKE_FAILED_RESTORE,
        status=ProbeStatus.ERROR,
        details=_merge_details(reason=reason, details=details),
    )



def make_smoke_runtime_failed_validation(
    *,
    run_id: str,
    request_id: str | None = None,
    reason: str,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return make_smoke_validation_record(
        run_id=run_id,
        request_id=request_id,
        classification=SmokeClassification.SMOKE_RUNTIME_FAILED,
        status=ProbeStatus.ERROR,
        details=_merge_details(reason=reason, details=details),
    )



def make_smoke_hung_validation(
    *,
    run_id: str,
    request_id: str | None = None,
    reason: str,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return make_smoke_validation_record(
        run_id=run_id,
        request_id=request_id,
        classification=SmokeClassification.SMOKE_HUNG,
        status=ProbeStatus.TIMEOUT,
        details=_merge_details(reason=reason, details=details),
    )



def make_smoke_not_supported_validation(
    *,
    run_id: str,
    request_id: str | None = None,
    reason: str,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    record = make_unavailable_smoke_validation(
        run_id=run_id,
        status=ProbeStatus.UNSUPPORTED,
        reason=reason,
        details=_merge_details(reason=reason, details=details),
    )
    return _with_request_id(record, request_id=request_id)



def make_smoke_not_attempted_validation(
    *,
    run_id: str,
    request_id: str | None = None,
    reason: str,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    record = make_unavailable_smoke_validation(
        run_id=run_id,
        status=ProbeStatus.SKIPPED,
        reason=reason,
        details=_merge_details(reason=reason, details=details),
    )
    return _with_request_id(record, request_id=request_id)



def classify_smoke_validation(
    *,
    run_id: str,
    runtime_session: RuntimeSession | None,
    smoke_preemption: Mapping[str, Any] | None,
    request_id: str | None = None,
    response_replayed: bool = False,
) -> dict[str, Any]:
    if runtime_session is not None and runtime_session.smoke_validation is not None:
        return _with_request_id(runtime_session.smoke_validation, request_id=request_id)

    if smoke_preemption is None:
        return make_smoke_not_attempted_validation(
            run_id=run_id,
            request_id=request_id,
            reason="smoke preemption record is missing",
        )

    preemption_details = dict(smoke_preemption.get("details") or {})
    reason = str(preemption_details.get("reason") or "smoke preemption outcome unavailable")
    outcome = str(preemption_details.get("outcome") or "").strip()
    status = _status_from_record(smoke_preemption)
    validation_details = {
        "reason": reason,
        "preemption_status": smoke_preemption.get("status"),
        "preemption": preemption_details,
    }

    if status == ProbeStatus.UNSUPPORTED or outcome == "not_supported":
        return make_smoke_not_supported_validation(
            run_id=run_id,
            request_id=request_id,
            reason=reason,
            details=validation_details,
        )

    if status == ProbeStatus.SKIPPED or outcome == "not_attempted":
        return make_smoke_not_attempted_validation(
            run_id=run_id,
            request_id=request_id,
            reason=reason,
            details=validation_details,
        )

    if status == ProbeStatus.TIMEOUT or outcome == "hung":
        return make_smoke_hung_validation(
            run_id=run_id,
            request_id=request_id,
            reason=reason,
            details=validation_details,
        )

    if status == ProbeStatus.ERROR:
        if outcome == "runtime_failed":
            return make_smoke_runtime_failed_validation(
                run_id=run_id,
                request_id=request_id,
                reason=reason,
                details=validation_details,
            )
        return make_smoke_failed_restore_validation(
            run_id=run_id,
            request_id=request_id,
            reason=reason,
            details=validation_details,
        )

    if response_replayed or outcome == "replayed":
        return make_smoke_replayed_validation(
            run_id=run_id,
            request_id=request_id,
            reason=reason,
            details=validation_details,
        )

    return make_smoke_completed_after_restore_validation(
        run_id=run_id,
        request_id=request_id,
        reason=reason,
        details=validation_details,
    )
