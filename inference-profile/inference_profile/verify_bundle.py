from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from inference_profile import experiments, manifests, telemetry
from inference_profile.paths import (
    CHECKSUM_MANIFEST_RELATIVE_PATH,
    bundle_paths_from_run_root,
)

_CHECKSUM_MANIFEST_PATH = CHECKSUM_MANIFEST_RELATIVE_PATH.as_posix()
_CHECKSUM_LINE_RE = re.compile(r"^(?P<digest>[0-9a-fA-F]{64})  (?P<path>.+)$")
_RAW_EVENT_FILENAMES = (
    "prefill_events.csv",
    "decode_events.csv",
    "pcie_events.csv",
)
_DERIVED_CSV_FILENAMES = (
    "normalized_ldpc_trace.csv",
    "model_constants.csv",
    "prefill_summary.csv",
    "decode_summary.csv",
    "pcie_summary.csv",
    "simulation_inputs.csv",
    "ran_inference_profiling_results.csv",
    "schedule_timeline.csv",
    "packed_exemplar_timeline.csv",
)
_CANONICAL_PLOT_FILENAMES = (
    "01_ran_trace_interleaving.png",
    "02_prefill_safety_boundary.png",
    "03_prefill_vram_composition.png",
    "04_ttft_vs_runway.png",
    "05_decode_tpot_degradation.png",
    "06_operation_level_microarchitecture_summary.png",
)
_INTERACTIVE_PLOT_FILENAMES = ("01_ran_trace_interleaving_interactive.html",)
_LOGS_DIRECTORY_KEY = "logs/"
_ZERO_BYTE_OK_LOG_SUFFIXES = (".stdout.log", ".stderr.log")


def _required_bundle_files(*, use_revised_plots: bool = False) -> tuple[str, ...]:
    """Return the run-level required artifact relative paths, excluding
    the plots/ entries which are resolved dynamically at verification time.

    The verify_bundle flow will accept either the canonical plot filenames or
    a revised set prefixed with `revised_`. We intentionally do not hardcode
    the plot filenames here because presence is detected against the run
    root during verification to keep legacy bundles stable.
    """
    raw_files = []
    for filename in _RAW_EVENT_FILENAMES:
        raw_files.append(f"raw/{filename}")
        raw_files.append(f"raw/{Path(filename).stem}_status.csv")

    derived_files = [f"derived/{filename}" for filename in _DERIVED_CSV_FILENAMES]

    plot_filenames = (
        tuple(f"revised_{filename}" for filename in _CANONICAL_PLOT_FILENAMES)
        if use_revised_plots
        else _CANONICAL_PLOT_FILENAMES
    )
    # include revised-only hardware utilization plot when revised contract
    if use_revised_plots:
        plot_filenames = tuple(
            list(plot_filenames) + ["revised_07_hardware_utilization_profiling.png"]
        )
        # revised-only decode memory consumption plot
        plot_filenames = tuple(
            list(plot_filenames) + ["revised_08_decode_memory_consumption.png"]
        )
        plot_filenames = tuple(
            list(plot_filenames) + ["revised_09_prefill_vram_composition_pie.png"]
        )
    interactive_plot_filenames = (
        tuple(f"revised_{filename}" for filename in _INTERACTIVE_PLOT_FILENAMES)
        if use_revised_plots
        else _INTERACTIVE_PLOT_FILENAMES
    )
    plot_files = [f"plots/{filename}" for filename in plot_filenames]
    pdf_plot_files = []
    if use_revised_plots:
        pdf_plot_files = [
            f"plots/{Path(filename).with_suffix('.pdf').name}"
            for filename in plot_filenames
        ]
    interactive_plot_files = [
        f"plots/{filename}" for filename in interactive_plot_filenames
    ]

    return (
        "run_manifest.json",
        "environment.json",
        *raw_files,
        *derived_files,
        *plot_files,
        *pdf_plot_files,
        *interactive_plot_files,
        "ran_inference_profiling_report.md",
        *(("report/report.md",) if use_revised_plots else ()),
        _CHECKSUM_MANIFEST_PATH,
    )


REQUIRED_BUNDLE_FILES = _required_bundle_files()
_REQUIRED_CHECKSUM_FILES = tuple(
    relative_path
    for relative_path in REQUIRED_BUNDLE_FILES
    if relative_path != _CHECKSUM_MANIFEST_PATH
)


