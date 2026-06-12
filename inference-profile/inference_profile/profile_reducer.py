from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pandas as pd

from inference_profile import experiments, manifests, telemetry

_SUCCESS_PUBLIC_STATUS = "success"
_STATUS_COLUMN_CANDIDATES = ("public_status", "status", "point_status")
_STATUS_SIDECAR_SUFFIXES = ("_status.csv", "_point_status.csv", ".status.csv")
_POINT_METADATA_JOIN_COLUMNS = ("point_id", "raw_output_path")

_MODEL_CONSTANTS_COLUMNS = ("model_id",)
_PREFILL_GROUP_COLUMNS = ("model_id", "chunk_tokens")
_PREFILL_SUMMARY_COLUMNS = (
    "model_id",
    "chunk_tokens",
    "prefill_max_gemm_us",
    "prefill_workspace_bytes",
    "prefill_parked_activation_bytes",
)
_DECODE_GROUP_COLUMNS = ("model_id", "sequence_length", "block_size")
_DECODE_SUMMARY_COLUMNS = (
    "model_id",
    "sequence_length",
    "block_size",
    "decode_max_gemv_us",
    "attention_fetch_compute_us",
    "reduction_overhead_us",
    "decode_workspace_bytes",
    "decode_parked_activation_bytes",
)
_PCIE_GROUP_COLUMNS = ("model_id", "block_size")
_PCIE_SUMMARY_COLUMNS = (
    "model_id",
    "block_size",
    "kv_block_bytes",
    "transfer_only_us",
    "overlap_total_us",
    "dummy_compute_us",
    "exposed_transfer_us",
    "effective_gbps",
)
_REVISED_TELEMETRY_SUMMARY_COLUMNS = (
    "telemetry_tier",
    "telemetry_provider",
    "telemetry_status",
    "nvml_available",
    "gpu_util",
    "gpu_mem_used_mb",
    "sm_clock_mhz",
    "mem_clock_mhz",
    "power_w",
    "pt_step_ms",
    "pt_mem_alloc_mb",
    "pt_mem_reserved_mb",
    "pt_workspace_mb",
    *telemetry.MICROSCOPIC_COUNTER_COLUMNS,
    "microscopic_telemetry_status",
    "microscopic_error",
)
_REVISED_PREFILL_GROUP_COLUMNS = ("model_id", "chunk_tokens", "sm_ai_partition")
_REVISED_PREFILL_SUMMARY_COLUMNS = (
    "model_id",
    "chunk_tokens",
    "sm_ai_partition",
    "max_input_tokens",
    "prefill_max_gemm_us",
    "prefill_workspace_bytes",
    "prefill_parked_activation_bytes",
    *_REVISED_TELEMETRY_SUMMARY_COLUMNS,
)
_REVISED_DECODE_GROUP_COLUMNS = (
    "model_id",
    "sequence_length",
    "block_size",
    "sm_ai_partition",
    "decode_mode",
)
_REVISED_DECODE_SUMMARY_COLUMNS = (
    "model_id",
    "sequence_length",
    "block_size",
    "sm_ai_partition",
    "decode_mode",
    "decode_max_gemv_us",
    "attention_fetch_compute_us",
    "reduction_overhead_us",
    "decode_workspace_bytes",
    "decode_parked_activation_bytes",
    *_REVISED_TELEMETRY_SUMMARY_COLUMNS,
)
_REVISED_PCIE_SUMMARY_COLUMNS = (
    "model_id",
    "block_size",
    "kv_block_bytes",
    "transfer_only_us",
    "overlap_total_us",
    "dummy_compute_us",
    "exposed_transfer_us",
    "effective_gbps",
    "overlap_status",
    *_REVISED_TELEMETRY_SUMMARY_COLUMNS,
)

