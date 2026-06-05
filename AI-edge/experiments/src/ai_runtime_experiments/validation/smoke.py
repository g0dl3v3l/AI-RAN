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



def _smoke_response_evidence(
    *,
    smoke_preemption: Mapping[str, Any] | None,
    smoke_response: Mapping[str, Any] | None,
    smoke_request: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    preemption_details = dict((smoke_preemption or {}).get("details") or {})
    smoke_details = preemption_details.get("smoke")
    checkpoint_details = preemption_details.get("checkpoint")
    restore_details = preemption_details.get("restore")

    request_status_raw = None
    request_monotonic_ns = None
    if isinstance(smoke_request, Mapping):
        request_status_raw = smoke_request.get("status")
        raw_request_monotonic_ns = smoke_request.get("monotonic_ns")
        if isinstance(raw_request_monotonic_ns, int):
            request_monotonic_ns = raw_request_monotonic_ns

    response_status_raw = None
    response_status = None
    response_monotonic_ns = None
    if isinstance(smoke_response, Mapping):
        response_status_raw = smoke_response.get("status")
        response_status = _status_from_record(smoke_response)
        raw_monotonic_ns = smoke_response.get("monotonic_ns")
        if isinstance(raw_monotonic_ns, int):
            response_monotonic_ns = raw_monotonic_ns

    request_started_before_checkpoint = False
    response_completed_before_restore = False
    response_completed_after_restore = False
    if isinstance(smoke_details, Mapping):
        if request_status_raw is None:
            request_status_raw = smoke_details.get("request_status")
        if request_monotonic_ns is None:
            raw_request_monotonic_ns = smoke_details.get("request_monotonic_ns")
            if isinstance(raw_request_monotonic_ns, int):
                request_monotonic_ns = raw_request_monotonic_ns
        request_started_before_checkpoint = bool(
            smoke_details.get("request_started_before_checkpoint")
        )
        if response_status_raw is None:
            response_status_raw = smoke_details.get("response_status")
        if response_monotonic_ns is None:
            raw_monotonic_ns = smoke_details.get("response_monotonic_ns")
            if isinstance(raw_monotonic_ns, int):
                response_monotonic_ns = raw_monotonic_ns
        response_completed_before_restore = bool(
            smoke_details.get("response_completed_before_restore")
        )
        response_completed_after_restore = bool(
            smoke_details.get("response_completed_after_restore")
        )

    checkpoint_start_monotonic_ns = None
    if isinstance(checkpoint_details, Mapping):
        raw_checkpoint_start_monotonic_ns = checkpoint_details.get("start_monotonic_ns")
        if isinstance(raw_checkpoint_start_monotonic_ns, int):
            checkpoint_start_monotonic_ns = raw_checkpoint_start_monotonic_ns

    restore_start_monotonic_ns = None
    restore_end_monotonic_ns = None
    if isinstance(restore_details, Mapping):
        raw_restore_start_monotonic_ns = restore_details.get("start_monotonic_ns")
        if isinstance(raw_restore_start_monotonic_ns, int):
            restore_start_monotonic_ns = raw_restore_start_monotonic_ns
        raw_restore_end_monotonic_ns = restore_details.get("end_monotonic_ns")
        if isinstance(raw_restore_end_monotonic_ns, int):
            restore_end_monotonic_ns = raw_restore_end_monotonic_ns

    if isinstance(request_monotonic_ns, int):
        if isinstance(checkpoint_start_monotonic_ns, int):
            request_started_before_checkpoint = request_monotonic_ns <= checkpoint_start_monotonic_ns
        elif isinstance(restore_start_monotonic_ns, int):
            request_started_before_checkpoint = request_monotonic_ns <= restore_start_monotonic_ns

    if response_status == ProbeStatus.OK and isinstance(response_monotonic_ns, int):
        if isinstance(restore_start_monotonic_ns, int):
            response_completed_before_restore = response_monotonic_ns < restore_start_monotonic_ns
        if isinstance(restore_end_monotonic_ns, int):
            response_completed_after_restore = response_monotonic_ns >= restore_end_monotonic_ns

    return {
        "request_status": request_status_raw,
        "request_monotonic_ns": request_monotonic_ns,
        "request_started_before_checkpoint": request_started_before_checkpoint,
        "status": response_status_raw,
        "monotonic_ns": response_monotonic_ns,
        "completed_before_restore": response_completed_before_restore,
        "completed_after_restore": response_completed_after_restore,
    }



def classify_smoke_validation(
    *,
    run_id: str,
    runtime_session: RuntimeSession | None,
    smoke_preemption: Mapping[str, Any] | None,
    request_id: str | None = None,
    smoke_response: Mapping[str, Any] | None = None,
    smoke_request: Mapping[str, Any] | None = None,
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
    response_evidence = _smoke_response_evidence(
        smoke_preemption=smoke_preemption,
        smoke_response=smoke_response,
        smoke_request=smoke_request,
    )
    validation_details = {
        "reason": reason,
        "preemption_status": smoke_preemption.get("status"),
        "preemption": preemption_details,
        "smoke_response": response_evidence,
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

    if response_evidence["completed_before_restore"]:
        timing_reason = (
            "smoke response completed before restore; post-restore completion was not observed"
        )
        timing_details = dict(validation_details)
        timing_details["reason"] = timing_reason
        return make_smoke_not_attempted_validation(
            run_id=run_id,
            request_id=request_id,
            reason=timing_reason,
            details=timing_details,
        )

    if not response_evidence["completed_after_restore"]:
        timing_reason = "successful smoke response after restore completion was not observed"
        timing_details = dict(validation_details)
        timing_details["reason"] = timing_reason
        return make_smoke_not_attempted_validation(
            run_id=run_id,
            request_id=request_id,
            reason=timing_reason,
            details=timing_details,
        )

    if not response_evidence["request_started_before_checkpoint"]:
        timing_reason = "request was not observed before checkpoint or restore timing"
        timing_details = dict(validation_details)
        timing_details["reason"] = timing_reason
        return make_smoke_not_attempted_validation(
            run_id=run_id,
            request_id=request_id,
            reason=timing_reason,
            details=timing_details,
        )

    if outcome == "replayed":
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
