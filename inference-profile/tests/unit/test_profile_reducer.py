"""Unit tests for profile reduction logic."""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from inference_profile import experiments, manifests, paths, profile_reducer


def test_reduce_prefill_events_computes_exact_maxima():
    """Verify prefill reduction computes exact maxima for all metrics."""
    raw_events = pd.DataFrame(
        {
            "model_id": ["facebook/opt-125m"] * 8,
            "chunk_tokens": [64] * 8,
            "op_type": ["gemm"] * 8,
            "op_name": [
                "q_proj",
                "k_proj",
                "fc1",
                "fc2",
                "q_proj",
                "k_proj",
                "fc1",
                "fc2",
            ],
            "duration_us": [100.0, 120.0, 180.0, 150.0, 110.0, 90.0, 220.0, 140.0],
            "dynamic_workspace_bytes": [32, 48, 96, 64, 40, 44, 112, 70],
            "output_bytes": [1536, 1536, 6144, 1536, 1536, 1536, 6144, 1536],
        }
    )

    reduced = profile_reducer._reduce_prefill_events(raw_events)

    assert len(reduced) == 1
    assert reduced.iloc[0]["model_id"] == "facebook/opt-125m"
    assert reduced.iloc[0]["chunk_tokens"] == 64

    assert reduced.iloc[0]["prefill_max_gemm_us"] == 220.0
    assert reduced.iloc[0]["prefill_workspace_bytes"] == 112
    assert reduced.iloc[0]["prefill_parked_activation_bytes"] == 6144


def test_reduce_prefill_events_ignores_attention_rows_for_gemm_duration_only():
    raw_events = pd.DataFrame(
        {
            "model_id": ["facebook/opt-125m"] * 3,
            "chunk_tokens": [64] * 3,
            "op_type": ["gemm", "gemm", "attention"],
            "op_name": ["q_proj", "fc1", "attention"],
            "duration_us": [100.0, 220.0, 900.0],
            "dynamic_workspace_bytes": [32, 112, 256],
            "output_bytes": [1536, 6144, 2048],
        }
    )

    reduced = profile_reducer._reduce_prefill_events(raw_events)

    assert reduced.iloc[0]["prefill_max_gemm_us"] == 220.0
    assert reduced.iloc[0]["prefill_workspace_bytes"] == 256


def test_reduce_decode_events_separates_timing_buckets_and_final_output_semantics():
    raw_events = pd.DataFrame(
        {
            "model_id": ["facebook/opt-125m"] * 8,
            "sequence_length": [1024] * 8,
            "block_size": [64] * 8,
            "op_type": [
                "gemv",
                "gemv",
                "attention_fetch_compute",
                "reduction_overhead",
                "gemv",
                "attention_fetch_compute",
                "reduction_overhead",
                "gemv",
            ],
            "op_name": ["q_proj", "fc1", None, None, "out_proj", None, None, "fc2"],
            "duration_us": [100.0, 250.0, 80.0, 30.0, 190.0, 100.0, 50.0, 175.0],
            "dynamic_workspace_bytes": [10, 20, 500, 25, 12, 650, 30, 14],
            "output_bytes": [1536, 6144, 4096, 1536, 1536, 8192, 1536, 1536],
        }
    )

    reduced = profile_reducer._reduce_decode_events(raw_events)

    assert len(reduced) == 1
    assert reduced.iloc[0]["decode_max_gemv_us"] == 250.0
    assert reduced.iloc[0]["attention_fetch_compute_us"] == 90.0
    assert reduced.iloc[0]["reduction_overhead_us"] == 40.0
    assert reduced.iloc[0]["decode_workspace_bytes"] == 650
    assert reduced.iloc[0]["decode_parked_activation_bytes"] == 1536


