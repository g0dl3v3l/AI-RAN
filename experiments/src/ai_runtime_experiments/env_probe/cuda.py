from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from ai_runtime_experiments.schemas import ProbeStatus, make_probe_result
from ai_runtime_experiments.utils.command import CommandResult, run_command

DEFAULT_TIMEOUT_S = 120.0
DEFAULT_CUDA_IMAGE = "nvidia/cuda:12.4.1-base-ubuntu22.04"
_COMMAND_LABEL = "docker run --gpus all"
_UNSUPPORTED_MARKERS = (
    "could not select device driver",
    "could not load nvidia",
    "could not find an available gpu",
    "error while loading shared libraries: libnvidia-ml.so",
    "nvidia-container-cli",
    "no cuda-capable device is detected",
    "no such device",
    "no such file or directory",
    "unknown flag: --gpus",
    "unknown runtime specified nvidia",
    "unsupported",
)
_DRIVER_VERSION_RE = re.compile(r"Driver Version:\s*([^\s|]+)")
_CUDA_VERSION_RE = re.compile(r"CUDA Version:\s*([^\s|]+)")

CommandRunner = Callable[..., CommandResult]


def build_cuda_probe_command(*, image: str = DEFAULT_CUDA_IMAGE) -> list[str]:
    return ["docker", "run", "--gpus", "all", "--rm", image, "nvidia-smi"]



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



def _classify_result(result: CommandResult) -> tuple[ProbeStatus, str | None]:
    if result.status == ProbeStatus.OK:
        return ProbeStatus.OK, None
    if result.status == ProbeStatus.UNSUPPORTED:
        return ProbeStatus.UNSUPPORTED, f"unsupported command(s): {_COMMAND_LABEL}"
    if result.status == ProbeStatus.TIMEOUT:
        return ProbeStatus.TIMEOUT, f"command timeout(s): {_COMMAND_LABEL}"
    if result.status == ProbeStatus.SKIPPED:
        return ProbeStatus.SKIPPED, f"skipped command(s): {_COMMAND_LABEL}"
    if any(marker in _combined_text(result) for marker in _UNSUPPORTED_MARKERS):
        return ProbeStatus.UNSUPPORTED, f"unsupported capability: {_COMMAND_LABEL}"
    return ProbeStatus.ERROR, f"command failure(s): {_COMMAND_LABEL}"



def _first_match(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    if match is None:
        return None
    value = match.group(1).strip()
    return value or None



def _extract_nvidia_fields(stdout: str) -> dict[str, Any]:
    extracted: dict[str, Any] = {}

    driver_version = _first_match(_DRIVER_VERSION_RE, stdout)
    if driver_version is not None:
        extracted["driver_version"] = driver_version

    cuda_version = _first_match(_CUDA_VERSION_RE, stdout)
    if cuda_version is not None:
        extracted["cuda_version"] = cuda_version

    return extracted



def collect_cuda_container_probe(
    *,
    run_id: str,
    runner: CommandRunner = run_command,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    image: str = DEFAULT_CUDA_IMAGE,
) -> dict[str, Any]:
    command = build_cuda_probe_command(image=image)
    result = runner(command, timeout_s=timeout_s)
    status, reason = _classify_result(result)

    details: dict[str, Any] = {
        "commands": {"docker_run_nvidia_smi": _command_details(result)},
        "container": {"image": image},
        "extracted": _extract_nvidia_fields(result.stdout),
    }
    if reason is not None:
        details["reason"] = reason

    return make_probe_result(
        run_id=run_id,
        component="cuda_check",
        status=status,
        details=details,
    )
