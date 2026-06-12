from __future__ import annotations

# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportCallIssue=false, reportPrivateImportUsage=false, reportReturnType=false

import json
import importlib
import math
import re
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.ticker import MultipleLocator
import numpy as np
import pandas as pd

from inference_profile import simulator, trace_contract, manifests, experiments

try:
    go = importlib.import_module("plotly.graph_objects")
    plotly_subplots = importlib.import_module("plotly.subplots")
except ModuleNotFoundError:
    go = None
    plotly_subplots = None

plt.switch_backend("Agg")

PLOT_FILENAMES = (
    "01_ran_trace_interleaving.png",
    "02_prefill_safety_boundary.png",
    "03_prefill_vram_composition.png",
    "04_ttft_vs_runway.png",
    "05_decode_tpot_degradation.png",
    "06_operation_level_microarchitecture_summary.png",
)
PLOT_SELECTION_FILENAME = "plot_selection.json"
INTERACTIVE_RAN_TRACE_FILENAME = "01_ran_trace_interleaving_interactive.html"

_RESULTS_REQUIRED_COLUMNS = (
    "model_id",
    "chunk_tokens",
    "sequence_length",
    "weight_bytes",
    "vram_ceiling_bytes",
    "prefill_max_gemm_us",
    "prefill_workspace_bytes",
    "prefill_parked_activation_bytes",
    "decode_runway_bytes",
    "decode_runway_tokens",
    "ttft_ms",
    "tpot_ms_vram",
    "tpot_ms_pcie_async",
    "status",
)
_PREFILL_EVENTS_REQUIRED_COLUMNS = (
    "model_id",
    "chunk_tokens",
    "op_name",
    "duration_us",
    "dynamic_workspace_bytes",
)
_DECODE_EVENTS_REQUIRED_COLUMNS = (
    "model_id",
    "sequence_length",
    "block_size",
    "op_type",
    "duration_us",
    "dynamic_workspace_bytes",
)
_MODEL_CONSTANTS_REQUIRED_COLUMNS = ("model_id",)
_MODEL_CONSTANTS_KV_FALLBACK_COLUMNS = (
    "hidden_size",
    "num_hidden_layers",
)
_TIMELINE_REQUIRED_COLUMNS = simulator.SCHEDULE_TIMELINE_COLUMNS
_PACKED_TIMELINE_REQUIRED_COLUMNS = simulator.PACKED_EXEMPLAR_TIMELINE_COLUMNS
_TRACE_REQUIRED_COLUMNS = trace_contract.NORMALIZED_TRACE_HEADERS
_SUCCESS_STATUS = "success"
_TIME_EPSILON_MS = 1e-9
_BYTES_PER_GIB = float(1024**3)
_US_PER_MS = 1_000.0
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_PNG_SAVE_METADATA = {"Software": "inference_profile.plots"}

_FIXED_MODEL_ORDER = (
    "facebook/opt-125m",
    "facebook/opt-350m",
    "facebook/opt-1.3b",
    "facebook/opt-2.7b",
    "facebook/opt-6.7b",
)
_MODEL_LABELS = {
    "facebook/opt-125m": "OPT-125M",
    "facebook/opt-350m": "OPT-350M",
    "facebook/opt-1.3b": "OPT-1.3B",
    "facebook/opt-2.7b": "OPT-2.7B",
    "facebook/opt-6.7b": "OPT-6.7B",
}
_MODEL_COLORS = {
    "facebook/opt-125m": "#0367A1",
    "facebook/opt-350m": "#EEBA0C",
    "facebook/opt-1.3b": "#009E73",
    "facebook/opt-2.7b": "#CC79A7",
    "facebook/opt-6.7b": "#B35106",
}
_TRACE_COLOR = "#2F4858"
_TTFT_COLOR = "#C43C5B"
_IDLE_REFERENCE_COLOR = "#222222"
_INTERVAL_COLORS = {
    "Prefill": "#0367A1",
    "Decode (VRAM)": "#EEBA0C",
    "Decode (PCIe async)": "#009E73",
}
_STACK_COLORS = {
    "Weights": "#2F4858",
    "Bulk KV cache": "#7A4CC2",
    "Prefill workspace": "#56B4E9",
    "Prefill parked activation": "#F0E442",
    "60% VRAM limit": "#C43C5B",
}
_TPOT_LINE_COLORS = {
    "DGX VRAM fetch": "#0367A1",
    "PCIe async fetch": "#009E73",
}
_SM_AI_PARTITION_COLORS = [
    "#0367A1",
    "#EEBA0C",
    "#009E73",
    "#CC79A7",
    "#B35106",
    "#7A4CC2",
]
_ANALYTICAL_FULL_GPU_SM_COUNT = 48.0
_MICROARCH_OPERATION_ORDER = (
    "QKV",
    "O_proj",
    "MLP_up",
    "MLP_down",
    "Attention",
)
_MODEL_SIZE_RE = re.compile(
    r"opt-(?P<value>\d+(?:\.\d+)?)(?P<unit>[mb])$", re.IGNORECASE
)


class PlotGenerationError(ValueError):
    pass


def generate_profiling_plots(
    *,
    run_root: str | Path,
) -> dict[str, Path]:
    run_root = Path(run_root)
    derived_root = run_root / "derived"
    plots_root = run_root / "plots"
    plots_root.mkdir(parents=True, exist_ok=True)

    # detect experiment schema version; when the run manifest indicates
    # the revised ran-dgxspark-v1 experiment, emit versioned plot filenames
    # rather than silently overloading legacy names. This keeps legacy
    # bundles stable while making revised artifacts explicit.
    schema_version = None
    is_revised = False
    try:
        from inference_profile import manifests, experiments

        manifest = manifests.load_run_manifest(run_root / "run_manifest.json")
        schema_version = manifest.get("schema_version")
        is_revised = schema_version == getattr(
            experiments, "RAN_DGXSPARK_V1_SCHEMA_VERSION", None
        ) or manifest.get("experiment_type") == getattr(
            experiments, "RAN_DGXSPARK_V1_EXPERIMENT_TYPE", None
        )
    except Exception:
        # on failure to load manifest or experiments metadata, default to
        # legacy behaviour (not revised)
        schema_version = None
        is_revised = False
    if is_revised:
        # versioned filenames for revised experiment
        PLOT_FILENAMES_LOCAL = tuple(f"revised_{name}" for name in PLOT_FILENAMES) + (
            "revised_07_hardware_utilization_profiling.png",
            "revised_08_decode_memory_consumption.png",
            "revised_09_prefill_vram_composition_pie.png",
            "revised_10_hardware_utilization_heatmap_acu.png",
            "revised_11_hardware_utilization_heatmap_gbu.png",
            "revised_12_hardware_utilization_heatmap_smu.png",
            "revised_13_hardware_utilization_heatmap_gpu_util.png",
            "revised_14_ttft_vs_runway_no_schedule.png",
            "revised_15_decode_tpot_degradation_no_schedule.png",
        )
        PLOT_SELECTION_FILENAME_LOCAL = f"revised_{PLOT_SELECTION_FILENAME}"
        INTERACTIVE_RAN_TRACE_FILENAME_LOCAL = (
            f"revised_{INTERACTIVE_RAN_TRACE_FILENAME}"
        )
    else:
        PLOT_FILENAMES_LOCAL = PLOT_FILENAMES
        PLOT_SELECTION_FILENAME_LOCAL = PLOT_SELECTION_FILENAME
        INTERACTIVE_RAN_TRACE_FILENAME_LOCAL = INTERACTIVE_RAN_TRACE_FILENAME

    results_df = _load_required_csv(
        derived_root / simulator.SIMULATION_RESULTS_FILENAME,
        required_columns=_RESULTS_REQUIRED_COLUMNS,
    )
    prefill_events_df = _load_required_csv(
        run_root / "raw" / "prefill_events.csv",
        required_columns=_PREFILL_EVENTS_REQUIRED_COLUMNS,
    )
    decode_events_df = _load_required_csv(
        run_root / "raw" / "decode_events.csv",
        required_columns=_DECODE_EVENTS_REQUIRED_COLUMNS,
    )
    model_constants_df = _load_required_csv(
        derived_root / "model_constants.csv",
        required_columns=_MODEL_CONSTANTS_REQUIRED_COLUMNS,
    )
    timeline_df = _load_required_csv(
        derived_root / simulator.SCHEDULE_TIMELINE_FILENAME,
        required_columns=_TIMELINE_REQUIRED_COLUMNS,
    )
    trace_df = _load_required_csv(
        derived_root / trace_contract.NORMALIZED_TRACE_FILENAME,
        required_columns=_TRACE_REQUIRED_COLUMNS,
    )

    if results_df.empty:
        raise PlotGenerationError(
            f"Results CSV must contain at least one row: {derived_root / simulator.SIMULATION_RESULTS_FILENAME}"
        )

    results_df = _normalize_results_frame(results_df)
    prefill_events_df = _normalize_prefill_events_frame(prefill_events_df)
    decode_events_df = _normalize_decode_events_frame(decode_events_df)
    model_constants_df = _normalize_model_constants_frame(model_constants_df)
    timeline_df = _normalize_timeline_frame(timeline_df)
    trace_df = _normalize_trace_frame(trace_df)
    if trace_df.empty:
        raise PlotGenerationError(
            "Normalized trace CSV must contain at least one row for plot generation"
        )

    success_rows = _select_success_rows(results_df)
    exemplar_row = _select_exemplar_row(success_rows)
    plot5_chunk_selection = _select_plot5_chunk_tokens(success_rows)
    exemplar_timeline = _filter_result_rows(
        timeline_df,
        model_id=str(exemplar_row["model_id"]),
        chunk_tokens=int(exemplar_row["chunk_tokens"]),
        sequence_length=int(exemplar_row["sequence_length"]),
    )
    if exemplar_timeline.empty:
        raise PlotGenerationError(
            "schedule_timeline.csv does not contain rows for the deterministic exemplar configuration"
        )
    packed_timeline_path = simulator.write_packed_exemplar_timeline(
        run_root=run_root,
        exemplar_result_row=exemplar_row.to_dict(),
        exemplar_timeline_rows=tuple(exemplar_timeline.to_dict(orient="records")),
        num_hidden_layers=_resolve_exemplar_num_hidden_layers(
            model_constants_df=model_constants_df,
            model_id=str(exemplar_row["model_id"]),
        ),
    )
    packed_timeline_df = _normalize_packed_timeline_frame(
        _load_required_csv(
            packed_timeline_path,
            required_columns=_PACKED_TIMELINE_REQUIRED_COLUMNS,
        )
    )
    selection_payload = _build_plot_selection_payload(
        exemplar_row=exemplar_row,
        plot5_chunk_selection=plot5_chunk_selection,
    )
    _write_plot_selection_metadata(
        derived_root / PLOT_SELECTION_FILENAME_LOCAL,
        payload=selection_payload,
    )

    _remove_noncanonical_pngs(plots_root)

    plot_paths: dict[str, Path] = {}
    plot_builders = tuple(
        (PLOT_FILENAMES_LOCAL[i], builder)
        for i, builder in enumerate(
            (
                _plot_ran_trace_interleaving,
                _plot_prefill_safety_boundary,
                _plot_prefill_vram_composition,
                _plot_ttft_vs_runway,
                _plot_decode_tpot_degradation,
                _plot_operation_level_microarchitecture_summary,
            )
        )
    )
    # add revised-only hardware utilization plot builder when revised
    if is_revised:
        plot_builders = tuple(plot_builders) + (
            (
                "revised_07_hardware_utilization_profiling.png",
                _plot_hardware_utilization_profiling,
            ),
        )
    # revised-only: decode memory consumption scaling vs sequence length
    if is_revised:
        plot_builders = tuple(plot_builders) + (
            (
                "revised_08_decode_memory_consumption.png",
                _plot_decode_memory_consumption,
            ),
        )
    if is_revised:
        plot_builders = tuple(plot_builders) + (
            (
                "revised_09_prefill_vram_composition_pie.png",
                _plot_prefill_vram_composition_pie,
            ),
            (
                "revised_10_hardware_utilization_heatmap_acu.png",
                _plot_hardware_utilization_heatmap_acu,
            ),
            (
                "revised_11_hardware_utilization_heatmap_gbu.png",
                _plot_hardware_utilization_heatmap_gbu,
            ),
            (
                "revised_12_hardware_utilization_heatmap_smu.png",
                _plot_hardware_utilization_heatmap_smu,
            ),
            (
                "revised_13_hardware_utilization_heatmap_gpu_util.png",
                _plot_hardware_utilization_heatmap_gpu_util,
            ),
            (
                "revised_14_ttft_vs_runway_no_schedule.png",
                _plot_ttft_vs_runway_no_schedule,
            ),
            (
                "revised_15_decode_tpot_degradation_no_schedule.png",
                _plot_decode_tpot_degradation_no_schedule,
            ),
        )
    for filename, builder in plot_builders:
        plot_path = plots_root / filename
        builder(
            results_df=results_df,
            prefill_events_df=prefill_events_df,
            decode_events_df=decode_events_df,
            model_constants_df=model_constants_df,
            success_rows=success_rows,
            trace_df=trace_df,
            timeline_df=timeline_df,
            packed_timeline_df=packed_timeline_df,
            exemplar_row=exemplar_row,
            plot5_chunk_selection=plot5_chunk_selection,
            plot_path=plot_path,
        )
        plot_paths[plot_path.stem] = plot_path

    return plot_paths


@contextmanager
def _apply_plot_style(
    *, width: float, height: float, font_size: float = 9.0
) -> Iterator[None]:
    rc_params = {
        "figure.figsize": (width, height),
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "font.size": font_size,
        "font.family": ["DejaVu Sans", "Liberation Sans", "sans-serif"],
        "axes.titlesize": font_size + 1,
        "axes.titleweight": "bold",
        "axes.labelsize": font_size,
        "axes.grid": True,
        "grid.alpha": 0.32,
        "grid.linestyle": ":",
        "grid.linewidth": 0.7,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "lines.linewidth": 2.0,
        "lines.markersize": 5.5,
        "legend.frameon": False,
        "legend.fontsize": font_size - 1,
        "xtick.labelsize": font_size - 1,
        "ytick.labelsize": font_size - 1,
    }
    with plt.rc_context(rc_params):
        yield


def _plot_ran_trace_interleaving(
    *,
    results_df: pd.DataFrame,
    prefill_events_df: pd.DataFrame,
    decode_events_df: pd.DataFrame,
    model_constants_df: pd.DataFrame,
    success_rows: pd.DataFrame,
    trace_df: pd.DataFrame,
    timeline_df: pd.DataFrame,
    packed_timeline_df: pd.DataFrame,
    exemplar_row: pd.Series,
    plot5_chunk_selection: dict[str, int | None],
    plot_path: Path,
) -> None:
    del (
        results_df,
        prefill_events_df,
        decode_events_df,
        model_constants_df,
        success_rows,
        plot5_chunk_selection,
    )

    exemplar_timeline = _filter_result_rows(
        timeline_df,
        model_id=str(exemplar_row["model_id"]),
        chunk_tokens=int(exemplar_row["chunk_tokens"]),
        sequence_length=int(exemplar_row["sequence_length"]),
    )
    if exemplar_timeline.empty:
        raise PlotGenerationError(
            "schedule_timeline.csv does not contain rows for the deterministic exemplar configuration"
        )

    with _apply_plot_style(width=11.0, height=4.6):
        # two stacked axes: top = SM count trace, bottom = timeline lanes
        fig, (ax_top, ax_bottom) = plt.subplots(
            nrows=2, ncols=1, sharex=True, gridspec_kw={"height_ratios": [3, 1]}
        )

        trace_x, trace_y, y_label_is_count = _build_trace_step_series(trace_df)

        # choose a tightened window around exemplar prefill completion as before
        try:
            prefill_completion_trace_ms = float(
                exemplar_timeline[exemplar_timeline["phase"] == "prefill"][
                    "end_time_ms"
                ].max()
            )
        except Exception:
            prefill_completion_trace_ms = float(exemplar_row["ttft_ms"])

        trace_min = float(trace_df["time_ms"].min())
        trace_max = float(trace_df["end_time_ms"].max())
        median_slot = float(trace_df["slot_duration_ms"].median())
        window_ms = max(200.0, median_slot * 50.0)
        left = max(trace_min, prefill_completion_trace_ms - window_ms / 2.0)
        right = min(trace_max, prefill_completion_trace_ms + window_ms / 2.0)

        # make x values relative to left so axis shows a local window without large offsets
        rel_trace_x = [x - left for x in trace_x]

        trace_label = (
            "RAN trace (SM count)" if y_label_is_count else "Normalized RAN trace"
        )
        ax_top.step(
            rel_trace_x,
            trace_y,
            where="post",
            color=_TRACE_COLOR,
            label=trace_label,
            zorder=3,
        )

        # prepare interval lanes for bottom axis using broken_barh
        merged = _merged_timeline_intervals(exemplar_timeline)
        # map labels to vertical lanes
        lanes: dict[int, list[tuple[float, float]]] = {}
        for label, start_ms, end_ms in merged:
            # each interval as (start_rel, duration)
            start_rel = max(start_ms, left) - left
            duration = max(0.0, min(end_ms, right) - max(start_ms, left))
            if duration <= 0:
                continue
            lanes.setdefault(label, []).append((start_rel, duration))

        # draw lanes stacked vertically with small height
        lane_height = 0.8
        y_positions: dict[str, float] = {}
        for i, label in enumerate(sorted(lanes.keys())):
            y_positions[label] = i * (lane_height + 0.2)
            rects = lanes[label]
            ax_bottom.broken_barh(
                rects,
                (y_positions[label], lane_height),
                facecolor=_INTERVAL_COLORS.get(label, "#9AA5B1"),
                alpha=0.6,
            )
            # add small text label on the left of the lane
            if rects:
                ax_bottom.text(
                    -0.01 * (right - left),
                    y_positions[label] + lane_height / 2.0,
                    label,
                    va="center",
                    ha="right",
                    fontsize=8,
                )

        # The exported `ttft_ms` is a latency (ms). The vertical marker on
        # the trace timeline must be placed at the exemplar prefill completion
        # absolute trace timestamp. Lookup the prefill end time from the
        # exemplar timeline and use that as the x-position; label with the
        # latency value from results.
        ttft_ms = float(exemplar_row["ttft_ms"])
        rel_ttft = prefill_completion_trace_ms - left
        ax_top.axvline(
            rel_ttft,
            color=_TTFT_COLOR,
            linestyle="--",
            linewidth=1.8,
            label=f"TTFT = {ttft_ms:.2f} ms",
            zorder=4,
        )

        # center the x-axis on the exemplar prefill completion and show a
        # tightened, relative window so interleaving is legible
        # set x-limits to relative window
        ax_top.set_xlim(0.0, right - left)
        ax_bottom.set_xlim(0.0, right - left)
        if y_label_is_count:
            ymin = 0
            ymax = max(1.0, float(pd.to_numeric(trace_df["sm_count"]).max()))
            ax_top.set_ylim(ymin - 0.5, ymax + 0.5)
            ax_top.set_ylabel("Active SMs")
        else:
            ax_top.set_ylim(-0.05, 1.05)
            ax_top.set_yticks([0.0, 1.0], ["Idle", "Busy"])
            ax_top.set_ylabel("Normalized RAN state")
        ax_bottom.set_ylim(-0.1, max(1.0, len(lanes) * (lane_height + 0.2)))
        ax_bottom.set_yticks([])
        ax_bottom.set_xlabel("Relative trace time (ms)")
        fig.suptitle(
            "RAN trace interleaving exemplar · "
            f"{_short_model_label(str(exemplar_row['model_id']))} · "
            f"N={int(exemplar_row['chunk_tokens'])} · "
            f"L={int(exemplar_row['sequence_length'])}",
            y=0.98,
        )
        # legend from top axis only
        handles, labels = ax_top.get_legend_handles_labels()
        deduped_handles: list[Any] = []
        deduped_labels: list[str] = []
        seen_labels: set[str] = set()
        for handle, label in zip(handles, labels):
            if label in seen_labels:
                continue
            seen_labels.add(label)
            deduped_handles.append(handle)
            deduped_labels.append(label)
        if deduped_handles:
            ax_top.legend(deduped_handles, deduped_labels, ncol=2, loc="upper right")
        fig.tight_layout()
        _save_figure(fig, plot_path)
        interactive_name = (
            f"revised_{INTERACTIVE_RAN_TRACE_FILENAME}"
            if plot_path.name.startswith("revised_")
            else INTERACTIVE_RAN_TRACE_FILENAME
        )
        interactive_path = plot_path.parent / interactive_name
        _emit_interactive_ran_trace(
            trace_df=trace_df,
            exemplar_timeline=exemplar_timeline,
            packed_timeline=packed_timeline_df,
            exemplar_row=exemplar_row,
            left=left,
            right=right,
            prefill_completion_trace_ms=prefill_completion_trace_ms,
            interactive_path=interactive_path,
        )


