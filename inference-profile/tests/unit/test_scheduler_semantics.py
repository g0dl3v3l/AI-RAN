from __future__ import annotations

import csv
from hashlib import sha256
from pathlib import Path
from typing import cast

import pandas as pd
import pytest

from inference_profile import experiments, simulator, trace_contract


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


def _write_scheduler_inputs(run_root: Path, *, vram_ceiling_bytes: int) -> None:
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
                "num_hidden_layers": 1,
                "hidden_size": 10,
                "num_attention_heads": 1,
                "ffn_dim": 40,
                "layer_index": 0,
                "layer_weight_bytes": 400,
                "total_weight_bytes_fp16": 400,
                "vram_ceiling_bytes": vram_ceiling_bytes,
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
                "chunk_tokens": 2048,
                "prefill_max_gemm_us": 500.0,
                "prefill_workspace_bytes": 80,
                "prefill_parked_activation_bytes": 100,
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
                "sequence_length": 4096,
                "block_size": 2048,
                "decode_max_gemv_us": 250.0,
                "attention_fetch_compute_us": 500.0,
                "reduction_overhead_us": 250.0,
                "decode_workspace_bytes": 50,
                "decode_parked_activation_bytes": 40,
            }
        ],
    )
    _write_csv(
        derived_root / "pcie_summary.csv",
        fieldnames=["model_id", "block_size", "exposed_transfer_us"],
        rows=[
            {
                "model_id": "facebook/opt-125m",
                "block_size": 2048,
                "exposed_transfer_us": 250.0,
            }
        ],
    )
    _write_csv(
        derived_root / trace_contract.NORMALIZED_TRACE_FILENAME,
        fieldnames=list(trace_contract.NORMALIZED_TRACE_HEADERS),
        rows=[
            {
                "time_ms": 0.0,
                "sm_utilization": 100.0,
                "slot_duration_ms": 1.0,
                "source_schema": trace_contract.SOURCE_SCHEMA_A,
            },
            {
                "time_ms": 1.0,
                "sm_utilization": 0.0,
                "slot_duration_ms": 2.0,
                "source_schema": trace_contract.SOURCE_SCHEMA_A,
            },
            {
                "time_ms": 3.0,
                "sm_utilization": 100.0,
                "slot_duration_ms": 1.0,
                "source_schema": trace_contract.SOURCE_SCHEMA_A,
            },
            {
                "time_ms": 4.0,
                "sm_utilization": 0.0,
                "slot_duration_ms": 4.0,
                "source_schema": trace_contract.SOURCE_SCHEMA_A,
            },
            {
                "time_ms": 8.0,
                "sm_utilization": 100.0,
                "slot_duration_ms": 0.5,
                "source_schema": trace_contract.SOURCE_SCHEMA_A,
            },
            {
                "time_ms": 8.5,
                "sm_utilization": 0.0,
                "slot_duration_ms": 4.0,
                "source_schema": trace_contract.SOURCE_SCHEMA_A,
            },
        ],
    )


