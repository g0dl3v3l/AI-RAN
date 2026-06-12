from __future__ import annotations

import csv
from pathlib import Path

import pytest
import torch

from inference_profile import decode_profile
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


def test_profile_decode_with_writer_emits_exact_task7_schema_without_warmup_rows(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    raw_output_path = tmp_path / "raw" / decode_profile.DECODE_EVENTS_FILENAME
    writer = RawCsvWriter(
        raw_output_path,
        fieldnames=decode_profile.DECODE_EVENT_FIELDNAMES,
    )
    linear_warmup_calls: list[tuple[str, str, int]] = []
    attention_warmup_calls: list[tuple[str, tuple[str, str], int, int]] = []
    config = decode_profile.resolve_opt_config(
        "facebook/opt-125m",
        config_payload=_OPT_125M_CONFIG,
    )

    def fake_build_ops(_config, *, device, dtype):
        del device, dtype
        return tuple(
            decode_profile.DecodeLinearOp(
                op_name=op_name,
                module=op_name,
                input_width=1,
                output_width=1,
            )
            for op_name in decode_profile.DECODE_OP_NAMES
        )

    def fake_build_inputs(_config, *, device, dtype):
        del device, dtype
        return {
            op_name: f"input-{op_name}" for op_name in decode_profile.DECODE_OP_NAMES
        }

    def fake_build_attention_query_tensor(_config, *, q_proj_module, hidden_input):
        return f"query-from-{q_proj_module}-{hidden_input}"

    def fake_build_kv_cache(_config, sequence_length, *, device, dtype):
        del device, dtype
        return (f"k-cache-{sequence_length}", f"v-cache-{sequence_length}")

    def fake_run_linear_warmup(module, input_tensor, warmup_iterations, *, device):
        del device
        linear_warmup_calls.append((str(module), str(input_tensor), warmup_iterations))

    def fake_run_attention_warmup(
        query,
        kv_cache,
        block_size,
        warmup_iterations,
        *,
        device,
    ):
        del device
        attention_warmup_calls.append(
            (
                str(query),
                (str(kv_cache[0]), str(kv_cache[1])),
                block_size,
                warmup_iterations,
            )
        )

    def fake_time_linear_op(
        *,
        model_id,
        sequence_length,
        block_size,
        op_name,
        timed_iteration,
        module,
        input_tensor,
        device,
        sm_ai_partition,
    ):
        del module, input_tensor, device
        output_bytes = (
            config.ffn_dim * 2 if op_name == "fc1" else config.hidden_size * 2
        )
        baseline_vram_bytes = 1_000
        dynamic_workspace_bytes = 100 + timed_iteration + len(op_name)
        return {
            "model_id": model_id,
            "sequence_length": sequence_length,
            "block_size": block_size,
            "op_type": decode_profile.DECODE_GEMV_OP_TYPE,
            "op_name": op_name,
            "sm_ai_partition": sm_ai_partition,
            "timed_iteration": timed_iteration,
            "duration_us": 50.0 + timed_iteration,
            "baseline_vram_bytes": baseline_vram_bytes,
            "peak_vram_bytes": baseline_vram_bytes + dynamic_workspace_bytes,
            "dynamic_workspace_bytes": dynamic_workspace_bytes,
            "output_bytes": output_bytes,
        }

    def fake_time_attention_iteration(
        *,
        model_id,
        sequence_length,
        block_size,
        timed_iteration,
        query,
        kv_cache,
        device,
        sm_ai_partition,
    ):
        del query, kv_cache, device
        num_blocks = decode_profile._calculate_num_blocks(sequence_length, block_size)
        attention_baseline_vram_bytes = 2_000
        attention_dynamic_workspace_bytes = 250 + num_blocks
        reduction_baseline_vram_bytes = 3_000
        reduction_dynamic_workspace_bytes = 25 + num_blocks
        return (
            {
                "model_id": model_id,
                "sequence_length": sequence_length,
                "block_size": block_size,
                "op_type": decode_profile.DECODE_ATTENTION_FETCH_COMPUTE_OP_TYPE,
                "op_name": "",
                "sm_ai_partition": sm_ai_partition,
                "timed_iteration": timed_iteration,
                "duration_us": 75.0 + timed_iteration,
                "baseline_vram_bytes": attention_baseline_vram_bytes,
                "peak_vram_bytes": attention_baseline_vram_bytes
                + attention_dynamic_workspace_bytes,
                "dynamic_workspace_bytes": attention_dynamic_workspace_bytes,
                "output_bytes": num_blocks * 64,
            },
            {
                "model_id": model_id,
                "sequence_length": sequence_length,
                "block_size": block_size,
                "op_type": decode_profile.DECODE_REDUCTION_OVERHEAD_OP_TYPE,
                "op_name": "",
                "sm_ai_partition": sm_ai_partition,
                "timed_iteration": timed_iteration,
                "duration_us": 7.5 + timed_iteration,
                "baseline_vram_bytes": reduction_baseline_vram_bytes,
                "peak_vram_bytes": reduction_baseline_vram_bytes
                + reduction_dynamic_workspace_bytes,
                "dynamic_workspace_bytes": reduction_dynamic_workspace_bytes,
                "output_bytes": config.hidden_size * 2,
            },
        )

    monkeypatch.setattr(
        decode_profile,
        "_require_cuda_device",
        lambda _gpu_id: torch.device("cuda:0"),
    )
    monkeypatch.setattr(decode_profile.torch.cuda, "set_device", lambda _device: None)
    monkeypatch.setattr(decode_profile, "_build_decode_linear_ops", fake_build_ops)
    monkeypatch.setattr(
        decode_profile, "_build_decode_input_tensors", fake_build_inputs
    )
    monkeypatch.setattr(
        decode_profile,
        "_build_attention_query_tensor",
        fake_build_attention_query_tensor,
    )
    monkeypatch.setattr(decode_profile, "_build_kv_cache", fake_build_kv_cache)
    monkeypatch.setattr(decode_profile, "_run_linear_warmup", fake_run_linear_warmup)
    monkeypatch.setattr(
        decode_profile,
        "_run_attention_warmup",
        fake_run_attention_warmup,
    )
    monkeypatch.setattr(decode_profile, "_time_linear_op", fake_time_linear_op)
    monkeypatch.setattr(
        decode_profile,
        "_time_attention_iteration",
        fake_time_attention_iteration,
    )

    try:
        result = decode_profile.profile_decode_with_writer(
            model_id="facebook/opt-125m",
            raw_writer=writer,
            sequence_lengths=(1024, 2048),
            block_sizes=(64, 128),
            warmup_iterations=2,
            timed_iterations=3,
            config_payload=_OPT_125M_CONFIG,
        )
    finally:
        writer.close()

    fieldnames, rows = _read_rows(raw_output_path)
    expected_points = 2 * 2 * 3
    expected_row_count = expected_points * (len(decode_profile.DECODE_OP_NAMES) + 2)

    assert fieldnames == list(decode_profile.DECODE_EVENT_FIELDNAMES)
    assert len(rows) == expected_row_count
    assert result.row_count == expected_row_count
    assert result.raw_output_path == raw_output_path
    assert result.decode_parked_activation_bytes == config.hidden_size * 2
    assert result.max_decode_workspace_bytes == max(
        int(row["dynamic_workspace_bytes"]) for row in rows
    )

    assert linear_warmup_calls == [
        (op_name, f"input-{op_name}", 2)
        for sequence_length in (1024, 2048)
        for block_size in (64, 128)
        for op_name in decode_profile.DECODE_OP_NAMES
    ]
    assert attention_warmup_calls == [
        (
            "query-from-q_proj-input-q_proj",
            (f"k-cache-{sequence_length}", f"v-cache-{sequence_length}"),
            block_size,
            2,
        )
        for sequence_length in (1024, 2048)
        for block_size in (64, 128)
    ]

    gemv_rows = [
        row for row in rows if row["op_type"] == decode_profile.DECODE_GEMV_OP_TYPE
    ]
    attention_rows = [
        row
        for row in rows
        if row["op_type"] == decode_profile.DECODE_ATTENTION_FETCH_COMPUTE_OP_TYPE
    ]
    reduction_rows = [
        row
        for row in rows
        if row["op_type"] == decode_profile.DECODE_REDUCTION_OVERHEAD_OP_TYPE
    ]

    assert len(gemv_rows) == expected_points * len(decode_profile.DECODE_OP_NAMES)
    assert len(attention_rows) == expected_points
    assert len(reduction_rows) == expected_points
    assert {row["op_name"] for row in gemv_rows} == set(decode_profile.DECODE_OP_NAMES)
    assert {row["op_name"] for row in attention_rows} == {""}
    assert {row["op_name"] for row in reduction_rows} == {""}
    assert {int(row["sm_ai_partition"]) for row in rows} == {100}

    rows_by_point: dict[tuple[int, int, int], list[dict[str, str]]] = {}
    for row in rows:
        key = (
            int(row["sequence_length"]),
            int(row["block_size"]),
            int(row["timed_iteration"]),
        )
        rows_by_point.setdefault(key, []).append(row)

    assert len(rows_by_point) == expected_points
    for point_rows in rows_by_point.values():
        assert len(point_rows) == len(decode_profile.DECODE_OP_NAMES) + 2
        assert sum(
            row["op_type"] == decode_profile.DECODE_GEMV_OP_TYPE for row in point_rows
        ) == len(decode_profile.DECODE_OP_NAMES)
        assert (
            sum(
                row["op_type"] == decode_profile.DECODE_ATTENTION_FETCH_COMPUTE_OP_TYPE
                for row in point_rows
            )
            == 1
        )
        assert (
            sum(
                row["op_type"] == decode_profile.DECODE_REDUCTION_OVERHEAD_OP_TYPE
                for row in point_rows
            )
            == 1
        )


def test_resolve_decode_output_path_defaults_to_raw_decode_events_csv(
    tmp_path: Path,
) -> None:
    assert decode_profile.resolve_decode_output_path(output_root=tmp_path) == (
        tmp_path / "raw" / decode_profile.DECODE_EVENTS_FILENAME
    )


def test_decode_fieldnames_and_constants_match_task7_contract() -> None:
    assert decode_profile.DECODE_EVENT_FIELDNAMES == (
        "model_id",
        "sequence_length",
        "block_size",
        "op_type",
        "op_name",
        "sm_ai_partition",
        "timed_iteration",
        "duration_us",
        "baseline_vram_bytes",
        "peak_vram_bytes",
        "dynamic_workspace_bytes",
        "output_bytes",
    )
    assert decode_profile.DECODE_BATCH_SIZE == 1
    assert decode_profile.DECODE_DTYPE_NAME == "float16"
    assert decode_profile.DECODE_OP_NAMES == (
        "q_proj",
        "k_proj",
        "v_proj",
        "out_proj",
        "fc1",
        "fc2",
    )
    assert decode_profile.DECODE_BLOCK_SIZES == (64, 128, 256, 512, 1024)


def test_decode_shape_normalizers_and_block_counter_validate_inputs() -> None:
    assert decode_profile._normalize_sequence_lengths([1024, 2048]) == (1024, 2048)
    assert decode_profile._normalize_block_sizes([64, 128]) == (64, 128)
    assert decode_profile._calculate_num_blocks(1024, 64) == 16
    assert decode_profile._calculate_num_blocks(1000, 64) == 16

    with pytest.raises(ValueError, match="sequence_lengths"):
        decode_profile._normalize_sequence_lengths([])
    with pytest.raises(ValueError, match="sequence_lengths"):
        decode_profile._normalize_sequence_lengths([0, -1])
    with pytest.raises(ValueError, match="block_sizes"):
        decode_profile._normalize_block_sizes([])
    with pytest.raises(ValueError, match="block_sizes"):
        decode_profile._normalize_block_sizes([0, -1])


def test_estimate_decode_parked_activation_bytes_uses_final_hidden_output() -> None:
    config = decode_profile.resolve_opt_config(
        "facebook/opt-125m",
        config_payload=_OPT_125M_CONFIG,
    )

    assert decode_profile.estimate_decode_parked_activation_bytes(config) == 768 * 2


def test_sequence_lengths_exceeding_context_reports_only_out_of_range_values() -> None:
    exceeded = decode_profile._sequence_lengths_exceeding_context(
        (1024, 2048, 4096, 8192),
        max_position_embeddings=4096,
    )
    assert exceeded == (8192,)


def test_warn_if_sequence_lengths_exceed_model_context_emits_runtime_warning() -> None:
    with pytest.warns(RuntimeWarning, match="synthetic kernel-level profiling"):
        decode_profile._warn_if_sequence_lengths_exceed_model_context(
            sequence_lengths=(4096, 8192),
            max_position_embeddings=4096,
            model_id="facebook/opt-350m",
        )
