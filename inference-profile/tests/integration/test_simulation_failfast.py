from __future__ import annotations

import csv
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest

from inference_profile import trace_contract

PROJECT_ROOT = Path(__file__).resolve().parents[2]


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


def _write_failfast_inputs(run_root: Path) -> None:
    derived_root = run_root / "derived"
    _write_csv(
        derived_root / "model_constants.csv",
        fieldnames=[
            "model_id",
            "num_hidden_layers",
            "hidden_size",
            "num_attention_heads",
            "ffn_dim",
            "layer_index",
            "layer_weight_bytes",
            "total_weight_bytes_fp16",
            "vram_ceiling_bytes",
        ],
        rows=[
            {
                "model_id": "facebook/opt-125m",
                "num_hidden_layers": 1,
                "hidden_size": 10,
                "num_attention_heads": 1,
                "ffn_dim": 40,
                "layer_index": 0,
                "layer_weight_bytes": 400,
                "total_weight_bytes_fp16": 400,
                "vram_ceiling_bytes": 450,
            }
        ],
    )
    _write_csv(
        derived_root / "prefill_summary.csv",
        fieldnames=[
            "model_id",
            "chunk_tokens",
            "prefill_max_gemm_us",
            "prefill_workspace_bytes",
            "prefill_parked_activation_bytes",
        ],
        rows=[
            {
                "model_id": "facebook/opt-125m",
                "chunk_tokens": 2048,
                "prefill_max_gemm_us": 500.0,
                "prefill_workspace_bytes": 80,
                "prefill_parked_activation_bytes": 100,
            }
        ],
    )
    _write_csv(
        derived_root / "decode_summary.csv",
        fieldnames=[
            "model_id",
            "sequence_length",
            "block_size",
            "decode_max_gemv_us",
            "attention_fetch_compute_us",
            "reduction_overhead_us",
            "decode_workspace_bytes",
            "decode_parked_activation_bytes",
        ],
        rows=[
            {
                "model_id": "facebook/opt-125m",
                "sequence_length": 4096,
                "block_size": 2048,
                "decode_max_gemv_us": 250.0,
                "attention_fetch_compute_us": 500.0,
                "reduction_overhead_us": 250.0,
                "decode_workspace_bytes": 50,
                "decode_parked_activation_bytes": 40,
            }
        ],
    )
    _write_csv(
        derived_root / "pcie_summary.csv",
        fieldnames=["model_id", "block_size", "exposed_transfer_us"],
        rows=[
            {
                "model_id": "facebook/opt-125m",
                "block_size": 2048,
                "exposed_transfer_us": 250.0,
            }
        ],
    )
    _write_csv(
        derived_root / trace_contract.NORMALIZED_TRACE_FILENAME,
        fieldnames=list(trace_contract.NORMALIZED_TRACE_HEADERS),
        rows=[
            {
                "time_ms": 0.0,
                "sm_utilization": 100.0,
                "slot_duration_ms": 1.0,
                "source_schema": trace_contract.SOURCE_SCHEMA_A,
            },
            {
                "time_ms": 1.0,
                "sm_utilization": 0.0,
                "slot_duration_ms": 2.0,
                "source_schema": trace_contract.SOURCE_SCHEMA_A,
            },
            {
                "time_ms": 3.0,
                "sm_utilization": 100.0,
                "slot_duration_ms": 1.0,
                "source_schema": trace_contract.SOURCE_SCHEMA_A,
            },
            {
                "time_ms": 4.0,
                "sm_utilization": 0.0,
                "slot_duration_ms": 4.0,
                "source_schema": trace_contract.SOURCE_SCHEMA_A,
            },
        ],
    )


def test_simulate_cli_emits_typed_parking_failure_row(tmp_path: Path) -> None:
    run_root = tmp_path / "simulate-failfast"
    _write_failfast_inputs(run_root)

    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "inference_profile.cli",
            "simulate",
            "--run-root",
            str(run_root),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stderr == ""

    results_df = pd.read_csv(
        run_root / "derived" / "ran_inference_profiling_results.csv"
    )
    assert len(results_df) == 1
    row = results_df.iloc[0]
    assert row["status"] == "parked_activation_oom"
    assert row["decode_runway_bytes"] == 0
    assert pd.isna(row["ttft_ms"])
    assert pd.isna(row["tpot_ms_vram"])
    assert pd.isna(row["tpot_ms_pcie_async"])

    timeline_df = pd.read_csv(run_root / "derived" / "schedule_timeline.csv")
    assert len(timeline_df) == 4
    assert set(timeline_df["phase"]) == {"prefill"}
    assert set(timeline_df["mode"]) == {"prefill"}
    assert timeline_df.iloc[-1]["end_time_ms"] == pytest.approx(3.0)
