from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from typing import Any

from ai_runtime_experiments.docker_criu.safety import (
    EXPERIMENT_CONTAINER_NAME_PREFIX,
    build_docker_label_args,
    build_experiment_container_name,
    ensure_experiment_owned_container,
)
from ai_runtime_experiments.schemas import ProbeStatus, make_probe_result
from ai_runtime_experiments.utils.command import CommandResult, run_command

DEFAULT_TIMEOUT_S = 10.0
DEFAULT_SMOKE_IMAGE = "busybox:1.36"
DEFAULT_CHECKPOINT_NAME = "ai-edge-v0-criu-checkpoint"
_DEFAULT_LOOP_COMMAND = "while true; do sleep 1; done"
_CRII_VERSION_RE = re.compile(r"(\d+\.\d+(?:\.\d+)*)")
_UNSUPPORTED_MARKERS = (
    "not a docker command",
    "unknown command",
    "not supported",
    "support not available",
    "experimental feature",
    "executable file not found",
    "no such file or directory",
    "checkpoint support",
)

CommandRunner = Callable[..., CommandResult]



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



def _combined_text(result: CommandResult) -> str:
    return "\n".join(
        part for part in (result.stdout, result.stderr, result.error_message or "") if part
    ).lower()



def _classify_result(
    result: CommandResult,
    *,
    command_label: str,
    capability_sensitive: bool = False,
) -> tuple[ProbeStatus, str | None]:
    if result.status == ProbeStatus.OK:
        return ProbeStatus.OK, None
    if result.status == ProbeStatus.UNSUPPORTED:
        return ProbeStatus.UNSUPPORTED, f"unsupported command(s): {command_label}"
    if result.status == ProbeStatus.TIMEOUT:
        return ProbeStatus.TIMEOUT, f"command timeout(s): {command_label}"
    if result.status == ProbeStatus.SKIPPED:
        return ProbeStatus.SKIPPED, f"skipped command(s): {command_label}"
    if capability_sensitive and any(marker in _combined_text(result) for marker in _UNSUPPORTED_MARKERS):
        return ProbeStatus.UNSUPPORTED, f"unsupported capability: {command_label}"
    return ProbeStatus.ERROR, f"command failure(s): {command_label}"



def _extract_criu_version(stdout: str) -> str | None:
    match = _CRII_VERSION_RE.search(stdout)
    if match is None:
        return None
    return match.group(1)



def _status_from_probe(record: Mapping[str, Any] | None) -> ProbeStatus | None:
    if record is None:
        return None
    status = record.get("status")
    if isinstance(status, ProbeStatus):
        return status
    if isinstance(status, str):
        try:
            return ProbeStatus(status)
        except ValueError:
            return None
    return None



def _parse_label_mapping(text: str) -> dict[str, str] | None:
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



def _finalize_record(
    *,
    run_id: str,
    status: ProbeStatus,
    details: dict[str, Any],
) -> dict[str, Any]:
    return make_probe_result(
        run_id=run_id,
        component="docker_criu_integration",
        status=status,
        details=details,
    )



def _cleanup_owned_container(
    *,
    container_name: str,
    labels: Mapping[str, str],
    runner: CommandRunner,
    timeout_s: float,
    details: dict[str, Any],
) -> CommandResult:
    ensure_experiment_owned_container(container_name=container_name, labels=labels)
    result = runner(["docker", "rm", "-f", container_name], timeout_s=timeout_s)
    details["commands"]["docker_rm_force"] = _command_details(result)
    return result



