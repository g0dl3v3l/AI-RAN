# V0 CDI CRIU Phase Switch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let V0 run vLLM with NVIDIA CDI devices and switch CRIU runc config between dump and restore phases so Docker+CRIU can exercise the working live-CUDA path.

**Architecture:** Extend vLLM Docker launch with explicit `gpu_mode` options (`gpus_flag`, `nvidia_runtime`, `cdi`) while preserving current defaults. Add an opt-in, lock-guarded preemption hook that writes a dump-safe `/etc/criu/runc.conf` before `docker checkpoint create`, writes a restore-safe config (adds `mntns-compat-mode`) before `docker start --checkpoint`, and restores the original config in `finally`, using noninteractive `sudo -n` only when explicitly enabled. All host mutation attempts must be recorded in diagnostics.

**Tech Stack:** Python stdlib, existing `CommandResult`/`run_command`, existing `ProbeStatus`, pytest with mocked runners.

---

## Design Constraints

- Default behavior unchanged unless config opts in.
- No interactive sudo: use `sudo -n` only if an explicit `allow_sudo: true` config gate is set.
- Do not mutate host CRIU config unless config explicitly enables phase switching.
- Acquire a host-level lock for the whole checkpoint→restore→cleanup sequence before mutating `/etc/criu/runc.conf`; fail early if lock contention exists.
- Preserve original config exactly; if it was missing, remove it in cleanup.
- Restore original config in `finally` for success, checkpoint failure, restore failure, timeout, and Python exceptions.
- Record every lock/config write/restore attempt in `smoke_preemption.details.commands` or `diagnostics`.
- If CRIU config write fails, fail early with useful diagnostics instead of running a misleading checkpoint.
- `mntns-compat-mode` must only be present for restore, never dump.
- If `gpu_mode: cdi` is requested, do not silently fall back to `--gpus all` or `--runtime nvidia`.

---

## Task 1: Add vLLM CDI GPU mode

**Files:**
- Modify: `experiments/src/ai_runtime_experiments/runtime_adapters/vllm.py`
- Modify: `experiments/tests/unit/test_vllm_adapter.py`
- Modify: `experiments/src/ai_runtime_experiments/config.py`
- Modify: `experiments/tests/unit/test_config.py`

- [ ] **Step 1: Add failing vLLM CDI test**

Append to `experiments/tests/unit/test_vllm_adapter.py` near host network tests:

```python
def test_docker_server_start_uses_cdi_gpu_device():
    from ai_runtime_experiments.runtime_adapters.vllm import VLLMRuntimeAdapter

    image_inspect = ["docker", "image", "inspect", DEFAULT_IMAGE]
    command = [
        "docker", "run", "-d",
        "--name", "ai-edge-v0-vllm-fixed",
        "--label", "ai-edge-experiment=v0",
        "--label", "ai-edge-component=vllm-runtime",
        "--label", "ai-edge-run-id=task-7",
        "--network", "host",
        "--device", "nvidia.com/gpu=all",
        DEFAULT_IMAGE,
        "--model", DEFAULT_MODEL,
        "--host", "0.0.0.0",
        "--port", "8000",
    ]
    probe_calls: list[dict[str, object]] = []

    def readiness_probe(*, base_url: str, timeout_s: float):
        probe_calls.append({"base_url": base_url, "timeout_s": timeout_s})
        return ProbeStatus.OK, {"models_url": f"{base_url}/models", "attempts": 1}

    runner = RecordingRunner({
        tuple(image_inspect): _result(image_inspect, status=ProbeStatus.OK, stdout="[]\n"),
        tuple(command): _result(command, status=ProbeStatus.OK, stdout="container-123\n"),
    })
    adapter = VLLMRuntimeAdapter(
        config={
            "docker_server": {
                "enabled": True,
                "image": DEFAULT_IMAGE,
                "model": DEFAULT_MODEL,
                "port": 8000,
                "network_mode": "host",
                "gpu_mode": "cdi",
                "gpu_device": "nvidia.com/gpu=all",
                "container_name": "ai-edge-v0-vllm-fixed",
            }
        },
        runner=runner,
        timeout_s=9.0,
        readiness_probe=readiness_probe,
    )

    session = adapter.start(run_id="task-7")

    assert session.status == ProbeStatus.OK
    assert session.base_url == "http://127.0.0.1:8000/v1"
    assert session.runtime_check["details"]["container"]["gpu_mode"] == "cdi"
    assert session.runtime_check["details"]["container"]["gpu_device"] == "nvidia.com/gpu=all"
    assert runner.calls == [image_inspect, command]
```