def _plot_prefill_safety_boundary(
    *,
    results_df: pd.DataFrame,
    prefill_events_df: pd.DataFrame,
    decode_events_df: pd.DataFrame,
    model_constants_df: pd.DataFrame,
    success_rows: pd.DataFrame,
    trace_df: pd.DataFrame,
    timeline_df: pd.DataFrame,
    packed_timeline_df: pd.DataFrame,
    exemplar_row: pd.Series,
    plot5_chunk_selection: dict[str, int | None],
    plot_path: Path,
) -> None:
    del (
        decode_events_df,
        model_constants_df,
        success_rows,
        trace_df,
        timeline_df,
        packed_timeline_df,
        exemplar_row,
        plot5_chunk_selection,
    )

    prefill_df = _build_prefill_safety_boundary_frame(results_df)
    if prefill_df.empty:
        raise PlotGenerationError(
            "Prefill safety boundary plot requires at least one prefill point"
        )

    models = _ordered_models(prefill_df["model_id"])
    partitions = (
        prefill_df["sm_ai_partition"]
        .dropna()
        .astype(int)
        .sort_values()
        .unique()
        .tolist()
    )
    color_map = {
        partition: _SM_AI_PARTITION_COLORS[index % len(_SM_AI_PARTITION_COLORS)]
        for index, partition in enumerate(partitions)
    }

    with _apply_plot_style(width=max(8.8, 3.8 * len(models)), height=4.6):
        fig, axes = plt.subplots(1, len(models), sharey=True)
        axes_list = axes.ravel().tolist() if hasattr(axes, "ravel") else [axes]

        for axis, model_id in zip(axes_list, models):
            model_rows = prefill_df[prefill_df["model_id"] == model_id].copy()
            for partition in partitions:
                partition_rows = model_rows[
                    model_rows["sm_ai_partition"] == partition
                ].sort_values("chunk_tokens")
                if partition_rows.empty:
                    continue
                axis.plot(
                    partition_rows["chunk_tokens"],
                    partition_rows["prefill_max_gemm_us"],
                    marker="o",
                    linestyle="-",
                    color=color_map[partition],
                    label=f"SMs={partition}",
                )
            axis.set_title(_short_model_label(model_id))
            axis.set_xlabel("Chunk size (tokens)")
            axis.set_ylim(bottom=0)

        axes_list[0].set_ylabel("Max partitioned prefill GEMM duration (μs)")
        handles, labels = axes_list[0].get_legend_handles_labels()
        if handles:
            fig.legend(
                handles,
                labels,
                loc="upper center",
                ncol=min(len(handles), 4),
                bbox_to_anchor=(0.5, 1.08),
            )
        fig.suptitle("Temporal safety boundary (Prefill)", y=1.14)
        fig.tight_layout()
        _save_figure(fig, plot_path)


def _plot_prefill_vram_composition(
    *,
    results_df: pd.DataFrame,
    prefill_events_df: pd.DataFrame,
    decode_events_df: pd.DataFrame,
    model_constants_df: pd.DataFrame,
    success_rows: pd.DataFrame,
    trace_df: pd.DataFrame,
    timeline_df: pd.DataFrame,
    packed_timeline_df: pd.DataFrame,
    exemplar_row: pd.Series,
    plot5_chunk_selection: dict[str, int | None],
    plot_path: Path,
) -> None:
    del (
        prefill_events_df,
        decode_events_df,
        success_rows,
        trace_df,
        timeline_df,
        packed_timeline_df,
        exemplar_row,
        plot5_chunk_selection,
    )

    composition_df = _build_prefill_vram_composition_frame(
        results_df=results_df,
        model_constants_df=model_constants_df,
    )

    models = _ordered_models(composition_df["model_id"])
    with _apply_plot_style(width=max(10.5, 3.6 * len(models)), height=4.8):
        fig, axes = plt.subplots(1, len(models), sharey=True)
        axes_list = axes.ravel().tolist() if hasattr(axes, "ravel") else [axes]

        for axis, model_id in zip(axes_list, models):
            model_rows = composition_df[
                composition_df["model_id"] == model_id
            ].sort_values("chunk_tokens")
            x_positions = list(range(len(model_rows)))
            weights_gib = model_rows["weight_bytes"] / _BYTES_PER_GIB
            bulk_kv_gib = model_rows["bulk_kv_cache_bytes"] / _BYTES_PER_GIB
            workspace_gib = model_rows["prefill_workspace_bytes"] / _BYTES_PER_GIB
            parked_gib = model_rows["prefill_parked_activation_bytes"] / _BYTES_PER_GIB

            axis.bar(
                x_positions,
                weights_gib,
                color=_STACK_COLORS["Weights"],
                label="Pinned weights",
            )
            axis.bar(
                x_positions,
                workspace_gib,
                bottom=weights_gib + bulk_kv_gib,
                color=_STACK_COLORS["Prefill workspace"],
                label="Prefill workspace",
            )
            axis.bar(
                x_positions,
                parked_gib,
                bottom=weights_gib + bulk_kv_gib + workspace_gib,
                color=_STACK_COLORS["Prefill parked activation"],
                label="Prefill parked activation",
            )
            axis.bar(
                x_positions,
                bulk_kv_gib,
                bottom=weights_gib,
                color=_STACK_COLORS["Bulk KV cache"],
                label="Bulk KV cache",
            )
            axis.set_xticks(
                x_positions,
                [int(value) for value in model_rows["chunk_tokens"].tolist()],
            )
            axis.set_title(_short_model_label(model_id))
            axis.set_xlabel("Chunk size N (tokens)")
            axis.set_ylim(bottom=0)

        axes_list[0].set_ylabel("VRAM composition (GiB)")
        handles, labels = axes_list[0].get_legend_handles_labels()
        if handles:
            fig.legend(
                handles,
                labels,
                loc="upper center",
                ncol=min(len(handles), 4),
                bbox_to_anchor=(0.5, 1.08),
            )
        fig.suptitle("Spatial VRAM composition (Prefill)", y=1.14)
        fig.tight_layout()
        _save_figure(fig, plot_path)


def _plot_prefill_vram_composition_pie(
    *,
    results_df: pd.DataFrame,
    prefill_events_df: pd.DataFrame,
    decode_events_df: pd.DataFrame,
    model_constants_df: pd.DataFrame,
    success_rows: pd.DataFrame,
    trace_df: pd.DataFrame,
    timeline_df: pd.DataFrame,
    packed_timeline_df: pd.DataFrame,
    exemplar_row: pd.Series,
    plot5_chunk_selection: dict[str, int | None],
    plot_path: Path,
) -> None:
    del (
        prefill_events_df,
        decode_events_df,
        success_rows,
        trace_df,
        timeline_df,
        packed_timeline_df,
        exemplar_row,
        plot5_chunk_selection,
    )

    composition_df = _build_prefill_vram_composition_frame(
        results_df=results_df,
        model_constants_df=model_constants_df,
    )
    if composition_df.empty:
        raise PlotGenerationError(
            "Prefill VRAM composition pie plot requires at least one successful row"
        )

    composition_df = composition_df.sort_values(
        by=["model_id", "chunk_tokens"],
        key=lambda series: series.map(_model_sort_value)
        if series.name == "model_id"
        else series,
        kind="mergesort",
    ).reset_index(drop=True)

    panel_count = len(composition_df)
    ncols = min(3, panel_count)
    nrows = max(1, math.ceil(panel_count / ncols))

    with _apply_plot_style(width=4.2 * ncols, height=3.8 * nrows):
        fig, axes = plt.subplots(nrows, ncols)
        axes_list = axes.ravel().tolist() if hasattr(axes, "ravel") else [axes]

        labels = [
            "Pinned weights",
            "Bulk KV cache",
            "Prefill workspace",
            "Prefill parked activation",
        ]
        colors = [
            _STACK_COLORS["Weights"],
            _STACK_COLORS["Bulk KV cache"],
            _STACK_COLORS["Prefill workspace"],
            _STACK_COLORS["Prefill parked activation"],
        ]
        pie_labels = labels + ["Unused VRAM"]
        pie_colors = colors + ["#D9D9D9"]

        def _autopct(value: float) -> str:
            return f"{value:.1f}%" if value >= 0.5 else ""

        for axis, row in zip(axes_list, composition_df.itertuples(index=False)):
            weight_bytes = float(row.weight_bytes)
            bulk_kv_bytes = float(row.bulk_kv_cache_bytes)
            workspace_bytes = float(row.prefill_workspace_bytes)
            parked_bytes = float(row.prefill_parked_activation_bytes)
            vram_limit_bytes = max(float(row.vram_ceiling_bytes), 1.0)
            used_bytes = weight_bytes + bulk_kv_bytes + workspace_bytes + parked_bytes
            unused_bytes = max(vram_limit_bytes - used_bytes, 0.0)

            values = [
                weight_bytes,
                bulk_kv_bytes,
                workspace_bytes,
                parked_bytes,
                unused_bytes,
            ]
            if sum(values) <= 0:
                axis.text(0.5, 0.5, "No data", ha="center", va="center")
            else:
                axis.pie(
                    values,
                    labels=None,
                    colors=pie_colors,
                    autopct=_autopct,
                    startangle=90,
                    counterclock=False,
                    pctdistance=0.72,
                    wedgeprops={"linewidth": 0.5, "edgecolor": "white"},
                    textprops={"fontsize": 8},
                )
                if used_bytes > vram_limit_bytes:
                    axis.text(
                        0.5,
                        0.08,
                        f"Used {used_bytes / vram_limit_bytes * 100.0:.1f}% of VRAM limit",
                        transform=axis.transAxes,
                        ha="center",
                        va="center",
                        fontsize=7,
                    )
            axis.set_title(
                f"{_short_model_label(str(row.model_id))} · N={int(row.chunk_tokens)}"
            )

        for axis in axes_list[panel_count:]:
            axis.axis("off")

        legend_handles = [
            Line2D([0], [0], marker="o", linestyle="", color=color, label=label)
            for label, color in zip(pie_labels, pie_colors)
        ]
        fig.legend(
            handles=legend_handles,
            loc="upper center",
            ncol=min(len(legend_handles), 4),
            bbox_to_anchor=(0.5, 1.04),
        )

        fig.suptitle(
            "Spatial VRAM composition (Prefill) · pie view (% of VRAM limit)",
            y=1.1,
        )
        fig.tight_layout()
        _save_figure(fig, plot_path)


def _plot_ttft_vs_runway(
    *,
    results_df: pd.DataFrame,
    prefill_events_df: pd.DataFrame,
    decode_events_df: pd.DataFrame,
    model_constants_df: pd.DataFrame,
    success_rows: pd.DataFrame,
    trace_df: pd.DataFrame,
    timeline_df: pd.DataFrame,
    packed_timeline_df: pd.DataFrame,
    exemplar_row: pd.Series,
    plot5_chunk_selection: dict[str, int | None],
    plot_path: Path,
) -> None:
    del (
        prefill_events_df,
        decode_events_df,
        model_constants_df,
        success_rows,
        trace_df,
        timeline_df,
        packed_timeline_df,
        exemplar_row,
        plot5_chunk_selection,
    )

    tradeoff_df = _build_ttft_tradeoff_rows(results_df)
    if tradeoff_df.empty:
        raise PlotGenerationError(
            "TTFT vs runway plot requires at least one row with a resolved ttft_ms value"
        )

    partition_df = _build_prefill_safety_boundary_frame(results_df)
    partition_values = (
        partition_df["sm_ai_partition"]
        .dropna()
        .astype(int)
        .sort_values()
        .unique()
        .tolist()
        if not partition_df.empty
        else []
    )
    partition_color_map = {
        partition: _SM_AI_PARTITION_COLORS[index % len(_SM_AI_PARTITION_COLORS)]
        for index, partition in enumerate(partition_values)
    }

    models = _ordered_models(tradeoff_df["model_id"])
    with _apply_plot_style(width=max(10.0, 3.8 * len(models)), height=4.9):
        fig, axes = plt.subplots(1, len(models), sharey=True)
        axes_list = axes.ravel().tolist() if hasattr(axes, "ravel") else [axes]
        runway_axes: list[Any] = []

        for axis, model_id in zip(axes_list, models):
            model_rows = tradeoff_df[tradeoff_df["model_id"] == model_id].sort_values(
                "chunk_tokens"
            )
            chunks = model_rows["chunk_tokens"].astype(int).tolist()
            x_positions = list(range(len(chunks)))
            color = _model_color(model_id)
            runway_axis = axis.twinx()
            runway_axes.append(runway_axis)

            axis.plot(
                x_positions,
                model_rows["ttft_s"],
                marker="o",
                linestyle="-",
                color=color,
                label="TTFT (s)",
            )

            if not partition_df.empty:
                model_partition_rows = partition_df[
                    partition_df["model_id"] == model_id
                ].copy()
                for partition in partition_values:
                    partition_rows = model_partition_rows[
                        model_partition_rows["sm_ai_partition"] == partition
                    ]
                    if partition_rows.empty:
                        continue
                    partition_rows = partition_rows.set_index("chunk_tokens")
                    chunk_scales: list[float] = []
                    partition_scale = _analytical_partition_scale(partition)
                    for chunk in chunks:
                        candidate = partition_rows.loc[
                            partition_rows.index == chunk,
                            "prefill_max_gemm_us",
                        ]
                        if candidate.empty:
                            chunk_scales.append(float("nan"))
                            continue
                        chunk_scales.append(partition_scale)

                    proxy_ttft = [
                        float(model_rows.iloc[idx]["ttft_s"]) * chunk_scales[idx]
                        if idx < len(chunk_scales)
                        and not bool(pd.isna(chunk_scales[idx]))
                        else float("nan")
                        for idx in range(len(model_rows))
                    ]
                    axis.plot(
                        x_positions,
                        proxy_ttft,
                        marker=".",
                        linestyle="--",
                        linewidth=1.1,
                        alpha=0.85,
                        color=partition_color_map[partition],
                        label=f"SMs={partition} TTFT proxy",
                    )

            runway_axis.bar(
                x_positions,
                model_rows["decode_runway_gib"],
                width=0.55,
                alpha=0.35,
                color=color,
                label="Decode runway (GiB)",
            )
            axis.set_xticks(x_positions, chunks)
            axis.set_xlabel("Chunk size N (tokens)")
            axis.set_title(_short_model_label(model_id))
            axis.set_ylim(bottom=0)
            runway_axis.set_ylim(bottom=0)

        axes_list[0].set_ylabel("Simulated TTFT (s)")
        if runway_axes:
            runway_axes[-1].set_ylabel("Decode VRAM runway (GiB)")
        metric_handles = [
            Line2D(
                [0], [0], color="#222222", marker="o", linestyle="-", label="TTFT (s)"
            ),
            Line2D(
                [0],
                [0],
                color="#777777",
                marker="s",
                linestyle="",
                label="Decode runway (GiB)",
            ),
        ]
        metric_handles.extend(
            Line2D(
                [0],
                [0],
                color=partition_color_map[partition],
                marker=".",
                linestyle="--",
                label=f"SMs={partition} TTFT proxy",
            )
            for partition in partition_values
        )
        fig.legend(
            handles=metric_handles,
            loc="upper center",
            ncol=min(max(2, len(metric_handles)), 4),
            bbox_to_anchor=(0.5, 1.08),
        )
        fig.suptitle("TTFT vs. runway trade-off (with SM-AI proxy lines)", y=1.14)
        fig.tight_layout()
        _save_figure(fig, plot_path)


