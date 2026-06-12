from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, cast

import pandas as pd
from pandas.errors import EmptyDataError

from inference_profile import (
    experiments,
    manifests,
    simulator,
    telemetry,
    trace_contract,
)
from inference_profile.paths import REPORTS_DIRNAME, bundle_paths_from_run_root

REPORT_TITLE = "RAN Inference Profiling Report"

_CANONICAL_PLOT_FILENAMES = (
    "01_ran_trace_interleaving.png",
    "02_prefill_safety_boundary.png",
    "03_prefill_vram_composition.png",
    "04_ttft_vs_runway.png",
    "05_decode_tpot_degradation.png",
    "06_operation_level_microarchitecture_summary.png",
)
_INTERACTIVE_PLOT_LINKS = {
    "01_ran_trace_interleaving.png": "01_ran_trace_interleaving_interactive.html",
}
_PLOT_TITLES = {
    "04_ttft_vs_runway.png": "04 TTFT vs. Additional Decode Tokens After Prefill",
    "revised_09_prefill_vram_composition_pie.png": "09 Spatial VRAM Composition (Prefill) · Pie View",
}
_SUCCESS_STATUS = "success"
_MODEL_SIZE_RE = re.compile(
    r"opt-(?P<value>\d+(?:\.\d+)?)(?P<unit>[mb])$",
    re.IGNORECASE,
)
_MODEL_CONSTANTS_FILENAME = "model_constants.csv"
_PREFILL_SUMMARY_FILENAME = "prefill_summary.csv"
_DECODE_SUMMARY_FILENAME = "decode_summary.csv"
_PCIE_SUMMARY_FILENAME = "pcie_summary.csv"
_RAW_PROFILE_TABLE_SPECS = (
    ("Prefill profile summary", "prefill_events.csv", _PREFILL_SUMMARY_FILENAME),
    ("Decode profile summary", "decode_events.csv", _DECODE_SUMMARY_FILENAME),
    ("PCIe profile summary", "pcie_events.csv", _PCIE_SUMMARY_FILENAME),
)


def generate_run_report(
    *,
    run_root: str | Path,
    experiment_type: str | None = None,
) -> Path:
    bundle_paths = bundle_paths_from_run_root(Path(run_root))
    raw_root = bundle_paths.raw_dir
    derived_root = bundle_paths.derived_dir

    environment_payload = _load_required_json(bundle_paths.environment_path)
    trace_inspection_payload = _load_required_json(
        raw_root / trace_contract.TRACE_INSPECTION_FILENAME
    )
    model_constants_df = _sort_frame(
        _load_required_csv(derived_root / _MODEL_CONSTANTS_FILENAME),
        by=("model_id",),
    )
    prefill_summary_df = _sort_frame(
        _load_required_csv(derived_root / _PREFILL_SUMMARY_FILENAME),
        by=("model_id", "chunk_tokens"),
    )
    decode_summary_df = _sort_frame(
        _load_required_csv(derived_root / _DECODE_SUMMARY_FILENAME),
        by=("model_id", "sequence_length", "block_size"),
    )
    pcie_summary_df = _sort_frame(
        _load_required_csv(derived_root / _PCIE_SUMMARY_FILENAME),
        by=("model_id", "block_size"),
    )
    results_df = _sort_frame(
        _load_required_csv(derived_root / simulator.SIMULATION_RESULTS_FILENAME),
        by=("model_id", "chunk_tokens", "sequence_length"),
    )
    plot_paths = _validate_plot_paths(
        bundle_paths.plots_dir,
        experiment_type=experiment_type,
    )

    sections: list[str] = [
        f"# {REPORT_TITLE}",
        "",
        f"Run root: `{bundle_paths.run_root}`",
        "",
    ]
    sections.extend(_render_environment_section(environment_payload))
    sections.extend(_render_model_constants_section(model_constants_df))
    sections.extend(_render_trace_inspection_section(trace_inspection_payload))
    sections.extend(
        _render_raw_profile_summary_section(
            raw_root=raw_root,
            prefill_summary_df=prefill_summary_df,
            decode_summary_df=decode_summary_df,
            pcie_summary_df=pcie_summary_df,
        )
    )
    sections.extend(_render_sla_tables_section(results_df))
    sections.extend(_render_scaling_analysis_section(results_df))
    sections.extend(_render_plots_section(plot_paths))

    report_content = "\n".join(section.rstrip() for section in sections).rstrip() + "\n"
    bundle_paths.report_path.write_text(report_content, encoding="utf-8")
    if _uses_revised_artifact_contract(
        run_manifest_path=bundle_paths.run_manifest_path,
        experiment_type=experiment_type,
    ):
        revised_report_path = bundle_paths.run_root / REPORTS_DIRNAME / "report.md"
        revised_report_path.parent.mkdir(parents=True, exist_ok=True)
        revised_report_content = report_content.replace("(plots/", "(../plots/")
        revised_report_path.write_text(revised_report_content, encoding="utf-8")

    write_run_checksum_manifest(
        run_root=bundle_paths.run_root,
        experiment_type=experiment_type,
    )
    return bundle_paths.report_path


