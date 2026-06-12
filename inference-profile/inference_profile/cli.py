from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from inference_profile import experiments
from inference_profile import manifests as run_manifests
from inference_profile.run_orchestrator import STAGE_ORDER

SUBCOMMAND_NAMES = (
    "bootstrap-env",
    "inspect-model",
    "validate-traces",
    "profile",
    "simulate",
    "report",
    "verify-bundle",
    "run-all",
)
SUBCOMMANDS = SUBCOMMAND_NAMES

_SUBCOMMAND_HELP = {
    "bootstrap-env": "Bootstrap the profiling environment.",
    "inspect-model": "Inspect fixed OPT model metadata.",
    "validate-traces": "Validate the required RAN traces.",
    "profile": "Run profiling stages (prefill, decode, PCIe).",
    "simulate": "Run the deterministic scheduler simulation.",
    "report": "Generate bundle plots and report artifacts.",
    "verify-bundle": "Verify bundle completeness and checksums.",
    "run-all": "Run the full stage pipeline in order.",
}


def _add_experiment_type_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--experiment-type",
        choices=list(experiments.EXPERIMENT_TYPES),
        default=experiments.LEGACY_EXPERIMENT_TYPE,
        help="Experiment path/version to execute",
    )


class CliUserError(Exception):
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m inference_profile.cli",
        description="Stageable CLI scaffold for remote RAN inference profiling.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap_parser = subparsers.add_parser(
        "bootstrap-env",
        help=_SUBCOMMAND_HELP["bootstrap-env"],
    )
    bootstrap_parser.add_argument("--output-root", type=Path, required=True)
    _add_experiment_type_argument(bootstrap_parser)
    bootstrap_parser.set_defaults(func=_handle_bootstrap_env)

    inspect_parser = subparsers.add_parser(
        "inspect-model",
        help=_SUBCOMMAND_HELP["inspect-model"],
    )
    inspect_parser.add_argument("--model", dest="model_id", required=True)
    inspect_parser.add_argument("--cache-root", type=Path, default=None)
    inspect_parser.add_argument("--output-root", type=Path, required=True)
    inspect_parser.set_defaults(func=_handle_inspect_model)

    validate_parser = subparsers.add_parser(
        "validate-traces",
        help=_SUBCOMMAND_HELP["validate-traces"],
    )
    validate_parser.add_argument("--ldpc-trace", type=Path, required=True)
    validate_parser.add_argument("--ran-ctrl-trace", type=Path, required=True)
    validate_parser.add_argument("--output-root", type=Path, required=True)
    _add_experiment_type_argument(validate_parser)
    validate_parser.set_defaults(func=_handle_validate_traces)

    profile_parser = subparsers.add_parser(
        "profile",
        help=_SUBCOMMAND_HELP["profile"],
    )
    profile_parser.add_argument(
        "--models",
        nargs="+",
        required=True,
        help="Model IDs to profile",
    )
    profile_parser.add_argument(
        "--chunk-sizes",
        type=int,
        nargs="+",
        default=[64, 128, 256, 512, 1024],
        help="Prefill chunk sizes to profile",
    )
    profile_parser.add_argument(
        "--sequence-lengths",
        type=int,
        nargs="+",
        default=[1024, 2048, 4096, 8192],
        help="Decode sequence lengths to profile",
    )
    profile_parser.add_argument(
        "--warmup",
        type=int,
        default=3,
        help="Warmup iterations per profiling point",
    )
    profile_parser.add_argument(
        "--iterations",
        type=int,
        default=5,
        help="Timed iterations per profiling point",
    )
    profile_parser.add_argument(
        "--gpu-id",
        type=int,
        default=0,
        help="GPU device ID",
    )
    profile_parser.add_argument(
        "--sm-ai-partition",
        type=int,
        default=100,
        help="Configured AI SM partition percentage for this profiling run",
    )
    profile_parser.add_argument(
        "--cache-root",
        type=Path,
        default=None,
        help="Cache root for downloaded model artifacts",
    )
    profile_parser.add_argument(
        "--output-root",
        type=Path,
        required=True,
        help="Output root for profiling results",
    )
    _add_experiment_type_argument(profile_parser)
    profile_parser.set_defaults(func=_handle_profile)

    simulate_parser = subparsers.add_parser(
        "simulate",
        help=_SUBCOMMAND_HELP["simulate"],
        description=(
            "Assemble simulation inputs and write canonical derived scheduler "
            "results under the run root."
        ),
    )
    simulate_parser.add_argument(
        "--run-root",
        type=Path,
        required=True,
        help=(
            "Existing run root. Writes derived/simulation_inputs.csv, "
            "derived/ran_inference_profiling_results.csv, and "
            "derived/schedule_timeline.csv in place."
        ),
    )
    _add_experiment_type_argument(simulate_parser)
    simulate_parser.set_defaults(func=_handle_simulate)

    report_parser = subparsers.add_parser(
        "report",
        help=_SUBCOMMAND_HELP["report"],
    )
    report_parser.add_argument("--run-root", type=Path, required=True)
    _add_experiment_type_argument(report_parser)
    report_parser.set_defaults(func=_handle_report)

    verify_parser = subparsers.add_parser(
        "verify-bundle",
        help=_SUBCOMMAND_HELP["verify-bundle"],
    )
    verify_parser.add_argument("--run-root", type=Path, required=True)
    _add_experiment_type_argument(verify_parser)
    verify_parser.set_defaults(func=_handle_verify_bundle)

    run_all_parser = subparsers.add_parser(
        "run-all",
        help=_SUBCOMMAND_HELP["run-all"],
    )
    run_all_parser.add_argument(
        "--run-root",
        type=Path,
        required=False,
        help="Root directory for run outputs",
    )
    run_all_parser.add_argument(
        "--ldpc-trace",
        type=Path,
        required=False,
        help="Path to LDPC trace file",
    )
    run_all_parser.add_argument(
        "--ran-ctrl-trace",
        type=Path,
        required=False,
        help="Path to RAN control trace file",
    )
    run_all_parser.add_argument(
        "--models",
        nargs="+",
        required=False,
        help="Model IDs to profile",
    )
    run_all_parser.add_argument(
        "--chunk-sizes",
        type=int,
        nargs="+",
        required=False,
        help="Chunk sizes for profiling",
    )
    run_all_parser.add_argument(
        "--sequence-lengths",
        type=int,
        nargs="+",
        required=False,
        help="Sequence lengths for profiling",
    )
    run_all_parser.add_argument(
        "--gpu-id",
        type=int,
        default=0,
        help="GPU ID to use (default: 0)",
    )
    run_all_parser.add_argument(
        "--sm-ai-partition",
        type=int,
        default=100,
        help="Configured AI SM partition percentage for this run",
    )
    run_all_parser.add_argument(
        "--cache-root",
        type=Path,
        default=None,
        help="Cache root for models",
    )
    run_all_parser.add_argument(
        "--resume-from",
        choices=list(STAGE_ORDER),
        default=None,
        help="Resume from a specific stage",
    )
    run_all_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Create/load the run manifest and print the planned stage order without executing stages",
    )
    _add_experiment_type_argument(run_all_parser)
    run_all_parser.set_defaults(func=_handle_run_all)

    return parser


