from __future__ import annotations

import csv
from pathlib import Path

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


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_minimal_normalized_trace(run_root: Path) -> None:
    _write_csv(
        run_root / "derived" / trace_contract.NORMALIZED_TRACE_FILENAME,
        fieldnames=list(trace_contract.NORMALIZED_TRACE_HEADERS),
        rows=[
            {
                "time_ms": 1.0,
                "sm_utilization": 0.0,
                "slot_duration_ms": 1.5,
                "source_schema": trace_contract.SOURCE_SCHEMA_B,
            },
            {
                "time_ms": 2.5,
                "sm_utilization": 100.0,
                "slot_duration_ms": 1.0,
                "source_schema": trace_contract.SOURCE_SCHEMA_B,
            },
        ],
    )


def _write_revised_simulation_inputs_fixture(run_root: Path) -> None:
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
            "total_memory_bytes",
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
                "total_memory_bytes": 32_000_000_000,
            }
        ],
    )

    prefill_rows: list[dict[str, object]] = []
    for partition, gemm_us, workspace_bytes, parked_bytes in (
        (8, 800.0, 140, 260),
        (16, 700.0, 130, 240),
        (24, 600.0, 120, 220),
        (32, 500.0, 110, 200),
    ):
        prefill_rows.append(
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
                "gpu_util": 62.0 + partition,
            }
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
            "gpu_util",
        ],
        rows=prefill_rows,
    )

    decode_rows: list[dict[str, object]] = []
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
                    "gpu_util": 50.0 + partition,
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
            "gpu_util",
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
            "gpu_util",
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
                "gpu_util": 48.0,
            }
        ],
    )
    _write_minimal_normalized_trace(run_root)