def write_run_checksum_manifest(
    *, run_root: str | Path, experiment_type: str | None = None
) -> Path:
    bundle_paths = bundle_paths_from_run_root(Path(run_root))
    use_revised_contract = _uses_revised_artifact_contract(
        run_manifest_path=bundle_paths.run_manifest_path,
        experiment_type=experiment_type,
    )
    required_paths = manifests.required_checksum_paths(
        bundle_paths,
        bundle_paths.raw_dir,
        bundle_paths.derived_dir,
        bundle_paths.plots_dir,
        *(
            (bundle_paths.run_root / telemetry.TELEMETRY_DIRNAME,)
            if use_revised_contract
            else ()
        ),
        *((bundle_paths.run_root / REPORTS_DIRNAME,) if use_revised_contract else ()),
    )
    return manifests.write_checksum_manifest(
        bundle_paths.run_root,
        required_paths=required_paths,
    )


def _uses_revised_artifact_contract(
    *, run_manifest_path: Path, experiment_type: str | None = None
) -> bool:
    if experiment_type is not None:
        return (
            experiments.normalize_experiment_type(experiment_type)
            == experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE
        )
    if not run_manifest_path.exists():
        return False
    try:
        manifest = manifests.load_run_manifest(run_manifest_path)
    except Exception:
        return False
    return (
        manifest.get("schema_version") == experiments.RAN_DGXSPARK_V1_SCHEMA_VERSION
        or manifest.get("experiment_type")
        == experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE
    )


def _render_environment_section(environment_payload: dict[str, Any]) -> list[str]:
    lines = ["## Environment", ""]
    lines.extend(_render_mapping_table(environment_payload))
    lines.append("")
    return lines


def _render_model_constants_section(model_constants_df: pd.DataFrame) -> list[str]:
    lines = ["## Model Constants", ""]
    lines.extend(_render_dataframe(model_constants_df))
    lines.append("")
    return lines


def _render_trace_inspection_section(
    trace_inspection_payload: dict[str, Any],
) -> list[str]:
    lines = ["## Trace Inspection", ""]
    for trace_key, label in (
        ("primary_trace", "Primary trace"),
        ("secondary_trace", "Secondary trace"),
    ):
        trace_payload = trace_inspection_payload.get(trace_key)
        if not isinstance(trace_payload, dict):
            raise ValueError(
                "trace_inspection.json must contain object entries for primary_trace and secondary_trace"
            )
        lines.extend([f"### {label}", ""])
        lines.extend(_render_mapping_table(trace_payload))
        lines.append("")
    return lines


def _render_raw_profile_summary_section(
    *,
    raw_root: Path,
    prefill_summary_df: pd.DataFrame,
    decode_summary_df: pd.DataFrame,
    pcie_summary_df: pd.DataFrame,
) -> list[str]:
    summary_frames = {
        _PREFILL_SUMMARY_FILENAME: prefill_summary_df,
        _DECODE_SUMMARY_FILENAME: decode_summary_df,
        _PCIE_SUMMARY_FILENAME: pcie_summary_df,
    }
    lines = ["## Raw-Profile Summary Tables", ""]
    for section_title, raw_filename, summary_filename in _RAW_PROFILE_TABLE_SPECS:
        raw_path = raw_root / raw_filename
        raw_row_count = _csv_row_count(raw_path)
        lines.extend([f"### {section_title}", ""])
        lines.append(
            f"Source raw rows: `{raw_path.relative_to(raw_root.parent).as_posix()}` = {raw_row_count}. "
            f"Summary artifact: `derived/{summary_filename}`."
        )
        lines.append("")
        lines.extend(_render_dataframe(summary_frames[summary_filename]))
        lines.append("")
    return lines


