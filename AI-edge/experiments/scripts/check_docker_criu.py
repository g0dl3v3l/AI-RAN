from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from ai_runtime_experiments.artifacts import write_json
from ai_runtime_experiments.docker_criu import collect_criu_probe, collect_docker_criu_integration
from ai_runtime_experiments.utils.paths import ensure_run_dir



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect Docker and CRIU capability probe artifacts."
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory that will receive criu_check.json and docker_criu_integration.json",
    )
    parser.add_argument("--run-id", required=True, help="Run identifier embedded in probe artifacts")
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

    criu_record = collect_criu_probe(run_id=args.run_id)
    integration_record = collect_docker_criu_integration(
        run_id=args.run_id,
        criu_probe=criu_record,
    )

    write_json(output_dir / "criu_check.json", criu_record)
    write_json(output_dir / "docker_criu_integration.json", integration_record)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
