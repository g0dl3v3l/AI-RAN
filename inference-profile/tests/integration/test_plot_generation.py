from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd
import pytest

from inference_profile import simulator, trace_contract
from inference_profile.plots import (
    INTERACTIVE_RAN_TRACE_FILENAME,
    PLOT_FILENAMES,
    PLOT_SELECTION_FILENAME,
    _build_prefill_vram_composition_frame,
    generate_profiling_plots,
)

MODEL_IDS = [
    "facebook/opt-125m",
    "facebook/opt-350m",
    "facebook/opt-1.3b",
    "facebook/opt-2.7b",
    "facebook/opt-6.7b",
]
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
EXPECTED_PLOT5_CHUNKS = {
    "facebook/opt-125m": 512,
    "facebook/opt-350m": 512,
    "facebook/opt-1.3b": 1024,
    "facebook/opt-2.7b": 1024,
    "facebook/opt-6.7b": 1024,
}
EXPECTED_OPERATION_PLOT_NAME = "06_operation_level_microarchitecture_summary.png"


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


def _build_results_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for model_index, model_id in enumerate(MODEL_IDS):
        for chunk_tokens in (256, 512, 1024):
            for sequence_length in (1024, 2048, 4096, 8192):
                status = "success"
                if (
                    model_id
                    in {
                        "facebook/opt-125m",
                        "facebook/opt-350m",
                    }
                    and chunk_tokens == 1024
                ):
                    status = "decode_trace_fit_failed_vram"

                weight_bytes = 2_000_000_000 + (model_index * 900_000_000)
                prefill_workspace_bytes = chunk_tokens * (model_index + 2) * 700_000
                prefill_parked_activation_bytes = (
                    chunk_tokens * (model_index + 1) * 350_000
                )
                vram_ceiling_bytes = (
                    weight_bytes
                    + prefill_workspace_bytes
                    + prefill_parked_activation_bytes
                    + 1_800_000_000
                )
                decode_runway_tokens = max(
                    0,
                    11_000
                    - (model_index * 1_200)
                    - (sequence_length // 2)
                    + (chunk_tokens // 2),
                )
                tpot_ms_vram = round(
                    0.8
                    + (model_index * 0.25)
                    + (sequence_length / 8192.0) * 1.2
                    + (chunk_tokens / 2048.0) * 0.3,
                    4,
                )
                if model_id == "facebook/opt-6.7b" and chunk_tokens in {512, 1024}:
                    ttft_ms: float | None = 10.0
                else:
                    ttft_ms = round(
                        14.0 + (model_index * 1.5) - (chunk_tokens / 2048.0), 4
                    )

                if status != "success":
                    ttft_ms = None
                    tpot_ms_vram = None
                    tpot_ms_pcie_async = None
                    decode_runway_tokens = 0
                else:
                    tpot_ms_pcie_async = round(tpot_ms_vram + 0.28, 4)

                rows.append(
                    {
                        "model_id": model_id,
                        "chunk_tokens": chunk_tokens,
                        "sequence_length": sequence_length,
                        "weight_bytes": weight_bytes,
                        "vram_ceiling_bytes": vram_ceiling_bytes,
                        "prefill_max_gemm_us": round(
                            250.0 + (chunk_tokens * (model_index + 1) * 0.9),
                            4,
                        ),
                        "prefill_workspace_bytes": prefill_workspace_bytes,
                        "prefill_parked_activation_bytes": prefill_parked_activation_bytes,
                        "decode_max_gemv_us": round(120.0 + (model_index * 15.0), 4),
                        "attention_fetch_compute_us": round(
                            180.0 + (sequence_length * 0.18) + (model_index * 20.0),
                            4,
                        ),
                        "reduction_overhead_us": round(45.0 + (model_index * 5.0), 4),
                        "pcie_exposed_us": round(60.0 + (sequence_length * 0.12), 4),
                        "survival_vram_bytes": (
                            vram_ceiling_bytes
                            - weight_bytes
                            - prefill_workspace_bytes
                            - prefill_parked_activation_bytes
                        ),
                        "decode_runway_bytes": decode_runway_tokens * 2048,
                        "decode_runway_tokens": decode_runway_tokens,
                        "ttft_ms": ttft_ms,
                        "tpot_ms_vram": tpot_ms_vram,
                        "tpot_ms_pcie_async": tpot_ms_pcie_async,
                        "trace_sha256": "a" * 64,
                        "status": status,
                    }
                )
    return rows


def _build_timeline_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

    def add_row(
        *,
        phase: str,
        mode: str,
        family: str,
        chunk_index: int | None,
        atom_index: int,
        trace_interval_index: int,
        start_time_ms: float,
        end_time_ms: float,
    ) -> None:
        rows.append(
            {
                "model_id": "facebook/opt-6.7b",
                "chunk_tokens": 1024,
                "sequence_length": 8192,
                "phase": phase,
                "mode": mode,
                "family": family,
                "chunk_index": chunk_index,
                "token_index": 0,
                "layer_index": 0,
                "atom_index": atom_index,
                "trace_interval_index": trace_interval_index,
                "start_time_ms": start_time_ms,
                "end_time_ms": end_time_ms,
                "duration_ms": round(end_time_ms - start_time_ms, 6),
            }
        )

    add_row(
        phase="prefill",
        mode="prefill",
        family="prefill_gemm",
        chunk_index=0,
        atom_index=0,
        trace_interval_index=1,
        start_time_ms=0.20,
        end_time_ms=0.95,
    )
    add_row(
        phase="prefill",
        mode="prefill",
        family="prefill_gemm",
        chunk_index=1,
        atom_index=0,
        trace_interval_index=3,
        start_time_ms=1.20,
        end_time_ms=2.00,
    )
    add_row(
        phase="decode",
        mode="vram",
        family="decode_gemv",
        chunk_index=None,
        atom_index=0,
        trace_interval_index=5,
        start_time_ms=2.20,
        end_time_ms=2.55,
    )
    add_row(
        phase="decode",
        mode="vram",
        family="decode_gemv",
        chunk_index=None,
        atom_index=1,
        trace_interval_index=7,
        start_time_ms=3.20,
        end_time_ms=3.55,
    )
    add_row(
        phase="decode",
        mode="pcie_async",
        family="pcie_exposed_transfer",
        chunk_index=None,
        atom_index=0,
        trace_interval_index=5,
        start_time_ms=2.20,
        end_time_ms=2.65,
    )
    add_row(
        phase="decode",
        mode="pcie_async",
        family="pcie_exposed_transfer",
        chunk_index=None,
        atom_index=1,
        trace_interval_index=7,
        start_time_ms=3.20,
        end_time_ms=3.78,
    )
    return rows


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
            "slot_duration_ms": 300.0,
            "source_schema": trace_contract.SOURCE_SCHEMA_A,
        },
        {
            "time_ms": 300.2,
            "sm_utilization": 100.0,
            "slot_duration_ms": 0.2,
            "source_schema": trace_contract.SOURCE_SCHEMA_A,
        },
        {
            "time_ms": 300.4,
            "sm_utilization": 0.0,
            "slot_duration_ms": 300.0,
            "source_schema": trace_contract.SOURCE_SCHEMA_A,
        },
        {
            "time_ms": 600.4,
            "sm_utilization": 100.0,
            "slot_duration_ms": 0.2,
            "source_schema": trace_contract.SOURCE_SCHEMA_A,
        },
        {
            "time_ms": 600.6,
            "sm_utilization": 0.0,
            "slot_duration_ms": 300.0,
            "source_schema": trace_contract.SOURCE_SCHEMA_A,
        },
        {
            "time_ms": 900.6,
            "sm_utilization": 100.0,
            "slot_duration_ms": 0.2,
            "source_schema": trace_contract.SOURCE_SCHEMA_A,
        },
        {
            "time_ms": 900.8,
            "sm_utilization": 0.0,
            "slot_duration_ms": 300.0,
            "source_schema": trace_contract.SOURCE_SCHEMA_A,
        },
    ]


