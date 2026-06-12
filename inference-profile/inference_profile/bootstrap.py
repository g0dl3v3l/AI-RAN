from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
import importlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from tempfile import NamedTemporaryFile
from typing import Any
import venv
import warnings

from inference_profile import experiments, manifests, paths

_BOOTSTRAP_STAGE_NAME = "bootstrap-env"
_DEFAULT_CACHE_DIRNAME = "cache"
_VENV_DIRNAME = ".venv"
_VENV_CREATE_COMMAND = "python3 -m venv --system-site-packages .venv"
_OPTIONAL_DEPENDENCIES = ("transformers", "safetensors")


@dataclass(frozen=True)
class BootstrapFailure:
    failure_kind: str
    failure_cause: str
    step: str
    public_status: str = "bootstrap_failed"

    def as_payload(self) -> dict[str, object]:
        return {
            "bootstrap_status": self.public_status,
            "public_status": self.public_status,
            "failure_kind": self.failure_kind,
            "failure_cause": self.failure_cause,
            "failed_step": self.step,
        }


@dataclass(frozen=True)
class BootstrapResult:
    output_root: Path
    cache_root: Path
    environment_path: Path
    payload: dict[str, Any]
    failure: BootstrapFailure | None = None

    @property
    def success(self) -> bool:
        return self.failure is None

    def user_error_message(self) -> str:
        if self.failure is None:
            return ""
        summary = f"{self.failure.failure_kind}: {self.failure.failure_cause}"
        if self.environment_path.exists():
            return f"{summary}. See {self.environment_path}"
        return summary


class BootstrapEnvironmentError(RuntimeError):
    def __init__(self, result: BootstrapResult) -> None:
        self.result = result
        super().__init__(result.user_error_message())


class _BootstrapCheckFailed(Exception):
    def __init__(self, failure: BootstrapFailure) -> None:
        self.failure = failure
        super().__init__(failure.failure_cause)


