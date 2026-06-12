from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from textwrap import dedent
from uuid import uuid4

from inference_profile import manifests, paths

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "deploy_and_run_remote.sh"


def _write_partial_remote_bundle(run_root: Path) -> dict[str, object]:
    bundle_paths = paths.bundle_paths_from_run_root(run_root)
    for directory in (bundle_paths.run_root, bundle_paths.logs_dir):
        directory.mkdir(parents=True, exist_ok=True)

    manifests.initialize_run_manifest(bundle_paths)
    manifests.update_stage_status(
        bundle_paths.run_manifest_path,
        stage="bootstrap-env",
        status="success",
        details={"dependencies_ready": True},
    )
    manifests.update_stage_status(
        bundle_paths.run_manifest_path,
        stage="validate-traces",
        status="success",
        details={"rows_checked": 12},
    )
    manifests.update_stage_status(
        bundle_paths.run_manifest_path,
        stage="profile",
        status="profile_failed",
        details={"reason": "GPU out of memory"},
        final_status="profile_failed",
    )

    (bundle_paths.logs_dir / "bootstrap-env.log").write_text(
        "bootstrap ok\n",
        encoding="utf-8",
    )
    (bundle_paths.logs_dir / "validate-traces.log").write_text(
        "validate ok\n",
        encoding="utf-8",
    )
    (bundle_paths.logs_dir / "profile.log").write_text(
        "profile failed: out of memory\n",
        encoding="utf-8",
    )
    return json.loads(bundle_paths.run_manifest_path.read_text(encoding="utf-8"))


def _install_fake_sshpass(
    tmp_path: Path, remote_runs_root: Path
) -> tuple[dict[str, str], Path]:
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    log_path = tmp_path / "sshpass-log.jsonl"
    sshpass_path = fake_bin / "sshpass"
    sshpass_path.write_text(
        dedent(
            """
            #!/usr/bin/env python3
            from __future__ import annotations

            import json
            import os
            import shutil
            import sys
            from pathlib import Path

            LOG_PATH = Path(os.environ["FAKE_SSHPASS_LOG"])
            REMOTE_RUNS_ROOT = Path(os.environ["FAKE_REMOTE_RUNS_ROOT"])
            REMOTE_PREFIX = "netsys@192.168.1.20:/home/netsys/dheeraj/inference-profile/runs/"

            args = sys.argv[1:]
            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with LOG_PATH.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(args) + "\\n")

            filtered = []
            index = 0
            while index < len(args):
                if args[index] == "-f":
                    index += 2
                    continue
                filtered.append(args[index])
                index += 1

            if not filtered:
                raise SystemExit("missing sshpass command")

            command = filtered[0]
            if command != "scp":
                raise SystemExit(f"unsupported sshpass command: {command}")

            scp_args = filtered[1:]
            path_args = []
            index = 0
            while index < len(scp_args):
                token = scp_args[index]
                if token == "-o":
                    index += 2
                    continue
                if token == "-r":
                    index += 1
                    continue
                path_args.append(token)
                index += 1

            if len(path_args) != 2:
                raise SystemExit(f"expected src and dst, got: {path_args!r}")

            source_spec, dest_spec = path_args
            if not source_spec.startswith(REMOTE_PREFIX):
                raise SystemExit(f"unexpected remote source: {source_spec}")

            relative_source = source_spec[len(REMOTE_PREFIX):]
            if relative_source.endswith("/."):
                run_id = relative_source[:-2].rstrip("/")
            elif relative_source.endswith("/"):
                run_id = relative_source[:-1]
            else:
                run_id = relative_source

            source_root = REMOTE_RUNS_ROOT / run_id
            dest_root = Path(dest_spec)
            if not source_root.exists():
                raise SystemExit(f"missing fake remote source: {source_root}")

            dest_root.mkdir(parents=True, exist_ok=True)
            for child in source_root.iterdir():
                target = dest_root / child.name
                if child.is_dir():
                    shutil.copytree(child, target, dirs_exist_ok=True)
                else:
                    shutil.copy2(child, target)
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    sshpass_path.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
    env["FAKE_SSHPASS_LOG"] = str(log_path)
    env["FAKE_REMOTE_RUNS_ROOT"] = str(remote_runs_root)
    return env, log_path


def _run_fetch(run_id: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT_PATH), "--stage", "fetch", "--run-id", run_id],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _read_sshpass_commands(log_path: Path) -> list[list[str]]:
    if not log_path.exists():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_fetch_stage_preserves_partial_remote_failure_logs_and_marks_local_manifest_fetch_failed(
    tmp_path: Path,
) -> None:
    run_id = f"fetch-partial-{uuid4().hex}"
    remote_runs_root = tmp_path / "remote-runs"
    remote_run_root = remote_runs_root / run_id
    remote_manifest = _write_partial_remote_bundle(remote_run_root)
    env, log_path = _install_fake_sshpass(tmp_path, remote_runs_root)
    local_run_root = REPO_ROOT / "runs" / run_id

    shutil.rmtree(local_run_root, ignore_errors=True)
    try:
        result = _run_fetch(run_id, env)

        assert result.returncode != 0
        assert (local_run_root / "logs" / "bootstrap-env.log").read_text(
            encoding="utf-8"
        ) == "bootstrap ok\n"
        assert (local_run_root / "logs" / "profile.log").read_text(
            encoding="utf-8"
        ) == "profile failed: out of memory\n"
        assert not (local_run_root / run_id).exists()

        local_manifest = json.loads(
            (local_run_root / "run_manifest.json").read_text(encoding="utf-8")
        )
        assert local_manifest["final_status"] == "profile_failed"
        assert [
            entry["status"] for entry in local_manifest["final_status_history"]
        ] == ["profile_failed"]
        assert local_manifest["stages"] == remote_manifest["stages"]

        sshpass_commands = _read_sshpass_commands(log_path)
        assert len(sshpass_commands) == 1
        assert sshpass_commands[0][2] == "scp"
    finally:
        shutil.rmtree(local_run_root, ignore_errors=True)
