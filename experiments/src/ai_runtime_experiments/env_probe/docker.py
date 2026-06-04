from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ai_runtime_experiments.schemas import ProbeStatus, make_probe_result
from ai_runtime_experiments.utils.command import CommandResult, run_command

DEFAULT_TIMEOUT_S = 5.0

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



def _extract_docker_fields(stdout: str) -> dict[str, Any]:
    extracted: dict[str, Any] = {}
    current_section: str | None = None

    for line in stdout.splitlines():
        if line.startswith("Client:"):
            current_section = "client"
            continue
        if line.startswith("Server:"):
            current_section = "server"
            continue

        stripped = line.strip()
        if not stripped.startswith("Version:"):
            continue

        version_parts = stripped.split(":", maxsplit=1)[1].strip().split()
        if not version_parts:
            continue

        version = version_parts[0]
        if current_section == "client" and "client_version" not in extracted:
            extracted["client_version"] = version
        if current_section == "server" and "server_version" not in extracted:
            extracted["server_version"] = version

    return extracted



def _reason_for_status(result: CommandResult) -> str | None:
    if result.status == ProbeStatus.UNSUPPORTED:
        return "unsupported command(s): docker version"
    if result.status == ProbeStatus.TIMEOUT:
        return "command timeout(s): docker version"
    if result.status == ProbeStatus.ERROR:
        return "command failure(s): docker version"
    if result.status == ProbeStatus.SKIPPED:
        return "skipped command(s): docker version"
    return None



def collect_docker_probe(
    *,
    run_id: str,
    runner: CommandRunner = run_command,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> dict[str, Any]:
    result = runner(["docker", "version"], timeout_s=timeout_s)

    details: dict[str, Any] = {
        "commands": {"docker_version": _command_details(result)},
        "extracted": _extract_docker_fields(result.stdout),
    }
    reason = _reason_for_status(result)
    if reason is not None:
        details["reason"] = reason

    return make_probe_result(
        run_id=run_id,
        component="docker",
        status=result.status,
        details=details,
    )
