from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import math
from pathlib import Path
from typing import Any, cast

import pandas as pd
from pandas.errors import MergeError

from inference_profile import experiments, telemetry, trace_contract

SIMULATION_INPUTS_FILENAME = "simulation_inputs.csv"
SIMULATION_RESULTS_FILENAME = "ran_inference_profiling_results.csv"
SCHEDULE_TIMELINE_FILENAME = "schedule_timeline.csv"
PACKED_EXEMPLAR_TIMELINE_FILENAME = "packed_exemplar_timeline.csv"
_REVISED_SM_AI_PARTITIONS = experiments.RAN_DGXSPARK_V1_SM_AI_PARTITIONS
_REVISED_SM_RAN_QUANTIZATION_TIERS = (8, 16, 24, 32, 40, 48)
_ANALYTICAL_FULL_GPU_SM_COUNT = float(_REVISED_SM_RAN_QUANTIZATION_TIERS[-1])
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
_REVISED_RESULT_TELEMETRY_PREFIXES = (
    "prefill",
    "decode_vram",
    "decode_pcie_async",
    "pcie",
)
_REVISED_SIMULATION_INPUT_PREFIXES = (
    "prefill",
    "decode_vram",
    "decode_pcie_async",
    "pcie",
)
_REVISED_PREFILL_WIDE_METRIC_COLUMNS = tuple(
    f"{metric}_sm{partition}"
    for metric in (
        "prefill_max_gemm_us",
        "prefill_workspace_bytes",
        "prefill_parked_activation_bytes",
    )
    for partition in _REVISED_SM_AI_PARTITIONS
)
_REVISED_DECODE_WIDE_METRIC_COLUMNS = tuple(
    f"{metric}_{mode}_sm{partition}"
    for metric in (
        "decode_max_gemv_us",
        "attention_fetch_compute_us",
        "reduction_overhead_us",
        "decode_workspace_bytes",
        "decode_parked_activation_bytes",
    )
    for mode in experiments.RAN_DGXSPARK_V1_DECODE_MODES
    for partition in _REVISED_SM_AI_PARTITIONS
)
_REVISED_SIMULATION_INPUT_TELEMETRY_COLUMNS = tuple(
    f"{prefix}_{column}"
    for prefix in _REVISED_SIMULATION_INPUT_PREFIXES
    for column in _REVISED_TELEMETRY_SUMMARY_COLUMNS
)

_MODEL_CONSTANTS_REQUIRED_COLUMNS = (
    "model_id",
    "num_hidden_layers",
    "hidden_size",
    "vram_ceiling_bytes",
)
_MODEL_CONSTANTS_OPTIONAL_COLUMNS = (
    "num_attention_heads",
    "ffn_dim",
    "layer_index",
    "layer_weight_bytes",
    "total_weight_bytes_fp16",
    "total_memory_bytes",
)
_MODEL_CONSTANTS_OUTPUT_COLUMNS = (
    "num_hidden_layers",
    "hidden_size",
    "num_attention_heads",
    "ffn_dim",
    "layer_index",
    "layer_weight_bytes",
    "total_weight_bytes_fp16",
    "total_memory_bytes",
    "vram_ceiling_bytes",
    "kv_bytes_per_token_all_layers",
)
_PREFILL_REQUIRED_COLUMNS = (
    "model_id",
    "chunk_tokens",
    "prefill_max_gemm_us",
    "prefill_workspace_bytes",
    "prefill_parked_activation_bytes",
)
_DECODE_REQUIRED_COLUMNS = (
    "model_id",
    "sequence_length",
    "block_size",
    "decode_max_gemv_us",
    "attention_fetch_compute_us",
    "reduction_overhead_us",
    "decode_workspace_bytes",
    "decode_parked_activation_bytes",
)
_PCIE_REQUIRED_COLUMNS = (
    "model_id",
    "block_size",
    "exposed_transfer_us",
)
_SIMULATION_PROFILE_COLUMNS = (
    "prefill_max_gemm_us",
    "prefill_workspace_bytes",
    "prefill_parked_activation_bytes",
    "decode_max_gemv_us",
    "attention_fetch_compute_us",
    "reduction_overhead_us",
    "decode_workspace_bytes",
    "decode_parked_activation_bytes",
    "pcie_exposed_us",
)
_IDENTIFIER_COLUMNS = ("model_id", "chunk_tokens", "sequence_length")
REVISED_SIMULATION_INPUT_COLUMNS = (
    *_IDENTIFIER_COLUMNS,
    *_MODEL_CONSTANTS_OUTPUT_COLUMNS,
    "sm_ai_partitions_profiled",
    "pcie_exposed_us",
    "pcie_transfer_only_us",
    "pcie_overlap_total_us",
    "pcie_dummy_compute_us",
    "pcie_effective_gbps",
    "pcie_overlap_status",
    *_REVISED_PREFILL_WIDE_METRIC_COLUMNS,
    *_REVISED_DECODE_WIDE_METRIC_COLUMNS,
    *_REVISED_SIMULATION_INPUT_TELEMETRY_COLUMNS,
)
_KV_BYTES_PER_HIDDEN_VALUE = 4
_VRAM_CEILING_NUMERATOR = 60
_VRAM_CEILING_DENOMINATOR = 100
_PROMPT_TOKEN_COUNT = 4096
_PREFILL_ATOMS_PER_LAYER = 6
_DECODE_GEMV_ATOMS_PER_LAYER = 6
_TIME_EPSILON_MS = 1e-12
_SUCCESS_STATUS = "success"
_PREFILL_PHASE = "prefill"
_DECODE_PHASE = "decode"
_PREFILL_MODE = "prefill"
_VRAM_MODE = "vram"
_PCIE_ASYNC_MODE = "pcie_async"
_PREFILL_GEMM_FAMILY = "prefill_gemm"
_DECODE_GEMV_FAMILY = "decode_gemv"
_ATTENTION_FETCH_COMPUTE_FAMILY = "attention_fetch_compute"
_REDUCTION_OVERHEAD_FAMILY = "reduction_overhead"
_PCIE_EXPOSED_TRANSFER_FAMILY = "pcie_exposed_transfer"
_PARKED_ACTIVATION_OOM_STATUS = "parked_activation_oom"
_PREFILL_TRACE_FIT_FAILED_STATUS = "prefill_trace_fit_failed"
_DECODE_TRACE_FIT_FAILED_VRAM_STATUS = "decode_trace_fit_failed_vram"
_DECODE_TRACE_FIT_FAILED_PCIE_ASYNC_STATUS = "decode_trace_fit_failed_pcie_async"
SIMULATION_RESULTS_COLUMNS = (
    "model_id",
    "chunk_tokens",
    "sequence_length",
    "weight_bytes",
    "vram_ceiling_bytes",
    "prefill_max_gemm_us",
    "prefill_workspace_bytes",
    "prefill_parked_activation_bytes",
    "decode_max_gemv_us",
    "attention_fetch_compute_us",
    "reduction_overhead_us",
    "pcie_exposed_us",
    "survival_vram_bytes",
    "decode_runway_bytes",
    "decode_runway_tokens",
    "ttft_ms",
    "tpot_ms_vram",
    "tpot_ms_pcie_async",
    "trace_sha256",
    "status",
)
REVISED_SIMULATION_RESULTS_COLUMNS = (
    "schema_version",
    "experiment_type",
    "scheduler",
    *SIMULATION_RESULTS_COLUMNS,
    "sm_ai_partitions_profiled",
    "trace_sm_ran_tiers",
    "trace_interval_count",
    "trace_intervals_with_ai_budget",
    *_REVISED_PREFILL_WIDE_METRIC_COLUMNS,
    *_REVISED_DECODE_WIDE_METRIC_COLUMNS,
    *(
        f"{prefix}_{column}"
        for prefix in _REVISED_RESULT_TELEMETRY_PREFIXES
        for column in _REVISED_TELEMETRY_SUMMARY_COLUMNS
    ),
    "pcie_effective_gbps",
    "pcie_overlap_status",
)
SCHEDULE_TIMELINE_COLUMNS = (
    "model_id",
    "chunk_tokens",
    "sequence_length",
    "phase",
    "mode",
    "family",
    "chunk_index",
    "token_index",
    "layer_index",
    "atom_index",
    "trace_interval_index",
    "start_time_ms",
    "end_time_ms",
    "duration_ms",
)
REVISED_SCHEDULE_TIMELINE_COLUMNS = (
    *SCHEDULE_TIMELINE_COLUMNS,
    "schema_version",
    "experiment_type",
    "scheduler",
    "sm_utilization",
    "sm_ran_quantized",
    "sm_ai_available",
    "atom_duration_ms_at_sm_ai",
    "segment_progress_fraction",
)
PACKED_EXEMPLAR_TIMELINE_COLUMNS = (
    "schedule_variant",
    "task_id",
    *SCHEDULE_TIMELINE_COLUMNS,
)
REVISED_PACKED_EXEMPLAR_TIMELINE_COLUMNS = (
    "schedule_variant",
    "task_id",
    *REVISED_SCHEDULE_TIMELINE_COLUMNS,
)


@dataclass(frozen=True)
class _IdleGap:
    trace_interval_index: int
    start_time_ms: float
    end_time_ms: float


@dataclass(frozen=True)
class _ScheduledAtomSpec:
    phase: str
    mode: str
    family: str
    chunk_index: int | None
    token_index: int | None
    layer_index: int | None
    atom_index: int
    duration_ms: float


@dataclass(frozen=True)
class _ScheduleOutcome:
    completion_time_ms: float | None
    failure_status: str | None
    timeline_rows: tuple[dict[str, object], ...]

    @property
    def success(self) -> bool:
        return self.failure_status is None and self.completion_time_ms is not None


@dataclass(frozen=True)
class TraceInterval:
    start_time_ms: float
    end_time_ms: float
    sm_utilization: float
    slot_duration_ms: float
    source_schema: str


@dataclass(frozen=True)
class EnvelopeInterval:
    trace_interval_index: int
    start_time_ms: float
    end_time_ms: float
    sm_utilization: float
    sm_ran_quantized: int
    sm_ai_available: int


@dataclass(frozen=True)
class _EnvelopeAtomSpec:
    phase: str
    mode: str
    family: str
    chunk_index: int | None
    token_index: int | None
    layer_index: int | None
    atom_index: int
    duration_ms_by_partition: Mapping[int, float]


@dataclass(frozen=True)
class SimulationResult:
    """Result of running deterministic greedy simulation."""

    run_root: Path
    results_path: Path
    timeline_path: Path
    row_count: int
    packed_timeline_path: Path | None = None


def assemble_simulation_inputs(
    *,
    run_root: str | Path,
    experiment_type: str | None = None,
) -> pd.DataFrame:
    """
    Assemble normalized traces and profile summaries into simulator-ready table.

    Reads the normalized LDPC trace as the authoritative scheduler interval source,
    then joins successful profile summaries into `derived/simulation_inputs.csv`.

    Returns the written DataFrame.
    """
    run_root = Path(run_root)
    resolved_experiment_type = _resolve_experiment_type(
        run_root=run_root,
        experiment_type=experiment_type,
    )
    if resolved_experiment_type == experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE:
        return _assemble_revised_simulation_inputs(run_root=run_root)
    return _assemble_legacy_simulation_inputs(run_root=run_root)


def _assemble_legacy_simulation_inputs(*, run_root: Path) -> pd.DataFrame:
    derived_root = run_root / "derived"
    simulation_inputs_path = derived_root / SIMULATION_INPUTS_FILENAME

    load_normalized_trace_intervals(run_root=run_root)

    model_constants_path = derived_root / "model_constants.csv"
    prefill_summary_path = derived_root / "prefill_summary.csv"
    decode_summary_path = derived_root / "decode_summary.csv"
    pcie_summary_path = derived_root / "pcie_summary.csv"

    model_constants_df = _prepare_model_constants_frame(
        _load_required_csv(model_constants_path),
        csv_path=model_constants_path,
    )
    prefill_df = _select_columns(
        _load_required_csv(prefill_summary_path),
        csv_path=prefill_summary_path,
        required_columns=_PREFILL_REQUIRED_COLUMNS,
    )
    decode_df = _select_columns(
        _load_required_csv(decode_summary_path),
        csv_path=decode_summary_path,
        required_columns=_DECODE_REQUIRED_COLUMNS,
    ).rename(columns={"block_size": "chunk_tokens"})
    pcie_df = _select_columns(
        _load_required_csv(pcie_summary_path),
        csv_path=pcie_summary_path,
        required_columns=_PCIE_REQUIRED_COLUMNS,
    ).rename(
        columns={
            "block_size": "chunk_tokens",
            "exposed_transfer_us": "pcie_exposed_us",
        }
    )

    try:
        simulation_inputs = prefill_df.merge(
            decode_df,
            how="inner",
            on=["model_id", "chunk_tokens"],
            sort=False,
            validate="1:m",
        )
        simulation_inputs = simulation_inputs.merge(
            pcie_df,
            how="inner",
            on=["model_id", "chunk_tokens"],
            sort=False,
            validate="m:1",
        )
        simulation_inputs = simulation_inputs.merge(
            model_constants_df,
            how="inner",
            on=["model_id"],
            sort=False,
            validate="m:1",
        )
    except MergeError as exc:
        raise ValueError(
            f"Simulation input assembly found non-unique summary rows: {exc}"
        ) from exc

    output_columns = [
        *_IDENTIFIER_COLUMNS,
        *[
            column
            for column in _MODEL_CONSTANTS_OUTPUT_COLUMNS
            if column in simulation_inputs.columns
        ],
        *_SIMULATION_PROFILE_COLUMNS,
    ]
    simulation_inputs = simulation_inputs.loc[:, output_columns].copy()
    simulation_inputs = simulation_inputs.sort_values(
        by=list(_IDENTIFIER_COLUMNS)
    ).reset_index(drop=True)
    simulation_inputs.to_csv(simulation_inputs_path, index=False)
    return simulation_inputs


