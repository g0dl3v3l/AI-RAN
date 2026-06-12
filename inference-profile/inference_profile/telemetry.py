from __future__ import annotations

from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import re
import subprocess
from typing import Any

from inference_profile import experiments

TELEMETRY_DIRNAME = "telemetry"
BASELINE_TELEMETRY_FILENAME = "telemetry.jsonl"
EXTERNAL_PROFILER_TELEMETRY_TIER = experiments.RAN_DGXSPARK_V1_EXTERNAL_TELEMETRY_TIER
_TELEMETRY_PROVIDER_NAME = "nvidia-smi"
_TELEMETRY_STATUS_OK = "ok"
_TELEMETRY_STATUS_PARTIAL = "partial"
_TELEMETRY_STATUS_UNAVAILABLE = "unavailable"
_MICROSCOPIC_STATUS_UNAVAILABLE = "unavailable"
_MICROSCOPIC_STATUS_ESTIMATED = "estimated"
_MAX_SM_AI_PARTITION = max(experiments.RAN_DGXSPARK_V1_SM_AI_PARTITIONS)
_CHUNK_TOKENS_MIN = 64.0
_CHUNK_TOKENS_MAX = 1024.0
_SEQUENCE_LENGTH_MIN = 1024.0
_SEQUENCE_LENGTH_MAX = 8192.0
_MODEL_PARAM_COUNT_MIN = 125_000_000.0
_MODEL_PARAM_COUNT_MAX = 6_700_000_000.0


@dataclass(frozen=True)
class _MicroscopicEstimate:
    acu_pct: float | None
    gbu_pct: float | None
    smu_pct: float | None
    microscopic_telemetry_status: str


MICROSCOPIC_COUNTER_COLUMNS = (
    "acu_pct",
    "gbu_pct",
    "smu_pct",
)
BASELINE_TELEMETRY_COLUMNS = (
    "ts",
    "point_id",
    "family",
    "model_id",
    "chunk_tokens",
    "sequence_length",
    "block_size",
    "sm_ai_partition",
    "decode_mode",
    "public_status",
    "telemetry_tier",
    "telemetry_provider",
    "telemetry_status",
    "gpu_id",
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
    *MICROSCOPIC_COUNTER_COLUMNS,
    "microscopic_telemetry_status",
    "microscopic_error",
)


def telemetry_path_for_run_root(run_root: str | Path) -> Path:
    run_root = Path(run_root)
    return run_root / TELEMETRY_DIRNAME / BASELINE_TELEMETRY_FILENAME


def make_baseline_telemetry_row(
    *,
    ts: str,
    gpu_id: int,
    point_id: str | None = None,
    family: str | None = None,
    model_id: str | None = None,
    chunk_tokens: int | None = None,
    sequence_length: int | None = None,
    block_size: int | None = None,
    sm_ai_partition: int | None = None,
    decode_mode: str | None = None,
    public_status: str | None = None,
    pt_step_ms: float | None,
    pt_mem_alloc_mb: float | None,
    pt_mem_reserved_mb: float | None,
    pt_workspace_mb: float | None = None,
    gpu_util: float | None = None,
    gpu_mem_used_mb: float | None = None,
    sm_clock_mhz: float | None = None,
    mem_clock_mhz: float | None = None,
    power_w: float | None = None,
    nvml_available: bool = False,
    sampling_error: str | None = None,
    telemetry_provider: str = _TELEMETRY_PROVIDER_NAME,
    telemetry_status: str | None = None,
    telemetry_tier: str = experiments.RAN_DGXSPARK_V1_TELEMETRY_TIER,
    acu_pct: float | None = None,
    gbu_pct: float | None = None,
    smu_pct: float | None = None,
    microscopic_telemetry_status: str = _MICROSCOPIC_STATUS_UNAVAILABLE,
    microscopic_error: str | None = None,
) -> dict[str, Any]:
    resolved_telemetry_status = telemetry_status or _derive_telemetry_status(
        nvml_available=nvml_available,
        pt_step_ms=pt_step_ms,
        pt_mem_alloc_mb=pt_mem_alloc_mb,
        pt_mem_reserved_mb=pt_mem_reserved_mb,
        pt_workspace_mb=pt_workspace_mb,
    )
    return {
        "ts": ts,
        "point_id": point_id,
        "family": family,
        "model_id": model_id,
        "chunk_tokens": _optional_int(chunk_tokens),
        "sequence_length": _optional_int(sequence_length),
        "block_size": _optional_int(block_size),
        "sm_ai_partition": _optional_int(sm_ai_partition),
        "decode_mode": decode_mode,
        "public_status": public_status,
        "telemetry_tier": telemetry_tier,
        "telemetry_provider": telemetry_provider,
        "telemetry_status": resolved_telemetry_status,
        "gpu_id": int(gpu_id),
        "gpu_util": gpu_util,
        "gpu_mem_used_mb": gpu_mem_used_mb,
        "sm_clock_mhz": sm_clock_mhz,
        "mem_clock_mhz": mem_clock_mhz,
        "power_w": power_w,
        "pt_step_ms": pt_step_ms,
        "pt_mem_alloc_mb": pt_mem_alloc_mb,
        "pt_mem_reserved_mb": pt_mem_reserved_mb,
        "pt_workspace_mb": pt_workspace_mb,
        "nvml_available": bool(nvml_available),
        "sampling_error": sampling_error,
        "acu_pct": acu_pct,
        "gbu_pct": gbu_pct,
        "smu_pct": smu_pct,
        "microscopic_telemetry_status": microscopic_telemetry_status,
        "microscopic_error": microscopic_error,
    }


