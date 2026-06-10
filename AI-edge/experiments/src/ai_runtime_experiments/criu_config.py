from __future__ import annotations

import fcntl
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

from ai_runtime_experiments.schemas import ProbeStatus
from ai_runtime_experiments.utils.command import CommandResult, run_command

RUNC_CONF_PATH = Path("/etc/criu/runc.conf")
RUNC_CONF_LOCK_PATH = Path("/tmp/ai-edge-criu-runc-conf.lock")
_BASE_LINES = [
    "libdir /usr/local/lib/criu",
    "ext-mount-map auto",
    "external mnt[]",
    "enable-external-masters",
    "tcp-established",
    "link-remap",
    "file-locks",
    "ghost-limit 1073741824",
]

CommandRunner = Callable[..., CommandResult]



def _command_result(
    argv: list[str],
    *,
    status: ProbeStatus,
    returncode: int | None = 0,
    stdout: str = "",
    stderr: str = "",
    error_type: str | None = None,
    error_message: str | None = None,
) -> CommandResult:
    return CommandResult(
        argv=list(argv),
        status=status,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        timed_out=False,
        duration_s=0.0,
        error_type=error_type,
        error_message=error_message,
    )



def _looks_like_missing_file(result: CommandResult) -> bool:
    text = "\n".join(
        part for part in (result.stderr, result.error_message or "") if part
    ).lower()
    return result.error_type == "FileNotFoundError" or "no such file or directory" in text



def _write_text(
    path: Path,
    text: str,
    *,
    runner: CommandRunner,
    timeout_s: float,
    use_sudo: bool,
) -> CommandResult:
    if use_sudo:
        return runner(
            ["sudo", "-n", "tee", str(path)],
            timeout_s=timeout_s,
            input_text=text,
        )

    start = time.monotonic()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        duration_s = time.monotonic() - start
        return CommandResult(
            argv=["tee", str(path)],
            status=ProbeStatus.OK,
            returncode=0,
            stdout=text,
            stderr="",
            timed_out=False,
            duration_s=duration_s,
            error_type=None,
            error_message=None,
        )
    except Exception as exc:  # pragma: no cover - exercised via command mocks in tests
        duration_s = time.monotonic() - start
        return CommandResult(
            argv=["tee", str(path)],
            status=ProbeStatus.ERROR,
            returncode=1,
            stdout="",
            stderr=str(exc),
            timed_out=False,
            duration_s=duration_s,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )



def _read_text(
    path: Path,
    *,
    runner: CommandRunner,
    timeout_s: float,
    use_sudo: bool,
) -> CommandResult:
    if use_sudo:
        return runner(["sudo", "-n", "cat", str(path)], timeout_s=timeout_s)

    start = time.monotonic()
    try:
        stdout = path.read_text(encoding="utf-8")
        duration_s = time.monotonic() - start
        return CommandResult(
            argv=["cat", str(path)],
            status=ProbeStatus.OK,
            returncode=0,
            stdout=stdout,
            stderr="",
            timed_out=False,
            duration_s=duration_s,
            error_type=None,
            error_message=None,
        )
    except FileNotFoundError as exc:
        duration_s = time.monotonic() - start
        return CommandResult(
            argv=["cat", str(path)],
            status=ProbeStatus.ERROR,
            returncode=1,
            stdout="",
            stderr=str(exc),
            timed_out=False,
            duration_s=duration_s,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
    except Exception as exc:  # pragma: no cover - exercised via command mocks in tests
        duration_s = time.monotonic() - start
        return CommandResult(
            argv=["cat", str(path)],
            status=ProbeStatus.ERROR,
            returncode=1,
            stdout="",
            stderr=str(exc),
            timed_out=False,
            duration_s=duration_s,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )



def remove_runc_conf(
    *,
    runner: CommandRunner = run_command,
    timeout_s: float = 5.0,
    use_sudo: bool = False,
    runc_conf_path: str | Path = RUNC_CONF_PATH,
) -> CommandResult:
    path = Path(runc_conf_path)
    if use_sudo:
        return runner(["sudo", "-n", "rm", "-f", str(path)], timeout_s=timeout_s)

    start = time.monotonic()
    try:
        path.unlink(missing_ok=True)
        duration_s = time.monotonic() - start
        return CommandResult(
            argv=["rm", "-f", str(path)],
            status=ProbeStatus.OK,
            returncode=0,
            stdout="",
            stderr="",
            timed_out=False,
            duration_s=duration_s,
            error_type=None,
            error_message=None,
        )
    except Exception as exc:  # pragma: no cover - exercised via command mocks in tests
        duration_s = time.monotonic() - start
        return CommandResult(
            argv=["rm", "-f", str(path)],
            status=ProbeStatus.ERROR,
            returncode=1,
            stdout="",
            stderr=str(exc),
            timed_out=False,
            duration_s=duration_s,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )



def build_runc_conf_text(*, phase: Literal["dump", "restore"]) -> str:
    lines = list(_BASE_LINES)
    if phase == "restore":
        lines.append("mntns-compat-mode")
    return "\n".join(lines) + "\n"



def write_runc_conf(
    *,
    phase: Literal["dump", "restore"],
    runner: CommandRunner = run_command,
    timeout_s: float = 5.0,
    use_sudo: bool = False,
    runc_conf_path: str | Path = RUNC_CONF_PATH,
) -> CommandResult:
    return _write_text(
        Path(runc_conf_path),
        build_runc_conf_text(phase=phase),
        runner=runner,
        timeout_s=timeout_s,
        use_sudo=use_sudo,
    )



@dataclass
class CriuRuncConfigPhaseSwitcher:
    runner: CommandRunner = run_command
    timeout_s: float = 5.0
    use_sudo: bool = False
    runc_conf_path: str | Path = RUNC_CONF_PATH
    lock_path: str | Path = RUNC_CONF_LOCK_PATH
    diagnostics: dict[str, Any] = field(default_factory=dict)
    lock_result: CommandResult | None = field(init=False, default=None)
    capture_original_result: CommandResult | None = field(init=False, default=None)
    restore_original_result: CommandResult | None = field(init=False, default=None)
    release_result: CommandResult | None = field(init=False, default=None)
    original_text: str | None = field(init=False, default=None)
    original_exists: bool = field(init=False, default=False)
    _cleanup_enabled: bool = field(init=False, default=False, repr=False)
    _lock_handle: Any = field(init=False, default=None, repr=False)

    def __post_init__(self) -> None:
        self.diagnostics = {
            "lock": {"path": str(Path(self.lock_path)), "status": "not_attempted"},
            "original": {"path": str(Path(self.runc_conf_path)), "status": "not_attempted"},
            "restore_original": {"path": str(Path(self.runc_conf_path)), "status": "not_attempted"},
        }

    def acquire(self) -> CommandResult:
        lock_path = Path(self.lock_path)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        argv = ["flock", str(lock_path)]
        try:
            lock_handle = lock_path.open("a+", encoding="utf-8")
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._lock_handle = lock_handle
            self.lock_result = _command_result(argv, status=ProbeStatus.OK)
            self.diagnostics["lock"].update({"status": ProbeStatus.OK.value, "acquired": True})
        except BlockingIOError as exc:
            self.lock_result = _command_result(
                argv,
                status=ProbeStatus.ERROR,
                returncode=1,
                error_type=type(exc).__name__,
                error_message="CRIU runc.conf lock contention",
                stderr="CRIU runc.conf lock contention",
            )
            self.diagnostics["lock"].update(
                {
                    "status": ProbeStatus.ERROR.value,
                    "acquired": False,
                    "reason": "CRIU runc.conf lock contention",
                }
            )
            return self.lock_result

        read_result = _read_text(
            Path(self.runc_conf_path),
            runner=self.runner,
            timeout_s=self.timeout_s,
            use_sudo=self.use_sudo,
        )
        if _looks_like_missing_file(read_result):
            self.capture_original_result = _command_result(
                list(read_result.argv),
                status=ProbeStatus.OK,
                stdout="",
                stderr=read_result.stderr,
                error_type=read_result.error_type,
                error_message=read_result.error_message,
            )
            self.original_exists = False
            self.original_text = None
            self._cleanup_enabled = True
            self.diagnostics["original"].update(
                {
                    "status": ProbeStatus.OK.value,
                    "exists": False,
                }
            )
            return self.lock_result

        self.capture_original_result = read_result
        if read_result.status != ProbeStatus.OK:
            self.diagnostics["original"].update(
                {
                    "status": read_result.status.value,
                    "exists": None,
                    "error_type": read_result.error_type,
                    "error_message": read_result.error_message,
                }
            )
            self._cleanup_enabled = False
            self.release()
            return read_result

        self.original_exists = True
        self.original_text = read_result.stdout
        self._cleanup_enabled = True
        self.diagnostics["original"].update(
            {
                "status": ProbeStatus.OK.value,
                "exists": True,
            }
        )
        return self.lock_result

    def write_phase(self, phase: Literal["dump", "restore"]) -> CommandResult:
        return write_runc_conf(
            phase=phase,
            runner=self.runner,
            timeout_s=self.timeout_s,
            use_sudo=self.use_sudo,
            runc_conf_path=self.runc_conf_path,
        )

    def restore_original(self) -> CommandResult:
        if not self._cleanup_enabled:
            self.restore_original_result = _command_result(
                ["restore", str(Path(self.runc_conf_path))],
                status=ProbeStatus.OK,
            )
            self.diagnostics["restore_original"].update(
                {
                    "status": ProbeStatus.OK.value,
                    "exists": self.original_exists,
                    "skipped": True,
                }
            )
            return self.restore_original_result

        if self.original_exists:
            result = _write_text(
                Path(self.runc_conf_path),
                self.original_text or "",
                runner=self.runner,
                timeout_s=self.timeout_s,
                use_sudo=self.use_sudo,
            )
        else:
            result = remove_runc_conf(
                runner=self.runner,
                timeout_s=self.timeout_s,
                use_sudo=self.use_sudo,
                runc_conf_path=self.runc_conf_path,
            )
        self.restore_original_result = result
        self.diagnostics["restore_original"].update(
            {
                "status": result.status.value,
                "exists": self.original_exists,
                "error_type": result.error_type,
                "error_message": result.error_message,
            }
        )
        return result

    def release(self) -> CommandResult:
        argv = ["funlock", str(Path(self.lock_path))]
        if self._lock_handle is None:
            self.release_result = _command_result(argv, status=ProbeStatus.OK)
            self.diagnostics["lock"].update({"released": True})
            return self.release_result

        try:
            fcntl.flock(self._lock_handle.fileno(), fcntl.LOCK_UN)
            self._lock_handle.close()
            self._lock_handle = None
            self.release_result = _command_result(argv, status=ProbeStatus.OK)
            self.diagnostics["lock"].update({"released": True})
            return self.release_result
        except Exception as exc:  # pragma: no cover - defensive cleanup path
            self.release_result = _command_result(
                argv,
                status=ProbeStatus.ERROR,
                returncode=1,
                error_type=type(exc).__name__,
                error_message=str(exc),
                stderr=str(exc),
            )
            self.diagnostics["lock"].update(
                {
                    "released": False,
                    "release_error": str(exc),
                }
            )
            return self.release_result
