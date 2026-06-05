from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from ai_runtime_experiments.artifacts import write_json
from ai_runtime_experiments.env_probe.mps import collect_mps_probe
from ai_runtime_experiments.utils.paths import ensure_run_dir



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect MPS capability probe artifact.")
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory that will receive mps_check.json",
    )
    parser.add_argument("--run-id", required=True, help="Run identifier embedded in the artifact")
    parser.add_argument(
        "--allow-start-stop",
        action="store_true",
        help="Explicitly allow probe-managed MPS start/stop lifecycle",
    )
    return parser



def _resolve_output_dir(output_dir: str | Path) -> Path:
    requested = Path(output_dir)
    if requested.exists():
        if not requested.is_dir():
            raise NotADirectoryError(f"output-dir exists and is not a directory: {requested}")
        return requested
    return ensure_run_dir(output_root=requested.parent, run_id=requested.name)



def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)

    output_dir = _resolve_output_dir(args.output_dir)
    mps_record = collect_mps_probe(
        run_id=args.run_id,
        allow_start_stop=args.allow_start_stop,
    )
    write_json(output_dir / "mps_check.json", mps_record)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