def append_telemetry_row(run_root: str | Path, row: dict[str, Any]) -> Path:
    path = telemetry_path_for_run_root(run_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
    return path


def sample_point_telemetry(
    *,
    ts: str,
    gpu_id: int,
    point_id: str,
    family: str,
    model_id: str,
    pt_step_ms: float | None,
    pt_mem_alloc_mb: float | None,
    pt_mem_reserved_mb: float | None,
    pt_workspace_mb: float | None = None,
    chunk_tokens: int | None = None,
    sequence_length: int | None = None,
    block_size: int | None = None,
    sm_ai_partition: int | None = None,
    decode_mode: str | None = None,
    public_status: str | None = None,
    preferred_tier: str | None = None,
) -> dict[str, Any]:
    nvml_metrics = sample_nvml_baseline(gpu_id=gpu_id)
    requested_tier = _normalize_requested_tier(preferred_tier)
    microscopic_error = None
    if requested_tier == EXTERNAL_PROFILER_TELEMETRY_TIER:
        microscopic_error = "external profiler unavailable"

    microscopic_estimate = estimate_microscopic_counters(
        gpu_util=nvml_metrics.get("gpu_util"),
        sm_ai_partition=sm_ai_partition,
        family=family,
        decode_mode=decode_mode,
        model_id=model_id,
        chunk_tokens=chunk_tokens,
        sequence_length=sequence_length,
        block_size=block_size,
    )

    return make_baseline_telemetry_row(
        ts=ts,
        gpu_id=gpu_id,
        point_id=point_id,
        family=family,
        model_id=model_id,
        chunk_tokens=chunk_tokens,
        sequence_length=sequence_length,
        block_size=block_size,
        sm_ai_partition=sm_ai_partition,
        decode_mode=decode_mode,
        public_status=public_status,
        pt_step_ms=pt_step_ms,
        pt_mem_alloc_mb=pt_mem_alloc_mb,
        pt_mem_reserved_mb=pt_mem_reserved_mb,
        pt_workspace_mb=pt_workspace_mb,
        gpu_util=nvml_metrics["gpu_util"],
        gpu_mem_used_mb=nvml_metrics["gpu_mem_used_mb"],
        sm_clock_mhz=nvml_metrics["sm_clock_mhz"],
        mem_clock_mhz=nvml_metrics["mem_clock_mhz"],
        power_w=nvml_metrics["power_w"],
        nvml_available=bool(nvml_metrics["nvml_available"]),
        telemetry_tier=requested_tier,
        sampling_error=_coalesce_strings(
            nvml_metrics.get("sampling_error"),
            microscopic_error,
        ),
        acu_pct=microscopic_estimate.acu_pct,
        gbu_pct=microscopic_estimate.gbu_pct,
        smu_pct=microscopic_estimate.smu_pct,
        microscopic_telemetry_status=microscopic_estimate.microscopic_telemetry_status,
        microscopic_error=microscopic_error,
    )


def sample_nvml_baseline(*, gpu_id: int) -> dict[str, Any]:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                f"--id={int(gpu_id)}",
                "--query-gpu=utilization.gpu,memory.used,clocks.sm,clocks.mem,power.draw",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "nvml_available": False,
            "gpu_util": None,
            "gpu_mem_used_mb": None,
            "sm_clock_mhz": None,
            "mem_clock_mhz": None,
            "power_w": None,
            "sampling_error": str(exc),
        }

    if result.returncode != 0:
        return {
            "nvml_available": False,
            "gpu_util": None,
            "gpu_mem_used_mb": None,
            "sm_clock_mhz": None,
            "mem_clock_mhz": None,
            "power_w": None,
            "sampling_error": (result.stderr or result.stdout).strip()
            or "nvidia-smi failed",
        }

    values = [value.strip() for value in result.stdout.strip().split(",")]
    if len(values) != 5:
        return {
            "nvml_available": False,
            "gpu_util": None,
            "gpu_mem_used_mb": None,
            "sm_clock_mhz": None,
            "mem_clock_mhz": None,
            "power_w": None,
            "sampling_error": f"unexpected nvidia-smi payload: {result.stdout!r}",
        }

    def _maybe_float(value: str) -> float | None:
        try:
            return float(value)
        except ValueError:
            return None

    return {
        "nvml_available": True,
        "gpu_util": _maybe_float(values[0]),
        "gpu_mem_used_mb": _maybe_float(values[1]),
        "sm_clock_mhz": _maybe_float(values[2]),
        "mem_clock_mhz": _maybe_float(values[3]),
        "power_w": _maybe_float(values[4]),
        "sampling_error": None,
    }


