from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from inference_profile import trace_contract

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures"


def _fixture_path(name: str) -> Path:
    return FIXTURE_ROOT / name


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_validate_trace_contract_normalizes_schema_b_fixture(tmp_path: Path) -> None:
    output_root = tmp_path / "trace-ok"

    result = trace_contract.validate_trace_contract(
        ldpc_trace=_fixture_path("ldpc_trace_valid.csv"),
        ran_ctrl_trace=_fixture_path("ran_ctrl_trace_valid.csv"),
        output_root=output_root,
    )

    assert result.success is True
    normalized_trace_path = result.normalized_trace_path
    assert normalized_trace_path is not None
    assert (
        normalized_trace_path
        == output_root / "derived" / trace_contract.NORMALIZED_TRACE_FILENAME
    )
    assert not (
        output_root / "raw" / trace_contract.VALIDATION_ERRORS_FILENAME
    ).exists()

    normalized_rows = _read_csv_rows(normalized_trace_path)
    assert normalized_rows == [
        {
            "time_ms": "1",
            "sm_utilization": "0",
            "slot_duration_ms": "1.5",
            "source_schema": trace_contract.SOURCE_SCHEMA_B,
        },
        {
            "time_ms": "2.5",
            "sm_utilization": "100",
            "slot_duration_ms": "1",
            "source_schema": trace_contract.SOURCE_SCHEMA_B,
        },
        {
            "time_ms": "3.5",
            "sm_utilization": "0",
            "slot_duration_ms": "1.25",
            "source_schema": trace_contract.SOURCE_SCHEMA_B,
        },
    ]

    inspection = _read_json(result.trace_inspection_path)
    primary = inspection["primary_trace"]
    secondary = inspection["secondary_trace"]
    assert primary["schema_detected"] == trace_contract.SOURCE_SCHEMA_B
    assert primary["usable"] is True
    assert primary["monotonicity"] == {
        "checked_column": "time_slot_sched_ns",
        "is_non_decreasing": True,
        "negative_delta_count": 0,
        "zero_delta_count": 0,
        "positive_delta_count": 2,
    }
    assert secondary["usable"] is True
    assert secondary["used_for_scheduler_capacity"] is False
    assert secondary["time_unit_hints"] == ["ns"]


def test_normalize_primary_trace_supports_schema_a(tmp_path: Path) -> None:
    trace_path = tmp_path / "ldpc_trace_schema_a.csv"
    trace_path.write_text(
        "time_ms,sm_utilization\n0,20\n1,60\n3,0\n",
        encoding="utf-8",
    )

    normalized_rows, inspection, issues = trace_contract.normalize_primary_trace(
        trace_path
    )

    assert issues == ()
    assert inspection["schema_detected"] == trace_contract.SOURCE_SCHEMA_A
    assert inspection["usable"] is True
    assert inspection["median_positive_delta_ms"] == 1.5
    assert normalized_rows == [
        {
            "time_ms": 0.0,
            "sm_utilization": 20.0,
            "slot_duration_ms": 1.0,
            "source_schema": trace_contract.SOURCE_SCHEMA_A,
        },
        {
            "time_ms": 1.0,
            "sm_utilization": 60.0,
            "slot_duration_ms": 2.0,
            "source_schema": trace_contract.SOURCE_SCHEMA_A,
        },
        {
            "time_ms": 3.0,
            "sm_utilization": 0.0,
            "slot_duration_ms": 1.5,
            "source_schema": trace_contract.SOURCE_SCHEMA_A,
        },
    ]


