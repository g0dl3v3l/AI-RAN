from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from textwrap import dedent
from uuid import uuid4

from inference_profile import manifests, paths
from inference_profile.paths import CHECKSUM_MANIFEST_RELATIVE_PATH
from inference_profile.verify_bundle import (
    REQUIRED_BUNDLE_FILES,
    compute_file_checksum,
    verify_bundle,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "deploy_and_run_remote.sh"


def _write_complete_remote_bundle(run_root: Path) -> dict[str, object]:
    checksum_relative_path = CHECKSUM_MANIFEST_RELATIVE_PATH.as_posix()
    bundle_paths = paths.bundle_paths_from_run_root(run_root)
    for directory in bundle_paths.directories:
        directory.mkdir(parents=True, exist_ok=True)

    manifests.initialize_run_manifest(bundle_paths)
    manifests.update_stage_status(
        bundle_paths.run_manifest_path,
        stage="report",
        status="success",
        details={"artifact": bundle_paths.report_path.name},
    )
    manifests.update_stage_status(
        bundle_paths.run_manifest_path,
        stage="verify-bundle",
        status="success",
        details={"verified_locally": True},
        final_status="success",
    )
    (bundle_paths.logs_dir / "profile-stage.log").write_text(
        "profile stage complete\n",
        encoding="utf-8",
    )

    for relative_path in REQUIRED_BUNDLE_FILES:
        if relative_path in {"run_manifest.json", checksum_relative_path}:
            continue
        artifact_path = run_root / relative_path
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(f"{relative_path}\n", encoding="utf-8")

    _rewrite_checksum_manifest(run_root)
    return json.loads(bundle_paths.run_manifest_path.read_text(encoding="utf-8"))


def _rewrite_checksum_manifest(run_root: Path) -> None:
    checksum_relative_path = CHECKSUM_MANIFEST_RELATIVE_PATH.as_posix()
    checksum_path = run_root / checksum_relative_path
    checksum_path.parent.mkdir(parents=True, exist_ok=True)

    checksum_lines = []
    relative_paths = list(REQUIRED_BUNDLE_FILES)
    relative_paths.extend(
        sorted(
            path.relative_to(run_root).as_posix()
            for path in (run_root / "logs").rglob("*")
            if path.is_file()
        )
    )
    for relative_path in relative_paths:
        if relative_path == checksum_relative_path:
            continue
        artifact_path = run_root / relative_path
        checksum_lines.append(
            f"{compute_file_checksum(artifact_path)}  {relative_path}"
        )

    checksum_path.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")


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
            copy_contents = relative_source.endswith("/.") or relative_source.endswith("/")
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
            if copy_contents:
                for child in source_root.iterdir():
                    target = dest_root / child.name
                    if child.is_dir():
                        shutil.copytree(child, target, dirs_exist_ok=True)
                    else:
                        shutil.copy2(child, target)
            else:
                shutil.copytree(source_root, dest_root / source_root.name, dirs_exist_ok=True)
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


def test_fetch_stage_copies_bundle_into_fixed_local_run_root_and_repeat_fetch_stays_fetch_only(
    tmp_path: Path,
) -> None:
    run_id = f"fetch-success-{uuid4().hex}"
    remote_runs_root = tmp_path / "remote-runs"
    remote_run_root = remote_runs_root / run_id
    remote_manifest = _write_complete_remote_bundle(remote_run_root)
    env, log_path = _install_fake_sshpass(tmp_path, remote_runs_root)
    local_run_root = REPO_ROOT / "runs" / run_id
    local_backup_root = REPO_ROOT / "runs" / f".{run_id}.previous"

    shutil.rmtree(local_run_root, ignore_errors=True)
    shutil.rmtree(local_backup_root, ignore_errors=True)
    try:
        first_result = _run_fetch(run_id, env)
        assert first_result.returncode == 0, first_result.stderr
        assert (local_run_root / "run_manifest.json").exists()
        assert not (local_run_root / run_id).exists()
        assert verify_bundle(local_run_root)["status"] == "success"
        assert (
            json.loads(
                (local_run_root / "run_manifest.json").read_text(encoding="utf-8")
            )
            == remote_manifest
        )

        updated_environment = remote_run_root / "environment.json"
        updated_environment.write_text(
            '{"revision": "second-fetch"}\n', encoding="utf-8"
        )
        _rewrite_checksum_manifest(remote_run_root)

        second_result = _run_fetch(run_id, env)
        assert second_result.returncode == 0, second_result.stderr
        assert updated_environment.read_text(encoding="utf-8") == (
            local_run_root / "environment.json"
        ).read_text(encoding="utf-8")
        assert not local_backup_root.exists()

        sshpass_commands = _read_sshpass_commands(log_path)
        assert len(sshpass_commands) == 2
        assert all(command[2] == "scp" for command in sshpass_commands)
    finally:
        shutil.rmtree(local_run_root, ignore_errors=True)
        shutil.rmtree(local_backup_root, ignore_errors=True)