def test_assemble_simulation_inputs_writes_complete_joined_table(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "simulation-inputs"
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
                "num_hidden_layers": 12,
                "hidden_size": 768,
                "num_attention_heads": 12,
                "ffn_dim": 3072,
                "layer_index": 5,
                "layer_weight_bytes": 14_175_744,
                "total_weight_bytes_fp16": 250_478_592,
                "vram_ceiling_bytes": 19_200_000_000,
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
                "chunk_tokens": 64,
                "prefill_max_gemm_us": 20.0,
                "prefill_workspace_bytes": 40,
                "prefill_parked_activation_bytes": 512,
            },
            {
                "model_id": "facebook/opt-125m",
                "chunk_tokens": 128,
                "prefill_max_gemm_us": 30.0,
                "prefill_workspace_bytes": 60,
                "prefill_parked_activation_bytes": 1024,
            },
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
                "sequence_length": 1024,
                "block_size": 64,
                "decode_max_gemv_us": 5.0,
                "attention_fetch_compute_us": 7.0,
                "reduction_overhead_us": 2.0,
                "decode_workspace_bytes": 32,
                "decode_parked_activation_bytes": 64,
            },
            {
                "model_id": "facebook/opt-125m",
                "sequence_length": 2048,
                "block_size": 64,
                "decode_max_gemv_us": 6.0,
                "attention_fetch_compute_us": 9.0,
                "reduction_overhead_us": 3.0,
                "decode_workspace_bytes": 36,
                "decode_parked_activation_bytes": 64,
            },
            {
                "model_id": "facebook/opt-125m",
                "sequence_length": 1024,
                "block_size": 128,
                "decode_max_gemv_us": 8.0,
                "attention_fetch_compute_us": 10.0,
                "reduction_overhead_us": 4.0,
                "decode_workspace_bytes": 48,
                "decode_parked_activation_bytes": 128,
            },
        ],
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
        ],
        rows=[
            {
                "model_id": "facebook/opt-125m",
                "block_size": 64,
                "kv_block_bytes": 2048,
                "transfer_only_us": 10.0,
                "overlap_total_us": 8.0,
                "dummy_compute_us": 5.0,
                "exposed_transfer_us": 3.0,
                "effective_gbps": 0.2048,
            }
        ],
    )
    _write_minimal_normalized_trace(run_root)

    assembled = simulator.assemble_simulation_inputs(run_root=run_root)

    assert list(assembled.columns) == [
        "model_id",
        "chunk_tokens",
        "sequence_length",
        "num_hidden_layers",
        "hidden_size",
        "num_attention_heads",
        "ffn_dim",
        "layer_index",
        "layer_weight_bytes",
        "total_weight_bytes_fp16",
        "total_memory_bytes",
        "vram_ceiling_bytes",
        "kv_bytes_per_token_all_layers",
        "prefill_max_gemm_us",
        "prefill_workspace_bytes",
        "prefill_parked_activation_bytes",
        "decode_max_gemv_us",
        "attention_fetch_compute_us",
        "reduction_overhead_us",
        "decode_workspace_bytes",
        "decode_parked_activation_bytes",
        "pcie_exposed_us",
    ]
    assert assembled.to_dict(orient="records") == [
        {
            "model_id": "facebook/opt-125m",
            "chunk_tokens": 64,
            "sequence_length": 1024,
            "num_hidden_layers": 12,
            "hidden_size": 768,
            "num_attention_heads": 12,
            "ffn_dim": 3072,
            "layer_index": 5,
            "layer_weight_bytes": 14_175_744,
            "total_weight_bytes_fp16": 250_478_592,
            "total_memory_bytes": 32_000_000_000,
            "vram_ceiling_bytes": 19_200_000_000,
            "kv_bytes_per_token_all_layers": 36_864,
            "prefill_max_gemm_us": 20.0,
            "prefill_workspace_bytes": 40,
            "prefill_parked_activation_bytes": 512,
            "decode_max_gemv_us": 5.0,
            "attention_fetch_compute_us": 7.0,
            "reduction_overhead_us": 2.0,
            "decode_workspace_bytes": 32,
            "decode_parked_activation_bytes": 64,
            "pcie_exposed_us": 3.0,
        },
        {
            "model_id": "facebook/opt-125m",
            "chunk_tokens": 64,
            "sequence_length": 2048,
            "num_hidden_layers": 12,
            "hidden_size": 768,
            "num_attention_heads": 12,
            "ffn_dim": 3072,
            "layer_index": 5,
            "layer_weight_bytes": 14_175_744,
            "total_weight_bytes_fp16": 250_478_592,
            "total_memory_bytes": 32_000_000_000,
            "vram_ceiling_bytes": 19_200_000_000,
            "kv_bytes_per_token_all_layers": 36_864,
            "prefill_max_gemm_us": 20.0,
            "prefill_workspace_bytes": 40,
            "prefill_parked_activation_bytes": 512,
            "decode_max_gemv_us": 6.0,
            "attention_fetch_compute_us": 9.0,
            "reduction_overhead_us": 3.0,
            "decode_workspace_bytes": 36,
            "decode_parked_activation_bytes": 64,
            "pcie_exposed_us": 3.0,
        },
    ]
    assert _read_csv_rows(derived_root / simulator.SIMULATION_INPUTS_FILENAME) == [
        {
            "model_id": "facebook/opt-125m",
            "chunk_tokens": "64",
            "sequence_length": "1024",
            "num_hidden_layers": "12",
            "hidden_size": "768",
            "num_attention_heads": "12",
            "ffn_dim": "3072",
            "layer_index": "5",
            "layer_weight_bytes": "14175744",
            "total_weight_bytes_fp16": "250478592",
            "total_memory_bytes": "32000000000",
            "vram_ceiling_bytes": "19200000000",
            "kv_bytes_per_token_all_layers": "36864",
            "prefill_max_gemm_us": "20.0",
            "prefill_workspace_bytes": "40",
            "prefill_parked_activation_bytes": "512",
            "decode_max_gemv_us": "5.0",
            "attention_fetch_compute_us": "7.0",
            "reduction_overhead_us": "2.0",
            "decode_workspace_bytes": "32",
            "decode_parked_activation_bytes": "64",
            "pcie_exposed_us": "3.0",
        },
        {
            "model_id": "facebook/opt-125m",
            "chunk_tokens": "64",
            "sequence_length": "2048",
            "num_hidden_layers": "12",
            "hidden_size": "768",
            "num_attention_heads": "12",
            "ffn_dim": "3072",
            "layer_index": "5",
            "layer_weight_bytes": "14175744",
            "total_weight_bytes_fp16": "250478592",
            "total_memory_bytes": "32000000000",
            "vram_ceiling_bytes": "19200000000",
            "kv_bytes_per_token_all_layers": "36864",
            "prefill_max_gemm_us": "20.0",
            "prefill_workspace_bytes": "40",
            "prefill_parked_activation_bytes": "512",
            "decode_max_gemv_us": "6.0",
            "attention_fetch_compute_us": "9.0",
            "reduction_overhead_us": "3.0",
            "decode_workspace_bytes": "36",
            "decode_parked_activation_bytes": "64",
            "pcie_exposed_us": "3.0",
        },
    ]


