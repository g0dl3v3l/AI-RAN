# V0 Debug Bundle Capture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make V0 automatically capture CRIU, Docker, runc, containerd, and NVIDIA/CUDA diagnostics before cleanup deletes transient checkpoint logs.

**Architecture:** Add a reusable `debug_capture.py` helper that parses CRIU log paths from command results, safely captures trusted root-owned paths via `sudo -n cat`, writes bounded/redacted text artifacts under the run directory, and returns diagnostics records. Integrate via an optional debug-capture callback in `docker_criu/probe.py` so core probe logic stays decoupled from artifact layout while still capturing logs before baseline cleanup. Integrate `v0_orchestrator.py` for end-of-run host/runtime debug bundles. All captures are best-effort and must never fail the probe.

**Tech Stack:** Python stdlib (`pathlib`, `re`, `shutil`), existing `CommandResult`/`run_command`, existing `ProbeStatus`, existing `artifacts.write_json`, pytest unit tests with mocked runners.

---

## Safety Rules

- Never interactive sudo. Use only `sudo -n` with short timeout.
- Sudo-read only normalized trusted CRIU log paths under `/run/containerd/io.containerd.runtime.v2.task/moby` or Docker data-root paths.
- Never fail a probe because diagnostics failed.
- Redact common secrets: `token`, `password`, `secret`, `api_key`, `apikey`.
- Bound text artifacts to last 256 KiB by default; mark truncation in diagnostics.
- Write debug files with mode `0600`.

---

## File Structure

- Create: `experiments/src/ai_runtime_experiments/debug_capture.py`
  - Owns CRIU path extraction, trusted-path checks, `sudo -n cat` fallback, redaction, bounded text artifact writes, and debug bundle assembly.
- Modify: `experiments/src/ai_runtime_experiments/docker_criu/probe.py`
  - Accept optional debug-capture callback and call it before `_cleanup_owned_container(...)` on checkpoint/start/state failures.
- Modify: `experiments/src/ai_runtime_experiments/v0_orchestrator.py`
  - Reuse `debug_capture` helpers, pass callback to Docker+CRIU probe, collect end-of-run debug bundle.
- Modify: `experiments/scripts/check_docker_criu.py`
  - Pass callback into `collect_docker_criu_integration` so standalone baseline captures logs too.
- Modify/Create tests:
  - `experiments/tests/unit/test_debug_capture.py`
  - `experiments/tests/unit/test_docker_criu.py`
  - `experiments/tests/unit/test_v0_orchestrator.py`

---

### Task 1: Add reusable debug capture helper

**Files:**
- Create: `experiments/src/ai_runtime_experiments/debug_capture.py`
- Create: `experiments/tests/unit/test_debug_capture.py`

- [ ] **Step 1: Write failing tests**

Create `experiments/tests/unit/test_debug_capture.py` with tests for:

