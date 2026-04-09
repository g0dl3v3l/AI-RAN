from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class ProfileReductionResult:
    """Result of reducing raw profiling events into canonical summaries."""
    model_constants_path: Path
    prefill_summary_path: Path
    decode_summary_path: Path
    pcie_summary_path: Path
    prefill_row_count: int
    decode_row_count: int
    pcie_row_count: int


def reduce_profile_events(
    *,
    run_root: str | Path,
) -> ProfileReductionResult:
    """
    Reduce raw profiling events into canonical summary files.
    
    Processes:
    - raw/prefill_events.csv → derived/prefill_summary.csv
    - raw/decode_events.csv → derived/decode_summary.csv
    - raw/pcie_events.csv → derived/pcie_summary.csv
    
    Returns: Path objects for the four summary files and row counts.
    """
    run_root = Path(run_root)
    raw_root = run_root / "raw"
    derived_root = run_root / "derived"
    derived_root.mkdir(parents=True, exist_ok=True)

    # Load raw events
    prefill_df = _load_raw_csv(raw_root / "prefill_events.csv")
    decode_df = _load_raw_csv(raw_root / "decode_events.csv")
    pcie_df = _load_raw_csv(raw_root / "pcie_events.csv")

    # Reduce to summaries
    model_constants = _compute_model_constants(prefill_df, decode_df, pcie_df)
    prefill_summary = _reduce_prefill_events(prefill_df)
    decode_summary = _reduce_decode_events(decode_df)
    pcie_summary = _reduce_pcie_events(pcie_df)

    # Write summaries
    model_constants_path = derived_root / "model_constants.csv"
    prefill_summary_path = derived_root / "prefill_summary.csv"
    decode_summary_path = derived_root / "decode_summary.csv"
    pcie_summary_path = derived_root / "pcie_summary.csv"

    model_constants.to_csv(model_constants_path, index=False)
    prefill_summary.to_csv(prefill_summary_path, index=False)
    decode_summary.to_csv(decode_summary_path, index=False)
    pcie_summary.to_csv(pcie_summary_path, index=False)

    return ProfileReductionResult(
        model_constants_path=model_constants_path,
        prefill_summary_path=prefill_summary_path,
        decode_summary_path=decode_summary_path,
        pcie_summary_path=pcie_summary_path,
        prefill_row_count=len(prefill_summary),
        decode_row_count=len(decode_summary),
        pcie_row_count=len(pcie_summary),
    )


def _load_raw_csv(csv_path: Path) -> pd.DataFrame:
    """Load raw CSV if it exists, otherwise return empty DataFrame."""
    if not csv_path.exists():
        return pd.DataFrame()
    return pd.read_csv(csv_path)