- [ ] **Step 2: Run RED**

```bash
PYTHONPATH=experiments/src pytest experiments/tests/unit/test_vllm_adapter.py::test_docker_server_start_uses_cdi_gpu_device -q
```

Expected: fails because `build_vllm_docker_command` has no CDI branch.

- [ ] **Step 3: Implement vLLM CDI mode**

In `build_vllm_docker_command`, add params:

```python
gpu_device: str = "nvidia.com/gpu=all",
```

Change GPU branch:

```python
    if gpu_mode == "nvidia_runtime":
        command.extend(["--runtime", "nvidia", "-e", "NVIDIA_VISIBLE_DEVICES=all"])
    elif gpu_mode == "cdi":
        command.extend(["--device", gpu_device])
    else:
        command.extend(["--gpus", "all"])
```

In `_start_docker_server`, read:

```python
        gpu_mode = str(docker_config.get("gpu_mode") or "gpus_flag").strip() or "gpus_flag"
        gpu_device = str(docker_config.get("gpu_device") or "nvidia.com/gpu=all").strip() or "nvidia.com/gpu=all"
```

Record in `details["container"]` and pass to both command builds.

- [ ] **Step 4: Add defaults/config test**

In `config.py` vLLM docker defaults add:

```python
"network_mode": None,
"gpu_mode": "gpus_flag",
"gpu_device": "nvidia.com/gpu=all",
```

In `test_config.py`, assert these defaults exist for vLLM.

- [ ] **Step 5: Run focused tests**

```bash
PYTHONPATH=experiments/src pytest experiments/tests/unit/test_vllm_adapter.py experiments/tests/unit/test_config.py -q
```

Expected: pass.

---

## Task 2: Add CRIU runc.conf phase switching helper

**Files:**
- Create: `experiments/src/ai_runtime_experiments/criu_config.py`
- Create: `experiments/tests/unit/test_criu_config.py`

- [ ] **Step 1: Write failing helper tests**

Create `experiments/tests/unit/test_criu_config.py`:

```python
from ai_runtime_experiments.schemas import ProbeStatus
from ai_runtime_experiments.utils.command import CommandResult


def _result(argv, *, status=ProbeStatus.OK, stdout="", stderr="", returncode=0):
    return CommandResult(list(argv), status, returncode, stdout, stderr, False, 0.01, None, None)


def test_builds_dump_and_restore_runc_conf_text():
    from ai_runtime_experiments.criu_config import build_runc_conf_text

    dump_text = build_runc_conf_text(phase="dump")
    restore_text = build_runc_conf_text(phase="restore")

    assert "libdir /usr/local/lib/criu" in dump_text
    assert "mntns-compat-mode" not in dump_text
    assert "mntns-compat-mode" in restore_text


def test_write_runc_conf_uses_noninteractive_sudo_tee():
    from ai_runtime_experiments.criu_config import write_runc_conf

    calls = []
    def runner(argv, *, timeout_s=None, input_text=None, **kwargs):
        del kwargs
        calls.append({"argv": list(argv), "timeout_s": timeout_s, "input_text": input_text})
        return _result(argv, stdout="ok\n")

    result = write_runc_conf(phase="restore", runner=runner, timeout_s=3.0)

    assert result.status == ProbeStatus.OK
    assert calls[0]["argv"] == ["sudo", "-n", "tee", "/etc/criu/runc.conf"]
    assert calls[0]["timeout_s"] == 3.0
    assert "mntns-compat-mode" in calls[0]["input_text"]
```

- [ ] **Step 2: Run RED**

```bash
PYTHONPATH=experiments/src pytest experiments/tests/unit/test_criu_config.py -q
```

Expected: module missing.