def bootstrap_environment(
    *,
    output_root: str | Path,
    cache_root: str | Path | None = None,
    gpu_id: int = 0,
    experiment_type: str | None = None,
    manifest_metadata: dict[str, Any] | None = None,
) -> BootstrapResult:
    resolved_gpu_id = _normalize_non_negative_int(gpu_id, name="gpu_id")
    resolved_output_root = Path(output_root)
    resolved_cache_root = (
        Path(cache_root)
        if cache_root is not None
        else resolved_output_root / _DEFAULT_CACHE_DIRNAME
    )
    environment_path = resolved_output_root / paths.ENVIRONMENT_FILENAME
    venv_path = resolved_output_root / _VENV_DIRNAME
    project_root = Path(__file__).resolve().parents[1]
    normalized_experiment_type = experiments.normalize_experiment_type(experiment_type)
    resolved_manifest_metadata = dict(manifest_metadata or {})

    payload: dict[str, Any] = {
        "stage": _BOOTSTRAP_STAGE_NAME,
        "captured_at": _utc_timestamp(),
        "output_root": str(resolved_output_root),
        "cache_root": str(resolved_cache_root),
        "gpu_id": resolved_gpu_id,
        "project_root": str(project_root),
        "python_version": platform.python_version(),
        "python_executable": sys.executable,
        "python_executable_exists": False,
        "platform": platform.platform(),
        "cwd": str(Path.cwd()),
        "experiment_type": normalized_experiment_type,
        "bootstrap_status": None,
        "public_status": None,
        "failure_kind": None,
        "failure_cause": None,
        "failed_step": None,
        "paths": {},
        "installation": {
            "mode": "validate-only",
            "system_packages_mutated": False,
            "project_installation_required": True,
            "python_only_dependency_installation_expected": True,
            "editable_install_command": None,
        },
        "venv": {
            "path": str(venv_path),
            "create_command": _VENV_CREATE_COMMAND,
            "system_site_packages_required": True,
            "status": "pending",
            "pyvenv_cfg_path": str(venv_path / "pyvenv.cfg"),
            "python_path": str(_venv_python_path(venv_path)),
            "include_system_site_packages": None,
        },
        "dependencies": {},
        "cuda": {
            "selected_gpu_id": resolved_gpu_id,
            "available": None,
            "device_count": None,
            "torch_cuda_build_version": None,
            "driver_version": None,
            "gpu_name": None,
            "total_memory_bytes": None,
            "multi_processor_count": None,
            "compute_capability": None,
            "probe_error": None,
        },
        "manifest_update": {
            "attempted": False,
            "status": "not_attempted",
            "path": str(resolved_output_root / paths.RUN_MANIFEST_FILENAME),
            "error": None,
        },
    }
    payload.update(resolved_manifest_metadata)

    failure: BootstrapFailure | None = None
    output_root_ready = False

    try:
        output_root_info = _validate_writable_directory(
            resolved_output_root,
            label="output_root",
        )
        output_root_ready = True
        payload["paths"]["output_root"] = output_root_info

        cache_root_info = _validate_writable_directory(
            resolved_cache_root,
            label="cache_root",
        )
        payload["paths"]["cache_root"] = cache_root_info

        python_executable = Path(sys.executable) if sys.executable else None
        payload["python_executable_exists"] = bool(
            python_executable is not None and python_executable.exists()
        )
        if not payload["python_executable_exists"]:
            _raise_failure(
                step="python",
                kind="python_missing",
                cause=f"Python executable {sys.executable!r} does not exist",
            )

        payload["venv"].update(_ensure_virtual_environment(venv_path))
        payload["installation"]["editable_install_command"] = (
            f"{payload['venv']['python_path']} -m pip install -e {project_root}"
        )

        dependency_payload, torch_module = _probe_dependencies()
        payload["dependencies"] = dependency_payload
        if torch_module is None:
            _raise_failure(
                step="dependencies",
                kind="dependency_missing",
                cause=(
                    "Required Python dependency 'torch' is not importable: "
                    f"{dependency_payload['torch']['error']}"
                ),
            )

        cuda_payload = dict(payload["cuda"])
        payload["cuda"] = cuda_payload
        _probe_torch_runtime(
            torch_module,
            gpu_id=resolved_gpu_id,
            payload=cuda_payload,
        )
    except _BootstrapCheckFailed as exc:
        failure = exc.failure
    except Exception as exc:
        failure = BootstrapFailure(
            failure_kind="bootstrap_exception",
            failure_cause=_exception_message(exc),
            step="bootstrap",
        )

    if failure is None:
        payload.update(
            {
                "bootstrap_status": "success",
                "public_status": "success",
                "failure_kind": None,
                "failure_cause": None,
                "failed_step": None,
            }
        )
    else:
        payload.update(failure.as_payload())

    if output_root_ready:
        payload["manifest_update"] = _maybe_update_manifest(
            run_root=resolved_output_root,
            environment_path=environment_path,
            gpu_id=resolved_gpu_id,
            failure=failure,
            experiment_type=normalized_experiment_type,
            manifest_metadata=resolved_manifest_metadata,
        )
        _write_json_file(environment_path, payload)

    result = BootstrapResult(
        output_root=resolved_output_root,
        cache_root=resolved_cache_root,
        environment_path=environment_path,
        payload=payload,
        failure=failure,
    )
    if failure is not None:
        raise BootstrapEnvironmentError(result)
    return result


def _ensure_virtual_environment(venv_path: Path) -> dict[str, Any]:
    pyvenv_cfg_path = venv_path / "pyvenv.cfg"
    created = False
    if not pyvenv_cfg_path.exists():
        _create_virtual_environment(venv_path)
        created = True

    if not pyvenv_cfg_path.exists():
        _raise_failure(
            step="venv",
            kind="venv_creation_failed",
            cause=f"Virtual environment metadata missing at {pyvenv_cfg_path}",
        )

    cfg_values = _read_pyvenv_cfg(pyvenv_cfg_path)
    include_system_site_packages = (
        cfg_values.get("include-system-site-packages", "").strip().lower() == "true"
    )
    if not include_system_site_packages:
        _raise_failure(
            step="venv",
            kind="venv_invalid",
            cause=(
                f"Existing virtual environment at {venv_path} does not enable "
                "system site packages"
            ),
        )

    python_path = _venv_python_path(venv_path)
    if not python_path.exists():
        _raise_failure(
            step="venv",
            kind="venv_invalid",
            cause=f"Virtual environment Python executable missing at {python_path}",
        )

    return {
        "status": "created" if created else "validated",
        "pyvenv_cfg_path": str(pyvenv_cfg_path),
        "python_path": str(python_path),
        "include_system_site_packages": include_system_site_packages,
    }