_DECODE_GEMV_OP_TYPE = "gemv"
_DECODE_ATTENTION_FETCH_COMPUTE_OP_TYPE = "attention_fetch_compute"
_DECODE_REDUCTION_OVERHEAD_OP_TYPE = "reduction_overhead"
_DECODE_FINAL_GEMV_OP_NAMES = ("out_proj", "fc2")
_PREFILL_GEMM_OP_TYPE = "gemm"


@dataclass(frozen=True)
class ProfileReductionResult:
    """Result of reducing raw profiling events into canonical summaries."""

    model_constants_path: Path
    prefill_summary_path: Path
    decode_summary_path: Path
    pcie_summary_path: Path
    prefill_row_count: int
    decode_row_count: int
    pcie_row_count: int


@dataclass(frozen=True)
class _ProfileRowPartition:
    success_rows: pd.DataFrame
    failed_rows: pd.DataFrame


def reduce_profile_events(
    *,
    run_root: str | Path,
) -> ProfileReductionResult:
    """Reduce raw profiling events into canonical summary files."""
    run_root = Path(run_root)
    raw_root = run_root / "raw"
    derived_root = run_root / "derived"
    derived_root.mkdir(parents=True, exist_ok=True)
    experiment_type = _experiment_type_for_run_root(run_root)
    is_revised = experiment_type == experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE

    prefill_events_path = raw_root / "prefill_events.csv"
    decode_events_path = raw_root / "decode_events.csv"
    pcie_events_path = raw_root / "pcie_events.csv"

    prefill_partition = _partition_profile_rows(
        _load_raw_csv(prefill_events_path),
        event_path=prefill_events_path,
        group_columns=(
            _REVISED_PREFILL_GROUP_COLUMNS if is_revised else _PREFILL_GROUP_COLUMNS
        ),
    )
    decode_partition = _partition_profile_rows(
        _load_raw_csv(decode_events_path),
        event_path=decode_events_path,
        group_columns=(
            _REVISED_DECODE_GROUP_COLUMNS if is_revised else _DECODE_GROUP_COLUMNS
        ),
    )
    pcie_partition = _partition_profile_rows(
        _load_raw_csv(pcie_events_path),
        event_path=pcie_events_path,
        group_columns=_PCIE_GROUP_COLUMNS,
    )

    model_constants = _compute_model_constants(
        raw_root=raw_root,
        prefill_df=prefill_partition.success_rows,
        decode_df=decode_partition.success_rows,
        pcie_df=pcie_partition.success_rows,
    )
    prefill_summary = _reduce_prefill_events(
        prefill_partition.success_rows,
        experiment_type=experiment_type,
    )
    decode_summary = _reduce_decode_events(
        decode_partition.success_rows,
        experiment_type=experiment_type,
    )
    pcie_summary = _reduce_pcie_events(
        pcie_partition.success_rows,
        experiment_type=experiment_type,
    )

    model_constants_path = derived_root / "model_constants.csv"
    prefill_summary_path = derived_root / "prefill_summary.csv"
    decode_summary_path = derived_root / "decode_summary.csv"
    pcie_summary_path = derived_root / "pcie_summary.csv"

    model_constants.to_csv(model_constants_path, index=False)
    prefill_summary.to_csv(prefill_summary_path, index=False)
    decode_summary.to_csv(decode_summary_path, index=False)
    pcie_summary.to_csv(pcie_summary_path, index=False)

    return ProfileReductionResult(
        model_constants_path=model_constants_path,
        prefill_summary_path=prefill_summary_path,
        decode_summary_path=decode_summary_path,
        pcie_summary_path=pcie_summary_path,
        prefill_row_count=len(prefill_summary),
        decode_row_count=len(decode_summary),
        pcie_row_count=len(pcie_summary),
    )


def _load_raw_csv(csv_path: Path) -> pd.DataFrame:
    """Load raw CSV if it exists, otherwise return an empty frame."""
    if not csv_path.exists():
        return pd.DataFrame()
    return pd.read_csv(csv_path)


