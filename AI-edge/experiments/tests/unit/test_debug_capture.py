from pathlib import Path
from typing import Any

from ai_runtime_experiments.schemas import ProbeStatus
from ai_runtime_experiments.utils.command import CommandResult



def _result(
    argv,
    *,
    status=ProbeStatus.OK,
    stdout="",
    stderr="",
    returncode=0,
    error_type=None,
    error_message=None,
):
    return CommandResult(
        list(argv),
        status,
        returncode,
        stdout,
        stderr,
        False,
        0.01,
        error_type,
        error_message,
    )



def test_extract_criu_log_paths_deduplicates_command_text():
    from ai_runtime_experiments.debug_capture import extract_criu_log_paths

    record: dict[str, Any] = {
        "details": {
            "commands": {
                "a": {"stderr": "path= /run/containerd/a/criu-dump.log\n"},
                "b": {"stderr": "path= /run/containerd/a/criu-dump.log\n"},
            }
        }
    }

    assert extract_criu_log_paths(record) == [Path("/run/containerd/a/criu-dump.log")]



def test_capture_criu_logs_copies_existing_file(tmp_path: Path):
    from ai_runtime_experiments.debug_capture import capture_criu_logs_for_record

    source = tmp_path / "criu-dump.log"
    source.write_text("dump root cause\n", encoding="utf-8")
    record: dict[str, Any] = {
        "details": {
            "commands": {
                "checkpoint": {"stderr": f"failed path= {source}\n"},
            }
        }
    }

    capture_criu_logs_for_record(
        run_dir=tmp_path / "run",
        artifact_name="docker_criu_integration.json",
        record=record,
    )

    copied = (
        tmp_path
        / "run"
        / "criu_logs"
        / "docker_criu_integration"
        / "01-criu-dump.log"
    )
    assert copied.read_text(encoding="utf-8") == "dump root cause\n"
    assert copied.stat().st_mode & 0o777 == 0o600
    assert record["details"]["diagnostics"]["criu_logs"][0]["status"] == "ok"



def test_capture_criu_logs_uses_sudo_cat_for_permission_error(tmp_path: Path, monkeypatch):
    import ai_runtime_experiments.debug_capture as debug_capture

    source = Path("/run/containerd/io.containerd.runtime.v2.task/moby/id/criu-dump.log")
    record: dict[str, Any] = {
        "details": {
            "commands": {
                "checkpoint": {"stderr": f"path= {source}\n"},
            }
        }
    }
    monkeypatch.setattr(
        debug_capture.shutil,
        "copyfile",
        lambda src, dst: (_ for _ in ()).throw(PermissionError("denied")),
    )
    calls = []

    def runner(argv, *, timeout_s=None, **kwargs):
        del kwargs
        calls.append((list(argv), timeout_s))
        return _result(argv, stdout="TOKEN=secret-value\nroot dump\n")

    debug_capture.capture_criu_logs_for_record(
        run_dir=tmp_path / "run",
        artifact_name="docker_criu_integration.json",
        record=record,
        runner=runner,
    )

    assert calls == [(["sudo", "-n", "cat", str(source)], 5.0)]
    entry = record["details"]["diagnostics"]["criu_logs"][0]
    assert (
        tmp_path
        / "run"
        / "criu_logs"
        / "docker_criu_integration"
        / "01-criu-dump.log"
    ).read_text(encoding="utf-8") == "TOKEN=[REDACTED]\nroot dump\n"
    assert "secret-value" not in entry["fallback_command"]["stdout"]



def test_collect_debug_bundle_redacts_and_bounds_outputs(tmp_path: Path):
    from ai_runtime_experiments.debug_capture import collect_debug_bundle

    responses = {
        ("docker", "version"): _result(["docker", "version"], stdout="Docker version\n"),
        ("docker", "info"): _result(["docker", "info"], stdout="TOKEN=secret-value\n"),
        (
            "docker",
            "ps",
            "-a",
            "--filter",
            "label=ai-edge-experiment=v0",
        ): _result(
            ["docker", "ps", "-a", "--filter", "label=ai-edge-experiment=v0"],
            stdout="CONTAINER ID\n",
        ),
        ("criu", "--version"): _result(["criu", "--version"], stdout="Version: 4.2\n"),
        ("criu", "check", "--all"): _result(
            ["criu", "check", "--all"],
            status=ProbeStatus.ERROR,
            returncode=1,
            stderr="warn\n",
        ),
        ("runc", "--version"): _result(["runc", "--version"], stdout="runc version\n"),
        ("nvidia-smi",): _result(["nvidia-smi"], stdout="GPU\n"),
        ("nvidia-smi", "-q"): _result(["nvidia-smi", "-q"], stdout="GPU query\n"),
        ("which", "cuda-checkpoint"): _result(
            ["which", "cuda-checkpoint"],
            status=ProbeStatus.ERROR,
            returncode=1,
            stderr="missing\n",
        ),
        ("sudo", "-n", "cat", "/etc/criu/runc.conf"): _result(
            ["sudo", "-n", "cat", "/etc/criu/runc.conf"],
            stdout="enable-external-masters\n",
        ),
        (
            "sudo",
            "-n",
            "journalctl",
            "-u",
            "docker",
            "--since",
            "1 hour ago",
            "-n",
            "500",
            "--no-pager",
        ): _result(
            [
                "sudo",
                "-n",
                "journalctl",
                "-u",
                "docker",
                "--since",
                "1 hour ago",
                "-n",
                "500",
                "--no-pager",
            ],
            stdout="docker journal\n",
        ),
        (
            "sudo",
            "-n",
            "journalctl",
            "-u",
            "containerd",
            "--since",
            "1 hour ago",
            "-n",
            "500",
            "--no-pager",
        ): _result(
            [
                "sudo",
                "-n",
                "journalctl",
                "-u",
                "containerd",
                "--since",
                "1 hour ago",
                "-n",
                "500",
                "--no-pager",
            ],
            stdout="containerd journal\n",
        ),
    }

    def runner(argv, *, timeout_s=None, **kwargs):
        del timeout_s, kwargs
        return responses[tuple(argv)]

    diagnostics = collect_debug_bundle(run_dir=tmp_path, runner=runner, since="1 hour ago")

    assert (tmp_path / "debug" / "docker-version.txt").read_text(encoding="utf-8") == "Docker version\n"
    assert "secret-value" not in (tmp_path / "debug" / "docker-info.txt").read_text(encoding="utf-8")
    assert "secret-value" not in diagnostics["commands"]["docker_info"]["stdout"]
    assert diagnostics["commands"]["criu_check_all"]["status"] == "error"
