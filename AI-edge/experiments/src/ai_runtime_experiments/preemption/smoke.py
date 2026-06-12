from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Mapping
from typing import Any

from ai_runtime_experiments.criu_config import (
    CriuRuncConfigPhaseSwitcher,
    build_runc_conf_text,
)
from ai_runtime_experiments.docker_criu.probe import (
    DEFAULT_CHECKPOINT_NAME,
    DEFAULT_POST_CHECKPOINT_DELAY_S,
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
_ALLOWED_RUNTIME_COMPONENTS = {"vllm-runtime", "llama-cpp-runtime"}
_CUSTOM_CHECKPOINTDIR_UNSUPPORTED_MARKERS = (
    "custom checkpointdir is not supported",
    "custom checkpoint dir is not supported",
)


def _parse_label_mapping(text: str) -> dict[str, str] | None:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(value, dict):
        return None
    return {
        key: item
        for key, item in value.items()
        if isinstance(key, str) and isinstance(item, str)
    }


def _ensure_experiment_owned_runtime_container(
    *,
    container_name: str,
    labels: Mapping[str, str],
) -> None:
    if not container_name.startswith("ai-edge-v0-"):
        raise ValueError(
            "refusing destructive Docker action because container is not experiment-owned: "
            f"{container_name}"
        )
    if labels.get("ai-edge-experiment") != "v0":
        raise ValueError(
            "refusing destructive Docker action because container is not experiment-owned: "
            f"{container_name}"
        )
    if labels.get("ai-edge-component") not in _ALLOWED_RUNTIME_COMPONENTS:
        raise ValueError(
            "refusing destructive Docker action because container is not experiment-owned: "
            f"{container_name}"
        )
    run_id = labels.get("ai-edge-run-id")
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError(
            "refusing destructive Docker action because container is not experiment-owned: "
            f"{container_name}"
        )


def _base_details(
    *,
    runtime_session: RuntimeSession,
    checkpoint_name: str,
    checkpoint_dir: str | None,
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
            "checkpoint_dir": checkpoint_dir,
        },
        "prerequisites": {
            "runtime_status": runtime_session.status.value,
            "docker_criu_integration_status": None,
        },
    }
    prerequisite_status = _status_from_probe(docker_criu_integration)
    if prerequisite_status is not None:
        details["prerequisites"]["docker_criu_integration_status"] = (
            prerequisite_status.value
        )
    if docker_criu_integration is not None:
        prerequisite_details = docker_criu_integration.get("details")
        if isinstance(prerequisite_details, Mapping) and prerequisite_details.get(
            "reason"
        ):
            details["prerequisites"]["docker_criu_integration_reason"] = (
                prerequisite_details["reason"]
            )
    return details


def _mark_phase_start(phase: dict[str, Any], *, phase_name: str) -> None:
    phase["attempted"] = True
    phase["start_timestamp_utc"] = utc_now_iso_z()
    phase["start_monotonic_ns"] = monotonic_ns()
    print(
        f"[{phase['start_timestamp_utc']}] [preemption.{phase_name}] start",
        flush=True,
    )


