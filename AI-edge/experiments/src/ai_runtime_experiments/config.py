from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from ai_runtime_experiments.docker_criu.probe import (
    DEFAULT_CHECKPOINT_NAME,
    DEFAULT_POST_CHECKPOINT_DELAY_S,
    DEFAULT_SMOKE_IMAGE,
    DEFAULT_SMOKE_NETWORK_MODE,
    DEFAULT_SMOKE_RUNTIME,
)
from ai_runtime_experiments.env_probe.cuda import DEFAULT_CUDA_IMAGE
from ai_runtime_experiments.env_probe.mps import (
    DEFAULT_MPS_CONTROL_BINARY,
    DEFAULT_MPS_CONTROL_PIPE_PATH,
)
from ai_runtime_experiments.runtime_adapters.llama_cpp import (
    DEFAULT_LLAMA_CPP_CTX_SIZE,
    DEFAULT_LLAMA_CPP_HOST_PORT,
    DEFAULT_LLAMA_CPP_IMAGE,
    DEFAULT_LLAMA_CPP_IMAGE_PULL_TIMEOUT_S,
    DEFAULT_LLAMA_CPP_MODEL_DIR,
    DEFAULT_LLAMA_CPP_THREADS,
)
from ai_runtime_experiments.runtime_adapters.vllm import (
    DEFAULT_DOCKER_IMAGE,
    DEFAULT_HOST_PORT,
    DEFAULT_IMAGE_PULL_TIMEOUT_S,
)

_ALLOWED_RUNTIMES = {"vllm", "llama_cpp"}
_REQUIRED_KEYS = (
    "experiment_id",
    "version",
    "runtime",
    "model",
    "arm",
    "workload",
    "preemption_policy",
    "resource_delta",
    "telemetry",
    "output_dir",
    "seed",
)
_DEFAULT_WORKLOAD = {
    "prompt": "Respond with the exact text 'smoke ok'.",
    "temperature": 0.0,
    "max_tokens": 64,
    "timeout_s": 30.0,
}
_DEFAULT_RUNTIME_OPTIONS = {
    "llama_cpp": {
        "external_server": {
            "enabled": False,
            "base_url": None,
        },
        "docker_server": {
            "enabled": False,
            "image": DEFAULT_LLAMA_CPP_IMAGE,
            "port": DEFAULT_LLAMA_CPP_HOST_PORT,
            "container_name": None,
            "extra_args": [],
            "image_pull_timeout_s": DEFAULT_LLAMA_CPP_IMAGE_PULL_TIMEOUT_S,
            "host_model_dir": None,
            "container_model_dir": DEFAULT_LLAMA_CPP_MODEL_DIR,
            "model_file": None,
            "threads": DEFAULT_LLAMA_CPP_THREADS,
            "ctx_size": DEFAULT_LLAMA_CPP_CTX_SIZE,
            "n_gpu_layers": 0,
            "network_mode": "host",
        },
    },
    "vllm": {
        "external_server": {
            "enabled": False,
            "base_url": None,
        },
        "docker_server": {
            "enabled": False,
            "image": DEFAULT_DOCKER_IMAGE,
            "port": DEFAULT_HOST_PORT,
            "container_name": None,
            "extra_args": [],
            "image_pull_timeout_s": DEFAULT_IMAGE_PULL_TIMEOUT_S,
            "model": None,
            "network_mode": None,
            "gpu_mode": "gpus_flag",
            "gpu_device": "nvidia.com/gpu=all",
        },
    }
}
_DEFAULT_PROBE_OPTIONS = {
    "hardware": {"timeout_s": 5.0},
    "docker": {"timeout_s": 5.0},
    "criu": {"timeout_s": 10.0},
    "docker_criu_integration": {
        "timeout_s": 60.0,
        "checkpoint_name": DEFAULT_CHECKPOINT_NAME,
        "smoke_image": DEFAULT_SMOKE_IMAGE,
        "smoke_runtime": DEFAULT_SMOKE_RUNTIME,
        "network_mode": DEFAULT_SMOKE_NETWORK_MODE,
        "post_checkpoint_delay_s": DEFAULT_POST_CHECKPOINT_DELAY_S,
    },
    "cuda": {
        "timeout_s": 120.0,
        "image": DEFAULT_CUDA_IMAGE,
    },
    "mps": {
        "timeout_s": 5.0,
        "allow_start_stop": False,
        "control_binary": DEFAULT_MPS_CONTROL_BINARY,
        "control_pipe_path": DEFAULT_MPS_CONTROL_PIPE_PATH,
    },
    "runtime": {"timeout_s": 180.0},
    "preemption": {
        "timeout_s": 180.0,
        "checkpoint_name": DEFAULT_CHECKPOINT_NAME,
        "criu_config_mode": None,
        "criu_config_allow_sudo": False,
    },
}


