from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, cast

from inference_profile.paths import (
    CHECKSUM_MANIFEST_RELATIVE_PATH,
    RunBundlePaths,
    bundle_paths_from_run_root,
)

MANIFEST_SCHEMA_VERSION = 1
FINAL_STATUSES = (
    "bootstrap_failed",
    "validation_failed",
    "profile_oom",
    "profile_failed",
    "simulate_failed",
    "report_failed",
    "ssh_failed",
    "fetch_failed",
    "success",
)
_FINAL_STATUS_SET = frozenset(FINAL_STATUSES)


def create_run_manifest(
    bundle_paths: RunBundlePaths,
    *,
    created_at: datetime | None = None,
) -> dict[str, object]:
    timestamp = _format_timestamp(created_at)
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "run_id": bundle_paths.run_id,
        "created_at": timestamp,
        "updated_at": timestamp,
        "final_status": None,
        "final_status_history": [],
        "bundle_layout": bundle_paths.relative_layout,
        "stages": {},
    }


def initialize_run_manifest(
    bundle_paths: RunBundlePaths,
    *,
    created_at: datetime | None = None,
) -> dict[str, object]:
    manifest = create_run_manifest(bundle_paths, created_at=created_at)
    _write_json_atomic(bundle_paths.run_manifest_path, manifest)
    return manifest


def load_run_manifest(manifest_path: Path) -> dict[str, object]:
    manifest_path = Path(manifest_path)
    if not manifest_path.exists():
        return create_run_manifest(bundle_paths_from_run_root(manifest_path.parent))

    with manifest_path.open("r", encoding="utf-8") as handle:
        payload = cast(object, json.load(handle))

    if not isinstance(payload, dict):
        raise ValueError(f"Expected manifest JSON object at {manifest_path}")
    if not payload:
        return create_run_manifest(bundle_paths_from_run_root(manifest_path.parent))

    manifest = dict(cast(dict[str, object], payload))
    manifest.setdefault("schema_version", MANIFEST_SCHEMA_VERSION)
    manifest.setdefault("run_id", manifest_path.parent.name)
    manifest.setdefault("created_at", _format_timestamp())
    manifest.setdefault("updated_at", manifest["created_at"])
    manifest.setdefault("final_status", None)
    manifest.setdefault("final_status_history", [])
    manifest.setdefault(
        "bundle_layout",
        bundle_paths_from_run_root(manifest_path.parent).relative_layout,
    )
    manifest.setdefault("stages", {})

    final_status = manifest["final_status"]
    if final_status is not None:
        _validate_status(cast(str, final_status))
    return manifest


def update_stage_status(
    manifest_path: Path,
    *,
    stage: str,
    status: str,
    timestamp: datetime | None = None,
    details: Mapping[str, object] | None = None,
    final_status: str | None = None,
) -> dict[str, object]:
    stage_name = stage.strip()
    if not stage_name:
        raise ValueError("stage must be a non-empty string")

    _validate_status(status)
    if final_status is not None:
        _validate_status(final_status)

    manifest = load_run_manifest(manifest_path)
    entry_timestamp = _format_timestamp(timestamp)
    details_dict = dict(details) if details is not None else None

    stages = manifest.setdefault("stages", {})
    if not isinstance(stages, dict):
        raise ValueError("Manifest field 'stages' must be an object")

    existing_stage = stages.get(stage_name, {})
    if not isinstance(existing_stage, dict):
        raise ValueError(f"Manifest stage {stage_name!r} must be an object")

    history_raw = existing_stage.get("history", [])
    if not isinstance(history_raw, list):
        raise ValueError(f"Manifest stage {stage_name!r} history must be a list")

    history = [dict(cast(dict[str, object], item)) for item in history_raw]
    history_entry: dict[str, object] = {
        "status": status,
        "timestamp": entry_timestamp,
    }
    if details_dict is not None:
        history_entry["details"] = details_dict
    history.append(history_entry)

    updated_stage = dict(existing_stage)
    updated_stage["latest_status"] = status
    updated_stage["updated_at"] = entry_timestamp
    updated_stage["history"] = history
    if details_dict is not None:
        updated_stage["details"] = details_dict
    stages[stage_name] = updated_stage

    manifest["updated_at"] = entry_timestamp
    if final_status is not None:
        _append_final_status(
            manifest,
            status=final_status,
            timestamp=entry_timestamp,
            details=details_dict,
        )

    _write_json_atomic(Path(manifest_path), manifest)
    return manifest


