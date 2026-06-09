# Automatic CRIU Log Capture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture Docker/containerd CRIU dump logs automatically during V0 checkpoint failure, including root-owned `/run/containerd/.../criu-dump.log` files, before cleanup removes the path.

**Architecture:** Keep capture inside `v0_orchestrator.py` where log paths are already parsed and capture already runs before runtime cleanup. Add a safe fallback that only escalates for expected Docker/containerd CRIU log locations and uses `sudo -n cat` so automation never blocks for a password. Record fallback command diagnostics in the existing `details.diagnostics.criu_logs` artifact field.

**Tech Stack:** Python stdlib (`pathlib`, `shutil`, `errno`), existing `ai_runtime_experiments.utils.command.run_command`, existing pytest unit tests.

---

### Task 1: Add sudo fallback tests

**Files:**
- Modify: `experiments/tests/unit/test_v0_orchestrator.py`

- [ ] **Step 1: Write failing sudo-success test**

Add this test after `test_capture_criu_logs_copies_paths_from_failed_command_stderr`:

```python
def test_capture_criu_logs_uses_sudo_cat_when_direct_copy_denied(
    tmp_path: Path, monkeypatch
):
    import ai_runtime_experiments.v0_orchestrator as orchestrator
    from ai_runtime_experiments.utils.command import CommandResult

    source_log = Path(
        "/run/containerd/io.containerd.runtime.v2.task/moby/container-id/criu-dump.log"
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    record = make_probe_result(
        run_id="run-with-root-criu-log",
        component="smoke_preemption",
        status=ProbeStatus.ERROR,
        details={
            "commands": {
                "docker_checkpoint_create": {
                    "stderr": f"criu failed: type DUMP errno 0 path= {source_log}\n"
                }
            }
        },
    )

    def _copyfile_raises_permission(src, dst):
        del src, dst
        raise PermissionError("permission denied")

    calls: list[list[str]] = []

    def _fake_run_command(argv, *, timeout_s=None, **kwargs):
        del kwargs
        calls.append(list(argv))
        assert timeout_s == 5.0
        return CommandResult(
            argv=list(argv),
            status=ProbeStatus.OK,
            returncode=0,
            stdout="root-owned criu details\n",
            stderr="",
            timed_out=False,
            duration_s=0.01,
            error_type=None,
            error_message=None,
        )

    monkeypatch.setattr(orchestrator.shutil, "copyfile", _copyfile_raises_permission)
    monkeypatch.setattr(orchestrator, "run_command", _fake_run_command)

    orchestrator._capture_criu_logs(run_dir=run_dir, records={"smoke_preemption.json": record})

    copied = run_dir / "criu_logs" / "smoke_preemption" / "01-criu-dump.log"
    assert copied.read_text(encoding="utf-8") == "root-owned criu details\n"
    assert calls == [["sudo", "-n", "cat", str(source_log)]]
    assert record["details"]["diagnostics"]["criu_logs"][0]["status"] == "ok"
    assert record["details"]["diagnostics"]["criu_logs"][0]["fallback"] == "sudo-cat"
```

- [ ] **Step 2: Write failing unsafe-path test**

Add this test after sudo-success test:

```python
def test_capture_criu_logs_does_not_sudo_cat_untrusted_log_path(
    tmp_path: Path, monkeypatch
):
    import ai_runtime_experiments.v0_orchestrator as orchestrator

    source_log = Path("/home/user/secret.log")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    record = make_probe_result(
        run_id="run-with-untrusted-log",
        component="smoke_preemption",
        status=ProbeStatus.ERROR,
        details={
            "commands": {
                "docker_checkpoint_create": {
                    "stderr": f"criu failed: type DUMP errno 0 path= {source_log}\n"
                }
            }
        },
    )

    def _copyfile_raises_permission(src, dst):
        del src, dst
        raise PermissionError("permission denied")

    def _run_command_must_not_run(*args, **kwargs):
        del args, kwargs
        raise AssertionError("sudo fallback must not run for untrusted paths")

    monkeypatch.setattr(orchestrator.shutil, "copyfile", _copyfile_raises_permission)
    monkeypatch.setattr(orchestrator, "run_command", _run_command_must_not_run)

    orchestrator._capture_criu_logs(run_dir=run_dir, records={"smoke_preemption.json": record})

    entry = record["details"]["diagnostics"]["criu_logs"][0]
    assert entry["status"] == "error"
    assert entry["error_type"] == "PermissionError"
    assert entry["fallback"] == "skipped-untrusted-path"
```