def _build_model_constants_rows() -> list[dict[str, object]]:
    return [
        {
            "model_id": model_id,
            "kv_bytes_per_token_all_layers": (model_index + 1) * 2_048,
        }
        for model_index, model_id in enumerate(MODEL_IDS)
    ]


def _build_prefill_event_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for partition in (40, 80):
        rows.extend(
            [
                {
                    "model_id": "facebook/opt-125m",
                    "chunk_tokens": 512,
                    "op_type": "gemm",
                    "op_name": "q_proj",
                    "sm_ai_partition": partition,
                    "timed_iteration": 0,
                    "duration_us": 120.0 + partition,
                    "baseline_vram_bytes": 1_000,
                    "peak_vram_bytes": 2_000,
                    "dynamic_workspace_bytes": 1_000,
                    "output_bytes": 512,
                },
                {
                    "model_id": "facebook/opt-125m",
                    "chunk_tokens": 512,
                    "op_type": "gemm",
                    "op_name": "k_proj",
                    "sm_ai_partition": partition,
                    "timed_iteration": 0,
                    "duration_us": 125.0 + partition,
                    "baseline_vram_bytes": 1_000,
                    "peak_vram_bytes": 2_100,
                    "dynamic_workspace_bytes": 1_100,
                    "output_bytes": 512,
                },
                {
                    "model_id": "facebook/opt-125m",
                    "chunk_tokens": 512,
                    "op_type": "gemm",
                    "op_name": "v_proj",
                    "sm_ai_partition": partition,
                    "timed_iteration": 0,
                    "duration_us": 130.0 + partition,
                    "baseline_vram_bytes": 1_000,
                    "peak_vram_bytes": 2_200,
                    "dynamic_workspace_bytes": 1_200,
                    "output_bytes": 512,
                },
                {
                    "model_id": "facebook/opt-125m",
                    "chunk_tokens": 512,
                    "op_type": "gemm",
                    "op_name": "out_proj",
                    "sm_ai_partition": partition,
                    "timed_iteration": 0,
                    "duration_us": 90.0 + partition,
                    "baseline_vram_bytes": 1_000,
                    "peak_vram_bytes": 1_600,
                    "dynamic_workspace_bytes": 600,
                    "output_bytes": 512,
                },
                {
                    "model_id": "facebook/opt-125m",
                    "chunk_tokens": 512,
                    "op_type": "gemm",
                    "op_name": "fc1",
                    "sm_ai_partition": partition,
                    "timed_iteration": 0,
                    "duration_us": 210.0 + partition,
                    "baseline_vram_bytes": 1_000,
                    "peak_vram_bytes": 2_500,
                    "dynamic_workspace_bytes": 1_500,
                    "output_bytes": 1024,
                },
                {
                    "model_id": "facebook/opt-125m",
                    "chunk_tokens": 512,
                    "op_type": "gemm",
                    "op_name": "fc2",
                    "sm_ai_partition": partition,
                    "timed_iteration": 0,
                    "duration_us": 160.0 + partition,
                    "baseline_vram_bytes": 1_000,
                    "peak_vram_bytes": 2_000,
                    "dynamic_workspace_bytes": 1_000,
                    "output_bytes": 512,
                },
                {
                    "model_id": "facebook/opt-125m",
                    "chunk_tokens": 512,
                    "op_type": "attention",
                    "op_name": "attention",
                    "sm_ai_partition": partition,
                    "timed_iteration": 0,
                    "duration_us": 300.0 + partition,
                    "baseline_vram_bytes": 1_000,
                    "peak_vram_bytes": 2_800,
                    "dynamic_workspace_bytes": 1_800,
                    "output_bytes": 1024,
                },
            ]
        )
    return rows


