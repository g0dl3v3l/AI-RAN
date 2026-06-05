from __future__ import annotations

import shutil
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ai_runtime_experiments.schemas import ProbeStatus, make_probe_result
from ai_runtime_experiments.utils.command import CommandResult, run_command

DEFAULT_TIMEOUT_S = 5.0
DEFAULT_MPS_CONTROL_BINARY = "nvidia-cuda-mps-control"
DEFAULT_MPS_CONTROL_PIPE_PATH = "/tmp/nvidia-mps/control"
_START_COMMAND_LABEL = "nvidia-cuda-mps-control -d"
_STOP_COMMAND_LABEL = "nvidia-cuda-mps-control quit"
_UNSUPPORTED_MARKERS = (
    "not supported",
    "unsupported",
    "no such file or directory",
    "not found",
)

CommandRunner = Callable[..., CommandResult]
BinaryLocator = Callable[[str], str | None]
ControlCommandRunner = Callable[..., CommandResult]


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



def _coerce_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value



def _combined_text(result: CommandResult) -> str:
    return "\n".join(
        part for part in (result.stdout, result.stderr, result.error_message or "") if part
    ).lower()



def _classify_result(result: CommandResult, *, command_label: str) -> tuple[ProbeStatus, str | None]:
    if result.status == ProbeStatus.OK:
        return ProbeStatus.OK, None
    if result.status == ProbeStatus.UNSUPPORTED:
        return ProbeStatus.UNSUPPORTED, f"unsupported command(s): {command_label}"
    if result.status == ProbeStatus.TIMEOUT:
        return ProbeStatus.TIMEOUT, f"command timeout(s): {command_label}"
    if result.status == ProbeStatus.SKIPPED:
        return ProbeStatus.SKIPPED, f"skipped command(s): {command_label}"
    if any(marker in _combined_text(result) for marker in _UNSUPPORTED_MARKERS):
        return ProbeStatus.UNSUPPORTED, f"unsupported capability: {command_label}"
    return ProbeStatus.ERROR, f"command failure(s): {command_label}"



def _resolve_control_pipe(control_pipe_path: Any) -> tuple[str, bool]:
    if hasattr(control_pipe_path, "exists") and not isinstance(control_pipe_path, (str, bytes, Path)):
        return str(control_pipe_path), bool(control_pipe_path.exists())

    resolved_path = Path(str(control_pipe_path))
    return str(resolved_path), resolved_path.exists()



def run_mps_control_command(
    *,
    binary_path: str,
    command: str,
    timeout_s: float | None = None,
) -> CommandResult:
    start = time.monotonic()
    argv = [binary_path]

    try:
        completed = subprocess.run(
            argv,
            input=f"{command}\n",
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        duration_s = time.monotonic() - start
        status = ProbeStatus.OK if completed.returncode == 0 else ProbeStatus.ERROR
        return CommandResult(
            argv=argv,
            status=status,
            returncode=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
            timed_out=False,
            duration_s=duration_s,
            error_type=None,
            error_message=None,
        )
    except subprocess.TimeoutExpired as exc:
        duration_s = time.monotonic() - start
        return CommandResult(
            argv=argv,
            status=ProbeStatus.TIMEOUT,
            returncode=None,
            stdout=_coerce_text(exc.stdout),
            stderr=_coerce_text(exc.stderr),
            timed_out=True,
            duration_s=duration_s,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
    except FileNotFoundError as exc:
        duration_s = time.monotonic() - start
        return CommandResult(
            argv=argv,
            status=ProbeStatus.UNSUPPORTED,
            returncode=None,
            stdout="",
            stderr="",
            timed_out=False,
            duration_s=duration_s,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
    except Exception as exc:  # pragma: no cover
        duration_s = time.monotonic() - start
        return CommandResult(
            argv=argv,
            status=ProbeStatus.ERROR,
            returncode=None,
            stdout="",
            stderr="",
            timed_out=False,
            duration_s=duration_s,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )



def collect_mps_probe(
    *,
    run_id: str,
    runner: CommandRunner = run_command,
    control_command_runner: ControlCommandRunner = run_mps_control_command,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    control_binary: str = DEFAULT_MPS_CONTROL_BINARY,
    allow_start_stop: bool = False,
    which: BinaryLocator = shutil.which,
    control_pipe_path: Any = DEFAULT_MPS_CONTROL_PIPE_PATH,
) -> dict[str, Any]:
    resolved_binary_path = which(control_binary)
    control_pipe_name, control_pipe_exists = _resolve_control_pipe(control_pipe_path)

    details: dict[str, Any] = {
        "commands": {},
        "mode": "start_stop" if allow_start_stop else "read_only",
        "daemon": {
            "control_binary": control_binary,
            "binary_path": resolved_binary_path,
            "control_pipe_path": control_pipe_name,
            "control_pipe_exists": control_pipe_exists,
        },
        "start_stop": {
            "allowed": allow_start_stop,
            "attempted": False,
            "started_by_probe": False,
        },
    }

    if resolved_binary_path is None:
        details["reason"] = f"unsupported command(s): {control_binary}"
        return make_probe_result(
            run_id=run_id,
            component="mps_check",
            status=ProbeStatus.UNSUPPORTED,
            details=details,
        )

    if not allow_start_stop:
        return make_probe_result(
            run_id=run_id,
            component="mps_check",
            status=ProbeStatus.OK,
            details=details,
        )

    if control_pipe_exists:
        details["start_stop"]["skip_reason"] = (
            "existing MPS control pipe detected; refusing lifecycle mutation"
        )
        return make_probe_result(
            run_id=run_id,
            component="mps_check",
            status=ProbeStatus.OK,
            details=details,
        )

    start_result = runner([resolved_binary_path, "-d"], timeout_s=timeout_s)
    details["commands"]["mps_start_daemon"] = _command_details(start_result)
    details["start_stop"]["attempted"] = True

    start_status, start_reason = _classify_result(start_result, command_label=_START_COMMAND_LABEL)
    if start_status != ProbeStatus.OK:
        details["reason"] = start_reason
        return make_probe_result(
            run_id=run_id,
            component="mps_check",
            status=start_status,
            details=details,
        )

    stop_result = control_command_runner(
        binary_path=resolved_binary_path,
        command="quit",
        timeout_s=timeout_s,
    )
    details["commands"]["mps_quit"] = _command_details(stop_result)
    details["start_stop"]["started_by_probe"] = True

    stop_status, stop_reason = _classify_result(stop_result, command_label=_STOP_COMMAND_LABEL)
    if stop_status != ProbeStatus.OK:
        details["reason"] = stop_reason
        return make_probe_result(
            run_id=run_id,
            component="mps_check",
            status=stop_status,
            details=details,
        )

    return make_probe_result(
        run_id=run_id,
        component="mps_check",
        status=ProbeStatus.OK,
        details=details,
    )
