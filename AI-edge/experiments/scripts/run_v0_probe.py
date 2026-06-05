from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from ai_runtime_experiments.config import load_config
from ai_runtime_experiments.v0_orchestrator import run_v0_orchestrator



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the V0 AI runtime probe orchestrator.")
    parser.add_argument("--config", required=True, help="Path to the V0 probe config YAML file.")
    parser.add_argument(
        "--output-dir",
        help="Optional run-directory override. Artifacts are written directly into this path.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write a complete deterministic artifact set without running Docker/GPU/vLLM probes.",
    )
    return parser



def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config(
            Path(args.config),
            output_dir_override=Path(args.output_dir) if args.output_dir else None,
            dry_run=bool(args.dry_run),
        )
        result = run_v0_orchestrator(config)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"V0 orchestration complete: {result.run_dir}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
