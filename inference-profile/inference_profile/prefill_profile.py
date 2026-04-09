from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from huggingface_hub import hf_hub_download
import torch

from inference_profile import opt_assets
from inference_profile.constants import PREFILL_CHUNK_SIZES
from inference_profile.worker_profile_point import RawCsvWriter

PREFILL_EVENTS_FILENAME = "prefill_events.csv"
PREFILL_BATCH_SIZE = 1
PREFILL_DTYPE_NAME = "float16"
PREFILL_OP_NAMES = (
    "q_proj",
    "k_proj",
    "v_proj",
    "out_proj",
    "fc1",
    "fc2",
)
PREFILL_EVENT_FIELDNAMES = (
    "model_id",
    "chunk_tokens",
    "op_name",
    "timed_iteration",
    "duration_us",
    "baseline_vram_bytes",
    "peak_vram_bytes",
    "dynamic_workspace_bytes",
    "output_bytes",
)
_DEFAULT_INPUT_SEED_BASE = 1_000
_PREFILL_REASON = "prefill_microbenchmark"


@dataclass(frozen=True)
class PrefillLinearOp:
    op_name: str
    module: Any
    input_width: int
    output_width: int


@dataclass(frozen=True)
class PrefillProfileResult:
    model_id: str
    raw_output_path: Path
    row_count: int
    parked_activation_bytes_by_chunk: dict[int, int]


def resolve_prefill_output_path(
    *,
    output_root: str | Path | None = None,
    raw_output_path: str | Path | None = None,
) -> Path:
    if raw_output_path is not None:
        return Path(raw_output_path)
    resolved_output_root = Path(output_root) if output_root is not None else Path(".")
    return resolved_output_root / "raw" / PREFILL_EVENTS_FILENAME


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


def build_prefill_output_byte_map(
    config: opt_assets.OptConfig,
    chunk_tokens: int,
) -> dict[str, int]:
    resolved_chunk_tokens = _normalize_chunk_tokens((chunk_tokens,))[0]
    hidden_bytes = (
        PREFILL_BATCH_SIZE
        * resolved_chunk_tokens
        * config.hidden_size
        * opt_assets.FP16_BYTES_PER_PARAMETER
    )
    fc1_bytes = (
        PREFILL_BATCH_SIZE
        * resolved_chunk_tokens
        * config.ffn_dim
        * opt_assets.FP16_BYTES_PER_PARAMETER
    )
    return {
        "q_proj": hidden_bytes,
        "k_proj": hidden_bytes,
        "v_proj": hidden_bytes,
        "out_proj": hidden_bytes,
        "fc1": fc1_bytes,
        "fc2": hidden_bytes,
    }


def estimate_prefill_parked_activation_bytes(
    config: opt_assets.OptConfig,
    chunk_tokens: int,
) -> int:
    output_bytes_by_op = build_prefill_output_byte_map(config, chunk_tokens)
    return max(output_bytes_by_op.values())


def largest_prefill_activation_op(
    config: opt_assets.OptConfig,
    chunk_tokens: int,
) -> str:
    output_bytes_by_op = build_prefill_output_byte_map(config, chunk_tokens)
    return max(PREFILL_OP_NAMES, key=lambda op_name: output_bytes_by_op[op_name])


def profile_prefill_sweep(
    *,
    model_id: str,
    output_root: str | Path | None = None,
    raw_output_path: str | Path | None = None,
    chunk_tokens: Sequence[int] = PREFILL_CHUNK_SIZES,
    warmup_iterations: int = 3,
    timed_iterations: int = 5,
    gpu_id: int = 0,
    config_payload: Mapping[str, Any] | opt_assets.OptConfig | None = None,
    cache_root: str | Path | None = None,
) -> PrefillProfileResult:
    resolved_output_path = resolve_prefill_output_path(
        output_root=output_root,
        raw_output_path=raw_output_path,
    )
    writer = RawCsvWriter(resolved_output_path, fieldnames=PREFILL_EVENT_FIELDNAMES)
    try:
        result = profile_prefill_with_writer(
            model_id=model_id,
            raw_writer=writer,
            chunk_tokens=chunk_tokens,
            warmup_iterations=warmup_iterations,
            timed_iterations=timed_iterations,
            gpu_id=gpu_id,
            config_payload=config_payload,
            cache_root=cache_root,
        )
    finally:
        writer.close()
    return result


