from __future__ import annotations

from collections.abc import Mapping, Sequence
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import sys
from tempfile import NamedTemporaryFile
from typing import Any, cast
import warnings

from inference_profile import (
    decode_profile,
    experiments,
    manifests,
    opt_assets,
    paths,
    pcie_profile,
    prefill_profile,
    profile_reducer,
    telemetry,
    worker_profile_point,
)
from inference_profile.constants import DECODE_SEQUENCE_LENGTHS, PREFILL_CHUNK_SIZES

_PROFILE_STAGE_NAME = "profile"
_PROFILE_FAMILIES = ("prefill", "decode", "pcie")
_PROFILE_POINT_TIMEOUT_SECONDS = 900.0
_PROFILE_INSPECTION_DIRNAME = "inspect-model"
_PROFILE_POINT_RAW_DIRNAME = "points"
_MODEL_CONSTANTS_SUMMARY_COLUMNS = (
    "model_id",
    "sm_ai_partition",
    "num_hidden_layers",
    "hidden_size",
    "num_attention_heads",
    "ffn_dim",
    "layer_index",
    "layer_weight_bytes",
    "total_weight_bytes_fp16",
    "vram_ceiling_bytes",
)
_RAW_ROW_METADATA_FIELDS = (
    "point_id",
    "public_status",
    "failure_kind",
    "failure_cause",
    "raw_output_path",
)
_REVISED_RAW_TELEMETRY_FIELDS = (
    "telemetry_ts",
    "telemetry_tier",
    "telemetry_provider",
    "telemetry_status",
    "gpu_util",
    "gpu_mem_used_mb",
    "sm_clock_mhz",
    "mem_clock_mhz",
    "power_w",
    "pt_step_ms",
    "pt_mem_alloc_mb",
    "pt_mem_reserved_mb",
    "pt_workspace_mb",
    "nvml_available",
    "sampling_error",
    *telemetry.MICROSCOPIC_COUNTER_COLUMNS,
    "microscopic_telemetry_status",
    "microscopic_error",
)
_STATUS_COMMON_FIELDS = (
    "point_id",
    "model_id",
    "public_status",
    "failure_kind",
    "failure_cause",
    "timed_out",
    "exit_code",
    "raw_output_path",
    "raw_row_count",
    "stdout_log_path",
    "stderr_log_path",
)
_PROFILE_PARENT_LOG_FILENAMES = {
    "stage": "profile-stage.log",
    "inspect-model": "profile-inspect-model.log",
    "prefill": "profile-prefill.log",
    "decode": "profile-decode.log",
    "pcie": "profile-pcie.log",
    "reducer": "profile-reducer.log",
}
_PREFILL_CANONICAL_FIELDNAMES = (
    *prefill_profile.PREFILL_EVENT_FIELDNAMES,
    *_RAW_ROW_METADATA_FIELDS,
)
_PREFILL_REVISED_CANONICAL_FIELDNAMES = (
    *prefill_profile.PREFILL_EVENT_FIELDNAMES,
    "max_input_tokens",
    *_REVISED_RAW_TELEMETRY_FIELDS,
    *_RAW_ROW_METADATA_FIELDS,
)
_DECODE_CANONICAL_FIELDNAMES = (
    *decode_profile.DECODE_EVENT_FIELDNAMES,
    *_RAW_ROW_METADATA_FIELDS,
)
_DECODE_REVISED_CANONICAL_FIELDNAMES = (
    *decode_profile.DECODE_EVENT_FIELDNAMES,
    "decode_mode",
    *_REVISED_RAW_TELEMETRY_FIELDS,
    *_RAW_ROW_METADATA_FIELDS,
)
_PCIE_CANONICAL_FIELDNAMES = (
    *pcie_profile.PCIE_EVENT_FIELDNAMES,
    *_RAW_ROW_METADATA_FIELDS,
)
_PCIE_REVISED_CANONICAL_FIELDNAMES = (
    *pcie_profile.PCIE_EVENT_FIELDNAMES,
    "overlap_status",
    *_REVISED_RAW_TELEMETRY_FIELDS,
    *_RAW_ROW_METADATA_FIELDS,
)
_PREFILL_STATUS_FIELDNAMES = (*_STATUS_COMMON_FIELDS, "chunk_tokens")
_DECODE_STATUS_FIELDNAMES = (*_STATUS_COMMON_FIELDS, "sequence_length", "block_size")
_PCIE_STATUS_FIELDNAMES = (*_STATUS_COMMON_FIELDS, "block_size")


@dataclass(frozen=True)
class ProfileOrchestratorResult:
    run_root: Path
    success: bool
    row_counts: dict[str, int]


@dataclass(frozen=True)
class _ProfilePointPlan:
    family: str
    point_id: str
    spec: dict[str, Any]
    manifest_fields: dict[str, object]


@dataclass
class _ProfilerFamilyState:
    family: str
    requested_points: int
    completed_points: int = 0
    successes: int = 0
    ooms: int = 0
    failures: int = 0
    raw_rows: int = 0

    def record_result(self, public_status: str, raw_rows: int) -> None:
        self.completed_points += 1
        self.raw_rows += int(raw_rows)
        if public_status == "success":
            self.successes += 1
            return
        if public_status == "profile_oom":
            self.ooms += 1
            return
        self.failures += 1

    def to_details(self) -> dict[str, int]:
        return {
            "requested_points": self.requested_points,
            "completed_points": self.completed_points,
            "successes": self.successes,
            "ooms": self.ooms,
            "failures": self.failures,
            "raw_rows": self.raw_rows,
        }


class _CanonicalCsvSink:
    def __init__(self, path: Path, *, fieldnames: Sequence[str]) -> None:
        self.path = Path(path)
        self.fieldnames = tuple(str(fieldname) for fieldname in fieldnames)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("w", encoding="utf-8", newline="")
        self._writer = csv.DictWriter(
            self._handle,
            fieldnames=list(self.fieldnames),
            extrasaction="raise",
        )
        self._writer.writeheader()
        self._handle.flush()

    def write_row(self, row: Mapping[str, object]) -> None:
        normalized_row = {
            fieldname: row.get(fieldname, "") for fieldname in self.fieldnames
        }
        self._writer.writerow(normalized_row)
        self._handle.flush()

    def close(self) -> None:
        self._handle.flush()
        self._handle.close()


