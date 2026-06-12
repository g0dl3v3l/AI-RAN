from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from inference_profile import experiments, manifests, paths

logger = logging.getLogger(__name__)

STAGE_ORDER = [
    "bootstrap-env",
    "validate-traces",
    "profile",
    "simulate",
    "report",
    "verify-bundle",
]

RESUMABLE_STAGES = frozenset(STAGE_ORDER)

_LEGACY_STAGE_FAILURE_STATUS = {
    "bootstrap-env": "bootstrap_failed",
    "validate-traces": "validation_failed",
    "profile": "profile_failed",
    "simulate": "simulate_failed",
    "report": "report_failed",
    "verify-bundle": "fetch_failed",
}


@dataclass(frozen=True)
class _StageResult:
    status: str
    details: dict[str, object]
    error_message: str | None = None
    stage_status_already_recorded: bool = False
    final_status_already_recorded: bool = False


def load_or_create_manifest(
    run_root: Path,
    *,
    experiment_type: str | None = None,
    metadata: Mapping[str, object] | None = None,
) -> dict[str, object]:
    return _load_or_create_manifest(
        Path(run_root),
        experiment_type=experiment_type,
        metadata=metadata,
    )


def save_manifest(run_root: Path, manifest: Mapping[str, object]) -> None:
    bundle_paths = paths.bundle_paths_from_run_root(Path(run_root))
    for directory in bundle_paths.directories:
        directory.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(bundle_paths.run_manifest_path, dict(manifest))


def get_resume_start_index(
    resume_from: str | None,
    manifest: Mapping[str, object],
) -> int:
    if resume_from is None:
        return 0

    if resume_from not in STAGE_ORDER:
        raise ValueError(
            f"Invalid resume stage: {resume_from}. "
            f"Valid stages: {', '.join(STAGE_ORDER)}"
        )

    start_index = STAGE_ORDER.index(resume_from)
    for stage in STAGE_ORDER[:start_index]:
        latest_status = _stage_latest_status(manifest, stage)
        if latest_status != "success":
            raise ValueError(
                f"Cannot resume from {resume_from!r}: prior stage {stage!r} "
                f"is not marked success (found {latest_status!r})"
            )

    return start_index


def run_orchestrator(
    run_root: Path,
    ldpc_trace: Path,
    ran_ctrl_trace: Path,
    models: list[str],
    chunk_sizes: list[int],
    sequence_lengths: list[int],
    gpu_id: int = 0,
    sm_ai_partition: int = 100,
    cache_root: Path | None = None,
    resume_from: str | None = None,
    experiment_type: str | None = None,
    dry_run: bool = False,
) -> dict[str, object]:
    resolved_run_root = Path(run_root)
    normalized_experiment_type = experiments.normalize_experiment_type(experiment_type)
    experiment_metadata = experiments.metadata_for_experiment(
        normalized_experiment_type,
        models=models,
        chunk_sizes=chunk_sizes,
        sequence_lengths=sequence_lengths,
    )
    manifest = load_or_create_manifest(
        resolved_run_root,
        experiment_type=normalized_experiment_type,
        metadata=experiment_metadata,
    )
    manifest_path = resolved_run_root / paths.RUN_MANIFEST_FILENAME
    if dry_run:
        return manifest
    start_index = get_resume_start_index(resume_from, manifest)

    logger.info(
        "Starting run orchestration at stage: %s",
        STAGE_ORDER[start_index],
    )

    for stage_index, stage in enumerate(
        STAGE_ORDER[start_index:],
        start=start_index,
    ):
        logger.info("Stage %s/%s: %s", stage_index + 1, len(STAGE_ORDER), stage)
        if stage == "verify-bundle" and stage_index == start_index:
            _refresh_run_checksums(resolved_run_root)
        stage_result = _run_stage(
            stage=stage,
            run_root=resolved_run_root,
            ldpc_trace=Path(ldpc_trace),
            ran_ctrl_trace=Path(ran_ctrl_trace),
            models=models,
            chunk_sizes=chunk_sizes,
            sequence_lengths=sequence_lengths,
            gpu_id=gpu_id,
            sm_ai_partition=sm_ai_partition,
            cache_root=cache_root,
            experiment_type=normalized_experiment_type,
            manifest_metadata=experiment_metadata,
        )

        _record_stage_status(
            manifest_path,
            stage=stage,
            status=stage_result.status,
            details=stage_result.details,
            allow_existing=stage_result.stage_status_already_recorded,
        )

        if stage == "report" and stage_result.status == "success":
            _refresh_run_checksums(resolved_run_root)

        if stage_result.status != "success":
            _record_final_status(
                manifest_path,
                status=stage_result.status,
                details=stage_result.details,
                allow_existing=stage_result.final_status_already_recorded,
            )
            raise RuntimeError(
                stage_result.error_message
                or f"Stage {stage!r} failed with status {stage_result.status!r}"
            )

    manifest = manifests.set_final_status(
        manifest_path,
        "success",
        details={
            "completed_stages": list(STAGE_ORDER),
            "resume_from": resume_from,
        },
    )
    _refresh_run_checksums(resolved_run_root)
    logger.info("Run completed successfully: %s", resolved_run_root)
    return manifests.load_run_manifest(manifest_path)


