from __future__ import annotations

import csv
import json
from pathlib import Path

from inference_profile import experiments, report, simulator, trace_contract
from inference_profile import telemetry
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


def _results_rows() -> list[dict[str, object]]:
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


def _timeline_rows() -> list[dict[str, object]]:
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


def _trace_rows() -> list[dict[str, object]]:
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


def _build_valid_bundle(run_root: Path) -> None:
    bundle_paths = bundle_paths_from_run_root(run_root)
    for directory in bundle_paths.directories:
        directory.mkdir(parents=True, exist_ok=True)

    (bundle_paths.logs_dir / "profile-stage.log").write_text(
        "profile stage complete\n",
        encoding="utf-8",
    )

    _write_json(bundle_paths.run_manifest_path, {"run_id": run_root.name})
    _write_json(
        bundle_paths.environment_path,
        {
            "stage": "profile",
            "models": ["facebook/opt-125m", "facebook/opt-350m", "facebook/opt-6.7b"],
            "cuda_available": False,
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
                "errors": [],
            },
            "secondary_trace": {
                "usable": True,
                "row_count": 3,
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
            }
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
            }
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
            }
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
            }
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
            }
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
            }
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
        rows=_results_rows(),
    )
    _write_csv(
        bundle_paths.derived_dir / simulator.SCHEDULE_TIMELINE_FILENAME,
        fieldnames=list(simulator.SCHEDULE_TIMELINE_COLUMNS),
        rows=_timeline_rows(),
    )
    _write_csv(
        bundle_paths.derived_dir / trace_contract.NORMALIZED_TRACE_FILENAME,
        fieldnames=list(trace_contract.NORMALIZED_TRACE_HEADERS),
        rows=_trace_rows(),
    )

    generate_profiling_plots(run_root=run_root)
    telemetry.append_telemetry_row(
        run_root,
        telemetry.make_baseline_telemetry_row(
            ts="2026-04-14T00:00:00Z",
            gpu_id=0,
            pt_step_ms=1.0,
            pt_mem_alloc_mb=1.0,
            pt_mem_reserved_mb=1.0,
            nvml_available=False,
            sampling_error="test",
        ),
    )
    report.generate_run_report(run_root=run_root)


def test_verify_bundle_fails_when_required_artifact_is_missing(tmp_path: Path) -> None:
    run_root = tmp_path / "missing-artifact"
    _build_valid_bundle(run_root)

    missing_relative = "derived/pcie_summary.csv"
    (run_root / missing_relative).unlink()

    result = verify_bundle(run_root)

    assert result["status"] == "fetch_failed"
    assert result["complete"] is False
    assert result["completeness_results"][missing_relative] is False
    assert result["missing_artifacts"] == [missing_relative]
    assert result["checksum_results"][missing_relative]["reason"] == "artifact missing"