def _partition_profile_rows(
    df: pd.DataFrame,
    *,
    event_path: Path,
    group_columns: tuple[str, ...],
) -> _ProfileRowPartition:
    if df.empty:
        return _ProfileRowPartition(success_rows=df.copy(), failed_rows=df.copy())

    annotated_df = df.copy()
    direct_status = _extract_direct_status_series(annotated_df)
    sidecar_status = _extract_sidecar_status_series(
        annotated_df,
        event_path=event_path,
        group_columns=group_columns,
    )

    if direct_status is None and sidecar_status is None:
        return _ProfileRowPartition(
            success_rows=annotated_df, failed_rows=annotated_df.iloc[0:0].copy()
        )

    combined_status = direct_status
    if combined_status is None:
        combined_status = pd.Series(index=annotated_df.index, dtype="object")

    if sidecar_status is not None:
        if direct_status is not None:
            conflict_mask = (
                direct_status.notna()
                & sidecar_status.notna()
                & (direct_status != sidecar_status)
            )
            if bool(conflict_mask.any()):
                raise ValueError(f"Conflicting status metadata found for {event_path}")
        combined_status = combined_status.where(combined_status.notna(), sidecar_status)

    failure_mask = combined_status.notna() & (combined_status != _SUCCESS_PUBLIC_STATUS)
    success_rows = annotated_df.loc[~failure_mask].reset_index(drop=True)
    failed_rows = annotated_df.loc[failure_mask].reset_index(drop=True)
    return _ProfileRowPartition(success_rows=success_rows, failed_rows=failed_rows)


def _extract_direct_status_series(df: pd.DataFrame) -> pd.Series | None:
    status_column = _find_status_column(df)
    if status_column is None:
        return None
    return _column_series(df, status_column).map(_normalize_status_value)


def _extract_sidecar_status_series(
    df: pd.DataFrame,
    *,
    event_path: Path,
    group_columns: tuple[str, ...],
) -> pd.Series | None:
    status_sidecar_path = _resolve_status_sidecar_path(event_path)
    if status_sidecar_path is None:
        return None

    sidecar_df = pd.read_csv(status_sidecar_path)
    status_column = _find_status_column(sidecar_df)
    if status_column is None:
        raise ValueError(
            f"Status sidecar {status_sidecar_path} must contain one of {_STATUS_COLUMN_CANDIDATES}"
        )

    join_columns = _resolve_status_join_columns(
        raw_df=df,
        sidecar_df=sidecar_df,
        group_columns=group_columns,
        event_path=event_path,
    )
    normalized_sidecar_df = cast(
        pd.DataFrame,
        sidecar_df[list(join_columns) + [status_column]].copy(),
    )
    normalized_sidecar_df["__status"] = _column_series(
        normalized_sidecar_df, status_column
    ).map(_normalize_status_value)
    normalized_sidecar_df = normalized_sidecar_df.drop(columns=[status_column])
    normalized_sidecar_df = normalized_sidecar_df.dropna(subset=["__status"])
    if normalized_sidecar_df.empty:
        return pd.Series(index=df.index, dtype="object")

    deduplicated_sidecar = _deduplicate_status_sidecar(
        normalized_sidecar_df,
        join_columns=join_columns,
        event_path=event_path,
        status_sidecar_path=status_sidecar_path,
    )
    merged = cast(
        pd.DataFrame,
        df.merge(
            deduplicated_sidecar,
            how="left",
            on=list(join_columns),
            sort=False,
        ),
    )
    return _column_series(merged, "__status")


def _resolve_status_sidecar_path(event_path: Path) -> Path | None:
    stem = event_path.stem
    for suffix in _STATUS_SIDECAR_SUFFIXES:
        candidate = event_path.with_name(f"{stem}{suffix}")
        if candidate.exists():
            return candidate
    return None


