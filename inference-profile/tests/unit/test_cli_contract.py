from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from inference_profile import cli

EXPECTED_SUBCOMMANDS = [
    "bootstrap-env",
    "inspect-model",
    "validate-traces",
    "profile",
    "simulate",
    "report",
    "verify-bundle",
    "run-all",
]


def _subcommand_names() -> list[str]:
    parser = cli.build_parser()

    for action in parser._actions:
        choices = getattr(action, "choices", None)
        if getattr(action, "dest", None) == "command" and isinstance(choices, dict):
            return list(choices)

    raise AssertionError("CLI parser is missing the command subparser group")


def test_build_parser_exposes_exact_subcommand_names() -> None:
    assert _subcommand_names() == EXPECTED_SUBCOMMANDS


def test_module_help_lists_all_stage_subcommands() -> None:
    project_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "-m", "inference_profile.cli", "--help"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Stageable CLI scaffold for remote RAN inference profiling." in result.stdout
    for subcommand in EXPECTED_SUBCOMMANDS:
        assert subcommand in result.stdout
