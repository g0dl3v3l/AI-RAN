from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any

PRIMARY_TRACE_NAME = "ldpc_trace.csv"
SECONDARY_TRACE_NAME = "ran_ctrl_trace.csv"

PRIMARY_SCHEMA_A_HEADERS = ("time_ms", "sm_utilization")
PRIMARY_SCHEMA_B_HEADERS = ("time_slot_sched_ns", "sm_count")
NORMALIZED_TRACE_HEADERS = (
    "time_ms",
    "sm_utilization",
    "slot_duration_ms",
    "source_schema",
)
VALIDATION_ERROR_HEADERS = ("trace_name", "error_code", "message")

NORMALIZED_TRACE_FILENAME = "normalized_ldpc_trace.csv"
TRACE_INSPECTION_FILENAME = "trace_inspection.json"
VALIDATION_ERRORS_FILENAME = "validation_errors.csv"

SOURCE_SCHEMA_A = "schema_a"
SOURCE_SCHEMA_B = "schema_b"


@dataclass(frozen=True)
class ValidationIssue:
    trace_name: str
    error_code: str
    message: str

    def as_csv_row(self) -> dict[str, str]:
        return {
            "trace_name": self.trace_name,
            "error_code": self.error_code,
            "message": self.message,
        }


@dataclass(frozen=True)
class CsvReadResult:
    header: tuple[str, ...]
    rows: tuple[tuple[int, tuple[str, ...]], ...]
    issues: tuple[ValidationIssue, ...]


@dataclass(frozen=True)
class TraceContractResult:
    output_root: Path
    normalized_trace_path: Path | None
    trace_inspection_path: Path
    validation_errors_path: Path | None
    inspection: dict[str, Any]
    validation_errors: tuple[ValidationIssue, ...]

    @property
    def success(self) -> bool:
        return len(self.validation_errors) == 0

    def user_error_message(self) -> str:
        if self.success:
            return ""
        summary = self.validation_errors[0].message
        if self.validation_errors_path is None:
            return summary
        return f"{summary}. See {self.validation_errors_path}"


def validate_trace_contract(
    ldpc_trace: str | Path,
    ran_ctrl_trace: str | Path,
    output_root: str | Path,
) -> TraceContractResult:
    output_root_path = Path(output_root)
    raw_dir = output_root_path / "raw"
    derived_dir = output_root_path / "derived"
    raw_dir.mkdir(parents=True, exist_ok=True)
    derived_dir.mkdir(parents=True, exist_ok=True)

    normalized_trace_path = derived_dir / NORMALIZED_TRACE_FILENAME
    trace_inspection_path = raw_dir / TRACE_INSPECTION_FILENAME
    validation_errors_path = raw_dir / VALIDATION_ERRORS_FILENAME

    _remove_if_exists(normalized_trace_path)
    _remove_if_exists(validation_errors_path)

    normalized_rows, primary_inspection, primary_issues = normalize_primary_trace(
        ldpc_trace
    )
    secondary_inspection = inspect_secondary_trace(ran_ctrl_trace)
    inspection = {
        "primary_trace": primary_inspection,
        "secondary_trace": secondary_inspection,
    }
    _write_json(trace_inspection_path, inspection)

    if primary_issues:
        _write_validation_errors(validation_errors_path, primary_issues)
        return TraceContractResult(
            output_root=output_root_path,
            normalized_trace_path=None,
            trace_inspection_path=trace_inspection_path,
            validation_errors_path=validation_errors_path,
            inspection=inspection,
            validation_errors=primary_issues,
        )

    _write_normalized_trace(normalized_trace_path, normalized_rows)
    return TraceContractResult(
        output_root=output_root_path,
        normalized_trace_path=normalized_trace_path,
        trace_inspection_path=trace_inspection_path,
        validation_errors_path=None,
        inspection=inspection,
        validation_errors=(),
    )


