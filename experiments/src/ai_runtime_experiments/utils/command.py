from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from ai_runtime_experiments.schemas import ProbeStatus


def _coerce_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


@dataclass(frozen=True)
class CommandResult:
    argv: list[str]
    status: ProbeStatus
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool
    duration_s: float
    error_type: str | None
    error_message: str | None


def run_command(
    argv: Sequence[str],
    *,
    timeout_s: float | None = None,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    shell: bool = False,
    input_text: str | None = None,
) -> CommandResult:
    """Run a command safely and return a structured result.

    Safety defaults:
    - shell=False (unless explicitly overridden)
    - stdout/stderr captured
    - exceptions are converted into status/error fields (no uncaught exceptions)
    """

    argv_list = list(argv)
    start = time.monotonic()

    try:
        completed = subprocess.run(
            argv_list,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=str(cwd) if cwd is not None else None,
            env=dict(env) if env is not None else None,
            shell=shell,
            input=input_text,
            check=False,
        )

        duration_s = time.monotonic() - start
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""

        status = ProbeStatus.OK if completed.returncode == 0 else ProbeStatus.ERROR

        return CommandResult(
            argv=argv_list,
            status=status,
            returncode=completed.returncode,
            stdout=stdout,
            stderr=stderr,
            timed_out=False,
            duration_s=duration_s,
            error_type=None,
            error_message=None,
        )

    except subprocess.TimeoutExpired as e:
        duration_s = time.monotonic() - start
        stdout = _coerce_text(e.stdout)
        stderr = _coerce_text(e.stderr)

        return CommandResult(
            argv=argv_list,
            status=ProbeStatus.TIMEOUT,
            returncode=None,
            stdout=stdout,
            stderr=stderr,
            timed_out=True,
            duration_s=duration_s,
            error_type=type(e).__name__,
            error_message=str(e),
        )

    except FileNotFoundError as e:
        duration_s = time.monotonic() - start

        return CommandResult(
            argv=argv_list,
            status=ProbeStatus.UNSUPPORTED,
            returncode=None,
            stdout="",
            stderr="",
            timed_out=False,
            duration_s=duration_s,
            error_type=type(e).__name__,
            error_message=str(e),
        )

    except Exception as e:  # pragma: no cover
        duration_s = time.monotonic() - start

        return CommandResult(
            argv=argv_list,
            status=ProbeStatus.ERROR,
            returncode=None,
            stdout="",
            stderr="",
            timed_out=False,
            duration_s=duration_s,
            error_type=type(e).__name__,
            error_message=str(e),
        )