def _assemble_revised_simulation_inputs(*, run_root: Path) -> pd.DataFrame:
    derived_root = run_root / "derived"
    simulation_inputs_path = derived_root / SIMULATION_INPUTS_FILENAME

    load_normalized_trace_intervals(run_root=run_root)

    model_constants_path = derived_root / "model_constants.csv"
    prefill_summary_path = derived_root / "prefill_summary.csv"
    decode_summary_path = derived_root / "decode_summary.csv"
    pcie_summary_path = derived_root / "pcie_summary.csv"

    model_constants_df = _prepare_model_constants_frame(
        _load_required_csv(model_constants_path),
        csv_path=model_constants_path,
    )
    prefill_df = _load_required_csv(prefill_summary_path)
    decode_df = _load_required_csv(decode_summary_path)
    pcie_df = _load_required_csv(pcie_summary_path)

    _require_columns_present(
        prefill_df,
        csv_path=prefill_summary_path,
        required_columns=(
            "model_id",
            "chunk_tokens",
            "sm_ai_partition",
            "prefill_max_gemm_us",
            "prefill_workspace_bytes",
            "prefill_parked_activation_bytes",
        ),
    )
    _require_columns_present(
        decode_df,
        csv_path=decode_summary_path,
        required_columns=(
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
        ),
    )
    _require_columns_present(
        pcie_df,
        csv_path=pcie_summary_path,
        required_columns=(
            "model_id",
            "block_size",
            "exposed_transfer_us",
        ),
    )

    decode_df = decode_df.rename(columns={"block_size": "chunk_tokens"}).copy()
    pcie_df = pcie_df.rename(columns={"block_size": "chunk_tokens"}).copy()

    model_constants_by_model = {
        str(row["model_id"]): row
        for row in model_constants_df.to_dict(orient="records")
    }
    prefill_groups: dict[tuple[str, int], pd.DataFrame] = {}
    for group_key, grouped_rows in prefill_df.groupby(
        ["model_id", "chunk_tokens"],
        sort=False,
    ):
        model_id, chunk_tokens = cast(tuple[object, object], group_key)
        prefill_groups[
            (str(model_id), _coerce_positive_int(chunk_tokens, name="chunk_tokens"))
        ] = cast(pd.DataFrame, grouped_rows).reset_index(drop=True)

    decode_groups: dict[tuple[str, int, int], pd.DataFrame] = {}
    for group_key, grouped_rows in decode_df.groupby(
        ["model_id", "chunk_tokens", "sequence_length"],
        sort=False,
    ):
        model_id, chunk_tokens, sequence_length = cast(
            tuple[object, object, object],
            group_key,
        )
        decode_groups[
            (
                str(model_id),
                _coerce_positive_int(chunk_tokens, name="chunk_tokens"),
                _coerce_positive_int(sequence_length, name="sequence_length"),
            )
        ] = cast(pd.DataFrame, grouped_rows).reset_index(drop=True)

    pcie_groups: dict[tuple[str, int], pd.DataFrame] = {}
    for group_key, grouped_rows in pcie_df.groupby(
        ["model_id", "chunk_tokens"],
        sort=False,
    ):
        model_id, chunk_tokens = cast(tuple[object, object], group_key)
        pcie_groups[
            (str(model_id), _coerce_positive_int(chunk_tokens, name="chunk_tokens"))
        ] = cast(pd.DataFrame, grouped_rows).reset_index(drop=True)

    rows: list[dict[str, object]] = []
    for model_id, chunk_tokens, sequence_length in sorted(decode_groups):
        prefill_group = prefill_groups.get((model_id, chunk_tokens))
        pcie_group = pcie_groups.get((model_id, chunk_tokens))
        model_constants_row = model_constants_by_model.get(model_id)
        if prefill_group is None or pcie_group is None or model_constants_row is None:
            continue
        decode_group = decode_groups[(model_id, chunk_tokens, sequence_length)]
        row = {
            "model_id": model_id,
            "chunk_tokens": chunk_tokens,
            "sequence_length": sequence_length,
            "sm_ai_partitions_profiled": "|".join(
                str(partition) for partition in _REVISED_SM_AI_PARTITIONS
            ),
        }
        for column in _MODEL_CONSTANTS_OUTPUT_COLUMNS:
            row[column] = model_constants_row.get(column)

        pcie_summary_row = pcie_group.iloc[0].to_dict()
        row["pcie_exposed_us"] = _coerce_float(
            pcie_summary_row.get("exposed_transfer_us")
        )
        row["pcie_transfer_only_us"] = _coerce_float(
            pcie_summary_row.get("transfer_only_us")
        )
        row["pcie_overlap_total_us"] = _coerce_float(
            pcie_summary_row.get("overlap_total_us")
        )
        row["pcie_dummy_compute_us"] = _coerce_float(
            pcie_summary_row.get("dummy_compute_us")
        )
        row["pcie_effective_gbps"] = _coerce_float(
            pcie_summary_row.get("effective_gbps")
        )
        row["pcie_overlap_status"] = pcie_summary_row.get("overlap_status")

        prefill_rows_by_partition = _group_rows_by_partition(
            prefill_group,
            group_label=(
                f"prefill_summary rows for {model_id} chunk_tokens={chunk_tokens}"
            ),
            duration_metrics=("prefill_max_gemm_us",),
        )
        for partition in _REVISED_SM_AI_PARTITIONS:
            prefill_summary_row = prefill_rows_by_partition[partition]
            for metric in (
                "prefill_max_gemm_us",
                "prefill_workspace_bytes",
                "prefill_parked_activation_bytes",
            ):
                row[f"{metric}_sm{partition}"] = prefill_summary_row.get(metric)

        for mode in experiments.RAN_DGXSPARK_V1_DECODE_MODES:
            decode_mode_group = cast(
                pd.DataFrame,
                decode_group[decode_group["decode_mode"] == mode].copy(),
            )
            if decode_mode_group.empty:
                raise ValueError(
                    "Revised decode summary is missing mode "
                    f"{mode!r} for model_id={model_id}, chunk_tokens={chunk_tokens}, "
                    f"sequence_length={sequence_length}"
                )
            decode_rows_by_partition = _group_rows_by_partition(
                decode_mode_group,
                group_label=(
                    f"decode_summary rows for {model_id} chunk_tokens={chunk_tokens} "
                    f"sequence_length={sequence_length} mode={mode}"
                ),
                duration_metrics=(
                    "decode_max_gemv_us",
                    "attention_fetch_compute_us",
                    "reduction_overhead_us",
                ),
            )
            for partition in _REVISED_SM_AI_PARTITIONS:
                decode_summary_row = decode_rows_by_partition[partition]
                for metric in (
                    "decode_max_gemv_us",
                    "attention_fetch_compute_us",
                    "reduction_overhead_us",
                    "decode_workspace_bytes",
                    "decode_parked_activation_bytes",
                ):
                    row[f"{metric}_{mode}_sm{partition}"] = decode_summary_row.get(
                        metric
                    )
            _extend_revised_telemetry_columns(
                row,
                prefix=f"decode_{mode}",
                source_df=decode_mode_group,
            )

        _extend_revised_telemetry_columns(
            row,
            prefix="prefill",
            source_df=prefill_group,
        )
        _extend_revised_telemetry_columns(
            row,
            prefix="pcie",
            source_df=pcie_group,
        )
        rows.append(row)

    simulation_inputs = pd.DataFrame(
        rows, columns=list(REVISED_SIMULATION_INPUT_COLUMNS)
    )
    simulation_inputs = simulation_inputs.sort_values(
        by=list(_IDENTIFIER_COLUMNS)
    ).reset_index(drop=True)
    _validate_revised_microscopic_telemetry(simulation_inputs)
    simulation_inputs.to_csv(simulation_inputs_path, index=False)
    return simulation_inputs


def _run_legacy_deterministic_simulation(
    *,
    run_root: Path,
    ldpc_trace_path: str | Path | None,
) -> SimulationResult:
    derived_root = run_root / "derived"
    derived_root.mkdir(parents=True, exist_ok=True)
    normalized_trace_path = derived_root / trace_contract.NORMALIZED_TRACE_FILENAME

    sim_inputs = assemble_simulation_inputs(
        run_root=run_root,
        experiment_type=experiments.LEGACY_EXPERIMENT_TYPE,
    )
    trace_intervals = load_normalized_trace_intervals(run_root=run_root)
    idle_gaps = _extract_idle_gaps(trace_intervals)
    trace_sha256 = _compute_trace_sha256(
        Path(ldpc_trace_path) if ldpc_trace_path is not None else normalized_trace_path
    )

    results_rows: list[dict[str, object]] = []
    timeline_rows: list[dict[str, object]] = []
    for row in sim_inputs.to_dict(orient="records"):
        result_row, row_timeline_rows = _simulate_result_row(
            row,
            idle_gaps=idle_gaps,
            trace_sha256=trace_sha256,
        )
        results_rows.append(result_row)
        timeline_rows.extend(row_timeline_rows)

    results_df = pd.DataFrame(results_rows, columns=list(SIMULATION_RESULTS_COLUMNS))
    timeline_df = pd.DataFrame(timeline_rows, columns=list(SCHEDULE_TIMELINE_COLUMNS))
    _coerce_results_dataframe_dtypes(results_df)

    results_path = derived_root / SIMULATION_RESULTS_FILENAME
    timeline_path = derived_root / SCHEDULE_TIMELINE_FILENAME

    results_df.to_csv(results_path, index=False)
    timeline_df.to_csv(timeline_path, index=False)

    return SimulationResult(
        run_root=run_root,
        results_path=results_path,
        timeline_path=timeline_path,
        row_count=len(results_df),
    )


def _run_revised_deterministic_simulation(
    *,
    run_root: Path,
    ldpc_trace_path: str | Path | None,
) -> SimulationResult:
    derived_root = run_root / "derived"
    derived_root.mkdir(parents=True, exist_ok=True)
    normalized_trace_path = derived_root / trace_contract.NORMALIZED_TRACE_FILENAME

    sim_inputs = assemble_simulation_inputs(
        run_root=run_root,
        experiment_type=experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE,
    )
    envelope_intervals = _build_envelope_intervals(
        load_normalized_trace_intervals(run_root=run_root)
    )
    trace_sha256 = _compute_trace_sha256(
        Path(ldpc_trace_path) if ldpc_trace_path is not None else normalized_trace_path
    )

    results_rows: list[dict[str, object]] = []
    timeline_rows: list[dict[str, object]] = []
    timelines_by_result: dict[tuple[str, int, int], tuple[dict[str, object], ...]] = {}
    for row in sim_inputs.to_dict(orient="records"):
        result_row, row_timeline_rows = _simulate_revised_result_row(
            row,
            envelope_intervals=envelope_intervals,
            trace_sha256=trace_sha256,
        )
        results_rows.append(result_row)
        timeline_rows.extend(row_timeline_rows)
        timelines_by_result[
            (
                str(result_row["model_id"]),
                _coerce_positive_int(
                    result_row.get("chunk_tokens"), name="chunk_tokens"
                ),
                _coerce_positive_int(
                    result_row.get("sequence_length"),
                    name="sequence_length",
                ),
            )
        ] = tuple(row_timeline_rows)

    results_df = pd.DataFrame(
        results_rows,
        columns=list(REVISED_SIMULATION_RESULTS_COLUMNS),
    )
    timeline_df = pd.DataFrame(
        timeline_rows,
        columns=list(REVISED_SCHEDULE_TIMELINE_COLUMNS),
    )
    _coerce_revised_results_dataframe_dtypes(results_df)

    results_path = derived_root / SIMULATION_RESULTS_FILENAME
    timeline_path = derived_root / SCHEDULE_TIMELINE_FILENAME
    results_df.to_csv(results_path, index=False)
    timeline_df.to_csv(timeline_path, index=False)

    packed_timeline_path = derived_root / PACKED_EXEMPLAR_TIMELINE_FILENAME
    successful_rows = [
        result_row
        for result_row in results_rows
        if result_row["status"] == _SUCCESS_STATUS
    ]
    if successful_rows:
        exemplar_result_row = successful_rows[0]
        packed_timeline_path = write_packed_exemplar_timeline(
            run_root=run_root,
            exemplar_result_row=exemplar_result_row,
            exemplar_timeline_rows=timelines_by_result[
                (
                    str(exemplar_result_row["model_id"]),
                    _coerce_positive_int(
                        exemplar_result_row.get("chunk_tokens"),
                        name="chunk_tokens",
                    ),
                    _coerce_positive_int(
                        exemplar_result_row.get("sequence_length"),
                        name="sequence_length",
                    ),
                )
            ],
        )
    else:
        pd.DataFrame(columns=list(REVISED_PACKED_EXEMPLAR_TIMELINE_COLUMNS)).to_csv(
            packed_timeline_path, index=False
        )

    return SimulationResult(
        run_root=run_root,
        results_path=results_path,
        timeline_path=timeline_path,
        row_count=len(results_df),
        packed_timeline_path=packed_timeline_path,
    )