def _derive_telemetry_status(
    *,
    nvml_available: bool,
    pt_step_ms: float | None,
    pt_mem_alloc_mb: float | None,
    pt_mem_reserved_mb: float | None,
    pt_workspace_mb: float | None,
) -> str:
    pt_available = any(
        metric is not None
        for metric in (
            pt_step_ms,
            pt_mem_alloc_mb,
            pt_mem_reserved_mb,
            pt_workspace_mb,
        )
    )
    if nvml_available and pt_available:
        return _TELEMETRY_STATUS_OK
    if nvml_available or pt_available:
        return _TELEMETRY_STATUS_PARTIAL
    return _TELEMETRY_STATUS_UNAVAILABLE


def _normalize_requested_tier(preferred_tier: str | None) -> str:
    candidate = preferred_tier or os.environ.get("INFERENCE_PROFILE_TELEMETRY_TIER")
    if candidate is None:
        return experiments.RAN_DGXSPARK_V1_TELEMETRY_TIER
    normalized = str(candidate).strip().lower()
    if normalized == EXTERNAL_PROFILER_TELEMETRY_TIER:
        return normalized
    return experiments.RAN_DGXSPARK_V1_TELEMETRY_TIER


def estimate_microscopic_counters(
    *,
    gpu_util: Any,
    sm_ai_partition: int | None,
    family: str,
    decode_mode: str | None,
    model_id: str | None = None,
    chunk_tokens: int | None = None,
    sequence_length: int | None = None,
    block_size: int | None = None,
) -> _MicroscopicEstimate:
    del gpu_util

    partition_ratio = _normalized_partition_ratio(sm_ai_partition)
    family_key = str(family or "").strip().lower()
    mode_key = str(decode_mode or "").strip().lower()
    effective_chunk_tokens = chunk_tokens if chunk_tokens is not None else block_size
    z_n = _normalized_log_position(
        value=effective_chunk_tokens,
        minimum=_CHUNK_TOKENS_MIN,
        maximum=_CHUNK_TOKENS_MAX,
    )
    z_l = _normalized_log_position(
        value=sequence_length,
        minimum=_SEQUENCE_LENGTH_MIN,
        maximum=_SEQUENCE_LENGTH_MAX,
    )
    z_nl = z_n * z_l
    z_m = _normalized_model_position(model_id)

    if family_key == "prefill":
        acu_scale = 0.72 + (0.28 * partition_ratio)
        gbu_scale = 0.46 + (0.22 * (1.0 - partition_ratio))
        smu_scale = 0.60 + (0.30 * partition_ratio)
        acu_scale *= 1.0 + (0.10 * z_n) + (0.06 * z_m) + (0.02 * z_m * z_n)
        gbu_scale *= 1.0 + (-0.12 * z_n) + (-0.05 * z_m) + (-0.02 * z_m * z_n)
        smu_scale *= 1.0 + (0.08 * z_n) + (0.05 * z_m) + (0.02 * z_m * z_n)
    elif family_key == "decode" and mode_key == "pcie_async":
        acu_scale = 0.52 + (0.18 * partition_ratio)
        gbu_scale = 0.78 + (0.12 * (1.0 - partition_ratio))
        smu_scale = 0.54 + (0.20 * partition_ratio)
        acu_scale *= (
            1.0
            + (0.00 * z_n)
            + (-0.03 * z_l)
            + (0.00 * z_nl)
            + (0.02 * z_m)
            + (0.00 * z_m * z_n)
            + (-0.01 * z_m * z_l)
        )
        gbu_scale *= (
            1.0
            + (0.02 * z_n)
            + (0.14 * z_l)
            + (0.03 * z_nl)
            + (0.08 * z_m)
            + (0.00 * z_m * z_n)
            + (0.03 * z_m * z_l)
        )
        smu_scale *= (
            1.0
            + (0.01 * z_n)
            + (0.04 * z_l)
            + (0.01 * z_nl)
            + (0.02 * z_m)
            + (0.00 * z_m * z_n)
            + (0.01 * z_m * z_l)
        )
    elif family_key == "decode":
        acu_scale = 0.58 + (0.20 * partition_ratio)
        gbu_scale = 0.70 + (0.10 * (1.0 - partition_ratio))
        smu_scale = 0.56 + (0.24 * partition_ratio)
        acu_scale *= (
            1.0
            + (0.02 * z_n)
            + (0.04 * z_l)
            + (0.01 * z_nl)
            + (0.04 * z_m)
            + (0.00 * z_m * z_n)
            + (0.01 * z_m * z_l)
        )
        gbu_scale *= (
            1.0
            + (0.01 * z_n)
            + (0.10 * z_l)
            + (0.02 * z_nl)
            + (0.03 * z_m)
            + (0.00 * z_m * z_n)
            + (0.02 * z_m * z_l)
        )
        smu_scale *= (
            1.0
            + (0.01 * z_n)
            + (0.06 * z_l)
            + (0.01 * z_nl)
            + (0.03 * z_m)
            + (0.00 * z_m * z_n)
            + (0.01 * z_m * z_l)
        )
    else:
        acu_scale = 0.65
        gbu_scale = 0.65
        smu_scale = 0.65

    return _MicroscopicEstimate(
        acu_pct=_clamp_percent(acu_scale * 100.0),
        gbu_pct=_clamp_percent(gbu_scale * 100.0),
        smu_pct=_clamp_percent(smu_scale * 100.0),
        microscopic_telemetry_status=_MICROSCOPIC_STATUS_ESTIMATED,
    )