def _resolve_status_join_columns(
    *,
    raw_df: pd.DataFrame,
    sidecar_df: pd.DataFrame,
    group_columns: tuple[str, ...],
    event_path: Path,
) -> tuple[str, ...]:
    for metadata_column in _POINT_METADATA_JOIN_COLUMNS:
        if metadata_column in raw_df.columns and metadata_column in sidecar_df.columns:
            return (metadata_column,)

    if all(
        column in raw_df.columns and column in sidecar_df.columns
        for column in group_columns
    ):
        return group_columns

    raise ValueError(
        f"Status sidecar for {event_path} must share point_id, raw_output_path, or the reducer grouping columns {group_columns}"
    )


def _deduplicate_status_sidecar(
    sidecar_df: pd.DataFrame,
    *,
    join_columns: tuple[str, ...],
    event_path: Path,
    status_sidecar_path: Path,
) -> pd.DataFrame:
    grouped = sidecar_df.groupby(list(join_columns), dropna=False, sort=False)[
        "__status"
    ]
    unique_status_counts = cast(pd.Series, grouped.nunique(dropna=True))
    conflicting_keys = cast(pd.Series, unique_status_counts[unique_status_counts > 1])
    if not conflicting_keys.empty:
        raise ValueError(
            f"Status sidecar {status_sidecar_path} contains conflicting statuses for {event_path}"
        )

    return cast(
        pd.DataFrame,
        sidecar_df.groupby(
            list(join_columns),
            dropna=False,
            sort=False,
            as_index=False,
        )
        .first()[list(join_columns) + ["__status"]]
        .copy(),
    )


def _find_status_column(df: pd.DataFrame) -> str | None:
    for candidate in _STATUS_COLUMN_CANDIDATES:
        if candidate in df.columns:
            return candidate
    return None


def _normalize_status_value(value: object) -> str | None:
    missing_value = pd.isna(value)
    if isinstance(missing_value, bool) and missing_value:
        return None
    normalized = str(value).strip().lower()
    return normalized or None