def orchestrate_profile_run(
    *,
    run_root: str | Path,
    models: Sequence[str],
    chunk_sizes: Sequence[int] = PREFILL_CHUNK_SIZES,
    sequence_lengths: Sequence[int] = DECODE_SEQUENCE_LENGTHS,
    warmup_iterations: int = 3,
    timed_iterations: int = 5,
    gpu_id: int = 0,
    sm_ai_partition: int = 100,
    cache_root: str | Path | None = None,
    experiment_type: str | None = None,
) -> ProfileOrchestratorResult:
    if not models:
        raise ValueError("models must contain at least one model")

    normalized_models = tuple(
        opt_assets.normalize_model_id(model_id) for model_id in models
    )
    resolved_chunk_sizes = _normalize_positive_int_sequence(
        "chunk_sizes",
        chunk_sizes,
    )
    resolved_sequence_lengths = _normalize_positive_int_sequence(
        "sequence_lengths",
        sequence_lengths,
    )
    resolved_warmup_iterations = _normalize_non_negative_int(
        warmup_iterations,
        name="warmup_iterations",
    )
    resolved_timed_iterations = _normalize_positive_int(
        timed_iterations,
        name="timed_iterations",
    )
    resolved_gpu_id = _normalize_non_negative_int(gpu_id, name="gpu_id")
    resolved_sm_ai_partition = _normalize_sm_ai_partition(
        sm_ai_partition,
        name="sm_ai_partition",
    )
    normalized_experiment_type = experiments.normalize_experiment_type(experiment_type)
    experiment_metadata = experiments.metadata_for_experiment(
        normalized_experiment_type,
        models=normalized_models,
        chunk_sizes=resolved_chunk_sizes,
        sequence_lengths=resolved_sequence_lengths,
    )
    resolved_cache_root = Path(cache_root) if cache_root is not None else None
    resolved_run_root = Path(run_root)

    bundle_paths = _ensure_bundle_layout(
        resolved_run_root,
        experiment_type=normalized_experiment_type,
        metadata=experiment_metadata,
    )
    manifest_path = bundle_paths.run_manifest_path
    parent_log_paths = _parent_log_paths(bundle_paths.logs_dir)

    _append_log(
        parent_log_paths["stage"],
        (
            "Starting profile stage for "
            f"{len(normalized_models)} model(s), "
            f"{len(resolved_chunk_sizes)} chunk size(s), and "
            f"{len(resolved_sequence_lengths)} sequence length(s)"
        ),
    )
    _write_environment_snapshot(
        bundle_paths=bundle_paths,
        models=normalized_models,
        chunk_sizes=resolved_chunk_sizes,
        sequence_lengths=resolved_sequence_lengths,
        warmup_iterations=resolved_warmup_iterations,
        timed_iterations=resolved_timed_iterations,
        gpu_id=resolved_gpu_id,
        sm_ai_partition=resolved_sm_ai_partition,
        cache_root=resolved_cache_root,
        experiment_type=normalized_experiment_type,
    )

    point_plans = _build_profile_point_plans(
        bundle_paths=bundle_paths,
        models=normalized_models,
        chunk_sizes=resolved_chunk_sizes,
        sequence_lengths=resolved_sequence_lengths,
        warmup_iterations=resolved_warmup_iterations,
        timed_iterations=resolved_timed_iterations,
        gpu_id=resolved_gpu_id,
        sm_ai_partition=resolved_sm_ai_partition,
        cache_root=resolved_cache_root,
        experiment_type=normalized_experiment_type,
    )
    family_states = {
        family: _ProfilerFamilyState(
            family=family, requested_points=len(point_plans[family])
        )
        for family in _PROFILE_FAMILIES
    }
    expected_summary_rows = {
        "model_constants": len(normalized_models),
        "prefill": len(point_plans["prefill"]),
        "decode": len(point_plans["decode"]),
        "pcie": len(point_plans["pcie"]),
    }
    canonical_raw_paths = {
        "prefill": bundle_paths.raw_dir / prefill_profile.PREFILL_EVENTS_FILENAME,
        "decode": bundle_paths.raw_dir / decode_profile.DECODE_EVENTS_FILENAME,
        "pcie": bundle_paths.raw_dir / pcie_profile.PCIE_EVENTS_FILENAME,
    }
    status_sidecar_paths = {
        family: _status_sidecar_path(canonical_raw_paths[family])
        for family in _PROFILE_FAMILIES
    }

    raw_sinks, status_sinks = _open_canonical_sinks(
        canonical_raw_paths=canonical_raw_paths,
        status_sidecar_paths=status_sidecar_paths,
        experiment_type=normalized_experiment_type,
    )
    inspection_results: tuple[opt_assets.InspectionResult, ...] = ()

    manifests.update_stage_status(
        manifest_path,
        stage=_PROFILE_STAGE_NAME,
        status="success",
        details=_build_stage_details(
            run_root=resolved_run_root,
            models=normalized_models,
            chunk_sizes=resolved_chunk_sizes,
            sequence_lengths=resolved_sequence_lengths,
            warmup_iterations=resolved_warmup_iterations,
            timed_iterations=resolved_timed_iterations,
            gpu_id=resolved_gpu_id,
            sm_ai_partition=resolved_sm_ai_partition,
            cache_root=resolved_cache_root,
            bundle_paths=bundle_paths,
            canonical_raw_paths=canonical_raw_paths,
            status_sidecar_paths=status_sidecar_paths,
            parent_log_paths=parent_log_paths,
            inspection_results=inspection_results,
            family_states=family_states,
            expected_summary_rows=expected_summary_rows,
            experiment_type=normalized_experiment_type,
        ),
    )

    try:
        inspection_results = _ensure_model_inspection_prerequisites(
            run_root=resolved_run_root,
            models=normalized_models,
            cache_root=resolved_cache_root,
            inspect_log_path=parent_log_paths["inspect-model"],
        )

        for family in _PROFILE_FAMILIES:
            family_log_path = parent_log_paths[family]
            for plan in point_plans[family]:
                result = worker_profile_point.run_profile_point(
                    plan.spec,
                    run_root=resolved_run_root,
                    timeout_seconds=_PROFILE_POINT_TIMEOUT_SECONDS,
                )
                point_telemetry = _collect_point_telemetry(
                    family=family,
                    plan=plan,
                    experiment_type=normalized_experiment_type,
                    gpu_id=resolved_gpu_id,
                    point_result=result,
                )
                merged_raw_rows = _append_point_raw_rows(
                    sink=raw_sinks[family],
                    family=family,
                    plan=plan,
                    point_result=result,
                    experiment_type=normalized_experiment_type,
                    point_telemetry=point_telemetry,
                )
                _append_point_status_row(
                    sink=status_sinks[family],
                    family=family,
                    plan=plan,
                    point_result=result,
                )
                _append_telemetry_for_point(
                    run_root=resolved_run_root,
                    point_telemetry=point_telemetry,
                )

                public_status = _result_public_status(result)
                family_states[family].record_result(public_status, merged_raw_rows)

                _append_log(
                    family_log_path,
                    (
                        f"{plan.point_id} status={public_status} "
                        f"raw_rows={merged_raw_rows} "
                        f"failure_kind={_optional_string(result.get('failure_kind')) or '-'}"
                    ),
                )
                manifests.update_stage_status(
                    manifest_path,
                    stage=_PROFILE_STAGE_NAME,
                    status=_derive_stage_status(family_states),
                    details=_build_stage_details(
                        run_root=resolved_run_root,
                        models=normalized_models,
                        chunk_sizes=resolved_chunk_sizes,
                        sequence_lengths=resolved_sequence_lengths,
                        warmup_iterations=resolved_warmup_iterations,
                        timed_iterations=resolved_timed_iterations,
                        gpu_id=resolved_gpu_id,
                        cache_root=resolved_cache_root,
                        bundle_paths=bundle_paths,
                        canonical_raw_paths=canonical_raw_paths,
                        status_sidecar_paths=status_sidecar_paths,
                        parent_log_paths=parent_log_paths,
                        inspection_results=inspection_results,
                        family_states=family_states,
                        expected_summary_rows=expected_summary_rows,
                        sm_ai_partition=resolved_sm_ai_partition,
                        experiment_type=normalized_experiment_type,
                        last_point={
                            "family": family,
                            "point_id": plan.point_id,
                            "public_status": public_status,
                            **plan.manifest_fields,
                        },
                    ),
                )

        reduction_result = profile_reducer.reduce_profile_events(
            run_root=resolved_run_root
        )
        _append_log(
            parent_log_paths["reducer"],
            (
                "Reducer completed with rows: "
                f"prefill={reduction_result.prefill_row_count}, "
                f"decode={reduction_result.decode_row_count}, "
                f"pcie={reduction_result.pcie_row_count}"
            ),
        )
        _write_model_constants_summary(
            reduction_result.model_constants_path,
            inspection_results,
            sm_ai_partition=resolved_sm_ai_partition,
        )

        actual_summary_rows = {
            "model_constants": _count_csv_rows(reduction_result.model_constants_path),
            "prefill": reduction_result.prefill_row_count,
            "decode": reduction_result.decode_row_count,
            "pcie": reduction_result.pcie_row_count,
        }
        missing_outputs = _missing_required_outputs(
            run_root=resolved_run_root,
            bundle_paths=bundle_paths,
            canonical_raw_paths=canonical_raw_paths,
            status_sidecar_paths=status_sidecar_paths,
            parent_log_paths=parent_log_paths,
            inspection_results=inspection_results,
            reduction_result=reduction_result,
            experiment_type=normalized_experiment_type,
        )
        summary_rows_complete = actual_summary_rows == expected_summary_rows
        final_status = _derive_final_stage_status(
            family_states,
            missing_outputs=missing_outputs,
            summary_rows_complete=summary_rows_complete,
        )
        success = final_status == "success"

        manifests.update_stage_status(
            manifest_path,
            stage=_PROFILE_STAGE_NAME,
            status=final_status,
            details=_build_stage_details(
                run_root=resolved_run_root,
                models=normalized_models,
                chunk_sizes=resolved_chunk_sizes,
                sequence_lengths=resolved_sequence_lengths,
                warmup_iterations=resolved_warmup_iterations,
                timed_iterations=resolved_timed_iterations,
                gpu_id=resolved_gpu_id,
                sm_ai_partition=resolved_sm_ai_partition,
                cache_root=resolved_cache_root,
                bundle_paths=bundle_paths,
                canonical_raw_paths=canonical_raw_paths,
                status_sidecar_paths=status_sidecar_paths,
                parent_log_paths=parent_log_paths,
                inspection_results=inspection_results,
                family_states=family_states,
                expected_summary_rows=expected_summary_rows,
                actual_summary_rows=actual_summary_rows,
                missing_outputs=missing_outputs,
                summary_rows_complete=summary_rows_complete,
                experiment_type=normalized_experiment_type,
            ),
        )
        _append_log(
            parent_log_paths["stage"],
            (
                f"Profile stage finished with status={final_status} "
                f"summary_rows_complete={summary_rows_complete}"
            ),
        )
        return ProfileOrchestratorResult(
            run_root=resolved_run_root,
            success=success,
            row_counts={
                family: family_states[family].raw_rows for family in _PROFILE_FAMILIES
            },
        )
    except Exception as exc:
        manifests.update_stage_status(
            manifest_path,
            stage=_PROFILE_STAGE_NAME,
            status="profile_failed",
            details=_build_stage_details(
                run_root=resolved_run_root,
                models=normalized_models,
                chunk_sizes=resolved_chunk_sizes,
                sequence_lengths=resolved_sequence_lengths,
                warmup_iterations=resolved_warmup_iterations,
                timed_iterations=resolved_timed_iterations,
                gpu_id=resolved_gpu_id,
                sm_ai_partition=resolved_sm_ai_partition,
                cache_root=resolved_cache_root,
                bundle_paths=bundle_paths,
                canonical_raw_paths=canonical_raw_paths,
                status_sidecar_paths=status_sidecar_paths,
                parent_log_paths=parent_log_paths,
                inspection_results=inspection_results,
                family_states=family_states,
                expected_summary_rows=expected_summary_rows,
                missing_outputs=[_exception_message(exc)],
                summary_rows_complete=False,
                experiment_type=normalized_experiment_type,
            ),
        )
        _append_log(
            parent_log_paths["stage"],
            f"Profile stage crashed: {_exception_message(exc)}",
        )
        raise RuntimeError(_exception_message(exc)) from None
    finally:
        for sink in (*raw_sinks.values(), *status_sinks.values()):
            sink.close()