```python
from pathlib import Path

from ai_runtime_experiments.schemas import ProbeStatus
from ai_runtime_experiments.utils.command import CommandResult


def _result(argv, *, status=ProbeStatus.OK, stdout="", stderr="", returncode=0, error_type=None, error_message=None):
    return CommandResult(list(argv), status, returncode, stdout, stderr, False, 0.01, error_type, error_message)


def test_extract_criu_log_paths_deduplicates_command_text():
    from ai_runtime_experiments.debug_capture import extract_criu_log_paths
    record = {"details": {"commands": {"a": {"stderr": "path= /run/containerd/a/criu-dump.log\n"}, "b": {"stderr": "path= /run/containerd/a/criu-dump.log\n"}}}}
    assert extract_criu_log_paths(record) == [Path("/run/containerd/a/criu-dump.log")]


def test_capture_criu_logs_copies_existing_file(tmp_path: Path):
    from ai_runtime_experiments.debug_capture import capture_criu_logs_for_record
    source = tmp_path / "criu-dump.log"
    source.write_text("dump root cause\n", encoding="utf-8")
    record = {"details": {"commands": {"checkpoint": {"stderr": f"failed path= {source}\n"}}}}
    capture_criu_logs_for_record(run_dir=tmp_path / "run", artifact_name="docker_criu_integration.json", record=record)
    copied = tmp_path / "run" / "criu_logs" / "docker_criu_integration" / "01-criu-dump.log"
    assert copied.read_text(encoding="utf-8") == "dump root cause\n"
    assert record["details"]["diagnostics"]["criu_logs"][0]["status"] == "ok"


def test_capture_criu_logs_uses_sudo_cat_for_permission_error(tmp_path: Path, monkeypatch):
    import ai_runtime_experiments.debug_capture as debug_capture
    source = Path("/run/containerd/io.containerd.runtime.v2.task/moby/id/criu-dump.log")
    record = {"details": {"commands": {"checkpoint": {"stderr": f"path= {source}\n"}}}}
    monkeypatch.setattr(debug_capture.shutil, "copyfile", lambda src, dst: (_ for _ in ()).throw(PermissionError("denied")))
    calls = []
    def runner(argv, *, timeout_s=None, **kwargs):
        del kwargs
        calls.append((list(argv), timeout_s))
        return _result(argv, stdout="root dump\n")
    debug_capture.capture_criu_logs_for_record(run_dir=tmp_path / "run", artifact_name="docker_criu_integration.json", record=record, runner=runner)
    assert calls == [(["sudo", "-n", "cat", str(source)], 5.0)]
    assert (tmp_path / "run" / "criu_logs" / "docker_criu_integration" / "01-criu-dump.log").read_text(encoding="utf-8") == "root dump\n"


def test_collect_debug_bundle_redacts_and_bounds_outputs(tmp_path: Path):
    from ai_runtime_experiments.debug_capture import collect_debug_bundle
    responses = {
        ("docker", "version"): _result(["docker", "version"], stdout="Docker version\n"),
        ("docker", "info"): _result(["docker", "info"], stdout="TOKEN=secret-value\n"),
        ("docker", "ps", "-a", "--filter", "label=ai-edge-experiment=v0"): _result([], stdout="CONTAINER ID\n"),
        ("criu", "--version"): _result([], stdout="Version: 4.2\n"),
        ("criu", "check", "--all"): _result([], status=ProbeStatus.ERROR, returncode=1, stderr="warn\n"),
        ("runc", "--version"): _result([], stdout="runc version\n"),
        ("nvidia-smi"): _result([], stdout="GPU\n"),
        ("nvidia-smi", "-q"): _result([], stdout="GPU query\n"),
        ("which", "cuda-checkpoint"): _result([], status=ProbeStatus.ERROR, returncode=1, stderr="missing\n"),
        ("sudo", "-n", "cat", "/etc/criu/runc.conf"): _result([], stdout="enable-external-masters\n"),
        ("sudo", "-n", "journalctl", "-u", "docker", "--since", "1 hour ago", "-n", "500", "--no-pager"): _result([], stdout="docker journal\n"),
        ("sudo", "-n", "journalctl", "-u", "containerd", "--since", "1 hour ago", "-n", "500", "--no-pager"): _result([], stdout="containerd journal\n"),
    }
    def runner(argv, *, timeout_s=None, **kwargs):
        del timeout_s, kwargs
        return responses[tuple(argv)]
    diagnostics = collect_debug_bundle(run_dir=tmp_path, runner=runner, since="1 hour ago")
    assert (tmp_path / "debug" / "docker-version.txt").read_text(encoding="utf-8") == "Docker version\n"
    assert "secret-value" not in (tmp_path / "debug" / "docker-info.txt").read_text(encoding="utf-8")
    assert diagnostics["commands"]["criu_check_all"]["status"] == "error"
```

- [ ] **Step 2: Run RED**

```bash
PYTHONPATH=experiments/src pytest experiments/tests/unit/test_debug_capture.py -q
```

Expected: module missing.

- [ ] **Step 3: Implement `debug_capture.py`**

Implement functions:
- `command_result_details`
- `iter_command_dicts`
- `extract_criu_log_paths`
- `trusted_criu_log_path`
- `redact_text`
- `bound_text`
- `write_text_artifact`
- `copy_criu_log_with_sudo_cat`
- `capture_criu_logs_for_record`
- `collect_debug_bundle`

Required command set for `collect_debug_bundle`:

```python
{
  "docker_version": ["docker", "version"],
  "docker_info": ["docker", "info"],
  "docker_ps_v0": ["docker", "ps", "-a", "--filter", "label=ai-edge-experiment=v0"],
  "criu_version": ["criu", "--version"],
  "criu_check_all": ["criu", "check", "--all"],
  "runc_version": ["runc", "--version"],
  "nvidia_smi": ["nvidia-smi"],
  "nvidia_smi_q": ["nvidia-smi", "-q"],
  "cuda_checkpoint_path": ["which", "cuda-checkpoint"],
  "runc_conf": ["sudo", "-n", "cat", "/etc/criu/runc.conf"],
  "docker_journal": ["sudo", "-n", "journalctl", "-u", "docker", "--since", since, "-n", "500", "--no-pager"],
  "containerd_journal": ["sudo", "-n", "journalctl", "-u", "containerd", "--since", since, "-n", "500", "--no-pager"],
}
```

- [ ] **Step 4: Run GREEN**

```bash
PYTHONPATH=experiments/src pytest experiments/tests/unit/test_debug_capture.py -q
```

Expected: all pass.

### Task 2: Capture baseline Docker+CRIU logs before cleanup

**Files:**
- Modify: `experiments/src/ai_runtime_experiments/docker_criu/probe.py`
- Modify: `experiments/scripts/check_docker_criu.py`
- Modify: `experiments/tests/unit/test_docker_criu.py`

- [ ] **Step 1: Write failing test**

Append a test in `test_docker_criu.py` proving `collect_docker_criu_integration(..., debug_capture_hook=hook)` calls hook before `docker rm -f` when checkpoint create fails. The hook should copy a tmp CRIU log before the runner deletes it during cleanup.