def compute_file_checksum(file_path: Path, algorithm: str = "sha256") -> str:
    digest = hashlib.new(algorithm)
    with Path(file_path).open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def verify_bundle(run_root: Path, experiment_type: str | None = None) -> dict[str, Any]:
    bundle_paths = bundle_paths_from_run_root(Path(run_root))
    log_relative_paths = _log_relative_paths(
        bundle_paths.logs_dir, bundle_paths.run_root
    )

    use_revised_plot_contract = _uses_revised_plot_contract(
        bundle_paths.run_manifest_path,
        experiment_type=experiment_type,
    )
    plots_dir = bundle_paths.plots_dir
    selected_plot_paths = [
        plots_dir / (f"revised_{name}" if use_revised_plot_contract else name)
        for name in _CANONICAL_PLOT_FILENAMES
    ]
    # include additional revised-only hardware utilization plot when revised contract
    if use_revised_plot_contract:
        selected_plot_paths.append(
            plots_dir / "revised_07_hardware_utilization_profiling.png"
        )
        selected_plot_paths.append(
            plots_dir / "revised_08_decode_memory_consumption.png"
        )
        selected_plot_paths.append(
            plots_dir / "revised_09_prefill_vram_composition_pie.png"
        )
    interactive_name = (
        f"revised_{_INTERACTIVE_PLOT_FILENAMES[0]}"
        if use_revised_plot_contract
        else _INTERACTIVE_PLOT_FILENAMES[0]
    )

    runtime_required = list(
        _required_bundle_files(use_revised_plots=use_revised_plot_contract)
    )
    try:
        interactive_index = next(
            i
            for i, v in enumerate(runtime_required)
            if v.startswith("plots/") and v.endswith(_INTERACTIVE_PLOT_FILENAMES[0])
        )
    except StopIteration:
        interactive_index = len(runtime_required)
    runtime_required = [
        p
        for p in runtime_required
        if not (
            p.startswith("plots/")
            and (p.endswith(".png") or p.endswith(".html") or p.endswith(".pdf"))
        )
    ]
    for idx, plot_path in enumerate(selected_plot_paths):
        runtime_required.insert(
            interactive_index + idx,
            plot_path.relative_to(bundle_paths.run_root).as_posix(),
        )
    runtime_required.insert(
        interactive_index + len(selected_plot_paths),
        f"plots/{interactive_name}",
    )
    if use_revised_plot_contract:
        for idx, plot_path in enumerate(selected_plot_paths):
            runtime_required.insert(
                interactive_index + len(selected_plot_paths) + 1 + idx,
                plot_path.with_suffix(".pdf")
                .relative_to(bundle_paths.run_root)
                .as_posix(),
            )
    if use_revised_plot_contract:
        runtime_required.insert(
            len(runtime_required) - 2,
            f"telemetry/{telemetry.BASELINE_TELEMETRY_FILENAME}",
        )

    artifact_results: dict[str, dict[str, Any]] = {}
    completeness_results: dict[str, bool] = {}
    missing_artifacts: list[str] = []
    zero_byte_artifacts: list[str] = []

    for relative_path in runtime_required:
        artifact_path = bundle_paths.run_root / relative_path
        exists = artifact_path.exists()
        size_bytes = int(artifact_path.stat().st_size) if exists else 0
        non_zero_size = exists and size_bytes > 0
        completeness_results[relative_path] = bool(non_zero_size)
        artifact_results[relative_path] = {
            "exists": exists,
            "non_zero_size": bool(non_zero_size),
            "size_bytes": size_bytes,
        }
        if not exists:
            missing_artifacts.append(relative_path)
        elif size_bytes == 0:
            zero_byte_artifacts.append(relative_path)

    logs_dir_exists = bundle_paths.logs_dir.exists()
    completeness_results[_LOGS_DIRECTORY_KEY] = bool(log_relative_paths)
    artifact_results[_LOGS_DIRECTORY_KEY] = {
        "exists": logs_dir_exists,
        "non_zero_size": bool(log_relative_paths),
        "size_bytes": 0,
        "file_count": len(log_relative_paths),
    }
    if not log_relative_paths:
        missing_artifacts.append(_LOGS_DIRECTORY_KEY)

    for relative_path in log_relative_paths:
        artifact_path = bundle_paths.run_root / relative_path
        size_bytes = int(artifact_path.stat().st_size)
        allows_zero_bytes = _allows_zero_byte_artifact(relative_path)
        non_zero_size = size_bytes > 0
        artifact_complete = non_zero_size or allows_zero_bytes
        completeness_results[relative_path] = bool(artifact_complete)
        artifact_results[relative_path] = {
            "exists": True,
            "non_zero_size": bool(non_zero_size),
            "allows_zero_bytes": allows_zero_bytes,
            "size_bytes": size_bytes,
        }
        if not artifact_complete:
            zero_byte_artifacts.append(relative_path)

    checksum_entries, checksum_manifest_error = _load_checksum_entries(
        bundle_paths.checksum_manifest_path
    )
    checksum_results: dict[str, dict[str, Any]] = {}
    checksum_missing_artifacts: list[str] = []
    checksum_mismatches: list[str] = []

    if checksum_manifest_error is not None:
        checksum_results[_CHECKSUM_MANIFEST_PATH] = {
            "computed": None,
            "expected": None,
            "match": False,
            "reason": checksum_manifest_error,
        }

    # Determine which artifacts should be present for checksum validation.
    # Use the runtime_required list (which includes the selected plot files when
    # detected) plus any log files discovered under logs/.
    required_checksum_files = tuple(
        sorted(
            relative_path
            for relative_path in {*runtime_required, *log_relative_paths}
            if relative_path != _CHECKSUM_MANIFEST_PATH
        )
    )

    for relative_path in required_checksum_files:
        artifact_path = bundle_paths.run_root / relative_path
        expected_checksum = checksum_entries.get(relative_path)

        if relative_path in missing_artifacts:
            checksum_results[relative_path] = {
                "computed": None,
                "expected": expected_checksum,
                "match": False,
                "reason": "artifact missing",
            }
            continue

        if relative_path in zero_byte_artifacts:
            checksum_results[relative_path] = {
                "computed": None,
                "expected": expected_checksum,
                "match": False,
                "reason": "artifact is zero-byte",
            }
            continue

        if checksum_manifest_error is not None:
            continue

        if expected_checksum is None:
            checksum_missing_artifacts.append(relative_path)
            checksum_results[relative_path] = {
                "computed": None,
                "expected": None,
                "match": False,
                "reason": "missing checksum manifest entry",
            }
            continue

        computed_checksum = compute_file_checksum(artifact_path)
        match = computed_checksum == expected_checksum
        if not match:
            checksum_mismatches.append(relative_path)
        checksum_results[relative_path] = {
            "computed": computed_checksum,
            "expected": expected_checksum,
            "match": match,
            "reason": None if match else "checksum mismatch",
        }

    complete = not missing_artifacts and not zero_byte_artifacts
    checksums_valid = not any(
        not result.get("match", False) for result in checksum_results.values()
    )
    status = "success" if complete and checksums_valid else "fetch_failed"

    return {
        "required_artifacts": [
            *runtime_required,
            _LOGS_DIRECTORY_KEY,
            *log_relative_paths,
        ],
        "artifact_results": artifact_results,
        "complete": complete,
        "completeness_results": completeness_results,
        "checksums_valid": checksums_valid,
        "checksum_results": checksum_results,
        "missing_artifacts": sorted(missing_artifacts),
        "zero_byte_artifacts": sorted(zero_byte_artifacts),
        "checksum_missing_artifacts": sorted(checksum_missing_artifacts),
        "checksum_mismatches": sorted(checksum_mismatches),
        "status": status,
    }


