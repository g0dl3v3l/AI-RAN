from __future__ import annotations

import csv
import json
from pathlib import Path

from inference_profile import report, simulator, trace_contract
from inference_profile.paths import bundle_paths_from_run_root
from inference_profile.plots import (
    INTERACTIVE_RAN_TRACE_FILENAME,
    PLOT_FILENAMES,
    generate_profiling_plots,
)
from inference_profile.verify_bundle import verify_bundle


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


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _build_results_rows() -> list[dict[str, object]]:
    return [
        {
            "model_id": "facebook/opt-125m",
            "chunk_tokens": 512,
            "sequence_length": 1024,
            "weight_bytes": 250_478_592,
            "vram_ceiling_bytes": 1_500_000_000,
            "prefill_max_gemm_us": 500.0,
            "prefill_workspace_bytes": 2_048,
            "prefill_parked_activation_bytes": 1_024,
            "decode_max_gemv_us": 50.0,
            "attention_fetch_compute_us": 60.0,
            "reduction_overhead_us": 10.0,
            "pcie_exposed_us": 6.0,
            "survival_vram_bytes": 1_249_518_336,
            "decode_runway_bytes": 524_288,
            "decode_runway_tokens": 256,
            "ttft_ms": 0.6,
            "tpot_ms_vram": 1.2,
            "tpot_ms_pcie_async": 1.4,
            "trace_sha256": "a" * 64,
            "status": "success",
        },
        {
            "model_id": "facebook/opt-350m",
            "chunk_tokens": 1024,
            "sequence_length": 2048,
            "weight_bytes": 700_000_000,
            "vram_ceiling_bytes": 2_200_000_000,
            "prefill_max_gemm_us": 920.0,
            "prefill_workspace_bytes": 4_096,
            "prefill_parked_activation_bytes": 2_048,
            "decode_max_gemv_us": 80.0,
            "attention_fetch_compute_us": 95.0,
            "reduction_overhead_us": 14.0,
            "pcie_exposed_us": 8.0,
            "survival_vram_bytes": 1_499_993_856,
            "decode_runway_bytes": 786_432,
            "decode_runway_tokens": 384,
            "ttft_ms": 0.8,
            "tpot_ms_vram": 1.9,
            "tpot_ms_pcie_async": 2.2,
            "trace_sha256": "b" * 64,
            "status": "success",
        },
        {
            "model_id": "facebook/opt-6.7b",
            "chunk_tokens": 1024,
            "sequence_length": 4096,
            "weight_bytes": 12_000_000_000,
            "vram_ceiling_bytes": 12_500_000_000,
            "prefill_max_gemm_us": 2_500.0,
            "prefill_workspace_bytes": 8_192,
            "prefill_parked_activation_bytes": 4_096,
            "decode_max_gemv_us": 180.0,
            "attention_fetch_compute_us": 210.0,
            "reduction_overhead_us": 32.0,
            "pcie_exposed_us": 18.0,
            "survival_vram_bytes": 0,
            "decode_runway_bytes": 0,
            "decode_runway_tokens": 0,
            "ttft_ms": None,
            "tpot_ms_vram": None,
            "tpot_ms_pcie_async": None,
            "trace_sha256": "c" * 64,
            "status": "decode_trace_fit_failed_vram",
        },
    ]


def _build_timeline_rows() -> list[dict[str, object]]:
    return [
        {
            "model_id": "facebook/opt-125m",
            "chunk_tokens": 512,
            "sequence_length": 1024,
            "phase": "prefill",
            "mode": "prefill",
            "family": "prefill_gemm",
            "chunk_index": 0,
            "token_index": 0,
            "layer_index": 0,
            "atom_index": 0,
            "trace_interval_index": 1,
            "start_time_ms": 0.2,
            "end_time_ms": 0.8,
            "duration_ms": 0.6,
        },
        {
            "model_id": "facebook/opt-125m",
            "chunk_tokens": 512,
            "sequence_length": 1024,
            "phase": "decode",
            "mode": "vram",
            "family": "decode_gemv",
            "chunk_index": None,
            "token_index": 0,
            "layer_index": 0,
            "atom_index": 0,
            "trace_interval_index": 3,
            "start_time_ms": 1.2,
            "end_time_ms": 1.6,
            "duration_ms": 0.4,
        },
        {
            "model_id": "facebook/opt-125m",
            "chunk_tokens": 512,
            "sequence_length": 1024,
            "phase": "decode",
            "mode": "pcie_async",
            "family": "pcie_exposed_transfer",
            "chunk_index": None,
            "token_index": 0,
            "layer_index": 0,
            "atom_index": 0,
            "trace_interval_index": 3,
            "start_time_ms": 1.2,
            "end_time_ms": 1.7,
            "duration_ms": 0.5,
        },
    ]