def _plot_decode_tpot_degradation(
    *,
    results_df: pd.DataFrame,
    prefill_events_df: pd.DataFrame,
    decode_events_df: pd.DataFrame,
    model_constants_df: pd.DataFrame,
    success_rows: pd.DataFrame,
    trace_df: pd.DataFrame,
    timeline_df: pd.DataFrame,
    packed_timeline_df: pd.DataFrame,
    exemplar_row: pd.Series,
    plot5_chunk_selection: dict[str, int | None],
    plot_path: Path,
) -> None:
    del (
        prefill_events_df,
        decode_events_df,
        trace_df,
        timeline_df,
        packed_timeline_df,
        exemplar_row,
    )

    tpot_partition_frame = _build_tpot_partition_frame(
        results_df=results_df,
        model_constants_df=model_constants_df,
    )
    if tpot_partition_frame.empty:
        with _apply_plot_style(width=17.0, height=3.8):
            available_models: list[str] = []
            for model_id in _ordered_models(success_rows["model_id"]):
                selected_chunk_tokens = plot5_chunk_selection.get(model_id)
                if selected_chunk_tokens is None:
                    continue
                panel_rows = _filter_result_rows(
                    success_rows,
                    model_id=model_id,
                    chunk_tokens=selected_chunk_tokens,
                ).dropna(
                    subset=["sequence_length", "tpot_ms_vram", "tpot_ms_pcie_async"]
                )
                if not panel_rows.empty:
                    available_models.append(model_id)
            if not available_models:
                raise PlotGenerationError(
                    "TPOT degradation plot has no model panels with data"
                )

            fig, axes = plt.subplots(1, len(available_models), sharey=True)
            axes_list = axes.ravel().tolist() if hasattr(axes, "ravel") else [axes]

            for axis, model_id in zip(axes_list, available_models):
                selected_chunk_tokens = int(plot5_chunk_selection.get(model_id) or 0)
                axis.set_title(_short_model_label(model_id))
                axis.set_xlabel("Sequence length")
                axis.set_axisbelow(True)

                panel_rows = _filter_result_rows(
                    success_rows,
                    model_id=model_id,
                    chunk_tokens=selected_chunk_tokens,
                ).dropna(
                    subset=["sequence_length", "tpot_ms_vram", "tpot_ms_pcie_async"]
                )
                panel_rows = panel_rows.sort_values("sequence_length")
                sequence_lengths = panel_rows["sequence_length"].astype(int)
                axis.plot(
                    sequence_lengths,
                    panel_rows["tpot_ms_vram"],
                    marker="o",
                    color=_TPOT_LINE_COLORS["DGX VRAM fetch"],
                    label="DGX VRAM fetch",
                )
                axis.plot(
                    sequence_lengths,
                    panel_rows["tpot_ms_pcie_async"],
                    marker="s",
                    color=_TPOT_LINE_COLORS["PCIe async fetch"],
                    label="PCIe async fetch",
                )
                axis.set_xticks(list(sequence_lengths))
                axis.set_ylim(bottom=0)
                axis.text(
                    0.03,
                    0.95,
                    f"N={selected_chunk_tokens}",
                    ha="left",
                    va="top",
                    transform=axis.transAxes,
                    fontsize=8,
                )

            handles = [
                Line2D(
                    [0],
                    [0],
                    color=_TPOT_LINE_COLORS["DGX VRAM fetch"],
                    marker="o",
                    linestyle="-",
                    label="DGX VRAM fetch",
                ),
                Line2D(
                    [0],
                    [0],
                    color=_TPOT_LINE_COLORS["PCIe async fetch"],
                    marker="s",
                    linestyle="-",
                    label="PCIe async fetch",
                ),
            ]
            fig.legend(
                handles=handles,
                loc="upper center",
                ncol=2,
                bbox_to_anchor=(0.5, 1.06),
            )
            fig.text(0.5, 0.01, "Sequence length", ha="center")
            fig.text(0.01, 0.5, "TPOT (ms)", va="center", rotation="vertical")
            fig.suptitle("Flash-decoding TPOT degradation (Decode)", y=1.08)
            fig.tight_layout()
            _save_figure(fig, plot_path)
        return

    _plot_tpot_with_partition_subplots(
        results_df=results_df,
        model_constants_df=model_constants_df,
        plot5_chunk_selection=plot5_chunk_selection,
        plot_path=plot_path,
        scheduled=True,
    )


def _plot_ttft_vs_runway_no_schedule(
    *,
    results_df: pd.DataFrame,
    prefill_events_df: pd.DataFrame,
    decode_events_df: pd.DataFrame,
    model_constants_df: pd.DataFrame,
    success_rows: pd.DataFrame,
    trace_df: pd.DataFrame,
    timeline_df: pd.DataFrame,
    packed_timeline_df: pd.DataFrame,
    exemplar_row: pd.Series,
    plot5_chunk_selection: dict[str, int | None],
    plot_path: Path,
) -> None:
    del (
        prefill_events_df,
        decode_events_df,
        success_rows,
        trace_df,
        timeline_df,
        packed_timeline_df,
        exemplar_row,
        plot5_chunk_selection,
    )
    no_schedule_df = _build_no_schedule_latency_frame(
        results_df=results_df,
        model_constants_df=model_constants_df,
    )
    tradeoff_df = _build_ttft_tradeoff_rows(
        no_schedule_df,
        ttft_column="ttft_ms_nosched",
    )
    if tradeoff_df.empty:
        raise PlotGenerationError(
            "No-schedule TTFT plot requires at least one row with resolved no-schedule timings"
        )

    ttft_partition_df = _build_ttft_no_schedule_partition_frame(
        results_df=results_df,
        model_constants_df=model_constants_df,
    )
    if ttft_partition_df.empty:
        raise PlotGenerationError(
            "No-schedule TTFT plot requires partition-level TTFT estimates"
        )

    partition_values = (
        ttft_partition_df["sm_ai_partition"]
        .dropna()
        .astype(int)
        .sort_values()
        .unique()
        .tolist()
    )
    partition_color_map = {
        partition: _SM_AI_PARTITION_COLORS[index % len(_SM_AI_PARTITION_COLORS)]
        for index, partition in enumerate(partition_values)
    }
    models = _ordered_models(ttft_partition_df["model_id"])
    models = [
        model_id
        for model_id in models
        if not ttft_partition_df[ttft_partition_df["model_id"] == model_id].empty
        and not tradeoff_df[tradeoff_df["model_id"] == model_id].empty
    ]
    if not models:
        raise PlotGenerationError("No-schedule TTFT plot requires at least one model")

    with _apply_plot_style(width=max(10.0, 3.8 * len(models)), height=4.9):
        fig, axes = plt.subplots(1, len(models), sharey=True)
        axes_list = axes.ravel().tolist() if hasattr(axes, "ravel") else [axes]
        runway_axes: list[Any] = []

        for axis, model_id in zip(axes_list, models):
            model_rows = tradeoff_df[tradeoff_df["model_id"] == model_id].sort_values(
                "chunk_tokens"
            )
            chunks = model_rows["chunk_tokens"].astype(int).tolist()
            x_positions = list(range(len(chunks)))
            color = _model_color(model_id)
            runway_axis = axis.twinx()
            runway_axes.append(runway_axis)

            model_partition_rows = ttft_partition_df[
                ttft_partition_df["model_id"] == model_id
            ].copy()
            model_partition_rows = model_partition_rows.set_index(
                ["chunk_tokens", "sm_ai_partition"]
            )
            for partition in partition_values:
                y_values: list[float] = []
                for chunk in chunks:
                    key = (chunk, partition)
                    if key not in model_partition_rows.index:
                        y_values.append(float("nan"))
                        continue
                    y_values.append(
                        float(model_partition_rows.loc[key, "ttft_s_nosched"])
                    )
                axis.plot(
                    x_positions,
                    y_values,
                    marker="o",
                    linestyle="-",
                    linewidth=1.5,
                    color=partition_color_map[partition],
                    label=f"SMs={partition}",
                )

            runway_axis.bar(
                x_positions,
                model_rows["decode_runway_gib"],
                width=0.55,
                alpha=0.35,
                color=color,
                label="Decode runway (GiB)",
            )
            axis.set_xticks(x_positions, chunks)
            axis.set_xlabel("Chunk size N (tokens)")
            axis.set_title(_short_model_label(model_id))
            axis.set_ylim(bottom=0)
            runway_axis.set_ylim(bottom=0)

        axes_list[0].set_ylabel("No-schedule TTFT (s)")
        if runway_axes:
            runway_axes[-1].set_ylabel("Decode VRAM runway (GiB)")
        metric_handles = [
            Line2D(
                [0],
                [0],
                color="#777777",
                marker="s",
                linestyle="",
                label="Decode runway (GiB)",
            ),
        ]
        metric_handles.extend(
            Line2D(
                [0],
                [0],
                color=partition_color_map[partition],
                marker="o",
                linestyle="-",
                label=f"SMs={partition}",
            )
            for partition in partition_values
        )
        fig.legend(
            handles=metric_handles,
            loc="upper center",
            ncol=min(max(2, len(metric_handles)), 5),
            bbox_to_anchor=(0.5, 1.08),
        )
        fig.suptitle("TTFT vs. runway trade-off (no schedule, by SM_AI)", y=1.14)
        fig.tight_layout()
        _save_figure(fig, plot_path)


def _plot_decode_tpot_degradation_no_schedule(
    *,
    results_df: pd.DataFrame,
    prefill_events_df: pd.DataFrame,
    decode_events_df: pd.DataFrame,
    model_constants_df: pd.DataFrame,
    success_rows: pd.DataFrame,
    trace_df: pd.DataFrame,
    timeline_df: pd.DataFrame,
    packed_timeline_df: pd.DataFrame,
    exemplar_row: pd.Series,
    plot5_chunk_selection: dict[str, int | None],
    plot_path: Path,
) -> None:
    del (
        prefill_events_df,
        decode_events_df,
        success_rows,
        trace_df,
        timeline_df,
        packed_timeline_df,
        exemplar_row,
    )
    _plot_tpot_with_partition_subplots(
        results_df=results_df,
        model_constants_df=model_constants_df,
        plot5_chunk_selection=plot5_chunk_selection,
        plot_path=plot_path,
        scheduled=False,
    )


def _plot_operation_level_microarchitecture_summary(
    *,
    results_df: pd.DataFrame,
    prefill_events_df: pd.DataFrame,
    decode_events_df: pd.DataFrame,
    model_constants_df: pd.DataFrame,
    success_rows: pd.DataFrame,
    trace_df: pd.DataFrame,
    timeline_df: pd.DataFrame,
    packed_timeline_df: pd.DataFrame,
    exemplar_row: pd.Series,
    plot5_chunk_selection: dict[str, int | None],
    plot_path: Path,
) -> None:
    del (
        results_df,
        model_constants_df,
        success_rows,
        trace_df,
        timeline_df,
        packed_timeline_df,
        exemplar_row,
        plot5_chunk_selection,
    )

    summary_df = _build_operation_level_summary_frame(
        prefill_events_df=prefill_events_df,
        decode_events_df=decode_events_df,
    )
    if summary_df.empty:
        raise PlotGenerationError(
            "Operation-level micro-architecture summary requires at least one raw profiling row"
        )

    phases = ("Prefill", "Decode")
    metrics = (
        ("duration_us", "Execution duration (μs)"),
        ("workspace_mb", "Peak workspace / memory footprint (MB)"),
    )
    partitions = (
        summary_df["sm_ai_partition"]
        .dropna()
        .astype(int)
        .sort_values()
        .unique()
        .tolist()
    )
    color_map = {
        partition: _SM_AI_PARTITION_COLORS[index % len(_SM_AI_PARTITION_COLORS)]
        for index, partition in enumerate(partitions)
    }

    with _apply_plot_style(width=12.5, height=7.6):
        fig, axes = plt.subplots(2, 2, sharex=False)
        bar_width = 0.8 / max(len(partitions), 1)
        x_positions = list(range(len(_MICROARCH_OPERATION_ORDER)))

        for row_index, phase in enumerate(phases):
            phase_rows = summary_df[summary_df["phase"] == phase]
            for col_index, (metric_column, ylabel) in enumerate(metrics):
                ax = axes[row_index][col_index]
                for partition_index, partition in enumerate(partitions):
                    partition_rows = phase_rows[
                        phase_rows["sm_ai_partition"] == partition
                    ]
                    values = []
                    for operation in _MICROARCH_OPERATION_ORDER:
                        operation_rows = partition_rows[
                            partition_rows["operation_group"] == operation
                        ]
                        value = (
                            float(operation_rows[metric_column].iloc[0])
                            if not operation_rows.empty
                            else 0.0
                        )
                        values.append(value)
                    offset = (partition_index - (len(partitions) - 1) / 2.0) * bar_width
                    ax.bar(
                        [position + offset for position in x_positions],
                        values,
                        width=bar_width,
                        color=color_map[partition],
                        label=f"SMs={partition}",
                    )
                ax.set_xticks(
                    x_positions, _MICROARCH_OPERATION_ORDER, rotation=25, ha="right"
                )
                ax.set_ylabel(ylabel)
                ax.set_title(
                    f"{phase} · {'Duration' if metric_column == 'duration_us' else 'Workspace'}"
                )
                ax.set_ylim(bottom=0)

        handles, labels = axes[0][0].get_legend_handles_labels()
        if handles:
            fig.legend(
                handles,
                labels,
                loc="upper center",
                ncol=min(len(handles), 4),
                bbox_to_anchor=(0.5, 1.02),
            )
        fig.suptitle("Operation-level micro-architecture summary", y=1.06)
        fig.tight_layout()
    _save_figure(fig, plot_path)


def _plot_hardware_utilization_profiling(
    *,
    results_df: pd.DataFrame,
    prefill_events_df: pd.DataFrame,
    decode_events_df: pd.DataFrame,
    model_constants_df: pd.DataFrame,
    success_rows: pd.DataFrame,
    trace_df: pd.DataFrame,
    timeline_df: pd.DataFrame,
    packed_timeline_df: pd.DataFrame,
    exemplar_row: pd.Series,
    plot5_chunk_selection: dict[str, int | None],
    plot_path: Path,
) -> None:
    """Revised-only: visualize hardware telemetry summary fields emitted in
    the revised simulation results. This plot is emitted only when the run
    manifest indicates the revised ran-dgxspark-v1 experiment.
    """
    del (
        prefill_events_df,
        decode_events_df,
        model_constants_df,
        timeline_df,
        packed_timeline_df,
        exemplar_row,
        plot5_chunk_selection,
    )

    required_macro = [
        "prefill_gpu_util",
        "decode_vram_gpu_util",
        "decode_pcie_async_gpu_util",
    ]
    missing = [column for column in required_macro if column not in results_df.columns]
    if missing:
        raise PlotGenerationError(
            "Revised hardware utilization profiling requires telemetry columns: "
            f"{', '.join(missing)}"
        )

    working = results_df.copy()
    for column in (
        "chunk_tokens",
        "sequence_length",
        "prefill_gpu_util",
        "prefill_acu_pct",
        "prefill_gbu_pct",
        "prefill_smu_pct",
        "decode_vram_gpu_util",
        "decode_pcie_async_gpu_util",
        "decode_vram_acu_pct",
        "decode_pcie_async_acu_pct",
        "decode_vram_gbu_pct",
        "decode_pcie_async_gbu_pct",
        "decode_vram_smu_pct",
        "decode_pcie_async_smu_pct",
    ):
        if column in working.columns:
            working[column] = pd.to_numeric(working[column], errors="coerce")

    prefill_agg = (
        working.groupby("chunk_tokens", as_index=False)
        .agg(
            gpu_util=("prefill_gpu_util", "mean"),
            acu=("prefill_acu_pct", "mean"),
            gbu=("prefill_gbu_pct", "mean"),
            smu=("prefill_smu_pct", "mean"),
        )
        .sort_values("chunk_tokens")
    )
    all_chunks = sorted(working["chunk_tokens"].dropna().astype(int).unique().tolist())
    if all_chunks:
        prefill_agg = (
            prefill_agg.set_index("chunk_tokens")
            .reindex(all_chunks)
            .reset_index()
            .rename(columns={"index": "chunk_tokens"})
        )
    decode_columns = {
        "gpu_util": ["decode_vram_gpu_util", "decode_pcie_async_gpu_util"],
        "acu": ["decode_vram_acu_pct", "decode_pcie_async_acu_pct"],
        "gbu": ["decode_vram_gbu_pct", "decode_pcie_async_gbu_pct"],
        "smu": ["decode_vram_smu_pct", "decode_pcie_async_smu_pct"],
    }
    for target_name, source_columns in decode_columns.items():
        available_columns = [
            column for column in source_columns if column in working.columns
        ]
        if available_columns:
            working[f"decode_{target_name}"] = working[available_columns].mean(axis=1)
        else:
            working[f"decode_{target_name}"] = float("nan")
    decode_agg = (
        working.groupby("sequence_length", as_index=False)
        .agg(
            gpu_util=("decode_gpu_util", "mean"),
            acu=("decode_acu", "mean"),
            gbu=("decode_gbu", "mean"),
            smu=("decode_smu", "mean"),
        )
        .sort_values("sequence_length")
    )
    all_sequence_lengths = sorted(
        working["sequence_length"].dropna().astype(int).unique().tolist()
    )
    if all_sequence_lengths:
        decode_agg = (
            decode_agg.set_index("sequence_length")
            .reindex(all_sequence_lengths)
            .reset_index()
            .rename(columns={"index": "sequence_length"})
        )

    if prefill_agg.empty or decode_agg.empty:
        raise PlotGenerationError(
            "Hardware utilization plotting requires non-empty prefill and decode telemetry"
        )

    with _apply_plot_style(width=13.0, height=5.1):
        fig, (prefill_ax, decode_ax) = plt.subplots(1, 2, sharey=False)

        def _plot_utilization_panel(
            axis: Any, frame: pd.DataFrame, *, x_col: str, title: str, xlabel: str
        ) -> None:
            x_values = [int(value) for value in frame[x_col].tolist()]
            x_positions = list(range(len(x_values)))
            width = 0.22
            gpu_values = frame["gpu_util"].fillna(0.0)
            microscopic_frame = frame[["acu", "gbu", "smu"]]
            if bool(cast(bool, microscopic_frame.isna().any().any())):
                raise ValueError("Microscopic telemetry missing")
            acu_values = frame["acu"].tolist()
            gbu_values = frame["gbu"].tolist()
            smu_values = frame["smu"].tolist()
            axis.bar(
                [x - width for x in x_positions],
                acu_values,
                width=width,
                label="ACU",
                color="#4C72B0",
            )
            axis.bar(
                x_positions,
                gbu_values,
                width=width,
                label="GBU",
                color="#55A868",
            )
            axis.bar(
                [x + width for x in x_positions],
                smu_values,
                width=width,
                label="SMU",
                color="#C44E52",
            )
            axis.scatter(
                [x - width for x in x_positions],
                acu_values,
                s=22,
                color="#4C72B0",
                zorder=3,
            )
            axis.scatter(
                x_positions,
                gbu_values,
                s=22,
                color="#55A868",
                zorder=3,
            )
            axis.scatter(
                [x + width for x in x_positions],
                smu_values,
                s=22,
                color="#C44E52",
                zorder=3,
            )
            axis.plot(
                x_positions,
                gpu_values,
                marker="o",
                color="#222222",
                linewidth=1.6,
                linestyle="--",
                label="GPU util (macro)",
            )
            axis.set_xticks(x_positions, x_values)
            axis.tick_params(axis="x", rotation=0)
            axis.margins(x=0.08)
            axis.set_xlabel(xlabel)
            axis.set_title(title)
            panel_max = max(
                float(max(acu_values, default=0.0)),
                float(max(gbu_values, default=0.0)),
                float(max(smu_values, default=0.0)),
                float(gpu_values.max() if not gpu_values.empty else 0.0),
            )
            if panel_max <= 10:
                tick_step = 1
            elif panel_max <= 25:
                tick_step = 2
            elif panel_max <= 50:
                tick_step = 5
            else:
                tick_step = 10
            y_upper = max(
                tick_step * 3,
                int(math.ceil((max(panel_max, 1.0) * 1.2) / tick_step) * tick_step),
            )
            axis.set_ylim(0, float(y_upper))
            axis.yaxis.set_major_locator(MultipleLocator(tick_step))

        _plot_utilization_panel(
            prefill_ax,
            prefill_agg,
            x_col="chunk_tokens",
            title="Prefill utilization vs chunk size",
            xlabel="Chunk size N (tokens)",
        )
        _plot_utilization_panel(
            decode_ax,
            decode_agg,
            x_col="sequence_length",
            title="Decode utilization vs sequence length",
            xlabel="Sequence length L (tokens)",
        )
        prefill_ax.set_ylabel("Utilization (%)")

        legend_handles = [
            Line2D([0], [0], color="#4C72B0", marker="s", linestyle="", label="ACU"),
            Line2D([0], [0], color="#55A868", marker="s", linestyle="", label="GBU"),
            Line2D([0], [0], color="#C44E52", marker="s", linestyle="", label="SMU"),
            Line2D(
                [0],
                [0],
                color="#222222",
                marker="o",
                linestyle="-",
                label="GPU util (macro)",
            ),
        ]
        fig.legend(
            handles=legend_handles,
            loc="upper center",
            ncol=4,
            bbox_to_anchor=(0.5, 1.08),
        )
        fig.suptitle("Hardware utilization profiling", y=1.13)
        fig.tight_layout()
    _save_figure(fig, plot_path)