def test_assemble_simulation_inputs_uses_explicit_total_memory_when_present(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "explicit-total-memory"
    derived_root = run_root / "derived"

    _write_csv(
        derived_root / "model_constants.csv",
        fieldnames=[
            "model_id",
            "num_hidden_layers",
            "hidden_size",
            "vram_ceiling_bytes",
            "total_memory_bytes",
        ],
        rows=[
            {
                "model_id": "facebook/opt-125m",
                "num_hidden_layers": 12,
                "hidden_size": 768,
                "vram_ceiling_bytes": 18_000_000_000,
                "total_memory_bytes": 40_000_000_000,
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
                "chunk_tokens": 64,
                "prefill_max_gemm_us": 20.0,
                "prefill_workspace_bytes": 40,
                "prefill_parked_activation_bytes": 512,
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
                "sequence_length": 1024,
                "block_size": 64,
                "decode_max_gemv_us": 5.0,
                "attention_fetch_compute_us": 7.0,
                "reduction_overhead_us": 2.0,
                "decode_workspace_bytes": 32,
                "decode_parked_activation_bytes": 64,
            }
        ],
    )
    _write_csv(
        derived_root / "pcie_summary.csv",
        fieldnames=["model_id", "block_size", "exposed_transfer_us"],
        rows=[
            {
                "model_id": "facebook/opt-125m",
                "block_size": 64,
                "exposed_transfer_us": 3.0,
            }
        ],
    )
    _write_minimal_normalized_trace(run_root)

    assembled = simulator.assemble_simulation_inputs(run_root=run_root)

    assert assembled.iloc[0]["total_memory_bytes"] == 40_000_000_000
    assert assembled.iloc[0]["kv_bytes_per_token_all_layers"] == 36_864


def test_assemble_simulation_inputs_dispatches_to_revised_schema(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "revised-simulation-inputs"
    _write_revised_simulation_inputs_fixture(run_root)

    assembled = simulator.assemble_simulation_inputs(
        run_root=run_root,
        experiment_type=experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE,
    )

    assert list(assembled.columns) == list(simulator.REVISED_SIMULATION_INPUT_COLUMNS)
    assert len(assembled) == 1
    row = assembled.iloc[0]
    assert row["model_id"] == "facebook/opt-125m"
    assert row["chunk_tokens"] == 2048
    assert row["sequence_length"] == 4096
    assert row["sm_ai_partitions_profiled"] == "8|16|24|32"
    assert row["prefill_max_gemm_us_sm32"] == 500.0
    assert row["prefill_workspace_bytes_sm8"] == 140
    assert row["decode_max_gemv_us_vram_sm24"] == 300.0
    assert row["decode_max_gemv_us_pcie_async_sm8"] == 450.0
    assert row["pcie_exposed_us"] == 75.0
    assert row["pcie_effective_gbps"] == 0.5
    assert row["pcie_overlap_status"] == "measured"
    assert row["prefill_telemetry_tier"] == experiments.RAN_DGXSPARK_V1_TELEMETRY_TIER
    assert row["decode_vram_telemetry_provider"] == "nvml"
    assert bool(row["pcie_nvml_available"]) is True
    assert row["prefill_acu_pct"] == pytest.approx(91.29)
    assert row["prefill_gbu_pct"] == pytest.approx(51.5375)
    assert row["prefill_smu_pct"] == pytest.approx(79.5375)
    assert row["prefill_microscopic_telemetry_status"] == "estimated"
    assert row["decode_vram_microscopic_telemetry_status"] == "estimated"
    assert row["decode_pcie_async_microscopic_telemetry_status"] == "estimated"
    assert row["pcie_microscopic_telemetry_status"] == "estimated"
    assert row["pcie_acu_pct"] == pytest.approx(65.0)
    assert row["pcie_gbu_pct"] == pytest.approx(65.0)
    assert row["pcie_smu_pct"] == pytest.approx(65.0)

    written_rows = _read_csv_rows(
        run_root / "derived" / simulator.SIMULATION_INPUTS_FILENAME
    )
    assert written_rows[0]["sm_ai_partitions_profiled"] == "8|16|24|32"
    assert written_rows[0]["prefill_max_gemm_us_sm32"] == "500.0"
    assert written_rows[0]["decode_max_gemv_us_vram_sm24"] == "300.0"
    assert written_rows[0]["pcie_overlap_status"] == "measured"
    assert written_rows[0]["prefill_microscopic_telemetry_status"] == "estimated"


def test_assemble_revised_simulation_inputs_coerces_nvml_available_string_booleans(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "revised-simulation-inputs-string-bools"
    _write_revised_simulation_inputs_fixture(run_root)

    prefill_summary_path = run_root / "derived" / "prefill_summary.csv"
    prefill_df = pd.read_csv(prefill_summary_path)
    prefill_df["nvml_available"] = "False"
    prefill_df.to_csv(prefill_summary_path, index=False)

    assembled = simulator.assemble_simulation_inputs(
        run_root=run_root,
        experiment_type=experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE,
    )

    row = assembled.iloc[0]
    assert bool(row["prefill_nvml_available"]) is False
    assert bool(row["decode_vram_nvml_available"]) is True


def test_assemble_revised_simulation_inputs_overrides_non_estimated_status_when_fallback_is_used(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "revised-simulation-inputs-status-override"
    _write_revised_simulation_inputs_fixture(run_root)

    prefill_summary_path = run_root / "derived" / "prefill_summary.csv"
    prefill_df = pd.read_csv(prefill_summary_path)
    prefill_df["microscopic_telemetry_status"] = "ok"
    prefill_df.to_csv(prefill_summary_path, index=False)

    assembled = simulator.assemble_simulation_inputs(
        run_root=run_root,
        experiment_type=experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE,
    )

    row = assembled.iloc[0]
    assert row["prefill_microscopic_telemetry_status"] == "estimated"


def test_group_rows_by_partition_synthesizes_missing_revised_partitions_for_duration_metrics() -> (
    None
):
    frame = pd.DataFrame(
        [
            {
                "sm_ai_partition": 32,
                "prefill_max_gemm_us": 320.0,
                "prefill_workspace_bytes": 128,
            }
        ]
    )

    grouped = simulator._group_rows_by_partition(
        frame,
        group_label="prefill test",
        duration_metrics=("prefill_max_gemm_us",),
    )

    assert set(grouped.keys()) == set(experiments.RAN_DGXSPARK_V1_SM_AI_PARTITIONS)
    assert grouped[32]["prefill_max_gemm_us"] == pytest.approx(320.0)
    # Baseline full duration = 320 * (32/48) = 213.333...
    # partition 8 duration = full * (48/8) = 1280
    assert grouped[8]["prefill_max_gemm_us"] == pytest.approx(1280.0)
    assert grouped[16]["prefill_max_gemm_us"] == pytest.approx(640.0)
    assert grouped[24]["prefill_max_gemm_us"] == pytest.approx(426.6666667)
    # non-duration metrics are copied from baseline synthesized row
    assert grouped[8]["prefill_workspace_bytes"] == 128