- [ ] **Step 3: Implement `criu_config.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ai_runtime_experiments.schemas import ProbeStatus
from ai_runtime_experiments.utils.command import CommandResult, run_command

RUNC_CONF_PATH = "/etc/criu/runc.conf"
RUNC_CONF_LOCK_PATH = "/tmp/ai-edge-criu-runc-conf.lock"
_BASE_LINES = [
    "libdir /usr/local/lib/criu",
    "ext-mount-map auto",
    "external mnt[]",
    "enable-external-masters",
    "tcp-established",
    "link-remap",
    "file-locks",
    "ghost-limit 1073741824",
]


def build_runc_conf_text(*, phase: Literal["dump", "restore"]) -> str:
    lines = list(_BASE_LINES)
    if phase == "restore":
        lines.append("mntns-compat-mode")
    return "\n".join(lines) + "\n"


def write_runc_conf(*, phase: Literal["dump", "restore"], runner=run_command, timeout_s: float = 5.0, use_sudo: bool = False) -> CommandResult:
    argv = ["tee", RUNC_CONF_PATH]
    if use_sudo:
        argv = ["sudo", "-n", *argv]
    return runner(argv, timeout_s=timeout_s, input_text=build_runc_conf_text(phase=phase))
```

Also implement helpers to acquire/release lock, read original config, restore original config, and remove missing original file. Use `sudo -n` only when `allow_sudo` is true.

If `run_command` does not support `input_text`, add support in `utils/command.py` with a test or use a safe Bash-free Python subprocess helper. Prefer adding `input_text` to `run_command` and preserving existing callers.

- [ ] **Step 4: Verify helper tests**

```bash
PYTHONPATH=experiments/src pytest experiments/tests/unit/test_criu_config.py -q
```

Expected: pass.

---

## Task 3: Wire CRIU phase switching into smoke preemption

**Files:**
- Modify: `experiments/src/ai_runtime_experiments/preemption/smoke.py`
- Modify: `experiments/tests/unit/test_smoke_preemption.py`
- Modify: `experiments/src/ai_runtime_experiments/config.py`
- Modify: `experiments/tests/unit/test_config.py`

- [ ] **Step 1: Add failing preemption test**

Append to `test_smoke_preemption.py`:

```python
def test_smoke_preemption_switches_criu_config_before_dump_and_restore():
    from ai_runtime_experiments.preemption import collect_smoke_preemption

    container_name = "ai-edge-v0-vllm-fixed"
    inspect_command = ["docker", "inspect", "--format", "{{json .Config.Labels}}", container_name]
    dump_conf = ["sudo", "-n", "tee", "/etc/criu/runc.conf"]
    checkpoint_command = ["docker", "checkpoint", "create", container_name, "cp1"]
    restore_conf = ["sudo", "-n", "tee", "/etc/criu/runc.conf"]
    start_command = ["docker", "start", "--checkpoint", "cp1", container_name]
    state_command = ["docker", "inspect", "--format", "{{.State.Status}}", container_name]

    runner = RecordingRunner({
        tuple(inspect_command): _result(inspect_command, status=ProbeStatus.OK, stdout='{"ai-edge-experiment":"v0","ai-edge-component":"vllm-runtime","ai-edge-run-id":"task-8"}\n'),
        tuple(dump_conf): _result(dump_conf, status=ProbeStatus.OK, stdout="ok\n"),
        tuple(checkpoint_command): _result(checkpoint_command, status=ProbeStatus.OK, stdout="cp1\n"),
        tuple(restore_conf): _result(restore_conf, status=ProbeStatus.OK, stdout="ok\n"),
        tuple(start_command): _result(start_command, status=ProbeStatus.OK, stdout=container_name + "\n"),
        tuple(state_command): _result(state_command, status=ProbeStatus.OK, stdout="running\n"),
    })

    record = collect_smoke_preemption(
        run_id="task-8",
        runtime_session=_runtime_session(container_name=container_name),
        docker_criu_integration=_docker_criu_probe(),
        runner=runner,
        checkpoint_name="cp1",
        post_checkpoint_delay_s=0,
        criu_config_mode="cdi_restore_compat",
        criu_config_allow_sudo=True,
    )

    assert record["status"] == "ok"
    assert runner.calls == [inspect_command, dump_conf, checkpoint_command, restore_conf, start_command, state_command]
    assert "mntns-compat-mode" not in record["details"]["commands"]["write_criu_runc_conf_dump"]["stdin"]
    assert "mntns-compat-mode" in record["details"]["commands"]["write_criu_runc_conf_restore"]["stdin"]
```

If command details do not include stdin, assert via runner captured calls instead.

- [ ] **Step 2: Implement optional `criu_config_mode`**

In `collect_smoke_preemption` signature add:

```python
criu_config_mode: str | None = None,
criu_config_allow_sudo: bool = False,
```

Reject phase switching if `criu_config_mode == "cdi_restore_compat"` and `criu_config_allow_sudo` is false while the current user is not root.

Before checkpoint:

```python
if criu_config_mode == "cdi_restore_compat":
    dump_conf_result = write_runc_conf(phase="dump", runner=runner)
    details["commands"]["write_criu_runc_conf_dump"] = _command_details(dump_conf_result)
    if dump_conf_result.status != ProbeStatus.OK or dump_conf_result.returncode != 0:
        details["reason"] = "failed to write dump CRIU runc.conf"
        details["outcome"] = "not_attempted"
        return _finalize_smoke_preemption(run_id=run_id, status=ProbeStatus.ERROR, details=details)
```

Before `docker start --checkpoint`:

```python
if criu_config_mode == "cdi_restore_compat":
    restore_conf_result = write_runc_conf(phase="restore", runner=runner)
    details["commands"]["write_criu_runc_conf_restore"] = _command_details(restore_conf_result)
    if restore_conf_result.status != ProbeStatus.OK or restore_conf_result.returncode != 0:
        _mark_phase_end(restore_phase, status=ProbeStatus.ERROR, reason="failed to write restore CRIU runc.conf", command="write_criu_runc_conf_restore")
        details["reason"] = "failed to write restore CRIU runc.conf"
        details["outcome"] = "restore_failed"
        return _finalize_smoke_preemption(run_id=run_id, status=ProbeStatus.ERROR, details=details)
```

- [ ] **Step 3: Pass config from orchestrator**

In `v0_orchestrator.py`, pass:

```python
criu_config_mode=preemption_options.get("criu_config_mode"),
```

to `collect_smoke_preemption`.

Add default in `config.py`:

```python
"criu_config_mode": None,
"criu_config_allow_sudo": False,
```

- [ ] **Step 4: Verify tests**

```bash
PYTHONPATH=experiments/src pytest experiments/tests/unit/test_criu_config.py experiments/tests/unit/test_smoke_preemption.py experiments/tests/unit/test_v0_orchestrator.py -q
```

Expected: pass.

---

## Task 4: Verify and commit

- [ ] **Step 1: Focused tests**

```bash
PYTHONPATH=experiments/src pytest experiments/tests/unit/test_vllm_adapter.py experiments/tests/unit/test_criu_config.py experiments/tests/unit/test_smoke_preemption.py experiments/tests/unit/test_v0_orchestrator.py experiments/tests/unit/test_config.py -q
```

- [ ] **Step 2: Full unit suite**

```bash
PYTHONPATH=experiments/src pytest experiments/tests/unit -q
```

- [ ] **Step 3: LSP diagnostics**

Run diagnostics on changed Python files.

- [ ] **Step 4: Commit locally only**

```bash
git add experiments/src/ai_runtime_experiments/runtime_adapters/vllm.py experiments/tests/unit/test_vllm_adapter.py experiments/src/ai_runtime_experiments/config.py experiments/tests/unit/test_config.py experiments/src/ai_runtime_experiments/criu_config.py experiments/tests/unit/test_criu_config.py experiments/src/ai_runtime_experiments/preemption/smoke.py experiments/tests/unit/test_smoke_preemption.py experiments/src/ai_runtime_experiments/v0_orchestrator.py docs/superpowers/plans/2026-06-10-v0-cdi-criu-phase-switch.md
git commit -m "feat(v0): support CDI restore-compatible checkpoints"
```

Do not push.

---

## Runtime config after implementation

```yaml
runtime_options:
  vllm:
    docker_server:
      enabled: true
      image: vllm/vllm-openai:latest
      port: 8000
      network_mode: host
      gpu_mode: cdi
      gpu_device: nvidia.com/gpu=all
      extra_args: []
      image_pull_timeout_s: 1800.0
      model: Qwen/Qwen2-0.5B-Instruct

probe_options:
  preemption:
    timeout_s: 1200.0
    checkpoint_name: ai-edge-v0-criu-checkpoint
    criu_config_mode: cdi_restore_compat
    criu_config_allow_sudo: true
```

## Self-Review

- Covers CDI Docker launch, CRIU dump/restore config switching, orchestrator config pass-through, tests, and run config.
- No placeholders.
- Explicitly gated behind config opt-ins, preserving existing default behavior.