def _build_trace_rows() -> list[dict[str, object]]:
    return [
        {
            "time_ms": 0.0,
            "sm_utilization": 100.0,
            "slot_duration_ms": 0.2,
            "source_schema": trace_contract.SOURCE_SCHEMA_A,
        },
        {
            "time_ms": 0.2,
            "sm_utilization": 0.0,
            "slot_duration_ms": 250.0,
            "source_schema": trace_contract.SOURCE_SCHEMA_A,
        },
        {
            "time_ms": 250.2,
            "sm_utilization": 100.0,
            "slot_duration_ms": 0.2,
            "source_schema": trace_contract.SOURCE_SCHEMA_A,
        },
        {
            "time_ms": 250.4,
            "sm_utilization": 0.0,
            "slot_duration_ms": 250.0,
            "source_schema": trace_contract.SOURCE_SCHEMA_A,
        },
    ]


def _build_run_bundle(run_root: Path) -> None:
    bundle_paths = bundle_paths_from_run_root(run_root)
    for directory in bundle_paths.directories:
        directory.mkdir(parents=True, exist_ok=True)

    (bundle_paths.logs_dir / "profile-stage.log").write_text(
        "profile stage complete\n",
        encoding="utf-8",
    )

    _write_json(
        bundle_paths.run_manifest_path,
        {
            "run_id": run_root.name,
            "final_status": "success",
        },
    )
    _write_json(
        bundle_paths.environment_path,
        {
            "stage": "profile",
            "models": [
                "facebook/opt-125m",
                "facebook/opt-350m",
                "facebook/opt-6.7b",
            ],
            "cuda_available": False,
            "python_version": "3.12.0",
        },
    )
    _write_json(
        bundle_paths.raw_dir / trace_contract.TRACE_INSPECTION_FILENAME,
        {
            "primary_trace": {
                "usable": True,
                "schema_detected": trace_contract.SOURCE_SCHEMA_A,
                "row_count": 4,
                "normalized_row_count": 4,
                "time_unit_hint": "ms",
                "monotonicity": {
                    "checked_column": "time_ms",
                    "is_non_decreasing": True,
                    "negative_delta_count": 0,
                    "zero_delta_count": 0,
                    "positive_delta_count": 3,
                },
                "errors": [],
            },
            "secondary_trace": {
                "usable": True,
                "row_count": 3,
                "time_unit_hints": ["ms"],
                "monotonicity": {
                    "checked_column": "time_ms",
                    "is_non_decreasing": True,
                    "negative_delta_count": 0,
                },
                "errors": [],
            },
        },
    )

    _write_csv(
        bundle_paths.raw_dir / "prefill_events.csv",
        fieldnames=[
            "model_id",
            "chunk_tokens",
            "op_name",
            "duration_us",
            "dynamic_workspace_bytes",
            "output_bytes",
        ],
        rows=[
            {
                "model_id": "facebook/opt-125m",
                "chunk_tokens": 512,
                "op_name": "q_proj",
                "duration_us": 500.0,
                "dynamic_workspace_bytes": 2_048,
                "output_bytes": 1_024,
            },
            {
                "model_id": "facebook/opt-350m",
                "chunk_tokens": 1024,
                "op_name": "attention",
                "duration_us": 920.0,
                "dynamic_workspace_bytes": 4_096,
                "output_bytes": 2_048,
            },
        ],
    )
    _write_csv(
        bundle_paths.raw_dir / "prefill_events_status.csv",
        fieldnames=["point_id", "model_id", "chunk_tokens", "public_status"],
        rows=[
            {
                "point_id": "prefill-125m",
                "model_id": "facebook/opt-125m",
                "chunk_tokens": 512,
                "public_status": "success",
            },
            {
                "point_id": "prefill-350m",
                "model_id": "facebook/opt-350m",
                "chunk_tokens": 1024,
                "public_status": "success",
            },
        ],
    )
    _write_csv(
        bundle_paths.raw_dir / "decode_events.csv",
        fieldnames=[
            "model_id",
            "sequence_length",
            "block_size",
            "op_type",
            "op_name",
            "duration_us",
            "dynamic_workspace_bytes",
            "output_bytes",
        ],
        rows=[
            {
                "model_id": "facebook/opt-125m",
                "sequence_length": 1024,
                "block_size": 512,
                "op_type": "gemv",
                "op_name": "out_proj",
                "duration_us": 50.0,
                "dynamic_workspace_bytes": 1_024,
                "output_bytes": 512,
            },
            {
                "model_id": "facebook/opt-350m",
                "sequence_length": 2048,
                "block_size": 1024,
                "op_type": "attention_fetch_compute",
                "op_name": "",
                "duration_us": 95.0,
                "dynamic_workspace_bytes": 2_048,
                "output_bytes": 1_024,
            },
        ],
    )
    _write_csv(
        bundle_paths.raw_dir / "decode_events_status.csv",
        fieldnames=[
            "point_id",
            "model_id",
            "sequence_length",
            "block_size",
            "public_status",
        ],
        rows=[
            {
                "point_id": "decode-125m",
                "model_id": "facebook/opt-125m",
                "sequence_length": 1024,
                "block_size": 512,
                "public_status": "success",
            },
            {
                "point_id": "decode-350m",
                "model_id": "facebook/opt-350m",
                "sequence_length": 2048,
                "block_size": 1024,
                "public_status": "success",
            },
        ],
    )
    _write_csv(
        bundle_paths.raw_dir / "pcie_events.csv",
        fieldnames=[
            "model_id",
            "block_size",
            "kv_block_bytes",
            "transfer_only_us",
            "overlap_total_us",
            "dummy_compute_us",
            "exposed_transfer_us",
        ],
        rows=[
            {
                "model_id": "facebook/opt-125m",
                "block_size": 512,
                "kv_block_bytes": 524_288,
                "transfer_only_us": 12.0,
                "overlap_total_us": 10.0,
                "dummy_compute_us": 4.0,
                "exposed_transfer_us": 6.0,
            },
            {
                "model_id": "facebook/opt-350m",
                "block_size": 1024,
                "kv_block_bytes": 1_048_576,
                "transfer_only_us": 16.0,
                "overlap_total_us": 13.0,
                "dummy_compute_us": 5.0,
                "exposed_transfer_us": 8.0,
            },
        ],
    )
    _write_csv(
        bundle_paths.raw_dir / "pcie_events_status.csv",
        fieldnames=["point_id", "model_id", "block_size", "public_status"],
        rows=[
            {
                "point_id": "pcie-125m",
                "model_id": "facebook/opt-125m",
                "block_size": 512,
                "public_status": "success",
            },
            {
                "point_id": "pcie-350m",
                "model_id": "facebook/opt-350m",
                "block_size": 1024,
                "public_status": "success",
            },
        ],
    )

    _write_csv(
        bundle_paths.derived_dir / "model_constants.csv",
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
            "kv_bytes_per_token_all_layers",
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
                "vram_ceiling_bytes": 1_500_000_000,
                "kv_bytes_per_token_all_layers": 36_864,
            },
            {
                "model_id": "facebook/opt-350m",
                "num_hidden_layers": 24,
                "hidden_size": 1024,
                "num_attention_heads": 16,
                "ffn_dim": 4096,
                "layer_index": 11,
                "layer_weight_bytes": 25_000_000,
                "total_weight_bytes_fp16": 700_000_000,
                "vram_ceiling_bytes": 2_200_000_000,
                "kv_bytes_per_token_all_layers": 98_304,
            },
            {
                "model_id": "facebook/opt-6.7b",
                "num_hidden_layers": 32,
                "hidden_size": 4096,
                "num_attention_heads": 32,
                "ffn_dim": 16384,
                "layer_index": 15,
                "layer_weight_bytes": 400_000_000,
                "total_weight_bytes_fp16": 12_000_000_000,
                "vram_ceiling_bytes": 12_500_000_000,
                "kv_bytes_per_token_all_layers": 524_288,
            },
        ],
    )
    _write_csv(
        bundle_paths.derived_dir / "prefill_summary.csv",
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
                "chunk_tokens": 512,
                "prefill_max_gemm_us": 500.0,
                "prefill_workspace_bytes": 2_048,
                "prefill_parked_activation_bytes": 1_024,
            },
            {
                "model_id": "facebook/opt-350m",
                "chunk_tokens": 1024,
                "prefill_max_gemm_us": 920.0,
                "prefill_workspace_bytes": 4_096,
                "prefill_parked_activation_bytes": 2_048,
            },
        ],
    )
    _write_csv(
        bundle_paths.derived_dir / "decode_summary.csv",
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
                "block_size": 512,
                "decode_max_gemv_us": 50.0,
                "attention_fetch_compute_us": 60.0,
                "reduction_overhead_us": 10.0,
                "decode_workspace_bytes": 1_024,
                "decode_parked_activation_bytes": 512,
            },
            {
                "model_id": "facebook/opt-350m",
                "sequence_length": 2048,
                "block_size": 1024,
                "decode_max_gemv_us": 80.0,
                "attention_fetch_compute_us": 95.0,
                "reduction_overhead_us": 14.0,
                "decode_workspace_bytes": 2_048,
                "decode_parked_activation_bytes": 1_024,
            },
        ],
    )
    _write_csv(
        bundle_paths.derived_dir / "pcie_summary.csv",
        fieldnames=[
            "model_id",
            "block_size",
            "kv_block_bytes",
            "transfer_only_us",
            "overlap_total_us",
            "dummy_compute_us",
            "exposed_transfer_us",
            "effective_gbps",
        ],
        rows=[
            {
                "model_id": "facebook/opt-125m",
                "block_size": 512,
                "kv_block_bytes": 524_288,
                "transfer_only_us": 12.0,
                "overlap_total_us": 10.0,
                "dummy_compute_us": 4.0,
                "exposed_transfer_us": 6.0,
                "effective_gbps": 43.6907,
            },
            {
                "model_id": "facebook/opt-350m",
                "block_size": 1024,
                "kv_block_bytes": 1_048_576,
                "transfer_only_us": 16.0,
                "overlap_total_us": 13.0,
                "dummy_compute_us": 5.0,
                "exposed_transfer_us": 8.0,
                "effective_gbps": 65.536,
            },
        ],
    )
    _write_csv(
        bundle_paths.derived_dir / simulator.SIMULATION_INPUTS_FILENAME,
        fieldnames=["model_id", "chunk_tokens", "sequence_length"],
        rows=[
            {
                "model_id": "facebook/opt-125m",
                "chunk_tokens": 512,
                "sequence_length": 1024,
            },
            {
                "model_id": "facebook/opt-350m",
                "chunk_tokens": 1024,
                "sequence_length": 2048,
            },
            {
                "model_id": "facebook/opt-6.7b",
                "chunk_tokens": 1024,
                "sequence_length": 4096,
            },
        ],
    )
    _write_csv(
        bundle_paths.derived_dir / simulator.SIMULATION_RESULTS_FILENAME,
        fieldnames=list(simulator.SIMULATION_RESULTS_COLUMNS),
        rows=_build_results_rows(),
    )
    _write_csv(
        bundle_paths.derived_dir / simulator.SCHEDULE_TIMELINE_FILENAME,
        fieldnames=list(simulator.SCHEDULE_TIMELINE_COLUMNS),
        rows=_build_timeline_rows(),
    )
    _write_csv(
        bundle_paths.derived_dir / trace_contract.NORMALIZED_TRACE_FILENAME,
        fieldnames=list(trace_contract.NORMALIZED_TRACE_HEADERS),
        rows=_build_trace_rows(),
    )