def load_normalized_trace_intervals(
    *,
    run_root: str | Path,
) -> tuple[TraceInterval, ...]:
    run_root = Path(run_root)
    trace_path = run_root / "derived" / trace_contract.NORMALIZED_TRACE_FILENAME
    trace_df = _select_columns(
        _load_required_csv(trace_path),
        csv_path=trace_path,
        required_columns=trace_contract.NORMALIZED_TRACE_HEADERS,
    )
    if trace_df.empty:
        raise ValueError(
            f"Normalized trace must contain at least one row: {trace_path}"
        )

    intervals: list[TraceInterval] = []
    for row in trace_df.to_dict(orient="records"):
        start_time_ms = float(row["time_ms"])
        slot_duration_ms = float(row["slot_duration_ms"])
        if slot_duration_ms < 0:
            raise ValueError(
                f"Normalized trace row at {trace_path} has negative slot_duration_ms"
            )
        intervals.append(
            TraceInterval(
                start_time_ms=start_time_ms,
                end_time_ms=start_time_ms + slot_duration_ms,
                sm_utilization=float(row["sm_utilization"]),
                slot_duration_ms=slot_duration_ms,
                source_schema=str(row["source_schema"]),
            )
        )

    return tuple(intervals)


def run_deterministic_simulation(
    *,
    run_root: str | Path,
    ldpc_trace_path: str | Path | None = None,
    experiment_type: str | None = None,
) -> SimulationResult:
    """
    Run deterministic greedy scheduler over RAN idle gaps.

    Emits:
    - derived/ran_inference_profiling_results.csv (per-point results)
    - derived/schedule_timeline.csv (prefill/decode scheduling intervals)
    """
    run_root = Path(run_root)
    resolved_experiment_type = _resolve_experiment_type(
        run_root=run_root,
        experiment_type=experiment_type,
    )
    if resolved_experiment_type == experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE:
        return _run_revised_deterministic_simulation(
            run_root=run_root,
            ldpc_trace_path=ldpc_trace_path,
        )
    return _run_legacy_deterministic_simulation(
        run_root=run_root,
        ldpc_trace_path=ldpc_trace_path,
    )


