from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

RUNS_DIRNAME = "runs"
LOGS_DIRNAME = "logs"
RAW_DIRNAME = "raw"
DERIVED_DIRNAME = "derived"
PLOTS_DIRNAME = "plots"
CHECKSUMS_DIRNAME = "checksums"

RUN_MANIFEST_FILENAME = "run_manifest.json"
ENVIRONMENT_FILENAME = "environment.json"
REPORT_FILENAME = "ran_inference_profiling_report.md"
CHECKSUM_MANIFEST_FILENAME = "sha256sums.txt"
CHECKSUM_MANIFEST_RELATIVE_PATH = Path(CHECKSUMS_DIRNAME) / CHECKSUM_MANIFEST_FILENAME


@dataclass(frozen=True)
class RunBundlePaths:
    run_id: str
    run_root: Path
    logs_dir: Path
    raw_dir: Path
    derived_dir: Path
    plots_dir: Path
    checksums_dir: Path
    run_manifest_path: Path
    environment_path: Path
    report_path: Path
    checksum_manifest_path: Path

    @property
    def directories(self) -> tuple[Path, ...]:
        return (
            self.run_root,
            self.logs_dir,
            self.raw_dir,
            self.derived_dir,
            self.plots_dir,
            self.checksums_dir,
        )

    @property
    def canonical_files(self) -> tuple[Path, ...]:
        return (
            self.run_manifest_path,
            self.environment_path,
            self.report_path,
            self.checksum_manifest_path,
        )

    @property
    def relative_layout(self) -> dict[str, str]:
        return {
            "logs": self.logs_dir.relative_to(self.run_root).as_posix(),
            "raw": self.raw_dir.relative_to(self.run_root).as_posix(),
            "derived": self.derived_dir.relative_to(self.run_root).as_posix(),
            "plots": self.plots_dir.relative_to(self.run_root).as_posix(),
            "checksums": self.checksums_dir.relative_to(self.run_root).as_posix(),
            "run_manifest": self.run_manifest_path.relative_to(
                self.run_root
            ).as_posix(),
            "environment": self.environment_path.relative_to(self.run_root).as_posix(),
            "report": self.report_path.relative_to(self.run_root).as_posix(),
            "checksum_manifest": self.checksum_manifest_path.relative_to(
                self.run_root
            ).as_posix(),
        }


def make_run_id(now: datetime | None = None) -> str:
    timestamp = _normalize_timestamp(now or datetime.now(timezone.utc))
    return timestamp.strftime("%Y%m%d_%H%M%S")


def build_run_bundle_paths(output_root: Path, run_id: str) -> RunBundlePaths:
    if not run_id.strip():
        raise ValueError("run_id must be a non-empty string")

    run_root = Path(output_root) / RUNS_DIRNAME / run_id
    return bundle_paths_from_run_root(run_root)


def bundle_paths_from_run_root(run_root: Path) -> RunBundlePaths:
    run_root = Path(run_root)
    if not run_root.name:
        raise ValueError("run_root must include a terminal run directory name")

    return RunBundlePaths(
        run_id=run_root.name,
        run_root=run_root,
        logs_dir=run_root / LOGS_DIRNAME,
        raw_dir=run_root / RAW_DIRNAME,
        derived_dir=run_root / DERIVED_DIRNAME,
        plots_dir=run_root / PLOTS_DIRNAME,
        checksums_dir=run_root / CHECKSUMS_DIRNAME,
        run_manifest_path=run_root / RUN_MANIFEST_FILENAME,
        environment_path=run_root / ENVIRONMENT_FILENAME,
        report_path=run_root / REPORT_FILENAME,
        checksum_manifest_path=run_root / CHECKSUM_MANIFEST_RELATIVE_PATH,
    )


def init_run_bundle(
    output_root: Path,
    run_id: str | None = None,
    *,
    now: datetime | None = None,
) -> RunBundlePaths:
    bundle_paths = build_run_bundle_paths(output_root, run_id or make_run_id(now))

    for directory in bundle_paths.directories:
        directory.mkdir(parents=True, exist_ok=True)

    _ensure_json_placeholder(bundle_paths.run_manifest_path)
    _ensure_json_placeholder(bundle_paths.environment_path)
    _ensure_text_placeholder(bundle_paths.report_path)
    _ensure_text_placeholder(bundle_paths.checksum_manifest_path)
    return bundle_paths


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _ensure_json_placeholder(path: Path) -> None:
    if path.exists():
        return
    path.write_text("{}\n", encoding="utf-8")


def _ensure_text_placeholder(path: Path) -> None:
    if path.exists():
        return
    path.touch()


__all__ = [
    "CHECKSUMS_DIRNAME",
    "CHECKSUM_MANIFEST_FILENAME",
    "CHECKSUM_MANIFEST_RELATIVE_PATH",
    "DERIVED_DIRNAME",
    "ENVIRONMENT_FILENAME",
    "LOGS_DIRNAME",
    "PLOTS_DIRNAME",
    "RAW_DIRNAME",
    "REPORT_FILENAME",
    "RUNS_DIRNAME",
    "RUN_MANIFEST_FILENAME",
    "RunBundlePaths",
    "build_run_bundle_paths",
    "bundle_paths_from_run_root",
    "init_run_bundle",
    "make_run_id",
]
