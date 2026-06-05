from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ai_runtime_experiments.artifacts import append_jsonl, write_json
from ai_runtime_experiments.config import ResolvedConfig, dump_config_yaml
from ai_runtime_experiments.docker_criu.probe import (
    collect_criu_probe,
    collect_docker_criu_integration,
)
from ai_runtime_experiments.env_probe.cuda import collect_cuda_container_probe
from ai_runtime_experiments.env_probe.docker import collect_docker_probe
from ai_runtime_experiments.env_probe.hardware import collect_hardware_probe
from ai_runtime_experiments.env_probe.mps import collect_mps_probe
from ai_runtime_experiments.preemption import collect_smoke_preemption
from ai_runtime_experiments.runtime_adapters import RuntimeSession, VLLMRuntimeAdapter
from ai_runtime_experiments.schemas import SCHEMA_VERSION, ProbeStatus, make_probe_result
from ai_runtime_experiments.utils.git_info import get_git_metadata
from ai_runtime_experiments.utils.paths import ensure_run_dir
from ai_runtime_experiments.utils.time import monotonic_ns, utc_now_iso_z
from ai_runtime_experiments.validation import classify_smoke_validation, make_smoke_not_attempted_validation
from ai_runtime_experiments.workload.llm_client import LLMSmokeClient

REQUIRED_V0_ARTIFACTS = {
    "hardware.json",
    "docker.json",
    "criu_check.json",
    "docker_criu_integration.json",
    "cuda_check.json",
    "mps_check.json",
    "runtime_check.json",
    "smoke_request.jsonl",
    "smoke_response.jsonl",
    "smoke_preemption.json",
    "smoke_validation.json",
    "run_metadata.json",
    "config.yaml",
}


@dataclass(frozen=True)
class OrchestratorResult:
    run_id: str
    run_dir: Path
    metadata: dict[str, Any]
    artifacts: dict[str, Path]



def _probe_status(record: dict[str, Any]) -> str:
    return str(record.get("status") or ProbeStatus.ERROR.value)



def _artifact_path(run_dir: Path, artifact_name: str) -> Path:
    return run_dir / artifact_name



def _probe_details(record: dict[str, Any]) -> dict[str, Any]:
    details = record.get("details")
    if isinstance(details, dict):
        return details
    return {}



def _probe_extracted(record: dict[str, Any]) -> dict[str, Any]:
    extracted = _probe_details(record).get("extracted")
    if isinstance(extracted, dict):
        return extracted
    return {}



