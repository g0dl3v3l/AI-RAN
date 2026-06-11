from __future__ import annotations

import json
import re
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, request

from ai_runtime_experiments.artifacts import append_jsonl, write_json
from ai_runtime_experiments.config import ResolvedConfig, dump_config_yaml
from ai_runtime_experiments.debug_capture import (
    capture_criu_logs_for_record,
    collect_debug_bundle,
)
from ai_runtime_experiments.docker_criu.probe import (
    collect_criu_probe,
    collect_docker_criu_integration,
)
from ai_runtime_experiments.env_probe.cuda import collect_cuda_container_probe
from ai_runtime_experiments.env_probe.docker import collect_docker_probe
from ai_runtime_experiments.env_probe.hardware import collect_hardware_probe
from ai_runtime_experiments.env_probe.mps import collect_mps_probe
from ai_runtime_experiments.preemption import collect_smoke_preemption
from ai_runtime_experiments.runtime_adapters import (
    LlamaCppRuntimeAdapter,
    RuntimeSession,
    VLLMRuntimeAdapter,
)
from ai_runtime_experiments.schemas import (
    SCHEMA_VERSION,
    ProbeStatus,
    make_probe_result,
)
from ai_runtime_experiments.utils.command import CommandResult, run_command
from ai_runtime_experiments.utils.git_info import get_git_metadata
from ai_runtime_experiments.utils.paths import ensure_run_dir
from ai_runtime_experiments.utils.time import monotonic_ns, utc_now_iso_z
from ai_runtime_experiments.validation import (
    classify_smoke_validation,
    make_smoke_not_attempted_validation,
)
from ai_runtime_experiments.workload.llm_client import LLMSmokeClient

_CRIU_LOG_PATH_RE = re.compile(r"path=\s*(?P<path>/\S+\.log)")

_TRUSTED_CRIU_LOG_PREFIXES = (
    Path("/run/containerd"),
    Path("/var/lib/docker"),
)


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
    "post_restore_probe.json",
    "stage_events.jsonl",
    "run_metadata.json",
    "config.yaml",
}


@dataclass(frozen=True)
class OrchestratorResult:
    run_id: str
    run_dir: Path
    metadata: dict[str, Any]
    artifacts: dict[str, Path]


def _emit_stage_event(
    *,
    run_dir: Path,
    run_id: str,
    stage: str,
    status: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    event = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "component": "stage_event",
        "stage": stage,
        "status": status,
        "message": message,
        "details": details or {},
        "timestamp_utc": utc_now_iso_z(),
        "monotonic_ns": monotonic_ns(),
    }
    append_jsonl(_artifact_path(run_dir, "stage_events.jsonl"), event)
    suffix = f" details={event['details']}" if event["details"] else ""
    print(
        f"[{event['timestamp_utc']}] [{stage}] {status}: {message}{suffix}",
        flush=True,
    )


def _status_from_raw(value: Any) -> ProbeStatus:
    if isinstance(value, ProbeStatus):
        return value
    if isinstance(value, str):
        try:
            return ProbeStatus(value)
        except ValueError:
            return ProbeStatus.ERROR
    return ProbeStatus.ERROR


