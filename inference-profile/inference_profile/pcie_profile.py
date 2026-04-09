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

PCIE_EVENTS_FILENAME = "pcie_events.csv"
PCIE_DTYPE_NAME = "float16"
PCIE_EVENT_FIELDNAMES = (
    "model_id",
    "block_size",
    "kv_block_bytes",
    "transfer_only_us",
    "overlap_total_us",
    "dummy_compute_us",
    "exposed_transfer_us",
    "timed_iteration",
)
_DEFAULT_INPUT_SEED_BASE = 3_000
_PCIE_REASON = "pcie_microbenchmark"


@dataclass(frozen=True)
class PcieProfileResult:
    model_id: str
    raw_output_path: Path
    row_count: int


def resolve_pcie_output_path(
    *,
    output_root: str | Path | None = None,
    raw_output_path: str | Path | None = None,
) -> Path:
    if raw_output_path is not None:
        return Path(raw_output_path)
    resolved_output_root = Path(output_root) if output_root is not None else Path(".")
    return resolved_output_root / "raw" / PCIE_EVENTS_FILENAME


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


def calculate_kv_block_bytes(
    block_size: int,
    num_attention_heads: int,
    head_dim: int,
) -> int:
    """Calculate bytes for one K/V block (both K and V, FP16)."""
    # K block: [num_heads, block_size, head_dim] in FP16
    # V block: [num_heads, block_size, head_dim] in FP16
    # Total: 2 * num_heads * block_size * head_dim * 2 bytes (FP16 = 2 bytes)
    return 2 * num_attention_heads * block_size * head_dim * 2