def profile_prefill_with_writer(
    *,
    model_id: str,
    raw_writer: RawCsvWriter,
    chunk_tokens: Sequence[int] = PREFILL_CHUNK_SIZES,
    warmup_iterations: int = 3,
    timed_iterations: int = 5,
    gpu_id: int = 0,
    config_payload: Mapping[str, Any] | opt_assets.OptConfig | None = None,
    cache_root: str | Path | None = None,
) -> PrefillProfileResult:
    if warmup_iterations < 0:
        raise ValueError("warmup_iterations must be >= 0")
    if timed_iterations <= 0:
        raise ValueError("timed_iterations must be > 0")

    resolved_chunk_tokens = _normalize_chunk_tokens(chunk_tokens)
    config = resolve_opt_config(
        model_id,
        config_payload=config_payload,
        cache_root=cache_root,
    )
    device = _require_cuda_device(gpu_id)
    torch_dtype = getattr(torch, PREFILL_DTYPE_NAME)
    torch.cuda.set_device(device)

    ops = _build_prefill_linear_ops(config, device=device, dtype=torch_dtype)
    parked_activation_bytes_by_chunk: dict[int, int] = {}

    with torch.inference_mode():
        for chunk in resolved_chunk_tokens:
            input_tensors = _build_input_tensors(
                config,
                chunk_tokens=chunk,
                device=device,
                dtype=torch_dtype,
            )
            parked_activation_bytes_by_chunk[chunk] = (
                estimate_prefill_parked_activation_bytes(
                    config,
                    chunk,
                )
            )
            for op in ops:
                input_tensor = input_tensors[op.op_name]
                _run_warmup(op.module, input_tensor, warmup_iterations, device=device)
                for iteration in range(timed_iterations):
                    row = _time_linear_op(
                        model_id=config.model_id,
                        chunk_tokens=chunk,
                        op_name=op.op_name,
                        timed_iteration=iteration,
                        module=op.module,
                        input_tensor=input_tensor,
                        device=device,
                    )
                    raw_writer.write_row(row)

    return PrefillProfileResult(
        model_id=config.model_id,
        raw_output_path=Path(raw_writer.path)
        if raw_writer.path is not None
        else Path(),
        row_count=raw_writer.row_count,
        parked_activation_bytes_by_chunk=parked_activation_bytes_by_chunk,
    )


def _normalize_chunk_tokens(chunk_tokens: Sequence[int]) -> tuple[int, ...]:
    if not chunk_tokens:
        raise ValueError("chunk_tokens must contain at least one value")
    resolved = tuple(int(chunk) for chunk in chunk_tokens)
    invalid = [chunk for chunk in resolved if chunk <= 0]
    if invalid:
        raise ValueError("chunk_tokens must contain only positive integers")
    return resolved


def _require_cuda_device(gpu_id: int) -> torch.device:
    if not torch.cuda.is_available():
        raise RuntimeError(
            "Prefill CUDA-event profiling requires an available CUDA GPU"
        )
    return torch.device(f"cuda:{int(gpu_id)}")


def _build_prefill_linear_ops(
    config: opt_assets.OptConfig,
    *,
    device: torch.device,
    dtype: torch.dtype,
) -> tuple[PrefillLinearOp, ...]:
    layer_index = opt_assets.select_middle_layer_index(config.num_hidden_layers)
    synthetic_layer = opt_assets.build_synthetic_layer_metadata(
        config,
        layer_index=layer_index,
        reason=_PREFILL_REASON,
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
        PrefillLinearOp(
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


def _build_input_tensors(
    config: opt_assets.OptConfig,
    *,
    chunk_tokens: int,
    device: torch.device,
    dtype: torch.dtype,
) -> dict[str, torch.Tensor]:
    hidden_tensor = _make_deterministic_fp16_tensor(
        (PREFILL_BATCH_SIZE, chunk_tokens, config.hidden_size),
        seed=_DEFAULT_INPUT_SEED_BASE + chunk_tokens,
        device=device,
    ).to(dtype=dtype)
    ffn_tensor = _make_deterministic_fp16_tensor(
        (PREFILL_BATCH_SIZE, chunk_tokens, config.ffn_dim),
        seed=_DEFAULT_INPUT_SEED_BASE + 10_000 + chunk_tokens,
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


def _run_warmup(
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


def _time_linear_op(
    *,
    model_id: str,
    chunk_tokens: int,
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
        "chunk_tokens": int(chunk_tokens),
        "op_name": op_name,
        "timed_iteration": int(timed_iteration),
        "duration_us": duration_us,
        "baseline_vram_bytes": baseline_vram_bytes,
        "peak_vram_bytes": peak_vram_bytes,
        "dynamic_workspace_bytes": peak_vram_bytes - baseline_vram_bytes,
        "output_bytes": output_bytes,
    }


__all__ = [
    "PREFILL_BATCH_SIZE",
    "PREFILL_DTYPE_NAME",
    "PREFILL_EVENT_FIELDNAMES",
    "PREFILL_EVENTS_FILENAME",
    "PREFILL_OP_NAMES",
    "PrefillProfileResult",
    "build_prefill_output_byte_map",
    "estimate_prefill_parked_activation_bytes",
    "largest_prefill_activation_op",
    "profile_prefill_sweep",
    "profile_prefill_with_writer",
    "resolve_opt_config",
    "resolve_prefill_output_path",
]
