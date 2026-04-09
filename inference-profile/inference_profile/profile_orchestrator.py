from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any

from inference_profile import (
    decode_profile,
    manifests,
    opt_assets,
    paths,
    pcie_profile,
    prefill_profile,
    profile_reducer,
    worker_profile_point,
)
from inference_profile.constants import (
    DECODE_SEQUENCE_LENGTHS,
    PREFILL_CHUNK_SIZES,
)


@dataclass(frozen=True)
class ProfileOrchestratorResult:
    """Result of orchestrating a profiling run."""
    run_root: Path
    success: bool
    row_counts: dict[str, int]


def orchestrate_profile_run(
    *,
    run_root: str | Path,
    models: Sequence[str],
    chunk_sizes: Sequence[int] = PREFILL_CHUNK_SIZES,
    sequence_lengths: Sequence[int] = DECODE_SEQUENCE_LENGTHS,
    warmup_iterations: int = 3,
    timed_iterations: int = 5,
    gpu_id: int = 0,
    cache_root: str | Path | None = None,
) -> ProfileOrchestratorResult:
    """
    Orchestrate complete profiling run: prefill, decode, PCIe, and reduction.
    
    This is the main entry point for the `profile` CLI stage.
    """
    run_root = Path(run_root)
    run_root.mkdir(parents=True, exist_ok=True)

    # Load or initialize manifest
    manifest_path = run_root / "run_manifest.json"
    manifest = manifests.load_run_manifest(manifest_path)

    try:
        # Resolve models
        normalized_models = tuple(opt_assets.normalize_model_id(m) for m in models)

        # Profile each model
        total_prefill_rows = 0
        total_decode_rows = 0
        total_pcie_rows = 0
        failed_prefill = 0
        failed_decode = 0
        failed_pcie = 0

        for model_id in normalized_models:
            # Prefill profiling
            prefill_result = _run_prefill_profiling(
                model_id=model_id,
                run_root=run_root,
                chunk_sizes=chunk_sizes,
                warmup_iterations=warmup_iterations,
                timed_iterations=timed_iterations,
                gpu_id=gpu_id,
                cache_root=cache_root,
            )
            if prefill_result is not None:
                total_prefill_rows += prefill_result.row_count
            else:
                failed_prefill += 1

            # Decode profiling
            decode_result = _run_decode_profiling(
                model_id=model_id,
                run_root=run_root,
                sequence_lengths=sequence_lengths,
                chunk_sizes=chunk_sizes,
                warmup_iterations=warmup_iterations,
                timed_iterations=timed_iterations,
                gpu_id=gpu_id,
                cache_root=cache_root,
            )
            if decode_result is not None:
                total_decode_rows += decode_result.row_count
            else:
                failed_decode += 1

            # PCIe profiling
            pcie_result = _run_pcie_profiling(
                model_id=model_id,
                run_root=run_root,
                block_sizes=chunk_sizes,
                warmup_iterations=warmup_iterations,
                timed_iterations=timed_iterations,
                gpu_id=gpu_id,
                cache_root=cache_root,
            )
            if pcie_result is not None:
                total_pcie_rows += pcie_result.row_count
            else:
                failed_pcie += 1

        # Reduce raw events to summaries
        reduction_result = profile_reducer.reduce_profile_events(run_root=run_root)

        # Update manifest with results
        manifests.update_stage_status(
            manifest_path,
            stage="profile",
            status="success",
            details={
                "models_profiled": len(normalized_models),
                "prefill_rows": total_prefill_rows,
                "decode_rows": total_decode_rows,
                "pcie_rows": total_pcie_rows,
                "prefill_failed": failed_prefill,
                "decode_failed": failed_decode,
                "pcie_failed": failed_pcie,
                "summary_rows": {
                    "prefill": reduction_result.prefill_row_count,
                    "decode": reduction_result.decode_row_count,
                    "pcie": reduction_result.pcie_row_count,
                },
            },
        )

        return ProfileOrchestratorResult(
            run_root=run_root,
            success=True,
            row_counts={
                "prefill": total_prefill_rows,
                "decode": total_decode_rows,
                "pcie": total_pcie_rows,
            },
        )

    except Exception as exc:
        manifests.update_stage_status(
            manifest_path,
            stage="profile",
            status="profile_failed",
        )
        raise


def _run_prefill_profiling(
    *,
    model_id: str,
    run_root: Path,
    chunk_sizes: Sequence[int],
    warmup_iterations: int,
    timed_iterations: int,
    gpu_id: int,
    cache_root: str | Path | None,
) -> prefill_profile.PrefillProfileResult | None:
    """Profile prefill for one model, catching failures."""
    try:
        return prefill_profile.profile_prefill_sweep(
            model_id=model_id,
            output_root=run_root,
            chunk_tokens=chunk_sizes,
            warmup_iterations=warmup_iterations,
            timed_iterations=timed_iterations,
            gpu_id=gpu_id,
            cache_root=cache_root,
        )
    except Exception as exc:
        print(f"⚠ Prefill profiling failed for {model_id}: {exc}", file=sys.stderr)
        return None


def _run_decode_profiling(
    *,
    model_id: str,
    run_root: Path,
    sequence_lengths: Sequence[int],
    chunk_sizes: Sequence[int],
    warmup_iterations: int,
    timed_iterations: int,
    gpu_id: int,
    cache_root: str | Path | None,
) -> decode_profile.DecodeProfileResult | None:
    """Profile decode for one model, catching failures."""
    try:
        return decode_profile.profile_decode_sweep(
            model_id=model_id,
            output_root=run_root,
            sequence_lengths=sequence_lengths,
            block_sizes=chunk_sizes,
            warmup_iterations=warmup_iterations,
            timed_iterations=timed_iterations,
            gpu_id=gpu_id,
            cache_root=cache_root,
        )
    except Exception as exc:
        print(f"⚠ Decode profiling failed for {model_id}: {exc}", file=sys.stderr)
        return None


def _run_pcie_profiling(
    *,
    model_id: str,
    run_root: Path,
    block_sizes: Sequence[int],
    warmup_iterations: int,
    timed_iterations: int,
    gpu_id: int,
    cache_root: str | Path | None,
) -> pcie_profile.PcieProfileResult | None:
    """Profile PCIe for one model, catching failures."""
    try:
        return pcie_profile.profile_pcie_sweep(
            model_id=model_id,
            output_root=run_root,
            block_sizes=block_sizes,
            warmup_iterations=warmup_iterations,
            timed_iterations=timed_iterations,
            gpu_id=gpu_id,
            cache_root=cache_root,
        )
    except Exception as exc:
        print(f"⚠ PCIe profiling failed for {model_id}: {exc}", file=sys.stderr)
        return None


__all__ = [
    "ProfileOrchestratorResult",
    "orchestrate_profile_run",
]
