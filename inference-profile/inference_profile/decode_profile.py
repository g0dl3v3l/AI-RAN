from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from huggingface_hub import hf_hub_download
import torch

from inference_profile import opt_assets
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
DECODE_BLOCK_SIZES = PREFILL_CHUNK_SIZES  # (64, 128, 256, 512, 1024)
DECODE_EVENT_FIELDNAMES = (
    "model_id",
    "sequence_length",
    "block_size",
    "op_type",
    "op_name",
    "timed_iteration",
    "duration_us",
    "baseline_vram_bytes",
    "peak_vram_bytes",
    "dynamic_workspace_bytes",
    "output_bytes",
)
_DEFAULT_INPUT_SEED_BASE = 2_000
_DECODE_REASON = "decode_microbenchmark"


@dataclass(frozen=True)
class DecodeLinearOp:
    op_name: str
    module: Any
    input_width: int
    output_width: int


@dataclass(frozen=True)
class DecodeProfileResult:
    model_id: str
    raw_output_path: Path
    row_count: int
    max_decode_workspace_bytes: int
    decode_parked_activation_bytes: int


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
    """Parked activation is the final [1,1,hidden_size] output size."""
    return (
        DECODE_BATCH_SIZE
        * 1
        * config.hidden_size
        * opt_assets.FP16_BYTES_PER_PARAMETER
    )


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
    config_payload: Mapping[str, Any] | opt_assets.OptConfig | None = None,
    cache_root: str | Path | None = None,
) -> DecodeProfileResult:
    if warmup_iterations < 0:
        raise ValueError("warmup_iterations must be >= 0")
    if timed_iterations <= 0:
        raise ValueError("timed_iterations must be > 0")

    resolved_sequence_lengths = _normalize_sequence_lengths(sequence_lengths)
    resolved_block_sizes = _normalize_block_sizes(block_sizes)
    config = resolve_opt_config(
        model_id,
        config_payload=config_payload,
        cache_root=cache_root,
    )
    device = _require_cuda_device(gpu_id)
    torch_dtype = getattr(torch, DECODE_DTYPE_NAME)
    torch.cuda.set_device(device)

    ops = _build_decode_linear_ops(config, device=device, dtype=torch_dtype)
    max_workspace_bytes = 0

    with torch.inference_mode():
        for seq_len in resolved_sequence_lengths:
            for block_size in resolved_block_sizes:
                # Profile the six linear ops on [1,1,hidden_size] inputs
                input_tensors = _build_decode_input_tensors(
                    config,
                    device=device,
                    dtype=torch_dtype,
                )

                for op in ops:
                    input_tensor = input_tensors[op.op_name]
                    _run_warmup(op.module, input_tensor, warmup_iterations, device=device)
                    for iteration in range(timed_iterations):
                        row = _time_linear_op(
                            model_id=config.model_id,
                            sequence_length=seq_len,
                            block_size=block_size,
                            op_type="gemv",
                            op_name=op.op_name,
                            timed_iteration=iteration,
                            module=op.module,
                            input_tensor=input_tensor,
                            device=device,
                        )
                        raw_writer.write_row(row)
                        workspace_bytes = int(row["dynamic_workspace_bytes"])
                        max_workspace_bytes = max(max_workspace_bytes, workspace_bytes)

                # Profile blockwise attention with separate timing buckets
                kv_cache = _build_kv_cache(
                    config,
                    sequence_length=seq_len,
                    device=device,
                    dtype=torch_dtype,
                )
                query = _make_deterministic_fp16_tensor(
                    (config.num_attention_heads, 1, config.head_dim),
                    seed=_DEFAULT_INPUT_SEED_BASE + seq_len + block_size,
                    device=device,
                )

                _run_warmup(
                    lambda q, k, v, bs: _blockwise_attention(q, k, v, bs),
                    (query, kv_cache, kv_cache, block_size),
                    warmup_iterations,
                    device=device,
                    is_lambda=True,
                )

                for iteration in range(timed_iterations):
                    # Time attention fetch+compute
                    row_attn = _time_blockwise_attention(
                        model_id=config.model_id,
                        sequence_length=seq_len,
                        block_size=block_size,
                        op_type="attention_fetch_compute",
                        timed_iteration=iteration,
                        query=query,
                        kv_cache=kv_cache,
                        device=device,
                    )
                    raw_writer.write_row(row_attn)
                    workspace_bytes = int(row_attn["dynamic_workspace_bytes"])
                    max_workspace_bytes = max(max_workspace_bytes, workspace_bytes)

                    # Time reduction overhead
                    row_reduce = _time_reduction_overhead(
                        model_id=config.model_id,
                        sequence_length=seq_len,
                        block_size=block_size,
                        timed_iteration=iteration,
                        query_head_dim=config.head_dim,
                        num_blocks=_calculate_num_blocks(seq_len, block_size),
                        device=device,
                    )
                    raw_writer.write_row(row_reduce)
                    workspace_bytes = int(row_reduce["dynamic_workspace_bytes"])
                    max_workspace_bytes = max(max_workspace_bytes, workspace_bytes)

    return DecodeProfileResult(
        model_id=config.model_id,
        raw_output_path=Path(raw_writer.path)
        if raw_writer.path is not None
        else Path(),
        row_count=raw_writer.row_count,
        max_decode_workspace_bytes=max_workspace_bytes,
        decode_parked_activation_bytes=estimate_decode_parked_activation_bytes(config),
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


def _calculate_num_blocks(sequence_length: int, block_size: int) -> int:
    """Calculate number of blocks needed to cover the sequence."""
    return (sequence_length + block_size - 1) // block_size


def _require_cuda_device(gpu_id: int) -> torch.device:
    if not torch.cuda.is_available():
        raise RuntimeError(
            "Decode CUDA-event profiling requires an available CUDA GPU"
        )
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
    """Build [1,1,hidden_size] or equivalent tensors for decode ops."""
    hidden_tensor = _make_deterministic_fp16_tensor(
        (DECODE_BATCH_SIZE, 1, config.hidden_size),
        seed=_DEFAULT_INPUT_SEED_BASE + 1,
        device=device,
    ).to(dtype=dtype)
    ffn_tensor = _make_deterministic_fp16_tensor(
        (DECODE_BATCH_SIZE, 1, config.ffn_dim),
        seed=_DEFAULT_INPUT_SEED_BASE + 10_000 + 1,
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


def _build_kv_cache(
    config: opt_assets.OptConfig,
    sequence_length: int,
    *,
    device: torch.device,
    dtype: torch.dtype,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Build KV cache shaped [num_heads, sequence_length, head_dim]."""
    cache_shape = (config.num_attention_heads, sequence_length, config.head_dim)
    k_cache = _make_deterministic_fp16_tensor(
        cache_shape,
        seed=_DEFAULT_INPUT_SEED_BASE + 100 + sequence_length,
        device=device,
    ).to(dtype=dtype)
    v_cache = _make_deterministic_fp16_tensor(
        cache_shape,
        seed=_DEFAULT_INPUT_SEED_BASE + 200 + sequence_length,
        device=device,
    ).to(dtype=dtype)
    return (k_cache, v_cache)


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


def _blockwise_attention(
    query: torch.Tensor,
    k_cache: torch.Tensor,
    v_cache: torch.Tensor,
    block_size: int,
) -> tuple[torch.Tensor, list[float], list[float], list[torch.Tensor]]:
    """
    Blockwise attention with per-block accumulation.
    
    Returns: (output, m_list, l_list, o_list) for reduction phase timing.
    """
    num_blocks = _calculate_num_blocks(k_cache.shape[1], block_size)
    head_dim = query.shape[-1]
    
    m_list: list[float] = []
    l_list: list[float] = []
    o_list: list[torch.Tensor] = []
    
    for block_idx in range(num_blocks):
        start = block_idx * block_size
        end = min(start + block_size, k_cache.shape[1])
        
        k_block = k_cache[:, start:end, :]  # [num_heads, block_len, head_dim]
        v_block = v_cache[:, start:end, :]  # [num_heads, block_len, head_dim]
        
        # Compute scores: query @ k_block^T / sqrt(d)
        scores = torch.matmul(query, k_block.transpose(-2, -1)) / (head_dim ** 0.5)
        
        # Per-block max (m_i) for numerical stability
        m_i = torch.max(scores)
        m_list.append(float(m_i))
        
        # Softmax weights with stability (l_i)
        softmax_weights = torch.exp(scores - m_i)
        l_i = torch.sum(softmax_weights)
        l_list.append(float(l_i))
        
        # Output accumulator (o_i)
        o_i = torch.matmul(softmax_weights, v_block)
        o_list.append(o_i)
    
    return (None, m_list, l_list, o_list)


def _run_warmup(
    func: Any,
    args: Any,
    warmup_iterations: int,
    *,
    device: torch.device,
    is_lambda: bool = False,
) -> None:
    if is_lambda:
        for _ in range(warmup_iterations):
            _ = func(*args)
    else:
        for _ in range(warmup_iterations):
            _ = func(args)
    torch.cuda.synchronize(device)


def _time_linear_op(
    *,
    model_id: str,
    sequence_length: int,
    block_size: int,
    op_type: str,
    op_name: str,
    timed_iteration: int,
    module: Any,
    input_tensor: torch.Tensor,
    device: torch.device,
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
        "op_type": op_type,
        "op_name": op_name,
        "timed_iteration": int(timed_iteration),
        "duration_us": duration_us,
        "baseline_vram_bytes": baseline_vram_bytes,
        "peak_vram_bytes": peak_vram_bytes,
        "dynamic_workspace_bytes": peak_vram_bytes - baseline_vram_bytes,
        "output_bytes": output_bytes,
    }


def _time_blockwise_attention(
    *,
    model_id: str,
    sequence_length: int,
    block_size: int,
    op_type: str,
    timed_iteration: int,
    query: torch.Tensor,
    kv_cache: tuple[torch.Tensor, torch.Tensor],
    device: torch.device,
) -> dict[str, int | float | str]:
    k_cache, v_cache = kv_cache
    
    torch.cuda.synchronize(device)
    torch.cuda.reset_peak_memory_stats(device)
    baseline_vram_bytes = int(torch.cuda.memory_allocated(device))

    start_event = torch.cuda.Event(enable_timing=True)
    end_event = torch.cuda.Event(enable_timing=True)
    start_event.record()
    output, _, _, _ = _blockwise_attention(query, k_cache, v_cache, block_size)
    end_event.record()

    torch.cuda.synchronize(device)
    duration_us = float(start_event.elapsed_time(end_event) * 1_000.0)
    peak_vram_bytes = int(torch.cuda.max_memory_allocated(device))

    return {
        "model_id": model_id,
        "sequence_length": int(sequence_length),
        "block_size": int(block_size),
        "op_type": op_type,
        "op_name": None,
        "timed_iteration": int(timed_iteration),
        "duration_us": duration_us,
        "baseline_vram_bytes": baseline_vram_bytes,
        "peak_vram_bytes": peak_vram_bytes,
        "dynamic_workspace_bytes": peak_vram_bytes - baseline_vram_bytes,
        "output_bytes": 0,
    }


def _time_reduction_overhead(
    *,
    model_id: str,
    sequence_length: int,
    block_size: int,
    timed_iteration: int,
    query_head_dim: int,
    num_blocks: int,
    device: torch.device,
) -> dict[str, int | float | str]:
    """Time the final reduction pass combining per-block accumulators."""
    torch.cuda.synchronize(device)
    torch.cuda.reset_peak_memory_stats(device)
    baseline_vram_bytes = int(torch.cuda.memory_allocated(device))

    # Create mock per-block accumulators for reduction timing
    m_list = [float(i) for i in range(num_blocks)]
    l_list = [float(i + 1) for i in range(num_blocks)]
    o_list = [torch.randn(1, query_head_dim, device=device, dtype=torch.float16) 
              for _ in range(num_blocks)]

    start_event = torch.cuda.Event(enable_timing=True)
    end_event = torch.cuda.Event(enable_timing=True)
    start_event.record()

    # Reduction: combine block statistics
    m_global = max(m_list)
    o_global = torch.zeros_like(o_list[0])
    l_global = 0.0
    for i in range(num_blocks):
        alpha_i = torch.exp(torch.tensor(m_list[i] - m_global, device=device, dtype=torch.float16))
        l_global += l_list[i] * float(alpha_i)
        o_global += o_list[i] * alpha_i

    output = o_global / (l_global + 1e-8)
    del output, o_global, o_list

    end_event.record()

    torch.cuda.synchronize(device)
    duration_us = float(start_event.elapsed_time(end_event) * 1_000.0)
    peak_vram_bytes = int(torch.cuda.max_memory_allocated(device))

    return {
        "model_id": model_id,
        "sequence_length": int(sequence_length),
        "block_size": int(block_size),
        "op_type": "reduction_overhead",
        "op_name": None,
        "timed_iteration": int(timed_iteration),
        "duration_us": duration_us,
        "baseline_vram_bytes": baseline_vram_bytes,
        "peak_vram_bytes": peak_vram_bytes,
        "dynamic_workspace_bytes": peak_vram_bytes - baseline_vram_bytes,
        "output_bytes": 0,
    }


__all__ = [
    "DECODE_BATCH_SIZE",
    "DECODE_BLOCK_SIZES",
    "DECODE_DTYPE_NAME",
    "DECODE_EVENT_FIELDNAMES",
    "DECODE_EVENTS_FILENAME",
    "DECODE_OP_NAMES",
    "DecodeProfileResult",
    "estimate_decode_parked_activation_bytes",
    "profile_decode_sweep",
    "profile_decode_with_writer",
    "resolve_decode_output_path",
    "resolve_opt_config",
]
