from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from inference_profile import profile_reducer


def test_reduce_profile_events_excludes_failed_points_from_success_summaries(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "profile-run"
    raw_root = run_root / "raw"
    raw_root.mkdir(parents=True)

    model_id = "facebook/opt-125m"

    pd.DataFrame(
        [
            {
                "point_id": "prefill-success",
                "model_id": model_id,
                "chunk_tokens": 64,
                "op_name": "q_proj",
                "duration_us": 100.0,
                "dynamic_workspace_bytes": 32,
                "output_bytes": 1536,
            },
            {
                "point_id": "prefill-success",
                "model_id": model_id,
                "chunk_tokens": 64,
                "op_name": "fc1",
                "duration_us": 220.0,
                "dynamic_workspace_bytes": 96,
                "output_bytes": 6144,
            },
            {
                "point_id": "prefill-failed",
                "model_id": model_id,
                "chunk_tokens": 64,
                "op_name": "q_proj",
                "duration_us": 9000.0,
                "dynamic_workspace_bytes": 900000,
                "output_bytes": 1536000,
            },
            {
                "point_id": "prefill-failed",
                "model_id": model_id,
                "chunk_tokens": 64,
                "op_name": "fc1",
                "duration_us": 9999.0,
                "dynamic_workspace_bytes": 999999,
                "output_bytes": 6144000,
            },
        ]
    ).to_csv(raw_root / "prefill_events.csv", index=False)
    pd.DataFrame(
        [
            {"point_id": "prefill-success", "public_status": "success"},
            {"point_id": "prefill-failed", "public_status": "profile_failed"},
        ]
    ).to_csv(raw_root / "prefill_events_status.csv", index=False)

    pd.DataFrame(
        [
            {
                "point_id": "decode-success",
                "model_id": model_id,
                "sequence_length": 1024,
                "block_size": 64,
                "op_type": "gemv",
                "op_name": "q_proj",
                "duration_us": 100.0,
                "dynamic_workspace_bytes": 10,
                "output_bytes": 1536,
            },
            {
                "point_id": "decode-success",
                "model_id": model_id,
                "sequence_length": 1024,
                "block_size": 64,
                "op_type": "gemv",
                "op_name": "fc1",
                "duration_us": 250.0,
                "dynamic_workspace_bytes": 20,
                "output_bytes": 6144,
            },
            {
                "point_id": "decode-success",
                "model_id": model_id,
                "sequence_length": 1024,
                "block_size": 64,
                "op_type": "attention_fetch_compute",
                "op_name": None,
                "duration_us": 80.0,
                "dynamic_workspace_bytes": 500,
                "output_bytes": 4096,
            },
            {
                "point_id": "decode-success",
                "model_id": model_id,
                "sequence_length": 1024,
                "block_size": 64,
                "op_type": "reduction_overhead",
                "op_name": None,
                "duration_us": 30.0,
                "dynamic_workspace_bytes": 25,
                "output_bytes": 1536,
            },
            {
                "point_id": "decode-failed",
                "model_id": model_id,
                "sequence_length": 1024,
                "block_size": 64,
                "op_type": "gemv",
                "op_name": "fc1",
                "duration_us": 15000.0,
                "dynamic_workspace_bytes": 1500000,
                "output_bytes": 9999999,
            },
            {
                "point_id": "decode-failed",
                "model_id": model_id,
                "sequence_length": 1024,
                "block_size": 64,
                "op_type": "attention_fetch_compute",
                "op_name": None,
                "duration_us": 5000.0,
                "dynamic_workspace_bytes": 2500000,
                "output_bytes": 8888888,
            },
            {
                "point_id": "decode-failed",
                "model_id": model_id,
                "sequence_length": 1024,
                "block_size": 64,
                "op_type": "reduction_overhead",
                "op_name": None,
                "duration_us": 3000.0,
                "dynamic_workspace_bytes": 1750000,
                "output_bytes": 7777777,
            },
        ]
    ).to_csv(raw_root / "decode_events.csv", index=False)
    pd.DataFrame(
        [
            {"point_id": "decode-success", "public_status": "success"},
            {"point_id": "decode-failed", "public_status": "profile_oom"},
        ]
    ).to_csv(raw_root / "decode_events_status.csv", index=False)

    pd.DataFrame(
        [
            {
                "point_id": "pcie-success",
                "model_id": model_id,
                "block_size": 64,
                "kv_block_bytes": 2097152,
                "transfer_only_us": 1000.0,
                "overlap_total_us": 500.0,
                "dummy_compute_us": 1000.0,
                "exposed_transfer_us": 0.0,
                "timed_iteration": 0,
            },
            {
                "point_id": "pcie-success",
                "model_id": model_id,
                "block_size": 64,
                "kv_block_bytes": 2097152,
                "transfer_only_us": 3000.0,
                "overlap_total_us": 2500.0,
                "dummy_compute_us": 0.0,
                "exposed_transfer_us": 2500.0,
                "timed_iteration": 1,
            },
            {
                "point_id": "pcie-failed",
                "model_id": model_id,
                "block_size": 64,
                "kv_block_bytes": 2097152,
                "transfer_only_us": 9000.0,
                "overlap_total_us": 9500.0,
                "dummy_compute_us": 100.0,
                "exposed_transfer_us": 9400.0,
                "timed_iteration": 0,
            },
        ]
    ).to_csv(raw_root / "pcie_events.csv", index=False)
    pd.DataFrame(
        [
            {"point_id": "pcie-success", "public_status": "success"},
            {"point_id": "pcie-failed", "public_status": "profile_failed"},
        ]
    ).to_csv(raw_root / "pcie_events_status.csv", index=False)

    result = profile_reducer.reduce_profile_events(run_root=run_root)

    model_constants = pd.read_csv(result.model_constants_path)
    prefill_summary = pd.read_csv(result.prefill_summary_path)
    decode_summary = pd.read_csv(result.decode_summary_path)
    pcie_summary = pd.read_csv(result.pcie_summary_path)

    assert result.prefill_row_count == 1
    assert result.decode_row_count == 1
    assert result.pcie_row_count == 1

    assert model_constants.to_dict("records") == [{"model_id": model_id}]
    assert prefill_summary.to_dict("records") == [
        {
            "model_id": model_id,
            "chunk_tokens": 64,
            "prefill_max_gemm_us": 220.0,
            "prefill_workspace_bytes": 96,
            "prefill_parked_activation_bytes": 6144,
        }
    ]
    assert decode_summary.to_dict("records") == [
        {
            "model_id": model_id,
            "sequence_length": 1024,
            "block_size": 64,
            "decode_max_gemv_us": 250.0,
            "attention_fetch_compute_us": 80.0,
            "reduction_overhead_us": 30.0,
            "decode_workspace_bytes": 500,
            "decode_parked_activation_bytes": 1536,
        }
    ]
    assert pcie_summary.iloc[0]["model_id"] == model_id
    assert pcie_summary.iloc[0]["block_size"] == 64
    assert pcie_summary.iloc[0]["kv_block_bytes"] == 2097152
    assert pcie_summary.iloc[0]["transfer_only_us"] == 2000.0
    assert pcie_summary.iloc[0]["overlap_total_us"] == 1500.0
    assert pcie_summary.iloc[0]["dummy_compute_us"] == 500.0
    assert pcie_summary.iloc[0]["exposed_transfer_us"] == 1000.0
    assert pcie_summary.iloc[0]["effective_gbps"] == pytest.approx(1.048576)
