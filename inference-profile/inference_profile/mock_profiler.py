"""Mock profiler for CPU-only testing environments."""

from pathlib import Path
from typing import Sequence
from inference_profile.worker_profile_point import RawCsvWriter

# Raw event column names (as expected by profile_reducer)
PREFILL_EVENT_FIELDNAMES = (
    "model_id",
    "chunk_tokens",
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

PCIE_EVENT_FIELDNAMES = (
    "model_id",
    "block_size",
    "kv_block_bytes",
    "transfer_only_us",
    "overlap_total_us",
    "dummy_compute_us",
    "exposed_transfer_us",
)


def generate_mock_prefill_events(
    model_id: str,
    output_path: str | Path,
    chunk_tokens: Sequence[int] = (64, 128, 256),
) -> int:
    """Generate mock prefill profiling events for testing."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    writer = RawCsvWriter(output_path, fieldnames=PREFILL_EVENT_FIELDNAMES)
    row_count = 0

    for chunk in chunk_tokens:
        base_us = 100 * (1 + chunk // 64)

        writer.write_row(
            {
                "model_id": model_id,
                "chunk_tokens": chunk,
                "op_type": "gemm",
                "op_name": "fc1",
                "sm_ai_partition": 100,
                "timed_iteration": 0,
                "duration_us": base_us,
                "baseline_vram_bytes": 2 * 1024 * 1024,
                "peak_vram_bytes": 2 * 1024 * 1024 + 1024 * 1024 * (1 + chunk // 128),
                "dynamic_workspace_bytes": 1024 * 1024 * (1 + chunk // 128),
                "output_bytes": 512 * 1024 * chunk // 64,
            }
        )
        row_count += 1

        writer.write_row(
            {
                "model_id": model_id,
                "chunk_tokens": chunk,
                "op_type": "attention",
                "op_name": "attention",
                "sm_ai_partition": 100,
                "timed_iteration": 0,
                "duration_us": base_us * 0.8,
                "baseline_vram_bytes": 2 * 1024 * 1024,
                "peak_vram_bytes": 2 * 1024 * 1024 + 768 * 1024,
                "dynamic_workspace_bytes": 768 * 1024,
                "output_bytes": 256 * 1024 * chunk // 64,
            }
        )
        row_count += 1

    writer.close()
    return row_count


def generate_mock_decode_events(
    model_id: str,
    output_path: str | Path,
    sequence_lengths: Sequence[int] = (1024, 2048, 4096),
    chunk_sizes: Sequence[int] = (64, 128, 256),
) -> int:
    """Generate mock decode profiling events for testing."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    writer = RawCsvWriter(output_path, fieldnames=DECODE_EVENT_FIELDNAMES)
    row_count = 0

    op_specs = [
        ("gemv", "q_proj"),
        ("gemv", "out_proj"),
        ("gemv", "fc1"),
        ("gemv", "fc2"),
        ("attention_fetch_compute", ""),
        ("reduction_overhead", ""),
    ]

    for seq_len in sequence_lengths:
        for block_size in chunk_sizes:
            for op_type, op_name in op_specs:
                if op_type == "gemv":
                    duration_us = 50 + (seq_len // 512) * 10 + (block_size // 64) * 5
                elif op_type == "attention_fetch_compute":
                    duration_us = 30 + (seq_len // 1024) * 5
                else:  # reduction_overhead
                    duration_us = 10 + (seq_len // 1024) * 2

                writer.write_row(
                    {
                        "model_id": model_id,
                        "sequence_length": seq_len,
                        "block_size": block_size,
                        "op_type": op_type,
                        "op_name": op_name,
                        "sm_ai_partition": 100,
                        "timed_iteration": 0,
                        "duration_us": duration_us,
                        "baseline_vram_bytes": 1024 * 1024,
                        "peak_vram_bytes": 1024 * 1024 + 512 * 1024,
                        "dynamic_workspace_bytes": 512 * 1024,
                        "output_bytes": 256 * 1024 * (seq_len // 1024),
                    }
                )
                row_count += 1

    writer.close()
    return row_count


def generate_mock_pcie_events(
    model_id: str,
    output_path: str | Path,
    chunk_sizes: Sequence[int] = (64, 128, 256),
) -> int:
    """Generate mock PCIe profiling events for testing."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    writer = RawCsvWriter(output_path, fieldnames=PCIE_EVENT_FIELDNAMES)
    row_count = 0

    for block_size in chunk_sizes:
        # Mock PCIe metrics
        kv_block_bytes = 16 * 1024 * block_size  # 16KB per token
        transfer_only_us = 100 + (block_size // 64) * 20
        overlap_total_us = 150 + (block_size // 64) * 30
        dummy_compute_us = 50  # Fixed overhead
        exposed_transfer_us = (
            transfer_only_us - 20 if transfer_only_us > 20 else 0
        )  # Some overlap

        writer.write_row(
            {
                "model_id": model_id,
                "block_size": block_size,
                "kv_block_bytes": kv_block_bytes,
                "transfer_only_us": transfer_only_us,
                "overlap_total_us": overlap_total_us,
                "dummy_compute_us": dummy_compute_us,
                "exposed_transfer_us": exposed_transfer_us,
            }
        )
        row_count += 1

    writer.close()
    return row_count


__all__ = [
    "generate_mock_prefill_events",
    "generate_mock_decode_events",
    "generate_mock_pcie_events",
]
