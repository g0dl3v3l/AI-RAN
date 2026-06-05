from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from ai_runtime_experiments.docker_criu.probe import (
    DEFAULT_CHECKPOINT_NAME,
    _classify_result,
    _command_details,
    _status_from_probe,
)
from ai_runtime_experiments.runtime_adapters import RuntimeSession
from ai_runtime_experiments.schemas import ProbeStatus, make_probe_result
from ai_runtime_experiments.utils.command import CommandResult, run_command
from ai_runtime_experiments.utils.time import monotonic_ns, utc_now_iso_z

CommandRunner = Callable[..., CommandResult]
DEFAULT_TIMEOUT_S = 10.0



def _base_details(
    *,
    runtime_session: RuntimeSession,
    checkpoint_name: str,
    docker_criu_integration: Mapping[str, Any] | None,
) -> dict[str, Any]:
    details: dict[str, Any] = {
        "runtime": runtime_session.runtime,
        "mode": runtime_session.mode,
        "commands": {},
        "smoke": {"attempted": False},
        "checkpoint": {"attempted": False},
        "restore": {"attempted": False},
        "container": {
            "name": runtime_session.container_name,
            "id": runtime_session.container_id,
            "checkpoint_name": checkpoint_name,
        },
        "prerequisites": {
            "runtime_status": runtime_session.status.value,
            "docker_criu_integration_status": None,
        },
    }
    prerequisite_status = _status_from_probe(docker_criu_integration)
    if prerequisite_status is not None:
        details["prerequisites"]["docker_criu_integration_status"] = prerequisite_status.value
    if docker_criu_integration is not None:
        prerequisite_details = docker_criu_integration.get("details")
        if isinstance(prerequisite_details, Mapping) and prerequisite_details.get("reason"):
            details["prerequisites"]["docker_criu_integration_reason"] = prerequisite_details["reason"]
    return details



def _mark_phase_start(phase: dict[str, Any]) -> None:
    phase["attempted"] = True
    phase["start_timestamp_utc"] = utc_now_iso_z()
    phase["start_monotonic_ns"] = monotonic_ns()



def _mark_phase_end(
    phase: dict[str, Any],
    *,
    status: ProbeStatus,
    reason: str | None = None,
    command: str | None = None,
) -> None:
    phase["end_timestamp_utc"] = utc_now_iso_z()
    phase["end_monotonic_ns"] = monotonic_ns()
    phase["status"] = status.value
    if reason is not None:
        phase["reason"] = reason
    if command is not None:
        phase["command"] = command



def _finalize_smoke_preemption(
    *,
    run_id: str,
    status: ProbeStatus,
    details: dict[str, Any],
) -> dict[str, Any]:
    return make_probe_result(
        run_id=run_id,
        component="smoke_preemption",
        status=status,
        details=details,
    )