def normalize_primary_trace(
    path: str | Path,
) -> tuple[list[dict[str, Any]], dict[str, Any], tuple[ValidationIssue, ...]]:
    trace_path = Path(path)
    inspection = _base_primary_inspection(trace_path)
    read_result = _read_csv(trace_path, PRIMARY_TRACE_NAME)
    inspection["header"] = list(read_result.header)
    inspection["row_count"] = len(read_result.rows)

    issues = list(read_result.issues)
    normalized_rows: list[dict[str, Any]] = []
    time_values_ms: list[float] = []
    sm_utilization_values: list[float] = []
    source_schema: str | None = None
    time_column: str | None = None

    if not issues:
        if read_result.header == PRIMARY_SCHEMA_A_HEADERS:
            source_schema = SOURCE_SCHEMA_A
            time_column = PRIMARY_SCHEMA_A_HEADERS[0]
            inspection["schema_detected"] = source_schema
            inspection["time_unit_hint"] = "ms"
            time_values_ms, sm_utilization_values, issues = _parse_schema_a_rows(
                read_result.rows
            )
        elif read_result.header == PRIMARY_SCHEMA_B_HEADERS:
            source_schema = SOURCE_SCHEMA_B
            time_column = PRIMARY_SCHEMA_B_HEADERS[0]
            inspection["schema_detected"] = source_schema
            inspection["time_unit_hint"] = "ns"
            time_values_ms, sm_utilization_values, issues = _parse_schema_b_rows(
                read_result.rows
            )
        else:
            issues.append(
                ValidationIssue(
                    trace_name=PRIMARY_TRACE_NAME,
                    error_code="unsupported_schema",
                    message=(
                        "Primary ldpc_trace.csv must use exactly one of the supported "
                        "headers: time_ms,sm_utilization or time_slot_sched_ns,sm_count"
                    ),
                )
            )

    if not issues and source_schema is not None and time_column is not None:
        (
            slot_durations_ms,
            negative_delta_count,
            zero_delta_count,
            positive_delta_count,
            median_positive_delta_ms,
            delta_issues,
        ) = _derive_slot_durations_ms(time_values_ms)
        issues.extend(delta_issues)
        inspection["monotonicity"] = {
            "checked_column": time_column,
            "is_non_decreasing": negative_delta_count == 0,
            "negative_delta_count": negative_delta_count,
            "zero_delta_count": zero_delta_count,
            "positive_delta_count": positive_delta_count,
        }
        inspection["median_positive_delta_ms"] = median_positive_delta_ms

        if not issues:
            normalized_rows = [
                {
                    "time_ms": time_values_ms[index],
                    "sm_utilization": sm_utilization_values[index],
                    "slot_duration_ms": slot_durations_ms[index],
                    "source_schema": source_schema,
                }
                for index in range(len(time_values_ms))
            ]
            inspection["normalized_row_count"] = len(normalized_rows)

    inspection["errors"] = [issue.message for issue in issues]
    inspection["usable"] = len(issues) == 0
    return normalized_rows, inspection, tuple(issues)


def inspect_secondary_trace(path: str | Path) -> dict[str, Any]:
    trace_path = Path(path)
    inspection = _base_secondary_inspection(trace_path)
    read_result = _read_csv(trace_path, SECONDARY_TRACE_NAME)
    inspection["header"] = list(read_result.header)
    inspection["row_count"] = len(read_result.rows)

    issues = list(read_result.issues)
    time_column = _select_time_column(read_result.header)
    inspection["time_unit_hints"] = _time_unit_hints(read_result.header)

    if not issues and time_column is None:
        issues.append(
            ValidationIssue(
                trace_name=SECONDARY_TRACE_NAME,
                error_code="missing_time_column_hint",
                message=(
                    "Secondary ran_ctrl_trace.csv does not expose a time-like column "
                    "for monotonicity inspection"
                ),
            )
        )

    if not issues and time_column is not None:
        time_values, time_issues = _parse_secondary_time_column(
            read_result.rows,
            read_result.header,
            time_column,
        )
        issues.extend(time_issues)
        if not time_issues:
            negative_delta_count = 0
            previous = time_values[0]
            for current in time_values[1:]:
                if current < previous:
                    negative_delta_count += 1
                previous = current
            inspection["monotonicity"] = {
                "checked_column": time_column,
                "is_non_decreasing": negative_delta_count == 0,
                "negative_delta_count": negative_delta_count,
            }
            if negative_delta_count > 0:
                issues.append(
                    ValidationIssue(
                        trace_name=SECONDARY_TRACE_NAME,
                        error_code="non_monotonic_time",
                        message=(
                            f"Secondary ran_ctrl_trace.csv column '{time_column}' "
                            "must be monotonically non-decreasing"
                        ),
                    )
                )

    inspection["errors"] = [issue.message for issue in issues]
    inspection["usable"] = len(issues) == 0
    return inspection