def _plot_hardware_utilization_heatmap_acu(
    **kwargs: Any,
) -> None:
    _plot_hardware_utilization_heatmap_metric(
        metric_column="acu_pct",
        metric_label="ACU (%)",
        **kwargs,
    )


def _plot_hardware_utilization_heatmap_gbu(
    **kwargs: Any,
) -> None:
    _plot_hardware_utilization_heatmap_metric(
        metric_column="gbu_pct",
        metric_label="GBU (%)",
        **kwargs,
    )


def _plot_hardware_utilization_heatmap_smu(
    **kwargs: Any,
) -> None:
    _plot_hardware_utilization_heatmap_metric(
        metric_column="smu_pct",
        metric_label="SMU (%)",
        **kwargs,
    )


def _plot_hardware_utilization_heatmap_gpu_util(
    **kwargs: Any,
) -> None:
    _plot_hardware_utilization_heatmap_metric(
        metric_column="gpu_util",
        metric_label="GPU util (%)",
        **kwargs,
    )


def _plot_hardware_utilization_heatmap_metric(
    *,
    results_df: pd.DataFrame,
    prefill_events_df: pd.DataFrame,
    decode_events_df: pd.DataFrame,
    model_constants_df: pd.DataFrame,
    success_rows: pd.DataFrame,
    trace_df: pd.DataFrame,
    timeline_df: pd.DataFrame,
    packed_timeline_df: pd.DataFrame,
    exemplar_row: pd.Series,
    plot5_chunk_selection: dict[str, int | None],
    plot_path: Path,
    metric_column: str,
    metric_label: str,
) -> None:
    del (
        model_constants_df,
        success_rows,
        trace_df,
        timeline_df,
        packed_timeline_df,
        exemplar_row,
        plot5_chunk_selection,
    )

    prefill_frame = _build_prefill_utilization_heatmap_frame(
        prefill_events_df=prefill_events_df,
        metric_column=metric_column,
    )
    if prefill_frame.empty:
        prefill_frame = _build_prefill_utilization_heatmap_frame_from_results(
            results_df=results_df,
            metric_column=metric_column,
        )
    decode_frame = _build_decode_utilization_heatmap_frame(
        decode_events_df=decode_events_df,
        metric_column=metric_column,
    )
    if decode_frame.empty:
        decode_frame = _build_decode_utilization_heatmap_frame_from_results(
            results_df=results_df,
            metric_column=metric_column,
        )
    if prefill_frame.empty and decode_frame.empty:
        raise PlotGenerationError(
            f"Revised heatmap requires telemetry rows for metric '{metric_column}'"
        )

    model_ids = pd.Series(dtype="object")
    if not prefill_frame.empty:
        model_ids = pd.concat([model_ids, prefill_frame["model_id"]], ignore_index=True)
    if not decode_frame.empty:
        model_ids = pd.concat([model_ids, decode_frame["model_id"]], ignore_index=True)
    models = _ordered_models(model_ids)
    if not models:
        raise PlotGenerationError("Heatmap rendering requires at least one model")

    vmax = 100.0

    with _apply_plot_style(
        width=12.0, height=max(4.2, 2.6 * len(models)), font_size=8.5
    ):
        fig, axes = plt.subplots(len(models), 2, squeeze=False)
        image_handle: Any | None = None

        for row_index, model_id in enumerate(models):
            prefill_axis = axes[row_index][0]
            decode_axis = axes[row_index][1]
            prefill_model = prefill_frame[prefill_frame["model_id"] == model_id].copy()
            decode_model = decode_frame[decode_frame["model_id"] == model_id].copy()
            image_handle = _render_utilization_heatmap_panel(
                axis=prefill_axis,
                frame=prefill_model,
                x_column="chunk_tokens",
                metric_label=metric_label,
                title=f"{_short_model_label(model_id)} · Prefill",
                xlabel="Chunk size N (tokens)",
                vmin=0.0,
                vmax=vmax,
                fallback_image=image_handle,
            )
            image_handle = _render_utilization_heatmap_panel(
                axis=decode_axis,
                frame=decode_model,
                x_column="sequence_length",
                metric_label=metric_label,
                title=f"{_short_model_label(model_id)} · Decode",
                xlabel="Sequence length L (tokens)",
                vmin=0.0,
                vmax=vmax,
                fallback_image=image_handle,
            )
            prefill_axis.set_ylabel("SM partition (SM count)")

        if image_handle is not None:
            fig.colorbar(
                image_handle,
                ax=axes.ravel().tolist(),
                location="right",
                shrink=0.9,
                label=metric_label,
            )
        fig.suptitle(
            f"Hardware utilization heatmap · {metric_label} (SM_AI × N/L)",
            y=1.02,
        )
        fig.tight_layout()
        _save_figure(fig, plot_path)


def _build_prefill_utilization_heatmap_frame(
    *,
    prefill_events_df: pd.DataFrame,
    metric_column: str,
) -> pd.DataFrame:
    required_columns = {"model_id", "chunk_tokens", "sm_ai_partition", metric_column}
    if prefill_events_df.empty or not required_columns.issubset(
        prefill_events_df.columns
    ):
        return pd.DataFrame(
            columns=["model_id", "chunk_tokens", "sm_ai_partition", "metric_value"]
        )
    frame = prefill_events_df.loc[
        :, ["model_id", "chunk_tokens", "sm_ai_partition", metric_column]
    ].copy()
    frame["chunk_tokens"] = pd.to_numeric(frame["chunk_tokens"], errors="coerce")
    frame["sm_ai_partition"] = pd.to_numeric(frame["sm_ai_partition"], errors="coerce")
    frame["metric_value"] = pd.to_numeric(frame[metric_column], errors="coerce")
    frame = frame.dropna(subset=["chunk_tokens", "sm_ai_partition", "metric_value"])
    grouped = (
        frame.groupby(["model_id", "chunk_tokens", "sm_ai_partition"], as_index=False)
        .agg(metric_value=("metric_value", "mean"))
        .sort_values(["model_id", "sm_ai_partition", "chunk_tokens"])
    )
    grouped["chunk_tokens"] = grouped["chunk_tokens"].astype(int)
    grouped["sm_ai_partition"] = grouped["sm_ai_partition"].astype(int)
    return grouped


def _build_decode_utilization_heatmap_frame(
    *,
    decode_events_df: pd.DataFrame,
    metric_column: str,
) -> pd.DataFrame:
    required_columns = {
        "model_id",
        "sequence_length",
        "sm_ai_partition",
        metric_column,
    }
    if decode_events_df.empty or not required_columns.issubset(
        decode_events_df.columns
    ):
        return pd.DataFrame(
            columns=["model_id", "sequence_length", "sm_ai_partition", "metric_value"]
        )
    frame = decode_events_df.loc[
        :, ["model_id", "sequence_length", "sm_ai_partition", metric_column]
    ].copy()
    frame["sequence_length"] = pd.to_numeric(frame["sequence_length"], errors="coerce")
    frame["sm_ai_partition"] = pd.to_numeric(frame["sm_ai_partition"], errors="coerce")
    frame["metric_value"] = pd.to_numeric(frame[metric_column], errors="coerce")
    frame = frame.dropna(subset=["sequence_length", "sm_ai_partition", "metric_value"])
    grouped = (
        frame.groupby(
            ["model_id", "sequence_length", "sm_ai_partition"], as_index=False
        )
        .agg(metric_value=("metric_value", "mean"))
        .sort_values(["model_id", "sm_ai_partition", "sequence_length"])
    )
    grouped["sequence_length"] = grouped["sequence_length"].astype(int)
    grouped["sm_ai_partition"] = grouped["sm_ai_partition"].astype(int)
    return grouped


def _build_prefill_utilization_heatmap_frame_from_results(
    *,
    results_df: pd.DataFrame,
    metric_column: str,
) -> pd.DataFrame:
    if results_df.empty:
        return pd.DataFrame(
            columns=["model_id", "chunk_tokens", "sm_ai_partition", "metric_value"]
        )
    metric_source_column = (
        "prefill_gpu_util"
        if metric_column == "gpu_util"
        else f"prefill_{metric_column}"
    )
    if metric_source_column not in results_df.columns:
        return pd.DataFrame(
            columns=["model_id", "chunk_tokens", "sm_ai_partition", "metric_value"]
        )
    partition_frame = _build_prefill_safety_boundary_frame(results_df)
    if partition_frame.empty:
        return pd.DataFrame(
            columns=["model_id", "chunk_tokens", "sm_ai_partition", "metric_value"]
        )

    working = results_df[["model_id", "chunk_tokens", metric_source_column]].copy()
    working["chunk_tokens"] = pd.to_numeric(working["chunk_tokens"], errors="coerce")
    working["metric_value"] = pd.to_numeric(
        working[metric_source_column], errors="coerce"
    )
    base_metric = (
        working.dropna(subset=["chunk_tokens", "metric_value"])
        .groupby(["model_id", "chunk_tokens"], as_index=False)
        .agg(metric_value=("metric_value", "mean"))
    )
    if base_metric.empty:
        return pd.DataFrame(
            columns=["model_id", "chunk_tokens", "sm_ai_partition", "metric_value"]
        )

    partition_frame = partition_frame.copy()
    partition_frame["chunk_tokens"] = pd.to_numeric(
        partition_frame["chunk_tokens"], errors="coerce"
    )
    partition_frame["sm_ai_partition"] = pd.to_numeric(
        partition_frame["sm_ai_partition"], errors="coerce"
    )
    partition_frame["prefill_max_gemm_us"] = pd.to_numeric(
        partition_frame["prefill_max_gemm_us"], errors="coerce"
    )
    partition_frame = partition_frame.dropna(
        subset=["chunk_tokens", "sm_ai_partition", "prefill_max_gemm_us"]
    )
    if partition_frame.empty:
        return pd.DataFrame(
            columns=["model_id", "chunk_tokens", "sm_ai_partition", "metric_value"]
        )

    merged = partition_frame.merge(
        base_metric,
        on=["model_id", "chunk_tokens"],
        how="left",
    )
    merged["metric_value"] = merged["metric_value"].clip(lower=0.0, upper=100.0)
    merged["chunk_tokens"] = merged["chunk_tokens"].astype(int)
    merged["sm_ai_partition"] = merged["sm_ai_partition"].astype(int)
    return (
        merged.groupby(["model_id", "chunk_tokens", "sm_ai_partition"], as_index=False)
        .agg(metric_value=("metric_value", "mean"))
        .sort_values(["model_id", "sm_ai_partition", "chunk_tokens"])
        .reset_index(drop=True)
    )


def _build_decode_utilization_heatmap_frame_from_results(
    *,
    results_df: pd.DataFrame,
    metric_column: str,
) -> pd.DataFrame:
    if results_df.empty or "sequence_length" not in results_df.columns:
        return pd.DataFrame(
            columns=["model_id", "sequence_length", "sm_ai_partition", "metric_value"]
        )
    if metric_column == "gpu_util":
        decode_sources = ["decode_vram_gpu_util", "decode_pcie_async_gpu_util"]
    else:
        decode_sources = [
            f"decode_vram_{metric_column}",
            f"decode_pcie_async_{metric_column}",
        ]
    available_sources = [
        column for column in decode_sources if column in results_df.columns
    ]
    if not available_sources:
        return pd.DataFrame(
            columns=["model_id", "sequence_length", "sm_ai_partition", "metric_value"]
        )

    base = results_df[["model_id", "sequence_length", *available_sources]].copy()
    base["sequence_length"] = pd.to_numeric(base["sequence_length"], errors="coerce")
    base["metric_value"] = base[available_sources].apply(
        lambda row: pd.to_numeric(row, errors="coerce").mean(),
        axis=1,
    )
    base_metric = (
        base.dropna(subset=["sequence_length", "metric_value"])
        .groupby(["model_id", "sequence_length"], as_index=False)
        .agg(metric_value=("metric_value", "mean"))
    )
    if base_metric.empty:
        return pd.DataFrame(
            columns=["model_id", "sequence_length", "sm_ai_partition", "metric_value"]
        )

    partition_pattern = re.compile(r"decode_max_gemv_us_(?:vram|pcie_async)_sm(\d+)")
    partition_columns = [
        column for column in results_df.columns if partition_pattern.match(column)
    ]
    if not partition_columns:
        is_revised = "experiment_type" in results_df.columns and (
            results_df["experiment_type"]
            .astype(str)
            .str.strip()
            .str.lower()
            .eq(experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE)
            .any()
        )
        if not is_revised:
            return pd.DataFrame(
                columns=[
                    "model_id",
                    "sequence_length",
                    "sm_ai_partition",
                    "metric_value",
                ]
            )
        synthetic_rows: list[dict[str, float | int | str]] = []
        for _, row in base_metric.iterrows():
            metric_value = pd.to_numeric(row.get("metric_value"), errors="coerce")
            sequence_value = pd.to_numeric(row.get("sequence_length"), errors="coerce")
            if bool(pd.isna(metric_value)) or bool(pd.isna(sequence_value)):
                continue
            metric_value = float(metric_value)
            sequence_length = int(float(sequence_value))
            for partition in experiments.RAN_DGXSPARK_V1_SM_AI_PARTITIONS:
                synthetic_rows.append(
                    {
                        "model_id": str(row.get("model_id")),
                        "sequence_length": sequence_length,
                        "sm_ai_partition": int(partition),
                        "metric_value": metric_value,
                    }
                )
        synthetic_df = pd.DataFrame(synthetic_rows)
        if synthetic_df.empty:
            return synthetic_df
        synthetic_df["metric_value"] = synthetic_df["metric_value"].clip(
            lower=0.0, upper=100.0
        )
        return synthetic_df.sort_values(
            ["model_id", "sm_ai_partition", "sequence_length"]
        ).reset_index(drop=True)

    partition_rows: list[dict[str, float | int | str]] = []
    for _, row in results_df.iterrows():
        model_id = str(row.get("model_id"))
        sequence_value = pd.to_numeric(row.get("sequence_length"), errors="coerce")
        if bool(pd.isna(sequence_value)):
            continue
        sequence_length = int(float(sequence_value))
        by_partition: dict[int, list[float]] = {}
        for column in partition_columns:
            match = partition_pattern.match(column)
            if match is None:
                continue
            value = pd.to_numeric(row.get(column), errors="coerce")
            if bool(pd.isna(value)):
                continue
            partition = int(match.group(1))
            by_partition.setdefault(partition, []).append(float(value))
        for partition, values in by_partition.items():
            partition_rows.append(
                {
                    "model_id": model_id,
                    "sequence_length": sequence_length,
                    "sm_ai_partition": partition,
                    "decode_max_gemv_proxy": float(np.mean(values)),
                }
            )

    partition_frame = pd.DataFrame(partition_rows)
    if partition_frame.empty:
        return pd.DataFrame(
            columns=["model_id", "sequence_length", "sm_ai_partition", "metric_value"]
        )
    merged = partition_frame.merge(
        base_metric,
        on=["model_id", "sequence_length"],
        how="left",
    )
    merged["metric_value"] = merged["metric_value"].clip(lower=0.0, upper=100.0)
    merged["sequence_length"] = merged["sequence_length"].astype(int)
    merged["sm_ai_partition"] = merged["sm_ai_partition"].astype(int)
    return (
        merged.groupby(
            ["model_id", "sequence_length", "sm_ai_partition"], as_index=False
        )
        .agg(metric_value=("metric_value", "mean"))
        .sort_values(["model_id", "sm_ai_partition", "sequence_length"])
        .reset_index(drop=True)
    )