def _write_revised_scheduler_inputs(run_root: Path) -> None:
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
                "num_hidden_layers": 1,
                "hidden_size": 10,
                "num_attention_heads": 1,
                "ffn_dim": 40,
                "layer_index": 0,
                "layer_weight_bytes": 400,
                "total_weight_bytes_fp16": 400,
                "vram_ceiling_bytes": 2_000,
            }
        ],
    )

    _write_csv(
        derived_root / "prefill_summary.csv",
        fieldnames=[
            "model_id",
            "chunk_tokens",
            "sm_ai_partition",
            "prefill_max_gemm_us",
            "prefill_workspace_bytes",
            "prefill_parked_activation_bytes",
            "telemetry_tier",
            "telemetry_provider",
            "telemetry_status",
            "nvml_available",
        ],
        rows=[
            {
                "model_id": "facebook/opt-125m",
                "chunk_tokens": 2048,
                "sm_ai_partition": partition,
                "prefill_max_gemm_us": gemm_us,
                "prefill_workspace_bytes": workspace_bytes,
                "prefill_parked_activation_bytes": parked_bytes,
                "telemetry_tier": experiments.RAN_DGXSPARK_V1_TELEMETRY_TIER,
                "telemetry_provider": "nvml",
                "telemetry_status": "ok",
                "nvml_available": True,
            }
            for partition, gemm_us, workspace_bytes, parked_bytes in (
                (8, 800.0, 140, 260),
                (16, 700.0, 130, 240),
                (24, 600.0, 120, 220),
                (32, 500.0, 110, 200),
            )
        ],
    )

    decode_metrics = {
        "vram": {
            8: (400.0, 600.0, 300.0, 120, 80),
            16: (350.0, 550.0, 280.0, 110, 70),
            24: (300.0, 500.0, 260.0, 100, 60),
            32: (250.0, 450.0, 250.0, 90, 50),
        },
        "pcie_async": {
            8: (450.0, 650.0, 320.0, 140, 90),
            16: (400.0, 600.0, 300.0, 130, 80),
            24: (350.0, 550.0, 280.0, 120, 70),
            32: (300.0, 500.0, 260.0, 110, 60),
        },
    }
    decode_rows: list[dict[str, object]] = []
    for mode, metrics_by_partition in decode_metrics.items():
        for partition, (
            gemv_us,
            attention_us,
            reduction_us,
            workspace_bytes,
            parked_bytes,
        ) in metrics_by_partition.items():
            decode_rows.append(
                {
                    "model_id": "facebook/opt-125m",
                    "sequence_length": 4096,
                    "block_size": 2048,
                    "sm_ai_partition": partition,
                    "decode_mode": mode,
                    "decode_max_gemv_us": gemv_us,
                    "attention_fetch_compute_us": attention_us,
                    "reduction_overhead_us": reduction_us,
                    "decode_workspace_bytes": workspace_bytes,
                    "decode_parked_activation_bytes": parked_bytes,
                    "telemetry_tier": experiments.RAN_DGXSPARK_V1_TELEMETRY_TIER,
                    "telemetry_provider": "nvml",
                    "telemetry_status": "ok",
                    "nvml_available": True,
                }
            )
    _write_csv(
        derived_root / "decode_summary.csv",
        fieldnames=[
            "model_id",
            "sequence_length",
            "block_size",
            "sm_ai_partition",
            "decode_mode",
            "decode_max_gemv_us",
            "attention_fetch_compute_us",
            "reduction_overhead_us",
            "decode_workspace_bytes",
            "decode_parked_activation_bytes",
            "telemetry_tier",
            "telemetry_provider",
            "telemetry_status",
            "nvml_available",
        ],
        rows=decode_rows,
    )

    _write_csv(
        derived_root / "pcie_summary.csv",
        fieldnames=[
            "model_id",
            "block_size",
            "kv_block_bytes",
            "transfer_only_us",
            "overlap_total_us",
            "dummy_compute_us",
            "exposed_transfer_us",
            "effective_gbps",
            "overlap_status",
            "telemetry_tier",
            "telemetry_provider",
            "telemetry_status",
            "nvml_available",
        ],
        rows=[
            {
                "model_id": "facebook/opt-125m",
                "block_size": 2048,
                "kv_block_bytes": 2048,
                "transfer_only_us": 125.0,
                "overlap_total_us": 100.0,
                "dummy_compute_us": 80.0,
                "exposed_transfer_us": 75.0,
                "effective_gbps": 0.5,
                "overlap_status": "measured",
                "telemetry_tier": experiments.RAN_DGXSPARK_V1_TELEMETRY_TIER,
                "telemetry_provider": "nvml",
                "telemetry_status": "ok",
                "nvml_available": True,
            }
        ],
    )

    _write_csv(
        derived_root / trace_contract.NORMALIZED_TRACE_FILENAME,
        fieldnames=list(trace_contract.NORMALIZED_TRACE_HEADERS),
        rows=[
            {
                "time_ms": 0.0,
                "sm_utilization": 0.0,
                "slot_duration_ms": 20.0,
                "source_schema": trace_contract.SOURCE_SCHEMA_B,
            }
        ],
    )


def _row_fits_idle_gap(row: pd.Series) -> bool:
    start_time_ms = float(cast(float | int | str, row["start_time_ms"]))
    end_time_ms = float(cast(float | int | str, row["end_time_ms"]))
    return (
        (1.0 <= start_time_ms and end_time_ms <= 3.0)
        or (4.0 <= start_time_ms and end_time_ms <= 8.0)
        or (8.5 <= start_time_ms and end_time_ms <= 12.5)
    )