def _compute_model_constants(
    prefill_df: pd.DataFrame,
    decode_df: pd.DataFrame,
    pcie_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Extract model-level constants that are common across all profiling points.
    """
    model_ids = set()
    if not prefill_df.empty:
        model_ids.update(prefill_df["model_id"].unique())
    if not decode_df.empty:
        model_ids.update(decode_df["model_id"].unique())
    if not pcie_df.empty:
        model_ids.update(pcie_df["model_id"].unique())

    rows = [{"model_id": mid} for mid in sorted(model_ids)]
    return pd.DataFrame(rows)


def _reduce_prefill_events(prefill_df: pd.DataFrame) -> pd.DataFrame:
    """
    Reduce prefill raw events to canonical summary.
    
    Columns: model_id, chunk_tokens, prefill_max_gemm_us, prefill_workspace_bytes, prefill_parked_activation_bytes
    """
    if prefill_df.empty:
        return pd.DataFrame(
            columns=[
                "model_id",
                "chunk_tokens",
                "prefill_max_gemm_us",
                "prefill_workspace_bytes",
                "prefill_parked_activation_bytes",
            ]
        )

    # Group by model and chunk_tokens
    grouped = prefill_df.groupby(["model_id", "chunk_tokens"], as_index=False).agg({
        "duration_us": "max",
        "dynamic_workspace_bytes": "max",
        "output_bytes": "max",
    })

    grouped.columns = [
        "model_id",
        "chunk_tokens",
        "prefill_max_gemm_us",
        "prefill_workspace_bytes",
        "prefill_parked_activation_bytes",
    ]

    return grouped[
        [
            "model_id",
            "chunk_tokens",
            "prefill_max_gemm_us",
            "prefill_workspace_bytes",
            "prefill_parked_activation_bytes",
        ]
    ].sort_values(["model_id", "chunk_tokens"]).reset_index(drop=True)


def _reduce_decode_events(decode_df: pd.DataFrame) -> pd.DataFrame:
    """
    Reduce decode raw events to canonical summary.
    
    Columns: model_id, sequence_length, block_size, decode_max_gemv_us, 
             attention_fetch_compute_us, reduction_overhead_us, 
             decode_workspace_bytes, decode_parked_activation_bytes
    """
    if decode_df.empty:
        return pd.DataFrame(
            columns=[
                "model_id",
                "sequence_length",
                "block_size",
                "decode_max_gemv_us",
                "attention_fetch_compute_us",
                "reduction_overhead_us",
                "decode_workspace_bytes",
                "decode_parked_activation_bytes",
            ]
        )

    summary_rows = []

    # Group by model, sequence_length, block_size
    for (model_id, seq_len, block_size), group in decode_df.groupby(
        ["model_id", "sequence_length", "block_size"]
    ):
        # Extract gemv (linear ops) max
        gemv_rows = group[group["op_type"] == "gemv"]
        max_gemv_us = float(gemv_rows["duration_us"].max()) if not gemv_rows.empty else 0.0

        # Extract attention_fetch_compute
        attn_rows = group[group["op_type"] == "attention_fetch_compute"]
        attn_compute_us = float(attn_rows["duration_us"].mean()) if not attn_rows.empty else 0.0

        # Extract reduction_overhead
        reduce_rows = group[group["op_type"] == "reduction_overhead"]
        reduce_overhead_us = float(reduce_rows["duration_us"].mean()) if not reduce_rows.empty else 0.0

        # Max workspace and output across all op types
        workspace_bytes = int(group["dynamic_workspace_bytes"].max())
        output_bytes = int(group["output_bytes"].max())

        summary_rows.append({
            "model_id": model_id,
            "sequence_length": int(seq_len),
            "block_size": int(block_size),
            "decode_max_gemv_us": max_gemv_us,
            "attention_fetch_compute_us": attn_compute_us,
            "reduction_overhead_us": reduce_overhead_us,
            "decode_workspace_bytes": workspace_bytes,
            "decode_parked_activation_bytes": output_bytes,
        })

    df = pd.DataFrame(summary_rows)
    return df.sort_values(
        ["model_id", "sequence_length", "block_size"]
    ).reset_index(drop=True)


def _reduce_pcie_events(pcie_df: pd.DataFrame) -> pd.DataFrame:
    """
    Reduce PCIe raw events to canonical summary.
    
    Columns: model_id, block_size, kv_block_bytes, transfer_only_us, 
             overlap_total_us, dummy_compute_us, exposed_transfer_us, effective_gbps
    """
    if pcie_df.empty:
        return pd.DataFrame(
            columns=[
                "model_id",
                "block_size",
                "kv_block_bytes",
                "transfer_only_us",
                "overlap_total_us",
                "dummy_compute_us",
                "exposed_transfer_us",
                "effective_gbps",
            ]
        )

    # Group by model and block_size
    grouped = pcie_df.groupby(["model_id", "block_size"], as_index=False).agg({
        "kv_block_bytes": "first",
        "transfer_only_us": "mean",
        "overlap_total_us": "mean",
        "dummy_compute_us": "mean",
        "exposed_transfer_us": "mean",
    })

    # Calculate effective_gbps = (kv_block_bytes / 1e9) / (transfer_only_us / 1e6)
    # = (kv_block_bytes * 1e6) / (transfer_only_us * 1e9)
    # = (kv_block_bytes / transfer_only_us) / 1000.0
    grouped["effective_gbps"] = grouped.apply(
        lambda row: (row["kv_block_bytes"] / row["transfer_only_us"]) / 1000.0
        if row["transfer_only_us"] > 0
        else 0.0,
        axis=1,
    )

    return grouped[
        [
            "model_id",
            "block_size",
            "kv_block_bytes",
            "transfer_only_us",
            "overlap_total_us",
            "dummy_compute_us",
            "exposed_transfer_us",
            "effective_gbps",
        ]
    ].sort_values(["model_id", "block_size"]).reset_index(drop=True)


__all__ = [
    "ProfileReductionResult",
    "reduce_profile_events",
]