def profile_pcie_sweep(
    *,
    model_id: str,
    output_root: str | Path | None = None,
    raw_output_path: str | Path | None = None,
    block_sizes: Sequence[int] = PREFILL_CHUNK_SIZES,
    warmup_iterations: int = 3,
    timed_iterations: int = 5,
    gpu_id: int = 0,
    config_payload: Mapping[str, Any] | opt_assets.OptConfig | None = None,
    cache_root: str | Path | None = None,
) -> PcieProfileResult:
    resolved_output_path = resolve_pcie_output_path(
        output_root=output_root,
        raw_output_path=raw_output_path,
    )
    writer = RawCsvWriter(resolved_output_path, fieldnames=PCIE_EVENT_FIELDNAMES)
    try:
        result = profile_pcie_with_writer(
            model_id=model_id,
            raw_writer=writer,
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


def profile_pcie_with_writer(
    *,
    model_id: str,
    raw_writer: RawCsvWriter,
    block_sizes: Sequence[int] = PREFILL_CHUNK_SIZES,
    warmup_iterations: int = 3,
    timed_iterations: int = 5,
    gpu_id: int = 0,
    config_payload: Mapping[str, Any] | opt_assets.OptConfig | None = None,
    cache_root: str | Path | None = None,
) -> PcieProfileResult:
    if warmup_iterations < 0:
        raise ValueError("warmup_iterations must be >= 0")
    if timed_iterations <= 0:
        raise ValueError("timed_iterations must be > 0")

    resolved_block_sizes = _normalize_block_sizes(block_sizes)
    config = resolve_opt_config(
        model_id,
        config_payload=config_payload,
        cache_root=cache_root,
    )
    device = _require_cuda_device(gpu_id)
    torch_dtype = getattr(torch, PCIE_DTYPE_NAME)
    torch.cuda.set_device(device)

    with torch.inference_mode():
        for block_size in resolved_block_sizes:
            kv_block_bytes = calculate_kv_block_bytes(
                block_size, config.num_attention_heads, config.head_dim
            )

            # Profile transfer only
            for _ in range(warmup_iterations):
                _run_pcie_transfer_warmup(
                    block_size=block_size,
                    num_attention_heads=config.num_attention_heads,
                    head_dim=config.head_dim,
                    device=device,
                    dtype=torch_dtype,
                )

            for iteration in range(timed_iterations):
                transfer_only_us = _time_pcie_transfer_only(
                    block_size=block_size,
                    num_attention_heads=config.num_attention_heads,
                    head_dim=config.head_dim,
                    device=device,
                    dtype=torch_dtype,
                )

                # Profile overlapped transfer + compute
                overlap_total_us, dummy_compute_us = _time_pcie_overlap(
                    block_size=block_size,
                    num_attention_heads=config.num_attention_heads,
                    head_dim=config.head_dim,
                    hidden_size=config.hidden_size,
                    ffn_dim=config.ffn_dim,
                    device=device,
                    dtype=torch_dtype,
                )

                # Calculate exposed transfer time
                exposed_transfer_us = max(0.0, overlap_total_us - dummy_compute_us)

                row = {
                    "model_id": config.model_id,
                    "block_size": int(block_size),
                    "kv_block_bytes": int(kv_block_bytes),
                    "transfer_only_us": float(transfer_only_us),
                    "overlap_total_us": float(overlap_total_us),
                    "dummy_compute_us": float(dummy_compute_us),
                    "exposed_transfer_us": float(exposed_transfer_us),
                    "timed_iteration": int(iteration),
                }
                raw_writer.write_row(row)

    return PcieProfileResult(
        model_id=config.model_id,
        raw_output_path=Path(raw_writer.path)
        if raw_writer.path is not None
        else Path(),
        row_count=raw_writer.row_count,
    )


def _normalize_block_sizes(block_sizes: Sequence[int]) -> tuple[int, ...]:
    if not block_sizes:
        raise ValueError("block_sizes must contain at least one value")
    resolved = tuple(int(size) for size in block_sizes)
    invalid = [size for size in resolved if size <= 0]
    if invalid:
        raise ValueError("block_sizes must contain only positive integers")
    return resolved


def _require_cuda_device(gpu_id: int) -> torch.device:
    if not torch.cuda.is_available():
        raise RuntimeError(
            "PCIe profiling requires an available CUDA GPU"
        )
    return torch.device(f"cuda:{int(gpu_id)}")


def _run_pcie_transfer_warmup(
    *,
    block_size: int,
    num_attention_heads: int,
    head_dim: int,
    device: torch.device,
    dtype: torch.dtype,
) -> None:
    """Warmup PCIe transfer without timing."""
    kv_block_bytes = calculate_kv_block_bytes(block_size, num_attention_heads, head_dim)
    host_tensor = _allocate_pinned_host_tensor(
        kv_block_bytes // 2,  # FP16 is 2 bytes
        device=device,
        dtype=dtype,
    )
    try:
        transfer_stream = torch.cuda.Stream(device=device)
        with torch.cuda.stream(transfer_stream):
            _ = host_tensor.to(device=device, non_blocking=True)
        torch.cuda.synchronize(device)
    finally:
        torch.cuda.empty_cache()


def _time_pcie_transfer_only(
    *,
    block_size: int,
    num_attention_heads: int,
    head_dim: int,
    device: torch.device,
    dtype: torch.dtype,
) -> float:
    """Time H2D transfer only (no overlap)."""
    kv_block_bytes = calculate_kv_block_bytes(block_size, num_attention_heads, head_dim)
    host_tensor = _allocate_pinned_host_tensor(
        kv_block_bytes // 2,
        device="cpu",
        dtype=dtype,
    )

    torch.cuda.synchronize(device)
    torch.cuda.reset_peak_memory_stats(device)

    transfer_stream = torch.cuda.Stream(device=device)
    start_event = torch.cuda.Event(enable_timing=True, stream=transfer_stream)
    end_event = torch.cuda.Event(enable_timing=True, stream=transfer_stream)

    with torch.cuda.stream(transfer_stream):
        start_event.record()
        _ = host_tensor.to(device=device, non_blocking=True)
        end_event.record()

    torch.cuda.synchronize(device)
    transfer_only_us = float(start_event.elapsed_time(end_event) * 1_000.0)

    torch.cuda.empty_cache()
    return transfer_only_us


def _time_pcie_overlap(
    *,
    block_size: int,
    num_attention_heads: int,
    head_dim: int,
    hidden_size: int,
    ffn_dim: int,
    device: torch.device,
    dtype: torch.dtype,
) -> tuple[float, float]:
    """
    Time overlapped H2D transfer + compute.
    
    Returns: (overlap_total_us, dummy_compute_us)
    """
    kv_block_bytes = calculate_kv_block_bytes(block_size, num_attention_heads, head_dim)
    host_tensor = _allocate_pinned_host_tensor(
        kv_block_bytes // 2,
        device="cpu",
        dtype=dtype,
    )

    # Create dummy compute tensor (FC1-shaped GEMV: [1, hidden_size] x [hidden_size, ffn_dim])
    compute_input = torch.randn(
        1, hidden_size, device=device, dtype=dtype
    )
    compute_weight = torch.randn(
        ffn_dim, hidden_size, device=device, dtype=dtype
    )

    torch.cuda.synchronize(device)
    torch.cuda.reset_peak_memory_stats(device)

    transfer_stream = torch.cuda.Stream(device=device)
    compute_stream = torch.cuda.Stream(device=device)

    # Time overall elapsed (overlap)
    start_event = torch.cuda.Event(enable_timing=True)
    end_event = torch.cuda.Event(enable_timing=True)

    start_event.record()

    # Transfer on transfer stream
    with torch.cuda.stream(transfer_stream):
        _ = host_tensor.to(device=device, non_blocking=True)

    # Compute on compute stream
    compute_start = torch.cuda.Event(enable_timing=True, stream=compute_stream)
    compute_end = torch.cuda.Event(enable_timing=True, stream=compute_stream)

    with torch.cuda.stream(compute_stream):
        compute_start.record()
        _ = torch.matmul(compute_input, compute_weight.t())
        compute_end.record()

    end_event.record()

    torch.cuda.synchronize(device)

    overlap_total_us = float(start_event.elapsed_time(end_event) * 1_000.0)
    dummy_compute_us = float(compute_start.elapsed_time(compute_end) * 1_000.0)

    torch.cuda.empty_cache()
    return (overlap_total_us, dummy_compute_us)


def _allocate_pinned_host_tensor(
    num_elements: int,
    *,
    device: str | torch.device = "cpu",
    dtype: torch.dtype = torch.float16,
) -> torch.Tensor:
    """Allocate a pinned host tensor."""
    tensor = torch.empty(
        num_elements,
        dtype=dtype,
        device="cpu",
        pin_memory=True if device == "cpu" else False,
    )
    # Fill with deterministic values for realism
    generator = torch.Generator(device="cpu")
    generator.manual_seed(_DEFAULT_INPUT_SEED_BASE)
    tensor.uniform_(-0.125, 0.125, generator=generator)
    return tensor


__all__ = [
    "PCIE_DTYPE_NAME",
    "PCIE_EVENT_FIELDNAMES",
    "PCIE_EVENTS_FILENAME",
    "PcieProfileResult",
    "calculate_kv_block_bytes",
    "profile_pcie_sweep",
    "profile_pcie_with_writer",
    "resolve_opt_config",
    "resolve_pcie_output_path",
]