def _create_virtual_environment(venv_path: Path) -> None:
    try:
        venv.EnvBuilder(
            system_site_packages=True,
            with_pip=False,
            clear=False,
        ).create(str(venv_path))
    except Exception as exc:
        _raise_failure(
            step="venv",
            kind="venv_creation_failed",
            cause=f"Could not create virtual environment at {venv_path}: {_exception_message(exc)}",
        )


def _probe_dependencies() -> tuple[dict[str, dict[str, Any]], Any | None]:
    payload: dict[str, dict[str, Any]] = {}
    torch_module, torch_info = _probe_dependency("torch", required=True)
    payload["torch"] = torch_info
    for module_name in _OPTIONAL_DEPENDENCIES:
        _module, module_info = _probe_dependency(module_name, required=False)
        payload[module_name] = module_info
    return payload, torch_module


def _probe_dependency(
    module_name: str,
    *,
    required: bool,
) -> tuple[Any | None, dict[str, Any]]:
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        return None, {
            "required": required,
            "available": False,
            "version": None,
            "error": _exception_message(exc),
        }

    return module, {
        "required": required,
        "available": True,
        "version": getattr(module, "__version__", None),
        "error": None,
    }


def _probe_torch_runtime(
    torch_module: Any,
    *,
    gpu_id: int,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cuda_available = False
    device_count = 0
    properties: Any | None = None
    resolved_payload = payload if payload is not None else {}
    resolved_payload.update(
        {
            "selected_gpu_id": gpu_id,
            "available": False,
            "device_count": 0,
            "torch_cuda_build_version": getattr(
                getattr(torch_module, "version", None),
                "cuda",
                None,
            ),
            "driver_version": None,
            "gpu_name": None,
            "total_memory_bytes": None,
            "multi_processor_count": None,
            "compute_capability": None,
            "probe_error": None,
        }
    )

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            cuda_available = bool(torch_module.cuda.is_available())
    except Exception as exc:
        resolved_payload["probe_error"] = _exception_message(exc)
        _raise_failure(
            step="cuda",
            kind="cuda_probe_failed",
            cause=(
                "Could not determine torch CUDA availability: "
                f"{resolved_payload['probe_error']}"
            ),
        )

    resolved_payload["available"] = cuda_available
    if not cuda_available:
        _raise_failure(
            step="cuda",
            kind="cuda_unavailable",
            cause="torch.cuda.is_available() returned False",
        )

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            device_count = int(torch_module.cuda.device_count())
    except Exception as exc:
        resolved_payload["probe_error"] = _exception_message(exc)
        _raise_failure(
            step="cuda",
            kind="cuda_probe_failed",
            cause=(
                f"Could not query CUDA device count: {resolved_payload['probe_error']}"
            ),
        )

    resolved_payload["device_count"] = device_count
    if gpu_id >= device_count:
        _raise_failure(
            step="cuda",
            kind="gpu_unavailable",
            cause=(
                f"Requested gpu_id {gpu_id} is unavailable; detected "
                f"{device_count} CUDA device(s)"
            ),
        )

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            properties = torch_module.cuda.get_device_properties(gpu_id)
    except Exception as exc:
        resolved_payload["probe_error"] = _exception_message(exc)
        _raise_failure(
            step="cuda",
            kind="gpu_properties_unavailable",
            cause=(
                f"Could not query CUDA device properties for gpu_id {gpu_id}: "
                f"{resolved_payload['probe_error']}"
            ),
        )

    resolved_payload.update(
        {
            "driver_version": _probe_cuda_driver_version(gpu_id),
            "gpu_name": getattr(properties, "name", None),
            "total_memory_bytes": _optional_int(
                getattr(properties, "total_memory", None)
            ),
            "multi_processor_count": _optional_int(
                getattr(properties, "multi_processor_count", None)
            ),
            "compute_capability": _compute_capability(properties),
        }
    )
    return resolved_payload


def _validate_writable_directory(path: Path, *, label: str) -> dict[str, Any]:
    free_bytes = 0
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        _raise_failure(
            step=label,
            kind="path_unusable",
            cause=f"Could not create {label} directory {path}: {_exception_message(exc)}",
        )

    if not path.is_dir():
        _raise_failure(
            step=label,
            kind="path_unusable",
            cause=f"{label} path {path} is not a directory",
        )

    try:
        free_bytes = int(shutil.disk_usage(path).free)
    except OSError as exc:
        _raise_failure(
            step=label,
            kind="disk_probe_failed",
            cause=f"Could not inspect free disk space for {path}: {_exception_message(exc)}",
        )

    if free_bytes <= 0:
        _raise_failure(
            step=label,
            kind="insufficient_disk_space",
            cause=f"{label} directory {path} has no free disk space",
        )

    marker_path: Path | None = None
    try:
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path,
            prefix=".bootstrap-write-check-",
            delete=False,
        ) as handle:
            handle.write("bootstrap-ok\n")
            marker_path = Path(handle.name)
    except OSError as exc:
        _raise_failure(
            step=label,
            kind="path_not_writable",
            cause=f"{label} directory {path} is not writable: {_exception_message(exc)}",
        )
    finally:
        if marker_path is not None and marker_path.exists():
            marker_path.unlink()

    return {
        "path": str(path),
        "exists": True,
        "writable": True,
        "free_bytes": free_bytes,
    }