def _handle_placeholder(args: argparse.Namespace) -> int:
    raise NotImplementedError(
        f"Subcommand {args.command!r} is scaffolded but not implemented yet."
    )


def _handle_bootstrap_env(args: argparse.Namespace) -> int:
    from inference_profile.bootstrap import bootstrap_environment

    try:
        bootstrap_environment(
            output_root=args.output_root,
            experiment_type=args.experiment_type,
        )
    except Exception as exc:
        raise CliUserError(_exception_message(exc)) from None
    return 0


def _handle_inspect_model(args: argparse.Namespace) -> int:
    from inference_profile.opt_assets import inspect_model

    try:
        inspect_model(
            model_id=args.model_id,
            cache_root=args.cache_root,
            output_root=args.output_root,
        )
    except (KeyError, ValueError) as exc:
        raise CliUserError(_exception_message(exc)) from None
    return 0


def _handle_validate_traces(args: argparse.Namespace) -> int:
    from inference_profile.trace_contract import validate_trace_contract

    result = validate_trace_contract(
        ldpc_trace=args.ldpc_trace,
        ran_ctrl_trace=args.ran_ctrl_trace,
        output_root=args.output_root,
    )
    if not result.success:
        raise CliUserError(result.user_error_message())
    return 0


def _handle_profile(args: argparse.Namespace) -> int:
    from inference_profile.profile_orchestrator import orchestrate_profile_run

    try:
        result = orchestrate_profile_run(
            run_root=args.output_root,
            models=args.models,
            chunk_sizes=args.chunk_sizes,
            sequence_lengths=args.sequence_lengths,
            warmup_iterations=args.warmup,
            timed_iterations=args.iterations,
            gpu_id=args.gpu_id,
            sm_ai_partition=args.sm_ai_partition,
            cache_root=args.cache_root,
            experiment_type=args.experiment_type,
        )
        if not result.success:
            raise CliUserError(
                f"Profiling stage failed; see {result.run_root / 'run_manifest.json'}"
            )
    except (KeyError, ValueError, RuntimeError) as exc:
        raise CliUserError(_exception_message(exc)) from None
    return 0


def _handle_simulate(args: argparse.Namespace) -> int:
    from inference_profile.simulator import run_deterministic_simulation

    try:
        effective_experiment_type = _resolve_run_root_experiment_type(
            run_root=Path(args.run_root),
            experiment_type=args.experiment_type,
        )
        run_deterministic_simulation(
            run_root=args.run_root,
            experiment_type=effective_experiment_type,
        )
    except (KeyError, ValueError) as exc:
        raise CliUserError(_exception_message(exc)) from None
    return 0