def test_run_deterministic_simulation_greedily_fits_prefill_and_decode_atoms(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "scheduler-semantics"
    _write_scheduler_inputs(run_root, vram_ceiling_bytes=1_000)

    result = simulator.run_deterministic_simulation(run_root=run_root)

    results_df = pd.read_csv(result.results_path)
    timeline_df = pd.read_csv(result.timeline_path)

    assert list(results_df.columns) == [
        "model_id",
        "chunk_tokens",
        "sequence_length",
        "weight_bytes",
        "vram_ceiling_bytes",
        "prefill_max_gemm_us",
        "prefill_workspace_bytes",
        "prefill_parked_activation_bytes",
        "decode_max_gemv_us",
        "attention_fetch_compute_us",
        "reduction_overhead_us",
        "pcie_exposed_us",
        "survival_vram_bytes",
        "decode_runway_bytes",
        "decode_runway_tokens",
        "ttft_ms",
        "tpot_ms_vram",
        "tpot_ms_pcie_async",
        "trace_sha256",
        "status",
    ]
    assert len(results_df) == 1
    row = results_df.iloc[0]
    assert row["status"] == "success"
    assert row["weight_bytes"] == 400
    assert row["vram_ceiling_bytes"] == 1_000
    assert row["survival_vram_bytes"] == 420
    assert row["decode_runway_bytes"] == 0
    assert row["decode_runway_tokens"] == 0
    # ttft_ms is latency from first prefill start (1.0) to prefill completion (8.0) -> 7.0
    assert row["ttft_ms"] == pytest.approx(7.0)
    assert row["tpot_ms_vram"] == pytest.approx(2.75)
    assert row["tpot_ms_pcie_async"] == pytest.approx(3.25)
    assert (
        row["trace_sha256"]
        == sha256(
            (
                run_root / "derived" / trace_contract.NORMALIZED_TRACE_FILENAME
            ).read_bytes()
        ).hexdigest()
    )

    assert len(timeline_df) == 30
    assert timeline_df["phase"].tolist().count("prefill") == 12
    assert timeline_df["mode"].tolist().count("vram") == 8
    assert timeline_df["mode"].tolist().count("pcie_async") == 10
    assert all(_row_fits_idle_gap(row) for _, row in timeline_df.iterrows())

    prefill_df = timeline_df[timeline_df["phase"] == "prefill"].reset_index(drop=True)
    assert prefill_df.iloc[0]["start_time_ms"] == pytest.approx(1.0)
    assert prefill_df.iloc[3]["end_time_ms"] == pytest.approx(3.0)
    assert prefill_df.iloc[4]["start_time_ms"] == pytest.approx(4.0)
    assert prefill_df.iloc[-1]["end_time_ms"] == pytest.approx(8.0)

    decode_vram_df = timeline_df[
        (timeline_df["phase"] == "decode") & (timeline_df["mode"] == "vram")
    ].reset_index(drop=True)
    assert decode_vram_df.iloc[0]["start_time_ms"] == pytest.approx(8.5)
    assert decode_vram_df.iloc[-1]["end_time_ms"] == pytest.approx(10.75)
    assert set(decode_vram_df["family"]) == {
        "decode_gemv",
        "attention_fetch_compute",
        "reduction_overhead",
    }

    decode_async_df = timeline_df[
        (timeline_df["phase"] == "decode") & (timeline_df["mode"] == "pcie_async")
    ].reset_index(drop=True)
    assert decode_async_df.iloc[0]["start_time_ms"] == pytest.approx(8.5)
    assert decode_async_df.iloc[-1]["end_time_ms"] == pytest.approx(11.25)
    assert decode_async_df["family"].tolist().count("pcie_exposed_transfer") == 2


def test_write_packed_exemplar_timeline_packs_repeated_tasks_with_task_ids(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "packed-exemplar"
    _write_scheduler_inputs(run_root, vram_ceiling_bytes=1_000)
    _write_csv(
        run_root / "derived" / trace_contract.NORMALIZED_TRACE_FILENAME,
        fieldnames=list(trace_contract.NORMALIZED_TRACE_HEADERS),
        rows=[
            {
                "time_ms": 0.0,
                "sm_utilization": 0.0,
                "slot_duration_ms": 40.0,
                "source_schema": trace_contract.SOURCE_SCHEMA_A,
            }
        ],
    )

    simulation_result = simulator.run_deterministic_simulation(run_root=run_root)
    results_df = pd.read_csv(simulation_result.results_path)
    timeline_df = pd.read_csv(simulation_result.timeline_path)

    packed_path = simulator.write_packed_exemplar_timeline(
        run_root=run_root,
        exemplar_result_row=results_df.iloc[0].to_dict(),
        exemplar_timeline_rows=tuple(timeline_df.to_dict(orient="records")),
    )

    packed_df = pd.read_csv(packed_path)

    assert (
        packed_path
        == run_root / "derived" / simulator.PACKED_EXEMPLAR_TIMELINE_FILENAME
    )
    assert list(packed_df.columns) == list(simulator.PACKED_EXEMPLAR_TIMELINE_COLUMNS)
    assert set(packed_df["schedule_variant"]) == {"vram", "pcie_async"}
    assert set(
        packed_df[packed_df["schedule_variant"] == "vram"]["task_id"].astype(int)
    ) == {0, 1, 2, 3}
    assert set(
        packed_df[packed_df["schedule_variant"] == "pcie_async"]["task_id"].astype(int)
    ) == {0, 1, 2, 3}
    assert packed_df.groupby(["schedule_variant", "task_id"]).size().to_dict() == {
        ("vram", 0): 20,
        ("vram", 1): 20,
        ("vram", 2): 20,
        ("vram", 3): 20,
        ("pcie_async", 0): 22,
        ("pcie_async", 1): 22,
        ("pcie_async", 2): 22,
        ("pcie_async", 3): 22,
    }


def test_run_deterministic_simulation_dispatches_to_revised_scheduler(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "revised-scheduler-semantics"
    _write_revised_scheduler_inputs(run_root)

    result = simulator.run_deterministic_simulation(
        run_root=run_root,
        experiment_type=experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE,
    )

    results_df = pd.read_csv(result.results_path)
    timeline_df = pd.read_csv(result.timeline_path)
    packed_df = pd.read_csv(cast(Path, result.packed_timeline_path))

    assert list(results_df.columns) == list(
        simulator.REVISED_SIMULATION_RESULTS_COLUMNS
    )
    assert list(timeline_df.columns) == list(
        simulator.REVISED_SCHEDULE_TIMELINE_COLUMNS
    )
    assert list(packed_df.columns) == list(
        simulator.REVISED_PACKED_EXEMPLAR_TIMELINE_COLUMNS
    )

    row = results_df.iloc[0]
    assert row["status"] == "success"
    assert row["schema_version"] == experiments.RAN_DGXSPARK_V1_SCHEMA_VERSION
    assert row["experiment_type"] == experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE
    assert row["scheduler"] == experiments.RAN_DGXSPARK_V1_SCHEDULER
    assert row["sm_ai_partitions_profiled"] == "8|16|24|32"
    assert row["trace_sm_ran_tiers"] == "8|16|24|32|40|48"
    assert row["trace_interval_count"] == 1
    assert row["trace_intervals_with_ai_budget"] == 1

    first_timeline_row = timeline_df.iloc[0]
    assert (
        first_timeline_row["schema_version"]
        == experiments.RAN_DGXSPARK_V1_SCHEMA_VERSION
    )
    assert (
        first_timeline_row["experiment_type"]
        == experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE
    )
    assert first_timeline_row["scheduler"] == experiments.RAN_DGXSPARK_V1_SCHEDULER
    assert first_timeline_row["sm_ran_quantized"] == 8
    assert first_timeline_row["sm_ai_available"] == 32
    assert first_timeline_row["atom_duration_ms_at_sm_ai"] == pytest.approx(0.5)
    assert first_timeline_row["segment_progress_fraction"] == pytest.approx(1.0)

    assert (
        result.results_path
        == run_root / "derived" / simulator.SIMULATION_RESULTS_FILENAME
    )
    assert (
        result.timeline_path
        == run_root / "derived" / simulator.SCHEDULE_TIMELINE_FILENAME
    )
    assert (
        result.packed_timeline_path
        == run_root / "derived" / simulator.PACKED_EXEMPLAR_TIMELINE_FILENAME
    )
    assert set(packed_df["schedule_variant"]) == {"vram", "pcie_async"}
    assert set(packed_df["scheduler"]) == {experiments.RAN_DGXSPARK_V1_SCHEDULER}