def _render_utilization_heatmap_panel(
    *,
    axis: Any,
    frame: pd.DataFrame,
    x_column: str,
    metric_label: str,
    title: str,
    xlabel: str,
    vmin: float,
    vmax: float,
    fallback_image: Any | None,
) -> Any:
    axis.set_title(title)
    axis.set_xlabel(xlabel)
    if frame.empty:
        axis.text(
            0.5,
            0.5,
            "No telemetry",
            transform=axis.transAxes,
            ha="center",
            va="center",
        )
        axis.set_xticks([])
        axis.set_yticks([])
        if fallback_image is not None:
            return fallback_image
        placeholder = np.array([[0.0]], dtype=float)
        image = axis.imshow(
            placeholder,
            aspect="auto",
            origin="lower",
            vmin=vmin,
            vmax=vmax,
            cmap="viridis",
        )
        axis.set_xticks([])
        axis.set_yticks([])
        return image

    aggregated = frame.copy()
    aggregated[x_column] = pd.to_numeric(aggregated[x_column], errors="coerce")
    aggregated["sm_ai_partition"] = pd.to_numeric(
        aggregated["sm_ai_partition"], errors="coerce"
    )
    aggregated["metric_value"] = pd.to_numeric(
        aggregated["metric_value"], errors="coerce"
    )
    aggregated = aggregated.dropna(subset=[x_column, "sm_ai_partition", "metric_value"])
    if aggregated.empty:
        axis.text(
            0.5,
            0.5,
            f"No {metric_label.lower()} values",
            transform=axis.transAxes,
            ha="center",
            va="center",
        )
        axis.set_xticks([])
        axis.set_yticks([])
        if fallback_image is not None:
            return fallback_image
        placeholder = np.array([[0.0]], dtype=float)
        image = axis.imshow(
            placeholder,
            aspect="auto",
            origin="lower",
            vmin=vmin,
            vmax=vmax,
            cmap="viridis",
        )
        axis.set_xticks([])
        axis.set_yticks([])
        return image

    aggregated[x_column] = aggregated[x_column].astype(int)
    aggregated["sm_ai_partition"] = aggregated["sm_ai_partition"].astype(int)
    aggregated = (
        aggregated.groupby(["sm_ai_partition", x_column], as_index=False)
        .agg(metric_value=("metric_value", "mean"))
        .sort_values(["sm_ai_partition", x_column])
    )

    x_values = sorted(aggregated[x_column].unique().tolist())
    y_values = sorted(aggregated["sm_ai_partition"].unique().tolist())
    matrix = np.full((len(y_values), len(x_values)), np.nan, dtype=float)
    x_index = {value: index for index, value in enumerate(x_values)}
    y_index = {value: index for index, value in enumerate(y_values)}
    for _, row in aggregated.iterrows():
        x_value = int(row[x_column])
        y_value = int(row["sm_ai_partition"])
        matrix[y_index[y_value], x_index[x_value]] = float(row["metric_value"])

    masked_matrix = np.ma.array(matrix, mask=np.isnan(matrix))
    image = axis.imshow(
        masked_matrix,
        aspect="auto",
        origin="lower",
        vmin=vmin,
        vmax=vmax,
        cmap="viridis",
    )
    axis.set_xticks(list(range(len(x_values))), x_values)
    axis.set_yticks(list(range(len(y_values))), y_values)
    axis.grid(False)
    if bool(np.isnan(matrix).all()):
        axis.text(
            0.5,
            0.5,
            f"No {metric_label.lower()} values",
            transform=axis.transAxes,
            ha="center",
            va="center",
        )
    return image


def _load_required_csv(
    csv_path: Path, *, required_columns: Sequence[str]
) -> pd.DataFrame:
    if not csv_path.exists():
        raise PlotGenerationError(f"Required plot input is missing: {csv_path}")
    frame = pd.read_csv(csv_path)
    missing_columns = [
        column for column in required_columns if column not in frame.columns
    ]
    if missing_columns:
        raise PlotGenerationError(
            f"{csv_path} is missing required column(s): {', '.join(missing_columns)}"
        )
    return frame.copy()


def _plot_decode_memory_consumption(
    *,
    results_df: pd.DataFrame,
    prefill_events_df: pd.DataFrame,
    decode_events_df: pd.DataFrame,
    model_constants_df: pd.DataFrame,
    success_rows: pd.DataFrame,
    trace_df: pd.DataFrame,
    timeline_df: pd.DataFrame,
    packed_timeline_df: pd.DataFrame,
    exemplar_row: pd.Series,
    plot5_chunk_selection: dict[str, int | None],
    plot_path: Path,
) -> None:
    """Revised-only: decode memory consumption scaling vs sequence length.

    X-axis: sequence length. Stacked components: pinned weights, decode workspace,
    bulk KV cache. Dashed line: VRAM ceiling.
    """
    del (
        prefill_events_df,
        decode_events_df,
        trace_df,
        timeline_df,
        packed_timeline_df,
        exemplar_row,
        plot5_chunk_selection,
    )

    # Build frame: group results by model_id and sequence_length choosing the
    # largest successful chunk_tokens per model to represent a stable chunk.
    if success_rows.empty:
        raise PlotGenerationError(
            "Decode memory consumption plot requires at least one successful result row"
        )

    # for each model pick a representative chunk_tokens (largest successful)
    representative_chunks = _select_plot5_chunk_tokens(success_rows)

    # prepare per-model panels
    models = [m for m in _FIXED_MODEL_ORDER if m in success_rows["model_id"].unique()]
    if not models:
        models = sorted(success_rows["model_id"].unique(), key=_model_sort_value)

    # build a mapping of kv_bytes_per_token_all_layers
    kv_map = {}
    if "kv_bytes_per_token_all_layers" in model_constants_df.columns:
        kv_map = dict(
            zip(
                model_constants_df["model_id"].astype(str),
                model_constants_df["kv_bytes_per_token_all_layers"],
            )
        )

    with _apply_plot_style(width=17.0, height=3.8):
        fig, axes = plt.subplots(1, len(models), sharey=True)
        axes_list = axes.ravel().tolist() if hasattr(axes, "ravel") else [axes]

        for axis, model_id in zip(axes_list, models):
            sel_chunk = representative_chunks.get(model_id)
            axis.set_title(_short_model_label(model_id))
            axis.set_xlabel("Sequence length")
            axis.set_axisbelow(True)

            model_rows = success_rows[success_rows["model_id"] == model_id].copy()
            if sel_chunk is not None:
                model_rows = model_rows[model_rows["chunk_tokens"] == sel_chunk]
            model_rows = model_rows.dropna(subset=["sequence_length"]).sort_values(
                "sequence_length"
            )
            if model_rows.empty:
                axis.text(
                    0.5,
                    0.5,
                    "No successful\nconfiguration",
                    ha="center",
                    va="center",
                    transform=axis.transAxes,
                )
                axis.set_xticks([])
                continue

            seqs = model_rows["sequence_length"].astype(int).tolist()
            # components in bytes
            weight_bytes = (
                (
                    model_rows["weight_bytes"]
                    if "weight_bytes" in model_rows.columns
                    else pd.Series(0, index=model_rows.index)
                )
                .fillna(0)
                .astype(float)
            )
            if "decode_workspace_bytes" in model_rows.columns:
                decode_workspace = (
                    model_rows["decode_workspace_bytes"].fillna(0).astype(float)
                )
            else:
                decode_workspace_columns = [
                    column
                    for column in model_rows.columns
                    if column.startswith("decode_workspace_bytes_vram_sm")
                ]
                if decode_workspace_columns:
                    decode_workspace = (
                        model_rows[decode_workspace_columns]
                        .apply(pd.to_numeric, errors="coerce")
                        .max(axis=1)
                        .fillna(0.0)
                        .astype(float)
                    )
                else:
                    decode_workspace = pd.Series(0.0, index=model_rows.index)
            kv_per_token = kv_map.get(model_id, None)
            if (
                kv_per_token is None
                and "kv_bytes_per_token_all_layers" in model_rows.columns
            ):
                kv_per_token = model_rows["kv_bytes_per_token_all_layers"].iloc[0]
            bulk_kv = (
                model_rows["sequence_length"].astype(float) * float(kv_per_token)
                if kv_per_token is not None
                else pd.Series(0.0, index=model_rows.index)
            )

            weights_gib = weight_bytes / _BYTES_PER_GIB
            workspace_gib = decode_workspace / _BYTES_PER_GIB
            bulk_kv_gib = bulk_kv / _BYTES_PER_GIB
            limit_gib = (
                model_rows["vram_ceiling_bytes"]
                if "vram_ceiling_bytes" in model_rows.columns
                else pd.Series(0, index=model_rows.index)
            ).fillna(0).astype(float) / _BYTES_PER_GIB

            axis.stackplot(
                seqs,
                weights_gib,
                workspace_gib,
                bulk_kv_gib,
                colors=(
                    _STACK_COLORS["Weights"],
                    _STACK_COLORS["Prefill workspace"],
                    _STACK_COLORS["Bulk KV cache"],
                ),
                labels=("Pinned weights", "Decode workspace", "Bulk KV cache"),
                alpha=0.78,
            )
            # draw dashed VRAM ceiling
            axis.plot(
                seqs,
                limit_gib,
                color=_STACK_COLORS.get("60% VRAM limit", "#C43C5B"),
                linestyle="--",
                linewidth=1.6,
                label="Physical VRAM limit",
            )

            axis.set_xticks(seqs)
            axis.set_ylim(bottom=0)
            axis.set_ylabel("VRAM footprint (GiB)")
            axis.legend(ncol=1, loc="upper left")

        fig.suptitle(
            "Decode memory consumption scaling vs. sequence length (revised)", y=1.08
        )
        fig.tight_layout()
        _save_figure(fig, plot_path)


def _normalize_results_frame(results_df: pd.DataFrame) -> pd.DataFrame:
    normalized = results_df.copy()
    numeric_columns = (
        "chunk_tokens",
        "sequence_length",
        "weight_bytes",
        "vram_ceiling_bytes",
        "prefill_max_gemm_us",
        "prefill_workspace_bytes",
        "prefill_parked_activation_bytes",
        "decode_runway_tokens",
        "ttft_ms",
        "tpot_ms_vram",
        "tpot_ms_pcie_async",
    )
    for column in numeric_columns:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    normalized["status"] = (
        normalized["status"].fillna("").astype(str).str.strip().str.lower()
    )
    return normalized


def _normalize_prefill_events_frame(prefill_events_df: pd.DataFrame) -> pd.DataFrame:
    normalized = prefill_events_df.copy()
    if "timed_iteration" not in normalized.columns:
        normalized["timed_iteration"] = 0
    numeric_columns = (
        "chunk_tokens",
        "timed_iteration",
        "duration_us",
        "dynamic_workspace_bytes",
    )
    for column in numeric_columns:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    normalized["model_id"] = normalized["model_id"].astype(str)
    normalized["op_name"] = normalized["op_name"].fillna("").astype(str).str.strip()
    if "op_type" not in normalized.columns:
        normalized["op_type"] = "gemm"
    normalized["op_type"] = (
        normalized["op_type"].fillna("gemm").astype(str).str.strip().str.lower()
    )
    if "sm_ai_partition" not in normalized.columns:
        normalized["sm_ai_partition"] = 100
    normalized["sm_ai_partition"] = pd.to_numeric(
        normalized["sm_ai_partition"], errors="coerce"
    ).fillna(100)
    return normalized


def _normalize_decode_events_frame(decode_events_df: pd.DataFrame) -> pd.DataFrame:
    normalized = decode_events_df.copy()
    if "timed_iteration" not in normalized.columns:
        normalized["timed_iteration"] = 0
    numeric_columns = (
        "sequence_length",
        "block_size",
        "timed_iteration",
        "duration_us",
        "dynamic_workspace_bytes",
    )
    for column in numeric_columns:
        if column in normalized.columns:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    normalized["model_id"] = normalized["model_id"].astype(str)
    if "op_name" not in normalized.columns:
        normalized["op_name"] = ""
    normalized["op_name"] = normalized["op_name"].fillna("").astype(str).str.strip()
    normalized["op_type"] = (
        normalized["op_type"].fillna("").astype(str).str.strip().str.lower()
    )
    if "sm_ai_partition" not in normalized.columns:
        normalized["sm_ai_partition"] = 100
    normalized["sm_ai_partition"] = pd.to_numeric(
        normalized["sm_ai_partition"], errors="coerce"
    ).fillna(100)
    return normalized


def _normalize_model_constants_frame(model_constants_df: pd.DataFrame) -> pd.DataFrame:
    normalized = model_constants_df.copy()
    normalized["model_id"] = normalized["model_id"].astype(str)

    if "kv_bytes_per_token_all_layers" not in normalized.columns:
        missing_fallback_columns = [
            column
            for column in _MODEL_CONSTANTS_KV_FALLBACK_COLUMNS
            if column not in normalized.columns
        ]
        if missing_fallback_columns:
            raise PlotGenerationError(
                "model_constants.csv must include kv_bytes_per_token_all_layers "
                "or enough data to derive it from hidden_size and num_hidden_layers"
            )
        hidden_size_values = pd.to_numeric(
            normalized["hidden_size"],
            errors="coerce",
        ).fillna(0)
        num_hidden_layers_values = pd.to_numeric(
            normalized["num_hidden_layers"],
            errors="coerce",
        ).fillna(0)
        normalized["kv_bytes_per_token_all_layers"] = [
            int(hidden_size)
            * int(num_hidden_layers)
            * simulator._KV_BYTES_PER_HIDDEN_VALUE
            for hidden_size, num_hidden_layers in zip(
                hidden_size_values.tolist(),
                num_hidden_layers_values.tolist(),
            )
        ]
    else:
        normalized["kv_bytes_per_token_all_layers"] = pd.to_numeric(
            normalized["kv_bytes_per_token_all_layers"],
            errors="coerce",
        )
    return normalized


def _normalize_timeline_frame(timeline_df: pd.DataFrame) -> pd.DataFrame:
    normalized = timeline_df.copy()
    numeric_columns = (
        "chunk_tokens",
        "sequence_length",
        "start_time_ms",
        "end_time_ms",
    )
    for column in numeric_columns:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    normalized["model_id"] = normalized["model_id"].astype(str)
    normalized["phase"] = (
        normalized["phase"].fillna("").astype(str).str.strip().str.lower()
    )
    normalized["mode"] = (
        normalized["mode"].fillna("").astype(str).str.strip().str.lower()
    )
    return normalized


def _normalize_packed_timeline_frame(timeline_df: pd.DataFrame) -> pd.DataFrame:
    normalized = _normalize_timeline_frame(timeline_df)
    normalized["schedule_variant"] = (
        normalized["schedule_variant"].fillna("").astype(str).str.strip().str.lower()
    )
    normalized["task_id"] = pd.to_numeric(normalized["task_id"], errors="coerce")
    return normalized


def _normalize_trace_frame(trace_df: pd.DataFrame) -> pd.DataFrame:
    normalized = trace_df.copy()
    normalized["time_ms"] = pd.to_numeric(normalized["time_ms"], errors="coerce")
    normalized["sm_utilization"] = pd.to_numeric(
        normalized["sm_utilization"], errors="coerce"
    )
    normalized["slot_duration_ms"] = pd.to_numeric(
        normalized["slot_duration_ms"], errors="coerce"
    )
    if "sm_count" in normalized.columns:
        normalized["sm_count"] = pd.to_numeric(normalized["sm_count"], errors="coerce")
    normalized["end_time_ms"] = normalized["time_ms"] + normalized["slot_duration_ms"]
    return normalized


def _select_success_rows(results_df: pd.DataFrame) -> pd.DataFrame:
    success_rows = results_df[results_df["status"] == _SUCCESS_STATUS].copy()
    if success_rows.empty:
        raise PlotGenerationError(
            "Plot generation requires at least one successful simulation result row"
        )
    return success_rows


def _select_exemplar_row(success_rows: pd.DataFrame) -> pd.Series:
    sortable_rows = success_rows.dropna(
        subset=["ttft_ms", "chunk_tokens", "sequence_length"]
    ).copy()
    if sortable_rows.empty:
        raise PlotGenerationError(
            "Deterministic exemplar selection requires successful rows with ttft_ms, chunk_tokens, and sequence_length"
        )

    sortable_rows["__model_rank"] = sortable_rows["model_id"].map(_model_size_rank)
    sorted_rows = sortable_rows.sort_values(
        by=["ttft_ms", "__model_rank", "chunk_tokens", "sequence_length"],
        ascending=[True, False, False, False],
        kind="mergesort",
    )
    return sorted_rows.iloc[0].copy()


def _select_plot5_chunk_tokens(success_rows: pd.DataFrame) -> dict[str, int | None]:
    selections: dict[str, int | None] = {}
    for model_id in _FIXED_MODEL_ORDER:
        model_rows = success_rows[success_rows["model_id"] == model_id]
        if model_rows.empty:
            selections[model_id] = None
            continue
        selections[model_id] = int(model_rows["chunk_tokens"].max())
    return selections


def _build_plot_selection_payload(
    *,
    exemplar_row: pd.Series,
    plot5_chunk_selection: dict[str, int | None],
) -> dict[str, Any]:
    return {
        "plot_01_selection_rule": {
            "source": simulator.SIMULATION_RESULTS_FILENAME,
            "status_filter": _SUCCESS_STATUS,
            "sort_order": [
                "ttft_ms ASC",
                "model_size_rank DESC",
                "chunk_tokens DESC",
                "sequence_length DESC",
            ],
        },
        "plot_01_exemplar": {
            "model_id": str(exemplar_row["model_id"]),
            "model_label": _short_model_label(str(exemplar_row["model_id"])),
            "model_size_rank": _model_size_rank(str(exemplar_row["model_id"])),
            "chunk_tokens": int(exemplar_row["chunk_tokens"]),
            "sequence_length": int(exemplar_row["sequence_length"]),
            "ttft_ms": float(exemplar_row["ttft_ms"]),
        },
        "plot_01_packed_timeline": {
            "source": simulator.PACKED_EXEMPLAR_TIMELINE_FILENAME,
            "task_id_field": "task_id",
            "schedule_variant_field": "schedule_variant",
            "policy": "repeat the selected exemplar task queue until the shared idle-gap trace is exhausted",
        },
        "plot_05_selection_rule": {
            "source": simulator.SIMULATION_RESULTS_FILENAME,
            "status_filter": _SUCCESS_STATUS,
            "policy": "largest successful chunk_tokens per fixed model",
        },
        "plot_05_largest_successful_chunk_by_model": [
            {
                "model_id": model_id,
                "model_label": _short_model_label(model_id),
                "selected_chunk_tokens": chunk_tokens,
            }
            for model_id, chunk_tokens in plot5_chunk_selection.items()
        ],
    }


