from __future__ import annotations

import json
import re
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from typing import Any
from urllib import error, request

from ai_runtime_experiments.docker_criu.probe import _classify_result
from ai_runtime_experiments.runtime_adapters.base import (
    BaseRuntimeAdapter,
    RuntimeSession,
    make_unavailable_smoke_validation,
)
from ai_runtime_experiments.schemas import ProbeStatus, make_probe_result
from ai_runtime_experiments.utils.command import CommandResult, run_command

DEFAULT_LLAMA_CPP_IMAGE = "ghcr.io/ggml-org/llama.cpp:server"
DEFAULT_LLAMA_CPP_HOST_PORT = 8080
DEFAULT_LLAMA_CPP_CONTAINER_PORT = 8080
DEFAULT_LLAMA_CPP_MODEL_DIR = "/models"
DEFAULT_LLAMA_CPP_THREADS = 4
DEFAULT_LLAMA_CPP_CTX_SIZE = 2048
DEFAULT_LLAMA_CPP_IMAGE_PULL_TIMEOUT_S = 900.0
EXPERIMENT_CONTAINER_NAME_PREFIX = "ai-edge-v0-llama-cpp-"
EXPERIMENT_LABEL_KEY = "ai-edge-experiment"
EXPERIMENT_LABEL_VALUE = "v0"
EXPERIMENT_COMPONENT_LABEL_KEY = "ai-edge-component"
EXPERIMENT_COMPONENT_LABEL_VALUE = "llama-cpp-runtime"
EXPERIMENT_RUN_ID_LABEL_KEY = "ai-edge-run-id"
DEFAULT_READINESS_REQUEST_TIMEOUT_S = 2.0
DEFAULT_READINESS_POLL_INTERVAL_S = 0.5
_DOCKER_NAME_SAFE_RE = re.compile(r"[^a-z0-9_.-]+")


def _slug(value: str, *, default: str) -> str:
    slug = _DOCKER_NAME_SAFE_RE.sub("-", value.lower().strip()).strip("-.")
    return slug or default


def build_llama_cpp_container_name(run_id: str, *, token: str | None = None) -> str:
    run_fragment = _slug(run_id, default="run")[:24]
    token_fragment = _slug(token or uuid.uuid4().hex[:8], default="token")[:12]
    return f"{EXPERIMENT_CONTAINER_NAME_PREFIX}{run_fragment}-{token_fragment}".rstrip("-")


def build_llama_cpp_labels(run_id: str) -> dict[str, str]:
    return {
        EXPERIMENT_LABEL_KEY: EXPERIMENT_LABEL_VALUE,
        EXPERIMENT_COMPONENT_LABEL_KEY: EXPERIMENT_COMPONENT_LABEL_VALUE,
        EXPERIMENT_RUN_ID_LABEL_KEY: run_id,
    }


def build_llama_cpp_label_args(run_id: str) -> list[str]:
    args: list[str] = []
    for key, value in build_llama_cpp_labels(run_id).items():
        args.extend(["--label", f"{key}={value}"])
    return args


def parse_llama_cpp_label_mapping(text: str) -> dict[str, str] | None:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(value, dict):
        return None
    parsed: dict[str, str] = {}
    for key, item in value.items():
        if isinstance(key, str) and isinstance(item, str):
            parsed[key] = item
    return parsed


def is_experiment_owned_llama_cpp_container(*, container_name: str, labels: Mapping[str, str]) -> bool:
    if not container_name.startswith(EXPERIMENT_CONTAINER_NAME_PREFIX):
        return False
    if labels.get(EXPERIMENT_LABEL_KEY) != EXPERIMENT_LABEL_VALUE:
        return False
    if labels.get(EXPERIMENT_COMPONENT_LABEL_KEY) != EXPERIMENT_COMPONENT_LABEL_VALUE:
        return False
    run_id = labels.get(EXPERIMENT_RUN_ID_LABEL_KEY)
    return isinstance(run_id, str) and bool(run_id.strip())