def test_validate_trace_contract_fails_closed_on_missing_column_fixture(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "trace-bad"

    result = trace_contract.validate_trace_contract(
        ldpc_trace=_fixture_path("ldpc_trace_missing_column.csv"),
        ran_ctrl_trace=_fixture_path("ran_ctrl_trace_valid.csv"),
        output_root=output_root,
    )

    assert result.success is False
    assert result.normalized_trace_path is None
    validation_errors_path = result.validation_errors_path
    assert validation_errors_path is not None
    assert (
        validation_errors_path
        == output_root / "raw" / trace_contract.VALIDATION_ERRORS_FILENAME
    )
    assert validation_errors_path.exists()
    assert not (
        output_root / "derived" / trace_contract.NORMALIZED_TRACE_FILENAME
    ).exists()

    validation_rows = _read_csv_rows(validation_errors_path)
    assert validation_rows == [
        {
            "trace_name": "ldpc_trace.csv",
            "error_code": "unsupported_schema",
            "message": (
                "Primary ldpc_trace.csv must use exactly one of the supported "
                "headers: time_ms,sm_utilization or time_slot_sched_ns,sm_count"
            ),
        }
    ]

    inspection = _read_json(result.trace_inspection_path)
    assert inspection["primary_trace"]["usable"] is False
    assert inspection["secondary_trace"]["usable"] is True


def test_normalize_primary_trace_rejects_negative_forward_delta_fixture() -> None:
    normalized_rows, inspection, issues = trace_contract.normalize_primary_trace(
        _fixture_path("ldpc_trace_negative_delta.csv")
    )

    assert normalized_rows == []
    assert inspection["usable"] is False
    assert inspection["monotonicity"] == {
        "checked_column": "time_slot_sched_ns",
        "is_non_decreasing": False,
        "negative_delta_count": 1,
        "zero_delta_count": 0,
        "positive_delta_count": 1,
    }
    assert [issue.error_code for issue in issues] == ["non_monotonic_time"]


def test_normalize_primary_trace_rejects_duplicate_header_fixture() -> None:
    normalized_rows, inspection, issues = trace_contract.normalize_primary_trace(
        _fixture_path("ldpc_trace_duplicate_header.csv")
    )

    assert normalized_rows == []
    assert inspection["usable"] is False
    assert [issue.error_code for issue in issues] == ["duplicate_header"]


def test_normalize_primary_trace_rejects_utf8_bom_header(tmp_path: Path) -> None:
    trace_path = tmp_path / "ldpc_trace_bom.csv"
    trace_path.write_text(
        "time_slot_sched_ns,sm_count\n1000000,1\n2000000,0\n",
        encoding="utf-8-sig",
    )

    normalized_rows, inspection, issues = trace_contract.normalize_primary_trace(
        trace_path
    )

    assert normalized_rows == []
    assert inspection["usable"] is False
    assert [issue.error_code for issue in issues] == ["bom_header"]


def test_normalize_primary_trace_rejects_invalid_utf8_bytes(tmp_path: Path) -> None:
    trace_path = tmp_path / "ldpc_trace_corrupt.csv"
    trace_path.write_bytes(b"time_slot_sched_ns,sm_count\n1000000,\xff\n")

    normalized_rows, inspection, issues = trace_contract.normalize_primary_trace(
        trace_path
    )

    assert normalized_rows == []
    assert inspection["usable"] is False
    assert [issue.error_code for issue in issues] == ["invalid_encoding"]


def test_secondary_trace_is_structural_only_and_does_not_block_primary_success(
    tmp_path: Path,
) -> None:
    ran_ctrl_trace = tmp_path / "ran_ctrl_trace_no_time.csv"
    ran_ctrl_trace.write_text(
        "ran_state\ngrant\nhold\n",
        encoding="utf-8",
    )

    output_root = tmp_path / "secondary-unusable"
    result = trace_contract.validate_trace_contract(
        ldpc_trace=_fixture_path("ldpc_trace_valid.csv"),
        ran_ctrl_trace=ran_ctrl_trace,
        output_root=output_root,
    )

    assert result.success is True
    inspection = _read_json(result.trace_inspection_path)
    assert inspection["secondary_trace"]["usable"] is False
    assert inspection["secondary_trace"]["used_for_scheduler_capacity"] is False
    assert (output_root / "derived" / trace_contract.NORMALIZED_TRACE_FILENAME).exists()
