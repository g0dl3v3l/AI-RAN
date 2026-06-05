from __future__ import annotations

import os
import re
from collections.abc import Callable, Mapping
from pathlib import Path
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
_FB_MEMORY_TOTAL_RE = re.compile(r"^Total\s*:\s*(\d+)\s*MiB$")

CommandRunner = Callable[..., CommandResult]
HostFactsGetter = Callable[[], Mapping[str, Any]]


PRIMARY_CPUINFO_KEYS = {"model name", "hardware", "model"}


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



def _extract_vram_totals_mib(text: str) -> list[int]:
    totals: list[int] = []
    in_fb_memory_block = False

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if stripped == "FB Memory Usage":
            in_fb_memory_block = True
            continue
        if not in_fb_memory_block:
            continue

        match = _FB_MEMORY_TOTAL_RE.match(stripped)
        if match is None:
            continue

        totals.append(int(match.group(1)))
        in_fb_memory_block = False

    return totals



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

    vram_totals_mib = _extract_vram_totals_mib(detailed_text)
    if vram_totals_mib:
        extracted["vram_total_mib"] = sum(vram_totals_mib)

    return extracted



def _read_proc_text(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return None



def _extract_cpu_model_from_procfs(text: str) -> str | None:
    processor_fallback: str | None = None

    for raw_line in text.splitlines():
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", maxsplit=1)
        normalized_key = key.strip().lower()
        normalized_value = value.strip()
        if not normalized_value:
            continue
        if normalized_key in PRIMARY_CPUINFO_KEYS:
            return normalized_value
        if normalized_key == "processor" and not normalized_value.isdigit():
            processor_fallback = normalized_value

    return processor_fallback



def _system_memory_total_bytes() -> int | None:
    if hasattr(os, "sysconf"):
        try:
            page_size = os.sysconf("SC_PAGE_SIZE")
            phys_pages = os.sysconf("SC_PHYS_PAGES")
        except (AttributeError, OSError, TypeError, ValueError):
            pass
        else:
            if isinstance(page_size, int) and isinstance(phys_pages, int):
                if page_size > 0 and phys_pages > 0:
                    return page_size * phys_pages

    meminfo = _read_proc_text("/proc/meminfo")
    if meminfo is None:
        return None

    for raw_line in meminfo.splitlines():
        if not raw_line.startswith("MemTotal:"):
            continue
        parts = raw_line.split()
        if len(parts) < 2:
            return None
        try:
            return int(parts[1]) * 1024
        except ValueError:
            return None

    return None



def collect_host_facts() -> dict[str, Any]:
    facts: dict[str, Any] = {}

    try:
        cpuinfo = _read_proc_text("/proc/cpuinfo")
        if cpuinfo is not None:
            cpu_model = _extract_cpu_model_from_procfs(cpuinfo)
            if cpu_model is not None:
                facts["cpu_model"] = cpu_model

        cpu_core_count = os.cpu_count()
        if cpu_core_count is not None:
            facts["cpu_core_count"] = int(cpu_core_count)

        system_memory_total_bytes = _system_memory_total_bytes()
        if system_memory_total_bytes is not None:
            facts["system_memory_total_bytes"] = system_memory_total_bytes
    except Exception:
        return {}

    return facts



def _safe_host_facts(host_facts_getter: HostFactsGetter) -> dict[str, Any]:
    try:
        facts = host_facts_getter()
    except Exception:
        return {}
    if not isinstance(facts, Mapping):
        return {}

    extracted: dict[str, Any] = {}

    cpu_model = facts.get("cpu_model")
    if cpu_model is not None:
        normalized_cpu_model = str(cpu_model).strip()
        if normalized_cpu_model:
            extracted["cpu_model"] = normalized_cpu_model

    cpu_core_count = facts.get("cpu_core_count")
    if cpu_core_count is not None:
        try:
            extracted["cpu_core_count"] = int(cpu_core_count)
        except (TypeError, ValueError):
            pass

    system_memory_total_bytes = facts.get("system_memory_total_bytes")
    if system_memory_total_bytes is not None:
        try:
            extracted["system_memory_total_bytes"] = int(system_memory_total_bytes)
        except (TypeError, ValueError):
            pass

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
    host_facts_getter: HostFactsGetter = collect_host_facts,
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

    extracted.update(_safe_host_facts(host_facts_getter))
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