def _build_hardware_summary(records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    extracted = _probe_extracted(records.get("hardware.json", {}))
    summary: dict[str, Any] = {}
    for key in (
        "cpu_model",
        "cpu_core_count",
        "system_memory_total_bytes",
        "vram_total_mib",
        "gpu_count",
        "gpu_names",
        "driver_version",
        "cuda_version",
    ):
        if key in extracted:
            summary[key] = deepcopy(extracted[key])
    return summary



def _build_mps_summary(records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    record = records.get("mps_check.json", {})
    details = _probe_details(record)
    summary: dict[str, Any] = {"status": _probe_status(record)}

    mode = details.get("mode")
    if mode is not None:
        summary["mode"] = mode

    reason = details.get("reason")
    if reason is not None:
        summary["reason"] = reason

    start_stop = details.get("start_stop")
    if isinstance(start_stop, dict):
        if "allowed" in start_stop:
            summary["allow_start_stop"] = bool(start_stop["allowed"])
        if "attempted" in start_stop:
            summary["attempted_start_stop"] = bool(start_stop["attempted"])
        if "started_by_probe" in start_stop:
            summary["started_by_probe"] = bool(start_stop["started_by_probe"])

    daemon = details.get("daemon")
    if isinstance(daemon, dict):
        if daemon.get("control_binary") is not None:
            summary["control_binary"] = daemon["control_binary"]
        if daemon.get("control_pipe_path") is not None:
            summary["control_pipe_path"] = daemon["control_pipe_path"]
        if "control_pipe_exists" in daemon:
            summary["control_pipe_exists"] = bool(daemon["control_pipe_exists"])

    return summary



def _docker_version(records: dict[str, dict[str, Any]]) -> str | None:
    extracted = _probe_extracted(records.get("docker.json", {}))
    docker_version = extracted.get("server_version") or extracted.get("client_version")
    if docker_version is None:
        return None
    return str(docker_version)



def _create_run_dir(config: ResolvedConfig) -> Path:
    return ensure_run_dir(
        output_root=config.output_dir.parent,
        run_id=config.output_dir.name,
        overwrite=False,
    ).resolve()



def _write_probe_artifact(run_dir: Path, artifact_name: str, record: dict[str, Any]) -> Path:
    path = _artifact_path(run_dir, artifact_name)
    write_json(path, record)
    return path



def _smoke_payload(config: ResolvedConfig) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": config.model,
        "temperature": config.workload.get("temperature", 0.0),
        "max_tokens": config.workload.get("max_tokens", 64),
    }
    if config.workload.get("messages") is not None:
        payload["messages"] = deepcopy(config.workload["messages"])
    else:
        payload["prompt"] = config.workload.get("prompt")
    return payload



def _write_smoke_placeholder_records(
    *,
    config: ResolvedConfig,
    run_dir: Path,
    status: ProbeStatus,
    reason: str,
    request_id: str,
    base_url: str | None,
) -> None:
    request_record = {
        "schema_version": SCHEMA_VERSION,
        "run_id": config.run_id,
        "request_id": request_id,
        "runtime": config.runtime,
        "base_url": base_url,
        "status": status.value,
        "component": "smoke_request",
        "timestamp_utc": utc_now_iso_z(),
        "monotonic_ns": monotonic_ns(),
        "payload": _smoke_payload(config),
        "details": {"reason": reason},
    }
    response_record = {
        "schema_version": SCHEMA_VERSION,
        "run_id": config.run_id,
        "request_id": request_id,
        "runtime": config.runtime,
        "base_url": base_url,
        "status": status.value,
        "component": "smoke_response",
        "timestamp_utc": utc_now_iso_z(),
        "monotonic_ns": monotonic_ns(),
        "response": None,
        "extracted": {"assistant_text": None},
        "details": {"reason": reason},
        "error_type": None,
        "error_message": None,
    }
    append_jsonl(_artifact_path(run_dir, "smoke_request.jsonl"), request_record)
    append_jsonl(_artifact_path(run_dir, "smoke_response.jsonl"), response_record)



def _make_skipped_probe(
    *,
    run_id: str,
    component: str,
    reason: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    merged_details = dict(details or {})
    merged_details.setdefault("reason", reason)
    return make_probe_result(
        run_id=run_id,
        component=component,
        status=ProbeStatus.SKIPPED,
        details=merged_details,
    )



def _latest_smoke_response_record(run_dir: Path) -> dict[str, Any] | None:
    path = _artifact_path(run_dir, "smoke_response.jsonl")
    if not path.exists():
        return None

    lines = path.read_text(encoding="utf-8").splitlines()
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            return None
        if isinstance(record, dict):
            return record
        return None
    return None



def _annotate_smoke_preemption_response_timing(
    *,
    run_dir: Path,
    smoke_preemption: dict[str, Any],
) -> dict[str, Any]:
    details = smoke_preemption.get("details")
    if not isinstance(details, dict):
        return smoke_preemption

    smoke_details = details.get("smoke")
    restore_details = details.get("restore")
    if not isinstance(smoke_details, dict) or not isinstance(restore_details, dict):
        return smoke_preemption

    response_record = _latest_smoke_response_record(run_dir)
    if response_record is None:
        return smoke_preemption

    response_status = response_record.get("status")
    response_monotonic_ns = response_record.get("monotonic_ns")
    restore_start_monotonic_ns = restore_details.get("start_monotonic_ns")
    if (
        response_status != ProbeStatus.OK.value
        or not isinstance(response_monotonic_ns, int)
        or not isinstance(restore_start_monotonic_ns, int)
    ):
        return smoke_preemption

    smoke_details["response_monotonic_ns"] = response_monotonic_ns
    smoke_details["response_completed_before_restore"] = (
        response_monotonic_ns < restore_start_monotonic_ns
    )
    return smoke_preemption



def _dry_run_probe_records(config: ResolvedConfig) -> dict[str, dict[str, Any]]:
    reason = "dry-run: external probes were not executed"
    runtime_reason = "dry-run: runtime start was not executed"
    smoke_reason = "dry-run: smoke request and preemption were not executed"
    return {
        "hardware.json": _make_skipped_probe(
            run_id=config.run_id,
            component="hardware",
            reason=reason,
        ),
        "docker.json": _make_skipped_probe(
            run_id=config.run_id,
            component="docker",
            reason=reason,
        ),
        "criu_check.json": _make_skipped_probe(
            run_id=config.run_id,
            component="criu_check",
            reason=reason,
        ),
        "docker_criu_integration.json": _make_skipped_probe(
            run_id=config.run_id,
            component="docker_criu_integration",
            reason=reason,
            details={"smoke": {"attempted": False}},
        ),
        "cuda_check.json": _make_skipped_probe(
            run_id=config.run_id,
            component="cuda_check",
            reason=reason,
        ),
        "mps_check.json": _make_skipped_probe(
            run_id=config.run_id,
            component="mps_check",
            reason=reason,
            details={"mode": "read_only"},
        ),
        "runtime_check.json": _make_skipped_probe(
            run_id=config.run_id,
            component="runtime_check",
            reason=runtime_reason,
            details={"runtime": config.runtime, "mode": "dry_run"},
        ),
        "smoke_preemption.json": _make_skipped_probe(
            run_id=config.run_id,
            component="smoke_preemption",
            reason=smoke_reason,
            details={
                "outcome": "not_attempted",
                "smoke": {"attempted": False},
                "checkpoint": {"attempted": False},
                "restore": {"attempted": False},
            },
        ),
        "smoke_validation.json": make_smoke_not_attempted_validation(
            run_id=config.run_id,
            request_id=f"{config.run_id}-dry-run-request",
            reason=smoke_reason,
            details={"runtime": config.runtime, "mode": "dry_run"},
        ),
    }



def _run_real_sequence(config: ResolvedConfig, run_dir: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any] | None]:
    probe_options = config.probe_options
    records: dict[str, dict[str, Any]] = {}
    runtime_adapter = None
    runtime_session: RuntimeSession | None = None
    cleanup_record: dict[str, Any] | None = None

    records["hardware.json"] = collect_hardware_probe(
        run_id=config.run_id,
        timeout_s=float(probe_options["hardware"]["timeout_s"]),
    )
    records["docker.json"] = collect_docker_probe(
        run_id=config.run_id,
        timeout_s=float(probe_options["docker"]["timeout_s"]),
    )
    records["criu_check.json"] = collect_criu_probe(
        run_id=config.run_id,
        timeout_s=float(probe_options["criu"]["timeout_s"]),
    )
    records["docker_criu_integration.json"] = collect_docker_criu_integration(
        run_id=config.run_id,
        criu_probe=records["criu_check.json"],
        timeout_s=float(probe_options["docker_criu_integration"]["timeout_s"]),
        checkpoint_name=str(probe_options["docker_criu_integration"]["checkpoint_name"]),
        smoke_image=str(probe_options["docker_criu_integration"]["smoke_image"]),
    )
    records["cuda_check.json"] = collect_cuda_container_probe(
        run_id=config.run_id,
        timeout_s=float(probe_options["cuda"]["timeout_s"]),
        image=str(probe_options["cuda"]["image"]),
    )
    records["mps_check.json"] = collect_mps_probe(
        run_id=config.run_id,
        timeout_s=float(probe_options["mps"]["timeout_s"]),
        allow_start_stop=bool(probe_options["mps"]["allow_start_stop"]),
        control_binary=str(probe_options["mps"]["control_binary"]),
        control_pipe_path=str(probe_options["mps"]["control_pipe_path"]),
    )

    try:
        if config.runtime != "vllm":
            raise ValueError(f"unsupported runtime: {config.runtime!r}")

        runtime_adapter = VLLMRuntimeAdapter(
            config=deepcopy(config.runtime_options["vllm"]),
            timeout_s=float(probe_options["runtime"]["timeout_s"]),
        )
        runtime_session = runtime_adapter.start(run_id=config.run_id)
        records["runtime_check.json"] = runtime_session.runtime_check

        request_id = str(config.workload.get("request_id") or f"{config.run_id}-smoke-request")
        smoke_request_executor: ThreadPoolExecutor | None = None
        smoke_request_future = None
        try:
            if runtime_session.status == ProbeStatus.OK and runtime_session.base_url and config.model:
                smoke_client = LLMSmokeClient(timeout_s=float(config.workload.get("timeout_s", 30.0)))
                smoke_request_kwargs = {
                    "run_id": config.run_id,
                    "output_dir": run_dir,
                    "base_url": runtime_session.base_url,
                    "model": config.model,
                    "prompt": config.workload.get("prompt"),
                    "messages": config.workload.get("messages"),
                    "request_id": request_id,
                    "runtime": config.runtime,
                    "temperature": float(config.workload.get("temperature", 0.0)),
                    "max_tokens": int(config.workload.get("max_tokens", 64)),
                }
                attempt_preemption_while_in_flight = (
                    _probe_status(records["docker_criu_integration.json"]) == ProbeStatus.OK.value
                    and runtime_session.container_name is not None
                    and runtime_session.container_id is not None
                )
                if attempt_preemption_while_in_flight:
                    smoke_request_executor = ThreadPoolExecutor(max_workers=1)
                    smoke_request_future = smoke_request_executor.submit(
                        smoke_client.send_smoke_request,
                        **smoke_request_kwargs,
                    )
                else:
                    smoke_client.send_smoke_request(**smoke_request_kwargs)
            else:
                reason = (
                    str(runtime_session.runtime_check.get("details", {}).get("reason"))
                    if runtime_session.runtime_check.get("details", {}).get("reason")
                    else "smoke request skipped because runtime is not runnable"
                )
                if runtime_session.status == ProbeStatus.OK and not config.model:
                    reason = "smoke request skipped because model is not configured"
                _write_smoke_placeholder_records(
                    config=config,
                    run_dir=run_dir,
                    status=runtime_session.status,
                    reason=reason,
                    request_id=request_id,
                    base_url=runtime_session.base_url,
                )

            records["smoke_preemption.json"] = collect_smoke_preemption(
                run_id=config.run_id,
                runtime_session=runtime_session,
                docker_criu_integration=records["docker_criu_integration.json"],
                timeout_s=float(probe_options["preemption"]["timeout_s"]),
                checkpoint_name=str(probe_options["preemption"]["checkpoint_name"]),
            )
            if smoke_request_future is not None:
                smoke_request_future.result()
        finally:
            if smoke_request_executor is not None:
                smoke_request_executor.shutdown(wait=True)
        records["smoke_preemption.json"] = _annotate_smoke_preemption_response_timing(
            run_dir=run_dir,
            smoke_preemption=records["smoke_preemption.json"],
        )
        records["smoke_validation.json"] = classify_smoke_validation(
            run_id=config.run_id,
            runtime_session=runtime_session,
            smoke_preemption=records["smoke_preemption.json"],
            request_id=request_id,
            response_replayed=bool(config.preemption_policy.get("response_replayed", False)),
        )
    finally:
        if runtime_adapter is not None and runtime_session is not None:
            cleanup_record = runtime_adapter.stop(runtime_session)

    return records, cleanup_record



def _build_run_metadata(
    *,
    config: ResolvedConfig,
    run_dir: Path,
    git: dict[str, Any],
    records: dict[str, dict[str, Any]],
    status: str,
    started_at_utc: str,
    started_monotonic_ns: int,
    cleanup_record: dict[str, Any] | None,
) -> dict[str, Any]:
    hardware_summary = _build_hardware_summary(records)
    docker_version = _docker_version(records)
    mps_summary = _build_mps_summary(records)

    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": config.run_id,
        "status": status,
        "experiment_id": config.experiment_id,
        "version": config.version,
        "runtime": config.runtime,
        "model": config.model,
        "arm": config.arm,
        "seed": config.seed,
        "dry_run": config.dry_run,
        "config_path": str(config.config_path),
        "output_dir": str(run_dir),
        "started_at_utc": started_at_utc,
        "started_monotonic_ns": started_monotonic_ns,
        "completed_at_utc": utc_now_iso_z(),
        "completed_monotonic_ns": monotonic_ns(),
        "gpu_names": deepcopy(hardware_summary.get("gpu_names")),
        "driver_version": hardware_summary.get("driver_version"),
        "cuda_version": hardware_summary.get("cuda_version"),
        "docker_version": docker_version,
        "mps_summary": mps_summary,
        "hardware_summary": hardware_summary,
        "probe_statuses": {
            path.rsplit(".", 1)[0]: _probe_status(record) for path, record in records.items()
        },
        "git": git,
        "cleanup": cleanup_record,
    }