def test_reduce_pcie_events_recomputes_formula_from_aggregated_timings():
    raw_events = pd.DataFrame(
        {
            "model_id": ["facebook/opt-125m"] * 2,
            "block_size": [64, 64],
            "kv_block_bytes": [2_097_152, 2_097_152],
            "transfer_only_us": [1000.0, 3000.0],
            "overlap_total_us": [500.0, 2500.0],
            "dummy_compute_us": [1000.0, 0.0],
            "exposed_transfer_us": [0.0, 2500.0],
        }
    )

    reduced = profile_reducer._reduce_pcie_events(raw_events)

    assert len(reduced) == 1

    assert reduced.iloc[0]["transfer_only_us"] == 2000.0
    assert reduced.iloc[0]["overlap_total_us"] == 1500.0
    assert reduced.iloc[0]["dummy_compute_us"] == 500.0
    assert reduced.iloc[0]["exposed_transfer_us"] == 1000.0
    assert reduced.iloc[0]["effective_gbps"] == pytest.approx(1.048576)


def test_reduce_empty_dataframes_keep_fixed_column_order():
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
    assert list(decode_result.columns) == [
        "model_id",
        "sequence_length",
        "block_size",
        "decode_max_gemv_us",
        "attention_fetch_compute_us",
        "reduction_overhead_us",
        "decode_workspace_bytes",
        "decode_parked_activation_bytes",
    ]

    pcie_result = profile_reducer._reduce_pcie_events(empty_df)
    assert len(pcie_result) == 0
    assert list(pcie_result.columns) == [
        "model_id",
        "block_size",
        "kv_block_bytes",
        "transfer_only_us",
        "overlap_total_us",
        "dummy_compute_us",
        "exposed_transfer_us",
        "effective_gbps",
    ]


