#!/usr/bin/env python3
"""OpenCode wrapper for teng-lin/notebooklm-py CLI.

This adapter intentionally shells out to the upstream `notebooklm` command so that
OpenCode workflows can use stable local command contracts while keeping all API
behavior delegated to `notebooklm-py`.
"""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from typing import Sequence


def _tool_bin() -> str:
    return os.environ.get("NOTEBOOKLM_PY_BIN", "notebooklm")


def _format_cmd(parts: Sequence[str]) -> str:
    return " ".join(shlex.quote(p) for p in parts)


def _run(parts: list[str], *, dry_run: bool = False) -> int:
    print(f"$ {_format_cmd(parts)}")
    if dry_run:
        return 0
    completed = subprocess.run(parts, check=False)
    return completed.returncode


def _require_binary() -> str:
    bin_name = _tool_bin()
    resolved = shutil.which(bin_name)
    if not resolved:
        raise RuntimeError(
            "Could not find notebooklm-py CLI binary. "
            "Install with 'pip install notebooklm-py' (or set NOTEBOOKLM_PY_BIN)."
        )
    return bin_name


def _exec_known(bin_name: str, argv: list[str], *, dry_run: bool = False) -> int:
    return _run([bin_name, *argv], dry_run=dry_run)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="OpenCode-friendly adapter for notebooklm-py CLI"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print command without executing",
    )

    def _add_dry_run_arg(cmd_parser: argparse.ArgumentParser) -> None:
        cmd_parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print command without executing",
        )

    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="Check CLI availability")
    _add_dry_run_arg(doctor)
    doctor.add_argument(
        "--auth-test",
        action="store_true",
        help="Also run 'notebooklm auth check --test'",
    )

    login = subparsers.add_parser("login", help="Run notebooklm login")
    _add_dry_run_arg(login)

    create = subparsers.add_parser("create", help="Create notebook")
    _add_dry_run_arg(create)
    create.add_argument("--title", required=True)

    use = subparsers.add_parser("use", help="Switch active notebook")
    _add_dry_run_arg(use)
    use.add_argument("--notebook-id", required=True)

    source_add = subparsers.add_parser("source-add", help="Add source")
    _add_dry_run_arg(source_add)
    source_add.add_argument("--kind", required=True, help="e.g., web/pdf/text/youtube")
    source_add.add_argument(
        "--value", required=True, help="URL/path/text depending on kind"
    )

    source_add_research = subparsers.add_parser(
        "source-add-research", help="Add web research results"
    )
    _add_dry_run_arg(source_add_research)
    source_add_research.add_argument("--query", required=True)
    source_add_research.add_argument(
        "--extra",
        nargs=argparse.REMAINDER,
        default=[],
        help="Additional passthrough args (prefix with --extra -- ...)",
    )

    ask = subparsers.add_parser("ask", help="Ask notebook question")
    _add_dry_run_arg(ask)
    ask.add_argument("--question", required=True)

    generate = subparsers.add_parser("generate", help="Generate artifact")
    _add_dry_run_arg(generate)
    generate.add_argument(
        "--artifact", required=True, help="e.g., study-guide/faq/timeline/podcast"
    )

    download = subparsers.add_parser("download", help="Download artifact")
    _add_dry_run_arg(download)
    download.add_argument("--artifact-id", required=True)
    download.add_argument("--output", required=False)

    metadata = subparsers.add_parser("metadata", help="Show metadata as JSON")
    _add_dry_run_arg(metadata)
    share_status = subparsers.add_parser("share-status", help="Show share status")
    _add_dry_run_arg(share_status)
    skill_install = subparsers.add_parser(
        "skill-install", help="Install local notebooklm skill"
    )
    _add_dry_run_arg(skill_install)

    raw = subparsers.add_parser("raw", help="Pass arbitrary args to notebooklm")
    _add_dry_run_arg(raw)
    raw.add_argument(
        "args",
        nargs=argparse.REMAINDER,
        help="Arguments passed to notebooklm CLI",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        bin_name = _require_binary()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    dry_run = bool(args.dry_run)

    if args.command == "doctor":
        rc = _exec_known(bin_name, ["--help"], dry_run=dry_run)
        if rc != 0:
            return rc
        if args.auth_test:
            return _exec_known(bin_name, ["auth", "check", "--test"], dry_run=dry_run)
        return 0

    if args.command == "login":
        return _exec_known(bin_name, ["login"], dry_run=dry_run)

    if args.command == "create":
        return _exec_known(bin_name, ["create", args.title], dry_run=dry_run)

    if args.command == "use":
        return _exec_known(bin_name, ["use", args.notebook_id], dry_run=dry_run)

    if args.command == "source-add":
        return _exec_known(
            bin_name,
            ["source", "add", args.kind, args.value],
            dry_run=dry_run,
        )

    if args.command == "source-add-research":
        return _exec_known(
            bin_name,
            ["source", "add-research", args.query, *args.extra],
            dry_run=dry_run,
        )

    if args.command == "ask":
        return _exec_known(bin_name, ["ask", args.question], dry_run=dry_run)

    if args.command == "generate":
        return _exec_known(bin_name, ["generate", args.artifact], dry_run=dry_run)

    if args.command == "download":
        cmd = [bin_name, "download", args.artifact_id]
        if args.output:
            cmd.extend(["--output", args.output])
        return _run(cmd, dry_run=dry_run)

    if args.command == "metadata":
        return _exec_known(bin_name, ["metadata", "--json"], dry_run=dry_run)

    if args.command == "share-status":
        return _exec_known(bin_name, ["share", "status"], dry_run=dry_run)

    if args.command == "skill-install":
        return _exec_known(bin_name, ["skill", "install"], dry_run=dry_run)

    if args.command == "raw":
        if not args.args:
            print("ERROR: raw mode requires args after --", file=sys.stderr)
            return 2
        return _exec_known(bin_name, list(args.args), dry_run=dry_run)

    print(f"Unhandled command: {args.command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
