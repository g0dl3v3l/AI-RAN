import pytest

from ai_runtime_experiments.schemas import (
    SCHEMA_VERSION,
    ProbeStatus,
    SmokeClassification,
    make_probe_result,
    validate_probe_result,
)


def test_probe_status_values():
    assert {s.value for s in ProbeStatus} == {
        "ok",
        "unsupported",
        "error",
        "skipped",
        "timeout",
    }


def test_smoke_classification_values():
    assert {c.value for c in SmokeClassification} == {
        "smoke_completed_after_restore",
        "smoke_replayed",
        "smoke_failed_restore",
        "smoke_runtime_failed",
        "smoke_hung",
        "smoke_not_supported",
        "smoke_not_attempted",
    }


def test_unsupported_probe_result_shape():
    record = make_probe_result(
        run_id="run_001",
        component="docker_criu",
        status=ProbeStatus.UNSUPPORTED,
        details={"reason": "Docker checkpoint command unavailable"},
        timestamp_utc="2026-01-01T00:00:00Z",
        monotonic_ns=123,
    )

    validate_probe_result(record)

    assert record["schema_version"] == SCHEMA_VERSION
    assert record["run_id"] == "run_001"
    assert record["status"] == "unsupported"
    assert record["component"] == "docker_criu"
    assert record["timestamp_utc"] == "2026-01-01T00:00:00Z"
    assert record["monotonic_ns"] == 123
    assert record["details"]["reason"] == "Docker checkpoint command unavailable"
