from __future__ import annotations

import csv
from pathlib import Path

import torch

from inference_profile import prefill_profile
from inference_profile.worker_profile_point import RawCsvWriter

_OPT_125M_CONFIG = {
    "hidden_size": 768,
    "num_hidden_layers": 12,
    "num_attention_heads": 12,
    "ffn_dim": 3072,
    "max_position_embeddings": 2048,
    "vocab_size": 50272,
    "word_embed_proj_dim": 768,
    "do_layer_norm_before": True,
}


def _read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames is not None
        return list(reader.fieldnames), list(reader)


def test_profile_prefill_with_writer_emits_exact_task6_schema_without_warmup_rows(
    monkeypatch,
    tmp_path: Path,
) -> None:
    raw_output_path = tmp_path / "raw" / prefill_profile.PREFILL_EVENTS_FILENAME
    writer = RawCsvWriter(
        raw_output_path,
        fieldnames=prefill_profile.PREFILL_EVENT_FIELDNAMES,
    )
    warmup_calls: list[tuple[str, object, int]] = []

    def fake_build_ops(_config, *, device, dtype):
        del device, dtype
        return tuple(
            prefill_profile.PrefillLinearOp(
                op_name=op_name,
                module=op_name,
                input_width=1,
                output_width=1,
            )
            for op_name in prefill_profile.PREFILL_OP_NAMES
        )

    def fake_build_inputs(_config, *, chunk_tokens, device, dtype):
        del device, dtype
        return {
            op_name: f"input-{op_name}-{chunk_tokens}"
            for op_name in prefill_profile.PREFILL_OP_NAMES
        }

    def fake_run_warmup(module, input_tensor, warmup_iterations, *, device):
        del device
        warmup_calls.append((str(module), input_tensor, warmup_iterations))

    def fake_time_linear_op(
        *,
        model_id,
        chunk_tokens,
        op_name,
        timed_iteration,
        module,
        input_tensor,
        device,
        sm_ai_partition,
    ):
        del module, input_tensor, device, sm_ai_partition
        output_bytes = prefill_profile.build_prefill_output_byte_map(
            prefill_profile.resolve_opt_config(
                model_id,
                config_payload=_OPT_125M_CONFIG,
            ),
            chunk_tokens,
        )[op_name]
        return {
            "model_id": model_id,
            "chunk_tokens": chunk_tokens,
            "op_type": prefill_profile.PREFILL_GEMM_OP_TYPE,
            "op_name": op_name,
            "sm_ai_partition": 100,
            "timed_iteration": timed_iteration,
            "duration_us": 100.0 + timed_iteration,
            "baseline_vram_bytes": 1_000,
            "peak_vram_bytes": 1_000 + output_bytes,
            "dynamic_workspace_bytes": output_bytes,
            "output_bytes": output_bytes,
        }

    def fake_build_prefill_attention_inputs(
        _config,
        *,
        q_proj_module,
        k_proj_module,
        v_proj_module,
        hidden_input,
    ):
        del q_proj_module, k_proj_module, v_proj_module, hidden_input
        return "query", "key", "value"

    def fake_run_attention_warmup(query, key, value, warmup_iterations, *, device):
        del query, key, value, warmup_iterations, device

    def fake_time_attention_op(
        *,
        model_id,
        chunk_tokens,
        timed_iteration,
        query,
        key,
        value,
        device,
        sm_ai_partition,
    ):
        del query, key, value, device
        return {
            "model_id": model_id,
            "chunk_tokens": chunk_tokens,
            "op_type": prefill_profile.PREFILL_ATTENTION_OP_TYPE,
            "op_name": prefill_profile.PREFILL_ATTENTION_OP_NAME,
            "sm_ai_partition": sm_ai_partition,
            "timed_iteration": timed_iteration,
            "duration_us": 300.0 + timed_iteration,
            "baseline_vram_bytes": 1_000,
            "peak_vram_bytes": 1_600,
            "dynamic_workspace_bytes": 600,
            "output_bytes": 1_024,
        }

    monkeypatch.setattr(
        prefill_profile, "_require_cuda_device", lambda _gpu_id: torch.device("cuda:0")
    )
    monkeypatch.setattr(prefill_profile.torch.cuda, "set_device", lambda _device: None)
    monkeypatch.setattr(prefill_profile, "_build_prefill_linear_ops", fake_build_ops)
    monkeypatch.setattr(prefill_profile, "_build_input_tensors", fake_build_inputs)
    monkeypatch.setattr(
        prefill_profile,
        "_build_prefill_attention_inputs",
        fake_build_prefill_attention_inputs,
    )
    monkeypatch.setattr(prefill_profile, "_run_warmup", fake_run_warmup)
    monkeypatch.setattr(
        prefill_profile, "_run_attention_warmup", fake_run_attention_warmup
    )
    monkeypatch.setattr(prefill_profile, "_time_linear_op", fake_time_linear_op)
    monkeypatch.setattr(prefill_profile, "_time_attention_op", fake_time_attention_op)

    try:
        result = prefill_profile.profile_prefill_with_writer(
            model_id="facebook/opt-125m",
            raw_writer=writer,
            chunk_tokens=(64, 128),
            warmup_iterations=2,
            timed_iterations=3,
            config_payload=_OPT_125M_CONFIG,
        )
    finally:
        writer.close()

    fieldnames, rows = _read_rows(raw_output_path)
    assert fieldnames == list(prefill_profile.PREFILL_EVENT_FIELDNAMES)
    assert len(rows) == (len(prefill_profile.PREFILL_OP_NAMES) + 1) * 2 * 3
    assert result.row_count == len(rows)
    assert result.raw_output_path == raw_output_path
    assert warmup_calls == [
        (f"{op_name}", f"input-{op_name}-{chunk}", 2)
        for chunk in (64, 128)
        for op_name in prefill_profile.PREFILL_OP_NAMES
    ]

    assert {row["model_id"] for row in rows} == {"facebook/opt-125m"}
    assert {int(row["chunk_tokens"]) for row in rows} == {64, 128}
    assert {row["op_name"] for row in rows} == {
        *prefill_profile.PREFILL_OP_NAMES,
        prefill_profile.PREFILL_ATTENTION_OP_NAME,
    }
    assert {row["op_type"] for row in rows} == {
        prefill_profile.PREFILL_GEMM_OP_TYPE,
        prefill_profile.PREFILL_ATTENTION_OP_TYPE,
    }
    assert {int(row["sm_ai_partition"]) for row in rows} == {100}
    assert {int(row["timed_iteration"]) for row in rows} == {0, 1, 2}
    assert all(float(row["duration_us"]) > 0 for row in rows)

    first_fc1_64 = next(
        row
        for row in rows
        if row["op_name"] == "fc1"
        and int(row["chunk_tokens"]) == 64
        and int(row["timed_iteration"]) == 0
    )
    assert int(first_fc1_64["output_bytes"]) == 64 * 3072 * 2
    assert int(first_fc1_64["dynamic_workspace_bytes"]) == int(
        first_fc1_64["peak_vram_bytes"]
    ) - int(first_fc1_64["baseline_vram_bytes"])
    assert result.parked_activation_bytes_by_chunk == {
        64: 64 * 3072 * 2,
        128: 128 * 3072 * 2,
    }


def test_resolve_prefill_output_path_defaults_to_raw_prefill_events_csv(
    tmp_path: Path,
) -> None:
    assert prefill_profile.resolve_prefill_output_path(output_root=tmp_path) == (
        tmp_path / "raw" / prefill_profile.PREFILL_EVENTS_FILENAME
    )