def ensure_experiment_owned_llama_cpp_container(*, container_name: str, labels: Mapping[str, str]) -> None:
    if not is_experiment_owned_llama_cpp_container(container_name=container_name, labels=labels):
        raise ValueError(
            "refusing destructive Docker action because container is not experiment-owned: "
            f"{container_name}"
        )


def build_llama_cpp_docker_command(
    *,
    run_id: str,
    image: str,
    model_file: str,
    container_name: str,
    host_port: int,
    host_model_dir: str,
    container_model_dir: str = DEFAULT_LLAMA_CPP_MODEL_DIR,
    threads: int = DEFAULT_LLAMA_CPP_THREADS,
    ctx_size: int = DEFAULT_LLAMA_CPP_CTX_SIZE,
    n_gpu_layers: int = 0,
    network_mode: str | None = "host",
    extra_args: Sequence[str] | None = None,
) -> list[str]:
    model_path = f"{container_model_dir.rstrip('/')}/{model_file}"
    command = [
        "docker",
        "run",
        "-d",
        "--name",
        container_name,
        *build_llama_cpp_label_args(run_id),
    ]
    if network_mode:
        command.extend(["--network", network_mode])
    if network_mode != "host":
        command.extend(["-p", f"127.0.0.1:{host_port}:{DEFAULT_LLAMA_CPP_CONTAINER_PORT}"])
    command.extend([
        "-v",
        f"{host_model_dir}:{container_model_dir}:ro",
        image,
        "-m",
        model_path,
        "--host",
        "0.0.0.0",
        "--port",
        str(DEFAULT_LLAMA_CPP_CONTAINER_PORT),
        "--threads",
        str(threads),
        "--ctx-size",
        str(ctx_size),
    ])
    if n_gpu_layers > 0:
        command.extend(["--n-gpu-layers", str(n_gpu_layers)])
    if extra_args:
        command.extend(str(item) for item in extra_args)
    return command


def _normalize_base_url(base_url: str | None) -> str | None:
    if base_url is None:
        return None
    normalized = str(base_url).strip().rstrip("/")
    return normalized or None


def _models_url(base_url: str) -> str:
    return f"{base_url}/models"