def _maybe_update_manifest(
    *,
    run_root: Path,
    environment_path: Path,
    gpu_id: int,
    failure: BootstrapFailure | None,
    experiment_type: str,
    manifest_metadata: Mapping[str, Any] | None,
) -> dict[str, Any]:
    manifest_path = run_root / paths.RUN_MANIFEST_FILENAME
    manifest_payload = _read_json_object(manifest_path)
    if (
        isinstance(manifest_payload, dict)
        and "stage_status" in manifest_payload
        and "stages" not in manifest_payload
    ):
        return {
            "attempted": True,
            "status": "skipped_legacy_manifest",
            "path": str(manifest_path),
            "error": None,
        }

    try:
        bundle_paths = paths.bundle_paths_from_run_root(run_root)
        if not manifest_path.exists() or not manifest_payload:
            schema_version, metadata = experiments.split_manifest_metadata(
                {
                    **experiments.metadata_for_experiment(experiment_type),
                    **dict(manifest_metadata or {}),
                }
            )
            manifests.initialize_run_manifest(
                bundle_paths,
                schema_version=schema_version,
                metadata=metadata,
            )
        manifests.update_stage_status(
            manifest_path,
            stage=_BOOTSTRAP_STAGE_NAME,
            status="success" if failure is None else failure.public_status,
            details={
                "environment_path": environment_path.relative_to(run_root).as_posix(),
                "gpu_id": gpu_id,
                "failure_kind": None if failure is None else failure.failure_kind,
                "failure_cause": None if failure is None else failure.failure_cause,
            },
            final_status=None if failure is None else failure.public_status,
        )
    except Exception as exc:
        return {
            "attempted": True,
            "status": "failed",
            "path": str(manifest_path),
            "error": _exception_message(exc),
        }

    return {
        "attempted": True,
        "status": "updated",
        "path": str(manifest_path),
        "error": None,
    }


def _read_json_object(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if isinstance(loaded, dict):
        return loaded
    return None


def _read_pyvenv_cfg(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if not separator:
            continue
        values[key.strip().lower()] = value.strip()
    return values


def _venv_python_path(venv_path: Path) -> Path:
    if sys.platform.startswith("win"):
        return venv_path / "Scripts" / "python.exe"
    return venv_path / "bin" / "python"


def _compute_capability(properties: Any) -> str | None:
    major = getattr(properties, "major", None)
    minor = getattr(properties, "minor", None)
    if major is None or minor is None:
        return None
    return f"{major}.{minor}"


def _probe_cuda_driver_version(gpu_id: int) -> str | None:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=driver_version",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if result.returncode != 0:
        return None

    versions = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not versions:
        return None
    if 0 <= gpu_id < len(versions):
        return versions[gpu_id]
    return versions[0]


def _write_json_file(path: Path, payload: dict[str, Any]) -> None:
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


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _raise_failure(*, step: str, kind: str, cause: str) -> None:
    raise _BootstrapCheckFailed(
        BootstrapFailure(
            failure_kind=kind,
            failure_cause=cause,
            step=step,
        )
    )


def _normalize_non_negative_int(value: int, *, name: str) -> int:
    normalized = int(value)
    if normalized < 0:
        raise ValueError(f"{name} must be non-negative")
    return normalized


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


def _exception_message(exc: Exception) -> str:
    if exc.args:
        return str(exc.args[0])
    return str(exc)


__all__ = [
    "BootstrapEnvironmentError",
    "BootstrapFailure",
    "BootstrapResult",
    "bootstrap_environment",
]