def _ensure_bundle_layout(
    run_root: Path,
    *,
    experiment_type: str,
    metadata: Mapping[str, object],
) -> paths.RunBundlePaths:
    bundle_paths = paths.bundle_paths_from_run_root(run_root)
    for directory in bundle_paths.directories:
        directory.mkdir(parents=True, exist_ok=True)
    schema_version, manifest_metadata = experiments.split_manifest_metadata(metadata)
    if not bundle_paths.run_manifest_path.exists():
        manifests.initialize_run_manifest(
            bundle_paths,
            schema_version=schema_version,
            metadata=manifest_metadata,
        )
    else:
        payload = manifests.load_run_manifest(bundle_paths.run_manifest_path)
        if experiment_type == experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE:
            updated = False
            if payload.get("schema_version") != schema_version:
                payload["schema_version"] = schema_version
                updated = True
            for key, value in metadata.items():
                if payload.get(key) != value:
                    payload[key] = value
                    updated = True
            if updated:
                rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
                bundle_paths.run_manifest_path.write_text(rendered, encoding="utf-8")
    return bundle_paths


def _parent_log_paths(logs_dir: Path) -> dict[str, Path]:
    return {
        key: logs_dir / filename
        for key, filename in _PROFILE_PARENT_LOG_FILENAMES.items()
    }


