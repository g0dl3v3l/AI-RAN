from __future__ import annotations

import re
import uuid
from collections.abc import Mapping, Sequence
from typing import Any

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
_EXPERIMENT_LABELS = {
    "ai-edge-experiment": "v0",
    "ai-edge-component": "vllm-runtime",
}
_DOCKER_NAME_SAFE_RE = re.compile(r"[^a-z0-9_.-]+")



def _slug(value: str, *, default: str) -> str:
    slug = _DOCKER_NAME_SAFE_RE.sub("-", value.lower().strip()).strip("-.")
    return slug or default



def build_vllm_container_name(run_id: str, *, token: str | None = None) -> str:
    run_fragment = _slug(run_id, default="run")[:24]
    token_fragment = _slug(token or uuid.uuid4().hex[:8], default="token")[:12]
    return f"{EXPERIMENT_CONTAINER_NAME_PREFIX}{run_fragment}-{token_fragment}".rstrip("-")



def build_vllm_label_args(run_id: str) -> list[str]:
    args: list[str] = []
    for key, value in {**_EXPERIMENT_LABELS, "ai-edge-run-id": run_id}.items():
        args.extend(["--label", f"{key}={value}"])
    return args



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
        "vllm",
        "serve",
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
    ) -> None:
        self.config = dict(config)
        self.runner = runner
        self.timeout_s = timeout_s

    def start(self, *, run_id: str) -> RuntimeSession:
        external_config = _mapping(self.config.get("external_server"))
        external_base_url = _normalize_base_url(external_config.get("base_url"))
        if external_base_url is not None:
            runtime_check = make_probe_result(
                run_id=run_id,
                component="runtime_check",
                status=ProbeStatus.OK,
                details={
                    "runtime": "vllm",
                    "mode": "external_server",
                    "base_url": external_base_url,
                },
            )
            return RuntimeSession(
                runtime="vllm",
                mode="external_server",
                status=ProbeStatus.OK,
                base_url=external_base_url,
                runtime_check=runtime_check,
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

    def stop(self, session: RuntimeSession) -> dict[str, Any] | None:
        if session.mode != "docker_server" or not session.container_name:
            return None

        result = self.runner(
            ["docker", "rm", "-f", session.container_name],
            timeout_s=self.timeout_s,
        )
        status = result.status if result.status != ProbeStatus.ERROR else ProbeStatus.ERROR
        details: dict[str, Any] = {
            "runtime": session.runtime,
            "mode": session.mode,
            "container": {"name": session.container_name},
            "commands": {"docker_rm_force": _command_details(result)},
        }
        if session.container_id is not None:
            details["container"]["id"] = session.container_id
        if status != ProbeStatus.OK:
            details["reason"] = _reason_for_status(status=status, mode=session.mode)

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
        base_url = (
            f"http://127.0.0.1:{host_port}/v1" if status == ProbeStatus.OK else None
        )
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
        if base_url is not None:
            details["base_url"] = base_url
        if status != ProbeStatus.OK:
            details["reason"] = _reason_for_status(status=status, mode="docker_server")

        runtime_check = make_probe_result(
            run_id=run_id,
            component="runtime_check",
            status=status,
            details=details,
        )
        smoke_validation = None
        if status != ProbeStatus.OK:
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
            base_url=base_url,
            smoke_validation=smoke_validation,
            container_name=container_name,
            container_id=container_id,
        )