def _compute_model_constants(
    *,
    raw_root: Path,
    prefill_df: pd.DataFrame,
    decode_df: pd.DataFrame,
    pcie_df: pd.DataFrame,
) -> pd.DataFrame:
    model_ids = _collect_model_ids(prefill_df, decode_df, pcie_df)
    model_constants_json = raw_root / "model_constants.json"
    if model_constants_json.exists():
        payload = json.loads(model_constants_json.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            row = dict(payload)
            if "model_id" not in row and len(model_ids) == 1:
                row = {"model_id": next(iter(model_ids)), **row}
            if "model_id" in row:
                columns = [
                    "model_id",
                    *[column for column in row if column != "model_id"],
                ]
                return pd.DataFrame([row], columns=columns)

    rows = [{"model_id": model_id} for model_id in sorted(model_ids)]
    return pd.DataFrame(rows, columns=list(_MODEL_CONSTANTS_COLUMNS))


def _collect_model_ids(*frames: pd.DataFrame) -> set[str]:
    model_ids: set[str] = set()
    for frame in frames:
        if frame.empty or "model_id" not in frame.columns:
            continue
        model_ids.update(
            str(model_id) for model_id in frame["model_id"].dropna().unique()
        )
    return model_ids


def _reduce_prefill_events(
    prefill_df: pd.DataFrame,
    *,
    experiment_type: str = experiments.LEGACY_EXPERIMENT_TYPE,
) -> pd.DataFrame:
    """Reduce prefill raw events to the canonical prefill summary."""
    is_revised = experiment_type == experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE
    group_columns = (
        _REVISED_PREFILL_GROUP_COLUMNS if is_revised else _PREFILL_GROUP_COLUMNS
    )
    summary_columns = (
        _REVISED_PREFILL_SUMMARY_COLUMNS if is_revised else _PREFILL_SUMMARY_COLUMNS
    )
    if prefill_df.empty:
        return pd.DataFrame(columns=list(summary_columns))

    gemm_rows = prefill_df
    if "op_type" in prefill_df.columns:
        op_type = _column_series(prefill_df, "op_type")
        gemm_rows = cast(pd.DataFrame, prefill_df[op_type == _PREFILL_GEMM_OP_TYPE])
        if gemm_rows.empty:
            gemm_rows = prefill_df

    grouped = cast(
        pd.DataFrame,
        prefill_df.groupby(list(group_columns), as_index=False).agg(
            prefill_workspace_bytes=("dynamic_workspace_bytes", "max"),
            prefill_parked_activation_bytes=("output_bytes", "max"),
        ),
    )
    gemm_grouped = cast(
        pd.DataFrame,
        gemm_rows.groupby(list(group_columns), as_index=False).agg(
            prefill_max_gemm_us=("duration_us", "max"),
        ),
    )
    grouped = cast(
        pd.DataFrame,
        grouped.merge(
            gemm_grouped,
            on=list(group_columns),
            how="left",
            validate="one_to_one",
        ),
    )
    if is_revised:
        grouped["max_input_tokens"] = _group_first_value(
            prefill_df,
            group_columns=group_columns,
            value_column="max_input_tokens",
        )
        grouped = _merge_revised_telemetry_summary(
            grouped,
            source_df=prefill_df,
            group_columns=group_columns,
        )
    selected_columns = cast(
        pd.DataFrame,
        grouped.loc[:, list(summary_columns)].copy(),
    )
    return selected_columns.sort_values(by=list(group_columns)).reset_index(drop=True)


def _reduce_decode_events(
    decode_df: pd.DataFrame,
    *,
    experiment_type: str = experiments.LEGACY_EXPERIMENT_TYPE,
) -> pd.DataFrame:
    """Reduce decode raw events to the canonical decode summary."""
    is_revised = experiment_type == experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE
    group_columns = (
        _REVISED_DECODE_GROUP_COLUMNS if is_revised else _DECODE_GROUP_COLUMNS
    )
    summary_columns = (
        _REVISED_DECODE_SUMMARY_COLUMNS if is_revised else _DECODE_SUMMARY_COLUMNS
    )
    if decode_df.empty:
        return pd.DataFrame(columns=list(summary_columns))

    summary_rows: list[dict[str, int | float | str]] = []
    for group_key, grouped_rows in decode_df.groupby(list(group_columns), sort=False):
        sm_ai_partition: object | None = None
        decode_mode: object | None = None
        if is_revised:
            model_id, sequence_length, block_size, sm_ai_partition, decode_mode = cast(
                tuple[object, object, object, object, object],
                group_key,
            )
        else:
            model_id, sequence_length, block_size = cast(
                tuple[object, object, object],
                group_key,
            )
        group = cast(pd.DataFrame, grouped_rows)
        op_type = _column_series(group, "op_type")
        gemv_rows = cast(pd.DataFrame, group[op_type == _DECODE_GEMV_OP_TYPE])
        attention_rows = cast(
            pd.DataFrame,
            group[op_type == _DECODE_ATTENTION_FETCH_COMPUTE_OP_TYPE],
        )
        reduction_rows = cast(
            pd.DataFrame,
            group[op_type == _DECODE_REDUCTION_OVERHEAD_OP_TYPE],
        )

        row: dict[str, int | float | str] = {
            "model_id": str(model_id),
            "sequence_length": _to_int(sequence_length),
            "block_size": _to_int(block_size),
            "decode_max_gemv_us": _series_max_as_float(
                _column_series(gemv_rows, "duration_us")
            ),
            "attention_fetch_compute_us": _series_mean_as_float(
                _column_series(attention_rows, "duration_us")
            ),
            "reduction_overhead_us": _series_mean_as_float(
                _column_series(reduction_rows, "duration_us")
            ),
            "decode_workspace_bytes": _series_max_as_int(
                _column_series(group, "dynamic_workspace_bytes")
            ),
            "decode_parked_activation_bytes": _resolve_decode_parked_activation_bytes(
                group,
                reduction_rows=reduction_rows,
            ),
        }
        if is_revised:
            row["sm_ai_partition"] = _to_int(sm_ai_partition)
            row["decode_mode"] = str(decode_mode)
            row.update(
                cast(dict[str, int | float | str], _aggregate_revised_telemetry(group))
            )
        summary_rows.append(row)

    selected_rows = cast(
        pd.DataFrame,
        pd.DataFrame(summary_rows, columns=list(summary_columns)).copy(),
    )
    return selected_rows.sort_values(by=list(group_columns)).reset_index(drop=True)


def _resolve_decode_parked_activation_bytes(
    group: pd.DataFrame,
    *,
    reduction_rows: pd.DataFrame,
) -> int:
    reduction_output_bytes = _series_max_as_int(
        _column_series(reduction_rows, "output_bytes")
    )
    if reduction_output_bytes > 0:
        return reduction_output_bytes

    final_gemv_rows = cast(
        pd.DataFrame,
        group[
            (_column_series(group, "op_type") == _DECODE_GEMV_OP_TYPE)
            & (
                _column_series(group, "op_name")
                .fillna("")
                .isin(list(_DECODE_FINAL_GEMV_OP_NAMES))
            )
        ],
    )
    final_gemv_output_bytes = _series_max_as_int(
        _column_series(final_gemv_rows, "output_bytes")
    )
    if final_gemv_output_bytes > 0:
        return final_gemv_output_bytes

    return _series_max_as_int(_column_series(group, "output_bytes"))


def _reduce_pcie_events(
    pcie_df: pd.DataFrame,
    *,
    experiment_type: str = experiments.LEGACY_EXPERIMENT_TYPE,
) -> pd.DataFrame:
    """Reduce PCIe raw events to the canonical PCIe summary."""
    is_revised = experiment_type == experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE
    summary_columns = (
        _REVISED_PCIE_SUMMARY_COLUMNS if is_revised else _PCIE_SUMMARY_COLUMNS
    )
    if pcie_df.empty:
        return pd.DataFrame(columns=list(summary_columns))

    grouped = cast(
        pd.DataFrame,
        pcie_df.groupby(list(_PCIE_GROUP_COLUMNS), as_index=False).agg(
            kv_block_bytes=("kv_block_bytes", "first"),
            transfer_only_us=("transfer_only_us", "mean"),
            overlap_total_us=("overlap_total_us", "mean"),
            dummy_compute_us=("dummy_compute_us", "mean"),
        ),
    )
    grouped["exposed_transfer_us"] = grouped.apply(
        lambda row: _calculate_exposed_transfer_from_grouped_row(row),
        axis=1,
    )
    grouped["effective_gbps"] = grouped.apply(
        lambda row: _calculate_effective_gbps(
            kv_block_bytes=row["kv_block_bytes"],
            transfer_only_us=row["transfer_only_us"],
        ),
        axis=1,
    )
    if is_revised:
        grouped["overlap_status"] = _group_first_value(
            pcie_df,
            group_columns=_PCIE_GROUP_COLUMNS,
            value_column="overlap_status",
        ).fillna("measured")
        grouped = _merge_revised_telemetry_summary(
            grouped,
            source_df=pcie_df,
            group_columns=_PCIE_GROUP_COLUMNS,
        )
    selected_columns = cast(
        pd.DataFrame,
        grouped.loc[:, list(summary_columns)].copy(),
    )
    return selected_columns.sort_values(by=list(_PCIE_GROUP_COLUMNS)).reset_index(
        drop=True
    )


def _calculate_effective_gbps(*, kv_block_bytes: Any, transfer_only_us: Any) -> float:
    transfer_only_us_value = float(transfer_only_us)
    if transfer_only_us_value <= 0:
        return 0.0
    return float(kv_block_bytes) / transfer_only_us_value / 1_000.0


def _calculate_exposed_transfer_from_grouped_row(row: pd.Series) -> float | None:
    overlap_total_us = cast(Any, row["overlap_total_us"])
    dummy_compute_us = cast(Any, row["dummy_compute_us"])
    if bool(pd.isna(overlap_total_us)) or bool(pd.isna(dummy_compute_us)):
        return None
    return max(0.0, float(overlap_total_us) - float(dummy_compute_us))


def _experiment_type_for_run_root(run_root: Path) -> str:
    manifest_path = run_root / "run_manifest.json"
    if not manifest_path.exists():
        return experiments.LEGACY_EXPERIMENT_TYPE
    manifest = manifests.load_run_manifest(manifest_path)
    return experiments.normalize_experiment_type(
        cast(str | None, manifest.get("experiment_type"))
    )


def _group_first_value(
    df: pd.DataFrame,
    *,
    group_columns: tuple[str, ...],
    value_column: str,
) -> pd.Series:
    if value_column not in df.columns:
        return pd.Series(dtype="object")
    grouped = cast(
        pd.DataFrame,
        df.groupby(list(group_columns), as_index=False, sort=False)[
            [value_column]
        ].first(),
    )
    return cast(pd.Series, grouped[value_column])


def _merge_revised_telemetry_summary(
    grouped_df: pd.DataFrame,
    *,
    source_df: pd.DataFrame,
    group_columns: tuple[str, ...],
) -> pd.DataFrame:
    summary_rows: list[dict[str, object]] = []
    for group_key, grouped_rows in source_df.groupby(list(group_columns), sort=False):
        if not isinstance(group_key, tuple):
            group_key = (group_key,)
        summary_row: dict[str, object] = {
            column: value
            for column, value in zip(group_columns, group_key, strict=True)
        }
        summary_row.update(
            _aggregate_revised_telemetry(cast(pd.DataFrame, grouped_rows))
        )
        summary_rows.append(summary_row)
    if not summary_rows:
        return grouped_df
    telemetry_summary = pd.DataFrame(summary_rows)
    return cast(
        pd.DataFrame,
        grouped_df.merge(
            telemetry_summary,
            on=list(group_columns),
            how="left",
            validate="one_to_one",
        ),
    )


def _aggregate_revised_telemetry(group: pd.DataFrame) -> dict[str, object]:
    aggregated: dict[str, object] = {}
    for column in _REVISED_TELEMETRY_SUMMARY_COLUMNS:
        if column not in group.columns:
            aggregated[column] = None
            continue
        series = _column_series(group, column)
        if column in {
            "telemetry_tier",
            "telemetry_provider",
            "telemetry_status",
            "microscopic_telemetry_status",
            "microscopic_error",
        }:
            aggregated[column] = _series_first_as_value(series)
        elif column == "nvml_available":
            value = _series_first_as_value(series)
            aggregated[column] = bool(value) if value is not None else None
        else:
            aggregated[column] = _series_mean_as_float_or_none(series)
    return aggregated


def _to_int(value: Any) -> int:
    return int(value)


def _column_series(df: pd.DataFrame, column: str) -> pd.Series:
    return cast(pd.Series, df[column])


def _series_max_as_float(series: pd.Series) -> float:
    if series.empty:
        return 0.0
    max_value = series.max()
    if pd.isna(max_value):
        return 0.0
    return float(max_value)


def _series_mean_as_float(series: pd.Series) -> float:
    if series.empty:
        return 0.0
    mean_value = series.mean()
    if pd.isna(mean_value):
        return 0.0
    return float(mean_value)


def _series_mean_as_float_or_none(series: pd.Series) -> float | None:
    if series.empty:
        return None
    mean_value = series.mean()
    if pd.isna(mean_value):
        return None
    return float(mean_value)


def _series_max_as_int(series: pd.Series) -> int:
    if series.empty:
        return 0
    max_value = series.max()
    if pd.isna(max_value):
        return 0
    return int(max_value)


def _series_first_as_value(series: pd.Series) -> object:
    if series.empty:
        return None
    for value in series:
        if pd.isna(value):
            continue
        return value
    return None


__all__ = ["ProfileReductionResult", "reduce_profile_events"]
