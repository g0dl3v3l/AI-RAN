from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any

from ai_runtime_experiments.schemas import ProbeStatus, make_probe_result
from ai_runtime_experiments.utils.command import CommandResult, run_command

DEFAULT_TIMEOUT_S = 5.0
_COMMAND_LABELS = {
    "uname_a": "uname -a",
    "python_version": "python --version",
    "nvidia_smi": "nvidia-smi",
    "nvidia_smi_q": "nvidia-smi -q",
}
_DRIVER_VERSION_RE = re.compile(r"^\s*Driver Version\s*:\s*(.+)$", re.MULTILINE)
_CUDA_VERSION_RE = re.compile(r"^\s*CUDA Version\s*:\s*(.+)$", re.MULTILINE)
_ATTACHED_GPUS_RE = re.compile(r"^\s*Attached GPUs\s*:\s*(\d+)$", re.MULTILINE)
_PRODUCT_NAME_RE = re.compile(r"^\s*Product Name\s*:\s*(.+)$", re.MULTILINE)
_SUMMARY_DRIVER_RE = re.compile(r"Driver Version:\s*([^\s|]+)")
_SUMMARY_CUDA_RE = re.compile(r"CUDA Version:\s*([^\s|]+)")

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



def _best_effort_text(result: CommandResult) -> str | None:
    text = result.stdout.strip() or result.stderr.strip()
    return text or None



def _first_match(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    if match is None:
        return None
    value = match.group(1).strip()
    return value or None



def _extract_gpu_names(text: str) -> list[str]:
    seen: set[str] = set()
    names: list[str] = []
    for match in _PRODUCT_NAME_RE.finditer(text):
        name = match.group(1).strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names



def _extract_nvidia_fields(*, summary_text: str, detailed_text: str) -> dict[str, Any]:
    extracted: dict[str, Any] = {}

    driver_version = _first_match(_DRIVER_VERSION_RE, detailed_text) or _first_match(
        _SUMMARY_DRIVER_RE, summary_text
    )
    if driver_version is not None:
        extracted["driver_version"] = driver_version

    cuda_version = _first_match(_CUDA_VERSION_RE, detailed_text) or _first_match(
        _SUMMARY_CUDA_RE, summary_text
    )
    if cuda_version is not None:
        extracted["cuda_version"] = cuda_version

    gpu_count = _first_match(_ATTACHED_GPUS_RE, detailed_text)
    if gpu_count is not None:
        extracted["gpu_count"] = int(gpu_count)

    gpu_names = _extract_gpu_names(detailed_text)
    if gpu_names:
        extracted["gpu_names"] = gpu_names

    return extracted



def _overall_status(command_results: Mapping[str, CommandResult]) -> tuple[ProbeStatus, str | None]:
    errored = [
        _COMMAND_LABELS[name]
        for name, result in command_results.items()
        if result.status == ProbeStatus.ERROR
    ]
    if errored:
        return ProbeStatus.ERROR, f"command failure(s): {', '.join(errored)}"

    timed_out = [
        _COMMAND_LABELS[name]
        for name, result in command_results.items()
        if result.status == ProbeStatus.TIMEOUT
    ]
    if timed_out:
        return ProbeStatus.TIMEOUT, f"command timeout(s): {', '.join(timed_out)}"

    unsupported = [
        _COMMAND_LABELS[name]
        for name, result in command_results.items()
        if result.status == ProbeStatus.UNSUPPORTED
    ]
    if unsupported:
        return ProbeStatus.UNSUPPORTED, f"unsupported command(s): {', '.join(unsupported)}"

    skipped = [
        _COMMAND_LABELS[name]
        for name, result in command_results.items()
        if result.status == ProbeStatus.SKIPPED
    ]
    if skipped:
        return ProbeStatus.SKIPPED, f"skipped command(s): {', '.join(skipped)}"

    return ProbeStatus.OK, None



def collect_hardware_probe(
    *,
    run_id: str,
    runner: CommandRunner = run_command,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> dict[str, Any]:
    command_results = {
        "uname_a": runner(["uname", "-a"], timeout_s=timeout_s),
        "python_version": runner(["python", "--version"], timeout_s=timeout_s),
        "nvidia_smi": runner(["nvidia-smi"], timeout_s=timeout_s),
        "nvidia_smi_q": runner(["nvidia-smi", "-q"], timeout_s=timeout_s),
    }

    status, reason = _overall_status(command_results)

    extracted: dict[str, Any] = {}
    uname_text = _best_effort_text(command_results["uname_a"])
    if uname_text is not None:
        extracted["uname_a"] = uname_text

    python_version = _best_effort_text(command_results["python_version"])
    if python_version is not None:
        extracted["python_version"] = python_version

    extracted.update(
        _extract_nvidia_fields(
            summary_text=command_results["nvidia_smi"].stdout,
            detailed_text=command_results["nvidia_smi_q"].stdout,
        )
    )

    details: dict[str, Any] = {
        "commands": {
            name: _command_details(result) for name, result in command_results.items()
        },
        "extracted": extracted,
    }
    if reason is not None:
        details["reason"] = reason

    return make_probe_result(
        run_id=run_id,
        component="hardware",
        status=status,
        details=details,
    )
