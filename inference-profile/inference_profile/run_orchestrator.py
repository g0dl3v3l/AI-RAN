"""Orchestrate full pipeline run with resumable stages."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

# Stage order (must not be changed)
STAGE_ORDER = [
    "bootstrap-env",
    "validate-traces",
    "profile",
    "simulate",
    "report",
    "verify-bundle",
]

# Valid resume-from stages
RESUMABLE_STAGES = frozenset(STAGE_ORDER)


def load_or_create_manifest(run_root: Path) -> dict:
    """Load manifest or create new one."""
    run_root = Path(run_root)
    run_root.mkdir(parents=True, exist_ok=True)
    
    manifest_path = run_root / "run_manifest.json"
    if manifest_path.exists():
        with open(manifest_path, "r") as f:
            return json.load(f)
    
    # Create new manifest with all stages pending
    manifest = {
        "run_id": run_root.name,
        "status": "running",
        "stage_status": {stage: "pending" for stage in STAGE_ORDER},
    }
    return manifest


def save_manifest(run_root: Path, manifest: dict) -> None:
    """Save manifest to disk."""
    manifest_path = Path(run_root) / "run_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)


def get_resume_start_index(
    resume_from: str | None,
    manifest: dict,
) -> int:
    """Determine which stage index to start from."""
    if resume_from is None:
        return 0
    
    if resume_from not in STAGE_ORDER:
        raise ValueError(
            f"Invalid resume stage: {resume_from}. "
            f"Valid stages: {', '.join(STAGE_ORDER)}"
        )
    
    return STAGE_ORDER.index(resume_from)


def run_orchestrator(
    run_root: Path,
    ldpc_trace: Path,
    ran_ctrl_trace: Path,
    models: list[str],
    chunk_sizes: list[int],
    sequence_lengths: list[int],
    gpu_id: int = 0,
    cache_root: Path | None = None,
    resume_from: str | None = None,
) -> dict:
    """
    Run full pipeline with stage orchestration and resumable execution.
    
    Returns:
        dict: Final manifest with all stage statuses.
        
    Raises:
        CliUserError: If any stage fails or manifest cannot be finalized.
    """
    from inference_profile.bootstrap import bootstrap_environment
    from inference_profile.trace_contract import validate_trace_contract
    from inference_profile.profile_orchestrator import orchestrate_profile_run
    from inference_profile.simulator import run_deterministic_simulation
    from inference_profile.plots import generate_profiling_plots
    from inference_profile.report import generate_run_report
    
    run_root = Path(run_root)
    run_root.mkdir(parents=True, exist_ok=True)
    
    # Load or create manifest
    manifest = load_or_create_manifest(run_root)
    
    # Determine starting stage index
    start_index = get_resume_start_index(resume_from, manifest)
    
    logger.info(f"Starting run orchestration at stage: {STAGE_ORDER[start_index]}")
    
    # Execute stages in order
    for idx, stage in enumerate(STAGE_ORDER[start_index:], start=start_index):
        logger.info(f"Stage {idx + 1}/{len(STAGE_ORDER)}: {stage}")
        
        # Skip if already completed
        if manifest["stage_status"].get(stage) == "success":
            logger.info(f"  -> Skipping (already successful)")
            continue
        
        try:
            # Mark as in-progress
            manifest["stage_status"][stage] = "running"
            save_manifest(run_root, manifest)
            
            # Execute stage handler
            if stage == "bootstrap-env":
                bootstrap_environment(output_root=run_root)
            
            elif stage == "validate-traces":
                result = validate_trace_contract(
                    ldpc_trace=ldpc_trace,
                    ran_ctrl_trace=ran_ctrl_trace,
                    output_root=run_root,
                )
                if not result.success:
                    raise RuntimeError(result.user_error_message())
            
            elif stage == "profile":
                result = orchestrate_profile_run(
                    run_root=run_root,
                    models=models,
                    chunk_sizes=chunk_sizes,
                    sequence_lengths=sequence_lengths,
                    warmup_iterations=1,
                    timed_iterations=3,
                    gpu_id=gpu_id,
                    cache_root=cache_root,
                )
                if not result.success:
                    raise RuntimeError("Profiling stage failed")
            
            elif stage == "simulate":
                run_deterministic_simulation(run_root=run_root)
            
            elif stage == "report":
                generate_profiling_plots(run_root=run_root)
                generate_run_report(run_root=run_root)
            
            elif stage == "verify-bundle":
                # Verify required files exist
                required_files = [
                    run_root / "raw" / "prefill_events.csv",
                    run_root / "raw" / "decode_events.csv",
                    run_root / "raw" / "pcie_events.csv",
                    run_root / "derived" / "prefill_summary.csv",
                    run_root / "derived" / "decode_summary.csv",
                    run_root / "derived" / "pcie_summary.csv",
                ]
                missing = [f for f in required_files if not f.exists()]
                if missing:
                    raise RuntimeError(f"Missing required files: {missing}")
            
            # Mark as successful
            manifest["stage_status"][stage] = "success"
            save_manifest(run_root, manifest)
            logger.info(f"  X {stage} completed")
        
        except Exception as exc:
            logger.error(f"  X {stage} failed: {exc}")
            manifest["stage_status"][stage] = "failed"
            manifest["status"] = "failed"
            save_manifest(run_root, manifest)
            raise
    
    # Mark overall run as successful
    manifest["status"] = "success"
    save_manifest(run_root, manifest)
    logger.info(f"Run completed successfully: {run_root}")
    
    return manifest