- [ ] **Step 2: Implement callback integration**

Add type alias:

```python
DebugCaptureHook = Callable[[dict[str, Any]], None]
```

Add optional keyword to `collect_docker_criu_integration`:

```python
debug_capture_hook: DebugCaptureHook | None = None,
```

Add helper:

```python
def _run_debug_capture_hook(
    *, debug_capture_hook: DebugCaptureHook | None, run_id: str, details: dict[str, Any]
) -> None:
    if debug_capture_hook is None:
        return
    record = _finalize_record(run_id=run_id, status=ProbeStatus.ERROR, details=details)
    try:
        debug_capture_hook(record)
    except Exception as exc:
        details.setdefault("diagnostics", {}).setdefault("debug_capture_errors", []).append({
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        })
```

Call this helper before cleanup in checkpoint/start/state failure branches.

- [ ] **Step 3: Update standalone CLI**

In `check_docker_criu.py`, import `capture_criu_logs_for_record` and pass callback:

```python
debug_capture_hook=lambda record: capture_criu_logs_for_record(
    run_dir=output_dir,
    artifact_name="docker_criu_integration.json",
    record=record,
)
```

- [ ] **Step 4: Verify focused tests**

```bash
PYTHONPATH=experiments/src pytest experiments/tests/unit/test_docker_criu.py::test_docker_criu_captures_checkpoint_log_before_cleanup experiments/tests/unit/test_docker_criu.py::test_check_docker_criu_cli_writes_artifacts -q
```

### Task 3: Integrate debug bundle in orchestrator

**Files:**
- Modify: `experiments/src/ai_runtime_experiments/v0_orchestrator.py`
- Modify: `experiments/tests/unit/test_v0_orchestrator.py`

- [ ] **Step 1: Replace duplicated local CRIU helper logic where practical**

Import from debug_capture:

```python
from ai_runtime_experiments.debug_capture import capture_criu_logs_for_record, collect_debug_bundle
```

Keep `_capture_criu_logs_for_record` wrapper if needed for tests, but delegate to shared helper.

- [ ] **Step 2: Pass callback to baseline probe**

In `_run_real_sequence`, change baseline probe call to include:

```python
debug_capture_hook=lambda record: capture_criu_logs_for_record(
    run_dir=run_dir,
    artifact_name="docker_criu_integration.json",
    record=record,
),
```

- [ ] **Step 3: Write final debug bundle artifact**

After `_capture_criu_logs(run_dir=run_dir, records=records)`, call:

```python
debug_bundle = collect_debug_bundle(run_dir=run_dir)
write_json(run_dir / "debug" / "debug_bundle.json", debug_bundle)
```

Include path/status in metadata:

```python
metadata["debug_bundle"] = {
    "status": debug_bundle.get("status"),
    "artifact_path": str(run_dir / "debug" / "debug_bundle.json"),
}
```

- [ ] **Step 4: Update tests**

Monkeypatch `collect_debug_bundle` in existing orchestrator tests where command availability would matter, returning `{"status": "ok", "commands": {}}`. Add one test asserting `debug/debug_bundle.json` exists and metadata points to it.

### Task 4: Verify and commit

- [ ] **Step 1: Focused tests**

```bash
PYTHONPATH=experiments/src pytest experiments/tests/unit/test_debug_capture.py experiments/tests/unit/test_docker_criu.py::test_docker_criu_captures_checkpoint_log_before_cleanup experiments/tests/unit/test_v0_orchestrator.py::test_orchestrator_copies_criu_log_before_runtime_cleanup_deletes_source -q
```

- [ ] **Step 2: Full unit suite**

```bash
PYTHONPATH=experiments/src pytest experiments/tests/unit -q
```

- [ ] **Step 3: LSP diagnostics on changed Python files**

Expected: no new errors.

- [ ] **Step 4: Commit locally only**

Use semantic commit:

```bash
git add experiments/src/ai_runtime_experiments/debug_capture.py experiments/src/ai_runtime_experiments/docker_criu/probe.py experiments/src/ai_runtime_experiments/v0_orchestrator.py experiments/scripts/check_docker_criu.py experiments/tests/unit/test_debug_capture.py experiments/tests/unit/test_docker_criu.py experiments/tests/unit/test_v0_orchestrator.py docs/superpowers/plans/2026-06-09-v0-debug-bundle-capture.md
git commit -m "fix(v0): capture debug bundle automatically"
```

Do not push.

---

## Self-Review

- Oracle feedback incorporated: optional callback, bounded commands, redaction, no interactive sudo, path trust, best-effort diagnostics.
- Spec coverage: baseline pre-cleanup CRIU capture, smoke-preemption reuse, final bundle, Docker/containerd/NVIDIA/CRIU diagnostics, standalone CLI, tests, local commit.
- Placeholder scan: no TODO/TBD placeholders.
- Type consistency: uses existing `CommandResult`, `ProbeStatus`, `runner`, `run_dir`, and artifact naming conventions.