- [ ] **Step 3: Run tests and confirm failure**

Run:

```bash
PYTHONPATH=experiments/src pytest experiments/tests/unit/test_v0_orchestrator.py::test_capture_criu_logs_uses_sudo_cat_when_direct_copy_denied experiments/tests/unit/test_v0_orchestrator.py::test_capture_criu_logs_does_not_sudo_cat_untrusted_log_path -q
```

Expected: both tests fail because `v0_orchestrator.py` does not import `run_command` and does not implement sudo fallback.

### Task 2: Implement safe sudo fallback

**Files:**
- Modify: `experiments/src/ai_runtime_experiments/v0_orchestrator.py`

- [ ] **Step 1: Import command helper**

Add import near existing imports:

```python
from ai_runtime_experiments.utils.command import CommandResult, run_command
```

- [ ] **Step 2: Add trusted path helper**

Add below `_CRIU_LOG_PATH_RE`:

```python
_TRUSTED_CRIU_LOG_PREFIXES = (
    Path("/run/containerd"),
    Path("/var/lib/docker"),
)


def _is_trusted_criu_log_path(path: Path) -> bool:
    try:
        resolved = path.resolve(strict=False)
    except OSError:
        resolved = path.absolute()
    return any(
        resolved == prefix or prefix in resolved.parents
        for prefix in _TRUSTED_CRIU_LOG_PREFIXES
    )
```

- [ ] **Step 3: Add command serialization helper**

Add below `_extract_criu_log_paths`:

```python
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
```

- [ ] **Step 4: Add sudo-cat fallback helper**

Add below `_command_result_details`:

```python
def _copy_criu_log_with_sudo_cat(source_path: Path, destination: Path) -> dict[str, Any]:
    result = run_command(
        ["sudo", "-n", "cat", str(source_path)],
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
```

- [ ] **Step 5: Replace PermissionError handling in `_capture_criu_logs_for_record`**

Change the `except OSError as exc:` block to:

```python
        except OSError as exc:
            entry["status"] = ProbeStatus.ERROR.value
            entry["error_type"] = type(exc).__name__
            entry["error_message"] = str(exc)
            if isinstance(exc, PermissionError):
                if _is_trusted_criu_log_path(source_path):
                    entry.update(_copy_criu_log_with_sudo_cat(source_path, destination))
                else:
                    entry["fallback"] = "skipped-untrusted-path"
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
PYTHONPATH=experiments/src pytest experiments/tests/unit/test_v0_orchestrator.py::test_capture_criu_logs_copies_paths_from_failed_command_stderr experiments/tests/unit/test_v0_orchestrator.py::test_capture_criu_logs_uses_sudo_cat_when_direct_copy_denied experiments/tests/unit/test_v0_orchestrator.py::test_capture_criu_logs_does_not_sudo_cat_untrusted_log_path experiments/tests/unit/test_v0_orchestrator.py::test_orchestrator_copies_criu_log_before_runtime_cleanup_deletes_source -q
```

Expected: all selected tests pass.

### Task 3: Verify and commit

**Files:**
- Verify: `experiments/src/ai_runtime_experiments/v0_orchestrator.py`
- Verify: `experiments/tests/unit/test_v0_orchestrator.py`
- Verify: `docs/superpowers/plans/2026-06-09-auto-criu-log-capture.md`

- [ ] **Step 1: Run full unit suite**

Run:

```bash
PYTHONPATH=experiments/src pytest experiments/tests/unit -q
```

Expected: all unit tests pass.

- [ ] **Step 2: Run diagnostics**

Run LSP diagnostics on changed Python files. Expected: no new errors in changed files.

- [ ] **Step 3: Check git diff**

Run:

```bash
git diff -- experiments/src/ai_runtime_experiments/v0_orchestrator.py experiments/tests/unit/test_v0_orchestrator.py docs/superpowers/plans/2026-06-09-auto-criu-log-capture.md
```

Expected: diff only contains sudo fallback, tests, and this plan.

- [ ] **Step 4: Commit only**

Run:

```bash
git add experiments/src/ai_runtime_experiments/v0_orchestrator.py experiments/tests/unit/test_v0_orchestrator.py docs/superpowers/plans/2026-06-09-auto-criu-log-capture.md
git commit -m "fix(v0): capture root-owned CRIU dump logs"
```

Expected: commit succeeds. Do not push.
