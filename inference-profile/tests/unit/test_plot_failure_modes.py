from __future__ import annotations

import csv
from pathlib import Path

import pytest

from inference_profile import simulator, trace_contract
from inference_profile.plots import PlotGenerationError, generate_profiling_plots


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


def _build_minimal_trace_rows() -> list[dict[str, object]]:
    return [
        {
            "time_ms": 0.0,
            "sm_utilization": 100.0,
            "slot_duration_ms": 0.5,
            "source_schema": trace_contract.SOURCE_SCHEMA_A,
        },
        {
            "time_ms": 0.5,
            "sm_utilization": 0.0,
            "slot_duration_ms": 2.0,
            "source_schema": trace_contract.SOURCE_SCHEMA_A,
        },
    ]


def _build_single_success_result_row() -> list[dict[str, object]]:
    return [
        {
            "model_id": "facebook/opt-125m",
            "chunk_tokens": 256,
            "sequence_length": 1024,
            "weight_bytes": 400_000_000,
            "vram_ceiling_bytes": 900_000_000,
            "prefill_max_gemm_us": 250.0,
            "prefill_workspace_bytes": 1_000_000,
            "prefill_parked_activation_bytes": 500_000,
            "decode_max_gemv_us": 120.0,
            "attention_fetch_compute_us": 180.0,
            "reduction_overhead_us": 45.0,
            "pcie_exposed_us": 60.0,
            "survival_vram_bytes": 498_500_000,
            "decode_runway_bytes": 2_048,
            "decode_runway_tokens": 1,
            "ttft_ms": 3.5,
            "tpot_ms_vram": 0.9,
            "tpot_ms_pcie_async": 1.1,
            "trace_sha256": "a" * 64,
            "status": "success",
        }
    ]


def _build_model_constants_rows() -> list[dict[str, object]]:
    return [
        {
            "model_id": "facebook/opt-125m",
            "kv_bytes_per_token_all_layers": 36_864,
        }
    ]


def _build_prefill_event_rows() -> list[dict[str, object]]:
    return [
        {
            "model_id": "facebook/opt-125m",
            "chunk_tokens": 256,
            "op_type": "gemm",
            "op_name": "q_proj",
            "sm_ai_partition": 100,
            "timed_iteration": 0,
            "duration_us": 120.0,
            "baseline_vram_bytes": 100,
            "peak_vram_bytes": 160,
            "dynamic_workspace_bytes": 60,
            "output_bytes": 128,
        }
    ]


def _build_decode_event_rows() -> list[dict[str, object]]:
    return [
        {
            "model_id": "facebook/opt-125m",
            "sequence_length": 1024,
            "block_size": 256,
            "op_type": "gemv",
            "op_name": "q_proj",
            "sm_ai_partition": 100,
            "timed_iteration": 0,
            "duration_us": 80.0,
            "baseline_vram_bytes": 100,
            "peak_vram_bytes": 180,
            "dynamic_workspace_bytes": 80,
            "output_bytes": 64,
        }
    ]


def _write_plot_inputs(
    run_root: Path,
    *,
    results_rows: list[dict[str, object]],
    timeline_rows: list[dict[str, object]],
    trace_rows: list[dict[str, object]],
) -> None:
    derived_root = run_root / "derived"
    _write_csv(
        derived_root / simulator.SIMULATION_RESULTS_FILENAME,
        fieldnames=list(simulator.SIMULATION_RESULTS_COLUMNS),
        rows=results_rows,
    )
    _write_csv(
        derived_root / simulator.SCHEDULE_TIMELINE_FILENAME,
        fieldnames=list(simulator.SCHEDULE_TIMELINE_COLUMNS),
        rows=timeline_rows,
    )
    _write_csv(
        derived_root / trace_contract.NORMALIZED_TRACE_FILENAME,
        fieldnames=list(trace_contract.NORMALIZED_TRACE_HEADERS),
        rows=trace_rows,
    )
    _write_csv(
        derived_root / "model_constants.csv",
        fieldnames=["model_id", "kv_bytes_per_token_all_layers"],
        rows=_build_model_constants_rows(),
    )
    _write_csv(
        run_root / "raw" / "prefill_events.csv",
        fieldnames=list(_build_prefill_event_rows()[0].keys()),
        rows=_build_prefill_event_rows(),
    )
    _write_csv(
        run_root / "raw" / "decode_events.csv",
        fieldnames=list(_build_decode_event_rows()[0].keys()),
        rows=_build_decode_event_rows(),
    )


def test_generate_profiling_plots_rejects_empty_results_table(tmp_path: Path) -> None:
    run_root = tmp_path / "empty-results"
    _write_plot_inputs(
        run_root,
        results_rows=[],
        timeline_rows=[],
        trace_rows=_build_minimal_trace_rows(),
    )

    with pytest.raises(
        PlotGenerationError,
        match="Results CSV must contain at least one row",
    ):
        generate_profiling_plots(run_root=run_root)


def test_generate_profiling_plots_rejects_exemplar_without_timeline_rows(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "missing-exemplar-timeline"
    _write_plot_inputs(
        run_root,
        results_rows=_build_single_success_result_row(),
        timeline_rows=[],
        trace_rows=_build_minimal_trace_rows(),
    )

    with pytest.raises(
        PlotGenerationError,
        match="schedule_timeline.csv does not contain rows for the deterministic exemplar configuration",
    ):
        generate_profiling_plots(run_root=run_root)

    assert not list((run_root / "plots").glob("*.png"))
