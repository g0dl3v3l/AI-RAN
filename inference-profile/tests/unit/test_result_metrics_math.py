from __future__ import annotations

from inference_profile import simulator


def _build_result_input(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "model_id": "facebook/opt-125m",
        "chunk_tokens": 64,
        "sequence_length": 1024,
        "num_hidden_layers": 1,
        "kv_bytes_per_token_all_layers": 25,
        "vram_ceiling_bytes": 1_000,
        "total_weight_bytes_fp16": 600,
        "prefill_max_gemm_us": 20.0,
        "prefill_workspace_bytes": 80,
        "prefill_parked_activation_bytes": 120,
        "decode_max_gemv_us": 5.0,
        "attention_fetch_compute_us": 7.0,
        "reduction_overhead_us": 2.0,
        "decode_workspace_bytes": 40,
        "decode_parked_activation_bytes": 60,
        "pcie_exposed_us": 3.0,
    }
    row.update(overrides)
    return row


def test_simulate_result_row_computes_survival_and_runway_metrics() -> None:
    result_row, timeline_rows = simulator._simulate_result_row(
        _build_result_input(),
        idle_gaps=(),
        trace_sha256="trace-sha",
    )

    assert result_row["survival_vram_bytes"] == 200
    assert result_row["decode_runway_bytes"] == 0
    assert result_row["decode_runway_tokens"] == 0
    assert result_row["status"] == "prefill_trace_fit_failed"
    assert result_row["trace_sha256"] == "trace-sha"
    assert timeline_rows == []


def test_simulate_result_row_clamps_decode_runway_but_not_survival() -> None:
    result_row, _ = simulator._simulate_result_row(
        _build_result_input(
            kv_bytes_per_token_all_layers=16,
            vram_ceiling_bytes=500,
            total_weight_bytes_fp16=450,
            prefill_workspace_bytes=10,
            prefill_parked_activation_bytes=80,
            decode_workspace_bytes=30,
            decode_parked_activation_bytes=40,
        ),
        idle_gaps=(),
        trace_sha256="trace-sha",
    )

    assert result_row["survival_vram_bytes"] == -40
    assert result_row["decode_runway_bytes"] == 0
    assert result_row["decode_runway_tokens"] == 0


def test_simulate_result_row_subtracts_bulk_kv_cache_from_decode_runway() -> None:
    result_row, _ = simulator._simulate_result_row(
        _build_result_input(
            chunk_tokens=4,
            kv_bytes_per_token_all_layers=25,
            vram_ceiling_bytes=1_200,
            total_weight_bytes_fp16=600,
            decode_workspace_bytes=40,
            decode_parked_activation_bytes=60,
            prefill_workspace_bytes=10,
            prefill_parked_activation_bytes=10,
        ),
        idle_gaps=(),
        trace_sha256="trace-sha",
    )

    assert result_row["decode_runway_bytes"] == 400
    assert result_row["decode_runway_tokens"] == 16