def _render_sla_tables_section(results_df: pd.DataFrame) -> list[str]:
    status_series = cast(pd.Series, results_df["status"])
    success_df = _sort_frame(
        cast(pd.DataFrame, results_df.loc[status_series == _SUCCESS_STATUS].copy()),
        by=("model_id", "chunk_tokens", "sequence_length"),
    )
    failure_df = _sort_frame(
        cast(pd.DataFrame, results_df.loc[status_series != _SUCCESS_STATUS].copy()),
        by=("model_id", "chunk_tokens", "sequence_length"),
    )

    lines = ["## SLA Tables", "", "### Successful configurations", ""]
    lines.extend(
        _render_dataframe(
            _select_columns(
                success_df,
                columns=(
                    "model_id",
                    "chunk_tokens",
                    "sequence_length",
                    "ttft_ms",
                    "tpot_ms_vram",
                    "tpot_ms_pcie_async",
                    "decode_runway_tokens",
                    "status",
                ),
            )
        )
    )
    lines.extend(["", "### Failed configurations", ""])
    lines.extend(
        _render_dataframe(
            _select_columns(
                failure_df,
                columns=(
                    "model_id",
                    "chunk_tokens",
                    "sequence_length",
                    "status",
                ),
            )
        )
    )
    lines.append("")
    return lines


def _render_scaling_analysis_section(results_df: pd.DataFrame) -> list[str]:
    lines = ["## Per-Model Scaling Analysis", ""]
    lines.extend(_render_dataframe(_build_scaling_analysis_frame(results_df)))
    lines.append("")
    return lines


def _render_plots_section(plot_paths: tuple[Path, ...]) -> list[str]:
    lines = ["## Plots", ""]
    for plot_path in plot_paths:
        title = _PLOT_TITLES.get(
            plot_path.name,
            plot_path.stem.replace("_", " ").title(),
        )
        relative_path = Path("plots") / plot_path.name
        lines.extend(
            [
                f"### {title}",
                "",
                f"![{title}]({relative_path.as_posix()})",
                "",
            ]
        )
        interactive_name = _INTERACTIVE_PLOT_LINKS.get(plot_path.name)
        if interactive_name is None and plot_path.name.startswith("revised_"):
            interactive_name = f"revised_{_INTERACTIVE_PLOT_LINKS.get(plot_path.name.removeprefix('revised_'), '')}"
        if interactive_name is None:
            continue
        interactive_path = Path("plots") / interactive_name
        if (plot_path.parent / interactive_name).exists():
            lines.append(f"[Interactive companion]({interactive_path.as_posix()})")
            lines.append("")
    return lines


def _build_scaling_analysis_frame(results_df: pd.DataFrame) -> pd.DataFrame:
    if results_df.empty:
        return pd.DataFrame(
            columns=[
                "model_id",
                "successful_configs",
                "failed_configs",
                "chunk_tokens_tested",
                "sequence_lengths_tested",
                "largest_successful_chunk_tokens",
                "ttft_ms_min",
                "ttft_ms_max",
                "tpot_ms_vram_min",
                "tpot_ms_vram_max",
                "tpot_ms_pcie_async_min",
                "tpot_ms_pcie_async_max",
                "max_decode_runway_tokens",
            ]
        )

    rows: list[dict[str, Any]] = []
    for model_id, grouped_rows in results_df.groupby("model_id", sort=False):
        model_rows = _sort_frame(
            cast(pd.DataFrame, grouped_rows.copy()),
            by=("model_id", "chunk_tokens", "sequence_length"),
        )
        model_status = cast(pd.Series, model_rows["status"])
        success_rows = cast(
            pd.DataFrame,
            model_rows.loc[model_status == _SUCCESS_STATUS].copy(),
        )
        rows.append(
            {
                "model_id": str(model_id),
                "successful_configs": int(len(success_rows)),
                "failed_configs": int(len(model_rows) - len(success_rows)),
                "chunk_tokens_tested": _join_unique_ints(model_rows, "chunk_tokens"),
                "sequence_lengths_tested": _join_unique_ints(
                    model_rows,
                    "sequence_length",
                ),
                "largest_successful_chunk_tokens": _series_max_int(
                    success_rows,
                    "chunk_tokens",
                ),
                "ttft_ms_min": _series_min_float(success_rows, "ttft_ms"),
                "ttft_ms_max": _series_max_float(success_rows, "ttft_ms"),
                "tpot_ms_vram_min": _series_min_float(success_rows, "tpot_ms_vram"),
                "tpot_ms_vram_max": _series_max_float(success_rows, "tpot_ms_vram"),
                "tpot_ms_pcie_async_min": _series_min_float(
                    success_rows,
                    "tpot_ms_pcie_async",
                ),
                "tpot_ms_pcie_async_max": _series_max_float(
                    success_rows,
                    "tpot_ms_pcie_async",
                ),
                "max_decode_runway_tokens": _series_max_int(
                    success_rows,
                    "decode_runway_tokens",
                ),
            }
        )

    scaling_df = pd.DataFrame(rows)
    return _sort_frame(scaling_df, by=("model_id",))