def _open_canonical_sinks(
    *,
    canonical_raw_paths: Mapping[str, Path],
    status_sidecar_paths: Mapping[str, Path],
    experiment_type: str,
) -> tuple[dict[str, _CanonicalCsvSink], dict[str, _CanonicalCsvSink]]:
    is_revised = experiment_type == experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE
    raw_sinks = {
        "prefill": _CanonicalCsvSink(
            canonical_raw_paths["prefill"],
            fieldnames=(
                _PREFILL_REVISED_CANONICAL_FIELDNAMES
                if is_revised
                else _PREFILL_CANONICAL_FIELDNAMES
            ),
        ),
        "decode": _CanonicalCsvSink(
            canonical_raw_paths["decode"],
            fieldnames=(
                _DECODE_REVISED_CANONICAL_FIELDNAMES
                if is_revised
                else _DECODE_CANONICAL_FIELDNAMES
            ),
        ),
        "pcie": _CanonicalCsvSink(
            canonical_raw_paths["pcie"],
            fieldnames=(
                _PCIE_REVISED_CANONICAL_FIELDNAMES
                if is_revised
                else _PCIE_CANONICAL_FIELDNAMES
            ),
        ),
    }
    status_sinks = {
        "prefill": _CanonicalCsvSink(
            status_sidecar_paths["prefill"],
            fieldnames=_PREFILL_STATUS_FIELDNAMES,
        ),
        "decode": _CanonicalCsvSink(
            status_sidecar_paths["decode"],
            fieldnames=_DECODE_STATUS_FIELDNAMES,
        ),
        "pcie": _CanonicalCsvSink(
            status_sidecar_paths["pcie"],
            fieldnames=_PCIE_STATUS_FIELDNAMES,
        ),
    }
    return raw_sinks, status_sinks


def _build_profile_point_plans(
    *,
    bundle_paths: paths.RunBundlePaths,
    models: Sequence[str],
    chunk_sizes: Sequence[int],
    sequence_lengths: Sequence[int],
    warmup_iterations: int,
    timed_iterations: int,
    gpu_id: int,
    sm_ai_partition: int,
    cache_root: Path | None,
    experiment_type: str,
) -> dict[str, tuple[_ProfilePointPlan, ...]]:
    resolved_cache_root = str(cache_root) if cache_root is not None else None
    is_revised = experiment_type == experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE
    sm_ai_partitions = (
        experiments.RAN_DGXSPARK_V1_SM_AI_PARTITIONS
        if is_revised
        else (int(sm_ai_partition),)
    )
    decode_modes = experiments.RAN_DGXSPARK_V1_DECODE_MODES if is_revised else ("vram",)

    prefill_plans: list[_ProfilePointPlan] = []
    for model_id in models:
        model_slug = _slugify(model_id)
        for chunk_tokens in chunk_sizes:
            for sm_partition in sm_ai_partitions:
                point_id = f"prefill-{model_slug}-chunk-{int(chunk_tokens)}"
                if is_revised:
                    point_id += f"-sm-{int(sm_partition)}"
                prefill_plans.append(
                    _ProfilePointPlan(
                        family="prefill",
                        point_id=point_id,
                        spec={
                            "point_id": point_id,
                            "callable_path": f"{__name__}._run_prefill_point_worker",
                            "raw_fieldnames": list(
                                prefill_profile.PREFILL_EVENT_FIELDNAMES
                            ),
                            "raw_output_path": str(
                                _point_raw_output_path(
                                    bundle_paths, "prefill", point_id
                                )
                            ),
                            "model_id": model_id,
                            "chunk_tokens": int(chunk_tokens),
                            "warmup_iterations": warmup_iterations,
                            "timed_iterations": timed_iterations,
                            "gpu_id": gpu_id,
                            "sm_ai_partition": int(sm_partition),
                            "cache_root": resolved_cache_root,
                            "experiment_type": experiment_type,
                        },
                        manifest_fields={
                            "model_id": model_id,
                            "chunk_tokens": int(chunk_tokens),
                            "sm_ai_partition": int(sm_partition),
                        },
                    )
                )

    decode_plans: list[_ProfilePointPlan] = []
    for model_id in models:
        model_slug = _slugify(model_id)
        for sequence_length in sequence_lengths:
            for block_size in chunk_sizes:
                for sm_partition in sm_ai_partitions:
                    for decode_mode in decode_modes:
                        point_id = (
                            f"decode-{model_slug}-seq-{int(sequence_length)}"
                            f"-block-{int(block_size)}"
                        )
                        if is_revised:
                            point_id += f"-mode-{decode_mode}-sm-{int(sm_partition)}"
                        decode_plans.append(
                            _ProfilePointPlan(
                                family="decode",
                                point_id=point_id,
                                spec={
                                    "point_id": point_id,
                                    "callable_path": f"{__name__}._run_decode_point_worker",
                                    "raw_fieldnames": list(
                                        decode_profile.DECODE_EVENT_FIELDNAMES
                                    ),
                                    "raw_output_path": str(
                                        _point_raw_output_path(
                                            bundle_paths, "decode", point_id
                                        )
                                    ),
                                    "model_id": model_id,
                                    "sequence_length": int(sequence_length),
                                    "block_size": int(block_size),
                                    "warmup_iterations": warmup_iterations,
                                    "timed_iterations": timed_iterations,
                                    "gpu_id": gpu_id,
                                    "sm_ai_partition": int(sm_partition),
                                    "decode_mode": decode_mode,
                                    "cache_root": resolved_cache_root,
                                    "experiment_type": experiment_type,
                                },
                                manifest_fields={
                                    "model_id": model_id,
                                    "sequence_length": int(sequence_length),
                                    "block_size": int(block_size),
                                    "sm_ai_partition": int(sm_partition),
                                    "decode_mode": decode_mode,
                                },
                            )
                        )

    pcie_plans: list[_ProfilePointPlan] = []
    for model_id in models:
        model_slug = _slugify(model_id)
        for block_size in chunk_sizes:
            point_id = f"pcie-{model_slug}-block-{int(block_size)}"
            pcie_plans.append(
                _ProfilePointPlan(
                    family="pcie",
                    point_id=point_id,
                    spec={
                        "point_id": point_id,
                        "callable_path": f"{__name__}._run_pcie_point_worker",
                        "raw_fieldnames": list(pcie_profile.PCIE_EVENT_FIELDNAMES),
                        "raw_output_path": str(
                            _point_raw_output_path(bundle_paths, "pcie", point_id)
                        ),
                        "model_id": model_id,
                        "block_size": int(block_size),
                        "warmup_iterations": warmup_iterations,
                        "timed_iterations": timed_iterations,
                        "gpu_id": gpu_id,
                        "cache_root": resolved_cache_root,
                        "experiment_type": experiment_type,
                    },
                    manifest_fields={
                        "model_id": model_id,
                        "block_size": int(block_size),
                    },
                )
            )

    return {
        "prefill": tuple(prefill_plans),
        "decode": tuple(decode_plans),
        "pcie": tuple(pcie_plans),
    }