def test_generate_run_report_writes_markdown_and_verifies_complete_bundle(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "report-bundle"
    _build_run_bundle(run_root)

    generate_profiling_plots(run_root=run_root)
    report_path = report.generate_run_report(run_root=run_root)

    assert report_path == run_root / "ran_inference_profiling_report.md"
    assert report_path.exists()
    assert (run_root / "checksums" / "sha256sums.txt").exists()
    assert (run_root / "derived" / simulator.PACKED_EXEMPLAR_TIMELINE_FILENAME).exists()

    content = report_path.read_text(encoding="utf-8")
    assert "## Environment" in content
    assert "## Model Constants" in content
    assert "## Trace Inspection" in content
    assert "## Raw-Profile Summary Tables" in content
    assert "## SLA Tables" in content
    assert "## Per-Model Scaling Analysis" in content
    assert "### Failed configurations" in content
    assert "facebook/opt-125m" in content
    assert "facebook/opt-350m" in content
    assert "decode_trace_fit_failed_vram" in content

    for filename in PLOT_FILENAMES:
        assert f"(plots/{filename})" in content
    assert f"(plots/{INTERACTIVE_RAN_TRACE_FILENAME})" in content

    verification_result = verify_bundle(run_root)

    assert verification_result["status"] == "success"
    assert verification_result["complete"] is True
    assert verification_result["checksums_valid"] is True
    assert verification_result["missing_artifacts"] == []
    assert verification_result["zero_byte_artifacts"] == []
    assert verification_result["checksum_missing_artifacts"] == []
    assert verification_result["checksum_mismatches"] == []
