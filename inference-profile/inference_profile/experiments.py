from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

LEGACY_EXPERIMENT_TYPE = "legacy"
RAN_DGXSPARK_V1_EXPERIMENT_TYPE = "ran-dgxspark-v1"
EXPERIMENT_TYPES = (
    LEGACY_EXPERIMENT_TYPE,
    RAN_DGXSPARK_V1_EXPERIMENT_TYPE,
)

RAN_DGXSPARK_V1_SCHEMA_VERSION = "ran_dgxspark_v1"
RAN_DGXSPARK_V1_TELEMETRY_TIER = "baseline_nvml_pt"
RAN_DGXSPARK_V1_EXTERNAL_TELEMETRY_TIER = "external_profiler"
RAN_DGXSPARK_V1_SCHEDULER = "envelope_v1"
RAN_DGXSPARK_V1_SM_AI_CAP = 32
RAN_DGXSPARK_V1_L_OUT = 1024
RAN_DGXSPARK_V1_RUN_PREFIX = "revised-ran-dgxspark"
RAN_DGXSPARK_V1_SM_AI_PARTITIONS = (8, 16, 24, 32)
RAN_DGXSPARK_V1_DECODE_MODES = ("vram", "pcie_async")


def normalize_experiment_type(experiment_type: str | None) -> str:
    if experiment_type is None:
        return LEGACY_EXPERIMENT_TYPE
    normalized = experiment_type.strip().lower()
    if normalized not in EXPERIMENT_TYPES:
        raise ValueError(
            f"Unsupported experiment type {experiment_type!r}; expected one of {EXPERIMENT_TYPES}"
        )
    return normalized


def schema_version_for_experiment(experiment_type: str | None) -> str | int:
    normalized = normalize_experiment_type(experiment_type)
    if normalized == RAN_DGXSPARK_V1_EXPERIMENT_TYPE:
        return RAN_DGXSPARK_V1_SCHEMA_VERSION
    return 1


def metadata_for_experiment(
    experiment_type: str | None,
    *,
    models: Sequence[str] | None = None,
    chunk_sizes: Sequence[int] | None = None,
    sequence_lengths: Sequence[int] | None = None,
) -> dict[str, Any]:
    normalized = normalize_experiment_type(experiment_type)
    metadata: dict[str, Any] = {}
    if normalized != RAN_DGXSPARK_V1_EXPERIMENT_TYPE:
        return metadata

    metadata.update(
        {
            "experiment_type": normalized,
            "schema_version": RAN_DGXSPARK_V1_SCHEMA_VERSION,
            "telemetry_tier": RAN_DGXSPARK_V1_TELEMETRY_TIER,
            "scheduler": RAN_DGXSPARK_V1_SCHEDULER,
            "sm_ai_cap": RAN_DGXSPARK_V1_SM_AI_CAP,
            "sm_ai_partitions": list(RAN_DGXSPARK_V1_SM_AI_PARTITIONS),
            "decode_modes": list(RAN_DGXSPARK_V1_DECODE_MODES),
            "l_out": RAN_DGXSPARK_V1_L_OUT,
        }
    )
    if models is not None:
        metadata["models"] = [str(model_id) for model_id in models]
    if chunk_sizes is not None:
        metadata["chunk_sizes"] = [int(value) for value in chunk_sizes]
    if sequence_lengths is not None:
        metadata["sequence_lengths"] = [int(value) for value in sequence_lengths]
    return metadata


def default_run_id_for_experiment(
    experiment_type: str | None,
    *,
    now: datetime | None = None,
) -> str:
    timestamp = _normalize_timestamp(now or datetime.now(timezone.utc)).strftime(
        "%Y%m%d_%H%M%S"
    )
    if normalize_experiment_type(experiment_type) == RAN_DGXSPARK_V1_EXPERIMENT_TYPE:
        return f"{RAN_DGXSPARK_V1_RUN_PREFIX}-{timestamp}"
    return timestamp


def split_manifest_metadata(
    metadata: Mapping[str, Any],
) -> tuple[str | int, dict[str, Any]]:
    schema_version = metadata.get("schema_version", 1)
    extras = dict(metadata)
    extras.pop("schema_version", None)
    return schema_version, extras


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


__all__ = [
    "EXPERIMENT_TYPES",
    "LEGACY_EXPERIMENT_TYPE",
    "RAN_DGXSPARK_V1_EXPERIMENT_TYPE",
    "RAN_DGXSPARK_V1_EXTERNAL_TELEMETRY_TIER",
    "RAN_DGXSPARK_V1_DECODE_MODES",
    "RAN_DGXSPARK_V1_L_OUT",
    "RAN_DGXSPARK_V1_RUN_PREFIX",
    "RAN_DGXSPARK_V1_SCHEMA_VERSION",
    "RAN_DGXSPARK_V1_SCHEDULER",
    "RAN_DGXSPARK_V1_SM_AI_CAP",
    "RAN_DGXSPARK_V1_SM_AI_PARTITIONS",
    "RAN_DGXSPARK_V1_TELEMETRY_TIER",
    "default_run_id_for_experiment",
    "metadata_for_experiment",
    "normalize_experiment_type",
    "schema_version_for_experiment",
    "split_manifest_metadata",
]
