from __future__ import annotations

import re
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ai_runtime_experiments.schemas import ProbeStatus
from ai_runtime_experiments.utils.command import CommandResult, run_command

CommandRunner = Callable[..., CommandResult]

_CRIU_LOG_PATH_RE = re.compile(r"path=\s*(?P<path>/\S+\.log)")
_SECRET_PATTERNS = (
    re.compile(r"(?i)(\b(?:token|password|secret|api[_-]?key|apikey)\b\s*[:=]\s*)(\S+)"),
    re.compile(
        r'(?i)(["\']?(?:token|password|secret|api[_-]?key|apikey)["\']?\s*:\s*["\'])([^"\']*)(["\'])'
    ),
)
_TRUSTED_CRIU_LOG_PREFIXES = (
    Path("/run/containerd/io.containerd.runtime.v2.task/moby"),
    Path("/var/lib/docker"),
)
_DEBUG_TEXT_LIMIT_BYTES = 256 * 1024
_DEBUG_COMMAND_TIMEOUT_S = 5.0



def _sanitize_text_for_json(text: str | None) -> tuple[str, bool, bool]:
    raw_text = text or ""
    redacted_text, redacted = redact_text(raw_text)
    bounded_text, truncated = bound_text(redacted_text)
    return bounded_text, redacted, truncated



def command_result_details(result: CommandResult) -> dict[str, Any]:
    stdout, stdout_redacted, stdout_truncated = _sanitize_text_for_json(result.stdout)
    stderr, stderr_redacted, stderr_truncated = _sanitize_text_for_json(result.stderr)
    error_message, error_message_redacted, error_message_truncated = _sanitize_text_for_json(
        result.error_message
    )
    return {
        "argv": result.argv,
        "status": result.status.value,
        "returncode": result.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "timed_out": result.timed_out,
        "duration_s": result.duration_s,
        "error_type": result.error_type,
        "error_message": error_message,
        "stdout_redacted": stdout_redacted,
        "stdout_truncated": stdout_truncated,
        "stderr_redacted": stderr_redacted,
        "stderr_truncated": stderr_truncated,
        "error_message_redacted": error_message_redacted,
        "error_message_truncated": error_message_truncated,
    }