def _run_stage(
    *,
    stage: str,
    run_root: Path,
    ldpc_trace: Path,
    ran_ctrl_trace: Path,
    models: Sequence[str],
    chunk_sizes: Sequence[int],
    sequence_lengths: Sequence[int],
    gpu_id: int,
    sm_ai_partition: int,
    cache_root: Path | None,
    experiment_type: str,
    manifest_metadata: Mapping[str, object],
) -> _StageResult:
    if stage == "bootstrap-env":
        return _run_bootstrap_stage(
            run_root=run_root,
            cache_root=cache_root,
            gpu_id=gpu_id,
            experiment_type=experiment_type,
            manifest_metadata=manifest_metadata,
        )
    if stage == "validate-traces":
        return _run_validate_traces_stage(
            run_root=run_root,
            ldpc_trace=ldpc_trace,
            ran_ctrl_trace=ran_ctrl_trace,
        )
    if stage == "profile":
        return _run_profile_stage(
            run_root=run_root,
            models=models,
            chunk_sizes=chunk_sizes,
            sequence_lengths=sequence_lengths,
            gpu_id=gpu_id,
            sm_ai_partition=sm_ai_partition,
            cache_root=cache_root,
            experiment_type=experiment_type,
        )
    if stage == "simulate":
        return _run_simulate_stage(
            run_root=run_root,
            ldpc_trace=ldpc_trace,
            experiment_type=experiment_type,
        )
    if stage == "report":
        return _run_report_stage(run_root=run_root)
    if stage == "verify-bundle":
        return _run_verify_bundle_stage(run_root=run_root)
    raise ValueError(f"Unsupported stage: {stage}")


def _run_bootstrap_stage(
    *,
    run_root: Path,
    cache_root: Path | None,
    gpu_id: int,
    experiment_type: str,
    manifest_metadata: Mapping[str, object],
) -> _StageResult:
    from inference_profile.bootstrap import (
        BootstrapEnvironmentError,
        bootstrap_environment,
    )

    manifest_path = run_root / paths.RUN_MANIFEST_FILENAME
    try:
        bootstrap_environment(
            output_root=run_root,
            cache_root=cache_root,
            gpu_id=gpu_id,
            experiment_type=experiment_type,
            manifest_metadata=dict(manifest_metadata),
        )
    except BootstrapEnvironmentError as exc:
        manifest = manifests.load_run_manifest(manifest_path)
        status = _stage_latest_status(manifest, "bootstrap-env") or (
            exc.result.failure.public_status
            if exc.result.failure is not None
            else "bootstrap_failed"
        )
        return _StageResult(
            status=status,
            details=_stage_details(manifest, "bootstrap-env"),
            error_message=exc.result.user_error_message() or _exception_message(exc),
            stage_status_already_recorded=True,
            final_status_already_recorded=manifest.get("final_status") == status,
        )
    except Exception as exc:
        return _StageResult(
            status="bootstrap_failed",
            details={"error": _exception_message(exc)},
            error_message=_exception_message(exc),
        )

    manifest = manifests.load_run_manifest(manifest_path)
    return _StageResult(
        status=_stage_latest_status(manifest, "bootstrap-env") or "success",
        details=_stage_details(manifest, "bootstrap-env"),
        stage_status_already_recorded=True,
    )