def test_reduce_profile_events_end_to_end():
    """Verify end-to-end reduction produces all four summary files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_root = Path(tmpdir)
        raw_root = run_root / "raw"
        raw_root.mkdir(parents=True)

        # Create minimal raw event files
        prefill_df = pd.DataFrame(
            {
                "model_id": ["facebook/opt-125m"],
                "chunk_tokens": [64],
                "op_name": ["q_proj"],
                "duration_us": [100.0],
                "dynamic_workspace_bytes": [1024],
                "output_bytes": [512],
            }
        )
        prefill_df.to_csv(raw_root / "prefill_events.csv", index=False)

        decode_df = pd.DataFrame(
            {
                "model_id": ["facebook/opt-125m", "facebook/opt-125m"],
                "sequence_length": [1024, 1024],
                "block_size": [64, 64],
                "op_type": ["gemv", "reduction_overhead"],
                "op_name": ["q_proj", None],
                "duration_us": [100.0, 25.0],
                "dynamic_workspace_bytes": [1024, 128],
                "output_bytes": [2048, 512],
            }
        )
        decode_df.to_csv(raw_root / "decode_events.csv", index=False)

        pcie_df = pd.DataFrame(
            {
                "model_id": ["facebook/opt-125m"],
                "block_size": [64],
                "kv_block_bytes": [2_097_152],
                "transfer_only_us": [1000.0],
                "overlap_total_us": [1500.0],
                "dummy_compute_us": [600.0],
                "exposed_transfer_us": [900.0],
            }
        )
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

        prefill_summary = pd.read_csv(result.prefill_summary_path)
        decode_summary = pd.read_csv(result.decode_summary_path)
        pcie_summary = pd.read_csv(result.pcie_summary_path)

        assert "effective_gbps" not in prefill_summary.columns
        assert "effective_gbps" not in decode_summary.columns
        assert "effective_gbps" in pcie_summary.columns
        assert decode_summary.iloc[0]["decode_parked_activation_bytes"] == 512


def test_reduce_profile_events_revised_schema_groups_by_sm_ai_and_decode_mode(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "revised-profile-run"
    bundle_paths = paths.bundle_paths_from_run_root(run_root)
    for directory in bundle_paths.directories:
        directory.mkdir(parents=True, exist_ok=True)
    manifests.initialize_run_manifest(
        bundle_paths,
        schema_version=experiments.RAN_DGXSPARK_V1_SCHEMA_VERSION,
        metadata={
            "experiment_type": experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE,
        },
    )

    raw_root = run_root / "raw"
    pd.DataFrame(
        [
            {
                "model_id": "facebook/opt-125m",
                "chunk_tokens": 64,
                "op_type": "gemm",
                "op_name": "fc1",
                "sm_ai_partition": 8,
                "timed_iteration": 0,
                "duration_us": 180.0,
                "dynamic_workspace_bytes": 96,
                "output_bytes": 6144,
                "max_input_tokens": 1024,
                "telemetry_tier": experiments.RAN_DGXSPARK_V1_TELEMETRY_TIER,
                "telemetry_provider": "nvidia-smi",
                "telemetry_status": "ok",
                "nvml_available": True,
                "gpu_util": 12.0,
                "gpu_mem_used_mb": 345.0,
                "sm_clock_mhz": 1500.0,
                "mem_clock_mhz": 9000.0,
                "power_w": 42.5,
                "pt_step_ms": 0.18,
                "pt_mem_alloc_mb": 8.0,
                "pt_mem_reserved_mb": 10.0,
                "pt_workspace_mb": 2.0,
                "microscopic_telemetry_status": "unavailable",
                "microscopic_error": "external profiler unavailable",
            },
            {
                "model_id": "facebook/opt-125m",
                "chunk_tokens": 64,
                "op_type": "gemm",
                "op_name": "fc1",
                "sm_ai_partition": 16,
                "timed_iteration": 0,
                "duration_us": 220.0,
                "dynamic_workspace_bytes": 128,
                "output_bytes": 8192,
                "max_input_tokens": 1024,
                "telemetry_tier": experiments.RAN_DGXSPARK_V1_TELEMETRY_TIER,
                "telemetry_provider": "nvidia-smi",
                "telemetry_status": "ok",
                "nvml_available": True,
                "gpu_util": 16.0,
                "gpu_mem_used_mb": 355.0,
                "sm_clock_mhz": 1510.0,
                "mem_clock_mhz": 9010.0,
                "power_w": 43.5,
                "pt_step_ms": 0.22,
                "pt_mem_alloc_mb": 9.0,
                "pt_mem_reserved_mb": 11.0,
                "pt_workspace_mb": 3.0,
                "microscopic_telemetry_status": "unavailable",
                "microscopic_error": "external profiler unavailable",
            },
        ]
    ).to_csv(raw_root / "prefill_events.csv", index=False)

    pd.DataFrame(
        [
            {
                "model_id": "facebook/opt-125m",
                "sequence_length": 1024,
                "block_size": 64,
                "sm_ai_partition": 8,
                "decode_mode": "vram",
                "op_type": "gemv",
                "op_name": "fc1",
                "duration_us": 90.0,
                "dynamic_workspace_bytes": 64,
                "output_bytes": 512,
                "telemetry_tier": experiments.RAN_DGXSPARK_V1_TELEMETRY_TIER,
                "telemetry_provider": "nvidia-smi",
                "telemetry_status": "ok",
            },
            {
                "model_id": "facebook/opt-125m",
                "sequence_length": 1024,
                "block_size": 64,
                "sm_ai_partition": 8,
                "decode_mode": "vram",
                "op_type": "attention_fetch_compute",
                "op_name": None,
                "duration_us": 50.0,
                "dynamic_workspace_bytes": 80,
                "output_bytes": 256,
                "telemetry_tier": experiments.RAN_DGXSPARK_V1_TELEMETRY_TIER,
                "telemetry_provider": "nvidia-smi",
                "telemetry_status": "ok",
            },
            {
                "model_id": "facebook/opt-125m",
                "sequence_length": 1024,
                "block_size": 64,
                "sm_ai_partition": 8,
                "decode_mode": "vram",
                "op_type": "reduction_overhead",
                "op_name": None,
                "duration_us": 10.0,
                "dynamic_workspace_bytes": 24,
                "output_bytes": 128,
                "telemetry_tier": experiments.RAN_DGXSPARK_V1_TELEMETRY_TIER,
                "telemetry_provider": "nvidia-smi",
                "telemetry_status": "ok",
            },
            {
                "model_id": "facebook/opt-125m",
                "sequence_length": 1024,
                "block_size": 64,
                "sm_ai_partition": 8,
                "decode_mode": "pcie_async",
                "op_type": "gemv",
                "op_name": "fc1",
                "duration_us": 95.0,
                "dynamic_workspace_bytes": 68,
                "output_bytes": 512,
                "telemetry_tier": experiments.RAN_DGXSPARK_V1_TELEMETRY_TIER,
                "telemetry_provider": "nvidia-smi",
                "telemetry_status": "ok",
            },
            {
                "model_id": "facebook/opt-125m",
                "sequence_length": 1024,
                "block_size": 64,
                "sm_ai_partition": 8,
                "decode_mode": "pcie_async",
                "op_type": "attention_fetch_compute",
                "op_name": None,
                "duration_us": 55.0,
                "dynamic_workspace_bytes": 84,
                "output_bytes": 256,
                "telemetry_tier": experiments.RAN_DGXSPARK_V1_TELEMETRY_TIER,
                "telemetry_provider": "nvidia-smi",
                "telemetry_status": "ok",
            },
            {
                "model_id": "facebook/opt-125m",
                "sequence_length": 1024,
                "block_size": 64,
                "sm_ai_partition": 8,
                "decode_mode": "pcie_async",
                "op_type": "reduction_overhead",
                "op_name": None,
                "duration_us": 12.0,
                "dynamic_workspace_bytes": 26,
                "output_bytes": 128,
                "telemetry_tier": experiments.RAN_DGXSPARK_V1_TELEMETRY_TIER,
                "telemetry_provider": "nvidia-smi",
                "telemetry_status": "ok",
            },
        ]
    ).to_csv(raw_root / "decode_events.csv", index=False)

    pd.DataFrame(
        [
            {
                "model_id": "facebook/opt-125m",
                "block_size": 64,
                "kv_block_bytes": 2_097_152,
                "transfer_only_us": 1000.0,
                "overlap_total_us": 800.0,
                "dummy_compute_us": 500.0,
                "exposed_transfer_us": 300.0,
                "timed_iteration": 0,
                "overlap_status": "measured",
                "telemetry_tier": experiments.RAN_DGXSPARK_V1_TELEMETRY_TIER,
                "telemetry_provider": "nvidia-smi",
                "telemetry_status": "ok",
            }
        ]
    ).to_csv(raw_root / "pcie_events.csv", index=False)

    result = profile_reducer.reduce_profile_events(run_root=run_root)

    prefill_summary = pd.read_csv(result.prefill_summary_path)
    decode_summary = pd.read_csv(result.decode_summary_path)
    pcie_summary = pd.read_csv(result.pcie_summary_path)

    assert set(prefill_summary.columns) >= {
        "model_id",
        "chunk_tokens",
        "sm_ai_partition",
        "max_input_tokens",
        "telemetry_tier",
        "telemetry_status",
    }
    assert sorted(prefill_summary["sm_ai_partition"].tolist()) == [8, 16]
    assert prefill_summary["max_input_tokens"].tolist() == [1024, 1024]

    assert set(decode_summary.columns) >= {
        "model_id",
        "sequence_length",
        "block_size",
        "sm_ai_partition",
        "decode_mode",
        "telemetry_tier",
    }
    assert sorted(decode_summary["decode_mode"].tolist()) == ["pcie_async", "vram"]

    assert set(pcie_summary.columns) >= {"overlap_status", "telemetry_tier"}
    assert pcie_summary.iloc[0]["overlap_status"] == "measured"