def test_verify_bundle_fails_when_required_artifact_is_zero_byte(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "zero-byte-artifact"
    _build_valid_bundle(run_root)

    zero_byte_relative = f"plots/{PLOT_FILENAMES[-1]}"
    (run_root / zero_byte_relative).write_bytes(b"")

    result = verify_bundle(run_root)

    assert result["status"] == "fetch_failed"
    assert result["complete"] is False
    assert result["completeness_results"][zero_byte_relative] is False
    assert result["zero_byte_artifacts"] == [zero_byte_relative]
    assert (
        result["checksum_results"][zero_byte_relative]["reason"]
        == "artifact is zero-byte"
    )


def test_verify_bundle_fails_when_interactive_artifact_is_missing(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "missing-interactive-artifact"
    _build_valid_bundle(run_root)
    generate_profiling_plots(run_root=run_root)
    report.generate_run_report(run_root=run_root)
    (run_root / "plots" / INTERACTIVE_RAN_TRACE_FILENAME).unlink()

    result = verify_bundle(run_root)

    missing_relative = f"plots/{INTERACTIVE_RAN_TRACE_FILENAME}"
    assert result["status"] == "fetch_failed"
    assert missing_relative in result["missing_artifacts"]


def test_verify_bundle_fails_when_interactive_artifact_is_zero_byte(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "zero-byte-interactive-artifact"
    _build_valid_bundle(run_root)
    generate_profiling_plots(run_root=run_root)
    report.generate_run_report(run_root=run_root)
    interactive_relative = f"plots/{INTERACTIVE_RAN_TRACE_FILENAME}"
    (run_root / interactive_relative).write_bytes(b"")
    report.write_run_checksum_manifest(run_root=run_root)

    result = verify_bundle(run_root)

    assert result["status"] == "fetch_failed"
    assert result["completeness_results"][interactive_relative] is False
    assert interactive_relative in result["zero_byte_artifacts"]


def test_verify_bundle_accepts_revised_plot_contract_when_manifest_marks_revised(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "revised-bundle"
    _build_valid_bundle(run_root)

    manifest_path = run_root / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema_version"] = experiments.RAN_DGXSPARK_V1_SCHEMA_VERSION
    manifest["experiment_type"] = experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    plots_dir = run_root / "plots"
    for filename in PLOT_FILENAMES:
        original_path = plots_dir / filename
        revised_path = plots_dir / f"revised_{filename}"
        revised_path.write_bytes(original_path.read_bytes())
        revised_path.with_suffix(".pdf").write_bytes(original_path.read_bytes())
        original_path.unlink()
    (plots_dir / "revised_07_hardware_utilization_profiling.png").write_bytes(b"png")
    (plots_dir / "revised_07_hardware_utilization_profiling.pdf").write_bytes(b"png")
    (plots_dir / "revised_08_decode_memory_consumption.png").write_bytes(b"png")
    (plots_dir / "revised_08_decode_memory_consumption.pdf").write_bytes(b"png")
    (plots_dir / "revised_09_prefill_vram_composition_pie.png").write_bytes(b"png")
    (plots_dir / "revised_09_prefill_vram_composition_pie.pdf").write_bytes(b"png")

    interactive_original = plots_dir / INTERACTIVE_RAN_TRACE_FILENAME
    interactive_revised = plots_dir / f"revised_{INTERACTIVE_RAN_TRACE_FILENAME}"
    interactive_revised.write_text(
        interactive_original.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    interactive_original.unlink()
    revised_report_path = run_root / "report" / "report.md"
    revised_report_path.parent.mkdir(parents=True, exist_ok=True)
    revised_report_path.write_text(
        (run_root / "ran_inference_profiling_report.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    telemetry.append_telemetry_row(
        run_root,
        telemetry.make_baseline_telemetry_row(
            ts="2026-04-14T00:00:00Z",
            gpu_id=0,
            pt_step_ms=1.0,
            pt_mem_alloc_mb=1.0,
            pt_mem_reserved_mb=1.0,
            nvml_available=False,
            sampling_error="test",
        ),
    )

    report.write_run_checksum_manifest(run_root=run_root)
    result = verify_bundle(run_root)

    assert result["status"] == "success"
    assert (
        f"plots/revised_{INTERACTIVE_RAN_TRACE_FILENAME}"
        in result["required_artifacts"]
    )


def test_verify_bundle_fails_when_packed_timeline_artifact_is_missing(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "missing-packed-timeline-artifact"
    _build_valid_bundle(run_root)

    packed_relative = f"derived/{simulator.PACKED_EXEMPLAR_TIMELINE_FILENAME}"
    (run_root / packed_relative).unlink()

    result = verify_bundle(run_root)

    assert result["status"] == "fetch_failed"
    assert packed_relative in result["missing_artifacts"]
    assert result["completeness_results"][packed_relative] is False


def test_verify_bundle_accepts_zero_byte_worker_logs(tmp_path: Path) -> None:
    run_root = tmp_path / "zero-byte-worker-logs"
    _build_valid_bundle(run_root)

    stdout_relative = "logs/prefill-facebook-opt-125m-chunk-64.stdout.log"
    stderr_relative = "logs/prefill-facebook-opt-125m-chunk-64.stderr.log"
    (run_root / stdout_relative).write_bytes(b"")
    (run_root / stderr_relative).write_bytes(b"")
    report.write_run_checksum_manifest(run_root=run_root)

    result = verify_bundle(run_root)

    assert result["status"] == "success"
    assert result["complete"] is True
    assert result["zero_byte_artifacts"] == []
    assert result["completeness_results"][stdout_relative] is True
    assert result["completeness_results"][stderr_relative] is True
    assert result["artifact_results"][stdout_relative]["allows_zero_bytes"] is True
    assert result["artifact_results"][stderr_relative]["allows_zero_bytes"] is True
    assert result["checksum_results"][stdout_relative]["match"] is True
    assert result["checksum_results"][stderr_relative]["match"] is True


def test_verify_bundle_fails_when_checksum_entry_is_missing(tmp_path: Path) -> None:
    run_root = tmp_path / "missing-checksum-entry"
    _build_valid_bundle(run_root)

    checksum_path = run_root / "checksums" / "sha256sums.txt"
    target_relative = "derived/decode_summary.csv"
    filtered_lines = [
        line
        for line in checksum_path.read_text(encoding="utf-8").splitlines()
        if not line.endswith(f"  {target_relative}")
    ]
    checksum_path.write_text("\n".join(filtered_lines) + "\n", encoding="utf-8")

    result = verify_bundle(run_root)

    assert result["status"] == "fetch_failed"
    assert result["checksums_valid"] is False
    assert result["checksum_missing_artifacts"] == [target_relative]
    assert (
        result["checksum_results"][target_relative]["reason"]
        == "missing checksum manifest entry"
    )


def test_verify_bundle_fails_when_checksum_mismatch_is_detected(tmp_path: Path) -> None:
    run_root = tmp_path / "checksum-mismatch"
    _build_valid_bundle(run_root)

    target_relative = "environment.json"
    (run_root / target_relative).write_text(
        json.dumps({"stage": "profile", "cuda_available": True}, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    result = verify_bundle(run_root)

    assert result["status"] == "fetch_failed"
    assert result["checksums_valid"] is False
    assert result["checksum_mismatches"] == [target_relative]
    assert result["checksum_results"][target_relative]["reason"] == "checksum mismatch"
    assert (
        result["checksum_results"][target_relative]["computed"]
        != result["checksum_results"][target_relative]["expected"]
    )