def _run_validate_traces_stage(
    *,
    run_root: Path,
    ldpc_trace: Path,
    ran_ctrl_trace: Path,
) -> _StageResult:
    from inference_profile.trace_contract import validate_trace_contract

    result = validate_trace_contract(
        ldpc_trace=ldpc_trace,
        ran_ctrl_trace=ran_ctrl_trace,
        output_root=run_root,
    )
    details = {
        "ldpc_trace": str(ldpc_trace),
        "ran_ctrl_trace": str(ran_ctrl_trace),
        "trace_inspection_path": _relative_run_path(
            run_root, result.trace_inspection_path
        ),
        "normalized_trace_path": _optional_relative_run_path(
            run_root,
            result.normalized_trace_path,
        ),
        "validation_errors_path": _optional_relative_run_path(
            run_root,
            result.validation_errors_path,
        ),
    }
    if result.success:
        return _StageResult(status="success", details=details)
    return _StageResult(
        status="validation_failed",
        details=details,
        error_message=result.user_error_message(),
    )


def _run_profile_stage(
    *,
    run_root: Path,
    models: Sequence[str],
    chunk_sizes: Sequence[int],
    sequence_lengths: Sequence[int],
    gpu_id: int,
    sm_ai_partition: int,
    cache_root: Path | None,
    experiment_type: str,
) -> _StageResult:
    from inference_profile.profile_orchestrator import orchestrate_profile_run

    manifest_path = run_root / paths.RUN_MANIFEST_FILENAME
    try:
        result = orchestrate_profile_run(
            run_root=run_root,
            models=models,
            chunk_sizes=chunk_sizes,
            sequence_lengths=sequence_lengths,
            gpu_id=gpu_id,
            sm_ai_partition=sm_ai_partition,
            cache_root=cache_root,
            experiment_type=experiment_type,
        )
    except Exception as exc:
        manifest = manifests.load_run_manifest(manifest_path)
        status = _stage_latest_status(manifest, "profile") or "profile_failed"
        details = _stage_details(manifest, "profile") or {
            "error": _exception_message(exc)
        }
        return _StageResult(
            status=status,
            details=details,
            error_message=_exception_message(exc),
            stage_status_already_recorded=_stage_latest_status(manifest, "profile")
            == status,
        )

    manifest = manifests.load_run_manifest(manifest_path)
    status = _stage_latest_status(manifest, "profile") or (
        "success" if result.success else "profile_failed"
    )
    details = _stage_details(manifest, "profile")
    if not details:
        details = {
            "row_counts": dict(result.row_counts),
            "run_root": str(result.run_root),
        }
    return _StageResult(
        status=status,
        details=details,
        error_message=(
            None
            if status == "success"
            else f"Profiling stage failed; see {manifest_path}"
        ),
        stage_status_already_recorded=True,
    )


def _run_simulate_stage(
    *,
    run_root: Path,
    ldpc_trace: Path,
    experiment_type: str,
) -> _StageResult:
    from inference_profile.simulator import run_deterministic_simulation

    try:
        result = run_deterministic_simulation(
            run_root=run_root,
            ldpc_trace_path=ldpc_trace,
            experiment_type=experiment_type,
        )
    except Exception as exc:
        return _StageResult(
            status="simulate_failed",
            details={"error": _exception_message(exc)},
            error_message=_exception_message(exc),
        )
    return _StageResult(
        status="success",
        details={
            "results_path": _relative_run_path(run_root, result.results_path),
            "timeline_path": _relative_run_path(run_root, result.timeline_path),
            "row_count": int(result.row_count),
        },
    )


def _run_report_stage(*, run_root: Path) -> _StageResult:
    from inference_profile.paths import bundle_paths_from_run_root
    from inference_profile.plots import generate_profiling_plots
    from inference_profile.report import generate_run_report

    try:
        generate_profiling_plots(run_root=run_root)
        report_path = generate_run_report(run_root=run_root)
    except Exception as exc:
        return _StageResult(
            status="report_failed",
            details={"error": _exception_message(exc)},
            error_message=_exception_message(exc),
        )

    bundle_paths = bundle_paths_from_run_root(run_root)
    plot_files = sorted(
        path.relative_to(run_root).as_posix()
        for path in bundle_paths.plots_dir.glob("*")
        if path.is_file()
    )
    return _StageResult(
        status="success",
        details={
            "report_path": _relative_run_path(run_root, Path(report_path)),
            "plot_files": plot_files,
            "checksum_manifest_path": _relative_run_path(
                run_root,
                bundle_paths.checksum_manifest_path,
            ),
        },
    )


