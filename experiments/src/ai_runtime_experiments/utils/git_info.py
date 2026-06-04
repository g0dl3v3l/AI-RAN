from __future__ import annotations

from pathlib import Path
from typing import Any

from ai_runtime_experiments.utils.command import run_command


def get_git_metadata(*, repo_root: str | Path | None = None, timeout_s: float = 2.0) -> dict[str, Any]:
    """Best-effort git metadata capture.

    This must never raise in normal operation; failures are encoded in the
    returned dict.
    """

    cwd = str(repo_root) if repo_root is not None else None
    errors: list[str] = []

    def _run(argv: list[str]) -> str | None:
        result = run_command(argv, timeout_s=timeout_s, cwd=cwd)
        if result.status.value != "ok":
            errors.append(f"{argv[0]} failed: {result.status.value} {result.error_type or ''} {result.error_message or ''}".strip())
            return None
        return result.stdout.strip()

    version = _run(["git", "--version"])
    if version is None:
        return {
            "git_available": False,
            "is_repo": False,
            "toplevel": None,
            "commit": None,
            "branch": None,
            "dirty": None,
            "describe": None,
            "remote_origin_url": None,
            "errors": errors,
        }

    inside = _run(["git", "rev-parse", "--is-inside-work-tree"])
    is_repo = inside == "true"

    if not is_repo:
        return {
            "git_available": True,
            "is_repo": False,
            "toplevel": None,
            "commit": None,
            "branch": None,
            "dirty": None,
            "describe": None,
            "remote_origin_url": None,
            "errors": errors,
        }

    toplevel = _run(["git", "rev-parse", "--show-toplevel"])
    commit = _run(["git", "rev-parse", "HEAD"])
    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])

    status = _run(["git", "status", "--porcelain"])
    dirty = None if status is None else (status != "")

    describe = _run(["git", "describe", "--tags", "--always", "--dirty"])
    remote = _run(["git", "config", "--get", "remote.origin.url"])

    return {
        "git_available": True,
        "is_repo": True,
        "toplevel": toplevel,
        "commit": commit,
        "branch": branch,
        "dirty": dirty,
        "describe": describe,
        "remote_origin_url": remote,
        "errors": errors,
    }
