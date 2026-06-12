from __future__ import annotations

import csv
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest

from inference_profile import experiments, simulator, trace_contract

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


def _write_simulate_cli_inputs(run_root: Path, *, revised: bool = False) -> None:
    derived_root = run_root / "derived"
    partitions = [8, 16, 24, 32] if revised else [None]
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
                "vram_ceiling_bytes": 1_000,
            },
            {
                "model_id": "facebook/opt-350m",
                "num_hidden_layers": 1,
                "hidden_size": 10,
                "num_attention_heads": 1,
                "ffn_dim": 40,
                "layer_index": 0,
                "layer_weight_bytes": 400,
                "total_weight_bytes_fp16": 400,
                "vram_ceiling_bytes": 450,
            },
        ],
    )
    _write_csv(
        derived_root / "prefill_summary.csv",
        fieldnames=[
            "model_id",
            "chunk_tokens",
            *(["sm_ai_partition"] if revised else []),
            "prefill_max_gemm_us",
            "prefill_workspace_bytes",
            "prefill_parked_activation_bytes",
        ],
        rows=[
            {
                "model_id": model_id,
                "chunk_tokens": 2048,
                **({"sm_ai_partition": partition} if revised else {}),
                "prefill_max_gemm_us": 500.0,
                "prefill_workspace_bytes": 80,
                "prefill_parked_activation_bytes": 100,
            }
            for model_id in ("facebook/opt-125m", "facebook/opt-350m")
            for partition in partitions
        ],
    )
    _write_csv(
        derived_root / "decode_summary.csv",
        fieldnames=[
            "model_id",
            "sequence_length",
            "block_size",
            *(["sm_ai_partition", "decode_mode"] if revised else []),
            "decode_max_gemv_us",
            "attention_fetch_compute_us",
            "reduction_overhead_us",
            "decode_workspace_bytes",
            "decode_parked_activation_bytes",
        ],
        rows=[
            {
                "model_id": model_id,
                "sequence_length": 4096,
                "block_size": 2048,
                **(
                    {"sm_ai_partition": partition, "decode_mode": mode}
                    if revised
                    else {}
                ),
                "decode_max_gemv_us": 250.0,
                "attention_fetch_compute_us": 500.0,
                "reduction_overhead_us": 250.0,
                "decode_workspace_bytes": 50,
                "decode_parked_activation_bytes": 40,
            }
            for model_id in ("facebook/opt-125m", "facebook/opt-350m")
            for partition in partitions
            for mode in (("vram", "pcie_async") if revised else (None,))
        ],
    )
    _write_csv(
        derived_root / "pcie_summary.csv",
        fieldnames=[
            "model_id",
            "block_size",
            *(["sm_ai_partition"] if revised else []),
            "exposed_transfer_us",
            *(
                [
                    "transfer_only_us",
                    "overlap_total_us",
                    "dummy_compute_us",
                    "effective_gbps",
                    "overlap_status",
                ]
                if revised
                else []
            ),
        ],
        rows=[
            {
                "model_id": model_id,
                "block_size": 2048,
                **({"sm_ai_partition": partition} if revised else {}),
                "exposed_transfer_us": 250.0,
                **(
                    {
                        "transfer_only_us": 300.0,
                        "overlap_total_us": 260.0,
                        "dummy_compute_us": 120.0,
                        "effective_gbps": 12.5,
                        "overlap_status": "supported",
                    }
                    if revised
                    else {}
                ),
            }
            for model_id in ("facebook/opt-125m", "facebook/opt-350m")
            for partition in partitions
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
            {
                "time_ms": 8.0,
                "sm_utilization": 100.0,
                "slot_duration_ms": 0.5,
                "source_schema": trace_contract.SOURCE_SCHEMA_A,
            },
            {
                "time_ms": 8.5,
                "sm_utilization": 0.0,
                "slot_duration_ms": 4.0,
                "source_schema": trace_contract.SOURCE_SCHEMA_A,
            },
        ],
    )


def test_simulate_cli_writes_canonical_results_and_keeps_typed_failure_rows(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "simulate-cli"
    _write_simulate_cli_inputs(run_root)

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
    assert result.stdout == ""
    assert result.stderr == ""

    derived_root = run_root / "derived"
    results_path = derived_root / simulator.SIMULATION_RESULTS_FILENAME
    timeline_path = derived_root / simulator.SCHEDULE_TIMELINE_FILENAME
    assert results_path.exists()
    assert timeline_path.exists()

    results_df = pd.read_csv(results_path)
    timeline_df = pd.read_csv(timeline_path)

    assert list(results_df.columns) == list(simulator.SIMULATION_RESULTS_COLUMNS)
    assert list(timeline_df.columns) == list(simulator.SCHEDULE_TIMELINE_COLUMNS)
    assert len(results_df) == 2

    success_row = results_df[results_df["model_id"] == "facebook/opt-125m"].iloc[0]
    failure_row = results_df[results_df["model_id"] == "facebook/opt-350m"].iloc[0]

    assert success_row["status"] == "success"
    assert success_row["survival_vram_bytes"] == 420
    assert success_row["decode_runway_bytes"] == 0
    assert success_row["decode_runway_tokens"] == 0
    # ttft_ms is latency: prefill completion (8.0) - first prefill start (1.0) = 7.0
    assert success_row["ttft_ms"] == pytest.approx(7.0)
    assert success_row["tpot_ms_vram"] == pytest.approx(2.75)
    assert success_row["tpot_ms_pcie_async"] == pytest.approx(3.25)

    assert failure_row["status"] == "parked_activation_oom"
    assert failure_row["survival_vram_bytes"] == -130
    assert failure_row["decode_runway_bytes"] == 0
    assert failure_row["decode_runway_tokens"] == 0
    assert pd.isna(failure_row["ttft_ms"])
    assert pd.isna(failure_row["tpot_ms_vram"])
    assert pd.isna(failure_row["tpot_ms_pcie_async"])

    success_timeline = timeline_df[timeline_df["model_id"] == "facebook/opt-125m"]
    failure_timeline = timeline_df[timeline_df["model_id"] == "facebook/opt-350m"]

    assert len(success_timeline) == 30
    assert len(failure_timeline) == 4
    assert set(success_timeline["phase"]) == {"prefill", "decode"}
    assert set(failure_timeline["phase"]) == {"prefill"}


def test_simulate_cli_infers_revised_experiment_type_from_manifest(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "revised-simulate-cli"
    _write_simulate_cli_inputs(run_root, revised=True)

    manifest_path = run_root / "run_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": experiments.RAN_DGXSPARK_V1_SCHEMA_VERSION,
                "experiment_type": experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

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

    assert result.returncode == 0, result.stderr
    rows = list(
        csv.DictReader(
            (run_root / "derived" / simulator.SIMULATION_RESULTS_FILENAME).open(
                encoding="utf-8"
            )
        )
    )
    assert rows
    assert rows[0]["schema_version"] == experiments.RAN_DGXSPARK_V1_SCHEMA_VERSION
    assert rows[0]["experiment_type"] == experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE
    assert rows[0]["scheduler"] == experiments.RAN_DGXSPARK_V1_SCHEDULER