def _coerce_percent_or_none(value: Any) -> float | None:
    try:
        return _clamp_percent(float(value))
    except (TypeError, ValueError):
        return None


def _normalized_partition_ratio(sm_ai_partition: int | None) -> float:
    if sm_ai_partition is None:
        return 1.0
    return max(0.0, min(float(sm_ai_partition) / float(_MAX_SM_AI_PARTITION), 1.0))


def _normalized_log_position(
    *,
    value: int | None,
    minimum: float,
    maximum: float,
) -> float:
    if value is None:
        return 0.0
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(numeric_value) or numeric_value <= 0.0:
        return 0.0
    if minimum <= 0.0 or maximum <= minimum:
        return 0.0
    denom = math.log2(maximum) - math.log2(minimum)
    if denom <= 0.0:
        return 0.0
    centered = 2.0 * ((math.log2(numeric_value) - math.log2(minimum)) / denom) - 1.0
    return max(-1.0, min(centered, 1.0))


def _normalized_model_position(model_id: str | None) -> float:
    parameter_count = _estimate_parameter_count(model_id)
    if parameter_count is None:
        return 0.0
    return _normalized_log10_position(
        value=parameter_count,
        minimum=_MODEL_PARAM_COUNT_MIN,
        maximum=_MODEL_PARAM_COUNT_MAX,
    )


def _estimate_parameter_count(model_id: str | None) -> float | None:
    if model_id is None:
        return None
    normalized = str(model_id).strip().lower()
    if not normalized:
        return None
    match = re.search(r"opt-(\d+(?:\.\d+)?)([mb])$", normalized)
    if not match:
        return None
    magnitude = float(match.group(1))
    suffix = match.group(2)
    multiplier = 1_000_000_000.0 if suffix == "b" else 1_000_000.0
    return magnitude * multiplier


def _normalized_log10_position(
    *, value: float, minimum: float, maximum: float
) -> float:
    if not math.isfinite(value) or value <= 0.0:
        return 0.0
    if minimum <= 0.0 or maximum <= minimum:
        return 0.0
    denominator = math.log10(maximum) - math.log10(minimum)
    if denominator <= 0.0:
        return 0.0
    centered = 2.0 * ((math.log10(value) - math.log10(minimum)) / denominator) - 1.0
    return max(-1.0, min(centered, 1.0))


def _clamp_percent(value: float) -> float:
    return max(0.0, min(float(value), 100.0))


def _optional_int(value: int | None) -> int | None:
    return int(value) if value is not None else None


def _coalesce_strings(*values: object) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


__all__ = [
    "BASELINE_TELEMETRY_COLUMNS",
    "BASELINE_TELEMETRY_FILENAME",
    "EXTERNAL_PROFILER_TELEMETRY_TIER",
    "MICROSCOPIC_COUNTER_COLUMNS",
    "TELEMETRY_DIRNAME",
    "append_telemetry_row",
    "make_baseline_telemetry_row",
    "sample_point_telemetry",
    "sample_nvml_baseline",
    "estimate_microscopic_counters",
    "telemetry_path_for_run_root",
]
