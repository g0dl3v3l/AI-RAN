# Decisions

## 2026-04-09T20:35:06Z Task: T1 scaffold conventions
- Use a root-package layout under `inference-profile/` rather than NVBenchSuite's separate `python/` subtree.
- Keep CLI entry simple: `def main() -> int`, stdlib `argparse`, subparsers for the eight fixed commands, and `raise SystemExit(main())` (or equivalent) in `inference_profile/cli.py`.
- Register pytest markers in `pyproject.toml` using `[tool.pytest.ini_options]`, and keep GPU tests additionally guarded with runtime skip checks.
