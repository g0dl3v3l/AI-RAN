from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from ai_runtime_experiments.artifacts import write_json
from ai_runtime_experiments.env_probe.cuda import DEFAULT_CUDA_IMAGE, collect_cuda_container_probe
from ai_runtime_experiments.utils.paths import ensure_run_dir



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect CUDA container capability probe artifact."
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory that will receive cuda_check.json",
    )
    parser.add_argument("--run-id", required=True, help="Run identifier embedded in the artifact")
    parser.add_argument(
        "--image",
        default=DEFAULT_CUDA_IMAGE,
        help="CUDA container image used for docker run --gpus all",
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
    cuda_record = collect_cuda_container_probe(run_id=args.run_id, image=args.image)
    write_json(output_dir / "cuda_check.json", cuda_record)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
