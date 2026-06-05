from __future__ import annotations

from ai_runtime_experiments.runtime_adapters import RuntimeSession
from ai_runtime_experiments.schemas import ProbeStatus, SmokeClassification, make_probe_result


def _runtime_session(*, smoke_validation: dict[str, object] | None = None) -> RuntimeSession:
    return RuntimeSession(
        runtime="vllm",
        mode="docker_server",
        status=ProbeStatus.OK,
        runtime_check=make_probe_result(
            run_id="task-8",
            component="runtime_check",
            status=ProbeStatus.OK,
            details={"runtime": "vllm", "mode": "docker_server"},
        ),
        base_url="http://127.0.0.1:8000/v1",
        smoke_validation=smoke_validation,
        container_name="ai-edge-v0-vllm-fixed",
        container_id="container-123",
    )


def _smoke_preemption(
    *,
    status: ProbeStatus,
    outcome: str,
    reason: str,
) -> dict[str, object]:
    return make_probe_result(
        run_id="task-8",
        component="smoke_preemption",
        status=status,
        details={
            "reason": reason,
            "outcome": outcome,
            "smoke": {"attempted": status in {ProbeStatus.OK, ProbeStatus.ERROR, ProbeStatus.TIMEOUT}},
            "checkpoint": {"attempted": outcome not in {"not_attempted", "not_supported"}},
            "restore": {"attempted": outcome in {"restore_failed", "runtime_failed", "replayed", "restored"}},
        },
    )


def test_skipped_preemption_classified_as_smoke_not_attempted():
    from ai_runtime_experiments.validation import classify_smoke_validation

    record = classify_smoke_validation(
        run_id="task-8",
        runtime_session=_runtime_session(),
        smoke_preemption=_smoke_preemption(
            status=ProbeStatus.SKIPPED,
            outcome="not_attempted",
            reason="runtime session has no experiment-owned container",
        ),
        request_id="req-skip",
    )

    assert record["status"] == "skipped"
    assert record["classification"] == SmokeClassification.SMOKE_NOT_ATTEMPTED.value
    assert record["request_id"] == "req-skip"


def test_checkpoint_error_classified_as_smoke_failed_restore():
    from ai_runtime_experiments.validation import classify_smoke_validation

    record = classify_smoke_validation(
        run_id="task-8",
        runtime_session=_runtime_session(),
        smoke_preemption=_smoke_preemption(
            status=ProbeStatus.ERROR,
            outcome="checkpoint_failed",
            reason="command failure(s): docker checkpoint create",
        ),
        request_id="req-error",
    )

    assert record["status"] == "error"
    assert record["classification"] == SmokeClassification.SMOKE_FAILED_RESTORE.value
    assert record["details"]["preemption"]["outcome"] == "checkpoint_failed"


def test_unsupported_preemption_classified_as_smoke_not_supported():
    from ai_runtime_experiments.validation import classify_smoke_validation

    record = classify_smoke_validation(
        run_id="task-8",
        runtime_session=_runtime_session(),
        smoke_preemption=_smoke_preemption(
            status=ProbeStatus.UNSUPPORTED,
            outcome="not_supported",
            reason="unsupported capability: docker checkpoint create",
        ),
        request_id="req-unsupported",
    )

    assert record["status"] == "unsupported"
    assert record["classification"] == SmokeClassification.SMOKE_NOT_SUPPORTED.value
    assert record["details"]["reason"] == "unsupported capability: docker checkpoint create"



def test_restored_preemption_with_response_completed_before_restore_is_not_attempted():
    from ai_runtime_experiments.validation import classify_smoke_validation

    record = classify_smoke_validation(
        run_id="task-8",
        runtime_session=_runtime_session(),
        smoke_preemption=make_probe_result(
            run_id="task-8",
            component="smoke_preemption",
            status=ProbeStatus.OK,
            details={
                "reason": "checkpoint and restore completed",
                "outcome": "restored",
                "smoke": {
                    "attempted": True,
                    "response_completed_before_restore": True,
                    "response_monotonic_ns": 100,
                },
                "checkpoint": {"attempted": True},
                "restore": {"attempted": True, "start_monotonic_ns": 200},
            },
        ),
        request_id="req-before-restore",
    )

    assert record["status"] == "skipped"
    assert record["classification"] == SmokeClassification.SMOKE_NOT_ATTEMPTED.value
    assert "before restore" in record["details"]["reason"]
