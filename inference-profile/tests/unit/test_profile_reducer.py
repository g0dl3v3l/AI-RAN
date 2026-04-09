"""Unit tests for profile reduction logic."""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from inference_profile import profile_reducer


def test_reduce_prefill_events_computes_exact_maxima():
    """Verify prefill reduction computes exact maxima for all metrics."""
    # Create sample prefill events
    raw_events = pd.DataFrame({
        "model_id": ["facebook/opt-125m"] * 6,
        "chunk_tokens": [64] * 6,
        "op_name": ["q_proj", "k_proj", "v_proj", "out_proj", "fc1", "fc2"],
        "duration_us": [100.0, 120.0, 110.0, 105.0, 200.0, 150.0],
        "dynamic_workspace_bytes": [1024] * 6,
        "output_bytes": [512] * 6,
    })
    
    reduced = profile_reducer._reduce_prefill_events(raw_events)
    
    # Should have one row (grouped by model_id, chunk_tokens)
    assert len(reduced) == 1
    assert reduced.iloc[0]["model_id"] == "facebook/opt-125m"
    assert reduced.iloc[0]["chunk_tokens"] == 64
    
    # Max gemm should be 200.0 (from fc1)
    assert reduced.iloc[0]["prefill_max_gemm_us"] == 200.0
    
    # Workspace max
    assert reduced.iloc[0]["prefill_workspace_bytes"] == 1024
    
    # Output bytes max
    assert reduced.iloc[0]["prefill_parked_activation_bytes"] == 512


def test_reduce_decode_events_separates_op_types():
    """Verify decode reduction correctly separates gemv, attention, and reduction."""
    raw_events = pd.DataFrame({
        "model_id": ["facebook/opt-125m"] * 4,
        "sequence_length": [1024] * 4,
        "block_size": [64] * 4,
        "op_type": ["gemv", "gemv", "attention_fetch_compute", "reduction_overhead"],
        "op_name": ["q_proj", "fc1", None, None],
        "duration_us": [100.0, 200.0, 50.0, 25.0],
        "dynamic_workspace_bytes": [1024] * 4,
        "output_bytes": [512] * 4,
    })
    
    reduced = profile_reducer._reduce_decode_events(raw_events)
    
    assert len(reduced) == 1
    assert reduced.iloc[0]["decode_max_gemv_us"] == 200.0  # Max of gemv ops
    assert reduced.iloc[0]["attention_fetch_compute_us"] == 50.0
    assert reduced.iloc[0]["reduction_overhead_us"] == 25.0


def test_reduce_pcie_events_calculates_effective_gbps():
    """Verify PCIe reduction calculates effective_gbps correctly."""
    raw_events = pd.DataFrame({
        "model_id": ["facebook/opt-125m"] * 2,
        "block_size": [64, 64],
        "kv_block_bytes": [2_097_152, 2_097_152],  # 2MB each
        "transfer_only_us": [1000.0, 1000.0],  # 1ms transfer
        "overlap_total_us": [1500.0, 1500.0],
        "dummy_compute_us": [600.0, 600.0],
        "exposed_transfer_us": [900.0, 900.0],
    })
    
    reduced = profile_reducer._reduce_pcie_events(raw_events)
    
    assert len(reduced) == 1
    
    # effective_gbps = (2_097_152 / 1000.0) / 1000.0 ≈ 2.097 GB/s
    expected_gbps = (2_097_152 / 1000.0) / 1000.0
    assert abs(reduced.iloc[0]["effective_gbps"] - expected_gbps) < 0.01


def test_reduce_empty_dataframes():
    """Verify reducer handles empty DataFrames gracefully."""
    empty_df = pd.DataFrame()
    
    prefill_result = profile_reducer._reduce_prefill_events(empty_df)
    assert len(prefill_result) == 0
    assert list(prefill_result.columns) == [
        "model_id",
        "chunk_tokens",
        "prefill_max_gemm_us",
        "prefill_workspace_bytes",
        "prefill_parked_activation_bytes",
    ]
    
    decode_result = profile_reducer._reduce_decode_events(empty_df)
    assert len(decode_result) == 0
    
    pcie_result = profile_reducer._reduce_pcie_events(empty_df)
    assert len(pcie_result) == 0


def test_reduce_profile_events_end_to_end():
    """Verify end-to-end reduction produces all four summary files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_root = Path(tmpdir)
        raw_root = run_root / "raw"
        raw_root.mkdir(parents=True)
        
        # Create minimal raw event files
        prefill_df = pd.DataFrame({
            "model_id": ["facebook/opt-125m"],
            "chunk_tokens": [64],
            "op_name": ["q_proj"],
            "duration_us": [100.0],
            "dynamic_workspace_bytes": [1024],
            "output_bytes": [512],
        })
        prefill_df.to_csv(raw_root / "prefill_events.csv", index=False)
        
        decode_df = pd.DataFrame({
            "model_id": ["facebook/opt-125m"],
            "sequence_length": [1024],
            "block_size": [64],
            "op_type": ["gemv"],
            "op_name": ["q_proj"],
            "duration_us": [100.0],
            "dynamic_workspace_bytes": [1024],
            "output_bytes": [512],
        })
        decode_df.to_csv(raw_root / "decode_events.csv", index=False)
        
        pcie_df = pd.DataFrame({
            "model_id": ["facebook/opt-125m"],
            "block_size": [64],
            "kv_block_bytes": [2_097_152],
            "transfer_only_us": [1000.0],
            "overlap_total_us": [1500.0],
            "dummy_compute_us": [600.0],
            "exposed_transfer_us": [900.0],
        })
        pcie_df.to_csv(raw_root / "pcie_events.csv", index=False)
        
        # Run reduction
        result = profile_reducer.reduce_profile_events(run_root=run_root)
        
        # Verify all four files exist
        assert result.model_constants_path.exists()
        assert result.prefill_summary_path.exists()
        assert result.decode_summary_path.exists()
        assert result.pcie_summary_path.exists()
        
        # Verify row counts
        assert result.prefill_row_count > 0
        assert result.decode_row_count > 0
        assert result.pcie_row_count > 0
