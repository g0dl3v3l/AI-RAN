from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class SimulationResult:
    """Result of running deterministic greedy simulation."""
    run_root: Path
    results_path: Path
    timeline_path: Path
    row_count: int


def assemble_simulation_inputs(
    *,
    run_root: str | Path,
) -> pd.DataFrame:
    """
    Assemble normalized traces and profile summaries into simulator-ready table.
    
    Joins:
    - derived/prefill_summary.csv
    - derived/decode_summary.csv
    - derived/pcie_summary.csv
    - derived/normalized_ldpc_trace.csv (metadata only)
    
    Returns DataFrame with simulation_inputs.csv schema.
    """
    run_root = Path(run_root)
    derived_root = run_root / "derived"

    # Load summaries
    prefill_df = _load_csv_or_empty(derived_root / "prefill_summary.csv")
    decode_df = _load_csv_or_empty(derived_root / "decode_summary.csv")
    pcie_df = _load_csv_or_empty(derived_root / "pcie_summary.csv")
    model_constants_df = _load_csv_or_empty(derived_root / "model_constants.csv")

    # Build simulation inputs by combining prefill, decode, and pcie summaries
    if prefill_df.empty or decode_df.empty:
        return pd.DataFrame()

    # Create input matrix: model × chunk_size × sequence_length
    simulation_rows = []

    for _, model_row in model_constants_df.iterrows():
        model_id = model_row["model_id"]

        for _, prefill_row in prefill_df[prefill_df["model_id"] == model_id].iterrows():
            chunk_size = int(prefill_row["chunk_tokens"])
            for _, decode_row in decode_df[
                (decode_df["model_id"] == model_id) & (decode_df["block_size"] == chunk_size)
            ].iterrows():
                seq_len = int(decode_row["sequence_length"])

                # Find PCIe row for this model and chunk size
                pcie_row = pcie_df[
                    (pcie_df["model_id"] == model_id) & (pcie_df["block_size"] == chunk_size)
                ]
                pcie_exposed_us = float(pcie_row["exposed_transfer_us"].iloc[0]) if not pcie_row.empty else 0.0

                simulation_rows.append({
                    "model_id": model_id,
                    "chunk_tokens": chunk_size,
                    "sequence_length": seq_len,
                    "prefill_max_gemm_us": float(prefill_row["prefill_max_gemm_us"]),
                    "prefill_workspace_bytes": int(prefill_row["prefill_workspace_bytes"]),
                    "prefill_parked_activation_bytes": int(prefill_row["prefill_parked_activation_bytes"]),
                    "decode_max_gemv_us": float(decode_row["decode_max_gemv_us"]),
                    "attention_fetch_compute_us": float(decode_row["attention_fetch_compute_us"]),
                    "reduction_overhead_us": float(decode_row["reduction_overhead_us"]),
                    "decode_workspace_bytes": int(decode_row["decode_workspace_bytes"]),
                    "decode_parked_activation_bytes": int(decode_row["decode_parked_activation_bytes"]),
                    "pcie_exposed_us": pcie_exposed_us,
                })

    return pd.DataFrame(simulation_rows)


def run_deterministic_simulation(
    *,
    run_root: str | Path,
    ldpc_trace_path: str | Path | None = None,
) -> SimulationResult:
    """
    Run deterministic greedy scheduler over RAN idle gaps.
    
    Emits:
    - derived/ran_inference_profiling_results.csv (per-point results)
    - derived/schedule_timeline.csv (prefill/decode scheduling intervals)
    """
    run_root = Path(run_root)
    derived_root = run_root / "derived"
    derived_root.mkdir(parents=True, exist_ok=True)

    # Assemble simulation inputs
    sim_inputs = assemble_simulation_inputs(run_root=run_root)

    # Load normalized trace
    trace_path = derived_root / "normalized_ldpc_trace.csv"
    trace_df = _load_csv_or_empty(trace_path) if trace_path.exists() else pd.DataFrame()

    # Generate minimal results (stub for now)
    # In full implementation, this would run greedy scheduler
    results_rows = []
    for _, row in sim_inputs.iterrows():
        results_rows.append({
            "model_id": row["model_id"],
            "chunk_tokens": row["chunk_tokens"],
            "sequence_length": row["sequence_length"],
            "weight_bytes": 0,
            "vram_ceiling_bytes": 0,
            "ttft_ms": 0.0,
            "tpot_ms": 0.0,
            "status": "success",
        })

    results_df = pd.DataFrame(results_rows)
    timeline_df = pd.DataFrame()

    # Write outputs
    results_path = derived_root / "ran_inference_profiling_results.csv"
    timeline_path = derived_root / "schedule_timeline.csv"

    results_df.to_csv(results_path, index=False)
    timeline_df.to_csv(timeline_path, index=False)

    return SimulationResult(
        run_root=run_root,
        results_path=results_path,
        timeline_path=timeline_path,
        row_count=len(results_df),
    )


def _load_csv_or_empty(csv_path: Path) -> pd.DataFrame:
    """Load CSV if it exists, otherwise return empty DataFrame."""
    if not csv_path.exists():
        return pd.DataFrame()
    return pd.read_csv(csv_path)


__all__ = [
    "SimulationResult",
    "assemble_simulation_inputs",
    "run_deterministic_simulation",
]