def _refresh_run_checksums(run_root: Path) -> None:
    from inference_profile.report import write_run_checksum_manifest

    write_run_checksum_manifest(run_root=run_root)


def _run_verify_bundle_stage(*, run_root: Path) -> _StageResult:
    from inference_profile.verify_bundle import verify_bundle

    result = verify_bundle(run_root)
    details = {
        "complete": bool(result.get("complete", False)),
        "checksums_valid": bool(result.get("checksums_valid", False)),
        "missing_artifacts": list(result.get("missing_artifacts", [])),
        "zero_byte_artifacts": list(result.get("zero_byte_artifacts", [])),
        "checksum_missing_artifacts": list(
            result.get("checksum_missing_artifacts", [])
        ),
        "checksum_mismatches": list(result.get("checksum_mismatches", [])),
    }
    status = str(result.get("status") or "fetch_failed")
    if status == "success":
        return _StageResult(status="success", details=details)
    return _StageResult(
        status=status,
        details=details,
        error_message=_verify_bundle_error_message(details),
    )


def _verify_bundle_error_message(details: Mapping[str, object]) -> str:
    fragments = ["Bundle verification failed"]
    missing_artifacts = _details_list(details, "missing_artifacts")
    zero_byte_artifacts = _details_list(details, "zero_byte_artifacts")
    checksum_missing_artifacts = _details_list(
        details,
        "checksum_missing_artifacts",
    )
    checksum_mismatches = _details_list(details, "checksum_mismatches")
    if missing_artifacts:
        fragments.append(f"missing={missing_artifacts}")
    if zero_byte_artifacts:
        fragments.append(f"zero_byte={zero_byte_artifacts}")
    if checksum_missing_artifacts:
        fragments.append(f"checksum_missing={checksum_missing_artifacts}")
    if checksum_mismatches:
        fragments.append(f"checksum_mismatches={checksum_mismatches}")
    return "; ".join(fragments)


def _record_stage_status(
    manifest_path: Path,
    *,
    stage: str,
    status: str,
    details: Mapping[str, object],
    allow_existing: bool,
) -> dict[str, object]:
    manifest = manifests.load_run_manifest(manifest_path)
    if allow_existing and _stage_latest_status(manifest, stage) == status:
        return manifest
    return manifests.update_stage_status(
        manifest_path,
        stage=stage,
        status=status,
        details=details,
    )


def _record_final_status(
    manifest_path: Path,
    *,
    status: str,
    details: Mapping[str, object],
    allow_existing: bool,
) -> dict[str, object]:
    manifest = manifests.load_run_manifest(manifest_path)
    if allow_existing and manifest.get("final_status") == status:
        return manifest
    return manifests.set_final_status(manifest_path, status, details=details)


def _load_or_create_manifest(
    run_root: Path,
    *,
    experiment_type: str | None,
    metadata: Mapping[str, object] | None,
) -> dict[str, object]:
    bundle_paths = paths.bundle_paths_from_run_root(run_root)
    for directory in bundle_paths.directories:
        directory.mkdir(parents=True, exist_ok=True)

    payload = _read_json_object(bundle_paths.run_manifest_path)
    if not payload:
        schema_version, manifest_metadata = experiments.split_manifest_metadata(
            {
                **experiments.metadata_for_experiment(experiment_type),
                **dict(metadata or {}),
            }
        )
        manifests.initialize_run_manifest(
            bundle_paths,
            schema_version=schema_version,
            metadata=manifest_metadata,
        )
        return manifests.load_run_manifest(bundle_paths.run_manifest_path)

    if "status" not in payload and "stage_status" not in payload:
        return manifests.load_run_manifest(bundle_paths.run_manifest_path)

    manifest = manifests.load_run_manifest(bundle_paths.run_manifest_path)
    legacy_stage_status = payload.get("stage_status")
    legacy_status = payload.get("status")

    manifest.pop("status", None)
    manifest.pop("stage_status", None)

    stages = manifest.setdefault("stages", {})
    if not isinstance(stages, dict):
        stages = {}
        manifest["stages"] = stages
    _merge_legacy_stage_statuses(
        manifest=manifest,
        stages=stages,
        legacy_stage_status=legacy_stage_status,
    )
    _backfill_legacy_final_status(
        manifest=manifest,
        legacy_status=legacy_status,
    )
    _write_json_atomic(bundle_paths.run_manifest_path, manifest)
    return manifests.load_run_manifest(bundle_paths.run_manifest_path)