def _point_raw_output_path(
    bundle_paths: paths.RunBundlePaths,
    family: str,
    point_id: str,
) -> Path:
    return (
        bundle_paths.raw_dir
        / _PROFILE_POINT_RAW_DIRNAME
        / family
        / f"{_slugify(point_id)}.csv"
    )


def _status_sidecar_path(raw_events_path: Path) -> Path:
    return raw_events_path.with_name(f"{raw_events_path.stem}_status.csv")


def _write_environment_snapshot(
    *,
    bundle_paths: paths.RunBundlePaths,
    models: Sequence[str],
    chunk_sizes: Sequence[int],
    sequence_lengths: Sequence[int],
    warmup_iterations: int,
    timed_iterations: int,
    gpu_id: int,
    sm_ai_partition: int,
    cache_root: Path | None,
    experiment_type: str,
) -> None:
    payload: dict[str, object] = {
        "stage": _PROFILE_STAGE_NAME,
        "captured_at": _utc_timestamp(),
        "run_root": str(bundle_paths.run_root),
        "models": list(models),
        "chunk_sizes": [int(chunk_size) for chunk_size in chunk_sizes],
        "sequence_lengths": [
            int(sequence_length) for sequence_length in sequence_lengths
        ],
        "warmup_iterations": int(warmup_iterations),
        "timed_iterations": int(timed_iterations),
        "gpu_id": int(gpu_id),
        "sm_ai_partition": int(sm_ai_partition),
        "experiment_type": experiment_type,
        "cache_root": str(cache_root) if cache_root is not None else None,
        "python_version": platform.python_version(),
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "cwd": str(Path.cwd()),
    }

    try:
        import torch
    except Exception as exc:
        payload.update(
            {
                "torch_available": False,
                "torch_import_error": _exception_message(exc),
            }
        )
    else:
        cuda_available = False
        cuda_device_count = 0
        cuda_error: str | None = None
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                cuda_available = bool(torch.cuda.is_available())
                cuda_device_count = (
                    int(torch.cuda.device_count()) if cuda_available else 0
                )
        except Exception as exc:
            cuda_error = _exception_message(exc)
        payload.update(
            {
                "torch_available": True,
                "torch_version": getattr(torch, "__version__", None),
                "cuda_available": cuda_available,
                "cuda_device_count": cuda_device_count,
            }
        )
        if cuda_error is not None:
            payload["cuda_probe_error"] = cuda_error

    payload.update(
        experiments.metadata_for_experiment(
            experiment_type,
            models=models,
            chunk_sizes=chunk_sizes,
            sequence_lengths=sequence_lengths,
        )
    )

    _write_json_file(bundle_paths.environment_path, payload)


def _ensure_model_inspection_prerequisites(
    *,
    run_root: Path,
    models: Sequence[str],
    cache_root: Path | None,
    inspect_log_path: Path,
) -> tuple[opt_assets.InspectionResult, ...]:
    inspection_results: list[opt_assets.InspectionResult] = []
    inspection_root = run_root / _PROFILE_INSPECTION_DIRNAME

    for model_id in models:
        output_root = inspection_root / _slugify(model_id)
        _append_log(
            inspect_log_path,
            f"Ensuring inspect-model prerequisites for {model_id} at {output_root}",
        )
        result = opt_assets.inspect_model(
            model_id=model_id,
            cache_root=cache_root,
            output_root=output_root,
        )
        inspection_results.append(result)
        _append_log(
            inspect_log_path,
            (
                f"Inspect-model complete for {model_id}: "
                f"asset_source={result.asset_source} "
                f"model_constants={result.model_constants_path}"
            ),
        )

    return tuple(inspection_results)


