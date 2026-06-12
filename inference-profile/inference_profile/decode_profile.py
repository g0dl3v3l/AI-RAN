from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any
import warnings

from huggingface_hub import hf_hub_download
import torch

from inference_profile import experiments, opt_assets
from inference_profile.constants import DECODE_SEQUENCE_LENGTHS, PREFILL_CHUNK_SIZES
from inference_profile.worker_profile_point import RawCsvWriter

DECODE_EVENTS_FILENAME = "decode_events.csv"
DECODE_BATCH_SIZE = 1
DECODE_DTYPE_NAME = "float16"
DECODE_OP_NAMES = (
    "q_proj",
    "k_proj",
    "v_proj",
    "out_proj",
    "fc1",
    "fc2",
)
DECODE_BLOCK_SIZES = PREFILL_CHUNK_SIZES
DECODE_GEMV_OP_TYPE = "gemv"
DECODE_ATTENTION_FETCH_COMPUTE_OP_TYPE = "attention_fetch_compute"
DECODE_REDUCTION_OVERHEAD_OP_TYPE = "reduction_overhead"
DECODE_EVENT_FIELDNAMES = (
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

_DEFAULT_INPUT_SEED_BASE = 2_000
_DECODE_REASON = "decode_microbenchmark"
_KV_CACHE_KEY_SEED_OFFSET = 100
_KV_CACHE_VALUE_SEED_OFFSET = 200


@dataclass(frozen=True)
class DecodeLinearOp:
    op_name: str
    module: Any
    input_width: int
    output_width: int


@dataclass(frozen=True)
class AttentionBlockStats:
    max_scores: torch.Tensor
    exp_sums: torch.Tensor
    weighted_values: torch.Tensor

    @property
    def output_bytes(self) -> int:
        return int(
            (self.max_scores.numel() * self.max_scores.element_size())
            + (self.exp_sums.numel() * self.exp_sums.element_size())
            + (self.weighted_values.numel() * self.weighted_values.element_size())
        )


@dataclass(frozen=True)
class DecodeProfileResult:
    model_id: str
    raw_output_path: Path
    row_count: int
    max_decode_workspace_bytes: int
    decode_parked_activation_bytes: int
    decode_mode: str


def resolve_decode_output_path(
    *,
    output_root: str | Path | None = None,
    raw_output_path: str | Path | None = None,
) -> Path:
    if raw_output_path is not None:
        return Path(raw_output_path)
    resolved_output_root = Path(output_root) if output_root is not None else Path(".")
    return resolved_output_root / "raw" / DECODE_EVENTS_FILENAME


def resolve_opt_config(
    model_id: str,
    *,
    config_payload: Mapping[str, Any] | opt_assets.OptConfig | None = None,
    cache_root: str | Path | None = None,
) -> opt_assets.OptConfig:
    normalized_model_id = opt_assets.normalize_model_id(model_id)
    if isinstance(config_payload, opt_assets.OptConfig):
        if config_payload.model_id != normalized_model_id:
            raise ValueError(
                "config_payload model_id does not match the requested model_id"
            )
        return config_payload

    if config_payload is not None:
        return opt_assets.derive_opt_config(normalized_model_id, config_payload)

    config_path = Path(
        hf_hub_download(
            repo_id=normalized_model_id,
            filename=opt_assets.CONFIG_FILENAME,
            cache_dir=Path(cache_root) if cache_root is not None else None,
        )
    )
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {config_path}")
    return opt_assets.derive_opt_config(normalized_model_id, payload)


def estimate_decode_parked_activation_bytes(config: opt_assets.OptConfig) -> int:
    return DECODE_BATCH_SIZE * config.hidden_size * opt_assets.FP16_BYTES_PER_PARAMETER


def profile_decode_sweep(
    *,
    model_id: str,
    output_root: str | Path | None = None,
    raw_output_path: str | Path | None = None,
    sequence_lengths: Sequence[int] = DECODE_SEQUENCE_LENGTHS,
    block_sizes: Sequence[int] = DECODE_BLOCK_SIZES,
    warmup_iterations: int = 3,
    timed_iterations: int = 5,
    gpu_id: int = 0,
    sm_ai_partition: int = 100,
    decode_mode: str = experiments.RAN_DGXSPARK_V1_DECODE_MODES[0],
    config_payload: Mapping[str, Any] | opt_assets.OptConfig | None = None,
    cache_root: str | Path | None = None,
) -> DecodeProfileResult:
    resolved_output_path = resolve_decode_output_path(
        output_root=output_root,
        raw_output_path=raw_output_path,
    )
    writer = RawCsvWriter(resolved_output_path, fieldnames=DECODE_EVENT_FIELDNAMES)
    try:
        result = profile_decode_with_writer(
            model_id=model_id,
            raw_writer=writer,
            sequence_lengths=sequence_lengths,
            block_sizes=block_sizes,
            warmup_iterations=warmup_iterations,
            timed_iterations=timed_iterations,
            gpu_id=gpu_id,
            sm_ai_partition=sm_ai_partition,
            decode_mode=decode_mode,
            config_payload=config_payload,
            cache_root=cache_root,
        )
    finally:
        writer.close()
    return result


def profile_decode_with_writer(
    *,
    model_id: str,
    raw_writer: RawCsvWriter,
    sequence_lengths: Sequence[int] = DECODE_SEQUENCE_LENGTHS,
    block_sizes: Sequence[int] = DECODE_BLOCK_SIZES,
    warmup_iterations: int = 3,
    timed_iterations: int = 5,
    gpu_id: int = 0,
    sm_ai_partition: int = 100,
    decode_mode: str = experiments.RAN_DGXSPARK_V1_DECODE_MODES[0],
    config_payload: Mapping[str, Any] | opt_assets.OptConfig | None = None,
    cache_root: str | Path | None = None,
) -> DecodeProfileResult:
    if warmup_iterations < 0:
        raise ValueError("warmup_iterations must be >= 0")
    if timed_iterations <= 0:
        raise ValueError("timed_iterations must be > 0")

    resolved_sequence_lengths = _normalize_sequence_lengths(sequence_lengths)
    resolved_block_sizes = _normalize_block_sizes(block_sizes)
    resolved_decode_mode = _normalize_decode_mode(decode_mode)
    config = resolve_opt_config(
        model_id,
        config_payload=config_payload,
        cache_root=cache_root,
    )
    _warn_if_sequence_lengths_exceed_model_context(
        sequence_lengths=resolved_sequence_lengths,
        max_position_embeddings=config.max_position_embeddings,
        model_id=config.model_id,
    )
    resolved_sm_ai_partition = _normalize_sm_ai_partition(sm_ai_partition)
    device = _require_cuda_device(gpu_id)
    torch_dtype = getattr(torch, DECODE_DTYPE_NAME)
    torch.cuda.set_device(device)

    ops = _build_decode_linear_ops(config, device=device, dtype=torch_dtype)
    input_tensors = _build_decode_input_tensors(
        config, device=device, dtype=torch_dtype
    )
    ops_by_name = {op.op_name: op for op in ops}
    query = _build_attention_query_tensor(
        config,
        q_proj_module=ops_by_name["q_proj"].module,
        hidden_input=input_tensors["q_proj"],
    )
    max_workspace_bytes = 0

    with torch.inference_mode():
        for sequence_length in resolved_sequence_lengths:
            for block_size in resolved_block_sizes:
                kv_cache = _build_kv_cache(
                    config,
                    sequence_length=sequence_length,
                    device=device,
                    dtype=torch_dtype,
                )

                for op in ops:
                    _run_linear_warmup(
                        op.module,
                        input_tensors[op.op_name],
                        warmup_iterations,
                        device=device,
                    )
                _run_attention_warmup(
                    query,
                    kv_cache,
                    block_size,
                    warmup_iterations,
                    device=device,
                )

                for timed_iteration in range(timed_iterations):
                    for op in ops:
                        row = _time_linear_op(
                            model_id=config.model_id,
                            sequence_length=sequence_length,
                            block_size=block_size,
                            op_name=op.op_name,
                            timed_iteration=timed_iteration,
                            module=op.module,
                            input_tensor=input_tensors[op.op_name],
                            device=device,
                            sm_ai_partition=resolved_sm_ai_partition,
                        )
                        raw_writer.write_row(row)
                        max_workspace_bytes = max(
                            max_workspace_bytes,
                            int(row["dynamic_workspace_bytes"]),
                        )

                    attention_row, reduction_row = _time_attention_iteration(
                        model_id=config.model_id,
                        sequence_length=sequence_length,
                        block_size=block_size,
                        timed_iteration=timed_iteration,
                        query=query,
                        kv_cache=kv_cache,
                        device=device,
                        sm_ai_partition=resolved_sm_ai_partition,
                    )
                    raw_writer.write_row(attention_row)
                    raw_writer.write_row(reduction_row)
                    max_workspace_bytes = max(
                        max_workspace_bytes,
                        int(attention_row["dynamic_workspace_bytes"]),
                        int(reduction_row["dynamic_workspace_bytes"]),
                    )

                del kv_cache

    return DecodeProfileResult(
        model_id=config.model_id,
        raw_output_path=Path(raw_writer.path)
        if raw_writer.path is not None
        else Path(),
        row_count=raw_writer.row_count,
        max_decode_workspace_bytes=max_workspace_bytes,
        decode_parked_activation_bytes=estimate_decode_parked_activation_bytes(config),
        decode_mode=resolved_decode_mode,
    )


def _normalize_sequence_lengths(sequence_lengths: Sequence[int]) -> tuple[int, ...]:
    if not sequence_lengths:
        raise ValueError("sequence_lengths must contain at least one value")
    resolved = tuple(int(length) for length in sequence_lengths)
    invalid = [length for length in resolved if length <= 0]
    if invalid:
        raise ValueError("sequence_lengths must contain only positive integers")
    return resolved


def _normalize_block_sizes(block_sizes: Sequence[int]) -> tuple[int, ...]:
    if not block_sizes:
        raise ValueError("block_sizes must contain at least one value")
    resolved = tuple(int(size) for size in block_sizes)
    invalid = [size for size in resolved if size <= 0]
    if invalid:
        raise ValueError("block_sizes must contain only positive integers")
    return resolved


def _normalize_decode_mode(decode_mode: str) -> str:
    normalized = str(decode_mode).strip().lower()
    if normalized not in experiments.RAN_DGXSPARK_V1_DECODE_MODES:
        raise ValueError(
            f"decode_mode must be one of {experiments.RAN_DGXSPARK_V1_DECODE_MODES}"
        )
    return normalized


def _calculate_num_blocks(sequence_length: int, block_size: int) -> int:
    return (int(sequence_length) + int(block_size) - 1) // int(block_size)


def _sequence_lengths_exceeding_context(
    sequence_lengths: Sequence[int],
    *,
    max_position_embeddings: int,
) -> tuple[int, ...]:
    return tuple(
        int(length)
        for length in sequence_lengths
        if int(length) > int(max_position_embeddings)
    )


def _warn_if_sequence_lengths_exceed_model_context(
    *,
    sequence_lengths: Sequence[int],
    max_position_embeddings: int,
    model_id: str,
) -> None:
    exceeded = _sequence_lengths_exceeding_context(
        sequence_lengths,
        max_position_embeddings=max_position_embeddings,
    )
    if not exceeded:
        return
    warnings.warn(
        (
            "Decode microbenchmark requested sequence lengths "
            f"{list(exceeded)} above model context limit "
            f"({max_position_embeddings}) for {model_id}. "
            "These points remain synthetic kernel-level profiling "
            "and are not equivalent to full autoregressive decode semantics."
        ),
        RuntimeWarning,
        stacklevel=2,
    )


def _require_cuda_device(gpu_id: int) -> torch.device:
    if not torch.cuda.is_available():
        raise RuntimeError("Decode CUDA-event profiling requires an available CUDA GPU")
    return torch.device(f"cuda:{int(gpu_id)}")


def _build_decode_linear_ops(
    config: opt_assets.OptConfig,
    *,
    device: torch.device,
    dtype: torch.dtype,
) -> tuple[DecodeLinearOp, ...]:
    layer_index = opt_assets.select_middle_layer_index(config.num_hidden_layers)
    synthetic_layer = opt_assets.build_synthetic_layer_metadata(
        config,
        layer_index=layer_index,
        reason=_DECODE_REASON,
    )
    parameter_specs = {
        str(parameter["name"]): dict(parameter)
        for parameter in synthetic_layer["parameters"]
    }
    hidden_size = config.hidden_size
    ffn_dim = config.ffn_dim
    op_definitions = (
        ("q_proj", hidden_size, hidden_size, "self_attn.q_proj"),
        ("k_proj", hidden_size, hidden_size, "self_attn.k_proj"),
        ("v_proj", hidden_size, hidden_size, "self_attn.v_proj"),
        ("out_proj", hidden_size, hidden_size, "self_attn.out_proj"),
        ("fc1", hidden_size, ffn_dim, "fc1"),
        ("fc2", ffn_dim, hidden_size, "fc2"),
    )
    return tuple(
        DecodeLinearOp(
            op_name=op_name,
            module=_build_linear_module(
                in_features=in_features,
                out_features=out_features,
                weight_spec=parameter_specs[f"{parameter_prefix}.weight"],
                bias_spec=parameter_specs[f"{parameter_prefix}.bias"],
                device=device,
                dtype=dtype,
            ),
            input_width=in_features,
            output_width=out_features,
        )
        for op_name, in_features, out_features, parameter_prefix in op_definitions
    )


def _build_linear_module(
    *,
    in_features: int,
    out_features: int,
    weight_spec: Mapping[str, Any],
    bias_spec: Mapping[str, Any],
    device: torch.device,
    dtype: torch.dtype,
) -> Any:
    module = torch.nn.Linear(
        in_features,
        out_features,
        bias=True,
        device=device,
        dtype=dtype,
    )
    weight_tensor = _make_deterministic_fp16_tensor(
        weight_spec["shape"],
        seed=int(weight_spec["seed"]),
        device=device,
    )
    bias_tensor = _make_deterministic_fp16_tensor(
        bias_spec["shape"],
        seed=int(bias_spec["seed"]),
        device=device,
    )
    with torch.inference_mode():
        module.weight.copy_(weight_tensor)
        module.bias.copy_(bias_tensor)
    module.eval()
    for parameter in module.parameters():
        parameter.requires_grad_(False)
    return module


def _build_decode_input_tensors(
    config: opt_assets.OptConfig,
    *,
    device: torch.device,
    dtype: torch.dtype,
) -> dict[str, torch.Tensor]:
    hidden_tensor = _make_deterministic_fp16_tensor(
        (DECODE_BATCH_SIZE, 1, config.hidden_size),
        seed=_DEFAULT_INPUT_SEED_BASE + 1,
        device=device,
    ).to(dtype=dtype)
    ffn_tensor = _make_deterministic_fp16_tensor(
        (DECODE_BATCH_SIZE, 1, config.ffn_dim),
        seed=_DEFAULT_INPUT_SEED_BASE + 10_001,
        device=device,
    ).to(dtype=dtype)
    return {
        "q_proj": hidden_tensor,
        "k_proj": hidden_tensor,
        "v_proj": hidden_tensor,
        "out_proj": hidden_tensor,
        "fc1": hidden_tensor,
        "fc2": ffn_tensor,
    }


def _build_attention_query_tensor(
    config: opt_assets.OptConfig,
    *,
    q_proj_module: Any,
    hidden_input: torch.Tensor,
) -> torch.Tensor:
    projected_query = q_proj_module(hidden_input)
    return _reshape_hidden_to_heads(projected_query, config)


def _reshape_hidden_to_heads(
    hidden_tensor: torch.Tensor,
    config: opt_assets.OptConfig,
) -> torch.Tensor:
    return (
        hidden_tensor.reshape(
            DECODE_BATCH_SIZE,
            1,
            config.num_attention_heads,
            config.head_dim,
        )
        .permute(2, 0, 1, 3)
        .reshape(config.num_attention_heads, 1, config.head_dim)
    )


def _flatten_heads_to_hidden(context_tensor: torch.Tensor) -> torch.Tensor:
    return context_tensor.permute(1, 0, 2).reshape(DECODE_BATCH_SIZE, 1, -1)


def _build_kv_cache(
    config: opt_assets.OptConfig,
    sequence_length: int,
    *,
    device: torch.device,
    dtype: torch.dtype,
) -> tuple[torch.Tensor, torch.Tensor]:
    cache_shape = (config.num_attention_heads, int(sequence_length), config.head_dim)
    k_cache = _make_deterministic_fp16_tensor(
        cache_shape,
        seed=_DEFAULT_INPUT_SEED_BASE
        + _KV_CACHE_KEY_SEED_OFFSET
        + int(sequence_length),
        device=device,
    ).to(dtype=dtype)
    v_cache = _make_deterministic_fp16_tensor(
        cache_shape,
        seed=_DEFAULT_INPUT_SEED_BASE
        + _KV_CACHE_VALUE_SEED_OFFSET
        + int(sequence_length),
        device=device,
    ).to(dtype=dtype)
    return k_cache, v_cache


def _make_deterministic_fp16_tensor(
    shape: Sequence[int],
    *,
    seed: int,
    device: torch.device,
) -> torch.Tensor:
    generator = torch.Generator(device="cpu")
    generator.manual_seed(int(seed))
    tensor = torch.empty(
        tuple(int(dimension) for dimension in shape), dtype=torch.float16
    )
    tensor.uniform_(-0.125, 0.125, generator=generator)
    return tensor.to(device=device, dtype=torch.float16)


def _collect_blockwise_attention_stats(
    query: torch.Tensor,
    k_cache: torch.Tensor,
    v_cache: torch.Tensor,
    block_size: int,
) -> tuple[AttentionBlockStats, ...]:
    if int(block_size) <= 0:
        raise ValueError("block_size must be > 0")

    sequence_length = int(k_cache.shape[1])
    scale = 1.0 / math.sqrt(int(query.shape[-1]))
    block_stats: list[AttentionBlockStats] = []
    for block_start in range(0, sequence_length, int(block_size)):
        block_end = min(block_start + int(block_size), sequence_length)
        k_block = k_cache[:, block_start:block_end, :]
        v_block = v_cache[:, block_start:block_end, :]
        scores = torch.matmul(query, k_block.transpose(-2, -1)) * scale
        max_scores = torch.max(scores, dim=-1, keepdim=True).values
        exp_scores = torch.exp(scores - max_scores)
        exp_sums = torch.sum(exp_scores, dim=-1, keepdim=True)
        weighted_values = torch.matmul(exp_scores, v_block)
        block_stats.append(
            AttentionBlockStats(
                max_scores=max_scores,
                exp_sums=exp_sums,
                weighted_values=weighted_values,
            )
        )
    return tuple(block_stats)


def _reduce_blockwise_attention_stats(
    block_stats: Sequence[AttentionBlockStats],
) -> torch.Tensor:
    if not block_stats:
        raise ValueError("block_stats must contain at least one block")

    global_max = (
        torch.stack([block.max_scores for block in block_stats], dim=0)
        .max(dim=0)
        .values
    )
    global_exp_sum = torch.zeros_like(block_stats[0].exp_sums)
    global_weighted_values = torch.zeros_like(block_stats[0].weighted_values)
    for block in block_stats:
        alpha = torch.exp(block.max_scores - global_max)
        global_exp_sum = global_exp_sum + (block.exp_sums * alpha)
        global_weighted_values = global_weighted_values + (
            block.weighted_values * alpha
        )

    context = global_weighted_values / global_exp_sum.clamp_min(
        torch.finfo(global_exp_sum.dtype).tiny
    )
    return _flatten_heads_to_hidden(context)


def _block_stats_output_bytes(block_stats: Sequence[AttentionBlockStats]) -> int:
    return sum(block.output_bytes for block in block_stats)


def _collect_full_attention_tensors(
    query: torch.Tensor,
    k_cache: torch.Tensor,
    v_cache: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    scale = 1.0 / math.sqrt(int(query.shape[-1]))
    scores = torch.matmul(query, k_cache.transpose(-2, -1)) * scale
    probabilities = torch.nn.functional.softmax(scores, dim=-1)
    weighted_values = torch.matmul(probabilities, v_cache)
    return scores, probabilities, weighted_values


def _full_attention_fetch_output_bytes(
    scores: torch.Tensor,
    probabilities: torch.Tensor,
    weighted_values: torch.Tensor,
) -> int:
    return int(
        (scores.numel() * scores.element_size())
        + (probabilities.numel() * probabilities.element_size())
        + (weighted_values.numel() * weighted_values.element_size())
    )


def _reduce_full_attention(weighted_values: torch.Tensor) -> torch.Tensor:
    return _flatten_heads_to_hidden(weighted_values)


def _run_linear_warmup(
    module: Any,
    input_tensor: torch.Tensor,
    warmup_iterations: int,
    *,
    device: torch.device,
) -> None:
    for _ in range(warmup_iterations):
        output = module(input_tensor)
        del output
    torch.cuda.synchronize(device)


def _run_attention_warmup(
    query: torch.Tensor,
    kv_cache: tuple[torch.Tensor, torch.Tensor],
    block_size: int,
    warmup_iterations: int,
    *,
    device: torch.device,
) -> None:
    del block_size
    k_cache, v_cache = kv_cache
    for _ in range(warmup_iterations):
        scores, probabilities, weighted_values = _collect_full_attention_tensors(
            query,
            k_cache,
            v_cache,
        )
        output = _reduce_full_attention(weighted_values)
        del output
        del scores
        del probabilities
        del weighted_values
    torch.cuda.synchronize(device)


def _time_linear_op(
    *,
    model_id: str,
    sequence_length: int,
    block_size: int,
    op_name: str,
    timed_iteration: int,
    module: Any,
    input_tensor: torch.Tensor,
    device: torch.device,
    sm_ai_partition: int,
) -> dict[str, int | float | str]:
    torch.cuda.synchronize(device)
    torch.cuda.reset_peak_memory_stats(device)
    baseline_vram_bytes = int(torch.cuda.memory_allocated(device))

    start_event = torch.cuda.Event(enable_timing=True)
    end_event = torch.cuda.Event(enable_timing=True)
    start_event.record()
    output = module(input_tensor)
    end_event.record()

    torch.cuda.synchronize(device)
    duration_us = float(start_event.elapsed_time(end_event) * 1_000.0)
    peak_vram_bytes = int(torch.cuda.max_memory_allocated(device))
    output_bytes = int(output.numel() * output.element_size())
    del output

    return {
        "model_id": model_id,
        "sequence_length": int(sequence_length),
        "block_size": int(block_size),
        "op_type": DECODE_GEMV_OP_TYPE,
        "op_name": op_name,
        "sm_ai_partition": int(sm_ai_partition),
        "timed_iteration": int(timed_iteration),
        "duration_us": duration_us,
        "baseline_vram_bytes": baseline_vram_bytes,
        "peak_vram_bytes": peak_vram_bytes,
        "dynamic_workspace_bytes": peak_vram_bytes - baseline_vram_bytes,
        "output_bytes": output_bytes,
    }


def _time_attention_iteration(
    *,
    model_id: str,
    sequence_length: int,
    block_size: int,
    timed_iteration: int,
    query: torch.Tensor,
    kv_cache: tuple[torch.Tensor, torch.Tensor],
    device: torch.device,
    sm_ai_partition: int,
) -> tuple[dict[str, int | float | str], dict[str, int | float | str]]:
    block_size_value = int(block_size)
    k_cache, v_cache = kv_cache

    torch.cuda.synchronize(device)
    torch.cuda.reset_peak_memory_stats(device)
    fetch_baseline_vram_bytes = int(torch.cuda.memory_allocated(device))

    fetch_start_event = torch.cuda.Event(enable_timing=True)
    fetch_end_event = torch.cuda.Event(enable_timing=True)
    fetch_start_event.record()
    scores, probabilities, weighted_values = _collect_full_attention_tensors(
        query,
        k_cache,
        v_cache,
    )
    fetch_end_event.record()

    torch.cuda.synchronize(device)
    fetch_duration_us = float(fetch_start_event.elapsed_time(fetch_end_event) * 1_000.0)
    fetch_peak_vram_bytes = int(torch.cuda.max_memory_allocated(device))
    fetch_output_bytes = _full_attention_fetch_output_bytes(
        scores,
        probabilities,
        weighted_values,
    )

    torch.cuda.reset_peak_memory_stats(device)
    reduction_baseline_vram_bytes = int(torch.cuda.memory_allocated(device))

    reduction_start_event = torch.cuda.Event(enable_timing=True)
    reduction_end_event = torch.cuda.Event(enable_timing=True)
    reduction_start_event.record()
    reduced_output = _reduce_full_attention(weighted_values)
    reduction_end_event.record()

    torch.cuda.synchronize(device)
    reduction_duration_us = float(
        reduction_start_event.elapsed_time(reduction_end_event) * 1_000.0
    )
    reduction_peak_vram_bytes = int(torch.cuda.max_memory_allocated(device))
    reduction_output_bytes = int(reduced_output.numel() * reduced_output.element_size())
    del reduced_output
    del scores
    del probabilities
    del weighted_values

    attention_row = {
        "model_id": model_id,
        "sequence_length": int(sequence_length),
        "block_size": block_size_value,
        "op_type": DECODE_ATTENTION_FETCH_COMPUTE_OP_TYPE,
        "op_name": "",
        "sm_ai_partition": int(sm_ai_partition),
        "timed_iteration": int(timed_iteration),
        "duration_us": fetch_duration_us,
        "baseline_vram_bytes": fetch_baseline_vram_bytes,
        "peak_vram_bytes": fetch_peak_vram_bytes,
        "dynamic_workspace_bytes": fetch_peak_vram_bytes - fetch_baseline_vram_bytes,
        "output_bytes": fetch_output_bytes,
    }
    reduction_row = {
        "model_id": model_id,
        "sequence_length": int(sequence_length),
        "block_size": int(block_size),
        "op_type": DECODE_REDUCTION_OVERHEAD_OP_TYPE,
        "op_name": "",
        "sm_ai_partition": int(sm_ai_partition),
        "timed_iteration": int(timed_iteration),
        "duration_us": reduction_duration_us,
        "baseline_vram_bytes": reduction_baseline_vram_bytes,
        "peak_vram_bytes": reduction_peak_vram_bytes,
        "dynamic_workspace_bytes": reduction_peak_vram_bytes
        - reduction_baseline_vram_bytes,
        "output_bytes": reduction_output_bytes,
    }
    return attention_row, reduction_row


def _normalize_sm_ai_partition(sm_ai_partition: int) -> int:
    resolved = int(sm_ai_partition)
    if resolved <= 0 or resolved > 100:
        raise ValueError("sm_ai_partition must be between 1 and 100")
    return resolved


__all__ = [
    "AttentionBlockStats",
    "DECODE_ATTENTION_FETCH_COMPUTE_OP_TYPE",
    "DECODE_BATCH_SIZE",
    "DECODE_BLOCK_SIZES",
    "DECODE_DTYPE_NAME",
    "DECODE_EVENT_FIELDNAMES",
    "DECODE_EVENTS_FILENAME",
    "DECODE_GEMV_OP_TYPE",
    "DECODE_OP_NAMES",
    "DECODE_REDUCTION_OVERHEAD_OP_TYPE",
    "DecodeProfileResult",
    "estimate_decode_parked_activation_bytes",
    "profile_decode_sweep",
    "profile_decode_with_writer",
    "resolve_decode_output_path",
    "resolve_opt_config",
]