def _build_decode_event_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for partition in (40, 80):
        rows.extend(
            [
                {
                    "model_id": "facebook/opt-125m",
                    "sequence_length": 1024,
                    "block_size": 512,
                    "op_type": "gemv",
                    "op_name": "q_proj",
                    "sm_ai_partition": partition,
                    "timed_iteration": 0,
                    "duration_us": 60.0 + partition,
                    "baseline_vram_bytes": 500,
                    "peak_vram_bytes": 900,
                    "dynamic_workspace_bytes": 400,
                    "output_bytes": 128,
                },
                {
                    "model_id": "facebook/opt-125m",
                    "sequence_length": 1024,
                    "block_size": 512,
                    "op_type": "gemv",
                    "op_name": "k_proj",
                    "sm_ai_partition": partition,
                    "timed_iteration": 0,
                    "duration_us": 61.0 + partition,
                    "baseline_vram_bytes": 500,
                    "peak_vram_bytes": 920,
                    "dynamic_workspace_bytes": 420,
                    "output_bytes": 128,
                },
                {
                    "model_id": "facebook/opt-125m",
                    "sequence_length": 1024,
                    "block_size": 512,
                    "op_type": "gemv",
                    "op_name": "v_proj",
                    "sm_ai_partition": partition,
                    "timed_iteration": 0,
                    "duration_us": 62.0 + partition,
                    "baseline_vram_bytes": 500,
                    "peak_vram_bytes": 930,
                    "dynamic_workspace_bytes": 430,
                    "output_bytes": 128,
                },
                {
                    "model_id": "facebook/opt-125m",
                    "sequence_length": 1024,
                    "block_size": 512,
                    "op_type": "gemv",
                    "op_name": "out_proj",
                    "sm_ai_partition": partition,
                    "timed_iteration": 0,
                    "duration_us": 70.0 + partition,
                    "baseline_vram_bytes": 500,
                    "peak_vram_bytes": 850,
                    "dynamic_workspace_bytes": 350,
                    "output_bytes": 128,
                },
                {
                    "model_id": "facebook/opt-125m",
                    "sequence_length": 1024,
                    "block_size": 512,
                    "op_type": "gemv",
                    "op_name": "fc1",
                    "sm_ai_partition": partition,
                    "timed_iteration": 0,
                    "duration_us": 95.0 + partition,
                    "baseline_vram_bytes": 500,
                    "peak_vram_bytes": 980,
                    "dynamic_workspace_bytes": 480,
                    "output_bytes": 256,
                },
                {
                    "model_id": "facebook/opt-125m",
                    "sequence_length": 1024,
                    "block_size": 512,
                    "op_type": "gemv",
                    "op_name": "fc2",
                    "sm_ai_partition": partition,
                    "timed_iteration": 0,
                    "duration_us": 88.0 + partition,
                    "baseline_vram_bytes": 500,
                    "peak_vram_bytes": 910,
                    "dynamic_workspace_bytes": 410,
                    "output_bytes": 128,
                },
                {
                    "model_id": "facebook/opt-125m",
                    "sequence_length": 1024,
                    "block_size": 512,
                    "op_type": "attention_fetch_compute",
                    "op_name": "",
                    "sm_ai_partition": partition,
                    "timed_iteration": 0,
                    "duration_us": 80.0 + partition,
                    "baseline_vram_bytes": 500,
                    "peak_vram_bytes": 1_000,
                    "dynamic_workspace_bytes": 500,
                    "output_bytes": 128,
                },
                {
                    "model_id": "facebook/opt-125m",
                    "sequence_length": 1024,
                    "block_size": 512,
                    "op_type": "reduction_overhead",
                    "op_name": "",
                    "sm_ai_partition": partition,
                    "timed_iteration": 0,
                    "duration_us": 25.0 + partition,
                    "baseline_vram_bytes": 500,
                    "peak_vram_bytes": 760,
                    "dynamic_workspace_bytes": 260,
                    "output_bytes": 64,
                },
            ]
        )
    return rows