def _append_point_raw_rows(
    *,
    sink: _CanonicalCsvSink,
    family: str,
    plan: _ProfilePointPlan,
    point_result: Mapping[str, Any],
    experiment_type: str,
    point_telemetry: Mapping[str, Any] | None,
) -> int:
    raw_output_path = _optional_string(point_result.get("raw_output_path"))
    if raw_output_path is None:
        return 0

    path = Path(raw_output_path)
    if not path.exists():
        if bool(point_result.get("success")):
            raise RuntimeError(
                f"Successful point {plan.point_id} did not produce {path}"
            )
        return 0

    merged_rows = 0
    result_payload = _optional_mapping(point_result.get("result_payload")) or {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            revised_fields: dict[str, object] = {}
            if experiment_type == experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE:
                if "max_input_tokens" in result_payload:
                    revised_fields["max_input_tokens"] = result_payload.get(
                        "max_input_tokens"
                    )
                if "decode_mode" in plan.manifest_fields:
                    revised_fields["decode_mode"] = plan.manifest_fields["decode_mode"]
                if family == "pcie":
                    revised_fields["overlap_status"] = result_payload.get(
                        "overlap_status"
                    ) or _infer_overlap_status(row)
                if point_telemetry is not None:
                    revised_fields.update(_raw_telemetry_projection(point_telemetry))
            sink.write_row(
                {
                    **row,
                    **revised_fields,
                    "point_id": plan.point_id,
                    "public_status": _result_public_status(point_result),
                    "failure_kind": _optional_string(point_result.get("failure_kind")),
                    "failure_cause": _optional_string(
                        point_result.get("failure_cause")
                    ),
                    "raw_output_path": str(path),
                }
            )
            merged_rows += 1
    return merged_rows


def _append_point_status_row(
    *,
    sink: _CanonicalCsvSink,
    family: str,
    plan: _ProfilePointPlan,
    point_result: Mapping[str, Any],
) -> None:
    row = {
        "point_id": plan.point_id,
        "model_id": str(plan.manifest_fields["model_id"]),
        "public_status": _result_public_status(point_result),
        "failure_kind": _optional_string(point_result.get("failure_kind")),
        "failure_cause": _optional_string(point_result.get("failure_cause")),
        "timed_out": bool(point_result.get("timed_out", False)),
        "exit_code": point_result.get("exit_code"),
        "raw_output_path": _optional_string(point_result.get("raw_output_path")),
        "raw_row_count": point_result.get("raw_row_count"),
        "stdout_log_path": _optional_string(point_result.get("stdout_log_path")),
        "stderr_log_path": _optional_string(point_result.get("stderr_log_path")),
    }
    if family == "prefill":
        row["chunk_tokens"] = plan.manifest_fields["chunk_tokens"]
    elif family == "decode":
        row["sequence_length"] = plan.manifest_fields["sequence_length"]
        row["block_size"] = plan.manifest_fields["block_size"]
    elif family == "pcie":
        row["block_size"] = plan.manifest_fields["block_size"]
    sink.write_row(row)


def _append_telemetry_for_point(
    *,
    run_root: Path,
    point_telemetry: Mapping[str, Any] | None,
) -> None:
    if point_telemetry is None:
        return
    telemetry.append_telemetry_row(run_root, dict(point_telemetry))


def _collect_point_telemetry(
    *,
    family: str,
    plan: _ProfilePointPlan,
    experiment_type: str,
    gpu_id: int,
    point_result: Mapping[str, Any],
) -> dict[str, Any] | None:
    if experiment_type != experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE:
        return None

    raw_output_path = _optional_string(point_result.get("raw_output_path"))
    metrics = _telemetry_metrics_from_raw_output(raw_output_path)
    return telemetry.sample_point_telemetry(
        ts=_utc_timestamp(),
        gpu_id=gpu_id,
        point_id=plan.point_id,
        family=family,
        model_id=str(plan.manifest_fields["model_id"]),
        chunk_tokens=_optional_int(plan.manifest_fields.get("chunk_tokens")),
        sequence_length=_optional_int(plan.manifest_fields.get("sequence_length")),
        block_size=_optional_int(plan.manifest_fields.get("block_size")),
        sm_ai_partition=_optional_int(plan.manifest_fields.get("sm_ai_partition")),
        decode_mode=_optional_string(plan.manifest_fields.get("decode_mode")),
        public_status=_result_public_status(point_result),
        pt_step_ms=metrics["pt_step_ms"],
        pt_mem_alloc_mb=metrics["pt_mem_alloc_mb"],
        pt_mem_reserved_mb=metrics["pt_mem_reserved_mb"],
        pt_workspace_mb=metrics["pt_workspace_mb"],
    )


def _telemetry_metrics_from_raw_output(
    raw_output_path: str | None,
) -> dict[str, float | None]:
    if raw_output_path is None:
        return {
            "pt_step_ms": None,
            "pt_mem_alloc_mb": None,
            "pt_mem_reserved_mb": None,
            "pt_workspace_mb": None,
        }

    path = Path(raw_output_path)
    if not path.exists():
        return {
            "pt_step_ms": None,
            "pt_mem_alloc_mb": None,
            "pt_mem_reserved_mb": None,
            "pt_workspace_mb": None,
        }

    max_duration_us = 0.0
    max_peak_vram_bytes = 0.0
    max_workspace_bytes = 0.0
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            max_duration_us = max(max_duration_us, _parse_float(row.get("duration_us")))
            max_peak_vram_bytes = max(
                max_peak_vram_bytes,
                _parse_float(row.get("peak_vram_bytes")),
            )
            max_workspace_bytes = max(
                max_workspace_bytes,
                _parse_float(row.get("dynamic_workspace_bytes")),
            )
    peak_mb = max_peak_vram_bytes / float(1024**2) if max_peak_vram_bytes else None
    workspace_mb = max_workspace_bytes / float(1024**2) if max_workspace_bytes else None
    return {
        "pt_step_ms": max_duration_us / 1000.0 if max_duration_us else None,
        "pt_mem_alloc_mb": peak_mb,
        "pt_mem_reserved_mb": peak_mb,
        "pt_workspace_mb": workspace_mb,
    }


def _missing_required_outputs(
    *,
    run_root: Path,
    bundle_paths: paths.RunBundlePaths,
    canonical_raw_paths: Mapping[str, Path],
    status_sidecar_paths: Mapping[str, Path],
    parent_log_paths: Mapping[str, Path],
    inspection_results: Sequence[opt_assets.InspectionResult],
    reduction_result: profile_reducer.ProfileReductionResult,
    experiment_type: str,
) -> list[str]:
    required_paths = [
        bundle_paths.environment_path,
        bundle_paths.run_manifest_path,
        reduction_result.model_constants_path,
        reduction_result.prefill_summary_path,
        reduction_result.decode_summary_path,
        reduction_result.pcie_summary_path,
        *canonical_raw_paths.values(),
        *status_sidecar_paths.values(),
        *parent_log_paths.values(),
    ]
    for inspection_result in inspection_results:
        required_paths.append(inspection_result.model_constants_path)
        required_paths.append(inspection_result.asset_manifest_path)
    if experiment_type == experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE:
        required_paths.append(telemetry.telemetry_path_for_run_root(run_root))

    missing_outputs = [
        _relative_run_path(run_root, path)
        for path in required_paths
        if not path.exists()
    ]
    return sorted(set(missing_outputs))


def _write_model_constants_summary(
    csv_path: Path,
    inspection_results: Sequence[opt_assets.InspectionResult],
    *,
    sm_ai_partition: int,
) -> None:
    rows = []
    for inspection_result in inspection_results:
        rows.append(
            {
                "model_id": inspection_result.model_id,
                "sm_ai_partition": int(sm_ai_partition),
                **inspection_result.model_constants,
            }
        )

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(_MODEL_CONSTANTS_SUMMARY_COLUMNS),
            extrasaction="raise",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _build_stage_details(
    *,
    run_root: Path,
    models: Sequence[str],
    chunk_sizes: Sequence[int],
    sequence_lengths: Sequence[int],
    warmup_iterations: int,
    timed_iterations: int,
    gpu_id: int,
    sm_ai_partition: int,
    cache_root: Path | None,
    experiment_type: str,
    bundle_paths: paths.RunBundlePaths,
    canonical_raw_paths: Mapping[str, Path],
    status_sidecar_paths: Mapping[str, Path],
    parent_log_paths: Mapping[str, Path],
    inspection_results: Sequence[opt_assets.InspectionResult],
    family_states: Mapping[str, _ProfilerFamilyState],
    expected_summary_rows: Mapping[str, int],
    actual_summary_rows: Mapping[str, int] | None = None,
    missing_outputs: Sequence[str] = (),
    summary_rows_complete: bool | None = None,
    last_point: Mapping[str, object] | None = None,
) -> dict[str, object]:
    details: dict[str, object] = {
        "models": list(models),
        "chunk_sizes": [int(chunk_size) for chunk_size in chunk_sizes],
        "sequence_lengths": [
            int(sequence_length) for sequence_length in sequence_lengths
        ],
        "warmup_iterations": int(warmup_iterations),
        "timed_iterations": int(timed_iterations),
        "gpu_id": int(gpu_id),
        "sm_ai_partition": int(sm_ai_partition),
        "experiment_type": experiment_type,
        "cache_root": str(cache_root) if cache_root is not None else None,
        "environment_path": _relative_run_path(run_root, bundle_paths.environment_path),
        "canonical_raw_paths": {
            family: _relative_run_path(run_root, path)
            for family, path in canonical_raw_paths.items()
        },
        "status_sidecar_paths": {
            family: _relative_run_path(run_root, path)
            for family, path in status_sidecar_paths.items()
        },
        "parent_log_paths": {
            key: _relative_run_path(run_root, path)
            for key, path in parent_log_paths.items()
        },
        "inspect_model_prerequisites": [
            {
                "model_id": inspection_result.model_id,
                "asset_source": inspection_result.asset_source,
                "output_root": _relative_run_path(
                    run_root, inspection_result.output_root
                ),
                "model_constants_path": _relative_run_path(
                    run_root,
                    inspection_result.model_constants_path,
                ),
                "asset_manifest_path": _relative_run_path(
                    run_root,
                    inspection_result.asset_manifest_path,
                ),
            }
            for inspection_result in inspection_results
        ],
        "profiler_families": {
            family: family_states[family].to_details() for family in _PROFILE_FAMILIES
        },
        "expected_summary_rows": {
            key: int(value) for key, value in expected_summary_rows.items()
        },
    }
    if experiment_type == experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE:
        details["telemetry_path"] = _relative_run_path(
            run_root,
            telemetry.telemetry_path_for_run_root(run_root),
        )
        details["telemetry_tier"] = experiments.RAN_DGXSPARK_V1_TELEMETRY_TIER
        details["sm_ai_partitions"] = list(experiments.RAN_DGXSPARK_V1_SM_AI_PARTITIONS)
        details["decode_modes"] = list(experiments.RAN_DGXSPARK_V1_DECODE_MODES)
    if actual_summary_rows is not None:
        details["actual_summary_rows"] = {
            key: int(value) for key, value in actual_summary_rows.items()
        }
    if summary_rows_complete is not None:
        details["summary_rows_complete"] = bool(summary_rows_complete)
    if missing_outputs:
        details["missing_outputs"] = list(missing_outputs)
    if last_point is not None:
        details["last_point"] = dict(last_point)
    return details


def _derive_stage_status(
    family_states: Mapping[str, _ProfilerFamilyState],
) -> str:
    if any(state.failures > 0 for state in family_states.values()):
        return "profile_failed"
    if any(state.ooms > 0 for state in family_states.values()):
        return "profile_oom"
    return "success"


def _derive_final_stage_status(
    family_states: Mapping[str, _ProfilerFamilyState],
    *,
    missing_outputs: Sequence[str],
    summary_rows_complete: bool,
) -> str:
    if any(state.failures > 0 for state in family_states.values()):
        return "profile_failed"
    if any(state.ooms > 0 for state in family_states.values()):
        return "profile_oom"
    if missing_outputs or not summary_rows_complete:
        return "profile_failed"
    return "success"


def _count_csv_rows(csv_path: Path) -> int:
    if not csv_path.exists():
        return 0
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def _relative_run_path(run_root: Path, path: Path) -> str:
    try:
        return path.relative_to(run_root).as_posix()
    except ValueError:
        return str(path)


def _append_log(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{_utc_timestamp()}] {message}\n")


def _write_json_file(path: Path, payload: Mapping[str, Any]) -> None:
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


def _normalize_positive_int_sequence(
    name: str,
    values: Sequence[int],
) -> tuple[int, ...]:
    if not values:
        raise ValueError(f"{name} must contain at least one value")
    resolved_values = tuple(int(value) for value in values)
    if any(value <= 0 for value in resolved_values):
        raise ValueError(f"{name} must contain only positive integers")
    return resolved_values


def _normalize_non_negative_int(value: Any, *, name: str) -> int:
    resolved_value = int(value)
    if resolved_value < 0:
        raise ValueError(f"{name} must be >= 0")
    return resolved_value


def _normalize_positive_int(value: Any, *, name: str) -> int:
    resolved_value = int(value)
    if resolved_value <= 0:
        raise ValueError(f"{name} must be > 0")
    return resolved_value


def _normalize_sm_ai_partition(value: Any, *, name: str) -> int:
    resolved_value = int(value)
    if resolved_value <= 0 or resolved_value > 100:
        raise ValueError(f"{name} must be between 1 and 100")
    return resolved_value


def _result_public_status(point_result: Mapping[str, Any]) -> str:
    return _optional_string(point_result.get("public_status")) or "profile_failed"


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _utc_timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace(
            "+00:00",
            "Z",
        )
    )


