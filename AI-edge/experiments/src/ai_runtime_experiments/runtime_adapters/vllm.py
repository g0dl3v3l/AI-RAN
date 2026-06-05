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

DEFAULT_DOCKER_IMAGE = "vllm/vllm-openai:latest"
DEFAULT_HOST_PORT = 8000
DEFAULT_CONTAINER_PORT = 8000
EXPERIMENT_CONTAINER_NAME_PREFIX = "ai-edge-v0-vllm-"
EXPERIMENT_LABEL_KEY = "ai-edge-experiment"
EXPERIMENT_LABEL_VALUE = "v0"
EXPERIMENT_COMPONENT_LABEL_KEY = "ai-edge-component"
EXPERIMENT_COMPONENT_LABEL_VALUE = "vllm-runtime"
EXPERIMENT_RUN_ID_LABEL_KEY = "ai-edge-run-id"
DEFAULT_READINESS_REQUEST_TIMEOUT_S = 2.0
DEFAULT_READINESS_POLL_INTERVAL_S = 0.5
_DOCKER_NAME_SAFE_RE = re.compile(r"[^a-z0-9_.-]+")



def _slug(value: str, *, default: str) -> str:
    slug = _DOCKER_NAME_SAFE_RE.sub("-", value.lower().strip()).strip("-.")
    return slug or default



def build_vllm_container_name(run_id: str, *, token: str | None = None) -> str:
    run_fragment = _slug(run_id, default="run")[:24]
    token_fragment = _slug(token or uuid.uuid4().hex[:8], default="token")[:12]
    return f"{EXPERIMENT_CONTAINER_NAME_PREFIX}{run_fragment}-{token_fragment}".rstrip("-")



def build_vllm_labels(run_id: str) -> dict[str, str]:
    return {
        EXPERIMENT_LABEL_KEY: EXPERIMENT_LABEL_VALUE,
        EXPERIMENT_COMPONENT_LABEL_KEY: EXPERIMENT_COMPONENT_LABEL_VALUE,
        EXPERIMENT_RUN_ID_LABEL_KEY: run_id,
    }



def build_vllm_label_args(run_id: str) -> list[str]:
    args: list[str] = []
    for key, value in build_vllm_labels(run_id).items():
        args.extend(["--label", f"{key}={value}"])
    return args



def parse_vllm_label_mapping(text: str) -> dict[str, str] | None:
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



def is_experiment_owned_vllm_container(*, container_name: str, labels: Mapping[str, str]) -> bool:
    if not container_name.startswith(EXPERIMENT_CONTAINER_NAME_PREFIX):
        return False
    if labels.get(EXPERIMENT_LABEL_KEY) != EXPERIMENT_LABEL_VALUE:
        return False
    if labels.get(EXPERIMENT_COMPONENT_LABEL_KEY) != EXPERIMENT_COMPONENT_LABEL_VALUE:
        return False
    run_id = labels.get(EXPERIMENT_RUN_ID_LABEL_KEY)
    return isinstance(run_id, str) and bool(run_id.strip())



def ensure_experiment_owned_vllm_container(*, container_name: str, labels: Mapping[str, str]) -> None:
    if not is_experiment_owned_vllm_container(container_name=container_name, labels=labels):
        raise ValueError(
            "refusing destructive Docker action because container is not experiment-owned: "
            f"{container_name}"
        )



def build_vllm_docker_command(
    *,
    run_id: str,
    image: str,
    model: str,
    container_name: str,
    host_port: int,
    extra_args: Sequence[str] | None = None,
) -> list[str]:
    command = [
        "docker",
        "run",
        "-d",
        "--name",
        container_name,
        *build_vllm_label_args(run_id),
        "-p",
        f"127.0.0.1:{host_port}:{DEFAULT_CONTAINER_PORT}",
        "--gpus",
        "all",
        image,
        "--model",
        model,
        "--host",
        "0.0.0.0",
        "--port",
        str(DEFAULT_CONTAINER_PORT),
    ]
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



def _probe_vllm_readiness(*, base_url: str, timeout_s: float) -> tuple[ProbeStatus, dict[str, Any]]:
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
                return ProbeStatus.OK, {
                    "models_url": models_url,
                    "attempts": attempts,
                }
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



