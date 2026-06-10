from __future__ import annotations

from pathlib import Path

from ai_runtime_experiments.schemas import ProbeStatus
from ai_runtime_experiments.utils.command import CommandResult



def _result(
    argv: list[str],
    *,
    status: ProbeStatus = ProbeStatus.OK,
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> CommandResult:
    return CommandResult(
        argv=list(argv),
        status=status,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        timed_out=False,
        duration_s=0.01,
        error_type=None,
        error_message=None,
    )



def test_builds_dump_and_restore_runc_conf_text():
    from ai_runtime_experiments.criu_config import build_runc_conf_text

    dump_text = build_runc_conf_text(phase="dump")
    restore_text = build_runc_conf_text(phase="restore")

    assert "libdir /usr/local/lib/criu" in dump_text
    assert "mntns-compat-mode" not in dump_text
    assert "mntns-compat-mode" in restore_text



def test_write_runc_conf_uses_noninteractive_sudo_tee():
    from ai_runtime_experiments.criu_config import write_runc_conf

    calls = []

    def runner(argv, *, timeout_s=None, input_text=None, **kwargs):
        del kwargs
        calls.append({"argv": list(argv), "timeout_s": timeout_s, "input_text": input_text})
        return _result(list(argv), stdout="ok\n")

    result = write_runc_conf(phase="restore", runner=runner, timeout_s=3.0, use_sudo=True)

    assert result.status == ProbeStatus.OK
    assert calls[0]["argv"] == ["sudo", "-n", "tee", "/etc/criu/runc.conf"]
    assert calls[0]["timeout_s"] == 3.0
    assert "mntns-compat-mode" in calls[0]["input_text"]



def test_phase_switcher_restores_original_runc_conf_contents(tmp_path: Path):
    from ai_runtime_experiments.criu_config import CriuRuncConfigPhaseSwitcher

    runc_conf_path = tmp_path / "runc.conf"
    lock_path = tmp_path / "runc.conf.lock"
    runc_conf_path.write_text("original\n", encoding="utf-8")

    switcher = CriuRuncConfigPhaseSwitcher(
        runc_conf_path=runc_conf_path,
        lock_path=lock_path,
    )

    acquire_result = switcher.acquire()
    dump_result = switcher.write_phase("dump")
    restore_result = switcher.write_phase("restore")
    cleanup_result = switcher.restore_original()
    release_result = switcher.release()

    assert acquire_result.status == ProbeStatus.OK
    assert dump_result.status == ProbeStatus.OK
    assert restore_result.status == ProbeStatus.OK
    assert cleanup_result.status == ProbeStatus.OK
    assert release_result.status == ProbeStatus.OK
    assert runc_conf_path.read_text(encoding="utf-8") == "original\n"



def test_phase_switcher_removes_runc_conf_when_original_file_was_missing(tmp_path: Path):
    from ai_runtime_experiments.criu_config import CriuRuncConfigPhaseSwitcher

    runc_conf_path = tmp_path / "runc.conf"
    lock_path = tmp_path / "runc.conf.lock"

    switcher = CriuRuncConfigPhaseSwitcher(
        runc_conf_path=runc_conf_path,
        lock_path=lock_path,
    )

    acquire_result = switcher.acquire()
    dump_result = switcher.write_phase("dump")
    cleanup_result = switcher.restore_original()
    release_result = switcher.release()

    assert acquire_result.status == ProbeStatus.OK
    assert dump_result.status == ProbeStatus.OK
    assert cleanup_result.status == ProbeStatus.OK
    assert release_result.status == ProbeStatus.OK
    assert not runc_conf_path.exists()



def test_phase_switcher_reports_lock_contention(tmp_path: Path):
    from ai_runtime_experiments.criu_config import CriuRuncConfigPhaseSwitcher

    runc_conf_path = tmp_path / "runc.conf"
    lock_path = tmp_path / "runc.conf.lock"

    first = CriuRuncConfigPhaseSwitcher(
        runc_conf_path=runc_conf_path,
        lock_path=lock_path,
    )
    second = CriuRuncConfigPhaseSwitcher(
        runc_conf_path=runc_conf_path,
        lock_path=lock_path,
    )

    first_result = first.acquire()
    second_result = second.acquire()
    release_result = first.release()

    assert first_result.status == ProbeStatus.OK
    assert second_result.status == ProbeStatus.ERROR
    assert "lock" in (second_result.error_message or "").lower()
    assert release_result.status == ProbeStatus.OK