def _exception_message(exc: BaseException) -> str:
    message = str(exc)
    if message:
        return message
    return f"{exc.__class__.__name__} raised without an error message"


def _parse_float(value: object) -> float:
    try:
        if value is None:
            return 0.0
        return float(cast(Any, value))
    except (TypeError, ValueError):
        return 0.0


def _optional_mapping(value: object) -> Mapping[str, Any] | None:
    if isinstance(value, Mapping):
        return value
    return None


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return int(cast(Any, value))


def _raw_telemetry_projection(point_telemetry: Mapping[str, Any]) -> dict[str, object]:
    projected: dict[str, object] = {
        "telemetry_ts": point_telemetry.get("ts"),
    }
    for fieldname in _REVISED_RAW_TELEMETRY_FIELDS:
        if fieldname in point_telemetry:
            projected[fieldname] = point_telemetry.get(fieldname)
    return projected


def _infer_overlap_status(row: Mapping[str, object]) -> str:
    overlap_total_us = _optional_string(row.get("overlap_total_us"))
    dummy_compute_us = _optional_string(row.get("dummy_compute_us"))
    if overlap_total_us is None or dummy_compute_us is None:
        return "unsupported"
    return "measured"


def _slugify(value: str) -> str:
    slug = "".join(
        character if character.isalnum() or character in {"-", "_"} else "-"
        for character in str(value)
    ).strip("-")
    return slug or "value"