class VLLMRuntimeAdapter(BaseRuntimeAdapter):
    def __init__(
        self,
        *,
        config: Mapping[str, Any],
        runner=run_command,
        timeout_s: float = 30.0,
        readiness_probe: Callable[..., tuple[ProbeStatus, dict[str, Any]]] = _probe_vllm_readiness,
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
                details={
                    "runtime": "vllm",
                    "mode": "external_server",
                    "base_url": external_base_url,
                },
            )

        docker_config = _mapping(self.config.get("docker_server"))
        if docker_config.get("enabled"):
            return self._start_docker_server(run_id=run_id, docker_config=docker_config)

        reason = _reason_for_status(status=ProbeStatus.SKIPPED, mode="skipped")
        runtime_check = make_probe_result(
            run_id=run_id,
            component="runtime_check",
            status=ProbeStatus.SKIPPED,
            details={
                "runtime": "vllm",
                "mode": "skipped",
                "reason": reason,
            },
        )
        smoke_validation = make_unavailable_smoke_validation(
            run_id=run_id,
            status=ProbeStatus.SKIPPED,
            reason=reason,
            details={"runtime": "vllm", "mode": "skipped"},
        )
        return RuntimeSession(
            runtime="vllm",
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
        status, readiness_details = self.readiness_probe(
            base_url=base_url,
            timeout_s=self.timeout_s,
        )
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
                details={
                    "runtime": "vllm",
                    "mode": mode,
                    "base_url": base_url,
                },
            )
            return RuntimeSession(
                runtime="vllm",
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
            runtime="vllm",
            mode=mode,
            status=ProbeStatus.OK,
            base_url=base_url,
            runtime_check=runtime_check,
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
        if session.container_id is not None:
            details["container"]["id"] = session.container_id

        inspect_labels_result = self.runner(
            ["docker", "inspect", "--format", "{{json .Config.Labels}}", session.container_name],
            timeout_s=self.timeout_s,
        )
        details["commands"]["docker_inspect_labels"] = _command_details(inspect_labels_result)
        inspect_status, inspect_reason = _classify_result(
            inspect_labels_result,
            command_label="docker inspect labels",
        )
        if inspect_status != ProbeStatus.OK:
            details["reason"] = inspect_reason or "unable to inspect runtime labels"
            return make_probe_result(
                run_id=session.runtime_check["run_id"],
                component="runtime_teardown",
                status=inspect_status,
                details=details,
            )

        labels = parse_vllm_label_mapping(inspect_labels_result.stdout)
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
            ensure_experiment_owned_vllm_container(
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

        result = self.runner(
            ["docker", "rm", "-f", session.container_name],
            timeout_s=self.timeout_s,
        )
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

    def _start_docker_server(
        self,
        *,
        run_id: str,
        docker_config: Mapping[str, Any],
    ) -> RuntimeSession:
        model = str(docker_config.get("model") or "").strip()
        container_name = str(
            docker_config.get("container_name") or build_vllm_container_name(run_id)
        )
        image = str(docker_config.get("image") or DEFAULT_DOCKER_IMAGE)
        host_port = int(docker_config.get("port") or DEFAULT_HOST_PORT)

        if not model:
            status = ProbeStatus.ERROR
            reason = "docker_server.enabled requires a non-empty model"
            runtime_check = make_probe_result(
                run_id=run_id,
                component="runtime_check",
                status=status,
                details={
                    "runtime": "vllm",
                    "mode": "docker_server",
                    "reason": reason,
                    "container": {
                        "name": container_name,
                        "image": image,
                        "host_port": host_port,
                        "container_port": DEFAULT_CONTAINER_PORT,
                    },
                },
            )
            smoke_validation = make_unavailable_smoke_validation(
                run_id=run_id,
                status=status,
                reason=reason,
                details={"runtime": "vllm", "mode": "docker_server"},
            )
            return RuntimeSession(
                runtime="vllm",
                mode="docker_server",
                status=status,
                runtime_check=runtime_check,
                smoke_validation=smoke_validation,
                container_name=container_name,
            )

        command = build_vllm_docker_command(
            run_id=run_id,
            image=image,
            model=model,
            container_name=container_name,
            host_port=host_port,
            extra_args=docker_config.get("extra_args"),
        )
        result = self.runner(command, timeout_s=self.timeout_s)
        status = result.status if result.status != ProbeStatus.ERROR else ProbeStatus.ERROR
        base_url = f"http://127.0.0.1:{host_port}/v1"
        container_id = result.stdout.strip() or None
        details: dict[str, Any] = {
            "runtime": "vllm",
            "mode": "docker_server",
            "commands": {"docker_run": _command_details(result)},
            "container": {
                "name": container_name,
                "image": image,
                "host_port": host_port,
                "container_port": DEFAULT_CONTAINER_PORT,
            },
        }
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
                details={"runtime": "vllm", "mode": "docker_server"},
            )
            return RuntimeSession(
                runtime="vllm",
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
