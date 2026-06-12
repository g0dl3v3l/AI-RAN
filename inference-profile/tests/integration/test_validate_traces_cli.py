from __future__ import annotations

import csv
import json
from pathlib import Path
import subprocess
import sys

from inference_profile import trace_contract

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = PROJECT_ROOT / "tests" / "fixtures"


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_validate_traces_cli_writes_normalized_csv_for_valid_fixture(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "validate-ok"

    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "inference_profile.cli",
            "validate-traces",
            "--ldpc-trace",
            str(FIXTURE_ROOT / "ldpc_trace_valid.csv"),
            "--ran-ctrl-trace",
            str(FIXTURE_ROOT / "ran_ctrl_trace_valid.csv"),
            "--output-root",
            str(output_root),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stderr == ""

    normalized_trace = (
        output_root / "derived" / trace_contract.NORMALIZED_TRACE_FILENAME
    )
    inspection_path = output_root / "raw" / trace_contract.TRACE_INSPECTION_FILENAME
    assert normalized_trace.exists()
    assert inspection_path.exists()
    assert not (
        output_root / "raw" / trace_contract.VALIDATION_ERRORS_FILENAME
    ).exists()

    normalized_rows = _read_csv_rows(normalized_trace)
    assert [row["source_schema"] for row in normalized_rows] == [
        trace_contract.SOURCE_SCHEMA_B,
        trace_contract.SOURCE_SCHEMA_B,
        trace_contract.SOURCE_SCHEMA_B,
    ]

    inspection = json.loads(inspection_path.read_text(encoding="utf-8"))
    assert inspection["primary_trace"]["usable"] is True
    assert inspection["secondary_trace"]["usable"] is True


def test_validate_traces_cli_accepts_schema_b_with_extra_primary_columns(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "validate-rich-primary"
    ldpc_trace = tmp_path / "ldpc_trace_rich.csv"
    ldpc_trace.write_text(
        (
            "frame,slot,time_slot_sched_ns,time_decode_start_actual_ns,sm_count,target_sm\n"
            "570,19,1000000,1200000,0,8\n"
            "572,18,2500000,2700000,3,8\n"
            "573,8,3500000,3600000,0,8\n"
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "inference_profile.cli",
            "validate-traces",
            "--ldpc-trace",
            str(ldpc_trace),
            "--ran-ctrl-trace",
            str(FIXTURE_ROOT / "ran_ctrl_trace_valid.csv"),
            "--output-root",
            str(output_root),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    normalized_trace = (
        output_root / "derived" / trace_contract.NORMALIZED_TRACE_FILENAME
    )
    inspection_path = output_root / "raw" / trace_contract.TRACE_INSPECTION_FILENAME
    assert normalized_trace.exists()
    inspection = json.loads(inspection_path.read_text(encoding="utf-8"))
    assert (
        inspection["primary_trace"]["schema_detected"] == trace_contract.SOURCE_SCHEMA_B
    )
    assert inspection["primary_trace"]["usable"] is True


def test_validate_traces_cli_fails_closed_for_invalid_primary_fixture(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "validate-bad"

    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "inference_profile.cli",
            "validate-traces",
            "--ldpc-trace",
            str(FIXTURE_ROOT / "ldpc_trace_missing_column.csv"),
            "--ran-ctrl-trace",
            str(FIXTURE_ROOT / "ran_ctrl_trace_valid.csv"),
            "--output-root",
            str(output_root),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert result.stderr.startswith(
        "Error: Primary ldpc_trace.csv must include one of the supported column pairs"
    )
    assert "Traceback" not in result.stderr

    assert (output_root / "raw" / trace_contract.TRACE_INSPECTION_FILENAME).exists()
    assert (output_root / "raw" / trace_contract.VALIDATION_ERRORS_FILENAME).exists()
    assert not (
        output_root / "derived" / trace_contract.NORMALIZED_TRACE_FILENAME
    ).exists()