def _log_relative_paths(logs_dir: Path, run_root: Path) -> tuple[str, ...]:
    if not logs_dir.exists():
        return ()
    return tuple(
        sorted(
            path.relative_to(run_root).as_posix()
            for path in logs_dir.rglob("*")
            if path.is_file()
        )
    )


def _uses_revised_plot_contract(
    manifest_path: Path, *, experiment_type: str | None = None
) -> bool:
    if experiment_type is not None:
        return (
            experiments.normalize_experiment_type(experiment_type)
            == experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE
        )
    if not manifest_path.exists():
        return False
    try:
        manifest = manifests.load_run_manifest(manifest_path)
    except Exception:
        return False
    return (
        manifest.get("schema_version") == experiments.RAN_DGXSPARK_V1_SCHEMA_VERSION
        or manifest.get("experiment_type")
        == experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE
    )


def _load_checksum_entries(
    checksum_manifest_path: Path,
) -> tuple[dict[str, str], str | None]:
    if not checksum_manifest_path.exists():
        return {}, "checksum manifest is missing"
    if checksum_manifest_path.stat().st_size == 0:
        return {}, "checksum manifest is zero-byte"

    entries: dict[str, str] = {}
    has_nonblank_line = False
    for line_number, raw_line in enumerate(
        checksum_manifest_path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw_line.strip()
        if not line:
            continue
        has_nonblank_line = True
        match = _CHECKSUM_LINE_RE.fullmatch(raw_line)
        if match is None:
            return (
                {},
                f"checksum manifest line {line_number} is malformed",
            )

        try:
            relative_path = _normalize_relative_path(match.group("path"))
        except ValueError as exc:
            return ({}, str(exc))

        if relative_path == _CHECKSUM_MANIFEST_PATH:
            continue
        if relative_path in entries:
            return (
                {},
                f"checksum manifest contains duplicate entry for {relative_path}",
            )
        entries[relative_path] = match.group("digest").lower()

    if not has_nonblank_line:
        return {}, "checksum manifest does not contain any checksum entries"
    return entries, None


def _allows_zero_byte_artifact(relative_path: str) -> bool:
    return relative_path.startswith("logs/") and relative_path.endswith(
        _ZERO_BYTE_OK_LOG_SUFFIXES
    )


def _normalize_relative_path(raw_path: str) -> str:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        raise ValueError("checksum manifest entries must be run-root-relative paths")
    if any(part == ".." for part in candidate.parts):
        raise ValueError("checksum manifest entries must not escape the run root")
    return candidate.as_posix()


__all__ = ["REQUIRED_BUNDLE_FILES", "compute_file_checksum", "verify_bundle"]