def _merge_legacy_stage_statuses(
    *,
    manifest: dict[str, object],
    stages: dict[str, object],
    legacy_stage_status: object,
) -> None:
    if not isinstance(legacy_stage_status, dict):
        return

    timestamp = _manifest_timestamp(manifest)
    for stage in STAGE_ORDER:
        if stage in stages:
            continue
        legacy_status = legacy_stage_status.get(stage)
        mapped_status = _map_legacy_stage_status(stage, legacy_status)
        if mapped_status is None:
            continue
        history_entry: dict[str, object] = {
            "status": mapped_status,
            "timestamp": timestamp,
        }
        if mapped_status != legacy_status:
            history_entry["details"] = {
                "migrated_from_legacy_status": legacy_status,
            }
        stages[stage] = {
            "latest_status": mapped_status,
            "updated_at": timestamp,
            "history": [history_entry],
        }


def _backfill_legacy_final_status(
    *,
    manifest: dict[str, object],
    legacy_status: object,
) -> None:
    if manifest.get("final_status") is not None:
        return
    if not isinstance(legacy_status, str):
        return

    if legacy_status == "success":
        _append_final_status_entry(manifest, "success")
        return
    if legacy_status != "failed":
        return

    for stage in reversed(STAGE_ORDER):
        stage_status = _stage_latest_status(manifest, stage)
        if stage_status is None or stage_status == "success":
            continue
        _append_final_status_entry(manifest, stage_status)
        return


def _append_final_status_entry(manifest: dict[str, object], status: str) -> None:
    timestamp = _manifest_timestamp(manifest)
    history = manifest.setdefault("final_status_history", [])
    if not isinstance(history, list):
        history = []
        manifest["final_status_history"] = history
    history.append(
        {
            "status": status,
            "timestamp": timestamp,
            "details": {"migrated_from_legacy_manifest": True},
        }
    )
    manifest["final_status"] = status
    manifest["updated_at"] = timestamp


def _map_legacy_stage_status(stage: str, legacy_status: object) -> str | None:
    if legacy_status == "success":
        return "success"
    if legacy_status == "failed":
        return _LEGACY_STAGE_FAILURE_STATUS.get(stage)
    return None


def _manifest_timestamp(manifest: Mapping[str, object]) -> str:
    updated_at = manifest.get("updated_at")
    if isinstance(updated_at, str) and updated_at:
        return updated_at
    created_at = manifest.get("created_at")
    if isinstance(created_at, str) and created_at:
        return created_at
    return _utc_timestamp()


def _stage_latest_status(manifest: Mapping[str, object], stage: str) -> str | None:
    stages = manifest.get("stages")
    if not isinstance(stages, dict):
        return None
    stage_payload = stages.get(stage)
    if not isinstance(stage_payload, dict):
        return None
    latest_status = stage_payload.get("latest_status")
    if isinstance(latest_status, str):
        return latest_status
    return None


def _stage_details(manifest: Mapping[str, object], stage: str) -> dict[str, object]:
    stages = manifest.get("stages")
    if not isinstance(stages, dict):
        return {}
    stage_payload = stages.get(stage)
    if not isinstance(stage_payload, dict):
        return {}
    details = stage_payload.get("details")
    if isinstance(details, dict):
        return dict(details)
    return {}


def _relative_run_path(run_root: Path, path: Path) -> str:
    try:
        return path.relative_to(run_root).as_posix()
    except ValueError:
        return str(path)


def _optional_relative_run_path(run_root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    return _relative_run_path(run_root, path)


def _read_json_object(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if isinstance(payload, dict):
        return payload
    return None


def _write_json_atomic(path: Path, payload: Mapping[str, object]) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
        ) as handle:
            handle.write(rendered)
            temporary_path = Path(handle.name)
        temporary_path.replace(path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _exception_message(exc: BaseException) -> str:
    message = str(exc)
    if message:
        return message
    return f"{exc.__class__.__name__} raised without an error message"


def _details_list(details: Mapping[str, object], key: str) -> list[str]:
    value = details.get(key)
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, tuple):
        return [str(item) for item in value]
    return []


def _utc_timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