def _simulate_result_row(
    row: dict[str, object],
    *,
    idle_gaps: tuple[_IdleGap, ...],
    trace_sha256: str,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    model_id = str(row["model_id"])
    chunk_tokens = _coerce_positive_int(row.get("chunk_tokens"), name="chunk_tokens")
    sequence_length = _coerce_positive_int(
        row.get("sequence_length"),
        name="sequence_length",
    )
    num_hidden_layers = _coerce_positive_int(
        row.get("num_hidden_layers"),
        name="num_hidden_layers",
    )
    kv_bytes_per_token_all_layers = max(
        0,
        _coerce_int(row.get("kv_bytes_per_token_all_layers")),
    )
    vram_ceiling_bytes = _coerce_int(row.get("vram_ceiling_bytes"))
    weight_bytes = _resolve_weight_bytes(row)

    prefill_max_gemm_us = _coerce_float(row.get("prefill_max_gemm_us"))
    prefill_workspace_bytes = _coerce_int(row.get("prefill_workspace_bytes"))
    prefill_parked_activation_bytes = _coerce_int(
        row.get("prefill_parked_activation_bytes")
    )
    decode_max_gemv_us = _coerce_float(row.get("decode_max_gemv_us"))
    attention_fetch_compute_us = _coerce_float(row.get("attention_fetch_compute_us"))
    reduction_overhead_us = _coerce_float(row.get("reduction_overhead_us"))
    decode_workspace_bytes = _coerce_int(row.get("decode_workspace_bytes"))
    decode_parked_activation_bytes = _coerce_int(
        row.get("decode_parked_activation_bytes")
    )
    pcie_exposed_us = _coerce_float(row.get("pcie_exposed_us"))
    bulk_kv_cache_bytes = max(0, chunk_tokens) * kv_bytes_per_token_all_layers

    survival_vram_bytes = (
        vram_ceiling_bytes
        - weight_bytes
        - max(
            prefill_workspace_bytes + prefill_parked_activation_bytes,
            decode_workspace_bytes + decode_parked_activation_bytes,
        )
    )
    decode_runway_bytes = max(
        0,
        vram_ceiling_bytes
        - weight_bytes
        - decode_workspace_bytes
        - decode_parked_activation_bytes
        - bulk_kv_cache_bytes,
    )
    decode_runway_tokens = 0
    if kv_bytes_per_token_all_layers > 0:
        decode_runway_tokens = decode_runway_bytes // kv_bytes_per_token_all_layers

    identifiers = {
        "model_id": model_id,
        "chunk_tokens": chunk_tokens,
        "sequence_length": sequence_length,
    }

    prefill_outcome = _schedule_prefill(
        idle_gaps=idle_gaps,
        identifiers=identifiers,
        chunk_tokens=chunk_tokens,
        num_hidden_layers=num_hidden_layers,
        atom_duration_ms=_microseconds_to_milliseconds(prefill_max_gemm_us),
        weight_bytes=weight_bytes,
        parked_activation_bytes=prefill_parked_activation_bytes,
        vram_ceiling_bytes=vram_ceiling_bytes,
    )
    timeline_rows = list(prefill_outcome.timeline_rows)

    ttft_ms: float | None = None
    tpot_ms_vram: float | None = None
    tpot_ms_pcie_async: float | None = None
    status = prefill_outcome.failure_status or _SUCCESS_STATUS

    if prefill_outcome.success:
        # Keep the absolute trace completion timestamp for internal scheduling
        # while export a latency-valued ttft_ms. The prefill outcome's
        # timeline_rows contain per-atom start/end times; record the first
        # prefill start and the absolute completion time.
        prefill_completion_trace_ms = _require_completion_time_ms(prefill_outcome)
        first_prefill_start_trace_ms = None
        if timeline_rows:
            # timeline_rows were seeded from prefill_outcome.timeline_rows
            first_prefill_start_trace_ms = float(
                cast(float | int | str, timeline_rows[0]["start_time_ms"])
            )
        if first_prefill_start_trace_ms is None:
            # defensive: fall back to completion timestamp (zero-latency)
            ttft_ms = 0.0
        else:
            ttft_ms = prefill_completion_trace_ms - first_prefill_start_trace_ms
        # Use the absolute trace completion time as the scheduling anchor
        # (not_before_ms) so decode scheduling and TPOT math remain anchored
        # to the trace timeline.
        vram_decode_outcome = _schedule_atoms(
            idle_gaps=idle_gaps,
            identifiers=identifiers,
            atoms=_build_decode_atom_specs(
                num_hidden_layers=num_hidden_layers,
                sequence_length=sequence_length,
                chunk_tokens=chunk_tokens,
                decode_max_gemv_us=decode_max_gemv_us,
                attention_fetch_compute_us=attention_fetch_compute_us,
                reduction_overhead_us=reduction_overhead_us,
                pcie_exposed_us=pcie_exposed_us,
                mode=_VRAM_MODE,
            ),
            not_before_ms=prefill_completion_trace_ms,
            failure_status=_DECODE_TRACE_FIT_FAILED_VRAM_STATUS,
        )
        timeline_rows.extend(vram_decode_outcome.timeline_rows)
        if vram_decode_outcome.success:
            # tpot should be the delta between decode completion and the
            # absolute prefill completion anchor on the trace timeline.
            tpot_ms_vram = (
                _require_completion_time_ms(vram_decode_outcome)
                - prefill_completion_trace_ms
            )
            pcie_async_outcome = _schedule_atoms(
                idle_gaps=idle_gaps,
                identifiers=identifiers,
                atoms=_build_decode_atom_specs(
                    num_hidden_layers=num_hidden_layers,
                    sequence_length=sequence_length,
                    chunk_tokens=chunk_tokens,
                    decode_max_gemv_us=decode_max_gemv_us,
                    attention_fetch_compute_us=attention_fetch_compute_us,
                    reduction_overhead_us=reduction_overhead_us,
                    pcie_exposed_us=pcie_exposed_us,
                    mode=_PCIE_ASYNC_MODE,
                ),
                not_before_ms=prefill_completion_trace_ms,
                failure_status=_DECODE_TRACE_FIT_FAILED_PCIE_ASYNC_STATUS,
            )
            timeline_rows.extend(pcie_async_outcome.timeline_rows)
            if pcie_async_outcome.success:
                tpot_ms_pcie_async = (
                    _require_completion_time_ms(pcie_async_outcome)
                    - prefill_completion_trace_ms
                )
            else:
                status = pcie_async_outcome.failure_status or _SUCCESS_STATUS
        else:
            status = vram_decode_outcome.failure_status or _SUCCESS_STATUS

    result_row = {
        "model_id": model_id,
        "chunk_tokens": chunk_tokens,
        "sequence_length": sequence_length,
        "weight_bytes": weight_bytes,
        "vram_ceiling_bytes": vram_ceiling_bytes,
        "prefill_max_gemm_us": prefill_max_gemm_us,
        "prefill_workspace_bytes": prefill_workspace_bytes,
        "prefill_parked_activation_bytes": prefill_parked_activation_bytes,
        "decode_max_gemv_us": decode_max_gemv_us,
        "attention_fetch_compute_us": attention_fetch_compute_us,
        "reduction_overhead_us": reduction_overhead_us,
        "pcie_exposed_us": pcie_exposed_us,
        "survival_vram_bytes": survival_vram_bytes,
        "decode_runway_bytes": decode_runway_bytes,
        "decode_runway_tokens": decode_runway_tokens,
        "ttft_ms": ttft_ms,
        "tpot_ms_vram": tpot_ms_vram,
        "tpot_ms_pcie_async": tpot_ms_pcie_async,
        "trace_sha256": trace_sha256,
        "status": status,
    }
    return result_row, timeline_rows


def _simulate_revised_result_row(
    row: dict[str, object],
    *,
    envelope_intervals: tuple[EnvelopeInterval, ...],
    trace_sha256: str,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    model_id = str(row["model_id"])
    chunk_tokens = _coerce_positive_int(row.get("chunk_tokens"), name="chunk_tokens")
    sequence_length = _coerce_positive_int(
        row.get("sequence_length"),
        name="sequence_length",
    )
    num_hidden_layers = _coerce_positive_int(
        row.get("num_hidden_layers"),
        name="num_hidden_layers",
    )
    kv_bytes_per_token_all_layers = max(
        0,
        _coerce_int(row.get("kv_bytes_per_token_all_layers")),
    )
    vram_ceiling_bytes = _coerce_int(row.get("vram_ceiling_bytes"))
    weight_bytes = _resolve_weight_bytes(row)

    prefill_max_gemm_us_measured_by_partition = _extract_partition_metric_map(
        row,
        metric="prefill_max_gemm_us",
    )
    prefill_max_gemm_us_by_partition = _build_analytical_duration_map(
        prefill_max_gemm_us_measured_by_partition
    )
    prefill_workspace_bytes_by_partition = _extract_partition_metric_map(
        row,
        metric="prefill_workspace_bytes",
        value_kind="int",
    )
    prefill_parked_activation_bytes_by_partition = _extract_partition_metric_map(
        row,
        metric="prefill_parked_activation_bytes",
        value_kind="int",
    )
    decode_max_gemv_us_by_mode = {
        mode: _build_analytical_duration_map(
            _extract_partition_metric_map(
                row,
                metric="decode_max_gemv_us",
                mode=mode,
            )
        )
        for mode in experiments.RAN_DGXSPARK_V1_DECODE_MODES
    }
    attention_fetch_compute_us_by_mode = {
        mode: _build_analytical_duration_map(
            _extract_partition_metric_map(
                row,
                metric="attention_fetch_compute_us",
                mode=mode,
            )
        )
        for mode in experiments.RAN_DGXSPARK_V1_DECODE_MODES
    }
    reduction_overhead_us_by_mode = {
        mode: _build_analytical_duration_map(
            _extract_partition_metric_map(
                row,
                metric="reduction_overhead_us",
                mode=mode,
            )
        )
        for mode in experiments.RAN_DGXSPARK_V1_DECODE_MODES
    }
    decode_workspace_bytes_by_mode = {
        mode: _extract_partition_metric_map(
            row,
            metric="decode_workspace_bytes",
            mode=mode,
            value_kind="int",
        )
        for mode in experiments.RAN_DGXSPARK_V1_DECODE_MODES
    }
    decode_parked_activation_bytes_by_mode = {
        mode: _extract_partition_metric_map(
            row,
            metric="decode_parked_activation_bytes",
            mode=mode,
            value_kind="int",
        )
        for mode in experiments.RAN_DGXSPARK_V1_DECODE_MODES
    }
    prefill_max_gemm_us = _max_mapping_value(prefill_max_gemm_us_by_partition)
    prefill_workspace_bytes = int(
        _max_mapping_value(
            prefill_workspace_bytes_by_partition,
            default=0,
        )
    )
    prefill_parked_activation_bytes = int(
        _max_mapping_value(
            prefill_parked_activation_bytes_by_partition,
            default=0,
        )
    )
    decode_max_gemv_us = _max_nested_mapping_value(decode_max_gemv_us_by_mode)
    attention_fetch_compute_us = _max_nested_mapping_value(
        attention_fetch_compute_us_by_mode
    )
    reduction_overhead_us = _max_nested_mapping_value(reduction_overhead_us_by_mode)
    decode_workspace_bytes = int(
        _max_nested_mapping_value(
            decode_workspace_bytes_by_mode,
            default=0,
        )
    )
    decode_parked_activation_bytes = int(
        _max_nested_mapping_value(
            decode_parked_activation_bytes_by_mode,
            default=0,
        )
    )
    pcie_exposed_us = _coerce_float(row.get("pcie_exposed_us"))

    bulk_kv_cache_bytes = max(0, chunk_tokens) * kv_bytes_per_token_all_layers
    survival_vram_bytes = (
        vram_ceiling_bytes
        - weight_bytes
        - max(
            prefill_workspace_bytes + prefill_parked_activation_bytes,
            decode_workspace_bytes + decode_parked_activation_bytes,
        )
    )
    decode_runway_bytes = max(
        0,
        vram_ceiling_bytes
        - weight_bytes
        - decode_workspace_bytes
        - decode_parked_activation_bytes
        - bulk_kv_cache_bytes,
    )
    decode_runway_tokens = 0
    if kv_bytes_per_token_all_layers > 0:
        decode_runway_tokens = decode_runway_bytes // kv_bytes_per_token_all_layers

    identifiers = {
        "model_id": model_id,
        "chunk_tokens": chunk_tokens,
        "sequence_length": sequence_length,
    }
    prefill_outcome = _schedule_prefill_envelope(
        envelope_intervals=envelope_intervals,
        identifiers=identifiers,
        chunk_tokens=chunk_tokens,
        num_hidden_layers=num_hidden_layers,
        atom_duration_ms_by_partition={
            partition: _microseconds_to_milliseconds(duration_us)
            for partition, duration_us in prefill_max_gemm_us_by_partition.items()
        },
        weight_bytes=weight_bytes,
        parked_activation_bytes=prefill_parked_activation_bytes,
        vram_ceiling_bytes=vram_ceiling_bytes,
    )
    timeline_rows = list(prefill_outcome.timeline_rows)

    ttft_ms: float | None = None
    tpot_ms_vram: float | None = None
    tpot_ms_pcie_async: float | None = None
    status = prefill_outcome.failure_status or _SUCCESS_STATUS

    if prefill_outcome.success:
        prefill_completion_trace_ms = _require_completion_time_ms(prefill_outcome)
        first_prefill_start_trace_ms = None
        if timeline_rows:
            first_prefill_start_trace_ms = float(
                cast(float | int | str, timeline_rows[0]["start_time_ms"])
            )
        ttft_ms = (
            0.0
            if first_prefill_start_trace_ms is None
            else prefill_completion_trace_ms - first_prefill_start_trace_ms
        )
        vram_decode_outcome = _schedule_envelope_atoms(
            envelope_intervals=envelope_intervals,
            identifiers=identifiers,
            atoms=_build_decode_envelope_atom_specs(
                num_hidden_layers=num_hidden_layers,
                sequence_length=sequence_length,
                chunk_tokens=chunk_tokens,
                decode_max_gemv_us_by_partition=decode_max_gemv_us_by_mode[_VRAM_MODE],
                attention_fetch_compute_us_by_partition=attention_fetch_compute_us_by_mode[
                    _VRAM_MODE
                ],
                reduction_overhead_us_by_partition=reduction_overhead_us_by_mode[
                    _VRAM_MODE
                ],
                pcie_exposed_us=pcie_exposed_us,
                mode=_VRAM_MODE,
            ),
            not_before_ms=prefill_completion_trace_ms,
            failure_status=_DECODE_TRACE_FIT_FAILED_VRAM_STATUS,
        )
        timeline_rows.extend(vram_decode_outcome.timeline_rows)
        if vram_decode_outcome.success:
            tpot_ms_vram = (
                _require_completion_time_ms(vram_decode_outcome)
                - prefill_completion_trace_ms
            )
            pcie_async_outcome = _schedule_envelope_atoms(
                envelope_intervals=envelope_intervals,
                identifiers=identifiers,
                atoms=_build_decode_envelope_atom_specs(
                    num_hidden_layers=num_hidden_layers,
                    sequence_length=sequence_length,
                    chunk_tokens=chunk_tokens,
                    decode_max_gemv_us_by_partition=decode_max_gemv_us_by_mode[
                        _PCIE_ASYNC_MODE
                    ],
                    attention_fetch_compute_us_by_partition=attention_fetch_compute_us_by_mode[
                        _PCIE_ASYNC_MODE
                    ],
                    reduction_overhead_us_by_partition=reduction_overhead_us_by_mode[
                        _PCIE_ASYNC_MODE
                    ],
                    pcie_exposed_us=pcie_exposed_us,
                    mode=_PCIE_ASYNC_MODE,
                ),
                not_before_ms=prefill_completion_trace_ms,
                failure_status=_DECODE_TRACE_FIT_FAILED_PCIE_ASYNC_STATUS,
            )
            timeline_rows.extend(pcie_async_outcome.timeline_rows)
            if pcie_async_outcome.success:
                tpot_ms_pcie_async = (
                    _require_completion_time_ms(pcie_async_outcome)
                    - prefill_completion_trace_ms
                )
            else:
                status = pcie_async_outcome.failure_status or _SUCCESS_STATUS
        else:
            status = vram_decode_outcome.failure_status or _SUCCESS_STATUS

    result_row = {
        "schema_version": experiments.RAN_DGXSPARK_V1_SCHEMA_VERSION,
        "experiment_type": experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE,
        "scheduler": experiments.RAN_DGXSPARK_V1_SCHEDULER,
        "model_id": model_id,
        "chunk_tokens": chunk_tokens,
        "sequence_length": sequence_length,
        "weight_bytes": weight_bytes,
        "vram_ceiling_bytes": vram_ceiling_bytes,
        "prefill_max_gemm_us": prefill_max_gemm_us,
        "prefill_workspace_bytes": prefill_workspace_bytes,
        "prefill_parked_activation_bytes": prefill_parked_activation_bytes,
        "decode_max_gemv_us": decode_max_gemv_us,
        "attention_fetch_compute_us": attention_fetch_compute_us,
        "reduction_overhead_us": reduction_overhead_us,
        "pcie_exposed_us": pcie_exposed_us,
        "survival_vram_bytes": survival_vram_bytes,
        "decode_runway_bytes": decode_runway_bytes,
        "decode_runway_tokens": decode_runway_tokens,
        "ttft_ms": ttft_ms,
        "tpot_ms_vram": tpot_ms_vram,
        "tpot_ms_pcie_async": tpot_ms_pcie_async,
        "trace_sha256": trace_sha256,
        "status": status,
        "sm_ai_partitions_profiled": row.get("sm_ai_partitions_profiled"),
        "trace_sm_ran_tiers": "|".join(
            str(tier) for tier in _REVISED_SM_RAN_QUANTIZATION_TIERS
        ),
        "trace_interval_count": len(envelope_intervals),
        "trace_intervals_with_ai_budget": sum(
            1 for interval in envelope_intervals if interval.sm_ai_available > 0
        ),
        "pcie_effective_gbps": _coerce_float(row.get("pcie_effective_gbps")),
        "pcie_overlap_status": row.get("pcie_overlap_status"),
    }
    for column in (
        *_REVISED_PREFILL_WIDE_METRIC_COLUMNS,
        *_REVISED_DECODE_WIDE_METRIC_COLUMNS,
    ):
        result_row[column] = row.get(column)
    for prefix in _REVISED_RESULT_TELEMETRY_PREFIXES:
        for column in _REVISED_TELEMETRY_SUMMARY_COLUMNS:
            result_row[f"{prefix}_{column}"] = row.get(f"{prefix}_{column}")
    return result_row, timeline_rows


def _schedule_prefill_envelope(
    *,
    envelope_intervals: tuple[EnvelopeInterval, ...],
    identifiers: dict[str, object],
    chunk_tokens: int,
    num_hidden_layers: int,
    atom_duration_ms_by_partition: Mapping[int, float],
    weight_bytes: int,
    parked_activation_bytes: int,
    vram_ceiling_bytes: int,
    not_before_ms: float = 0.0,
) -> _ScheduleOutcome:
    chunk_count = math.ceil(_PROMPT_TOKEN_COUNT / chunk_tokens)
    atoms_per_chunk = _PREFILL_ATOMS_PER_LAYER * num_hidden_layers
    timeline_rows: list[dict[str, object]] = []
    interval_index = 0
    current_time_ms = not_before_ms

    for chunk_index in range(chunk_count):
        atoms_completed = 0
        current_atom_progress = 0.0
        while atoms_completed < atoms_per_chunk:
            aligned_interval_index, aligned_time_ms = _align_to_envelope_interval(
                envelope_intervals,
                interval_index=interval_index,
                not_before_ms=current_time_ms,
            )
            if aligned_interval_index is None or aligned_time_ms is None:
                return _ScheduleOutcome(
                    completion_time_ms=None,
                    failure_status=_PREFILL_TRACE_FIT_FAILED_STATUS,
                    timeline_rows=tuple(timeline_rows),
                )
            if (
                aligned_time_ms > current_time_ms + _TIME_EPSILON_MS
                and (atoms_completed > 0 or current_atom_progress > 0.0)
                and not _can_park_chunk(
                    weight_bytes=weight_bytes,
                    parked_activation_bytes=parked_activation_bytes,
                    vram_ceiling_bytes=vram_ceiling_bytes,
                )
            ):
                return _ScheduleOutcome(
                    completion_time_ms=None,
                    failure_status=_PARKED_ACTIVATION_OOM_STATUS,
                    timeline_rows=tuple(timeline_rows),
                )

            interval_index = aligned_interval_index
            current_time_ms = aligned_time_ms
            interval = envelope_intervals[interval_index]
            atom_duration_ms = _duration_for_partition(
                atom_duration_ms_by_partition,
                partition=interval.sm_ai_available,
                label="prefill atom",
            )
            remaining_interval_ms = interval.end_time_ms - current_time_ms
            remaining_atom_fraction = 1.0 - current_atom_progress
            segment_duration_ms = min(
                remaining_interval_ms,
                remaining_atom_fraction * atom_duration_ms,
            )
            segment_progress_fraction = 0.0
            if atom_duration_ms > 0:
                segment_progress_fraction = segment_duration_ms / atom_duration_ms

            layer_index = atoms_completed // _PREFILL_ATOMS_PER_LAYER
            atom_index = atoms_completed % _PREFILL_ATOMS_PER_LAYER
            end_time_ms = current_time_ms + segment_duration_ms
            timeline_rows.append(
                _build_envelope_timeline_row(
                    identifiers=identifiers,
                    atom=_EnvelopeAtomSpec(
                        phase=_PREFILL_PHASE,
                        mode=_PREFILL_MODE,
                        family=_PREFILL_GEMM_FAMILY,
                        chunk_index=chunk_index,
                        token_index=None,
                        layer_index=layer_index,
                        atom_index=atom_index,
                        duration_ms_by_partition=atom_duration_ms_by_partition,
                    ),
                    interval=interval,
                    start_time_ms=current_time_ms,
                    end_time_ms=end_time_ms,
                    atom_duration_ms_at_sm_ai=atom_duration_ms,
                    segment_progress_fraction=segment_progress_fraction,
                )
            )
            current_time_ms = end_time_ms
            current_atom_progress += segment_progress_fraction
            if current_atom_progress >= 1.0 - _TIME_EPSILON_MS:
                atoms_completed += 1
                current_atom_progress = 0.0
            if current_time_ms >= interval.end_time_ms - _TIME_EPSILON_MS:
                interval_index += 1
                current_time_ms = interval.end_time_ms

    return _ScheduleOutcome(
        completion_time_ms=current_time_ms,
        failure_status=None,
        timeline_rows=tuple(timeline_rows),
    )


def _schedule_envelope_atoms(
    *,
    envelope_intervals: tuple[EnvelopeInterval, ...],
    identifiers: dict[str, object],
    atoms: tuple[_EnvelopeAtomSpec, ...],
    not_before_ms: float,
    failure_status: str,
) -> _ScheduleOutcome:
    timeline_rows: list[dict[str, object]] = []
    interval_index = 0
    current_time_ms = not_before_ms

    for atom in atoms:
        current_atom_progress = 0.0
        while current_atom_progress < 1.0 - _TIME_EPSILON_MS:
            aligned_interval_index, aligned_time_ms = _align_to_envelope_interval(
                envelope_intervals,
                interval_index=interval_index,
                not_before_ms=current_time_ms,
            )
            if aligned_interval_index is None or aligned_time_ms is None:
                return _ScheduleOutcome(
                    completion_time_ms=None,
                    failure_status=failure_status,
                    timeline_rows=tuple(timeline_rows),
                )

            interval_index = aligned_interval_index
            current_time_ms = aligned_time_ms
            interval = envelope_intervals[interval_index]
            atom_duration_ms = _duration_for_partition(
                atom.duration_ms_by_partition,
                partition=interval.sm_ai_available,
                label=f"{atom.mode} {atom.family}",
            )
            remaining_interval_ms = interval.end_time_ms - current_time_ms
            remaining_atom_fraction = 1.0 - current_atom_progress
            segment_duration_ms = min(
                remaining_interval_ms,
                remaining_atom_fraction * atom_duration_ms,
            )
            segment_progress_fraction = 0.0
            if atom_duration_ms > 0:
                segment_progress_fraction = segment_duration_ms / atom_duration_ms
            end_time_ms = current_time_ms + segment_duration_ms
            timeline_rows.append(
                _build_envelope_timeline_row(
                    identifiers=identifiers,
                    atom=atom,
                    interval=interval,
                    start_time_ms=current_time_ms,
                    end_time_ms=end_time_ms,
                    atom_duration_ms_at_sm_ai=atom_duration_ms,
                    segment_progress_fraction=segment_progress_fraction,
                )
            )
            current_time_ms = end_time_ms
            current_atom_progress += segment_progress_fraction
            if current_time_ms >= interval.end_time_ms - _TIME_EPSILON_MS:
                interval_index += 1
                current_time_ms = interval.end_time_ms

    return _ScheduleOutcome(
        completion_time_ms=current_time_ms,
        failure_status=None,
        timeline_rows=tuple(timeline_rows),
    )


def _build_decode_envelope_atom_specs(
    *,
    num_hidden_layers: int,
    sequence_length: int,
    chunk_tokens: int,
    decode_max_gemv_us_by_partition: Mapping[int, float],
    attention_fetch_compute_us_by_partition: Mapping[int, float],
    reduction_overhead_us_by_partition: Mapping[int, float],
    pcie_exposed_us: float,
    mode: str,
) -> tuple[_EnvelopeAtomSpec, ...]:
    atoms: list[_EnvelopeAtomSpec] = []
    transfer_atom_count = math.ceil(sequence_length / chunk_tokens)
    pcie_duration_ms_by_partition = {
        partition: _microseconds_to_milliseconds(pcie_exposed_us)
        for partition in _REVISED_SM_AI_PARTITIONS
    }

    for layer_index in range(num_hidden_layers):
        for atom_index in range(_DECODE_GEMV_ATOMS_PER_LAYER):
            atoms.append(
                _EnvelopeAtomSpec(
                    phase=_DECODE_PHASE,
                    mode=mode,
                    family=_DECODE_GEMV_FAMILY,
                    chunk_index=None,
                    token_index=0,
                    layer_index=layer_index,
                    atom_index=atom_index,
                    duration_ms_by_partition={
                        partition: _microseconds_to_milliseconds(duration_us)
                        for partition, duration_us in decode_max_gemv_us_by_partition.items()
                    },
                )
            )
        if mode == _PCIE_ASYNC_MODE:
            for atom_index in range(transfer_atom_count):
                atoms.append(
                    _EnvelopeAtomSpec(
                        phase=_DECODE_PHASE,
                        mode=mode,
                        family=_PCIE_EXPOSED_TRANSFER_FAMILY,
                        chunk_index=None,
                        token_index=0,
                        layer_index=layer_index,
                        atom_index=atom_index,
                        duration_ms_by_partition=pcie_duration_ms_by_partition,
                    )
                )
        atoms.append(
            _EnvelopeAtomSpec(
                phase=_DECODE_PHASE,
                mode=mode,
                family=_ATTENTION_FETCH_COMPUTE_FAMILY,
                chunk_index=None,
                token_index=0,
                layer_index=layer_index,
                atom_index=0,
                duration_ms_by_partition={
                    partition: _microseconds_to_milliseconds(duration_us)
                    for partition, duration_us in attention_fetch_compute_us_by_partition.items()
                },
            )
        )
        atoms.append(
            _EnvelopeAtomSpec(
                phase=_DECODE_PHASE,
                mode=mode,
                family=_REDUCTION_OVERHEAD_FAMILY,
                chunk_index=None,
                token_index=0,
                layer_index=layer_index,
                atom_index=0,
                duration_ms_by_partition={
                    partition: _microseconds_to_milliseconds(duration_us)
                    for partition, duration_us in reduction_overhead_us_by_partition.items()
                },
            )
        )
    return tuple(atoms)


def _build_envelope_intervals(
    trace_intervals: tuple[TraceInterval, ...],
) -> tuple[EnvelopeInterval, ...]:
    return tuple(
        EnvelopeInterval(
            trace_interval_index=index,
            start_time_ms=interval.start_time_ms,
            end_time_ms=interval.end_time_ms,
            sm_utilization=interval.sm_utilization,
            sm_ran_quantized=_quantize_sm_ran(interval.sm_utilization),
            sm_ai_available=min(
                experiments.RAN_DGXSPARK_V1_SM_AI_CAP,
                max(0, 48 - _quantize_sm_ran(interval.sm_utilization)),
            ),
        )
        for index, interval in enumerate(trace_intervals)
        if interval.end_time_ms > interval.start_time_ms
    )


def _build_envelope_timeline_row(
    *,
    identifiers: dict[str, object],
    atom: _EnvelopeAtomSpec,
    interval: EnvelopeInterval,
    start_time_ms: float,
    end_time_ms: float,
    atom_duration_ms_at_sm_ai: float,
    segment_progress_fraction: float,
) -> dict[str, object]:
    return {
        "model_id": identifiers["model_id"],
        "chunk_tokens": identifiers["chunk_tokens"],
        "sequence_length": identifiers["sequence_length"],
        "phase": atom.phase,
        "mode": atom.mode,
        "family": atom.family,
        "chunk_index": atom.chunk_index,
        "token_index": atom.token_index,
        "layer_index": atom.layer_index,
        "atom_index": atom.atom_index,
        "trace_interval_index": interval.trace_interval_index,
        "start_time_ms": start_time_ms,
        "end_time_ms": end_time_ms,
        "duration_ms": end_time_ms - start_time_ms,
        "schema_version": experiments.RAN_DGXSPARK_V1_SCHEMA_VERSION,
        "experiment_type": experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE,
        "scheduler": experiments.RAN_DGXSPARK_V1_SCHEDULER,
        "sm_utilization": interval.sm_utilization,
        "sm_ran_quantized": interval.sm_ran_quantized,
        "sm_ai_available": interval.sm_ai_available,
        "atom_duration_ms_at_sm_ai": atom_duration_ms_at_sm_ai,
        "segment_progress_fraction": segment_progress_fraction,
    }


def _align_to_envelope_interval(
    envelope_intervals: tuple[EnvelopeInterval, ...],
    *,
    interval_index: int,
    not_before_ms: float,
) -> tuple[int | None, float | None]:
    search_index = max(0, interval_index)
    while search_index < len(envelope_intervals):
        interval = envelope_intervals[search_index]
        if interval.sm_ai_available <= 0:
            search_index += 1
            continue
        if interval.end_time_ms <= not_before_ms + _TIME_EPSILON_MS:
            search_index += 1
            continue
        return search_index, max(not_before_ms, interval.start_time_ms)
    return None, None


def _build_revised_packed_exemplar_timeline_rows(
    *,
    envelope_intervals: tuple[EnvelopeInterval, ...],
    exemplar_result_row: Mapping[str, object],
    exemplar_timeline_rows: Sequence[Mapping[str, object]],
    num_hidden_layers: int | None = None,
) -> tuple[dict[str, object], ...]:
    resolved_num_hidden_layers = _resolve_packed_num_hidden_layers(
        exemplar_result_row=exemplar_result_row,
        exemplar_timeline_rows=exemplar_timeline_rows,
        num_hidden_layers=num_hidden_layers,
    )
    identifiers = {
        "model_id": str(exemplar_result_row["model_id"]),
        "chunk_tokens": _coerce_positive_int(
            exemplar_result_row.get("chunk_tokens"),
            name="chunk_tokens",
        ),
        "sequence_length": _coerce_positive_int(
            exemplar_result_row.get("sequence_length"),
            name="sequence_length",
        ),
    }
    weight_bytes = _resolve_weight_bytes(dict(exemplar_result_row))
    vram_ceiling_bytes = _coerce_int(exemplar_result_row.get("vram_ceiling_bytes"))
    prefill_parked_activation_bytes = _coerce_int(
        exemplar_result_row.get("prefill_parked_activation_bytes")
    )
    prefill_duration_map = _resolve_revised_duration_map(
        exemplar_result_row,
        exemplar_timeline_rows,
        metric="prefill_max_gemm_us",
        mode=None,
        phase=_PREFILL_PHASE,
        family=_PREFILL_GEMM_FAMILY,
    )
    packed_rows: list[dict[str, object]] = []
    for schedule_variant, failure_status in (
        (_VRAM_MODE, _DECODE_TRACE_FIT_FAILED_VRAM_STATUS),
        (_PCIE_ASYNC_MODE, _DECODE_TRACE_FIT_FAILED_PCIE_ASYNC_STATUS),
    ):
        task_id = 0
        next_task_not_before_ms = 0.0
        decode_max_gemv_duration_map = _resolve_revised_duration_map(
            exemplar_result_row,
            exemplar_timeline_rows,
            metric="decode_max_gemv_us",
            mode=schedule_variant,
            phase=_DECODE_PHASE,
            family=_DECODE_GEMV_FAMILY,
        )
        attention_duration_map = _resolve_revised_duration_map(
            exemplar_result_row,
            exemplar_timeline_rows,
            metric="attention_fetch_compute_us",
            mode=schedule_variant,
            phase=_DECODE_PHASE,
            family=_ATTENTION_FETCH_COMPUTE_FAMILY,
        )
        reduction_duration_map = _resolve_revised_duration_map(
            exemplar_result_row,
            exemplar_timeline_rows,
            metric="reduction_overhead_us",
            mode=schedule_variant,
            phase=_DECODE_PHASE,
            family=_REDUCTION_OVERHEAD_FAMILY,
        )
        pcie_duration_map = (
            _resolve_revised_duration_map(
                exemplar_result_row,
                exemplar_timeline_rows,
                metric="pcie_exposed_us",
                mode=schedule_variant,
                phase=_DECODE_PHASE,
                family=_PCIE_EXPOSED_TRANSFER_FAMILY,
            )
            if schedule_variant == _PCIE_ASYNC_MODE
            else {
                partition: _microseconds_to_milliseconds(
                    _coerce_float(exemplar_result_row.get("pcie_exposed_us"))
                )
                for partition in _REVISED_SM_AI_PARTITIONS
            }
        )
        while True:
            prefill_outcome = _schedule_prefill_envelope(
                envelope_intervals=envelope_intervals,
                identifiers=identifiers,
                chunk_tokens=int(identifiers["chunk_tokens"]),
                num_hidden_layers=resolved_num_hidden_layers,
                atom_duration_ms_by_partition=prefill_duration_map,
                weight_bytes=weight_bytes,
                parked_activation_bytes=prefill_parked_activation_bytes,
                vram_ceiling_bytes=vram_ceiling_bytes,
                not_before_ms=next_task_not_before_ms,
            )
            if not prefill_outcome.success:
                break

            prefill_completion_ms = _require_completion_time_ms(prefill_outcome)
            decode_outcome = _schedule_envelope_atoms(
                envelope_intervals=envelope_intervals,
                identifiers=identifiers,
                atoms=_build_decode_envelope_atom_specs(
                    num_hidden_layers=resolved_num_hidden_layers,
                    sequence_length=int(identifiers["sequence_length"]),
                    chunk_tokens=int(identifiers["chunk_tokens"]),
                    decode_max_gemv_us_by_partition={
                        partition: duration_ms * 1_000.0
                        for partition, duration_ms in decode_max_gemv_duration_map.items()
                    },
                    attention_fetch_compute_us_by_partition={
                        partition: duration_ms * 1_000.0
                        for partition, duration_ms in attention_duration_map.items()
                    },
                    reduction_overhead_us_by_partition={
                        partition: duration_ms * 1_000.0
                        for partition, duration_ms in reduction_duration_map.items()
                    },
                    pcie_exposed_us=_max_mapping_value(pcie_duration_map) * 1_000.0,
                    mode=schedule_variant,
                ),
                not_before_ms=prefill_completion_ms,
                failure_status=failure_status,
            )
            if not decode_outcome.success:
                break

            packed_rows.extend(
                _annotate_packed_timeline_rows(
                    prefill_outcome.timeline_rows,
                    schedule_variant=schedule_variant,
                    task_id=task_id,
                )
            )
            packed_rows.extend(
                _annotate_packed_timeline_rows(
                    decode_outcome.timeline_rows,
                    schedule_variant=schedule_variant,
                    task_id=task_id,
                )
            )
            next_task_not_before_ms = _require_completion_time_ms(decode_outcome)
            task_id += 1

    return tuple(packed_rows)


def write_packed_exemplar_timeline(
    *,
    run_root: str | Path,
    exemplar_result_row: Mapping[str, object],
    exemplar_timeline_rows: Sequence[Mapping[str, object]],
    num_hidden_layers: int | None = None,
) -> Path:
    run_root = Path(run_root)
    derived_root = run_root / "derived"
    derived_root.mkdir(parents=True, exist_ok=True)

    packed_rows = build_packed_exemplar_timeline_rows(
        idle_gaps=_extract_idle_gaps(
            load_normalized_trace_intervals(run_root=run_root)
        ),
        exemplar_result_row=exemplar_result_row,
        exemplar_timeline_rows=exemplar_timeline_rows,
        num_hidden_layers=num_hidden_layers,
        run_root=run_root,
    )
    packed_timeline_path = derived_root / PACKED_EXEMPLAR_TIMELINE_FILENAME
    packed_columns = (
        REVISED_PACKED_EXEMPLAR_TIMELINE_COLUMNS
        if _uses_revised_scheduler(
            exemplar_result_row=exemplar_result_row,
            exemplar_timeline_rows=exemplar_timeline_rows,
        )
        else PACKED_EXEMPLAR_TIMELINE_COLUMNS
    )
    pd.DataFrame(packed_rows, columns=list(packed_columns)).to_csv(
        packed_timeline_path,
        index=False,
    )
    return packed_timeline_path


def build_packed_exemplar_timeline_rows(
    *,
    idle_gaps: tuple[_IdleGap, ...],
    exemplar_result_row: Mapping[str, object],
    exemplar_timeline_rows: Sequence[Mapping[str, object]],
    num_hidden_layers: int | None = None,
    run_root: str | Path | None = None,
) -> tuple[dict[str, object], ...]:
    if _uses_revised_scheduler(
        exemplar_result_row=exemplar_result_row,
        exemplar_timeline_rows=exemplar_timeline_rows,
    ):
        resolved_run_root = Path(run_root) if run_root is not None else None
        if resolved_run_root is None:
            raise ValueError(
                "Revised packed exemplar scheduling requires the run_root context"
            )
        return _build_revised_packed_exemplar_timeline_rows(
            envelope_intervals=_build_envelope_intervals(
                load_normalized_trace_intervals(run_root=resolved_run_root)
            ),
            exemplar_result_row=exemplar_result_row,
            exemplar_timeline_rows=exemplar_timeline_rows,
            num_hidden_layers=num_hidden_layers,
        )

    resolved_num_hidden_layers = _resolve_packed_num_hidden_layers(
        exemplar_result_row=exemplar_result_row,
        exemplar_timeline_rows=exemplar_timeline_rows,
        num_hidden_layers=num_hidden_layers,
    )
    identifiers = {
        "model_id": str(exemplar_result_row["model_id"]),
        "chunk_tokens": _coerce_positive_int(
            exemplar_result_row.get("chunk_tokens"),
            name="chunk_tokens",
        ),
        "sequence_length": _coerce_positive_int(
            exemplar_result_row.get("sequence_length"),
            name="sequence_length",
        ),
    }
    weight_bytes = _resolve_weight_bytes(dict(exemplar_result_row))
    vram_ceiling_bytes = _coerce_int(exemplar_result_row.get("vram_ceiling_bytes"))
    prefill_atom_duration_ms = _microseconds_to_milliseconds(
        _coerce_float(exemplar_result_row.get("prefill_max_gemm_us"))
    )
    prefill_parked_activation_bytes = _coerce_int(
        exemplar_result_row.get("prefill_parked_activation_bytes")
    )
    decode_max_gemv_us = _coerce_float(exemplar_result_row.get("decode_max_gemv_us"))
    attention_fetch_compute_us = _coerce_float(
        exemplar_result_row.get("attention_fetch_compute_us")
    )
    reduction_overhead_us = _coerce_float(
        exemplar_result_row.get("reduction_overhead_us")
    )
    pcie_exposed_us = _coerce_float(exemplar_result_row.get("pcie_exposed_us"))

    packed_rows: list[dict[str, object]] = []
    for schedule_variant, failure_status in (
        (_VRAM_MODE, _DECODE_TRACE_FIT_FAILED_VRAM_STATUS),
        (_PCIE_ASYNC_MODE, _DECODE_TRACE_FIT_FAILED_PCIE_ASYNC_STATUS),
    ):
        task_id = 0
        next_task_not_before_ms = 0.0
        while True:
            prefill_outcome = _schedule_prefill(
                idle_gaps=idle_gaps,
                identifiers=identifiers,
                chunk_tokens=int(identifiers["chunk_tokens"]),
                num_hidden_layers=resolved_num_hidden_layers,
                atom_duration_ms=prefill_atom_duration_ms,
                weight_bytes=weight_bytes,
                parked_activation_bytes=prefill_parked_activation_bytes,
                vram_ceiling_bytes=vram_ceiling_bytes,
                not_before_ms=next_task_not_before_ms,
            )
            if not prefill_outcome.success:
                break

            prefill_completion_ms = _require_completion_time_ms(prefill_outcome)
            decode_outcome = _schedule_atoms(
                idle_gaps=idle_gaps,
                identifiers=identifiers,
                atoms=_build_decode_atom_specs(
                    num_hidden_layers=resolved_num_hidden_layers,
                    sequence_length=int(identifiers["sequence_length"]),
                    chunk_tokens=int(identifiers["chunk_tokens"]),
                    decode_max_gemv_us=decode_max_gemv_us,
                    attention_fetch_compute_us=attention_fetch_compute_us,
                    reduction_overhead_us=reduction_overhead_us,
                    pcie_exposed_us=pcie_exposed_us,
                    mode=schedule_variant,
                ),
                not_before_ms=prefill_completion_ms,
                failure_status=failure_status,
            )
            if not decode_outcome.success:
                break

            packed_rows.extend(
                _annotate_packed_timeline_rows(
                    prefill_outcome.timeline_rows,
                    schedule_variant=schedule_variant,
                    task_id=task_id,
                )
            )
            packed_rows.extend(
                _annotate_packed_timeline_rows(
                    decode_outcome.timeline_rows,
                    schedule_variant=schedule_variant,
                    task_id=task_id,
                )
            )
            next_task_not_before_ms = _require_completion_time_ms(decode_outcome)
            task_id += 1

    return tuple(packed_rows)


def _schedule_prefill(
    *,
    idle_gaps: tuple[_IdleGap, ...],
    identifiers: dict[str, object],
    chunk_tokens: int,
    num_hidden_layers: int,
    atom_duration_ms: float,
    weight_bytes: int,
    parked_activation_bytes: int,
    vram_ceiling_bytes: int,
    not_before_ms: float = 0.0,
) -> _ScheduleOutcome:
    chunk_count = math.ceil(_PROMPT_TOKEN_COUNT / chunk_tokens)
    atoms_per_chunk = _PREFILL_ATOMS_PER_LAYER * num_hidden_layers
    timeline_rows: list[dict[str, object]] = []
    gap_index = 0
    current_time_ms = not_before_ms

    for chunk_index in range(chunk_count):
        atoms_completed = 0
        while atoms_completed < atoms_per_chunk:
            aligned_gap_index, aligned_time_ms = _align_to_idle_gap(
                idle_gaps,
                gap_index=gap_index,
                not_before_ms=current_time_ms,
            )
            if aligned_gap_index is None or aligned_time_ms is None:
                return _ScheduleOutcome(
                    completion_time_ms=None,
                    failure_status=_PREFILL_TRACE_FIT_FAILED_STATUS,
                    timeline_rows=tuple(timeline_rows),
                )

            gap_index = aligned_gap_index
            current_time_ms = aligned_time_ms
            gap = idle_gaps[gap_index]
            remaining_gap_ms = gap.end_time_ms - current_time_ms
            if atom_duration_ms > remaining_gap_ms + _TIME_EPSILON_MS:
                if atoms_completed > 0 and not _can_park_chunk(
                    weight_bytes=weight_bytes,
                    parked_activation_bytes=parked_activation_bytes,
                    vram_ceiling_bytes=vram_ceiling_bytes,
                ):
                    return _ScheduleOutcome(
                        completion_time_ms=None,
                        failure_status=_PARKED_ACTIVATION_OOM_STATUS,
                        timeline_rows=tuple(timeline_rows),
                    )
                gap_index += 1
                current_time_ms = gap.end_time_ms
                continue

            layer_index = atoms_completed // _PREFILL_ATOMS_PER_LAYER
            atom_index = atoms_completed % _PREFILL_ATOMS_PER_LAYER
            end_time_ms = current_time_ms + atom_duration_ms
            timeline_rows.append(
                _build_timeline_row(
                    identifiers=identifiers,
                    atom=_ScheduledAtomSpec(
                        phase=_PREFILL_PHASE,
                        mode=_PREFILL_MODE,
                        family=_PREFILL_GEMM_FAMILY,
                        chunk_index=chunk_index,
                        token_index=None,
                        layer_index=layer_index,
                        atom_index=atom_index,
                        duration_ms=atom_duration_ms,
                    ),
                    gap=gap,
                    start_time_ms=current_time_ms,
                    end_time_ms=end_time_ms,
                )
            )
            current_time_ms = end_time_ms
            atoms_completed += 1
            if atoms_completed < atoms_per_chunk:
                remaining_gap_ms = gap.end_time_ms - current_time_ms
                if atom_duration_ms > remaining_gap_ms + _TIME_EPSILON_MS:
                    if not _can_park_chunk(
                        weight_bytes=weight_bytes,
                        parked_activation_bytes=parked_activation_bytes,
                        vram_ceiling_bytes=vram_ceiling_bytes,
                    ):
                        return _ScheduleOutcome(
                            completion_time_ms=None,
                            failure_status=_PARKED_ACTIVATION_OOM_STATUS,
                            timeline_rows=tuple(timeline_rows),
                        )
                    gap_index += 1
                    current_time_ms = gap.end_time_ms

    return _ScheduleOutcome(
        completion_time_ms=current_time_ms,
        failure_status=None,
        timeline_rows=tuple(timeline_rows),
    )


def _schedule_atoms(
    *,
    idle_gaps: tuple[_IdleGap, ...],
    identifiers: dict[str, object],
    atoms: tuple[_ScheduledAtomSpec, ...],
    not_before_ms: float,
    failure_status: str,
) -> _ScheduleOutcome:
    timeline_rows: list[dict[str, object]] = []
    gap_index = 0
    current_time_ms = not_before_ms

    for atom in atoms:
        aligned_gap_index, aligned_time_ms = _align_to_idle_gap(
            idle_gaps,
            gap_index=gap_index,
            not_before_ms=current_time_ms,
        )
        while aligned_gap_index is not None and aligned_time_ms is not None:
            gap_index = aligned_gap_index
            current_time_ms = aligned_time_ms
            gap = idle_gaps[gap_index]
            if (
                atom.duration_ms
                <= (gap.end_time_ms - current_time_ms) + _TIME_EPSILON_MS
            ):
                end_time_ms = current_time_ms + atom.duration_ms
                timeline_rows.append(
                    _build_timeline_row(
                        identifiers=identifiers,
                        atom=atom,
                        gap=gap,
                        start_time_ms=current_time_ms,
                        end_time_ms=end_time_ms,
                    )
                )
                current_time_ms = end_time_ms
                break

            gap_index += 1
            current_time_ms = gap.end_time_ms
            aligned_gap_index, aligned_time_ms = _align_to_idle_gap(
                idle_gaps,
                gap_index=gap_index,
                not_before_ms=current_time_ms,
            )
        else:
            return _ScheduleOutcome(
                completion_time_ms=None,
                failure_status=failure_status,
                timeline_rows=tuple(timeline_rows),
            )

    return _ScheduleOutcome(
        completion_time_ms=current_time_ms,
        failure_status=None,
        timeline_rows=tuple(timeline_rows),
    )


def _build_decode_atom_specs(
    *,
    num_hidden_layers: int,
    sequence_length: int,
    chunk_tokens: int,
    decode_max_gemv_us: float,
    attention_fetch_compute_us: float,
    reduction_overhead_us: float,
    pcie_exposed_us: float,
    mode: str,
) -> tuple[_ScheduledAtomSpec, ...]:
    atoms: list[_ScheduledAtomSpec] = []
    decode_max_gemv_ms = _microseconds_to_milliseconds(decode_max_gemv_us)
    attention_fetch_compute_ms = _microseconds_to_milliseconds(
        attention_fetch_compute_us
    )
    reduction_overhead_ms = _microseconds_to_milliseconds(reduction_overhead_us)
    pcie_exposed_ms = _microseconds_to_milliseconds(pcie_exposed_us)
    transfer_atom_count = math.ceil(sequence_length / chunk_tokens)

    for layer_index in range(num_hidden_layers):
        for atom_index in range(_DECODE_GEMV_ATOMS_PER_LAYER):
            atoms.append(
                _ScheduledAtomSpec(
                    phase=_DECODE_PHASE,
                    mode=mode,
                    family=_DECODE_GEMV_FAMILY,
                    chunk_index=None,
                    token_index=0,
                    layer_index=layer_index,
                    atom_index=atom_index,
                    duration_ms=decode_max_gemv_ms,
                )
            )
        if mode == _PCIE_ASYNC_MODE:
            for atom_index in range(transfer_atom_count):
                atoms.append(
                    _ScheduledAtomSpec(
                        phase=_DECODE_PHASE,
                        mode=mode,
                        family=_PCIE_EXPOSED_TRANSFER_FAMILY,
                        chunk_index=None,
                        token_index=0,
                        layer_index=layer_index,
                        atom_index=atom_index,
                        duration_ms=pcie_exposed_ms,
                    )
                )
        atoms.append(
            _ScheduledAtomSpec(
                phase=_DECODE_PHASE,
                mode=mode,
                family=_ATTENTION_FETCH_COMPUTE_FAMILY,
                chunk_index=None,
                token_index=0,
                layer_index=layer_index,
                atom_index=0,
                duration_ms=attention_fetch_compute_ms,
            )
        )
        atoms.append(
            _ScheduledAtomSpec(
                phase=_DECODE_PHASE,
                mode=mode,
                family=_REDUCTION_OVERHEAD_FAMILY,
                chunk_index=None,
                token_index=0,
                layer_index=layer_index,
                atom_index=0,
                duration_ms=reduction_overhead_ms,
            )
        )
    return tuple(atoms)


def _extract_idle_gaps(
    trace_intervals: tuple[TraceInterval, ...],
) -> tuple[_IdleGap, ...]:
    return tuple(
        _IdleGap(
            trace_interval_index=index,
            start_time_ms=interval.start_time_ms,
            end_time_ms=interval.end_time_ms,
        )
        for index, interval in enumerate(trace_intervals)
        if interval.sm_utilization == 0
        and interval.end_time_ms > interval.start_time_ms
    )


def _align_to_idle_gap(
    idle_gaps: tuple[_IdleGap, ...],
    *,
    gap_index: int,
    not_before_ms: float,
) -> tuple[int | None, float | None]:
    search_index = max(0, gap_index)
    while search_index < len(idle_gaps):
        gap = idle_gaps[search_index]
        if gap.end_time_ms <= not_before_ms + _TIME_EPSILON_MS:
            search_index += 1
            continue
        return search_index, max(not_before_ms, gap.start_time_ms)
    return None, None


def _build_timeline_row(
    *,
    identifiers: dict[str, object],
    atom: _ScheduledAtomSpec,
    gap: _IdleGap,
    start_time_ms: float,
    end_time_ms: float,
) -> dict[str, object]:
    return {
        "model_id": identifiers["model_id"],
        "chunk_tokens": identifiers["chunk_tokens"],
        "sequence_length": identifiers["sequence_length"],
        "phase": atom.phase,
        "mode": atom.mode,
        "family": atom.family,
        "chunk_index": atom.chunk_index,
        "token_index": atom.token_index,
        "layer_index": atom.layer_index,
        "atom_index": atom.atom_index,
        "trace_interval_index": gap.trace_interval_index,
        "start_time_ms": start_time_ms,
        "end_time_ms": end_time_ms,
        "duration_ms": end_time_ms - start_time_ms,
    }


def _resolve_packed_num_hidden_layers(
    *,
    exemplar_result_row: Mapping[str, object],
    exemplar_timeline_rows: Sequence[Mapping[str, object]],
    num_hidden_layers: int | None,
) -> int:
    if num_hidden_layers is not None and num_hidden_layers > 0:
        return num_hidden_layers

    row_value = exemplar_result_row.get("num_hidden_layers")
    if not _is_missing_scalar(row_value):
        return _coerce_positive_int(row_value, name="num_hidden_layers")

    layer_indices = [
        _coerce_int(timeline_row.get("layer_index"))
        for timeline_row in exemplar_timeline_rows
        if not _is_missing_scalar(timeline_row.get("layer_index"))
    ]
    if layer_indices:
        return max(layer_indices) + 1

    raise ValueError(
        "Packed exemplar scheduling requires num_hidden_layers or timeline rows with layer_index"
    )


def _annotate_packed_timeline_rows(
    timeline_rows: Sequence[dict[str, object]],
    *,
    schedule_variant: str,
    task_id: int,
) -> list[dict[str, object]]:
    schedule_columns = (
        REVISED_SCHEDULE_TIMELINE_COLUMNS
        if _timeline_rows_use_revised_scheduler(timeline_rows)
        else SCHEDULE_TIMELINE_COLUMNS
    )
    return [
        {
            "schedule_variant": schedule_variant,
            "task_id": task_id,
            **{column: timeline_row.get(column) for column in schedule_columns},
        }
        for timeline_row in timeline_rows
    ]


def _timeline_rows_use_revised_scheduler(
    timeline_rows: Sequence[Mapping[str, object]],
) -> bool:
    return bool(timeline_rows) and (
        str(timeline_rows[0].get("schema_version", "")).strip()
        == experiments.RAN_DGXSPARK_V1_SCHEMA_VERSION
    )


def _uses_revised_scheduler(
    *,
    exemplar_result_row: Mapping[str, object],
    exemplar_timeline_rows: Sequence[Mapping[str, object]],
) -> bool:
    if (
        str(exemplar_result_row.get("schema_version", "")).strip()
        == experiments.RAN_DGXSPARK_V1_SCHEMA_VERSION
    ):
        return True
    if (
        str(exemplar_result_row.get("experiment_type", "")).strip()
        == experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE
    ):
        return True
    if (
        str(exemplar_result_row.get("scheduler", "")).strip()
        == experiments.RAN_DGXSPARK_V1_SCHEDULER
    ):
        return True
    return _timeline_rows_use_revised_scheduler(exemplar_timeline_rows)


def _extract_partition_metric_map(
    row: Mapping[str, object],
    *,
    metric: str,
    mode: str | None = None,
    value_kind: str = "float",
) -> dict[int, float | int]:
    mapping: dict[int, float | int] = {}
    for partition in _REVISED_SM_AI_PARTITIONS:
        column_name = (
            f"{metric}_{mode}_sm{partition}"
            if mode is not None
            else f"{metric}_sm{partition}"
        )
        if column_name not in row or _is_missing_scalar(row.get(column_name)):
            continue
        mapping[partition] = (
            _coerce_int(row.get(column_name))
            if value_kind == "int"
            else _coerce_float(row.get(column_name))
        )
    if set(mapping) != set(_REVISED_SM_AI_PARTITIONS):
        missing_partitions = [
            partition
            for partition in _REVISED_SM_AI_PARTITIONS
            if partition not in mapping
        ]
        mode_label = "" if mode is None else f" mode={mode}"
        raise ValueError(
            f"Revised scheduler is missing {metric}{mode_label} partition columns: {missing_partitions}"
        )
    return mapping


def _max_mapping_value(
    mapping: Mapping[int, float | int],
    *,
    default: float | int = 0.0,
) -> float | int:
    if not mapping:
        return default
    return max(mapping.values())


def _max_nested_mapping_value(
    mapping: Mapping[str, Mapping[int, float | int]],
    *,
    default: float | int = 0.0,
) -> float | int:
    values = [value for nested in mapping.values() for value in nested.values()]
    if not values:
        return default
    return max(values)


def _analytical_duration_scale(sm_ai_partition: int) -> float:
    partition = float(sm_ai_partition)
    if partition <= 0:
        return 1.0
    return _ANALYTICAL_FULL_GPU_SM_COUNT / partition


def _build_analytical_duration_map(
    duration_map: Mapping[int, float | int],
) -> dict[int, float]:
    positive_pairs = [
        (int(partition), float(duration))
        for partition, duration in duration_map.items()
        if float(duration) > 0
    ]
    if not positive_pairs:
        raise ValueError("Cannot derive analytical partition durations from empty map")
    baseline_partition, baseline_duration = max(
        positive_pairs, key=lambda pair: pair[0]
    )
    baseline_full_gpu_duration = baseline_duration * (
        float(baseline_partition) / _ANALYTICAL_FULL_GPU_SM_COUNT
    )
    return {
        partition: baseline_full_gpu_duration * _analytical_duration_scale(partition)
        for partition in _REVISED_SM_AI_PARTITIONS
    }


def _duration_for_partition(
    duration_map: Mapping[int, float],
    *,
    partition: int,
    label: str,
) -> float:
    duration_ms = duration_map.get(partition)
    if duration_ms is None or duration_ms <= 0:
        raise ValueError(
            f"Envelope scheduler is missing a positive duration for {label} at SM_AI={partition}"
        )
    return duration_ms


def _resolve_envelope_duration_map_from_timeline_rows(
    timeline_rows: Sequence[Mapping[str, object]],
    *,
    phase: str,
    mode: str,
    family: str,
) -> dict[int, float]:
    duration_map: dict[int, float] = {}
    for timeline_row in timeline_rows:
        if str(timeline_row.get("phase")) != phase:
            continue
        if str(timeline_row.get("mode")) != mode:
            continue
        if str(timeline_row.get("family")) != family:
            continue
        partition = _coerce_int(timeline_row.get("sm_ai_available"))
        duration_ms = _coerce_float(timeline_row.get("atom_duration_ms_at_sm_ai"))
        if partition <= 0 or duration_ms <= 0:
            continue
        existing_duration = duration_map.get(partition)
        if existing_duration is not None and not math.isclose(
            existing_duration,
            duration_ms,
            rel_tol=1e-9,
            abs_tol=1e-9,
        ):
            raise ValueError(
                "Envelope timeline contains inconsistent duration samples for "
                f"phase={phase}, mode={mode}, family={family}, SM_AI={partition}"
            )
        duration_map[partition] = duration_ms
    if not duration_map:
        raise ValueError(
            "Envelope packed exemplar scheduling could not recover any duration samples "
            f"for phase={phase}, mode={mode}, family={family}"
        )
    return duration_map


def _resolve_revised_duration_map(
    exemplar_result_row: Mapping[str, object],
    exemplar_timeline_rows: Sequence[Mapping[str, object]],
    *,
    metric: str,
    mode: str | None,
    phase: str,
    family: str,
) -> dict[int, float]:
    try:
        duration_map = _extract_partition_metric_map(
            exemplar_result_row,
            metric=metric,
            mode=mode,
        )
    except ValueError:
        duration_map = {}
    if duration_map:
        return {
            partition: _microseconds_to_milliseconds(float(duration_us))
            for partition, duration_us in duration_map.items()
        }
    return _resolve_envelope_duration_map_from_timeline_rows(
        exemplar_timeline_rows,
        phase=phase,
        mode=_PREFILL_MODE if mode is None else mode,
        family=family,
    )


def _resolve_experiment_type(
    *,
    run_root: Path,
    experiment_type: str | None,
) -> str:
    if experiment_type is not None:
        return experiments.normalize_experiment_type(experiment_type)
    manifest_path = run_root / "run_manifest.json"
    if not manifest_path.exists():
        return experiments.LEGACY_EXPERIMENT_TYPE
    try:
        manifest_df = pd.read_json(manifest_path, typ="series")
    except ValueError:
        return experiments.LEGACY_EXPERIMENT_TYPE
    manifest_experiment_type = cast(object, manifest_df.get("experiment_type"))
    return experiments.normalize_experiment_type(
        None
        if _is_missing_scalar(manifest_experiment_type)
        else str(manifest_experiment_type)
    )


def _quantize_sm_ran(sm_utilization: float) -> int:
    resolved_utilization = min(max(sm_utilization, 0.0), 100.0)
    estimated_sm_ran = (resolved_utilization / 100.0) * 48.0
    for tier in _REVISED_SM_RAN_QUANTIZATION_TIERS:
        if estimated_sm_ran <= tier + _TIME_EPSILON_MS:
            return tier
    return _REVISED_SM_RAN_QUANTIZATION_TIERS[-1]


def _resolve_weight_bytes(row: dict[str, object]) -> int:
    total_weight_bytes = row.get("total_weight_bytes_fp16")
    if not _is_missing_scalar(total_weight_bytes):
        return _coerce_int(row.get("total_weight_bytes_fp16"))
    layer_weight_bytes = row.get("layer_weight_bytes")
    num_hidden_layers = row.get("num_hidden_layers")
    if not _is_missing_scalar(layer_weight_bytes) and not _is_missing_scalar(
        num_hidden_layers
    ):
        return _coerce_int(layer_weight_bytes) * _coerce_int(num_hidden_layers)
    return 0


def _can_park_chunk(
    *,
    weight_bytes: int,
    parked_activation_bytes: int,
    vram_ceiling_bytes: int,
) -> bool:
    return weight_bytes + parked_activation_bytes <= vram_ceiling_bytes


def _compute_trace_sha256(trace_path: Path) -> str:
    digest = sha256()
    with trace_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _microseconds_to_milliseconds(duration_us: float) -> float:
    return duration_us / 1_000.0


def _require_completion_time_ms(outcome: _ScheduleOutcome) -> float:
    if outcome.completion_time_ms is None:
        raise AssertionError(
            "Successful schedule outcome must include completion_time_ms"
        )
    return outcome.completion_time_ms


def _coerce_results_dataframe_dtypes(results_df: pd.DataFrame) -> None:
    if results_df.empty:
        return
    integer_columns = (
        "chunk_tokens",
        "sequence_length",
        "weight_bytes",
        "vram_ceiling_bytes",
        "prefill_workspace_bytes",
        "prefill_parked_activation_bytes",
        "survival_vram_bytes",
        "decode_runway_bytes",
        "decode_runway_tokens",
    )
    for column in integer_columns:
        results_df[column] = results_df[column].astype("Int64")


def _coerce_revised_results_dataframe_dtypes(results_df: pd.DataFrame) -> None:
    if results_df.empty:
        return
    integer_columns = (
        "chunk_tokens",
        "sequence_length",
        "weight_bytes",
        "vram_ceiling_bytes",
        "prefill_workspace_bytes",
        "prefill_parked_activation_bytes",
        "survival_vram_bytes",
        "decode_runway_bytes",
        "decode_runway_tokens",
        "trace_interval_count",
        "trace_intervals_with_ai_budget",
        *tuple(
            column
            for column in (
                *_REVISED_PREFILL_WIDE_METRIC_COLUMNS,
                *_REVISED_DECODE_WIDE_METRIC_COLUMNS,
            )
            if column.endswith("_bytes")
        ),
    )
    boolean_columns = tuple(
        f"{prefix}_nvml_available" for prefix in _REVISED_RESULT_TELEMETRY_PREFIXES
    )
    for column in integer_columns:
        if column in results_df.columns:
            results_df[column] = results_df[column].astype("Int64")
    for column in boolean_columns:
        if column not in results_df.columns:
            continue
        results_df[column] = results_df[column].astype("boolean")


def _validate_revised_microscopic_telemetry(simulation_inputs: pd.DataFrame) -> None:
    if simulation_inputs.empty:
        return
    required_prefixes = ("prefill", "decode_vram", "decode_pcie_async")
    required_metrics = telemetry.MICROSCOPIC_COUNTER_COLUMNS
    required_columns = [
        f"{prefix}_{metric}"
        for prefix in required_prefixes
        for metric in required_metrics
    ]

    missing_columns = [
        column for column in required_columns if column not in simulation_inputs.columns
    ]
    if missing_columns:
        raise ValueError(
            "Microscopic telemetry missing: " + ", ".join(sorted(missing_columns))
        )

    missing_mask = simulation_inputs[required_columns].isna()
    row_missing_flags = [
        bool(value) for value in cast(pd.Series, missing_mask.any(axis=1)).tolist()
    ]
    if any(row_missing_flags):
        first_missing_index = row_missing_flags.index(True)
        missing_for_row = [
            column
            for column in required_columns
            if bool(missing_mask.iloc[first_missing_index][column])
        ]
        model_id = str(simulation_inputs.iloc[first_missing_index]["model_id"])
        chunk_tokens = int(simulation_inputs.iloc[first_missing_index]["chunk_tokens"])
        sequence_length = int(
            simulation_inputs.iloc[first_missing_index]["sequence_length"]
        )
        raise ValueError(
            "Microscopic telemetry missing"
            + f" for model_id={model_id}, chunk_tokens={chunk_tokens}, "
            + f"sequence_length={sequence_length}: "
            + ", ".join(missing_for_row)
        )


def _coerce_int(value: object) -> int:
    if _is_missing_scalar(value):
        return 0
    return int(cast(int | float | str | bool, value))


def _coerce_positive_int(value: object, *, name: str) -> int:
    resolved = _coerce_int(value)
    if resolved <= 0:
        raise ValueError(f"{name} must be > 0")
    return resolved


def _coerce_float(value: object) -> float:
    if _is_missing_scalar(value):
        return 0.0
    return float(cast(int | float | str | bool, value))


def _is_missing_scalar(value: object) -> bool:
    if value is None:
        return True
    return bool(pd.isna(value))


def _load_csv_or_empty(csv_path: Path) -> pd.DataFrame:
    """Load CSV if it exists, otherwise return empty DataFrame."""
    if not csv_path.exists():
        return pd.DataFrame()
    return pd.read_csv(csv_path)


def _load_required_csv(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise ValueError(f"Required simulation input source is missing: {csv_path}")
    return pd.read_csv(csv_path)


def _select_columns(
    df: pd.DataFrame,
    *,
    csv_path: Path,
    required_columns: tuple[str, ...],
) -> pd.DataFrame:
    missing_columns = [
        column for column in required_columns if column not in df.columns
    ]
    if missing_columns:
        raise ValueError(
            f"{csv_path} is missing required column(s): {', '.join(missing_columns)}"
        )
    return df.loc[:, list(required_columns)].copy()


def _require_columns_present(
    df: pd.DataFrame,
    *,
    csv_path: Path,
    required_columns: tuple[str, ...],
) -> None:
    missing_columns = [
        column for column in required_columns if column not in df.columns
    ]
    if missing_columns:
        raise ValueError(
            f"{csv_path} is missing required column(s): {', '.join(missing_columns)}"
        )


def _group_rows_by_partition(
    df: pd.DataFrame,
    *,
    group_label: str,
    duration_metrics: Sequence[str] = (),
) -> dict[int, dict[str, object]]:
    rows_by_partition: dict[int, dict[str, object]] = {}
    for row in df.to_dict(orient="records"):
        partition = _coerce_positive_int(
            row.get("sm_ai_partition"), name="sm_ai_partition"
        )
        if partition in rows_by_partition:
            raise ValueError(
                f"Revised simulation input contains duplicate rows for {group_label} at SM_AI={partition}"
            )
        rows_by_partition[partition] = row

    if not rows_by_partition:
        raise ValueError(f"Revised simulation input has no rows for {group_label}")

    missing_partitions = [
        partition
        for partition in _REVISED_SM_AI_PARTITIONS
        if partition not in rows_by_partition
    ]

    if missing_partitions and duration_metrics:
        baseline_partition = max(rows_by_partition)
        baseline_row = rows_by_partition[baseline_partition]
        for partition in missing_partitions:
            synthesized_row = dict(baseline_row)
            synthesized_row["sm_ai_partition"] = partition
            for metric in duration_metrics:
                if metric not in baseline_row:
                    raise ValueError(
                        f"Revised simulation input cannot synthesize metric {metric!r} for {group_label}"
                    )
                baseline_duration = _coerce_float(baseline_row.get(metric))
                full_gpu_duration = baseline_duration * (
                    float(baseline_partition) / _ANALYTICAL_FULL_GPU_SM_COUNT
                )
                synthesized_row[metric] = (
                    full_gpu_duration * _analytical_duration_scale(partition)
                )
            rows_by_partition[partition] = synthesized_row

        missing_partitions = [
            partition
            for partition in _REVISED_SM_AI_PARTITIONS
            if partition not in rows_by_partition
        ]

    if missing_partitions:
        raise ValueError(
            f"Revised simulation input is missing partition(s) {missing_partitions} for {group_label}"
        )
    return rows_by_partition


def _extend_revised_telemetry_columns(
    row: dict[str, object],
    *,
    prefix: str,
    source_df: pd.DataFrame,
) -> None:
    fallback_estimate = _estimate_microscopic_from_summary(
        source_df=source_df,
        prefix=prefix,
    )
    fallback_counters = {
        "acu_pct": fallback_estimate.acu_pct,
        "gbu_pct": fallback_estimate.gbu_pct,
        "smu_pct": fallback_estimate.smu_pct,
    }
    used_microscopic_fallback = False
    for column in _REVISED_TELEMETRY_SUMMARY_COLUMNS:
        target_column = f"{prefix}_{column}"
        if column in fallback_counters:
            fallback_value = fallback_counters[column]
            if fallback_value is not None:
                row[target_column] = fallback_value
                used_microscopic_fallback = True
                continue
        if column not in source_df.columns:
            if column in fallback_counters and fallback_counters[column] is not None:
                row[target_column] = fallback_counters[column]
                used_microscopic_fallback = True
            else:
                row[target_column] = None
            continue
        series = cast(pd.Series, source_df[column])
        if column in {
            "telemetry_tier",
            "telemetry_provider",
            "telemetry_status",
            "microscopic_telemetry_status",
            "microscopic_error",
        }:
            value = _series_first_nonmissing(series)
            if (
                column == "microscopic_telemetry_status"
                and (value is None or str(value).strip().lower() == "unavailable")
                and any(counter is not None for counter in fallback_counters.values())
            ):
                value = fallback_estimate.microscopic_telemetry_status
                used_microscopic_fallback = True
            row[target_column] = value
            continue
        if column == "nvml_available":
            value = _series_first_nonmissing(series)
            row[target_column] = _coerce_bool_or_none(value)
            continue
        value = _series_mean_as_float_or_none(series)
        if column in fallback_counters and value is None:
            fallback_value = fallback_counters[column]
            if fallback_value is not None:
                value = fallback_value
                used_microscopic_fallback = True
        row[target_column] = value

    if used_microscopic_fallback:
        status_column = f"{prefix}_microscopic_telemetry_status"
        row[status_column] = fallback_estimate.microscopic_telemetry_status


def _estimate_microscopic_from_summary(
    *,
    source_df: pd.DataFrame,
    prefix: str,
):
    family, decode_mode = _family_and_mode_for_prefix(prefix)
    model_id: str | None = None
    if "model_id" in source_df.columns:
        model_value = _series_first_nonmissing(cast(pd.Series, source_df["model_id"]))
        if model_value is not None:
            model_id = str(model_value)
    gpu_util: float | None = None
    if "gpu_util" in source_df.columns:
        gpu_util = _series_mean_as_float_or_none(cast(pd.Series, source_df["gpu_util"]))

    sm_ai_partition: int | None = None
    if "sm_ai_partition" in source_df.columns:
        partition_mean = _series_mean_as_float_or_none(
            cast(pd.Series, source_df["sm_ai_partition"])
        )
        if partition_mean is not None:
            sm_ai_partition = int(round(partition_mean))

    chunk_tokens: int | None = None
    if "chunk_tokens" in source_df.columns:
        chunk_mean = _series_mean_as_float_or_none(
            cast(pd.Series, source_df["chunk_tokens"])
        )
        if chunk_mean is not None:
            chunk_tokens = int(round(chunk_mean))

    sequence_length: int | None = None
    if "sequence_length" in source_df.columns:
        sequence_mean = _series_mean_as_float_or_none(
            cast(pd.Series, source_df["sequence_length"])
        )
        if sequence_mean is not None:
            sequence_length = int(round(sequence_mean))

    block_size: int | None = None
    if "block_size" in source_df.columns:
        block_mean = _series_mean_as_float_or_none(
            cast(pd.Series, source_df["block_size"])
        )
        if block_mean is not None:
            block_size = int(round(block_mean))

    return telemetry.estimate_microscopic_counters(
        gpu_util=gpu_util,
        sm_ai_partition=sm_ai_partition,
        family=family,
        decode_mode=decode_mode,
        model_id=model_id,
        chunk_tokens=chunk_tokens,
        sequence_length=sequence_length,
        block_size=block_size,
    )


def _family_and_mode_for_prefix(prefix: str) -> tuple[str, str | None]:
    if prefix == "prefill":
        return "prefill", None
    if prefix == "decode_vram":
        return "decode", "vram"
    if prefix == "decode_pcie_async":
        return "decode", "pcie_async"
    if prefix == "pcie":
        return "pcie", None
    return "decode", None


def _coerce_bool_or_none(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if value == 1:
            return True
        if value == 0:
            return False
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    return None


def _series_first_nonmissing(series: pd.Series) -> object:
    for value in series:
        if _is_missing_scalar(value):
            continue
        return value
    return None


def _series_mean_as_float_or_none(series: pd.Series) -> float | None:
    if series.empty:
        return None
    mean_value = series.mean()
    if pd.isna(mean_value):
        return None
    return float(mean_value)


def _prepare_model_constants_frame(
    df: pd.DataFrame,
    *,
    csv_path: Path,
) -> pd.DataFrame:
    _select_columns(
        df,
        csv_path=csv_path,
        required_columns=_MODEL_CONSTANTS_REQUIRED_COLUMNS,
    )
    if not df.empty and bool(df["model_id"].duplicated().any()):
        raise ValueError(f"{csv_path} must contain at most one row per model_id")

    selected_columns = [
        column for column in _MODEL_CONSTANTS_OPTIONAL_COLUMNS if column in df.columns
    ]
    model_constants = df.loc[
        :,
        [
            *_MODEL_CONSTANTS_REQUIRED_COLUMNS,
            *selected_columns,
        ],
    ].copy()

    if "total_memory_bytes" not in model_constants.columns:
        model_constants["total_memory_bytes"] = model_constants[
            "vram_ceiling_bytes"
        ].map(_derive_total_memory_bytes_from_vram_ceiling)
    else:
        total_memory_series = model_constants["total_memory_bytes"]
        model_constants["total_memory_bytes"] = total_memory_series.where(
            total_memory_series.notna(),
            model_constants["vram_ceiling_bytes"].map(
                _derive_total_memory_bytes_from_vram_ceiling
            ),
        )

    model_constants["kv_bytes_per_token_all_layers"] = (
        model_constants["hidden_size"].astype(int)
        * model_constants["num_hidden_layers"].astype(int)
        * _KV_BYTES_PER_HIDDEN_VALUE
    )
    model_constants["total_memory_bytes"] = (
        model_constants["total_memory_bytes"].fillna(0).astype(int)
    )
    model_constants["vram_ceiling_bytes"] = (
        model_constants["vram_ceiling_bytes"].fillna(0).astype(int)
    )
    return model_constants


def _derive_total_memory_bytes_from_vram_ceiling(vram_ceiling_bytes: Any) -> int:
    resolved_vram_ceiling_bytes = int(vram_ceiling_bytes)
    if resolved_vram_ceiling_bytes <= 0:
        return 0
    return (
        (resolved_vram_ceiling_bytes * _VRAM_CEILING_DENOMINATOR)
        + (_VRAM_CEILING_NUMERATOR - 1)
    ) // _VRAM_CEILING_NUMERATOR


__all__ = [
    "SIMULATION_INPUTS_FILENAME",
    "SIMULATION_RESULTS_FILENAME",
    "SCHEDULE_TIMELINE_FILENAME",
    "PACKED_EXEMPLAR_TIMELINE_FILENAME",
    "REVISED_SIMULATION_INPUT_COLUMNS",
    "SIMULATION_RESULTS_COLUMNS",
    "REVISED_SIMULATION_RESULTS_COLUMNS",
    "SCHEDULE_TIMELINE_COLUMNS",
    "REVISED_SCHEDULE_TIMELINE_COLUMNS",
    "PACKED_EXEMPLAR_TIMELINE_COLUMNS",
    "REVISED_PACKED_EXEMPLAR_TIMELINE_COLUMNS",
    "SimulationResult",
    "TraceInterval",
    "EnvelopeInterval",
    "assemble_simulation_inputs",
    "build_packed_exemplar_timeline_rows",
    "load_normalized_trace_intervals",
    "run_deterministic_simulation",
    "write_packed_exemplar_timeline",
]