def _mark_phase_end(
    phase: dict[str, Any],
    *,
    phase_name: str,
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
    print(
        f"[{phase['end_timestamp_utc']}] [preemption.{phase_name}] end status={status.value}"
        + (f" reason={reason}" if reason else ""),
        flush=True,
    )


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


def _command_details_with_input(
    result: CommandResult,
    *,
    input_text: str | None = None,
) -> dict[str, Any]:
    details = _command_details(result)
    if input_text is not None:
        details["stdin"] = input_text
    return details


def _command_failed(result: CommandResult) -> bool:
    return result.status != ProbeStatus.OK or result.returncode not in (None, 0)


def _is_custom_checkpointdir_unsupported(result: CommandResult) -> bool:
    combined = "\n".join(
        part
        for part in (result.stdout, result.stderr, result.error_message or "")
        if part
    ).lower()
    return any(marker in combined for marker in _CUSTOM_CHECKPOINTDIR_UNSUPPORTED_MARKERS)


def _safe_runner_command(
    *,
    runner: CommandRunner,
    argv: list[str],
    timeout_s: float,
) -> CommandResult:
    try:
        return runner(argv, timeout_s=timeout_s)
    except Exception as exc:
        return CommandResult(
            argv=argv,
            status=ProbeStatus.ERROR,
            returncode=None,
            stdout="",
            stderr="",
            timed_out=False,
            duration_s=0.0,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )


def _capture_checkpoint_storage_details(
    *,
    details: dict[str, Any],
    runner: CommandRunner,
    timeout_s: float,
    checkpoint_dir: str | None,
) -> None:
    storage = details.setdefault("checkpoint_storage", {})

    docker_root_result = _safe_runner_command(
        runner=runner,
        argv=["docker", "info", "--format", "{{.DockerRootDir}}"],
        timeout_s=timeout_s,
    )
    details["commands"]["docker_info_root_dir"] = _command_details(docker_root_result)
    docker_root = docker_root_result.stdout.strip()
    if docker_root_result.status == ProbeStatus.OK and docker_root:
        storage["docker_root_dir"] = docker_root
        docker_root_mount = _safe_runner_command(
            runner=runner,
            argv=["findmnt", "-no", "TARGET,SOURCE,FSTYPE,OPTIONS", docker_root],
            timeout_s=timeout_s,
        )
        details["commands"]["docker_root_findmnt"] = _command_details(docker_root_mount)
        if (
            docker_root_mount.status == ProbeStatus.OK
            and docker_root_mount.stdout.strip()
        ):
            storage["docker_root_mount"] = docker_root_mount.stdout.strip()

    if checkpoint_dir:
        storage["checkpoint_dir"] = checkpoint_dir
        checkpoint_mount = _safe_runner_command(
            runner=runner,
            argv=["findmnt", "-no", "TARGET,SOURCE,FSTYPE,OPTIONS", checkpoint_dir],
            timeout_s=timeout_s,
        )
        details["commands"]["checkpoint_dir_findmnt"] = _command_details(
            checkpoint_mount
        )
        if (
            checkpoint_mount.status == ProbeStatus.OK
            and checkpoint_mount.stdout.strip()
        ):
            storage["checkpoint_dir_mount"] = checkpoint_mount.stdout.strip()


def _capture_memory_snapshot(
    *,
    details: dict[str, Any],
    runner: CommandRunner,
    timeout_s: float,
    container_name: str,
    label: str,
) -> None:
    snapshots = details.setdefault("memory", {}).setdefault("snapshots", {})
    snapshot: dict[str, Any] = {
        "timestamp_utc": utc_now_iso_z(),
        "monotonic_ns": monotonic_ns(),
        "commands": {},
    }
    command_timeout_s = max(5.0, min(timeout_s, 30.0))

    free_result = _safe_runner_command(
        runner=runner,
        argv=["free", "-b"],
        timeout_s=command_timeout_s,
    )
    snapshot["commands"]["free_b"] = _command_details(free_result)

    gpu_result = _safe_runner_command(
        runner=runner,
        argv=[
            "nvidia-smi",
            "--query-gpu=name,memory.total,memory.used",
            "--format=csv,noheader",
        ],
        timeout_s=command_timeout_s,
    )
    snapshot["commands"]["nvidia_smi_gpu"] = _command_details(gpu_result)

    proc_result = _safe_runner_command(
        runner=runner,
        argv=[
            "nvidia-smi",
            "--query-compute-apps=pid,process_name,used_memory",
            "--format=csv,noheader",
        ],
        timeout_s=command_timeout_s,
    )
    snapshot["commands"]["nvidia_smi_compute_apps"] = _command_details(proc_result)

    docker_stats_result = _safe_runner_command(
        runner=runner,
        argv=[
            "docker",
            "stats",
            "--no-stream",
            "--format",
            "{{json .}}",
            container_name,
        ],
        timeout_s=command_timeout_s,
    )
    snapshot["commands"]["docker_stats_no_stream"] = _command_details(
        docker_stats_result
    )

    snapshots[label] = snapshot


def collect_smoke_preemption(
    *,
    run_id: str,
    runtime_session: RuntimeSession,
    docker_criu_integration: Mapping[str, Any] | None,
    runner: CommandRunner = run_command,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    checkpoint_name: str = DEFAULT_CHECKPOINT_NAME,
    checkpoint_dir: str | None = None,
    capture_memory_telemetry: bool = False,
    post_checkpoint_delay_s: float = DEFAULT_POST_CHECKPOINT_DELAY_S,
    criu_config_mode: str | None = None,
    criu_config_allow_sudo: bool = False,
) -> dict[str, Any]:
    details = _base_details(
        runtime_session=runtime_session,
        checkpoint_name=checkpoint_name,
        checkpoint_dir=checkpoint_dir,
        docker_criu_integration=docker_criu_integration,
    )
    criu_config_switcher: CriuRuncConfigPhaseSwitcher | None = None
    criu_diagnostics: dict[str, Any] | None = None
    if criu_config_mode is not None:
        criu_diagnostics = details.setdefault("diagnostics", {}).setdefault(
            "criu_config",
            {
                "mode": criu_config_mode,
                "allow_sudo": bool(criu_config_allow_sudo),
            },
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
        prerequisite_details = (
            docker_criu_integration.get("details") if docker_criu_integration else None
        )
        prerequisite_reason = None
        if isinstance(prerequisite_details, Mapping):
            raw_reason = prerequisite_details.get("reason")
            if isinstance(raw_reason, str) and raw_reason.strip():
                prerequisite_reason = raw_reason.strip()
        details["reason"] = (
            prerequisite_reason or "docker_criu_integration prerequisite is unsupported"
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

    if criu_config_mode not in (None, "cdi_restore_compat"):
        details["reason"] = f"unsupported criu_config_mode: {criu_config_mode!r}"
        details["outcome"] = "not_attempted"
        if criu_diagnostics is not None:
            criu_diagnostics["status"] = ProbeStatus.ERROR.value
        return _finalize_smoke_preemption(
            run_id=run_id,
            status=ProbeStatus.ERROR,
            details=details,
        )

    if (
        criu_config_mode == "cdi_restore_compat"
        and not criu_config_allow_sudo
        and getattr(os, "geteuid", lambda: 1)() != 0
    ):
        details["reason"] = (
            "criu_config_mode cdi_restore_compat requires root or criu_config_allow_sudo"
        )
        details["outcome"] = "not_attempted"
        if criu_diagnostics is not None:
            criu_diagnostics["status"] = ProbeStatus.ERROR.value
        return _finalize_smoke_preemption(
            run_id=run_id,
            status=ProbeStatus.ERROR,
            details=details,
        )

    container_name = runtime_session.container_name
    inspect_labels_result = runner(
        ["docker", "inspect", "--format", "{{json .Config.Labels}}", container_name],
        timeout_s=timeout_s,
    )
    details["commands"]["docker_inspect_labels"] = _command_details(
        inspect_labels_result
    )
    inspect_status, inspect_reason = _classify_result(
        inspect_labels_result,
        command_label="docker inspect labels",
    )
    if inspect_status != ProbeStatus.OK:
        details["reason"] = inspect_reason or "unable to inspect runtime labels"
        details["outcome"] = "not_attempted"
        return _finalize_smoke_preemption(
            run_id=run_id,
            status=inspect_status,
            details=details,
        )

    labels = _parse_label_mapping(inspect_labels_result.stdout)
    if labels is None:
        details["reason"] = "unable to parse docker inspect labels JSON"
        details["outcome"] = "not_attempted"
        return _finalize_smoke_preemption(
            run_id=run_id,
            status=ProbeStatus.ERROR,
            details=details,
        )

    details["container"]["inspected_labels"] = labels
    try:
        _ensure_experiment_owned_runtime_container(
            container_name=container_name, labels=labels
        )
    except ValueError as exc:
        details["reason"] = str(exc)
        details["outcome"] = "not_attempted"
        return _finalize_smoke_preemption(
            run_id=run_id,
            status=ProbeStatus.ERROR,
            details=details,
        )

    details["smoke"]["attempted"] = True
    if capture_memory_telemetry:
        _capture_checkpoint_storage_details(
            details=details,
            runner=runner,
            timeout_s=timeout_s,
            checkpoint_dir=checkpoint_dir,
        )
        _capture_memory_snapshot(
            details=details,
            runner=runner,
            timeout_s=timeout_s,
            container_name=container_name,
            label="pre_checkpoint",
        )

    try:
        if criu_config_mode == "cdi_restore_compat":
            criu_config_switcher = CriuRuncConfigPhaseSwitcher(
                runner=runner,
                timeout_s=timeout_s,
                use_sudo=bool(criu_config_allow_sudo),
            )
            acquire_result = criu_config_switcher.acquire()
            if criu_diagnostics is not None:
                criu_diagnostics.update(criu_config_switcher.diagnostics)
            if criu_config_switcher.lock_result is not None:
                details["commands"]["acquire_criu_runc_conf_lock"] = _command_details(
                    criu_config_switcher.lock_result
                )
            if criu_config_switcher.capture_original_result is not None:
                details["commands"]["capture_criu_runc_conf_original"] = (
                    _command_details(criu_config_switcher.capture_original_result)
                )
            if acquire_result.status != ProbeStatus.OK:
                details["reason"] = str(
                    criu_config_switcher.diagnostics.get("lock", {}).get("reason")
                    or criu_config_switcher.diagnostics.get("original", {}).get(
                        "error_message"
                    )
                    or "failed to prepare CRIU runc.conf switching"
                )
                details["outcome"] = "not_attempted"
                return _finalize_smoke_preemption(
                    run_id=run_id,
                    status=ProbeStatus.ERROR,
                    details=details,
                )

        checkpoint_phase = details["checkpoint"]
        _mark_phase_start(checkpoint_phase, phase_name="checkpoint")
        if criu_config_switcher is not None:
            dump_text = build_runc_conf_text(phase="dump")
            dump_conf_result = criu_config_switcher.write_phase("dump")
            details["commands"]["write_criu_runc_conf_dump"] = (
                _command_details_with_input(
                    dump_conf_result,
                    input_text=dump_text,
                )
            )
            if (
                dump_conf_result.status != ProbeStatus.OK
                or dump_conf_result.returncode != 0
            ):
                _mark_phase_end(
                    checkpoint_phase,
                    phase_name="checkpoint",
                    status=ProbeStatus.ERROR,
                    reason="failed to write dump CRIU runc.conf",
                    command="write_criu_runc_conf_dump",
                )
                details["reason"] = "failed to write dump CRIU runc.conf"
                details["outcome"] = "not_attempted"
                return _finalize_smoke_preemption(
                    run_id=run_id,
                    status=ProbeStatus.ERROR,
                    details=details,
                )

        checkpoint_argv = ["docker", "checkpoint", "create"]
        if checkpoint_dir:
            checkpoint_argv.extend(["--checkpoint-dir", checkpoint_dir])
        checkpoint_argv.extend([container_name, checkpoint_name])
        checkpoint_result = runner(
            checkpoint_argv,
            timeout_s=timeout_s,
        )
        details["commands"]["docker_checkpoint_create"] = _command_details(
            checkpoint_result
        )
        checkpoint_status, checkpoint_reason = _classify_result(
            checkpoint_result,
            command_label="docker checkpoint create",
            capability_sensitive=True,
        )
        _mark_phase_end(
            checkpoint_phase,
            phase_name="checkpoint",
            status=checkpoint_status,
            reason=checkpoint_reason,
            command="docker_checkpoint_create",
        )
        if checkpoint_status != ProbeStatus.OK:
            if capture_memory_telemetry:
                _capture_memory_snapshot(
                    details=details,
                    runner=runner,
                    timeout_s=timeout_s,
                    container_name=container_name,
                    label="checkpoint_failed",
                )
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
        _mark_phase_start(restore_phase, phase_name="restore")
        if capture_memory_telemetry:
            _capture_memory_snapshot(
                details=details,
                runner=runner,
                timeout_s=timeout_s,
                container_name=container_name,
                label="pre_restore",
            )
        if post_checkpoint_delay_s > 0:
            time.sleep(post_checkpoint_delay_s)
            details["commands"]["post_checkpoint_delay"] = {
                "duration_s": post_checkpoint_delay_s,
                "status": ProbeStatus.OK.value,
            }

        if criu_config_switcher is not None:
            restore_text = build_runc_conf_text(phase="restore")
            restore_conf_result = criu_config_switcher.write_phase("restore")
            details["commands"]["write_criu_runc_conf_restore"] = (
                _command_details_with_input(
                    restore_conf_result,
                    input_text=restore_text,
                )
            )
            if (
                restore_conf_result.status != ProbeStatus.OK
                or restore_conf_result.returncode != 0
            ):
                _mark_phase_end(
                    restore_phase,
                    phase_name="restore",
                    status=ProbeStatus.ERROR,
                    reason="failed to write restore CRIU runc.conf",
                    command="write_criu_runc_conf_restore",
                )
                details["reason"] = "failed to write restore CRIU runc.conf"
                details["outcome"] = "restore_failed"
                return _finalize_smoke_preemption(
                    run_id=run_id,
                    status=ProbeStatus.ERROR,
                    details=details,
                )

        start_argv = ["docker", "start"]
        if checkpoint_dir:
            start_argv.extend(["--checkpoint-dir", checkpoint_dir])
        start_argv.extend(["--checkpoint", checkpoint_name, container_name])
        start_result = runner(
            start_argv,
            timeout_s=timeout_s,
        )
        details["commands"]["docker_start_checkpoint"] = _command_details(start_result)
        start_status, start_reason = _classify_result(
            start_result,
            command_label="docker start --checkpoint",
            capability_sensitive=True,
        )

        fallback_used = False
        if (
            start_status != ProbeStatus.OK
            and checkpoint_dir
            and start_status == ProbeStatus.UNSUPPORTED
            and _is_custom_checkpointdir_unsupported(start_result)
        ):
            fallback_details = details.setdefault("fallback", {})
            fallback_details["reason"] = (
                "docker start does not support custom checkpointdir on this host; "
                "retrying with default checkpoint storage"
            )
            fallback_details["triggered_by"] = "docker_start_checkpoint"
            fallback_details["original_checkpoint_dir"] = checkpoint_dir

            recover_start_result = runner(
                ["docker", "start", container_name],
                timeout_s=timeout_s,
            )
            details["commands"]["docker_start_recover_after_checkpointdir_failure"] = (
                _command_details(recover_start_result)
            )
            recover_start_status, recover_start_reason = _classify_result(
                recover_start_result,
                command_label="docker start",
                capability_sensitive=True,
            )
            if recover_start_status == ProbeStatus.OK:
                fallback_checkpoint_name = f"{checkpoint_name}-default-fallback"
                fallback_details["checkpoint_name"] = fallback_checkpoint_name

                fallback_checkpoint_result = runner(
                    [
                        "docker",
                        "checkpoint",
                        "create",
                        container_name,
                        fallback_checkpoint_name,
                    ],
                    timeout_s=timeout_s,
                )
                details["commands"]["docker_checkpoint_create_fallback"] = (
                    _command_details(fallback_checkpoint_result)
                )
                fallback_checkpoint_status, fallback_checkpoint_reason = _classify_result(
                    fallback_checkpoint_result,
                    command_label="docker checkpoint create (fallback)",
                    capability_sensitive=True,
                )
                if fallback_checkpoint_status == ProbeStatus.OK:
                    fallback_start_result = runner(
                        [
                            "docker",
                            "start",
                            "--checkpoint",
                            fallback_checkpoint_name,
                            container_name,
                        ],
                        timeout_s=timeout_s,
                    )
                    details["commands"]["docker_start_checkpoint_fallback"] = (
                        _command_details(fallback_start_result)
                    )
                    fallback_start_status, fallback_start_reason = _classify_result(
                        fallback_start_result,
                        command_label="docker start --checkpoint (fallback)",
                        capability_sensitive=True,
                    )
                    if fallback_start_status == ProbeStatus.OK:
                        fallback_used = True
                        start_status = ProbeStatus.OK
                        start_reason = None
                    else:
                        start_status = fallback_start_status
                        start_reason = (
                            fallback_start_reason
                            or "fallback restore start failed"
                        )
                else:
                    start_status = fallback_checkpoint_status
                    start_reason = (
                        fallback_checkpoint_reason
                        or "fallback checkpoint creation failed"
                    )
            else:
                start_status = recover_start_status
                start_reason = (
                    recover_start_reason or "failed to recover runtime after unsupported checkpoint-dir"
                )

        if start_status != ProbeStatus.OK:
            _mark_phase_end(
                restore_phase,
                phase_name="restore",
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

        state_command_name = "docker_inspect_state"
        if fallback_used:
            state_command_name = "docker_inspect_state_fallback"
        state_result = runner(
            ["docker", "inspect", "--format", "{{.State.Status}}", container_name],
            timeout_s=timeout_s,
        )
        details["commands"][state_command_name] = _command_details(state_result)
        state_status, state_reason = _classify_result(
            state_result,
            command_label="docker inspect state",
        )
        if state_status != ProbeStatus.OK:
            _mark_phase_end(
                restore_phase,
                phase_name="restore",
                status=state_status,
                reason=state_reason,
                command="docker_inspect_state",
            )
            details["reason"] = (
                state_reason or "unable to inspect restored runtime state"
            )
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
                phase_name="restore",
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
            phase_name="restore",
            status=ProbeStatus.OK,
            command=state_command_name,
        )
        if fallback_used:
            details["fallback"]["used"] = True
            details["fallback"]["status"] = ProbeStatus.OK.value
        if capture_memory_telemetry:
            _capture_memory_snapshot(
                details=details,
                runner=runner,
                timeout_s=timeout_s,
                container_name=container_name,
                label="post_restore",
            )
        details["reason"] = "checkpoint and restore completed"
        details["outcome"] = "restored"
        return _finalize_smoke_preemption(
            run_id=run_id,
            status=ProbeStatus.OK,
            details=details,
        )
    finally:
        if criu_config_switcher is not None:
            restore_original_result = criu_config_switcher.restore_original()
            restore_original_input = None
            if criu_config_switcher.original_exists:
                restore_original_input = criu_config_switcher.original_text or ""
            details["commands"]["restore_criu_runc_conf_original"] = (
                _command_details_with_input(
                    restore_original_result,
                    input_text=restore_original_input,
                )
            )
            release_result = criu_config_switcher.release()
            details["commands"]["release_criu_runc_conf_lock"] = _command_details(
                release_result
            )
            if criu_diagnostics is None:
                criu_diagnostics = details.setdefault("diagnostics", {}).setdefault(
                    "criu_config",
                    {
                        "mode": criu_config_mode,
                        "allow_sudo": bool(criu_config_allow_sudo),
                    },
                )
            assert criu_diagnostics is not None
            criu_diagnostics.update(criu_config_switcher.diagnostics)

            failed_cleanup_steps: list[str] = []
            if _command_failed(restore_original_result):
                failed_cleanup_steps.append("restore_original")
            if _command_failed(release_result):
                failed_cleanup_steps.append("release_lock")

            if failed_cleanup_steps:
                previous_outcome = details.get("outcome")
                previous_reason = details.get("reason")
                cleanup_reason = "CRIU cleanup failed: " + ", ".join(
                    failed_cleanup_steps
                )
                if isinstance(previous_reason, str) and previous_reason.strip():
                    cleanup_reason = f"{cleanup_reason} (after {previous_reason})"
                details["cleanup"] = {
                    "status": ProbeStatus.ERROR.value,
                    "failed_steps": failed_cleanup_steps,
                    "previous_outcome": previous_outcome,
                    "previous_reason": previous_reason,
                }
                criu_diagnostics["cleanup_failure"] = {
                    "steps": failed_cleanup_steps,
                    "previous_outcome": previous_outcome,
                    "previous_reason": previous_reason,
                }
                details["reason"] = cleanup_reason
                details["outcome"] = "cleanup_failed"
                return _finalize_smoke_preemption(
                    run_id=run_id,
                    status=ProbeStatus.ERROR,
                    details=details,
                )