def _handle_report(args: argparse.Namespace) -> int:
    from inference_profile.plots import generate_profiling_plots
    from inference_profile.report import generate_run_report

    try:
        effective_experiment_type = _resolve_run_root_experiment_type(
            run_root=Path(args.run_root),
            experiment_type=args.experiment_type,
        )
        generate_profiling_plots(run_root=args.run_root)
        generate_run_report(
            run_root=args.run_root,
            experiment_type=effective_experiment_type,
        )
    except (KeyError, ValueError) as exc:
        raise CliUserError(_exception_message(exc)) from None
    return 0


def _handle_verify_bundle(args: argparse.Namespace) -> int:
    from inference_profile.verify_bundle import verify_bundle

    try:
        run_root = Path(args.run_root)
        effective_experiment_type = _resolve_run_root_experiment_type(
            run_root=run_root,
            experiment_type=args.experiment_type,
        )
        result = verify_bundle(run_root, experiment_type=effective_experiment_type)

        if result["status"] != "success":
            # Build error message
            missing_files = [
                f for f, exists in result["completeness_results"].items() if not exists
            ]
            checksum_failures = [
                f
                for f, check in result["checksum_results"].items()
                if not check.get("match", True)
            ]

            error_msg = "Bundle verification failed:"
            if missing_files:
                error_msg += f" Missing files: {missing_files}."
            if checksum_failures:
                error_msg += f" Checksum failures: {checksum_failures}."

            raise CliUserError(error_msg)
    except (KeyError, ValueError) as exc:
        raise CliUserError(_exception_message(exc)) from None
    return 0


def _handle_run_all(args: argparse.Namespace) -> int:
    from inference_profile.run_orchestrator import run_orchestrator

    try:
        run_root = args.run_root
        if run_root is None:
            if args.experiment_type == experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE:
                bundle_paths = experiments.default_run_id_for_experiment(
                    args.experiment_type
                )
                run_root = Path("runs") / bundle_paths
            else:
                raise CliUserError(
                    "--run-root is required for the legacy experiment path"
                )
        if not args.dry_run:
            missing_args = []
            if args.ldpc_trace is None:
                missing_args.append("--ldpc-trace")
            if args.ran_ctrl_trace is None:
                missing_args.append("--ran-ctrl-trace")
            if not args.models:
                missing_args.append("--models")
            if not args.chunk_sizes:
                missing_args.append("--chunk-sizes")
            if not args.sequence_lengths:
                missing_args.append("--sequence-lengths")
            if missing_args:
                raise CliUserError(
                    "run-all requires the following arguments unless --dry-run is used: "
                    + ", ".join(missing_args)
                )
        manifest = run_orchestrator(
            run_root=run_root,
            ldpc_trace=args.ldpc_trace,
            ran_ctrl_trace=args.ran_ctrl_trace,
            models=args.models,
            chunk_sizes=args.chunk_sizes,
            sequence_lengths=args.sequence_lengths,
            gpu_id=args.gpu_id,
            sm_ai_partition=args.sm_ai_partition,
            cache_root=args.cache_root,
            resume_from=args.resume_from,
            experiment_type=args.experiment_type,
            dry_run=args.dry_run,
        )
        if args.dry_run:
            print("Planned stages:")
            for stage in STAGE_ORDER:
                print(f"- {stage}")
            print(f"Run manifest: {run_root / 'run_manifest.json'}")
            return 0
        if manifest.get("final_status") != "success":
            raise CliUserError(
                f"Run failed with final status: {manifest.get('final_status')}"
            )
    except (KeyError, ValueError, RuntimeError) as exc:
        raise CliUserError(_exception_message(exc)) from None
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except CliUserError as exc:
        parser.exit(status=2, message=f"Error: {exc}\n")
    except NotImplementedError as exc:
        parser.exit(status=2, message=f"{exc}\n")


def _exception_message(exc: Exception) -> str:
    if exc.args:
        return str(exc.args[0])
    return str(exc)


def _resolve_run_root_experiment_type(
    *, run_root: Path, experiment_type: str | None
) -> str | None:
    normalized = experiments.normalize_experiment_type(experiment_type)
    if normalized != experiments.LEGACY_EXPERIMENT_TYPE:
        return normalized
    manifest_path = run_root / "run_manifest.json"
    if not manifest_path.exists():
        return None
    try:
        manifest = run_manifests.load_run_manifest(manifest_path)
    except Exception:
        return None
    manifest_experiment_type = manifest.get("experiment_type")
    if not isinstance(manifest_experiment_type, str):
        return None
    return experiments.normalize_experiment_type(manifest_experiment_type)


if __name__ == "__main__":
    raise SystemExit(main())