def _write_plot_selection_metadata(
    selection_path: Path, *, payload: dict[str, Any]
) -> None:
    selection_path.parent.mkdir(parents=True, exist_ok=True)
    selection_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _remove_noncanonical_pngs(plots_root: Path) -> None:
    run_manifest_path = plots_root.parent / "run_manifest.json"
    use_revised_plots = False
    if run_manifest_path.exists():
        try:
            manifest = manifests.load_run_manifest(run_manifest_path)
            use_revised_plots = (
                manifest.get("schema_version")
                == experiments.RAN_DGXSPARK_V1_SCHEMA_VERSION
                or manifest.get("experiment_type")
                == experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE
            )
        except Exception:
            use_revised_plots = False
    expected_names = set(
        f"revised_{name}" if use_revised_plots else name for name in PLOT_FILENAMES
    )
    if use_revised_plots:
        expected_names.update(
            {
                "revised_07_hardware_utilization_profiling.png",
                "revised_08_decode_memory_consumption.png",
                "revised_09_prefill_vram_composition_pie.png",
                "revised_10_hardware_utilization_heatmap_acu.png",
                "revised_11_hardware_utilization_heatmap_gbu.png",
                "revised_12_hardware_utilization_heatmap_smu.png",
                "revised_13_hardware_utilization_heatmap_gpu_util.png",
                "revised_14_ttft_vs_runway_no_schedule.png",
                "revised_15_decode_tpot_degradation_no_schedule.png",
            }
        )
    for existing_png in plots_root.glob("*.png"):
        if existing_png.name not in expected_names:
            existing_png.unlink()


def _save_figure(fig: Figure, plot_path: Path) -> None:
    plot_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        plot_path,
        dpi=200,
        bbox_inches="tight",
        pad_inches=0.08,
        metadata=_PNG_SAVE_METADATA,
    )
    fig.savefig(plot_path.with_suffix(".pdf"), bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    if not plot_path.exists():
        raise PlotGenerationError(f"Matplotlib did not emit a plot file: {plot_path}")
    if plot_path.read_bytes()[: len(_PNG_SIGNATURE)] != _PNG_SIGNATURE:
        raise PlotGenerationError(
            f"Matplotlib did not emit a valid PNG file: {plot_path}"
        )


def _emit_interactive_ran_trace(
    *,
    trace_df: pd.DataFrame,
    exemplar_timeline: pd.DataFrame,
    packed_timeline: pd.DataFrame,
    exemplar_row: pd.Series,
    left: float,
    right: float,
    prefill_completion_trace_ms: float,
    interactive_path: Path,
) -> None:
    """Emit a self-contained Plotly HTML timeline that mirrors the PNG for plot 01.

    This is a companion artifact and must not replace the canonical PNG output.
    """
    if go is None:
        raise PlotGenerationError(
            "Plotly is required to generate the interactive RAN trace companion; install plotly>=5.0.0"
        )
    if plotly_subplots is None:
        raise PlotGenerationError(
            "Plotly subplots are required to generate the interactive RAN trace companion"
        )

    if not packed_timeline.empty:
        _emit_packed_interactive_ran_trace(
            trace_df=trace_df,
            packed_timeline=packed_timeline,
            exemplar_row=exemplar_row,
            left=left,
            right=right,
            prefill_completion_trace_ms=prefill_completion_trace_ms,
            interactive_path=interactive_path,
        )
        return

    plotly_go = cast(Any, go)

    trace_x, trace_y, y_is_count = _build_trace_step_series(trace_df)
    rel_x = [x - left for x in trace_x]

    fig = plotly_go.Figure()
    fig.add_trace(
        plotly_go.Scatter(
            x=rel_x,
            y=trace_y,
            mode="lines",
            line=dict(shape="hv", color=_TRACE_COLOR),
            name=("RAN trace (SM count)" if y_is_count else "Normalized RAN trace"),
        )
    )

    # Add timeline intervals as rectangles.
    # Prefer lane-assigned packed timelines when present in the exemplar_timeline
    # Dataframe field names that indicate packed lane assignment include
    # 'lane', 'lane_id', or 'task_lane'. Fall back to merged-phase intervals.
    lane_field = None
    for cand in ("lane", "lane_id", "task_lane"):
        if cand in exemplar_timeline.columns:
            lane_field = cand
            break

    lane_y: dict[str, float] = {}
    lane_height = 0.8

    if lane_field is not None:
        # Use explicit lanes from the packed timeline. Expect rows with start_time_ms/end_time_ms
        # and a lane identifier. Lane identifiers may be numeric or string.
        # Order lanes by their numeric value when possible, otherwise by first-seen ordering.
        lanes_order = []
        # build mapping of lane -> list of intervals
        lane_intervals: dict[str, list[tuple[float, float, str]]] = {}
        for row in exemplar_timeline.itertuples(index=False):
            lane_val = str(getattr(row, lane_field))
            start_ms = float(getattr(row, "start_time_ms"))
            end_ms = float(getattr(row, "end_time_ms"))
            if end_ms <= start_ms:
                continue
            lane_intervals.setdefault(lane_val, []).append(
                (
                    start_ms,
                    end_ms,
                    _timeline_label(phase=str(row.phase), mode=str(row.mode)),
                )
            )
            if lane_val not in lanes_order:
                lanes_order.append(lane_val)

        # order by numeric if possible
        try:
            lanes_order = sorted(lanes_order, key=lambda v: int(v))
        except Exception:
            # keep insertion order
            pass

        for idx, lane in enumerate(lanes_order):
            lane_y[lane] = idx * (lane_height + 0.2)
            for start_ms, end_ms, label in lane_intervals.get(lane, []):
                start_rel = max(start_ms, left) - left
                end_rel = min(end_ms, right) - left
                if end_rel <= start_rel:
                    continue
                color = _INTERVAL_COLORS.get(label, "#9AA5B1")
                fig.add_shape(
                    type="rect",
                    x0=start_rel,
                    x1=end_rel,
                    y0=lane_y[lane],
                    y1=lane_y[lane] + lane_height,
                    fillcolor=color,
                    opacity=0.6,
                    line_width=0,
                )
            # annotate lane with lane id on left
            fig.add_annotation(
                x=left - left * 0.01 if left != 0 else 0,
                y=lane_y[lane] + lane_height / 2.0,
                xanchor="right",
                text=lane,
                showarrow=False,
                font=dict(size=10),
            )
    else:
        # Fall back to merged-phase intervals (legacy behaviour)
        merged = _merged_timeline_intervals(exemplar_timeline)
        for i, (label, start_ms, end_ms) in enumerate(merged):
            # compute lane index by unique labels ordering
            if label not in lane_y:
                lane_y[label] = len(lane_y) * (lane_height + 0.2)
            start_rel = max(start_ms, left) - left
            end_rel = min(end_ms, right) - left
            if end_rel <= start_rel:
                continue
            color = _INTERVAL_COLORS.get(label, "#9AA5B1")
            fig.add_shape(
                type="rect",
                x0=start_rel,
                x1=end_rel,
                y0=lane_y[label],
                y1=lane_y[label] + lane_height,
                fillcolor=color,
                opacity=0.6,
                line_width=0,
            )
            fig.add_annotation(
                x=max(start_rel, left - 0.01 * (right - left)),
                y=lane_y[label] + lane_height / 2.0,
                xanchor="right",
                text=label,
                showarrow=False,
                font=dict(size=10),
            )

    # TTFT vertical marker
    ttft_ms = float(exemplar_row["ttft_ms"])
    rel_ttft = prefill_completion_trace_ms - left
    fig.add_vline(
        x=rel_ttft,
        line=dict(color=_TTFT_COLOR, dash="dash"),
        annotation_text=f"TTFT = {ttft_ms:.2f} ms",
        annotation_position="top right",
    )

    fig.update_layout(
        title=(
            "RAN trace interleaving exemplar · "
            f"{_short_model_label(str(exemplar_row['model_id']))} · N={int(exemplar_row['chunk_tokens'])} · L={int(exemplar_row['sequence_length'])}"
        ),
        xaxis_title="Relative trace time (ms)",
        yaxis_title=("Active SMs" if y_is_count else "RAN state"),
        showlegend=False,
        height=600,
    )

    interactive_path.parent.mkdir(parents=True, exist_ok=True)
    # embed Plotly JS so file is self-contained for offline viewing
    fig.write_html(
        interactive_path,
        include_plotlyjs=True,
        full_html=True,
    )


def _emit_packed_interactive_ran_trace(
    *,
    trace_df: pd.DataFrame,
    packed_timeline: pd.DataFrame,
    exemplar_row: pd.Series,
    left: float,
    right: float,
    prefill_completion_trace_ms: float,
    interactive_path: Path,
) -> None:
    plotly_go = cast(Any, go)
    make_subplots = cast(Any, plotly_subplots).make_subplots

    windowed_trace_df = _window_trace_frame(trace_df, left=left, right=right)
    trace_x, trace_y, y_is_count = _build_trace_step_series(windowed_trace_df)
    rel_trace_x = [x - left for x in trace_x]

    packed_timeline = _window_packed_timeline(
        packed_timeline,
        left=left,
        right=right,
    )

    variant_counts = _packed_task_counts(packed_timeline)
    if not variant_counts:
        raise PlotGenerationError(
            "Packed exemplar timeline must contain at least one packed task row"
        )
    variant_order = _ordered_schedule_variants(variant_counts)
    default_variant = variant_order[0]

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.35, 0.65],
        vertical_spacing=0.08,
    )
    fig.add_trace(
        plotly_go.Scatter(
            x=rel_trace_x,
            y=trace_y,
            mode="lines",
            line=dict(shape="hv", color=_TRACE_COLOR),
            name=("RAN trace (SM count)" if y_is_count else "Normalized RAN trace"),
            hovertemplate="Trace time %{x:.3f} ms<extra></extra>",
        ),
        row=1,
        col=1,
    )

    trace_indices_by_variant: dict[str, list[int]] = {}
    for schedule_variant in variant_order:
        variant_rows = packed_timeline[
            packed_timeline["schedule_variant"] == schedule_variant
        ].copy()
        for label, x_values, y_values, hover_text in _build_packed_task_trace_data(
            variant_rows,
            left=left,
            right=right,
        ):
            fig.add_trace(
                plotly_go.Scatter(
                    x=x_values,
                    y=y_values,
                    mode="lines",
                    line=dict(
                        color=_INTERVAL_COLORS.get(label, "#9AA5B1"),
                        width=11,
                    ),
                    name=label,
                    visible=(schedule_variant == default_variant),
                    hovertemplate="%{fullData.name}<br>Task %{y:.0f}<br>Relative trace time %{x:.3f} ms<extra></extra>",
                    text=hover_text,
                ),
                row=2,
                col=1,
            )
            trace_indices_by_variant.setdefault(schedule_variant, []).append(
                len(fig.data) - 1
            )

    first_task_prefill = packed_timeline[
        (packed_timeline["task_id"] == 0) & (packed_timeline["phase"] == "prefill")
    ]
    if not first_task_prefill.empty:
        prefill_completion_trace_ms = float(first_task_prefill["end_time_ms"].max())
    rel_ttft = prefill_completion_trace_ms - left
    fig.add_vline(
        x=rel_ttft,
        line=dict(color=_TTFT_COLOR, dash="dash"),
        annotation_text=f"TTFT = {float(exemplar_row['ttft_ms']):.2f} ms",
        annotation_position="top right",
        row=1,
        col=1,
    )

    max_task_count = max(variant_counts.values())
    y_tick_step = max(1, math.ceil(max_task_count / 12))
    fig.update_xaxes(title_text="Relative trace time (ms)", row=2, col=1)
    fig.update_yaxes(
        title_text=("Active SMs" if y_is_count else "RAN state"),
        row=1,
        col=1,
    )
    if not y_is_count:
        fig.update_yaxes(
            range=[-0.05, 1.05],
            tickmode="array",
            tickvals=[0.0, 1.0],
            ticktext=["Idle", "Busy"],
            row=1,
            col=1,
        )
    fig.update_yaxes(
        title_text="Packed exemplar task ID",
        autorange="reversed",
        tickmode="linear",
        tick0=0,
        dtick=y_tick_step,
        row=2,
        col=1,
    )
    fig.update_layout(
        title=_packed_interactive_title(
            exemplar_row=exemplar_row,
            schedule_variant=default_variant,
            task_count=variant_counts[default_variant],
        ),
        hovermode="closest",
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0.0,
        ),
        height=780,
    )
    fig.update_xaxes(range=[0.0, max(right - left, 1e-6)], row=1, col=1)
    fig.update_xaxes(range=[0.0, max(right - left, 1e-6)], row=2, col=1)

    if len(variant_order) > 1:
        button_specs = []
        total_trace_count = len(fig.data)
        for schedule_variant in variant_order:
            visible = [True] + [False] * (total_trace_count - 1)
            for trace_index in trace_indices_by_variant.get(schedule_variant, []):
                visible[trace_index] = True
            button_specs.append(
                {
                    "label": _packed_variant_button_label(
                        schedule_variant=schedule_variant,
                        task_count=variant_counts[schedule_variant],
                    ),
                    "method": "update",
                    "args": [
                        {"visible": visible},
                        {
                            "title": _packed_interactive_title(
                                exemplar_row=exemplar_row,
                                schedule_variant=schedule_variant,
                                task_count=variant_counts[schedule_variant],
                            )
                        },
                    ],
                }
            )
        fig.update_layout(
            updatemenus=[
                {
                    "buttons": button_specs,
                    "direction": "right",
                    "showactive": True,
                    "x": 0.0,
                    "xanchor": "left",
                    "y": 1.16,
                    "yanchor": "top",
                }
            ]
        )

    interactive_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(
        interactive_path,
        include_plotlyjs=True,
        full_html=True,
    )


def _ordered_models(model_ids: Sequence[Any]) -> list[str]:
    return sorted({str(model_id) for model_id in model_ids}, key=_model_sort_value)


def _model_sort_value(model_id: str) -> tuple[int, float, str]:
    if model_id in _FIXED_MODEL_ORDER:
        return (0, float(_FIXED_MODEL_ORDER.index(model_id)), model_id)
    return (1, -_model_size_rank(model_id), model_id)


def _model_size_rank(model_id: str) -> float:
    if model_id in _FIXED_MODEL_ORDER:
        return float(_FIXED_MODEL_ORDER.index(model_id) + 1)

    normalized = model_id.rsplit("/", 1)[-1]
    match = _MODEL_SIZE_RE.search(normalized)
    if match is None:
        return 0.0
    value = float(match.group("value"))
    unit = match.group("unit").lower()
    return value * 1_000.0 if unit == "b" else value


def _short_model_label(model_id: str) -> str:
    if model_id in _MODEL_LABELS:
        return _MODEL_LABELS[model_id]
    normalized = model_id.rsplit("/", 1)[-1]
    return normalized.replace("opt-", "OPT-").upper()


def _model_color(model_id: str) -> str:
    return _MODEL_COLORS.get(model_id, "#4F5D75")


def _analytical_partition_scale(sm_ai_partition: int | float) -> float:
    partition = float(sm_ai_partition)
    if partition <= 0:
        return 1.0
    return _ANALYTICAL_FULL_GPU_SM_COUNT / partition


def _filter_result_rows(
    frame: pd.DataFrame,
    *,
    model_id: str,
    chunk_tokens: int,
    sequence_length: int | None = None,
) -> pd.DataFrame:
    filtered = frame[
        (frame["model_id"] == model_id) & (frame["chunk_tokens"] == chunk_tokens)
    ]
    if sequence_length is not None:
        filtered = filtered[filtered["sequence_length"] == sequence_length]
    return filtered.copy()


def _timeline_label(*, phase: str, mode: str) -> str:
    if phase == "prefill":
        return "Prefill"
    if mode == "vram":
        return "Decode (VRAM)"
    if mode == "pcie_async":
        return "Decode (PCIe async)"
    return f"{phase.title()} ({mode})"


def _resolve_exemplar_num_hidden_layers(
    *,
    model_constants_df: pd.DataFrame,
    model_id: str,
) -> int | None:
    if "num_hidden_layers" not in model_constants_df.columns:
        return None
    matching_rows = model_constants_df[model_constants_df["model_id"] == model_id]
    if matching_rows.empty:
        return None
    values = pd.to_numeric(matching_rows["num_hidden_layers"], errors="coerce").dropna()
    if values.empty:
        return None
    return int(values.iloc[0])


def _ordered_schedule_variants(variant_counts: dict[str, int]) -> list[str]:
    preferred_order = {"pcie_async": 0, "vram": 1}
    return sorted(
        variant_counts,
        key=lambda schedule_variant: (
            -variant_counts[schedule_variant],
            preferred_order.get(schedule_variant, 99),
            schedule_variant,
        ),
    )


def _packed_task_counts(packed_timeline: pd.DataFrame) -> dict[str, int]:
    if packed_timeline.empty:
        return {}
    counts: dict[str, int] = {}
    for schedule_variant, variant_rows in packed_timeline.groupby(
        "schedule_variant", sort=False
    ):
        task_ids = pd.to_numeric(variant_rows["task_id"], errors="coerce").dropna()
        counts[str(schedule_variant)] = int(task_ids.nunique())
    return counts