def _parse_schema_a_rows(
    rows: tuple[tuple[int, tuple[str, ...]], ...],
) -> tuple[list[float], list[float], list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    time_values_ms: list[float] = []
    sm_utilization_values: list[float] = []

    for line_number, cells in rows:
        time_ms = _coerce_float(cells[0], column="time_ms", line_number=line_number)
        sm_utilization = _coerce_float(
            cells[1],
            column="sm_utilization",
            line_number=line_number,
        )
        if time_ms is None or sm_utilization is None:
            issues.append(
                ValidationIssue(
                    trace_name=PRIMARY_TRACE_NAME,
                    error_code="non_numeric_value",
                    message=(
                        "Primary ldpc_trace.csv schema A contains non-numeric values; "
                        f"check CSV line {line_number}"
                    ),
                )
            )
            continue
        if time_ms < 0:
            issues.append(
                ValidationIssue(
                    trace_name=PRIMARY_TRACE_NAME,
                    error_code="negative_time",
                    message=(
                        f"Primary ldpc_trace.csv time_ms must be >= 0; check CSV line {line_number}"
                    ),
                )
            )
            continue
        if sm_utilization < 0 or sm_utilization > 100:
            issues.append(
                ValidationIssue(
                    trace_name=PRIMARY_TRACE_NAME,
                    error_code="sm_utilization_out_of_range",
                    message=(
                        "Primary ldpc_trace.csv schema A requires sm_utilization in [0, 100]; "
                        f"check CSV line {line_number}"
                    ),
                )
            )
            continue
        time_values_ms.append(time_ms)
        sm_utilization_values.append(sm_utilization)

    return time_values_ms, sm_utilization_values, issues


def _parse_schema_b_rows(
    rows: tuple[tuple[int, tuple[str, ...]], ...],
) -> tuple[list[float], list[float], list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    time_values_ms: list[float] = []
    sm_utilization_values: list[float] = []

    for line_number, cells in rows:
        time_slot_sched_ns = _coerce_float(
            cells[0],
            column="time_slot_sched_ns",
            line_number=line_number,
        )
        sm_count = _coerce_float(cells[1], column="sm_count", line_number=line_number)
        if time_slot_sched_ns is None or sm_count is None:
            issues.append(
                ValidationIssue(
                    trace_name=PRIMARY_TRACE_NAME,
                    error_code="non_numeric_value",
                    message=(
                        "Primary ldpc_trace.csv schema B contains non-numeric values; "
                        f"check CSV line {line_number}"
                    ),
                )
            )
            continue
        if time_slot_sched_ns < 0:
            issues.append(
                ValidationIssue(
                    trace_name=PRIMARY_TRACE_NAME,
                    error_code="negative_time",
                    message=(
                        "Primary ldpc_trace.csv time_slot_sched_ns must be >= 0; "
                        f"check CSV line {line_number}"
                    ),
                )
            )
            continue
        if not sm_count.is_integer():
            issues.append(
                ValidationIssue(
                    trace_name=PRIMARY_TRACE_NAME,
                    error_code="non_integer_sm_count",
                    message=(
                        "Primary ldpc_trace.csv schema B requires integer sm_count values; "
                        f"check CSV line {line_number}"
                    ),
                )
            )
            continue
        sm_count_int = int(sm_count)
        if sm_count_int < 0:
            issues.append(
                ValidationIssue(
                    trace_name=PRIMARY_TRACE_NAME,
                    error_code="negative_sm_count",
                    message=(
                        f"Primary ldpc_trace.csv sm_count must be >= 0; check CSV line {line_number}"
                    ),
                )
            )
            continue
        time_values_ms.append(time_slot_sched_ns / 1e6)
        sm_utilization_values.append(100.0 if sm_count_int > 0 else 0.0)

    return time_values_ms, sm_utilization_values, issues


def _derive_slot_durations_ms(
    time_values_ms: list[float],
) -> tuple[list[float], int, int, int, float | None, list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    if not time_values_ms:
        return [], 0, 0, 0, None, issues

    deltas_ms = [
        time_values_ms[index + 1] - time_values_ms[index]
        for index in range(len(time_values_ms) - 1)
    ]
    negative_delta_count = sum(delta < 0 for delta in deltas_ms)
    zero_delta_count = sum(delta == 0 for delta in deltas_ms)
    positive_deltas_ms = [delta for delta in deltas_ms if delta > 0]
    positive_delta_count = len(positive_deltas_ms)

    if negative_delta_count > 0:
        issues.append(
            ValidationIssue(
                trace_name=PRIMARY_TRACE_NAME,
                error_code="non_monotonic_time",
                message=(
                    "Primary ldpc_trace.csv timestamps must be monotonically "
                    "non-decreasing; negative forward deltas are not allowed"
                ),
            )
        )

    if positive_delta_count == 0:
        issues.append(
            ValidationIssue(
                trace_name=PRIMARY_TRACE_NAME,
                error_code="missing_positive_delta",
                message=(
                    "Primary ldpc_trace.csv must contain at least one positive forward "
                    "delta to derive slot_duration_ms"
                ),
            )
        )
        return (
            [],
            negative_delta_count,
            zero_delta_count,
            positive_delta_count,
            None,
            issues,
        )

    median_positive_delta_ms = float(median(positive_deltas_ms))
    slot_durations_ms = list(deltas_ms)
    slot_durations_ms.append(median_positive_delta_ms)
    return (
        slot_durations_ms,
        negative_delta_count,
        zero_delta_count,
        positive_delta_count,
        median_positive_delta_ms,
        issues,
    )


def _parse_secondary_time_column(
    rows: tuple[tuple[int, tuple[str, ...]], ...],
    header: tuple[str, ...],
    time_column: str,
) -> tuple[list[float], list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    index = header.index(time_column)
    time_values: list[float] = []

    for line_number, cells in rows:
        value = _coerce_float(cells[index], column=time_column, line_number=line_number)
        if value is None:
            issues.append(
                ValidationIssue(
                    trace_name=SECONDARY_TRACE_NAME,
                    error_code="non_numeric_time",
                    message=(
                        "Secondary ran_ctrl_trace.csv contains non-numeric time values; "
                        f"check CSV line {line_number}"
                    ),
                )
            )
            continue
        time_values.append(value)

    return time_values, issues


def _read_csv(path: Path, trace_name: str) -> CsvReadResult:
    issues: list[ValidationIssue] = []
    header: tuple[str, ...] = ()
    rows: list[tuple[int, tuple[str, ...]]] = []

    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            raw_header = next(reader, None)
            if raw_header is None:
                issues.append(
                    ValidationIssue(
                        trace_name=trace_name,
                        error_code="missing_header",
                        message=f"{trace_name} is empty and does not contain a CSV header",
                    )
                )
                return CsvReadResult(header=(), rows=(), issues=tuple(issues))

            header = tuple(raw_header)
            if any("\ufeff" in field for field in header):
                issues.append(
                    ValidationIssue(
                        trace_name=trace_name,
                        error_code="bom_header",
                        message=f"{trace_name} header contains a UTF-8 BOM and must be rewritten without it",
                    )
                )
            duplicate_headers = sorted(
                {field for field in header if header.count(field) > 1}
            )
            if duplicate_headers:
                issues.append(
                    ValidationIssue(
                        trace_name=trace_name,
                        error_code="duplicate_header",
                        message=(
                            f"{trace_name} contains duplicate header names: "
                            + ", ".join(duplicate_headers)
                        ),
                    )
                )
            if any(field == "" for field in header):
                issues.append(
                    ValidationIssue(
                        trace_name=trace_name,
                        error_code="empty_header_name",
                        message=f"{trace_name} contains an empty header name",
                    )
                )

            for line_number, row in enumerate(reader, start=2):
                if len(row) != len(header):
                    issues.append(
                        ValidationIssue(
                            trace_name=trace_name,
                            error_code="row_width_mismatch",
                            message=(
                                f"{trace_name} line {line_number} has {len(row)} field(s); "
                                f"expected {len(header)}"
                            ),
                        )
                    )
                    break
                rows.append((line_number, tuple(row)))
    except FileNotFoundError:
        issues.append(
            ValidationIssue(
                trace_name=trace_name,
                error_code="file_not_found",
                message=f"{trace_name} does not exist: {path}",
            )
        )
    except UnicodeDecodeError:
        issues.append(
            ValidationIssue(
                trace_name=trace_name,
                error_code="invalid_encoding",
                message=f"{trace_name} must be valid UTF-8 text",
            )
        )
    except csv.Error as exc:
        issues.append(
            ValidationIssue(
                trace_name=trace_name,
                error_code="csv_parse_error",
                message=f"{trace_name} could not be parsed as CSV: {exc}",
            )
        )

    if header and not rows and not issues:
        issues.append(
            ValidationIssue(
                trace_name=trace_name,
                error_code="empty_trace",
                message=f"{trace_name} must contain at least one data row",
            )
        )

    return CsvReadResult(header=header, rows=tuple(rows), issues=tuple(issues))


def _base_primary_inspection(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "header": [],
        "row_count": 0,
        "usable": False,
        "used_for_scheduler_capacity": True,
        "usage_policy": "primary_only",
        "schema_detected": None,
        "time_unit_hint": None,
        "normalized_row_count": 0,
        "median_positive_delta_ms": None,
        "monotonicity": {
            "checked_column": None,
            "is_non_decreasing": None,
            "negative_delta_count": None,
            "zero_delta_count": None,
            "positive_delta_count": None,
        },
        "normalization": {
            "output_relative_path": f"derived/{NORMALIZED_TRACE_FILENAME}",
            "output_columns": list(NORMALIZED_TRACE_HEADERS),
            "last_row_duration_policy": "median_positive_forward_delta_ms",
        },
        "errors": [],
    }


def _base_secondary_inspection(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "header": [],
        "row_count": 0,
        "usable": False,
        "used_for_scheduler_capacity": False,
        "usage_policy": "structural_only",
        "time_unit_hints": [],
        "monotonicity": {
            "checked_column": None,
            "is_non_decreasing": None,
            "negative_delta_count": None,
        },
        "errors": [],
    }


def _select_time_column(header: tuple[str, ...]) -> str | None:
    preferred = (
        "time_slot_sched_ns",
        "time_decode_start_actual_ns",
        "time_ms",
        "timestamp_ns",
        "timestamp_us",
        "timestamp_ms",
    )
    for name in preferred:
        if name in header:
            return name
    for name in header:
        lowered = name.lower()
        if "time" in lowered or "timestamp" in lowered:
            return name
    return None


def _time_unit_hints(header: tuple[str, ...]) -> list[str]:
    hints: set[str] = set()
    for name in header:
        lowered = name.lower()
        if "time" not in lowered and "timestamp" not in lowered:
            continue
        if lowered.endswith("_ns"):
            hints.add("ns")
        elif lowered.endswith("_us"):
            hints.add("us")
        elif lowered.endswith("_ms"):
            hints.add("ms")
        elif lowered.endswith("_s"):
            hints.add("s")
    return sorted(hints)


def _coerce_float(raw_value: str, *, column: str, line_number: int) -> float | None:
    del column, line_number
    try:
        value = float(raw_value)
    except ValueError:
        return None
    if not math.isfinite(value):
        return None
    return value


def _write_normalized_trace(
    path: Path,
    rows: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(NORMALIZED_TRACE_HEADERS))
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "time_ms": _format_number(float(row["time_ms"])),
                    "sm_utilization": _format_number(float(row["sm_utilization"])),
                    "slot_duration_ms": _format_number(float(row["slot_duration_ms"])),
                    "source_schema": str(row["source_schema"]),
                }
            )


def _write_validation_errors(
    path: Path,
    issues: tuple[ValidationIssue, ...],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(VALIDATION_ERROR_HEADERS))
        writer.writeheader()
        for issue in issues:
            writer.writerow(
                {
                    "trace_name": issue.trace_name,
                    "error_code": issue.error_code,
                    "message": issue.message,
                }
            )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _remove_if_exists(path: Path) -> None:
    if path.exists():
        path.unlink()


def _format_number(value: float) -> str:
    return f"{value:.15g}"


__all__ = [
    "NORMALIZED_TRACE_FILENAME",
    "NORMALIZED_TRACE_HEADERS",
    "PRIMARY_SCHEMA_A_HEADERS",
    "PRIMARY_SCHEMA_B_HEADERS",
    "SOURCE_SCHEMA_A",
    "SOURCE_SCHEMA_B",
    "TRACE_INSPECTION_FILENAME",
    "TraceContractResult",
    "VALIDATION_ERRORS_FILENAME",
    "ValidationIssue",
    "inspect_secondary_trace",
    "normalize_primary_trace",
    "validate_trace_contract",
]
