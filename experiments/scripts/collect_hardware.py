from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from ai_runtime_experiments.artifacts import write_json
from ai_runtime_experiments.env_probe import collect_docker_probe, collect_hardware_probe


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect host hardware and Docker probe artifacts.")
    parser.add_argument("--output-dir", required=True, help="Directory that will receive hardware.json and docker.json")
    parser.add_argument("--run-id", required=True, help="Run identifier embedded in probe artifacts")
    return parser



def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    hardware_record = collect_hardware_probe(run_id=args.run_id)
    docker_record = collect_docker_probe(run_id=args.run_id)

    write_json(output_dir / "hardware.json", hardware_record)
    write_json(output_dir / "docker.json", docker_record)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