def _build_packed_task_trace_data(
    packed_variant_df: pd.DataFrame,
    *,
    left: float,
    right: float,
) -> list[tuple[str, list[float | None], list[float | None], list[str | None]]]:
    trace_data: list[
        tuple[str, list[float | None], list[float | None], list[str | None]]
    ] = []
    if packed_variant_df.empty:
        return trace_data

    sortable = packed_variant_df.sort_values(
        by=["task_id", "start_time_ms", "end_time_ms", "phase", "mode"],
        kind="mergesort",
    )

    # Compact contiguous rows for the same task into larger spans to avoid
    # emitting atom-level shapes in the interactive HTML. Merge only when
    # consecutive rows have identical task_id, phase, mode, and trace_interval_index
    # and when there is no real gap between them (allow tiny epsilon).
    def _compact_rows(df: pd.DataFrame) -> list[dict[str, object]]:
        compacted: list[dict[str, object]] = []
        if df.empty:
            return compacted
        eps = _TIME_EPSILON_MS
        current = None
        for row in df.itertuples(index=False):
            task_id = int(float(cast(Any, row.task_id)))
            phase = str(row.phase)
            mode = str(row.mode)
            trace_idx = getattr(row, "trace_interval_index", None)
            start_ms = float(cast(Any, row.start_time_ms))
            end_ms = float(cast(Any, row.end_time_ms))
            duration_ms = (
                float(cast(Any, row.duration_ms))
                if hasattr(row, "duration_ms")
                else end_ms - start_ms
            )
            key = (task_id, phase, mode, trace_idx)
            if current is None:
                current = {
                    "task_id": task_id,
                    "phase": phase,
                    "mode": mode,
                    "trace_interval_index": trace_idx,
                    "start_time_ms": start_ms,
                    "end_time_ms": end_ms,
                    "duration_ms": duration_ms,
                }
                continue
            curr_key = (
                current["task_id"],
                current["phase"],
                current["mode"],
                current.get("trace_interval_index"),
            )
            # contiguous if same key and start <= current.end + eps
            if key == curr_key and start_ms <= current["end_time_ms"] + eps:
                # extend end and accumulate duration
                current["end_time_ms"] = max(current["end_time_ms"], end_ms)
                current["duration_ms"] = current.get("duration_ms", 0.0) + duration_ms
            else:
                compacted.append(current)
                current = {
                    "task_id": task_id,
                    "phase": phase,
                    "mode": mode,
                    "trace_interval_index": trace_idx,
                    "start_time_ms": start_ms,
                    "end_time_ms": end_ms,
                    "duration_ms": duration_ms,
                }
        if current is not None:
            compacted.append(current)
        return compacted

    compact_rows = _compact_rows(sortable)
    for label in ("Prefill", "Decode (VRAM)", "Decode (PCIe async)"):
        label_rows = sortable[
            sortable.apply(
                lambda row: _timeline_label(
                    phase=str(row["phase"]),
                    mode=str(row["mode"]),
                )
                == label,
                axis=1,
            )
        ]
        if label_rows.empty:
            continue
        x_values: list[float | None] = []
        y_values: list[float | None] = []
        hover_text: list[str | None] = []
        # iterate compacted spans instead of raw rows
        for span in compact_rows:
            # filter spans by label (phase/mode match)
            span_label = _timeline_label(phase=span["phase"], mode=span["mode"])
            if span_label != label:
                continue
            task_id = int(span["task_id"])
            start_time_ms = max(float(span["start_time_ms"]), left)
            end_time_ms = min(float(span["end_time_ms"]), right)
            if end_time_ms <= start_time_ms:
                continue
            x_values.extend([start_time_ms - left, end_time_ms - left, None])
            y_values.extend([float(task_id), float(task_id), None])
            hover_text.extend([None, None, None])
        trace_data.append((label, x_values, y_values, hover_text))
    return trace_data


def _window_trace_frame(
    trace_df: pd.DataFrame, *, left: float, right: float
) -> pd.DataFrame:
    windowed_rows = trace_df[
        (trace_df["time_ms"] < right) & (trace_df["end_time_ms"] > left)
    ].copy()
    if windowed_rows.empty:
        return trace_df.copy()
    windowed_rows["time_ms"] = windowed_rows["time_ms"].clip(lower=left, upper=right)
    windowed_rows["end_time_ms"] = windowed_rows["end_time_ms"].clip(
        lower=left, upper=right
    )
    return windowed_rows


def _window_packed_timeline(
    packed_timeline: pd.DataFrame,
    *,
    left: float,
    right: float,
) -> pd.DataFrame:
    windowed_rows = packed_timeline[
        (packed_timeline["start_time_ms"] < right)
        & (packed_timeline["end_time_ms"] > left)
    ].copy()
    if windowed_rows.empty:
        return packed_timeline.copy()
    return windowed_rows


def _packed_variant_button_label(*, schedule_variant: str, task_count: int) -> str:
    return f"{_packed_variant_label(schedule_variant)} · {task_count} tasks"


def _packed_variant_label(schedule_variant: str) -> str:
    if schedule_variant == "pcie_async":
        return "PCIe async packed queue"
    if schedule_variant == "vram":
        return "VRAM packed queue"
    return f"{schedule_variant} packed queue"


def _packed_interactive_title(
    *,
    exemplar_row: pd.Series,
    schedule_variant: str,
    task_count: int,
) -> str:
    return (
        "RAN trace interleaving exemplar · "
        f"{_short_model_label(str(exemplar_row['model_id']))} · "
        f"N={int(exemplar_row['chunk_tokens'])} · "
        f"L={int(exemplar_row['sequence_length'])} · "
        f"{_packed_variant_label(schedule_variant)} · {task_count} tasks"
    )


def _merged_timeline_intervals(
    timeline_df: pd.DataFrame,
) -> list[tuple[str, float, float]]:
    merged: dict[str, list[tuple[float, float]]] = {}
    sorted_rows = timeline_df.sort_values(
        by=["start_time_ms", "end_time_ms", "phase", "mode"], kind="mergesort"
    )
    for row in sorted_rows.itertuples(index=False):
        start_time_ms = float(row.start_time_ms)
        end_time_ms = float(row.end_time_ms)
        if end_time_ms <= start_time_ms:
            continue
        label = _timeline_label(phase=str(row.phase), mode=str(row.mode))
        bucket = merged.setdefault(label, [])
        if bucket and start_time_ms <= bucket[-1][1] + _TIME_EPSILON_MS:
            previous_start, previous_end = bucket[-1]
            bucket[-1] = (previous_start, max(previous_end, end_time_ms))
        else:
            bucket.append((start_time_ms, end_time_ms))

    merged_intervals: list[tuple[str, float, float]] = []
    for label in ("Prefill", "Decode (VRAM)", "Decode (PCIe async)"):
        for start_time_ms, end_time_ms in merged.get(label, []):
            merged_intervals.append((label, start_time_ms, end_time_ms))
    return merged_intervals


def _build_trace_step_series(
    trace_df: pd.DataFrame,
) -> tuple[list[float], list[float], bool]:
    sorted_rows = trace_df.sort_values(by=["time_ms", "end_time_ms"], kind="mergesort")
    trace_x: list[float] = []
    trace_y: list[float] = []
    use_sm_count = ("sm_count" in trace_df.columns) and bool(
        trace_df["sm_count"].notna().any()
    )
    for row in sorted_rows.itertuples(index=False):
        start_time_ms = float(row.time_ms)
        end_time_ms = float(row.end_time_ms)
        if use_sm_count:
            # prefer sm_count when present
            y_value = (
                float(row.sm_count)
                if getattr(row, "sm_count", None) is not None
                else 0.0
            )
        else:
            y_value = 1.0 if float(row.sm_utilization) > 0 else 0.0
        if not trace_x:
            trace_x.append(start_time_ms)
            trace_y.append(y_value)
        trace_x.append(end_time_ms)
        trace_y.append(y_value)
    return trace_x, trace_y, use_sm_count


def _average_idle_gap_ms(trace_df: pd.DataFrame) -> float:
    idle_rows = trace_df[trace_df["sm_utilization"] == 0].copy()
    if idle_rows.empty:
        return 0.0
    return float(idle_rows["slot_duration_ms"].mean())