def collect_smoke_preemption(
    *,
    run_id: str,
    runtime_session: RuntimeSession,
    docker_criu_integration: Mapping[str, Any] | None,
    runner: CommandRunner = run_command,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    checkpoint_name: str = DEFAULT_CHECKPOINT_NAME,
) -> dict[str, Any]:
    details = _base_details(
        runtime_session=runtime_session,
        checkpoint_name=checkpoint_name,
        docker_criu_integration=docker_criu_integration,
    )

    prerequisite_status = _status_from_probe(docker_criu_integration)
    if prerequisite_status is None:
        details["reason"] = "docker_criu_integration prerequisite record is missing"
        details["outcome"] = "not_attempted"
        return _finalize_smoke_preemption(
            run_id=run_id,
            status=ProbeStatus.SKIPPED,
            details=details,
        )

    if prerequisite_status == ProbeStatus.UNSUPPORTED:
        prerequisite_details = docker_criu_integration.get("details") if docker_criu_integration else None
        prerequisite_reason = None
        if isinstance(prerequisite_details, Mapping):
            raw_reason = prerequisite_details.get("reason")
            if isinstance(raw_reason, str) and raw_reason.strip():
                prerequisite_reason = raw_reason.strip()
        details["reason"] = (
            prerequisite_reason
            or "docker_criu_integration prerequisite is unsupported"
        )
        details["outcome"] = "not_supported"
        return _finalize_smoke_preemption(
            run_id=run_id,
            status=ProbeStatus.UNSUPPORTED,
            details=details,
        )

    if prerequisite_status != ProbeStatus.OK:
        details["reason"] = (
            "docker_criu_integration prerequisite is not ready: "
            f"{prerequisite_status.value}"
        )
        details["outcome"] = "not_attempted"
        return _finalize_smoke_preemption(
            run_id=run_id,
            status=ProbeStatus.SKIPPED,
            details=details,
        )

    if runtime_session.status != ProbeStatus.OK:
        details["reason"] = (
            f"runtime session is not preemptible: {runtime_session.status.value}"
        )
        details["outcome"] = "not_attempted"
        return _finalize_smoke_preemption(
            run_id=run_id,
            status=ProbeStatus.SKIPPED,
            details=details,
        )

    if not runtime_session.container_name or not runtime_session.container_id:
        details["reason"] = "runtime session has no experiment-owned container"
        details["outcome"] = "not_attempted"
        return _finalize_smoke_preemption(
            run_id=run_id,
            status=ProbeStatus.SKIPPED,
            details=details,
        )

    container_name = runtime_session.container_name
    details["smoke"]["attempted"] = True

    checkpoint_phase = details["checkpoint"]
    _mark_phase_start(checkpoint_phase)
    checkpoint_result = runner(
        ["docker", "checkpoint", "create", container_name, checkpoint_name],
        timeout_s=timeout_s,
    )
    details["commands"]["docker_checkpoint_create"] = _command_details(checkpoint_result)
    checkpoint_status, checkpoint_reason = _classify_result(
        checkpoint_result,
        command_label="docker checkpoint create",
        capability_sensitive=True,
    )
    _mark_phase_end(
        checkpoint_phase,
        status=checkpoint_status,
        reason=checkpoint_reason,
        command="docker_checkpoint_create",
    )
    if checkpoint_status != ProbeStatus.OK:
        details["reason"] = checkpoint_reason or "smoke checkpoint failed"
        if checkpoint_status == ProbeStatus.UNSUPPORTED:
            details["outcome"] = "not_supported"
        elif checkpoint_status == ProbeStatus.TIMEOUT:
            details["outcome"] = "hung"
        else:
            details["outcome"] = "checkpoint_failed"
        return _finalize_smoke_preemption(
            run_id=run_id,
            status=checkpoint_status,
            details=details,
        )

    restore_phase = details["restore"]
    _mark_phase_start(restore_phase)

    stop_result = runner(["docker", "stop", container_name], timeout_s=timeout_s)
    details["commands"]["docker_stop"] = _command_details(stop_result)
    stop_status, stop_reason = _classify_result(
        stop_result,
        command_label="docker stop",
    )
    if stop_status != ProbeStatus.OK:
        _mark_phase_end(
            restore_phase,
            status=stop_status,
            reason=stop_reason,
            command="docker_stop",
        )
        details["reason"] = stop_reason or "smoke restore stop failed"
        if stop_status == ProbeStatus.UNSUPPORTED:
            details["outcome"] = "not_supported"
        elif stop_status == ProbeStatus.TIMEOUT:
            details["outcome"] = "hung"
        else:
            details["outcome"] = "restore_failed"
        return _finalize_smoke_preemption(
            run_id=run_id,
            status=stop_status,
            details=details,
        )

    start_result = runner(
        ["docker", "start", "--checkpoint", checkpoint_name, container_name],
        timeout_s=timeout_s,
    )
    details["commands"]["docker_start_checkpoint"] = _command_details(start_result)
    start_status, start_reason = _classify_result(
        start_result,
        command_label="docker start --checkpoint",
        capability_sensitive=True,
    )
    if start_status != ProbeStatus.OK:
        _mark_phase_end(
            restore_phase,
            status=start_status,
            reason=start_reason,
            command="docker_start_checkpoint",
        )
        details["reason"] = start_reason or "smoke restore start failed"
        if start_status == ProbeStatus.UNSUPPORTED:
            details["outcome"] = "not_supported"
        elif start_status == ProbeStatus.TIMEOUT:
            details["outcome"] = "hung"
        else:
            details["outcome"] = "restore_failed"
        return _finalize_smoke_preemption(
            run_id=run_id,
            status=start_status,
            details=details,
        )

    state_result = runner(
        ["docker", "inspect", "--format", "{{.State.Status}}", container_name],
        timeout_s=timeout_s,
    )
    details["commands"]["docker_inspect_state"] = _command_details(state_result)
    state_status, state_reason = _classify_result(
        state_result,
        command_label="docker inspect state",
    )
    if state_status != ProbeStatus.OK:
        _mark_phase_end(
            restore_phase,
            status=state_status,
            reason=state_reason,
            command="docker_inspect_state",
        )
        details["reason"] = state_reason or "unable to inspect restored runtime state"
        if state_status == ProbeStatus.TIMEOUT:
            details["outcome"] = "hung"
        else:
            details["outcome"] = "restore_failed"
        return _finalize_smoke_preemption(
            run_id=run_id,
            status=state_status,
            details=details,
        )

    container_state = state_result.stdout.strip() or "unknown"
    details.setdefault("extracted", {})["container_state"] = container_state
    if container_state != "running":
        reason = f"runtime container not running after restore: {container_state}"
        _mark_phase_end(
            restore_phase,
            status=ProbeStatus.ERROR,
            reason=reason,
            command="docker_inspect_state",
        )
        details["reason"] = reason
        details["outcome"] = "runtime_failed"
        return _finalize_smoke_preemption(
            run_id=run_id,
            status=ProbeStatus.ERROR,
            details=details,
        )

    _mark_phase_end(
        restore_phase,
        status=ProbeStatus.OK,
        command="docker_inspect_state",
    )
    details["reason"] = "checkpoint and restore completed"
    details["outcome"] = "restored"
    return _finalize_smoke_preemption(
        run_id=run_id,
        status=ProbeStatus.OK,
        details=details,
    )