def _run_prefill_point_worker(
    point_spec: Mapping[str, Any],
    raw_writer: worker_profile_point.RawCsvWriter,
) -> Mapping[str, Any]:
    chunk_tokens = _normalize_positive_int(
        point_spec.get("chunk_tokens"), name="chunk_tokens"
    )
    result = prefill_profile.profile_prefill_with_writer(
        model_id=str(point_spec["model_id"]),
        raw_writer=raw_writer,
        chunk_tokens=(chunk_tokens,),
        warmup_iterations=_normalize_non_negative_int(
            point_spec.get("warmup_iterations", 0),
            name="warmup_iterations",
        ),
        timed_iterations=_normalize_positive_int(
            point_spec.get("timed_iterations", 1),
            name="timed_iterations",
        ),
        gpu_id=_normalize_non_negative_int(point_spec.get("gpu_id", 0), name="gpu_id"),
        sm_ai_partition=_normalize_sm_ai_partition(
            point_spec.get("sm_ai_partition", 100),
            name="sm_ai_partition",
        ),
        cache_root=_optional_string(point_spec.get("cache_root")),
    )
    return {
        "family": "prefill",
        "model_id": result.model_id,
        "chunk_tokens": chunk_tokens,
        "sm_ai_partition": _normalize_sm_ai_partition(
            point_spec.get("sm_ai_partition", 100),
            name="sm_ai_partition",
        ),
        "max_input_tokens": result.max_input_tokens,
        "row_count": result.row_count,
    }


def _run_decode_point_worker(
    point_spec: Mapping[str, Any],
    raw_writer: worker_profile_point.RawCsvWriter,
) -> Mapping[str, Any]:
    sequence_length = _normalize_positive_int(
        point_spec.get("sequence_length"),
        name="sequence_length",
    )
    block_size = _normalize_positive_int(
        point_spec.get("block_size"), name="block_size"
    )
    decode_mode = _optional_string(point_spec.get("decode_mode")) or "vram"
    result = decode_profile.profile_decode_with_writer(
        model_id=str(point_spec["model_id"]),
        raw_writer=raw_writer,
        sequence_lengths=(sequence_length,),
        block_sizes=(block_size,),
        warmup_iterations=_normalize_non_negative_int(
            point_spec.get("warmup_iterations", 0),
            name="warmup_iterations",
        ),
        timed_iterations=_normalize_positive_int(
            point_spec.get("timed_iterations", 1),
            name="timed_iterations",
        ),
        gpu_id=_normalize_non_negative_int(point_spec.get("gpu_id", 0), name="gpu_id"),
        sm_ai_partition=_normalize_sm_ai_partition(
            point_spec.get("sm_ai_partition", 100),
            name="sm_ai_partition",
        ),
        decode_mode=decode_mode,
        cache_root=_optional_string(point_spec.get("cache_root")),
    )
    return {
        "family": "decode",
        "model_id": result.model_id,
        "sequence_length": sequence_length,
        "block_size": block_size,
        "sm_ai_partition": _normalize_sm_ai_partition(
            point_spec.get("sm_ai_partition", 100),
            name="sm_ai_partition",
        ),
        "decode_mode": result.decode_mode,
        "row_count": result.row_count,
    }


def _run_pcie_point_worker(
    point_spec: Mapping[str, Any],
    raw_writer: worker_profile_point.RawCsvWriter,
) -> Mapping[str, Any]:
    block_size = _normalize_positive_int(
        point_spec.get("block_size"), name="block_size"
    )
    result = pcie_profile.profile_pcie_with_writer(
        model_id=str(point_spec["model_id"]),
        raw_writer=raw_writer,
        block_sizes=(block_size,),
        warmup_iterations=_normalize_non_negative_int(
            point_spec.get("warmup_iterations", 0),
            name="warmup_iterations",
        ),
        timed_iterations=_normalize_positive_int(
            point_spec.get("timed_iterations", 1),
            name="timed_iterations",
        ),
        gpu_id=_normalize_non_negative_int(point_spec.get("gpu_id", 0), name="gpu_id"),
        cache_root=_optional_string(point_spec.get("cache_root")),
    )
    return {
        "family": "pcie",
        "model_id": result.model_id,
        "block_size": block_size,
        "overlap_status": result.overlap_status,
        "row_count": result.row_count,
    }


__all__ = [
    "ProfileOrchestratorResult",
    "orchestrate_profile_run",
]