@pytest.fixture
def plot_run_root(tmp_path: Path) -> Path:
    run_root = tmp_path / "plot-run"
    derived_root = run_root / "derived"
    _write_csv(
        derived_root / simulator.SIMULATION_RESULTS_FILENAME,
        fieldnames=list(simulator.SIMULATION_RESULTS_COLUMNS),
        rows=_build_results_rows(),
    )
    _write_csv(
        derived_root / simulator.SCHEDULE_TIMELINE_FILENAME,
        fieldnames=list(simulator.SCHEDULE_TIMELINE_COLUMNS),
        rows=_build_timeline_rows(),
    )
    _write_csv(
        derived_root / trace_contract.NORMALIZED_TRACE_FILENAME,
        fieldnames=list(trace_contract.NORMALIZED_TRACE_HEADERS),
        rows=_build_trace_rows(),
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

    plots_root = run_root / "plots"
    plots_root.mkdir(parents=True, exist_ok=True)
    (plots_root / "legacy.png").write_bytes(b"legacy")
    return run_root


def test_generate_profiling_plots_creates_all_required_pngs_and_selection_metadata(
    plot_run_root: Path,
) -> None:
    plot_paths = generate_profiling_plots(run_root=plot_run_root)

    assert len(plot_paths) == 6
    assert list(plot_paths) == [Path(filename).stem for filename in PLOT_FILENAMES]

    plots_root = plot_run_root / "plots"
    generated_pngs = sorted(path.name for path in plots_root.glob("*.png"))
    assert generated_pngs == sorted(PLOT_FILENAMES)
    for filename in PLOT_FILENAMES:
        plot_path = plots_root / filename
        assert plot_path.exists()
        assert plot_path.stat().st_size > 0
        assert plot_path.read_bytes()[: len(PNG_SIGNATURE)] == PNG_SIGNATURE
        assert plot_paths[plot_path.stem] == plot_path

    selection_path = plot_run_root / "derived" / PLOT_SELECTION_FILENAME
    assert selection_path.exists()
    packed_timeline_path = (
        plot_run_root / "derived" / simulator.PACKED_EXEMPLAR_TIMELINE_FILENAME
    )
    assert packed_timeline_path.exists()
    packed_timeline_df = pd.read_csv(packed_timeline_path)
    assert list(packed_timeline_df.columns) == list(
        simulator.PACKED_EXEMPLAR_TIMELINE_COLUMNS
    )
    assert set(packed_timeline_df["schedule_variant"]) == {"vram", "pcie_async"}
    assert packed_timeline_df["task_id"].min() == 0
    interactive_path = plots_root / INTERACTIVE_RAN_TRACE_FILENAME
    assert interactive_path.exists()
    assert interactive_path.stat().st_size > 0
    interactive_html = interactive_path.read_text(encoding="utf-8")
    assert "plotly" in interactive_html.lower()
    assert "Relative trace time (ms)" in interactive_html
    assert "Packed exemplar task ID" in interactive_html
    payload = json.loads(selection_path.read_text(encoding="utf-8"))

    exemplar = payload["plot_01_exemplar"]
    assert exemplar == {
        "model_id": "facebook/opt-6.7b",
        "model_label": "OPT-6.7B",
        "model_size_rank": 5.0,
        "chunk_tokens": 1024,
        "sequence_length": 8192,
        "ttft_ms": 10.0,
    }

    plot5_selection = {
        entry["model_id"]: entry["selected_chunk_tokens"]
        for entry in payload["plot_05_largest_successful_chunk_by_model"]
    }
    assert plot5_selection == EXPECTED_PLOT5_CHUNKS
    assert (
        payload["plot_01_packed_timeline"]["source"]
        == simulator.PACKED_EXEMPLAR_TIMELINE_FILENAME
    )
    assert EXPECTED_OPERATION_PLOT_NAME in generated_pngs


def test_prefill_vram_composition_frame_includes_bulk_kv_cache() -> None:
    composition_df = _build_prefill_vram_composition_frame(
        results_df=pd.DataFrame(_build_results_rows()),
        model_constants_df=pd.DataFrame(_build_model_constants_rows()),
    )

    row = composition_df[
        (composition_df["model_id"] == "facebook/opt-2.7b")
        & (composition_df["chunk_tokens"] == 512)
    ].iloc[0]

    assert int(row["weight_bytes"]) > 0
    assert int(row["prefill_workspace_bytes"]) > 0
    assert int(row["prefill_parked_activation_bytes"]) > 0
    assert "bulk_kv_cache_bytes" in composition_df.columns
    assert float(row["bulk_kv_cache_bytes"]) > 0.0