def _render_mapping_table(payload: dict[str, Any]) -> list[str]:
    if not payload:
        return ["No data available."]

    flattened = _flatten_mapping(payload)
    if not flattened:
        return ["No data available."]

    rows = [
        {"field": key, "value": value}
        for key, value in sorted(flattened.items(), key=lambda item: item[0])
    ]
    return _render_markdown_table(rows=rows, columns=("field", "value"))


def _render_dataframe(df: pd.DataFrame) -> list[str]:
    if df.empty:
        return ["No rows available."]

    rows = df.to_dict(orient="records")
    return _render_markdown_table(rows=rows, columns=tuple(df.columns))


def _render_markdown_table(
    *,
    rows: list[dict[str, Any]],
    columns: tuple[str, ...],
) -> list[str]:
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    lines = [header, separator]
    for row in rows:
        rendered_cells = [
            _escape_markdown_cell(_format_value(row.get(column))) for column in columns
        ]
        lines.append("| " + " | ".join(rendered_cells) + " |")
    return lines


def _escape_markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


def _format_value(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value or ""
    if isinstance(value, (list, tuple, set, dict)):
        return json.dumps(value, sort_keys=True)

    missing = pd.isna(value)
    if isinstance(missing, bool) and missing:
        return "n/a"

    if isinstance(value, float):
        rendered = f"{value:.4f}".rstrip("0").rstrip(".")
        return rendered or "0"
    return str(value)


def _flatten_mapping(
    payload: dict[str, Any],
    *,
    prefix: str = "",
) -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for key, value in payload.items():
        nested_key = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            flattened.update(_flatten_mapping(value, prefix=nested_key))
            continue
        flattened[nested_key] = value
    return flattened


def _select_columns(df: pd.DataFrame, *, columns: tuple[str, ...]) -> pd.DataFrame:
    available_columns = [column for column in columns if column in df.columns]
    if not available_columns:
        return pd.DataFrame(columns=list(columns))
    return df.loc[:, available_columns].copy()


def _sort_frame(df: pd.DataFrame, *, by: tuple[str, ...]) -> pd.DataFrame:
    if df.empty:
        return df.reset_index(drop=True)

    working = df.copy()
    sort_columns: list[str] = []
    ascending: list[bool] = []
    if "model_id" in by and "model_id" in working.columns:
        working["__model_sort"] = working["model_id"].map(_model_sort_value)
        sort_columns.extend(["__model_sort", "model_id"])
        ascending.extend([True, True])

    for column in by:
        if column == "model_id" or column not in working.columns:
            continue
        sort_columns.append(column)
        ascending.append(True)

    if not sort_columns:
        return working.reset_index(drop=True)

    sorted_df = working.sort_values(
        by=sort_columns,
        ascending=ascending,
        kind="mergesort",
    )
    return sorted_df.drop(columns=["__model_sort"], errors="ignore").reset_index(
        drop=True
    )


def _model_sort_value(model_id: Any) -> float:
    match = _MODEL_SIZE_RE.search(str(model_id))
    if match is None:
        return float("inf")

    value = float(match.group("value"))
    unit = match.group("unit").lower()
    if unit == "m":
        return value / 1_000.0
    return value


def _join_unique_ints(df: pd.DataFrame, column: str) -> str:
    if column not in df.columns or df.empty:
        return "n/a"

    series = cast(pd.Series, df[column]).dropna()
    values = sorted({int(value) for value in series.tolist()})
    if not values:
        return "n/a"
    return ", ".join(str(value) for value in values)


def _series_min_float(df: pd.DataFrame, column: str) -> float | None:
    if column not in df.columns or df.empty:
        return None
    series = cast(pd.Series, df[column]).dropna()
    if series.empty:
        return None
    minimum = series.min()
    missing = pd.isna(minimum)
    if isinstance(missing, bool) and missing:
        return None
    return float(cast(Any, minimum))


def _series_max_float(df: pd.DataFrame, column: str) -> float | None:
    if column not in df.columns or df.empty:
        return None
    series = cast(pd.Series, df[column]).dropna()
    if series.empty:
        return None
    maximum = series.max()
    missing = pd.isna(maximum)
    if isinstance(missing, bool) and missing:
        return None
    return float(cast(Any, maximum))


def _series_max_int(df: pd.DataFrame, column: str) -> int | None:
    if column not in df.columns or df.empty:
        return None
    series = cast(pd.Series, df[column]).dropna()
    if series.empty:
        return None
    maximum = series.max()
    missing = pd.isna(maximum)
    if isinstance(missing, bool) and missing:
        return None
    return int(cast(Any, maximum))


def _validate_plot_paths(
    plots_root: Path,
    *,
    experiment_type: str | None = None,
) -> tuple[Path, ...]:
    plot_paths: list[Path] = []

    run_manifest_path = plots_root.parent / "run_manifest.json"
    use_revised_plots = _uses_revised_artifact_contract(
        run_manifest_path=run_manifest_path,
        experiment_type=experiment_type,
    )

    selected_set = (
        tuple(f"revised_{name}" for name in _CANONICAL_PLOT_FILENAMES)
        if use_revised_plots
        else _CANONICAL_PLOT_FILENAMES
    )
    # include revised-only hardware utilization plot when using revised contract
    if use_revised_plots:
        selected_set = tuple(
            list(selected_set) + ["revised_07_hardware_utilization_profiling.png"]
        )
        # revised-only decode memory consumption plot
        selected_set = tuple(
            list(selected_set) + ["revised_08_decode_memory_consumption.png"]
        )
        selected_set = tuple(
            list(selected_set) + ["revised_09_prefill_vram_composition_pie.png"]
        )

    missing_list = []
    for filename in selected_set:
        plot_path = plots_root / filename
        if not plot_path.exists() or plot_path.stat().st_size == 0:
            missing_list.append(str(plot_path))
        else:
            plot_paths.append(plot_path)

    if missing_list:
        raise FileNotFoundError(
            f"Missing required plot images. Examples missing: {missing_list[:3]}"
        )

    interactive_names = (
        tuple(f"revised_{name}" for name in _INTERACTIVE_PLOT_LINKS.values())
        if use_revised_plots
        else tuple(_INTERACTIVE_PLOT_LINKS.values())
    )
    missing_interactive = [
        str(plots_root / name)
        for name in interactive_names
        if not (plots_root / name).exists() or (plots_root / name).stat().st_size == 0
    ]
    if missing_interactive:
        raise FileNotFoundError(
            f"Missing required interactive plot artifact(s): {missing_interactive}"
        )

    return tuple(plot_paths)


def _csv_row_count(csv_path: Path) -> int:
    return len(_load_required_csv(csv_path))


def _load_required_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required JSON artifact: {path}")
    if path.stat().st_size == 0:
        raise ValueError(f"Required JSON artifact is zero-byte: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def _load_required_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing required CSV artifact: {path}")
    if path.stat().st_size == 0:
        raise ValueError(f"Required CSV artifact is zero-byte: {path}")

    try:
        return pd.read_csv(path)
    except EmptyDataError as exc:
        raise ValueError(
            f"Required CSV artifact has no readable header: {path}"
        ) from exc


__all__ = ["generate_run_report"]
