from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from ai_runtime_experiments.artifacts import write_json
from ai_runtime_experiments.runtime_adapters import DEFAULT_DOCKER_IMAGE, VLLMRuntimeAdapter
from ai_runtime_experiments.schemas import ProbeStatus
from ai_runtime_experiments.utils.paths import ensure_run_dir
from ai_runtime_experiments.workload import LLMSmokeClient



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a single OpenAI-compatible smoke request against a vLLM runtime."
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory that will receive runtime_check.json and smoke request artifacts",
    )
    parser.add_argument("--run-id", required=True, help="Run identifier embedded in the artifacts")
    parser.add_argument("--model", required=True, help="Model name sent to the runtime")
    parser.add_argument(
        "--prompt",
        default="Say pong.",
        help="Prompt content for the single smoke request",
    )
    parser.add_argument(
        "--base-url",
        default="",
        help="Existing OpenAI-compatible base URL (for example http://localhost:8000/v1)",
    )
    parser.add_argument(
        "--allow-docker-start",
        action="store_true",
        help="Start an experiment-owned vLLM Docker container instead of staying in skipped mode",
    )
    parser.add_argument(
        "--docker-image",
        default=DEFAULT_DOCKER_IMAGE,
        help="Docker image used when --allow-docker-start is set",
    )
    parser.add_argument(
        "--docker-port",
        type=int,
        default=8000,
        help="Localhost port bound to the vLLM Docker runtime",
    )
    parser.add_argument(
        "--container-name",
        default="",
        help="Optional fixed container name for the Docker runtime",
    )
    parser.add_argument(
        "--api-key",
        default="EMPTY",
        help="Bearer token sent to OpenAI-compatible runtimes",
    )
    return parser



def _resolve_output_dir(output_dir: str | Path) -> Path:
    requested = Path(output_dir)
    if requested.exists():
        if not requested.is_dir():
            raise NotADirectoryError(f"output-dir exists and is not a directory: {requested}")
        return requested
    return ensure_run_dir(output_root=requested.parent, run_id=requested.name)



def _build_runtime_config(args: argparse.Namespace) -> dict[str, object]:
    docker_server: dict[str, object] = {
        "enabled": args.allow_docker_start,
        "image": args.docker_image,
        "model": args.model,
        "port": args.docker_port,
    }
    if args.container_name:
        docker_server["container_name"] = args.container_name
    return {
        "external_server": {
            "enabled": bool(str(args.base_url).strip()),
            "base_url": args.base_url,
        },
        "docker_server": docker_server,
    }



def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    output_dir = _resolve_output_dir(args.output_dir)

    adapter = VLLMRuntimeAdapter(config=_build_runtime_config(args))
    session = adapter.start(run_id=args.run_id)
    write_json(output_dir / "runtime_check.json", session.runtime_check)

    try:
        if session.smoke_validation is not None:
            write_json(output_dir / "smoke_validation.json", session.smoke_validation)
            return 0

        client = LLMSmokeClient(api_key=args.api_key)
        response_record = client.send_smoke_request(
            run_id=args.run_id,
            output_dir=output_dir,
            base_url=session.base_url or args.base_url,
            model=args.model,
            prompt=args.prompt,
        )
        if response_record["status"] != ProbeStatus.OK.value:
            return 0
        return 0
    finally:
        adapter.stop(session)


if __name__ == "__main__":
    raise SystemExit(main())