def _probe_llama_cpp_readiness(*, base_url: str, timeout_s: float) -> tuple[ProbeStatus, dict[str, Any]]:
    models_url = _models_url(base_url)
    attempts = 0
    last_error: str | None = None
    total_timeout_s = max(float(timeout_s), 0.0)
    request_timeout_s = max(
        0.1,
        min(
            DEFAULT_READINESS_REQUEST_TIMEOUT_S,
            total_timeout_s or DEFAULT_READINESS_REQUEST_TIMEOUT_S,
        ),
    )
    deadline = time.monotonic() + total_timeout_s

    while True:
        attempts += 1
        try:
            with request.urlopen(models_url, timeout=request_timeout_s) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if isinstance(payload, Mapping) and isinstance(payload.get("data"), list):
                return ProbeStatus.OK, {"models_url": models_url, "attempts": attempts}
            last_error = "response missing OpenAI-compatible models data"
        except (error.URLError, TimeoutError, OSError, ValueError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"

        remaining_s = deadline - time.monotonic()
        if remaining_s <= 0:
            return ProbeStatus.TIMEOUT, {
                "models_url": models_url,
                "attempts": attempts,
                "reason": "timed out waiting for /v1/models",
                "last_error": last_error,
            }
        time.sleep(min(DEFAULT_READINESS_POLL_INTERVAL_S, remaining_s))


def _command_details(result: CommandResult) -> dict[str, Any]:
    return {
        "argv": result.argv,
        "status": result.status.value,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "timed_out": result.timed_out,
        "duration_s": result.duration_s,
        "error_type": result.error_type,
        "error_message": result.error_message,
    }


def _reason_for_status(*, status: ProbeStatus, mode: str) -> str:
    if status == ProbeStatus.SKIPPED:
        return "no runtime URL configured and docker runtime start disabled"
    if status == ProbeStatus.UNSUPPORTED:
        return f"{mode} runtime support is unavailable on this host"
    if status == ProbeStatus.TIMEOUT:
        return f"{mode} runtime startup timed out"
    return f"{mode} runtime startup failed"


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


class LlamaCppRuntimeAdapter(BaseRuntimeAdapter):
    def __init__(
        self,
        *,
        config: Mapping[str, Any],
        runner=run_command,
        timeout_s: float = 30.0,
        readiness_probe: Callable[..., tuple[ProbeStatus, dict[str, Any]]] = _probe_llama_cpp_readiness,
    ) -> None:
        self.config = dict(config)
        self.runner = runner
        self.timeout_s = timeout_s
        self.readiness_probe = readiness_probe

    def start(self, *, run_id: str) -> RuntimeSession:
        external_config = _mapping(self.config.get("external_server"))
        external_enabled = bool(external_config.get("enabled"))
        external_base_url = _normalize_base_url(external_config.get("base_url"))
        if external_enabled and external_base_url is not None:
            return self._resolve_ready_session(
                run_id=run_id,
                mode="external_server",
                base_url=external_base_url,
                details={"runtime": "llama_cpp", "mode": "external_server", "base_url": external_base_url},
            )

        docker_config = _mapping(self.config.get("docker_server"))
        if docker_config.get("enabled"):
            return self._start_docker_server(run_id=run_id, docker_config=docker_config)

        reason = _reason_for_status(status=ProbeStatus.SKIPPED, mode="skipped")
        runtime_check = make_probe_result(
            run_id=run_id,
            component="runtime_check",
            status=ProbeStatus.SKIPPED,
            details={"runtime": "llama_cpp", "mode": "skipped", "reason": reason},
        )
        smoke_validation = make_unavailable_smoke_validation(
            run_id=run_id,
            status=ProbeStatus.SKIPPED,
            reason=reason,
            details={"runtime": "llama_cpp", "mode": "skipped"},
        )
        return RuntimeSession(
            runtime="llama_cpp",
            mode="skipped",
            status=ProbeStatus.SKIPPED,
            runtime_check=runtime_check,
            smoke_validation=smoke_validation,
        )

    def _resolve_ready_session(
        self,
        *,
        run_id: str,
        mode: str,
        base_url: str,
        details: Mapping[str, Any],
        container_name: str | None = None,
        container_id: str | None = None,
    ) -> RuntimeSession:
        status, readiness_details = self.readiness_probe(base_url=base_url, timeout_s=self.timeout_s)
        merged_details = dict(details)
        merged_details.update(readiness_details)
        if status != ProbeStatus.OK:
            reason = str(merged_details.get("reason") or _reason_for_status(status=status, mode=mode))
            merged_details["reason"] = reason
            runtime_check = make_probe_result(
                run_id=run_id,
                component="runtime_check",
                status=status,
                details=merged_details,
            )
            smoke_validation = make_unavailable_smoke_validation(
                run_id=run_id,
                status=status,
                reason=reason,
                details={"runtime": "llama_cpp", "mode": mode, "base_url": base_url},
            )
            return RuntimeSession(
                runtime="llama_cpp",
                mode=mode,
                status=status,
                runtime_check=runtime_check,
                smoke_validation=smoke_validation,
                container_name=container_name,
                container_id=container_id,
            )
        runtime_check = make_probe_result(
            run_id=run_id,
            component="runtime_check",
            status=ProbeStatus.OK,
            details=merged_details,
        )
        return RuntimeSession(
            runtime="llama_cpp",
            mode=mode,
            status=ProbeStatus.OK,
            base_url=base_url,
            runtime_check=runtime_check,
            container_name=container_name,
            container_id=container_id,
        )

    def _start_docker_server(self, *, run_id: str, docker_config: Mapping[str, Any]) -> RuntimeSession:
        model_file = str(docker_config.get("model_file") or "").strip()
        host_model_dir = str(docker_config.get("host_model_dir") or "").strip()
        container_name = str(
            docker_config.get("container_name") or build_llama_cpp_container_name(run_id)
        )
        image = str(docker_config.get("image") or DEFAULT_LLAMA_CPP_IMAGE)
        host_port = int(docker_config.get("port") or DEFAULT_LLAMA_CPP_HOST_PORT)
        container_model_dir = str(docker_config.get("container_model_dir") or DEFAULT_LLAMA_CPP_MODEL_DIR)
        threads = int(docker_config.get("threads") or DEFAULT_LLAMA_CPP_THREADS)
        ctx_size = int(docker_config.get("ctx_size") or DEFAULT_LLAMA_CPP_CTX_SIZE)
        n_gpu_layers = int(docker_config.get("n_gpu_layers") or 0)
        network_mode = str(docker_config.get("network_mode") or "host")
        image_pull_timeout_s = float(
            docker_config.get("image_pull_timeout_s") or DEFAULT_LLAMA_CPP_IMAGE_PULL_TIMEOUT_S
        )
        base_url = f"http://127.0.0.1:{host_port}/v1"
        details: dict[str, Any] = {
            "runtime": "llama_cpp",
            "mode": "docker_server",
            "commands": {},
            "container": {
                "name": container_name,
                "image": image,
                "host_port": host_port,
                "container_port": DEFAULT_LLAMA_CPP_CONTAINER_PORT,
                "host_model_dir": host_model_dir,
                "container_model_dir": container_model_dir,
                "model_file": model_file,
                "network_mode": network_mode,
            },
        }
        if not model_file or not host_model_dir:
            reason = "docker_server.enabled requires host_model_dir and model_file"
            runtime_check = make_probe_result(
                run_id=run_id,
                component="runtime_check",
                status=ProbeStatus.ERROR,
                details={**details, "reason": reason},
            )
            smoke_validation = make_unavailable_smoke_validation(
                run_id=run_id,
                status=ProbeStatus.ERROR,
                reason=reason,
                details={"runtime": "llama_cpp", "mode": "docker_server"},
            )
            return RuntimeSession(
                runtime="llama_cpp",
                mode="docker_server",
                status=ProbeStatus.ERROR,
                runtime_check=runtime_check,
                smoke_validation=smoke_validation,
                container_name=container_name,
            )

        inspect_image_result = self.runner(["docker", "image", "inspect", image], timeout_s=self.timeout_s)
        details["commands"]["docker_image_inspect"] = _command_details(inspect_image_result)
        inspect_status, inspect_reason = _classify_result(
            inspect_image_result,
            command_label="docker image inspect",
            capability_sensitive=True,
        )
        if inspect_status == ProbeStatus.UNSUPPORTED:
            details["reason"] = inspect_reason or "docker image inspect is unavailable"
            runtime_check = make_probe_result(
                run_id=run_id,
                component="runtime_check",
                status=ProbeStatus.UNSUPPORTED,
                details=details,
            )
            smoke_validation = make_unavailable_smoke_validation(
                run_id=run_id,
                status=ProbeStatus.UNSUPPORTED,
                reason=details["reason"],
                details={"runtime": "llama_cpp", "mode": "docker_server"},
            )
            return RuntimeSession(
                runtime="llama_cpp",
                mode="docker_server",
                status=ProbeStatus.UNSUPPORTED,
                runtime_check=runtime_check,
                smoke_validation=smoke_validation,
                container_name=container_name,
            )
        if inspect_image_result.status != ProbeStatus.OK:
            pull_result = self.runner(["docker", "pull", image], timeout_s=image_pull_timeout_s)
            details["commands"]["docker_pull"] = _command_details(pull_result)
            pull_status, pull_reason = _classify_result(
                pull_result,
                command_label="docker pull",
                capability_sensitive=True,
            )
            if pull_status != ProbeStatus.OK:
                details["reason"] = pull_reason or "docker image pull failed"
                runtime_check = make_probe_result(
                    run_id=run_id,
                    component="runtime_check",
                    status=pull_status,
                    details=details,
                )
                smoke_validation = make_unavailable_smoke_validation(
                    run_id=run_id,
                    status=pull_status,
                    reason=details["reason"],
                    details={"runtime": "llama_cpp", "mode": "docker_server"},
                )
                return RuntimeSession(
                    runtime="llama_cpp",
                    mode="docker_server",
                    status=pull_status,
                    runtime_check=runtime_check,
                    smoke_validation=smoke_validation,
                    container_name=container_name,
                )

        command = build_llama_cpp_docker_command(
            run_id=run_id,
            image=image,
            model_file=model_file,
            container_name=container_name,
            host_port=host_port,
            host_model_dir=host_model_dir,
            container_model_dir=container_model_dir,
            threads=threads,
            ctx_size=ctx_size,
            n_gpu_layers=n_gpu_layers,
            network_mode=network_mode,
            extra_args=docker_config.get("extra_args"),
        )
        result = self.runner(command, timeout_s=self.timeout_s)
        details["commands"]["docker_run"] = _command_details(result)
        status = result.status if result.status != ProbeStatus.ERROR else ProbeStatus.ERROR
        container_id = result.stdout.strip() or None
        if container_id is not None:
            details["container"]["id"] = container_id
        if status != ProbeStatus.OK:
            details["reason"] = _reason_for_status(status=status, mode="docker_server")
            runtime_check = make_probe_result(
                run_id=run_id,
                component="runtime_check",
                status=status,
                details=details,
            )
            smoke_validation = make_unavailable_smoke_validation(
                run_id=run_id,
                status=status,
                reason=details["reason"],
                details={"runtime": "llama_cpp", "mode": "docker_server"},
            )
            return RuntimeSession(
                runtime="llama_cpp",
                mode="docker_server",
                status=status,
                runtime_check=runtime_check,
                smoke_validation=smoke_validation,
                container_name=container_name,
                container_id=container_id,
            )

        details["base_url"] = base_url
        return self._resolve_ready_session(
            run_id=run_id,
            mode="docker_server",
            base_url=base_url,
            details=details,
            container_name=container_name,
            container_id=container_id,
        )

    def stop(self, session: RuntimeSession) -> dict[str, Any] | None:
        if session.mode != "docker_server" or not session.container_name:
            return None
        details: dict[str, Any] = {
            "runtime": session.runtime,
            "mode": session.mode,
            "container": {"name": session.container_name},
            "commands": {},
        }
        inspect_labels_result = self.runner(
            ["docker", "inspect", "--format", "{{json .Config.Labels}}", session.container_name],
            timeout_s=self.timeout_s,
        )
        details["commands"]["docker_inspect_labels"] = _command_details(inspect_labels_result)
        inspect_status, inspect_reason = _classify_result(inspect_labels_result, command_label="docker inspect labels")
        if inspect_status != ProbeStatus.OK:
            details["reason"] = inspect_reason or "unable to inspect runtime labels"
            return make_probe_result(
                run_id=session.runtime_check["run_id"],
                component="runtime_teardown",
                status=inspect_status,
                details=details,
            )
        labels = parse_llama_cpp_label_mapping(inspect_labels_result.stdout)
        if labels is None:
            details["reason"] = "unable to parse docker inspect labels JSON"
            return make_probe_result(
                run_id=session.runtime_check["run_id"],
                component="runtime_teardown",
                status=ProbeStatus.ERROR,
                details=details,
            )
        details["container"]["inspected_labels"] = labels
        try:
            ensure_experiment_owned_llama_cpp_container(
                container_name=session.container_name,
                labels=labels,
            )
        except ValueError as exc:
            details["reason"] = str(exc)
            return make_probe_result(
                run_id=session.runtime_check["run_id"],
                component="runtime_teardown",
                status=ProbeStatus.ERROR,
                details=details,
            )
        result = self.runner(["docker", "rm", "-f", session.container_name], timeout_s=self.timeout_s)
        details["commands"]["docker_rm_force"] = _command_details(result)
        status, reason = _classify_result(result, command_label="docker rm -f")
        if status != ProbeStatus.OK:
            details["reason"] = reason or "runtime teardown failed"
        return make_probe_result(
            run_id=session.runtime_check["run_id"],
            component="runtime_teardown",
            status=status,
            details=details,
        )
