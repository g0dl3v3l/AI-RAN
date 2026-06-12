from __future__ import annotations

import csv
from pathlib import Path
import subprocess
import sys

from inference_profile import simulator, trace_contract

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


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_simulate_cli_writes_simulation_inputs_csv(tmp_path: Path) -> None:
    run_root = tmp_path / "simulate-cli"
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
                "num_hidden_layers": 12,
                "hidden_size": 768,
                "num_attention_heads": 12,
                "ffn_dim": 3072,
                "layer_index": 5,
                "layer_weight_bytes": 14_175_744,
                "total_weight_bytes_fp16": 250_478_592,
                "vram_ceiling_bytes": 19_200_000_000,
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
                "chunk_tokens": 64,
                "prefill_max_gemm_us": 20.0,
                "prefill_workspace_bytes": 40,
                "prefill_parked_activation_bytes": 512,
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
                "sequence_length": 1024,
                "block_size": 64,
                "decode_max_gemv_us": 5.0,
                "attention_fetch_compute_us": 7.0,
                "reduction_overhead_us": 2.0,
                "decode_workspace_bytes": 32,
                "decode_parked_activation_bytes": 64,
            }
        ],
    )
    _write_csv(
        derived_root / "pcie_summary.csv",
        fieldnames=["model_id", "block_size", "exposed_transfer_us"],
        rows=[
            {
                "model_id": "facebook/opt-125m",
                "block_size": 64,
                "exposed_transfer_us": 3.0,
            }
        ],
    )
    _write_csv(
        derived_root / trace_contract.NORMALIZED_TRACE_FILENAME,
        fieldnames=list(trace_contract.NORMALIZED_TRACE_HEADERS),
        rows=[
            {
                "time_ms": 1.0,
                "sm_utilization": 0.0,
                "slot_duration_ms": 1.5,
                "source_schema": trace_contract.SOURCE_SCHEMA_B,
            },
            {
                "time_ms": 2.5,
                "sm_utilization": 100.0,
                "slot_duration_ms": 1.0,
                "source_schema": trace_contract.SOURCE_SCHEMA_B,
            },
        ],
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

    assert result.returncode == 0
    assert result.stderr == ""
    assert (derived_root / "ran_inference_profiling_results.csv").exists()
    assert (derived_root / "schedule_timeline.csv").exists()
    assert _read_csv_rows(derived_root / simulator.SIMULATION_INPUTS_FILENAME) == [
        {
            "model_id": "facebook/opt-125m",
            "chunk_tokens": "64",
            "sequence_length": "1024",
            "num_hidden_layers": "12",
            "hidden_size": "768",
            "num_attention_heads": "12",
            "ffn_dim": "3072",
            "layer_index": "5",
            "layer_weight_bytes": "14175744",
            "total_weight_bytes_fp16": "250478592",
            "total_memory_bytes": "32000000000",
            "vram_ceiling_bytes": "19200000000",
            "kv_bytes_per_token_all_layers": "36864",
            "prefill_max_gemm_us": "20.0",
            "prefill_workspace_bytes": "40",
            "prefill_parked_activation_bytes": "512",
            "decode_max_gemv_us": "5.0",
            "attention_fetch_compute_us": "7.0",
            "reduction_overhead_us": "2.0",
            "decode_workspace_bytes": "32",
            "decode_parked_activation_bytes": "64",
            "pcie_exposed_us": "3.0",
        }
    ]