def collect_criu_probe(
    *,
    run_id: str,
    runner: CommandRunner = run_command,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> dict[str, Any]:
    result = runner(["criu", "--version"], timeout_s=timeout_s)
    status, reason = _classify_result(
        result,
        command_label="criu --version",
        capability_sensitive=True,
    )

    extracted: dict[str, Any] = {}
    version = _extract_criu_version(result.stdout)
    if version is not None:
        extracted["criu_version"] = version

    details: dict[str, Any] = {
        "commands": {"criu_version": _command_details(result)},
        "extracted": extracted,
    }
    if reason is not None:
        details["reason"] = reason

    return make_probe_result(
        run_id=run_id,
        component="criu_check",
        status=status,
        details=details,
    )



def collect_docker_criu_integration(
    *,
    run_id: str,
    runner: CommandRunner = run_command,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    criu_probe: Mapping[str, Any] | None = None,
    container_name: str | None = None,
    checkpoint_name: str = DEFAULT_CHECKPOINT_NAME,
    smoke_image: str = DEFAULT_SMOKE_IMAGE,
) -> dict[str, Any]:
    resolved_container_name = container_name or build_experiment_container_name(run_id)
    if not resolved_container_name.startswith(EXPERIMENT_CONTAINER_NAME_PREFIX):
        raise ValueError(
            f"container_name must start with {EXPERIMENT_CONTAINER_NAME_PREFIX!r}: {resolved_container_name}"
        )

    details: dict[str, Any] = {
        "commands": {},
        "container": {
            "name": resolved_container_name,
            "checkpoint_name": checkpoint_name,
            "image": smoke_image,
        },
        "smoke": {"attempted": False},
    }

    criu_status = _status_from_probe(criu_probe)
    if criu_probe is not None:
        details["prerequisites"] = {"criu_status": criu_probe.get("status")}
    if criu_status is not None and criu_status != ProbeStatus.OK:
        status = ProbeStatus.UNSUPPORTED if criu_status == ProbeStatus.UNSUPPORTED else criu_status
        details["reason"] = f"criu prerequisite is not available: {status.value}"
        return _finalize_record(run_id=run_id, status=status, details=details)

    help_result = runner(["docker", "checkpoint", "--help"], timeout_s=timeout_s)
    details["commands"]["docker_checkpoint_help"] = _command_details(help_result)
    help_status, help_reason = _classify_result(
        help_result,
        command_label="docker checkpoint --help",
        capability_sensitive=True,
    )
    if help_status != ProbeStatus.OK:
        details["reason"] = help_reason
        return _finalize_record(run_id=run_id, status=help_status, details=details)

    run_result = runner(
        [
            "docker",
            "run",
            "-d",
            "--name",
            resolved_container_name,
            *build_docker_label_args(run_id),
            smoke_image,
            "sh",
            "-c",
            _DEFAULT_LOOP_COMMAND,
        ],
        timeout_s=timeout_s,
    )
    details["smoke"]["attempted"] = True
    details["commands"]["docker_run"] = _command_details(run_result)
    run_status, run_reason = _classify_result(run_result, command_label="docker run")
    if run_status != ProbeStatus.OK:
        details["reason"] = run_reason
        return _finalize_record(run_id=run_id, status=run_status, details=details)

    container_id = run_result.stdout.strip()
    if container_id:
        details["smoke"]["container_id"] = container_id

    inspect_labels_result = runner(
        ["docker", "inspect", "--format", "{{json .Config.Labels}}", resolved_container_name],
        timeout_s=timeout_s,
    )
    details["commands"]["docker_inspect_labels"] = _command_details(inspect_labels_result)
    inspect_status, inspect_reason = _classify_result(
        inspect_labels_result,
        command_label="docker inspect labels",
    )
    if inspect_status != ProbeStatus.OK:
        details["reason"] = inspect_reason
        return _finalize_record(run_id=run_id, status=inspect_status, details=details)

    labels = _parse_label_mapping(inspect_labels_result.stdout)
    if labels is None:
        details["reason"] = "unable to parse docker inspect labels JSON"
        return _finalize_record(run_id=run_id, status=ProbeStatus.ERROR, details=details)

    details["container"]["inspected_labels"] = labels

    try:
        ensure_experiment_owned_container(container_name=resolved_container_name, labels=labels)
    except ValueError as exc:
        details["reason"] = str(exc)
        return _finalize_record(run_id=run_id, status=ProbeStatus.ERROR, details=details)

    checkpoint_result = runner(
        ["docker", "checkpoint", "create", resolved_container_name, checkpoint_name],
        timeout_s=timeout_s,
    )
    details["commands"]["docker_checkpoint_create"] = _command_details(checkpoint_result)
    checkpoint_status, checkpoint_reason = _classify_result(
        checkpoint_result,
        command_label="docker checkpoint create",
        capability_sensitive=True,
    )
    if checkpoint_status != ProbeStatus.OK:
        cleanup_result = _cleanup_owned_container(
            container_name=resolved_container_name,
            labels=labels,
            runner=runner,
            timeout_s=timeout_s,
            details=details,
        )
        cleanup_status, cleanup_reason = _classify_result(
            cleanup_result,
            command_label="docker rm -f",
        )
        details["reason"] = checkpoint_reason
        if cleanup_status != ProbeStatus.OK:
            details["cleanup_reason"] = cleanup_reason
        return _finalize_record(run_id=run_id, status=checkpoint_status, details=details)

    stop_result = runner(["docker", "stop", resolved_container_name], timeout_s=timeout_s)
    details["commands"]["docker_stop"] = _command_details(stop_result)
    stop_status, stop_reason = _classify_result(
        stop_result,
        command_label="docker stop",
    )
    if stop_status != ProbeStatus.OK:
        cleanup_result = _cleanup_owned_container(
            container_name=resolved_container_name,
            labels=labels,
            runner=runner,
            timeout_s=timeout_s,
            details=details,
        )
        cleanup_status, cleanup_reason = _classify_result(
            cleanup_result,
            command_label="docker rm -f",
        )
        details["reason"] = stop_reason
        if cleanup_status != ProbeStatus.OK:
            details["cleanup_reason"] = cleanup_reason
        return _finalize_record(run_id=run_id, status=stop_status, details=details)

    start_result = runner(
        ["docker", "start", "--checkpoint", checkpoint_name, resolved_container_name],
        timeout_s=timeout_s,
    )
    details["commands"]["docker_start_checkpoint"] = _command_details(start_result)
    start_status, start_reason = _classify_result(
        start_result,
        command_label="docker start --checkpoint",
        capability_sensitive=True,
    )
    if start_status != ProbeStatus.OK:
        cleanup_result = _cleanup_owned_container(
            container_name=resolved_container_name,
            labels=labels,
            runner=runner,
            timeout_s=timeout_s,
            details=details,
        )
        cleanup_status, cleanup_reason = _classify_result(
            cleanup_result,
            command_label="docker rm -f",
        )
        details["reason"] = start_reason
        if cleanup_status != ProbeStatus.OK:
            details["cleanup_reason"] = cleanup_reason
        return _finalize_record(run_id=run_id, status=start_status, details=details)

    state_result = runner(
        ["docker", "inspect", "--format", "{{.State.Status}}", resolved_container_name],
        timeout_s=timeout_s,
    )
    details["commands"]["docker_inspect_state"] = _command_details(state_result)
    state_status, state_reason = _classify_result(
        state_result,
        command_label="docker inspect state",
    )
    if state_status != ProbeStatus.OK:
        cleanup_result = _cleanup_owned_container(
            container_name=resolved_container_name,
            labels=labels,
            runner=runner,
            timeout_s=timeout_s,
            details=details,
        )
        cleanup_status, cleanup_reason = _classify_result(
            cleanup_result,
            command_label="docker rm -f",
        )
        details["reason"] = state_reason
        if cleanup_status != ProbeStatus.OK:
            details["cleanup_reason"] = cleanup_reason
        return _finalize_record(run_id=run_id, status=state_status, details=details)

    details.setdefault("extracted", {})["container_state"] = state_result.stdout.strip()

    cleanup_result = _cleanup_owned_container(
        container_name=resolved_container_name,
        labels=labels,
        runner=runner,
        timeout_s=timeout_s,
        details=details,
    )
    cleanup_status, cleanup_reason = _classify_result(
        cleanup_result,
        command_label="docker rm -f",
    )
    if cleanup_status != ProbeStatus.OK:
        details["reason"] = cleanup_reason
        return _finalize_record(run_id=run_id, status=cleanup_status, details=details)

    return _finalize_record(run_id=run_id, status=ProbeStatus.OK, details=details)