def run_v0_orchestrator(
    config: ResolvedConfig,
    *,
    git_metadata_getter=get_git_metadata,
) -> OrchestratorResult:
    run_dir = _create_run_dir(config)
    dump_config_yaml(config, _artifact_path(run_dir, "config.yaml"))

    started_at_utc = utc_now_iso_z()
    started_monotonic_ns = monotonic_ns()
    git_metadata = git_metadata_getter(repo_root=Path.cwd())
    write_json(
        _artifact_path(run_dir, "run_metadata.json"),
        {
            "schema_version": SCHEMA_VERSION,
            "run_id": config.run_id,
            "status": "running",
            "experiment_id": config.experiment_id,
            "version": config.version,
            "runtime": config.runtime,
            "model": config.model,
            "arm": config.arm,
            "seed": config.seed,
            "dry_run": config.dry_run,
            "config_path": str(config.config_path),
            "output_dir": str(run_dir),
            "started_at_utc": started_at_utc,
            "started_monotonic_ns": started_monotonic_ns,
            "gpu_names": None,
            "driver_version": None,
            "cuda_version": None,
            "docker_version": None,
            "mps_summary": None,
            "hardware_summary": {},
            "git": git_metadata,
        },
    )

    if config.dry_run:
        request_id = f"{config.run_id}-dry-run-request"
        _write_smoke_placeholder_records(
            config=config,
            run_dir=run_dir,
            status=ProbeStatus.SKIPPED,
            reason="dry-run: smoke request and preemption were not executed",
            request_id=request_id,
            base_url=None,
        )
        records = _dry_run_probe_records(config)
        cleanup_record = None
    else:
        records, cleanup_record = _run_real_sequence(config, run_dir)

    artifact_paths = {
        name: _write_probe_artifact(run_dir, name, record)
        for name, record in records.items()
    }

    metadata = _build_run_metadata(
        config=config,
        run_dir=run_dir,
        git=git_metadata,
        records=records,
        status="completed",
        started_at_utc=started_at_utc,
        started_monotonic_ns=started_monotonic_ns,
        cleanup_record=cleanup_record,
    )
    metadata_path = _artifact_path(run_dir, "run_metadata.json")
    write_json(metadata_path, metadata)
    artifact_paths["run_metadata.json"] = metadata_path
    artifact_paths["config.yaml"] = _artifact_path(run_dir, "config.yaml")

    found_artifacts = {path.name for path in run_dir.iterdir() if path.is_file()}
    missing = REQUIRED_V0_ARTIFACTS - found_artifacts
    if missing:
        raise RuntimeError(f"missing required V0 artifacts: {sorted(missing)}")

    return OrchestratorResult(
        run_id=config.run_id,
        run_dir=run_dir,
        metadata=metadata,
        artifacts=artifact_paths,
    )