def set_final_status(
    manifest_path: Path,
    status: str,
    *,
    timestamp: datetime | None = None,
    details: Mapping[str, object] | None = None,
) -> dict[str, object]:
    _validate_status(status)
    manifest = load_run_manifest(manifest_path)
    entry_timestamp = _format_timestamp(timestamp)
    details_dict = dict(details) if details is not None else None
    manifest["updated_at"] = entry_timestamp
    _append_final_status(
        manifest,
        status=status,
        timestamp=entry_timestamp,
        details=details_dict,
    )
    _write_json_atomic(Path(manifest_path), manifest)
    return manifest


def required_checksum_paths(
    bundle_paths: RunBundlePaths,
    *extra_paths: Path,
) -> tuple[Path, ...]:
    return (
        bundle_paths.run_manifest_path,
        bundle_paths.environment_path,
        bundle_paths.report_path,
        *extra_paths,
    )


def write_checksum_manifest(
    run_root: Path,
    *,
    required_paths: Iterable[Path] | None = None,
) -> Path:
    bundle_paths = bundle_paths_from_run_root(run_root)
    targets = (
        tuple(required_paths)
        if required_paths is not None
        else required_checksum_paths(bundle_paths)
    )
    files = _expand_required_files(bundle_paths.run_root, targets)

    lines = []
    for artifact_path in files:
        relative_path = artifact_path.relative_to(bundle_paths.run_root).as_posix()
        lines.append(f"{_sha256_hex(artifact_path)}  {relative_path}")

    content = "\n".join(lines)
    if content:
        content += "\n"
    _write_text_atomic(bundle_paths.checksum_manifest_path, content)
    return bundle_paths.checksum_manifest_path


def _append_final_status(
    manifest: dict[str, object],
    *,
    status: str,
    timestamp: str,
    details: Mapping[str, object] | None,
) -> None:
    history_raw = manifest.setdefault("final_status_history", [])
    if not isinstance(history_raw, list):
        raise ValueError("Manifest field 'final_status_history' must be a list")

    history = [dict(cast(dict[str, object], item)) for item in history_raw]
    entry: dict[str, object] = {
        "status": status,
        "timestamp": timestamp,
    }
    if details is not None:
        entry["details"] = dict(details)
    history.append(entry)
    manifest["final_status"] = status
    manifest["final_status_history"] = history


def _expand_required_files(run_root: Path, targets: Iterable[Path]) -> list[Path]:
    files_by_relative_path: dict[str, Path] = {}

    for target in targets:
        candidate = target if target.is_absolute() else run_root / target
        if not candidate.exists():
            raise FileNotFoundError(
                f"Required checksum target does not exist: {candidate}"
            )

        if candidate.is_dir():
            discovered = [path for path in candidate.rglob("*") if path.is_file()]
        else:
            discovered = [candidate]

        for file_path in discovered:
            relative_path = _relative_run_path(run_root, file_path)
            if relative_path == CHECKSUM_MANIFEST_RELATIVE_PATH:
                continue
            files_by_relative_path[relative_path.as_posix()] = file_path

    return [
        files_by_relative_path[relative_path]
        for relative_path in sorted(files_by_relative_path)
    ]


def _relative_run_path(run_root: Path, path: Path) -> Path:
    try:
        return path.relative_to(run_root)
    except ValueError as exc:
        raise ValueError(
            f"Artifact path {path} is outside run root {run_root}"
        ) from exc


def _sha256_hex(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _validate_status(status: str) -> None:
    if status not in _FINAL_STATUS_SET:
        raise ValueError(
            f"Unsupported final status {status!r}; expected one of {FINAL_STATUSES}"
        )


def _format_timestamp(value: datetime | None = None) -> str:
    timestamp = value or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    else:
        timestamp = timestamp.astimezone(timezone.utc)
    return timestamp.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    _write_text_atomic(path, f"{rendered}\n")


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
        ) as handle:
            handle.write(content)
            temp_path = Path(handle.name)
        temp_path.replace(path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


__all__ = [
    "FINAL_STATUSES",
    "MANIFEST_SCHEMA_VERSION",
    "create_run_manifest",
    "initialize_run_manifest",
    "load_run_manifest",
    "required_checksum_paths",
    "set_final_status",
    "update_stage_status",
    "write_checksum_manifest",
]