def _probe_post_restore_readiness(
    *,
    base_url: str,
    timeout_s: float,
    poll_interval_s: float,
) -> tuple[ProbeStatus, dict[str, Any]]:
    models_url = f"{base_url.rstrip('/')}/v1/models"
    request_timeout_s = max(0.5, min(2.0, timeout_s if timeout_s > 0 else 2.0))
    deadline = monotonic_ns() + int(max(timeout_s, 0.0) * 1_000_000_000)
    attempts = 0
    last_error: str | None = None

    while True:
        attempts += 1
        try:
            with request.urlopen(models_url, timeout=request_timeout_s) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if isinstance(payload, dict) and isinstance(payload.get("data"), list):
                return ProbeStatus.OK, {
                    "models_url": models_url,
                    "attempts": attempts,
                }
            last_error = "response missing models list"
        except (error.URLError, TimeoutError, OSError, ValueError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"

        if monotonic_ns() >= deadline:
            return ProbeStatus.TIMEOUT, {
                "models_url": models_url,
                "attempts": attempts,
                "reason": "timed out waiting for post-restore /v1/models readiness",
                "last_error": last_error,
            }

        if poll_interval_s > 0:
            time.sleep(poll_interval_s)


def _run_post_restore_probe(
    *,
    config: ResolvedConfig,
    run_dir: Path,
    runtime_session: RuntimeSession,
    smoke_preemption: dict[str, Any],
    base_request_id: str,
) -> dict[str, Any]:
    details: dict[str, Any] = {
        "runtime": config.runtime,
        "base_url": runtime_session.base_url,
        "preemption_outcome": (
            (smoke_preemption.get("details") or {}).get("outcome")
            if isinstance(smoke_preemption.get("details"), dict)
            else None
        ),
    }
    enabled = bool(config.workload.get("post_restore_probe_enabled", True))
    if not enabled:
        details["reason"] = "post-restore probe disabled by config"
        return make_probe_result(
            run_id=config.run_id,
            component="post_restore_probe",
            status=ProbeStatus.SKIPPED,
            details=details,
        )

    outcome = details.get("preemption_outcome")
    if outcome != "restored":
        details["reason"] = (
            f"post-restore probe skipped because preemption outcome is {outcome!r}"
        )
        return make_probe_result(
            run_id=config.run_id,
            component="post_restore_probe",
            status=ProbeStatus.SKIPPED,
            details=details,
        )

    if runtime_session.base_url is None:
        details["reason"] = (
            "post-restore probe skipped because runtime base_url is unavailable"
        )
        return make_probe_result(
            run_id=config.run_id,
            component="post_restore_probe",
            status=ProbeStatus.ERROR,
            details=details,
        )

    if not config.model:
        details["reason"] = "post-restore probe skipped because model is not configured"
        return make_probe_result(
            run_id=config.run_id,
            component="post_restore_probe",
            status=ProbeStatus.SKIPPED,
            details=details,
        )

    readiness_status, readiness_details = _probe_post_restore_readiness(
        base_url=runtime_session.base_url,
        timeout_s=float(config.workload.get("post_restore_readiness_timeout_s", 120.0)),
        poll_interval_s=float(
            config.workload.get("post_restore_readiness_poll_interval_s", 1.0)
        ),
    )
    details["readiness"] = readiness_details
    details["readiness_status"] = readiness_status.value
    if readiness_status != ProbeStatus.OK:
        details["reason"] = (
            readiness_details.get("reason") or "post-restore readiness probe failed"
        )
        return make_probe_result(
            run_id=config.run_id,
            component="post_restore_probe",
            status=readiness_status,
            details=details,
        )

    post_restore_request_id = f"{base_request_id}-post-restore"
    smoke_client = LLMSmokeClient(
        timeout_s=float(config.workload.get("timeout_s", 30.0))
    )
    response_record = smoke_client.send_smoke_request(
        run_id=config.run_id,
        output_dir=run_dir,
        base_url=runtime_session.base_url,
        model=config.model,
        prompt=config.workload.get("prompt"),
        messages=config.workload.get("messages"),
        request_id=post_restore_request_id,
        runtime=config.runtime,
        temperature=float(config.workload.get("temperature", 0.0)),
        max_tokens=int(config.workload.get("max_tokens", 64)),
    )
    response_status = _status_from_raw(response_record.get("status"))
    details["post_restore_request_id"] = post_restore_request_id
    details["post_restore_response_status"] = response_status.value
    details["post_restore_response_monotonic_ns"] = response_record.get("monotonic_ns")
    details["reason"] = (
        "post-restore smoke request completed"
        if response_status == ProbeStatus.OK
        else "post-restore smoke request failed"
    )
    return make_probe_result(
        run_id=config.run_id,
        component="post_restore_probe",
        status=response_status,
        details=details,
    )


def _probe_status(record: dict[str, Any]) -> str:
    return str(record.get("status") or ProbeStatus.ERROR.value)


def _artifact_path(run_dir: Path, artifact_name: str) -> Path:
    return run_dir / artifact_name


def _iter_command_dicts(value: Any):
    if isinstance(value, dict):
        if any(key in value for key in ("stderr", "stdout", "error_message")):
            yield value
        for nested in value.values():
            yield from _iter_command_dicts(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _iter_command_dicts(nested)


def _trusted_criu_log_path(path: Path) -> Path | None:
    try:
        resolved = path.resolve(strict=False)
    except OSError:
        return None
    if any(
        resolved == prefix or prefix in resolved.parents
        for prefix in _TRUSTED_CRIU_LOG_PREFIXES
    ):
        return resolved
    return None


def _extract_criu_log_paths(record: dict[str, Any]) -> list[Path]:
    paths: list[Path] = []
    seen: set[str] = set()
    for command in _iter_command_dicts(record):
        text = "\n".join(
            str(command.get(key) or "") for key in ("stderr", "stdout", "error_message")
        )
        for match in _CRIU_LOG_PATH_RE.finditer(text):
            raw_path = match.group("path")
            if raw_path not in seen:
                paths.append(Path(raw_path))
                seen.add(raw_path)
    return paths


def _command_result_details(result: CommandResult) -> dict[str, Any]:
    return {
        "argv": result.argv,
        "status": result.status.value,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "timed_out": result.timed_out,
        "duration_s": result.duration_s,
        "error_type": result.error_type,
        "error_message": result.error_message,
    }


def _copy_criu_log_with_sudo_cat(
    source_path: Path, destination: Path
) -> dict[str, Any]:
    trusted_source_path = _trusted_criu_log_path(source_path)
    if trusted_source_path is None:
        return {
            "status": ProbeStatus.ERROR.value,
            "fallback": "sudo-cat",
            "error_type": "UntrustedPath",
            "error_message": f"Refused sudo fallback for untrusted path: {source_path}",
        }
    result = run_command(
        ["sudo", "-n", "cat", str(trusted_source_path)],
        timeout_s=5.0,
    )
    details = _command_result_details(result)
    if result.status == ProbeStatus.OK and result.returncode == 0:
        destination.write_text(result.stdout, encoding="utf-8")
        destination.chmod(0o600)
        return {
            "status": ProbeStatus.OK.value,
            "fallback": "sudo-cat",
            "fallback_command": details,
        }
    return {
        "status": ProbeStatus.ERROR.value,
        "fallback": "sudo-cat",
        "error_type": result.error_type or "CommandFailed",
        "error_message": result.stderr or result.error_message or "sudo cat failed",
        "fallback_command": details,
    }


def _capture_criu_logs_for_record(
    *,
    run_dir: Path,
    artifact_name: str,
    record: dict[str, Any],
) -> None:
    capture_criu_logs_for_record(
        run_dir=run_dir,
        artifact_name=artifact_name,
        record=record,
        runner=run_command,
        copyfile=shutil.copyfile,
    )


def _capture_criu_logs(*, run_dir: Path, records: dict[str, dict[str, Any]]) -> None:
    for artifact_name in (
        "docker_criu_integration.json",
        "smoke_preemption.json",
        "smoke_validation.json",
    ):
        record = records.get(artifact_name)
        if record is not None:
            _capture_criu_logs_for_record(
                run_dir=run_dir, artifact_name=artifact_name, record=record
            )


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


def _write_probe_artifact(
    run_dir: Path, artifact_name: str, record: dict[str, Any]
) -> Path:
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


def _latest_jsonl_record(run_dir: Path, artifact_name: str) -> dict[str, Any] | None:
    path = _artifact_path(run_dir, artifact_name)
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


def _latest_smoke_request_record(run_dir: Path) -> dict[str, Any] | None:
    return _latest_jsonl_record(run_dir, "smoke_request.jsonl")


def _latest_smoke_response_record(run_dir: Path) -> dict[str, Any] | None:
    return _latest_jsonl_record(run_dir, "smoke_response.jsonl")


def _annotate_smoke_preemption_response_timing(
    *,
    run_dir: Path,
    smoke_preemption: dict[str, Any],
    smoke_request_record: dict[str, Any] | None = None,
    smoke_response_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    details = smoke_preemption.get("details")
    if not isinstance(details, dict):
        return smoke_preemption

    smoke_details = details.get("smoke")
    restore_details = details.get("restore")
    if not isinstance(smoke_details, dict) or not isinstance(restore_details, dict):
        return smoke_preemption

    request_record = smoke_request_record or _latest_smoke_request_record(run_dir)
    if request_record is not None:
        request_status = request_record.get("status")
        request_monotonic_ns = request_record.get("monotonic_ns")
        smoke_details["request_status"] = request_status
        if isinstance(request_monotonic_ns, int):
            smoke_details["request_monotonic_ns"] = request_monotonic_ns
            checkpoint_details = details.get("checkpoint")
            checkpoint_start_monotonic_ns = None
            if isinstance(checkpoint_details, dict):
                checkpoint_start_monotonic_ns = checkpoint_details.get(
                    "start_monotonic_ns"
                )
            restore_start_monotonic_ns = restore_details.get("start_monotonic_ns")
            if isinstance(checkpoint_start_monotonic_ns, int):
                smoke_details["request_started_before_checkpoint"] = (
                    request_monotonic_ns <= checkpoint_start_monotonic_ns
                )
            elif isinstance(restore_start_monotonic_ns, int):
                smoke_details["request_started_before_checkpoint"] = (
                    request_monotonic_ns <= restore_start_monotonic_ns
                )

    response_record = smoke_response_record or _latest_smoke_response_record(run_dir)
    if response_record is None:
        return smoke_preemption

    response_status = response_record.get("status")
    response_monotonic_ns = response_record.get("monotonic_ns")
    smoke_details["response_status"] = response_status
    if not isinstance(response_monotonic_ns, int):
        return smoke_preemption

    smoke_details["response_monotonic_ns"] = response_monotonic_ns
    if response_status != ProbeStatus.OK.value:
        return smoke_preemption

    restore_start_monotonic_ns = restore_details.get("start_monotonic_ns")
    if isinstance(restore_start_monotonic_ns, int):
        smoke_details["response_completed_before_restore"] = (
            response_monotonic_ns < restore_start_monotonic_ns
        )

    restore_end_monotonic_ns = restore_details.get("end_monotonic_ns")
    if isinstance(restore_end_monotonic_ns, int):
        smoke_details["response_completed_after_restore"] = (
            response_monotonic_ns >= restore_end_monotonic_ns
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
        "post_restore_probe.json": _make_skipped_probe(
            run_id=config.run_id,
            component="post_restore_probe",
            reason=smoke_reason,
            details={"runtime": config.runtime, "mode": "dry_run"},
        ),
    }


def _run_real_sequence(
    config: ResolvedConfig, run_dir: Path
) -> tuple[dict[str, dict[str, Any]], dict[str, Any] | None]:
    probe_options = config.probe_options
    records: dict[str, dict[str, Any]] = {}
    runtime_adapter = None
    runtime_session: RuntimeSession | None = None
    cleanup_record: dict[str, Any] | None = None

    _emit_stage_event(
        run_dir=run_dir,
        run_id=config.run_id,
        stage="probe_sequence",
        status="start",
        message="running environment and runtime probes",
    )

    _emit_stage_event(
        run_dir=run_dir,
        run_id=config.run_id,
        stage="hardware_probe",
        status="start",
        message="collecting hardware probe",
    )
    records["hardware.json"] = collect_hardware_probe(
        run_id=config.run_id,
        timeout_s=float(probe_options["hardware"]["timeout_s"]),
    )
    _emit_stage_event(
        run_dir=run_dir,
        run_id=config.run_id,
        stage="hardware_probe",
        status="done",
        message="hardware probe completed",
        details={"probe_status": _probe_status(records["hardware.json"])},
    )

    _emit_stage_event(
        run_dir=run_dir,
        run_id=config.run_id,
        stage="docker_probe",
        status="start",
        message="collecting docker probe",
    )
    records["docker.json"] = collect_docker_probe(
        run_id=config.run_id,
        timeout_s=float(probe_options["docker"]["timeout_s"]),
    )
    _emit_stage_event(
        run_dir=run_dir,
        run_id=config.run_id,
        stage="docker_probe",
        status="done",
        message="docker probe completed",
        details={"probe_status": _probe_status(records["docker.json"])},
    )

    _emit_stage_event(
        run_dir=run_dir,
        run_id=config.run_id,
        stage="criu_probe",
        status="start",
        message="collecting criu probe",
    )
    records["criu_check.json"] = collect_criu_probe(
        run_id=config.run_id,
        timeout_s=float(probe_options["criu"]["timeout_s"]),
    )
    _emit_stage_event(
        run_dir=run_dir,
        run_id=config.run_id,
        stage="criu_probe",
        status="done",
        message="criu probe completed",
        details={"probe_status": _probe_status(records["criu_check.json"])},
    )

    _emit_stage_event(
        run_dir=run_dir,
        run_id=config.run_id,
        stage="docker_criu_integration",
        status="start",
        message="running docker CRIU integration probe",
    )
    records["docker_criu_integration.json"] = collect_docker_criu_integration(
        run_id=config.run_id,
        criu_probe=records["criu_check.json"],
        timeout_s=float(probe_options["docker_criu_integration"]["timeout_s"]),
        checkpoint_name=str(
            probe_options["docker_criu_integration"]["checkpoint_name"]
        ),
        checkpoint_dir=(
            str(probe_options["docker_criu_integration"].get("checkpoint_dir"))
            if probe_options["docker_criu_integration"].get("checkpoint_dir")
            else None
        ),
        smoke_image=str(probe_options["docker_criu_integration"]["smoke_image"]),
        smoke_runtime=probe_options["docker_criu_integration"].get("smoke_runtime")
        or "runc",
        smoke_network_mode=probe_options["docker_criu_integration"].get("network_mode")
        or "host",
        post_checkpoint_delay_s=float(
            probe_options["docker_criu_integration"].get("post_checkpoint_delay_s", 5.0)
        ),
        debug_capture_hook=lambda record: capture_criu_logs_for_record(
            run_dir=run_dir,
            artifact_name="docker_criu_integration.json",
            record=record,
        ),
    )
    _emit_stage_event(
        run_dir=run_dir,
        run_id=config.run_id,
        stage="docker_criu_integration",
        status="done",
        message="docker CRIU integration probe completed",
        details={
            "probe_status": _probe_status(records["docker_criu_integration.json"])
        },
    )

    _emit_stage_event(
        run_dir=run_dir,
        run_id=config.run_id,
        stage="cuda_probe",
        status="start",
        message="collecting cuda probe",
    )
    records["cuda_check.json"] = collect_cuda_container_probe(
        run_id=config.run_id,
        timeout_s=float(probe_options["cuda"]["timeout_s"]),
        image=str(probe_options["cuda"]["image"]),
    )
    _emit_stage_event(
        run_dir=run_dir,
        run_id=config.run_id,
        stage="cuda_probe",
        status="done",
        message="cuda probe completed",
        details={"probe_status": _probe_status(records["cuda_check.json"])},
    )

    _emit_stage_event(
        run_dir=run_dir,
        run_id=config.run_id,
        stage="mps_probe",
        status="start",
        message="collecting mps probe",
    )
    records["mps_check.json"] = collect_mps_probe(
        run_id=config.run_id,
        timeout_s=float(probe_options["mps"]["timeout_s"]),
        allow_start_stop=bool(probe_options["mps"]["allow_start_stop"]),
        control_binary=str(probe_options["mps"]["control_binary"]),
        control_pipe_path=str(probe_options["mps"]["control_pipe_path"]),
    )
    _emit_stage_event(
        run_dir=run_dir,
        run_id=config.run_id,
        stage="mps_probe",
        status="done",
        message="mps probe completed",
        details={"probe_status": _probe_status(records["mps_check.json"])},
    )

    try:
        _emit_stage_event(
            run_dir=run_dir,
            run_id=config.run_id,
            stage="runtime_start",
            status="start",
            message="starting runtime adapter",
        )
        if config.runtime == "vllm":
            runtime_adapter = VLLMRuntimeAdapter(
                config=deepcopy(config.runtime_options["vllm"]),
                timeout_s=float(probe_options["runtime"]["timeout_s"]),
            )
        elif config.runtime == "llama_cpp":
            runtime_adapter = LlamaCppRuntimeAdapter(
                config=deepcopy(config.runtime_options["llama_cpp"]),
                timeout_s=float(probe_options["runtime"]["timeout_s"]),
            )
        else:
            raise ValueError(f"unsupported runtime: {config.runtime!r}")
        runtime_session = runtime_adapter.start(run_id=config.run_id)
        records["runtime_check.json"] = runtime_session.runtime_check
        _emit_stage_event(
            run_dir=run_dir,
            run_id=config.run_id,
            stage="runtime_start",
            status="done",
            message="runtime adapter start completed",
            details={
                "probe_status": _probe_status(records["runtime_check.json"]),
                "runtime_mode": runtime_session.mode,
                "base_url": runtime_session.base_url,
            },
        )

        request_id = str(
            config.workload.get("request_id") or f"{config.run_id}-smoke-request"
        )
        smoke_request_executor: ThreadPoolExecutor | None = None
        smoke_request_future = None
        try:
            if (
                runtime_session.status == ProbeStatus.OK
                and runtime_session.base_url
                and config.model
            ):
                _emit_stage_event(
                    run_dir=run_dir,
                    run_id=config.run_id,
                    stage="smoke_request",
                    status="start",
                    message="issuing initial smoke request",
                    details={"request_id": request_id},
                )
                smoke_client = LLMSmokeClient(
                    timeout_s=float(config.workload.get("timeout_s", 30.0))
                )
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
                    _probe_status(records["docker_criu_integration.json"])
                    == ProbeStatus.OK.value
                    and runtime_session.container_name is not None
                    and runtime_session.container_id is not None
                )
                if attempt_preemption_while_in_flight:
                    smoke_request_executor = ThreadPoolExecutor(max_workers=1)
                    smoke_request_future = smoke_request_executor.submit(
                        smoke_client.send_smoke_request,
                        **smoke_request_kwargs,
                    )
                    _emit_stage_event(
                        run_dir=run_dir,
                        run_id=config.run_id,
                        stage="smoke_request",
                        status="in_progress",
                        message="smoke request running concurrently with preemption",
                        details={"request_id": request_id},
                    )
                else:
                    smoke_client.send_smoke_request(**smoke_request_kwargs)
                    _emit_stage_event(
                        run_dir=run_dir,
                        run_id=config.run_id,
                        stage="smoke_request",
                        status="done",
                        message="initial smoke request completed",
                        details={"request_id": request_id},
                    )
            else:
                reason = (
                    str(runtime_session.runtime_check.get("details", {}).get("reason"))
                    if runtime_session.runtime_check.get("details", {}).get("reason")
                    else "smoke request skipped because runtime is not runnable"
                )
                placeholder_status = runtime_session.status
                if runtime_session.status == ProbeStatus.OK and not config.model:
                    reason = "smoke request skipped because model is not configured"
                    placeholder_status = ProbeStatus.SKIPPED
                _write_smoke_placeholder_records(
                    config=config,
                    run_dir=run_dir,
                    status=placeholder_status,
                    reason=reason,
                    request_id=request_id,
                    base_url=runtime_session.base_url,
                )
                _emit_stage_event(
                    run_dir=run_dir,
                    run_id=config.run_id,
                    stage="smoke_request",
                    status="skipped",
                    message=reason,
                    details={"request_id": request_id},
                )

            _emit_stage_event(
                run_dir=run_dir,
                run_id=config.run_id,
                stage="smoke_preemption",
                status="start",
                message="running checkpoint/restore preemption probe",
            )
            records["smoke_preemption.json"] = collect_smoke_preemption(
                run_id=config.run_id,
                runtime_session=runtime_session,
                docker_criu_integration=records["docker_criu_integration.json"],
                timeout_s=float(probe_options["preemption"]["timeout_s"]),
                checkpoint_name=str(probe_options["preemption"]["checkpoint_name"]),
                checkpoint_dir=(
                    str(probe_options["preemption"].get("checkpoint_dir"))
                    if probe_options["preemption"].get("checkpoint_dir")
                    else None
                ),
                capture_memory_telemetry=bool(
                    probe_options["preemption"].get("capture_memory_telemetry", False)
                ),
                post_checkpoint_delay_s=float(
                    probe_options["docker_criu_integration"].get(
                        "post_checkpoint_delay_s", 5.0
                    )
                ),
                criu_config_mode=probe_options["preemption"].get("criu_config_mode"),
                criu_config_allow_sudo=bool(
                    probe_options["preemption"].get("criu_config_allow_sudo", False)
                ),
            )
            _capture_criu_logs_for_record(
                run_dir=run_dir,
                artifact_name="smoke_preemption.json",
                record=records["smoke_preemption.json"],
            )
            _emit_stage_event(
                run_dir=run_dir,
                run_id=config.run_id,
                stage="smoke_preemption",
                status="done",
                message="checkpoint/restore preemption probe completed",
                details={
                    "probe_status": _probe_status(records["smoke_preemption.json"]),
                    "outcome": (
                        (records["smoke_preemption.json"].get("details") or {}).get(
                            "outcome"
                        )
                        if isinstance(
                            records["smoke_preemption.json"].get("details"), dict
                        )
                        else None
                    ),
                },
            )
            if smoke_request_future is not None:
                smoke_request_future.result()
                _emit_stage_event(
                    run_dir=run_dir,
                    run_id=config.run_id,
                    stage="smoke_request",
                    status="done",
                    message="initial in-flight smoke request completed",
                    details={"request_id": request_id},
                )
        finally:
            if smoke_request_executor is not None:
                smoke_request_executor.shutdown(wait=True)

        initial_smoke_request_record = _latest_smoke_request_record(run_dir)
        initial_smoke_response_record = _latest_smoke_response_record(run_dir)

        _emit_stage_event(
            run_dir=run_dir,
            run_id=config.run_id,
            stage="post_restore_probe",
            status="start",
            message="running explicit post-restore readiness+smoke proof",
        )
        records["post_restore_probe.json"] = _run_post_restore_probe(
            config=config,
            run_dir=run_dir,
            runtime_session=runtime_session,
            smoke_preemption=records["smoke_preemption.json"],
            base_request_id=request_id,
        )
        _emit_stage_event(
            run_dir=run_dir,
            run_id=config.run_id,
            stage="post_restore_probe",
            status="done",
            message="post-restore probe completed",
            details={
                "probe_status": _probe_status(records["post_restore_probe.json"]),
                "reason": (
                    (records["post_restore_probe.json"].get("details") or {}).get(
                        "reason"
                    )
                    if isinstance(
                        records["post_restore_probe.json"].get("details"), dict
                    )
                    else None
                ),
            },
        )

        records["smoke_preemption.json"] = _annotate_smoke_preemption_response_timing(
            run_dir=run_dir,
            smoke_preemption=records["smoke_preemption.json"],
            smoke_request_record=initial_smoke_request_record,
            smoke_response_record=initial_smoke_response_record,
        )
        _emit_stage_event(
            run_dir=run_dir,
            run_id=config.run_id,
            stage="smoke_validation",
            status="start",
            message="classifying smoke validation",
        )
        records["smoke_validation.json"] = classify_smoke_validation(
            run_id=config.run_id,
            runtime_session=runtime_session,
            smoke_preemption=records["smoke_preemption.json"],
            request_id=request_id,
            smoke_response=initial_smoke_response_record,
            smoke_request=initial_smoke_request_record,
        )
        _capture_criu_logs_for_record(
            run_dir=run_dir,
            artifact_name="smoke_validation.json",
            record=records["smoke_validation.json"],
        )
        _emit_stage_event(
            run_dir=run_dir,
            run_id=config.run_id,
            stage="smoke_validation",
            status="done",
            message="smoke validation completed",
            details={
                "probe_status": _probe_status(records["smoke_validation.json"]),
                "classification": records["smoke_validation.json"].get(
                    "classification"
                ),
                "reason": (
                    (records["smoke_validation.json"].get("details") or {}).get(
                        "reason"
                    )
                    if isinstance(records["smoke_validation.json"].get("details"), dict)
                    else None
                ),
            },
        )
    finally:
        if runtime_adapter is not None and runtime_session is not None:
            _emit_stage_event(
                run_dir=run_dir,
                run_id=config.run_id,
                stage="runtime_teardown",
                status="start",
                message="stopping runtime adapter",
            )
            cleanup_record = runtime_adapter.stop(runtime_session)
            _emit_stage_event(
                run_dir=run_dir,
                run_id=config.run_id,
                stage="runtime_teardown",
                status="done",
                message="runtime adapter stopped",
                details={
                    "cleanup_status": cleanup_record.get("status")
                    if isinstance(cleanup_record, dict)
                    else None
                },
            )

    _emit_stage_event(
        run_dir=run_dir,
        run_id=config.run_id,
        stage="probe_sequence",
        status="done",
        message="real probe sequence completed",
    )

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
    debug_bundle: dict[str, Any],
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
            path.rsplit(".", 1)[0]: _probe_status(record)
            for path, record in records.items()
        },
        "debug_bundle": {
            "status": debug_bundle.get("status"),
            "artifact_path": str(run_dir / "debug" / "debug_bundle.json"),
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
    _emit_stage_event(
        run_dir=run_dir,
        run_id=config.run_id,
        stage="orchestrator",
        status="start",
        message="starting V0 orchestration",
        details={"config_path": str(config.config_path), "output_dir": str(run_dir)},
    )
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
        _emit_stage_event(
            run_dir=run_dir,
            run_id=config.run_id,
            stage="dry_run",
            status="start",
            message="generating deterministic dry-run artifacts",
        )
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
        _emit_stage_event(
            run_dir=run_dir,
            run_id=config.run_id,
            stage="dry_run",
            status="done",
            message="dry-run artifacts generated",
        )
    else:
        records, cleanup_record = _run_real_sequence(config, run_dir)

    _emit_stage_event(
        run_dir=run_dir,
        run_id=config.run_id,
        stage="criu_log_capture",
        status="start",
        message="capturing CRIU logs from probe artifacts",
    )
    _capture_criu_logs(run_dir=run_dir, records=records)
    _emit_stage_event(
        run_dir=run_dir,
        run_id=config.run_id,
        stage="criu_log_capture",
        status="done",
        message="CRIU log capture finished",
    )

    _emit_stage_event(
        run_dir=run_dir,
        run_id=config.run_id,
        stage="debug_bundle",
        status="start",
        message="collecting debug bundle",
    )
    try:
        debug_bundle = collect_debug_bundle(run_dir=run_dir)
    except Exception as exc:
        debug_bundle = {
            "status": ProbeStatus.ERROR.value,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "commands": {},
        }
    debug_bundle_path = run_dir / "debug" / "debug_bundle.json"
    write_json(debug_bundle_path, debug_bundle)
    debug_bundle_path.chmod(0o600)
    _emit_stage_event(
        run_dir=run_dir,
        run_id=config.run_id,
        stage="debug_bundle",
        status="done",
        message="debug bundle collected",
        details={"debug_bundle_status": debug_bundle.get("status")},
    )

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
        debug_bundle=debug_bundle,
    )
    metadata_path = _artifact_path(run_dir, "run_metadata.json")
    write_json(metadata_path, metadata)
    artifact_paths["run_metadata.json"] = metadata_path
    artifact_paths["config.yaml"] = _artifact_path(run_dir, "config.yaml")
    artifact_paths["debug_bundle.json"] = debug_bundle_path

    found_artifacts = {path.name for path in run_dir.iterdir() if path.is_file()}
    missing = REQUIRED_V0_ARTIFACTS - found_artifacts
    if missing:
        raise RuntimeError(f"missing required V0 artifacts: {sorted(missing)}")

    _emit_stage_event(
        run_dir=run_dir,
        run_id=config.run_id,
        stage="orchestrator",
        status="done",
        message="V0 orchestration completed",
    )

    return OrchestratorResult(
        run_id=config.run_id,
        run_dir=run_dir,
        metadata=metadata,
        artifacts=artifact_paths,
    )