@dataclass(frozen=True)
class ResolvedConfig:
    config_path: Path
    experiment_id: str
    version: str
    runtime: str
    model: str | None
    arm: str
    workload: dict[str, Any]
    preemption_policy: dict[str, Any]
    resource_delta: dict[str, Any]
    telemetry: dict[str, Any]
    output_dir: Path
    seed: int
    dry_run: bool
    run_id: str
    runtime_options: dict[str, Any]
    probe_options: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "version": self.version,
            "runtime": self.runtime,
            "model": self.model,
            "arm": self.arm,
            "workload": deepcopy(self.workload),
            "preemption_policy": deepcopy(self.preemption_policy),
            "resource_delta": deepcopy(self.resource_delta),
            "telemetry": deepcopy(self.telemetry),
            "output_dir": str(self.output_dir),
            "seed": self.seed,
            "dry_run": self.dry_run,
            "run_id": self.run_id,
            "runtime_options": deepcopy(self.runtime_options),
            "probe_options": deepcopy(self.probe_options),
            "config_path": str(self.config_path),
        }



def _deep_merge(defaults: Mapping[str, Any], overrides: Mapping[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = deepcopy(dict(defaults))
    for key, value in overrides.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged



def _ensure_mapping(value: Any, *, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping")
    return dict(value)



def _normalize_output_dir(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()



def _derive_run_id(*, output_dir: Path, experiment_id: str) -> str:
    run_id = output_dir.name.strip()
    return run_id or experiment_id



def _load_yaml_mapping(config_path: Path) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError("config must use safe YAML features") from exc

    if not isinstance(loaded, Mapping):
        raise ValueError("config root must be a mapping")
    return dict(loaded)



def _validate_required_keys(raw_config: Mapping[str, Any]) -> None:
    missing = [key for key in _REQUIRED_KEYS if key not in raw_config]
    if missing:
        raise ValueError(f"config is missing required keys: {missing}")



def load_config(
    config_path: str | Path,
    *,
    output_dir_override: str | Path | None = None,
    dry_run: bool = False,
) -> ResolvedConfig:
    resolved_path = Path(config_path).expanduser().resolve()
    raw_config = _load_yaml_mapping(resolved_path)
    _validate_required_keys(raw_config)

    runtime = str(raw_config.get("runtime") or "").strip().lower()
    if runtime not in _ALLOWED_RUNTIMES:
        raise ValueError(f"unsupported runtime: {runtime!r}")

    experiment_id = str(raw_config.get("experiment_id") or "").strip()
    if not experiment_id:
        raise ValueError("experiment_id must be non-empty")

    output_dir_value = output_dir_override if output_dir_override is not None else raw_config["output_dir"]
    output_dir = _normalize_output_dir(output_dir_value)
    run_id = _derive_run_id(output_dir=output_dir, experiment_id=experiment_id)

    workload = _deep_merge(_DEFAULT_WORKLOAD, _ensure_mapping(raw_config.get("workload"), field_name="workload"))
    runtime_options = _deep_merge(
        _DEFAULT_RUNTIME_OPTIONS,
        _ensure_mapping(raw_config.get("runtime_options"), field_name="runtime_options"),
    )
    probe_options = _deep_merge(
        _DEFAULT_PROBE_OPTIONS,
        _ensure_mapping(raw_config.get("probe_options"), field_name="probe_options"),
    )

    model = raw_config.get("model")
    normalized_model = None if model is None else str(model).strip() or None
    if normalized_model is not None:
        runtime_options["vllm"]["docker_server"]["model"] = normalized_model
        runtime_options["llama_cpp"]["docker_server"]["model_file"] = normalized_model

    seed_value = raw_config.get("seed")
    if seed_value is None:
        raise ValueError("seed must be present")

    return ResolvedConfig(
        config_path=resolved_path,
        experiment_id=experiment_id,
        version=str(raw_config.get("version") or "").strip(),
        runtime=runtime,
        model=normalized_model,
        arm=str(raw_config.get("arm") or "").strip(),
        workload=workload,
        preemption_policy=_ensure_mapping(raw_config.get("preemption_policy"), field_name="preemption_policy"),
        resource_delta=_ensure_mapping(raw_config.get("resource_delta"), field_name="resource_delta"),
        telemetry=_ensure_mapping(raw_config.get("telemetry"), field_name="telemetry"),
        output_dir=output_dir,
        seed=int(seed_value),
        dry_run=bool(dry_run),
        run_id=run_id,
        runtime_options=runtime_options,
        probe_options=probe_options,
    )



def dump_config_yaml(config: ResolvedConfig, path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(config.to_dict(), sort_keys=False),
        encoding="utf-8",
    )