def _build_prefill_vram_composition_frame(
    *,
    results_df: pd.DataFrame,
    model_constants_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    working = results_df.copy()
    if "bulk_kv_cache_bytes" in working.columns:
        working["bulk_kv_cache_bytes"] = pd.to_numeric(
            working["bulk_kv_cache_bytes"], errors="coerce"
        )
    else:
        working["bulk_kv_cache_bytes"] = float("nan")

    if "kv_bytes_per_token_all_layers" in working.columns:
        kv_series = pd.to_numeric(
            working["kv_bytes_per_token_all_layers"], errors="coerce"
        ).fillna(0.0)
        chunk_series = pd.to_numeric(working["chunk_tokens"], errors="coerce").fillna(
            0.0
        )
        derived_bulk = pd.Series(
            [
                max(0.0, float(chunk_tokens)) * float(kv_bytes)
                for chunk_tokens, kv_bytes in zip(
                    chunk_series.tolist(),
                    kv_series.tolist(),
                )
            ],
            index=working.index,
        )
        working["bulk_kv_cache_bytes"] = working["bulk_kv_cache_bytes"].fillna(
            derived_bulk
        )

    if model_constants_df is not None and not model_constants_df.empty:
        if "kv_bytes_per_token_all_layers" in model_constants_df.columns:
            constants = model_constants_df.copy()
            constants["kv_bytes_per_token_all_layers"] = pd.to_numeric(
                constants["kv_bytes_per_token_all_layers"], errors="coerce"
            )
            kv_lookup = dict(
                zip(
                    constants["model_id"].astype(str),
                    constants["kv_bytes_per_token_all_layers"],
                )
            )
            derived_bulk = [
                max(0.0, float(chunk_tokens))
                * float(kv_lookup.get(str(model_id), 0.0) or 0.0)
                for model_id, chunk_tokens in zip(
                    working["model_id"],
                    pd.to_numeric(working["chunk_tokens"], errors="coerce").fillna(0.0),
                )
            ]
            working["bulk_kv_cache_bytes"] = working["bulk_kv_cache_bytes"].fillna(
                pd.Series(derived_bulk, index=working.index)
            )

    composition_df = (
        working.groupby(["model_id", "chunk_tokens"], as_index=False)
        .agg(
            weight_bytes=("weight_bytes", "max"),
            bulk_kv_cache_bytes=("bulk_kv_cache_bytes", "max"),
            prefill_workspace_bytes=("prefill_workspace_bytes", "max"),
            prefill_parked_activation_bytes=("prefill_parked_activation_bytes", "max"),
            vram_ceiling_bytes=("vram_ceiling_bytes", "max"),
        )
        .sort_values(
            by=["model_id", "chunk_tokens"],
            key=lambda series: series.map(_model_sort_value)
            if series.name == "model_id"
            else series,
            kind="mergesort",
        )
        .reset_index(drop=True)
    )
    composition_df["bulk_kv_cache_bytes"] = pd.to_numeric(
        composition_df["bulk_kv_cache_bytes"], errors="coerce"
    ).fillna(0.0)
    return composition_df


def _build_prefill_safety_boundary_frame(results_df: pd.DataFrame) -> pd.DataFrame:
    working_results = results_df.copy()
    if "status" in working_results.columns:
        working_results = working_results[working_results["status"] == _SUCCESS_STATUS]

    is_revised = "experiment_type" in working_results.columns and (
        working_results["experiment_type"]
        .astype(str)
        .str.strip()
        .str.lower()
        .eq(experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE)
        .any()
    )

    if is_revised:
        fallback_df = working_results.groupby(
            ["model_id", "chunk_tokens"], as_index=False
        ).agg(prefill_max_gemm_us=("prefill_max_gemm_us", "max"))
        synthetic_rows: list[dict[str, float | int | str]] = []
        for _, row in fallback_df.iterrows():
            base_duration_us = pd.to_numeric(
                row.get("prefill_max_gemm_us"), errors="coerce"
            )
            chunk_tokens_value = pd.to_numeric(row.get("chunk_tokens"), errors="coerce")
            if bool(pd.isna(base_duration_us)) or bool(pd.isna(chunk_tokens_value)):
                continue
            base_duration_us = float(base_duration_us)
            chunk_tokens = int(float(chunk_tokens_value))
            for partition in experiments.RAN_DGXSPARK_V1_SM_AI_PARTITIONS:
                synthetic_rows.append(
                    {
                        "model_id": str(row.get("model_id")),
                        "chunk_tokens": chunk_tokens,
                        "sm_ai_partition": int(partition),
                        "prefill_max_gemm_us": base_duration_us
                        * _analytical_partition_scale(partition),
                    }
                )
        synthetic_df = pd.DataFrame(synthetic_rows)
        if synthetic_df.empty:
            return synthetic_df
        return synthetic_df.sort_values(
            by=["model_id", "chunk_tokens", "sm_ai_partition"],
            key=lambda series: series.map(_model_sort_value)
            if series.name == "model_id"
            else series,
            kind="mergesort",
        ).reset_index(drop=True)

    partitioned_columns = [
        column
        for column in working_results.columns
        if column.startswith("prefill_max_gemm_us_sm")
    ]
    if not partitioned_columns:
        fallback_df = working_results.groupby(
            ["model_id", "chunk_tokens"], as_index=False
        ).agg(prefill_max_gemm_us=("prefill_max_gemm_us", "max"))
        if not is_revised:
            fallback_df = fallback_df.assign(sm_ai_partition=100)
            return fallback_df.sort_values(
                by=["model_id", "chunk_tokens", "sm_ai_partition"],
                key=lambda series: series.map(_model_sort_value)
                if series.name == "model_id"
                else series,
                kind="mergesort",
            ).reset_index(drop=True)

        synthetic_rows: list[dict[str, float | int | str]] = []
        for _, row in fallback_df.iterrows():
            base_duration_us = pd.to_numeric(
                row.get("prefill_max_gemm_us"), errors="coerce"
            )
            chunk_tokens_value = pd.to_numeric(row.get("chunk_tokens"), errors="coerce")
            if bool(pd.isna(base_duration_us)) or bool(pd.isna(chunk_tokens_value)):
                continue
            base_duration_us = float(base_duration_us)
            chunk_tokens = int(float(chunk_tokens_value))
            for partition in experiments.RAN_DGXSPARK_V1_SM_AI_PARTITIONS:
                synthetic_rows.append(
                    {
                        "model_id": str(row.get("model_id")),
                        "chunk_tokens": chunk_tokens,
                        "sm_ai_partition": int(partition),
                        "prefill_max_gemm_us": base_duration_us
                        * _analytical_partition_scale(partition),
                    }
                )
        synthetic_df = pd.DataFrame(synthetic_rows)
        if synthetic_df.empty:
            return synthetic_df
        return synthetic_df.sort_values(
            by=["model_id", "chunk_tokens", "sm_ai_partition"],
            key=lambda series: series.map(_model_sort_value)
            if series.name == "model_id"
            else series,
            kind="mergesort",
        ).reset_index(drop=True)

    rows: list[dict[str, float | int | str]] = []
    for _, row in working_results.iterrows():
        model_id = str(row.get("model_id"))
        chunk_value = pd.to_numeric(row.get("chunk_tokens"), errors="coerce")
        if bool(pd.isna(chunk_value)):
            continue
        chunk_tokens = int(float(chunk_value))
        for column in partitioned_columns:
            value = pd.to_numeric(row.get(column), errors="coerce")
            if bool(pd.isna(value)):
                continue
            partition_suffix = column.removeprefix("prefill_max_gemm_us_sm")
            partition = int(partition_suffix)
            rows.append(
                {
                    "model_id": model_id,
                    "chunk_tokens": chunk_tokens,
                    "sm_ai_partition": partition,
                    "prefill_max_gemm_us": float(value),
                }
            )

    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return (
        frame.groupby(["model_id", "chunk_tokens", "sm_ai_partition"], as_index=False)
        .agg(prefill_max_gemm_us=("prefill_max_gemm_us", "max"))
        .sort_values(
            by=["model_id", "chunk_tokens", "sm_ai_partition"],
            key=lambda series: series.map(_model_sort_value)
            if series.name == "model_id"
            else series,
            kind="mergesort",
        )
        .reset_index(drop=True)
    )


def _build_ttft_tradeoff_rows(
    results_df: pd.DataFrame,
    *,
    ttft_column: str = "ttft_ms",
) -> pd.DataFrame:
    candidates = (
        results_df[results_df["status"] == _SUCCESS_STATUS]
        .dropna(subset=[ttft_column, "chunk_tokens", "sequence_length"])
        .copy()
    )
    if candidates.empty:
        return candidates

    selected_rows: list[pd.Series] = []
    for _, group in candidates.groupby(["model_id", "chunk_tokens"], sort=False):
        sorted_group = group.sort_values(
            by=["sequence_length"],
            ascending=[False],
            kind="mergesort",
        )
        selected_rows.append(sorted_group.iloc[0])

    tradeoff_df = pd.DataFrame(selected_rows).copy()
    ttft_ms_series = cast(
        pd.Series,
        pd.to_numeric(tradeoff_df[ttft_column], errors="coerce").fillna(0.0),
    )
    decode_runway_bytes_series = cast(
        pd.Series,
        pd.to_numeric(tradeoff_df["decode_runway_bytes"], errors="coerce").fillna(0.0),
    )
    tradeoff_df["ttft_s"] = ttft_ms_series / 1000.0
    tradeoff_df["decode_runway_gib"] = decode_runway_bytes_series / _BYTES_PER_GIB
    return tradeoff_df.sort_values(
        by=["model_id", "chunk_tokens"],
        key=lambda series: series.map(_model_sort_value)
        if series.name == "model_id"
        else series,
        kind="mergesort",
    ).reset_index(drop=True)


def _build_no_schedule_latency_frame(
    *,
    results_df: pd.DataFrame,
    model_constants_df: pd.DataFrame,
) -> pd.DataFrame:
    if results_df.empty:
        return results_df.copy()

    frame = results_df.copy()
    hidden_layer_map: dict[str, int] = {}
    if "num_hidden_layers" in model_constants_df.columns:
        for _, row in model_constants_df.iterrows():
            value = pd.to_numeric(row.get("num_hidden_layers"), errors="coerce")
            if bool(pd.isna(value)):
                continue
            hidden_layer_map[str(row.get("model_id"))] = int(value)

    frame["num_hidden_layers_for_no_schedule"] = [
        hidden_layer_map.get(str(model_id), 0)
        for model_id in frame["model_id"].tolist()
    ]
    numeric_columns = [
        "chunk_tokens",
        "sequence_length",
        "prefill_max_gemm_us",
        "decode_max_gemv_us",
        "attention_fetch_compute_us",
        "reduction_overhead_us",
        "pcie_exposed_us",
    ]
    for column in numeric_columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["num_hidden_layers_for_no_schedule"] = pd.to_numeric(
        frame["num_hidden_layers_for_no_schedule"], errors="coerce"
    )

    prompt_tokens = float(getattr(simulator, "_PROMPT_TOKEN_COUNT", 4096))
    prefill_atoms_per_layer = float(getattr(simulator, "_PREFILL_ATOMS_PER_LAYER", 6))
    decode_gemv_atoms_per_layer = float(
        getattr(simulator, "_DECODE_GEMV_ATOMS_PER_LAYER", 6)
    )
    frame["chunk_count_for_no_schedule"] = (
        prompt_tokens / frame["chunk_tokens"].replace(0, np.nan)
    ).apply(np.ceil)
    frame["decode_transfer_atom_count_for_no_schedule"] = (
        frame["sequence_length"] / frame["chunk_tokens"].replace(0, np.nan)
    ).apply(np.ceil)

    prefill_atom_ms = frame["prefill_max_gemm_us"] / 1000.0
    decode_gemv_ms = frame["decode_max_gemv_us"] / 1000.0
    attention_ms = frame["attention_fetch_compute_us"] / 1000.0
    reduction_ms = frame["reduction_overhead_us"] / 1000.0
    pcie_ms = frame["pcie_exposed_us"] / 1000.0

    frame["ttft_ms_nosched"] = (
        frame["chunk_count_for_no_schedule"]
        * frame["num_hidden_layers_for_no_schedule"]
        * prefill_atoms_per_layer
        * prefill_atom_ms
    )
    frame["tpot_ms_vram_nosched"] = frame["num_hidden_layers_for_no_schedule"] * (
        (decode_gemv_atoms_per_layer * decode_gemv_ms) + attention_ms + reduction_ms
    )
    frame["tpot_ms_pcie_async_nosched"] = frame["num_hidden_layers_for_no_schedule"] * (
        (decode_gemv_atoms_per_layer * decode_gemv_ms)
        + attention_ms
        + reduction_ms
        + (frame["decode_transfer_atom_count_for_no_schedule"] * pcie_ms)
    )
    for column in (
        "ttft_ms_nosched",
        "tpot_ms_vram_nosched",
        "tpot_ms_pcie_async_nosched",
    ):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame[column] = frame[column].where(frame[column] >= 0)
    return frame


def _build_ttft_no_schedule_partition_frame(
    *,
    results_df: pd.DataFrame,
    model_constants_df: pd.DataFrame,
) -> pd.DataFrame:
    prefill_partition_df = _build_prefill_safety_boundary_frame(results_df)
    if prefill_partition_df.empty:
        return pd.DataFrame(
            columns=[
                "model_id",
                "chunk_tokens",
                "sm_ai_partition",
                "ttft_ms_nosched",
                "ttft_s_nosched",
            ]
        )

    hidden_layer_map: dict[str, int] = {}
    if "num_hidden_layers" in model_constants_df.columns:
        for _, row in model_constants_df.iterrows():
            value = pd.to_numeric(row.get("num_hidden_layers"), errors="coerce")
            if bool(pd.isna(value)):
                continue
            hidden_layer_map[str(row.get("model_id"))] = int(value)

    prompt_tokens = float(getattr(simulator, "_PROMPT_TOKEN_COUNT", 4096))
    prefill_atoms_per_layer = float(getattr(simulator, "_PREFILL_ATOMS_PER_LAYER", 6))
    frame = prefill_partition_df.copy()
    frame["chunk_tokens"] = pd.to_numeric(frame["chunk_tokens"], errors="coerce")
    frame["prefill_max_gemm_us"] = pd.to_numeric(
        frame["prefill_max_gemm_us"], errors="coerce"
    )
    frame = frame.dropna(subset=["chunk_tokens", "prefill_max_gemm_us"])
    frame["num_hidden_layers"] = [
        hidden_layer_map.get(str(model_id), 0)
        for model_id in frame["model_id"].tolist()
    ]
    frame["num_hidden_layers"] = pd.to_numeric(
        frame["num_hidden_layers"], errors="coerce"
    )
    frame = frame[frame["num_hidden_layers"] > 0]
    if frame.empty:
        return pd.DataFrame(
            columns=[
                "model_id",
                "chunk_tokens",
                "sm_ai_partition",
                "ttft_ms_nosched",
                "ttft_s_nosched",
            ]
        )
    frame["chunk_count"] = (
        prompt_tokens / frame["chunk_tokens"].replace(0, np.nan)
    ).apply(np.ceil)
    frame["ttft_ms_nosched"] = (
        frame["chunk_count"]
        * frame["num_hidden_layers"]
        * prefill_atoms_per_layer
        * (frame["prefill_max_gemm_us"] / 1000.0)
    )
    frame["ttft_s_nosched"] = frame["ttft_ms_nosched"] / 1000.0
    frame["chunk_tokens"] = frame["chunk_tokens"].astype(int)
    frame["sm_ai_partition"] = (
        pd.to_numeric(frame["sm_ai_partition"], errors="coerce").fillna(100).astype(int)
    )
    return frame[
        [
            "model_id",
            "chunk_tokens",
            "sm_ai_partition",
            "ttft_ms_nosched",
            "ttft_s_nosched",
        ]
    ]


def _build_tpot_partition_frame(
    *,
    results_df: pd.DataFrame,
    model_constants_df: pd.DataFrame,
) -> pd.DataFrame:
    working_results = results_df.copy()
    if "status" in working_results.columns:
        working_results = working_results[working_results["status"] == _SUCCESS_STATUS]
    no_schedule_df = _build_no_schedule_latency_frame(
        results_df=working_results,
        model_constants_df=model_constants_df,
    )
    if no_schedule_df.empty:
        return pd.DataFrame()

    def _extract_partitions(prefix: str) -> set[int]:
        pattern = re.compile(rf"^{re.escape(prefix)}_sm(\d+)$")
        partitions: set[int] = set()
        for column in no_schedule_df.columns:
            match = pattern.match(column)
            if match is not None:
                partitions.add(int(match.group(1)))
        return partitions

    partition_values = sorted(
        _extract_partitions("decode_max_gemv_us_vram")
        | _extract_partitions("attention_fetch_compute_us_vram")
        | _extract_partitions("reduction_overhead_us_vram")
        | _extract_partitions("decode_max_gemv_us_pcie_async")
        | _extract_partitions("attention_fetch_compute_us_pcie_async")
        | _extract_partitions("reduction_overhead_us_pcie_async")
    )
    if not partition_values:
        partition_values = [100]

    decode_gemv_atoms_per_layer = float(
        getattr(simulator, "_DECODE_GEMV_ATOMS_PER_LAYER", 6)
    )

    rows: list[dict[str, float | int | str]] = []
    for _, row in no_schedule_df.iterrows():
        model_id = str(row.get("model_id"))
        chunk_tokens_value = pd.to_numeric(row.get("chunk_tokens"), errors="coerce")
        sequence_length_value = pd.to_numeric(
            row.get("sequence_length"), errors="coerce"
        )
        num_hidden_layers_value = pd.to_numeric(
            row.get("num_hidden_layers_for_no_schedule"), errors="coerce"
        )
        if (
            bool(pd.isna(chunk_tokens_value))
            or bool(pd.isna(sequence_length_value))
            or bool(pd.isna(num_hidden_layers_value))
            or float(chunk_tokens_value) <= 0
            or float(num_hidden_layers_value) <= 0
        ):
            continue
        chunk_tokens = int(float(chunk_tokens_value))
        sequence_length = int(float(sequence_length_value))
        num_hidden_layers = float(num_hidden_layers_value)
        transfer_atom_count = math.ceil(sequence_length / chunk_tokens)
        pcie_exposed_us = pd.to_numeric(row.get("pcie_exposed_us"), errors="coerce")
        pcie_ms = (
            float(pcie_exposed_us) / 1000.0
            if not bool(pd.isna(pcie_exposed_us))
            else float("nan")
        )
        base_vram_scheduled = pd.to_numeric(row.get("tpot_ms_vram"), errors="coerce")
        base_pcie_scheduled = pd.to_numeric(
            row.get("tpot_ms_pcie_async"), errors="coerce"
        )

        partition_latencies: dict[int, tuple[float, float]] = {}
        for partition in partition_values:
            scale_factor = _ANALYTICAL_FULL_GPU_SM_COUNT / float(partition)
            gemv_us = pd.to_numeric(row.get("decode_max_gemv_us"), errors="coerce")
            attention_us = pd.to_numeric(
                row.get("attention_fetch_compute_us"), errors="coerce"
            )
            reduction_us = pd.to_numeric(
                row.get("reduction_overhead_us"), errors="coerce"
            )
            gemv_ms = (
                float(gemv_us) / 1000.0 if not bool(pd.isna(gemv_us)) else float("nan")
            )
            attention_ms = (
                float(attention_us) / 1000.0
                if not bool(pd.isna(attention_us))
                else float("nan")
            )
            reduction_ms = (
                float(reduction_us) / 1000.0
                if not bool(pd.isna(reduction_us))
                else float("nan")
            )
            scaled_gemv_ms = gemv_ms * scale_factor
            scaled_attention_ms = attention_ms * scale_factor
            scaled_reduction_ms = reduction_ms * scale_factor
            scaled_pcie_ms = pcie_ms * scale_factor
            vram_nosched = num_hidden_layers * (
                (decode_gemv_atoms_per_layer * scaled_gemv_ms)
                + scaled_attention_ms
                + scaled_reduction_ms
            )
            pcie_nosched = vram_nosched + (transfer_atom_count * scaled_pcie_ms)
            partition_latencies[partition] = (vram_nosched, pcie_nosched)

        reference_partition = max(partition_values)
        ref_vram, ref_pcie = partition_latencies.get(
            reference_partition, (float("nan"), float("nan"))
        )
        for partition in partition_values:
            vram_nosched, pcie_nosched = partition_latencies[partition]
            if (
                bool(pd.isna(base_vram_scheduled))
                or bool(pd.isna(ref_vram))
                or ref_vram <= 0
                or bool(pd.isna(vram_nosched))
            ):
                vram_sched_proxy = float("nan")
            else:
                vram_sched_proxy = float(base_vram_scheduled) * (
                    vram_nosched / ref_vram
                )
            if (
                bool(pd.isna(base_pcie_scheduled))
                or bool(pd.isna(ref_pcie))
                or ref_pcie <= 0
                or bool(pd.isna(pcie_nosched))
            ):
                pcie_sched_proxy = float("nan")
            else:
                pcie_sched_proxy = float(base_pcie_scheduled) * (
                    pcie_nosched / ref_pcie
                )

            rows.append(
                {
                    "model_id": model_id,
                    "chunk_tokens": chunk_tokens,
                    "sequence_length": sequence_length,
                    "sm_ai_partition": partition,
                    "tpot_ms_vram_nosched": vram_nosched,
                    "tpot_ms_pcie_async_nosched": pcie_nosched,
                    "tpot_ms_vram_sched_proxy": vram_sched_proxy,
                    "tpot_ms_pcie_async_sched_proxy": pcie_sched_proxy,
                }
            )

    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return (
        frame.groupby(
            ["model_id", "chunk_tokens", "sequence_length", "sm_ai_partition"],
            as_index=False,
        )
        .agg(
            tpot_ms_vram_nosched=("tpot_ms_vram_nosched", "mean"),
            tpot_ms_pcie_async_nosched=("tpot_ms_pcie_async_nosched", "mean"),
            tpot_ms_vram_sched_proxy=("tpot_ms_vram_sched_proxy", "mean"),
            tpot_ms_pcie_async_sched_proxy=("tpot_ms_pcie_async_sched_proxy", "mean"),
        )
        .sort_values(["model_id", "chunk_tokens", "sequence_length", "sm_ai_partition"])
        .reset_index(drop=True)
    )


def _plot_tpot_with_partition_subplots(
    *,
    results_df: pd.DataFrame,
    model_constants_df: pd.DataFrame,
    plot5_chunk_selection: dict[str, int | None],
    plot_path: Path,
    scheduled: bool,
) -> None:
    tpot_frame = _build_tpot_partition_frame(
        results_df=results_df,
        model_constants_df=model_constants_df,
    )
    if tpot_frame.empty:
        raise PlotGenerationError(
            "TPOT plotting requires partition-level decode timing data"
        )

    vram_column = "tpot_ms_vram_sched_proxy" if scheduled else "tpot_ms_vram_nosched"
    pcie_column = (
        "tpot_ms_pcie_async_sched_proxy" if scheduled else "tpot_ms_pcie_async_nosched"
    )
    candidate_models = _ordered_models(tpot_frame["model_id"])
    models: list[str] = []
    for model_id in candidate_models:
        selected_chunk_tokens = plot5_chunk_selection.get(model_id)
        if selected_chunk_tokens is None:
            continue
        model_rows = tpot_frame[
            (tpot_frame["model_id"] == model_id)
            & (tpot_frame["chunk_tokens"] == selected_chunk_tokens)
        ]
        if model_rows.empty:
            continue
        has_any = (
            not model_rows[vram_column].dropna().empty
            or not model_rows[pcie_column].dropna().empty
        )
        if has_any:
            models.append(model_id)

    if not models:
        raise PlotGenerationError(
            "No TPOT panels have data for the selected chunk sizes"
        )

    partitions = (
        tpot_frame["sm_ai_partition"]
        .dropna()
        .astype(int)
        .sort_values()
        .unique()
        .tolist()
    )
    color_map = {
        partition: _SM_AI_PARTITION_COLORS[index % len(_SM_AI_PARTITION_COLORS)]
        for index, partition in enumerate(partitions)
    }

    with _apply_plot_style(width=12.8, height=max(3.4, 2.9 * len(models))):
        fig, axes = plt.subplots(
            len(models), 2, squeeze=False, sharex=False, sharey=False
        )

        for row_index, model_id in enumerate(models):
            selected_chunk_tokens = int(plot5_chunk_selection[model_id] or 0)
            model_rows = tpot_frame[
                (tpot_frame["model_id"] == model_id)
                & (tpot_frame["chunk_tokens"] == selected_chunk_tokens)
            ].copy()
            model_rows["sequence_length"] = pd.to_numeric(
                model_rows["sequence_length"], errors="coerce"
            )
            model_rows = model_rows.dropna(subset=["sequence_length"])
            model_rows["sequence_length"] = model_rows["sequence_length"].astype(int)
            model_rows = model_rows.sort_values("sequence_length")

            vram_axis = axes[row_index][0]
            pcie_axis = axes[row_index][1]
            for partition in partitions:
                partition_rows = model_rows[
                    model_rows["sm_ai_partition"] == partition
                ].sort_values("sequence_length")
                if partition_rows.empty:
                    continue
                sequence_lengths = (
                    partition_rows["sequence_length"].astype(int).tolist()
                )
                vram_values = partition_rows[vram_column].tolist()
                pcie_values = partition_rows[pcie_column].tolist()
                vram_axis.plot(
                    sequence_lengths,
                    vram_values,
                    marker="o",
                    linestyle="-",
                    color=color_map[partition],
                    label=f"SMs={partition}",
                )
                pcie_axis.plot(
                    sequence_lengths,
                    pcie_values,
                    marker="s",
                    linestyle="-",
                    color=color_map[partition],
                    label=f"SMs={partition}",
                )

            vram_axis.set_title(f"{_short_model_label(model_id)} · DGX VRAM fetch")
            pcie_axis.set_title(f"{_short_model_label(model_id)} · PCIe async fetch")
            vram_axis.set_xlabel("Sequence length")
            pcie_axis.set_xlabel("Sequence length")
            vram_axis.set_ylim(bottom=0)
            pcie_axis.set_ylim(bottom=0)
            if not model_rows.empty:
                ticks = sorted(model_rows["sequence_length"].unique().tolist())
                vram_axis.set_xticks(ticks)
                pcie_axis.set_xticks(ticks)
            vram_axis.text(
                0.03,
                0.95,
                f"N={selected_chunk_tokens}",
                ha="left",
                va="top",
                transform=vram_axis.transAxes,
                fontsize=8,
            )
            pcie_axis.text(
                0.03,
                0.95,
                f"N={selected_chunk_tokens}",
                ha="left",
                va="top",
                transform=pcie_axis.transAxes,
                fontsize=8,
            )
            vram_axis.set_ylabel("TPOT (ms)" if scheduled else "No-schedule TPOT (ms)")

        legend_handles = [
            Line2D(
                [0],
                [0],
                color=color_map[partition],
                marker="o",
                linestyle="-",
                label=f"SMs={partition}",
            )
            for partition in partitions
        ]
        fig.legend(
            handles=legend_handles,
            loc="upper center",
            ncol=min(max(2, len(legend_handles)), 5),
            bbox_to_anchor=(0.5, 1.02),
        )
        fig.suptitle(
            "Flash-decoding TPOT degradation (scheduled, by SM_AI)"
            if scheduled
            else "Flash-decoding TPOT degradation (no schedule, by SM_AI)",
            y=1.06,
        )
        fig.tight_layout()
        _save_figure(fig, plot_path)


def _build_operation_level_summary_frame(
    *,
    prefill_events_df: pd.DataFrame,
    decode_events_df: pd.DataFrame,
) -> pd.DataFrame:
    per_phase_frames = []
    for phase_name, frame, group_columns in (
        (
            "Prefill",
            prefill_events_df,
            ["model_id", "chunk_tokens", "timed_iteration", "sm_ai_partition"],
        ),
        (
            "Decode",
            decode_events_df,
            [
                "model_id",
                "sequence_length",
                "block_size",
                "timed_iteration",
                "sm_ai_partition",
            ],
        ),
    ):
        if frame.empty:
            continue
        working = frame.copy()
        working["phase"] = phase_name
        working["operation_group"] = [
            _operation_group(
                phase=phase_name, op_type=str(op_type), op_name=str(op_name)
            )
            for op_type, op_name in zip(working["op_type"], working["op_name"])
        ]
        working = working[working["operation_group"].notna()].copy()
        if working.empty:
            continue
        per_context = working.groupby(
            group_columns + ["phase", "operation_group"], as_index=False
        ).agg(
            duration_us=("duration_us", "sum"),
            workspace_bytes=("dynamic_workspace_bytes", "max"),
        )
        summary = per_context.groupby(
            ["phase", "sm_ai_partition", "operation_group"], as_index=False
        ).agg(
            duration_us=("duration_us", "mean"),
            workspace_bytes=("workspace_bytes", "max"),
        )
        per_phase_frames.append(summary)
    if not per_phase_frames:
        return pd.DataFrame(
            columns=[
                "phase",
                "sm_ai_partition",
                "operation_group",
                "duration_us",
                "workspace_bytes",
                "workspace_mb",
            ]
        )
    summary_df = pd.concat(per_phase_frames, ignore_index=True)
    summary_df["workspace_mb"] = summary_df["workspace_bytes"] / float(1024**2)
    return summary_df


def _operation_group(*, phase: str, op_type: str, op_name: str) -> str | None:
    normalized_op_type = op_type.strip().lower()
    normalized_op_name = op_name.strip().lower()
    if phase == "Prefill" and (
        normalized_op_type == "attention" or normalized_op_name == "attention"
    ):
        return "Attention"
    if phase == "Decode" and normalized_op_type in {
        "attention_fetch_compute",
        "reduction_overhead",
    }:
        return "Attention"
    if normalized_op_name in {"q_proj", "k_proj", "v_proj"}:
        return "QKV"
    if normalized_op_name == "out_proj":
        return "O_proj"
    if normalized_op_name == "fc1":
        return "MLP_up"
    if normalized_op_name == "fc2":
        return "MLP_down"
    return None


__all__ = [
    "PLOT_FILENAMES",
    "PLOT_SELECTION_FILENAME",
    "PlotGenerationError",
    "generate_profiling_plots",
]