def iter_command_dicts(value: Any):
    if isinstance(value, dict):
        if any(key in value for key in ("stderr", "stdout", "error_message")):
            yield value
        for nested in value.values():
            yield from iter_command_dicts(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from iter_command_dicts(nested)



def extract_criu_log_paths(record: dict[str, Any]) -> list[Path]:
    paths: list[Path] = []
    seen: set[str] = set()
    for command in iter_command_dicts(record):
        text = "\n".join(
            str(command.get(key) or "") for key in ("stderr", "stdout", "error_message")
        )
        for match in _CRIU_LOG_PATH_RE.finditer(text):
            raw_path = match.group("path")
            if raw_path not in seen:
                paths.append(Path(raw_path))
                seen.add(raw_path)
    return paths



def trusted_criu_log_path(path: Path) -> Path | None:
    try:
        resolved = path.resolve(strict=False)
    except OSError:
        return None
    if any(
        resolved == prefix or prefix in resolved.parents
        for prefix in _TRUSTED_CRIU_LOG_PREFIXES
    ):
        return resolved
    return None



def redact_text(text: str) -> tuple[str, bool]:
    redacted = text
    for pattern in _SECRET_PATTERNS:
        if pattern.pattern.endswith("(\\S+)"):
            redacted = pattern.sub(r"\1[REDACTED]", redacted)
        else:
            redacted = pattern.sub(r"\1[REDACTED]\3", redacted)
    return redacted, redacted != text



def bound_text(text: str, *, max_bytes: int = _DEBUG_TEXT_LIMIT_BYTES) -> tuple[str, bool]:
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return text, False
    marker = f"[truncated to last {max_bytes} bytes]\n"
    marker_bytes = marker.encode("utf-8")
    if len(marker_bytes) >= max_bytes:
        return marker_bytes[:max_bytes].decode("utf-8", errors="ignore"), True
    tail_budget = max_bytes - len(marker_bytes)
    tail = encoded[-tail_budget:].decode("utf-8", errors="ignore")
    return marker + tail, True



def write_text_artifact(
    path: str | Path,
    text: str,
    *,
    max_bytes: int = _DEBUG_TEXT_LIMIT_BYTES,
) -> dict[str, Any]:
    artifact_path = Path(path)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    redacted_text, redacted = redact_text(text)
    bounded_text, truncated = bound_text(redacted_text, max_bytes=max_bytes)
    artifact_path.write_text(bounded_text, encoding="utf-8")
    artifact_path.chmod(0o600)
    return {
        "artifact_path": str(artifact_path),
        "size_bytes": artifact_path.stat().st_size,
        "redacted": redacted,
        "truncated": truncated,
    }



def copy_criu_log_with_sudo_cat(
    source_path: Path,
    destination: Path,
    *,
    runner: CommandRunner = run_command,
) -> dict[str, Any]:
    trusted_source_path = trusted_criu_log_path(source_path)
    if trusted_source_path is None:
        return {
            "status": ProbeStatus.ERROR.value,
            "fallback": "sudo-cat",
            "error_type": "UntrustedPath",
            "error_message": f"Refused sudo fallback for untrusted path: {source_path}",
        }

    result = runner(
        ["sudo", "-n", "cat", str(trusted_source_path)],
        timeout_s=_DEBUG_COMMAND_TIMEOUT_S,
    )
    details = command_result_details(result)
    if result.status == ProbeStatus.OK and result.returncode == 0:
        artifact_details = write_text_artifact(destination, result.stdout)
        return {
            "status": ProbeStatus.OK.value,
            "fallback": "sudo-cat",
            "fallback_command": details,
            **artifact_details,
        }
    return {
        "status": ProbeStatus.ERROR.value,
        "fallback": "sudo-cat",
        "error_type": result.error_type or "CommandFailed",
        "error_message": result.stderr or result.error_message or "sudo cat failed",
        "fallback_command": details,
    }



def capture_criu_logs_for_record(
    *,
    run_dir: Path,
    artifact_name: str,
    record: dict[str, Any],
    runner: CommandRunner = run_command,
    copyfile: Callable[[str | Path, str | Path], Any] | None = None,
) -> None:
    details = record.get("details")
    if not isinstance(details, dict):
        return
    diagnostics = details.get("diagnostics")
    if isinstance(diagnostics, dict) and diagnostics.get("criu_logs"):
        return

    log_paths = extract_criu_log_paths(record)
    if not log_paths:
        return

    capture_dir = run_dir / "criu_logs" / artifact_name.removesuffix(".json")
    capture_dir.mkdir(parents=True, exist_ok=True)
    copyfile_func = copyfile or shutil.copyfile
    captured: list[dict[str, Any]] = []
    for index, source_path in enumerate(log_paths, start=1):
        destination = capture_dir / f"{index:02d}-{source_path.name}"
        entry: dict[str, Any] = {
            "source_path": str(source_path),
            "destination_path": str(destination),
        }
        try:
            copyfile_func(source_path, destination)
            artifact_details = write_text_artifact(
                destination,
                destination.read_text(encoding="utf-8", errors="replace"),
            )
        except OSError as exc:
            if isinstance(exc, PermissionError):
                trusted_source_path = trusted_criu_log_path(source_path)
                if trusted_source_path is not None:
                    entry["direct_copy_error_type"] = type(exc).__name__
                    entry["direct_copy_error_message"] = str(exc)
                    entry.update(
                        copy_criu_log_with_sudo_cat(
                            trusted_source_path,
                            destination,
                            runner=runner,
                        )
                    )
                else:
                    entry["status"] = ProbeStatus.ERROR.value
                    entry["error_type"] = type(exc).__name__
                    entry["error_message"] = str(exc)
                    entry["fallback"] = "skipped-untrusted-path"
            else:
                entry["status"] = ProbeStatus.ERROR.value
                entry["error_type"] = type(exc).__name__
                entry["error_message"] = str(exc)
        else:
            entry["status"] = ProbeStatus.OK.value
            entry.update(artifact_details)
        captured.append(entry)

    details.setdefault("diagnostics", {})["criu_logs"] = captured



def collect_debug_bundle(
    *,
    run_dir: Path,
    runner: CommandRunner = run_command,
    since: str = "1 hour ago",
    timeout_s: float = _DEBUG_COMMAND_TIMEOUT_S,
) -> dict[str, Any]:
    debug_dir = run_dir / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)

    commands = {
        "docker_version": ["docker", "version"],
        "docker_info": ["docker", "info"],
        "docker_ps_v0": ["docker", "ps", "-a", "--filter", "label=ai-edge-experiment=v0"],
        "criu_version": ["criu", "--version"],
        "criu_check_all": ["criu", "check", "--all"],
        "runc_version": ["runc", "--version"],
        "nvidia_smi": ["nvidia-smi"],
        "nvidia_smi_q": ["nvidia-smi", "-q"],
        "cuda_checkpoint_path": ["which", "cuda-checkpoint"],
        "runc_conf": ["sudo", "-n", "cat", "/etc/criu/runc.conf"],
        "docker_journal": [
            "sudo",
            "-n",
            "journalctl",
            "-u",
            "docker",
            "--since",
            since,
            "-n",
            "500",
            "--no-pager",
        ],
        "containerd_journal": [
            "sudo",
            "-n",
            "journalctl",
            "-u",
            "containerd",
            "--since",
            since,
            "-n",
            "500",
            "--no-pager",
        ],
    }

    bundle: dict[str, Any] = {
        "status": ProbeStatus.OK.value,
        "artifact_dir": str(debug_dir),
        "commands": {},
    }
    for label, argv in commands.items():
        result = runner(argv, timeout_s=timeout_s)
        details = command_result_details(result)
        text = "\n".join(
            part for part in (result.stdout, result.stderr, result.error_message or "") if part
        )
        if text:
            details.update(
                write_text_artifact(debug_dir / f"{label.replace('_', '-')}.txt", text)
            )
        bundle["commands"][label] = details
    return bundle
