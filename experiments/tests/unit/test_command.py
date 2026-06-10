import subprocess
import sys
from pathlib import Path

import pytest

from ai_runtime_experiments.schemas import ProbeStatus
from ai_runtime_experiments.utils.command import run_command  # pyright: ignore[reportMissingImports]


def test_run_command_success():
    result = run_command([sys.executable, "-c", "print('hello')"], timeout_s=2)

    assert result.status == ProbeStatus.OK
    assert result.returncode == 0
    assert result.stdout.strip() == "hello"
    assert result.stderr == ""
    assert result.timed_out is False
    assert result.error_type is None
    assert result.error_message is None


def test_run_command_timeout():
    result = run_command([sys.executable, "-c", "import time; time.sleep(2)"], timeout_s=0.1)

    assert result.status == ProbeStatus.TIMEOUT
    assert result.timed_out is True
    assert result.returncode is None


def test_run_command_missing_is_unsupported(tmp_path: Path):
    missing_exe = tmp_path / "definitely_missing_executable"
    result = run_command([str(missing_exe)], timeout_s=1)

    assert result.status == ProbeStatus.UNSUPPORTED
    assert result.returncode is None
    assert result.error_type is not None


def test_run_command_does_not_use_shell_by_default(monkeypatch: pytest.MonkeyPatch):
    import ai_runtime_experiments.utils.command as command_module  # pyright: ignore[reportMissingImports]

    captured: dict[str, dict[str, object]] = {}

    def fake_run(args, **kwargs: object):
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr(command_module.subprocess, "run", fake_run)

    result = run_command([sys.executable, "-c", "print('x')"], timeout_s=1)

    assert result.status == ProbeStatus.OK
    assert result.returncode == 0
    assert captured["kwargs"].get("shell", False) is False


def test_run_command_passes_input_text_to_subprocess(monkeypatch: pytest.MonkeyPatch):
    import ai_runtime_experiments.utils.command as command_module  # pyright: ignore[reportMissingImports]

    captured_kwargs: dict[str, object] = {}

    def fake_run(args, **kwargs: object):
        del args
        captured_kwargs.update(kwargs)
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr(command_module.subprocess, "run", fake_run)

    result = run_command([sys.executable, "-c", "print('x')"], timeout_s=1, input_text="hello\n")

    assert result.status == ProbeStatus.OK
    assert result.returncode == 0
    assert captured_kwargs["input"] == "hello\n"
