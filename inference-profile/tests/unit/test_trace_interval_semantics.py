from __future__ import annotations

import csv
from pathlib import Path

import pytest

from inference_profile import simulator, trace_contract

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures"


def _write_csv(
    path: Path,
    *,
    fieldnames: list[str],
    rows: list[dict[str, object]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_load_normalized_trace_intervals_treats_rows_as_half_open_intervals(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "half-open-trace"
    _write_csv(
        run_root / "derived" / trace_contract.NORMALIZED_TRACE_FILENAME,
        fieldnames=list(trace_contract.NORMALIZED_TRACE_HEADERS),
        rows=[
            {
                "time_ms": 10.0,
                "sm_utilization": 0.0,
                "slot_duration_ms": 5.0,
                "source_schema": trace_contract.SOURCE_SCHEMA_A,
            },
            {
                "time_ms": 15.0,
                "sm_utilization": 100.0,
                "slot_duration_ms": 5.0,
                "source_schema": trace_contract.SOURCE_SCHEMA_A,
            },
        ],
    )

    first_interval, second_interval = simulator.load_normalized_trace_intervals(
        run_root=run_root
    )

    assert first_interval.start_time_ms == 10.0
    assert first_interval.end_time_ms == 15.0
    assert second_interval.start_time_ms == 15.0
    assert second_interval.end_time_ms == 20.0
    assert (first_interval.start_time_ms <= 15.0 < first_interval.end_time_ms) is False
    assert (second_interval.start_time_ms <= 15.0 < second_interval.end_time_ms) is True


def test_load_normalized_trace_intervals_keeps_last_row_median_positive_delta(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "validated-trace"

    result = trace_contract.validate_trace_contract(
        ldpc_trace=FIXTURE_ROOT / "ldpc_trace_valid.csv",
        ran_ctrl_trace=FIXTURE_ROOT / "ran_ctrl_trace_valid.csv",
        output_root=output_root,
    )

    assert result.success is True
    intervals = simulator.load_normalized_trace_intervals(run_root=output_root)

    assert [interval.slot_duration_ms for interval in intervals] == pytest.approx(
        [1.5, 1.0, 1.25]
    )
    assert intervals[-1].start_time_ms == pytest.approx(3.5)
    assert intervals[-1].end_time_ms == pytest.approx(4.75)
    assert intervals[-1].source_schema == trace_contract.SOURCE_SCHEMA_B
