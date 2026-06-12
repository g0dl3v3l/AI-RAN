# V0 Checkpoint/Restore — Cross-Session Handoff (Detailed)

## Purpose
This document consolidates work from the referenced sessions plus the current session so a new chat/session can continue without losing context.

---

## Sessions Covered

### 1) Primary long-running research/debug session
- **Session ID:** `ses_171a574cbffeTON1cZZZU44x6e`
- **Range:** 2026-06-03 to 2026-06-11
- **Role in project:** established the core research framing + early CRIU/v0 experiments + architecture direction.

### 2) Follow-up implementation/debug session
- **Session ID:** `ses_148adf896ffeEkFFMDf4wkxgB7`
- **Range:** 2026-06-11
- **Role in project:** concrete archive analysis, implementation of post-restore validation defaults, CRIU config switching, commits/pushes, runbook creation.

### 3) Continuation session from #2
- **Session ID:** `ses_1478a7a25ffecH4PT1P4ue0BYS`
- **Range:** 2026-06-11 to 2026-06-12
- **Role in project:** continued v0 debug automation, additional fixes, expanded full-debug workflow, log collection improvements, and later archive triage.

### 4) Current session (this chat)
- **Range:** 2026-06-12 (current)
- **Role in project:** analyzed newly added failure archives:
  - `ai-edge-v0-vllm-disk-20260612-041925-unsupported-failure-logs.tar.gz`
  - `ai-edge-v0-vllm-disk-20260612-041925-unsupported-failure-logs-with-checkpoints.tar.gz`
  and identified exact failure mechanism with evidence.

---

## Project Goal (Current)
Validate and harden AI-edge **v0 checkpoint/restore** workflow for vLLM under real host conditions, while separating:
1. container/process restore success, and
2. application-layer serving continuity success.

---

## Research/Design Direction Agreed Earlier (from sessions)

The work was intentionally reframed as:

> **Checkpoint-resume study for AI serving systems under lease/resource reconfiguration.**

Key modeling assumptions that were repeatedly discussed:
- Preserve **portable application/serving state** (requests, scheduler state, logical progress).
- Do **not** rely on guaranteed portability of raw CUDA/NVIDIA runtime internals across restore/resource changes.
- Treat CRIU as a practical baseline/experimental arm, not a guaranteed universal solution for GPU-resident execution state.

Experiment arms evolved around:
1. Cold restart
2. CRIU/container checkpoint-resume
3. Application-level checkpoint
4. Generic intermediate-state checkpoint (not LLM-only)
5. Idealized/oracle resume baseline

---

## What Was Implemented Across Sessions

### A) Post-restore proof path and validation behavior
- Commit: `a2113c0` — **make post-restore probing default proof path**.
- Intent: avoid falsely concluding restore failure from an in-flight request that started pre-checkpoint and timed out before restore completed.

### B) CRIU config switching in shipped probe configs
- Commit: `7e55542` — **enable CRIU config switching in v0 probe configs**.
- Intent: ensure proper phase-aware CRIU/runc configuration handling is applied by default in probe runs.

### C) Full debug one-command workflow and hardening commits
Recent commit chain (already present in repo history):
- `ca21602` feat(v0): add one-command full debug workflow
- `09607c8` fix(v0): add preflight cleanup and storage guards to debug runner
- `1c2f78c` fix(v0): enforce host-network restore defaults in debug runner
- `1fa3e85` fix(v0): enforce minimum preemption timeout in debug runner
- plus supporting commits around CRIU log capture/debug collection and probe safety.

---

## Key Historical Findings (Before Current Archive)

### Archive class 1 (older)
- Failure was CRIU checkpoint-side (`/dev/shm` semaphore remap/link-remap issue).

### Archive class 2 (older)
- Checkpoint+restore commands completed, but smoke proof was inconclusive because request timing and restore windows overlapped badly; not a clean post-restore liveness proof.

---

## Current Session: New Archive Analysis (041925)

## Input archives analyzed
1. `ai-edge-v0-vllm-disk-20260612-041925-unsupported-failure-logs.tar.gz`
2. `ai-edge-v0-vllm-disk-20260612-041925-unsupported-failure-logs-with-checkpoints.tar.gz`

Both archives show the **same failure pattern**.

## Verified outcome chain
From artifacts in both archives:
- `smoke_preemption.status = "unsupported"`
- `smoke_preemption.details.outcome = "not_supported"`
- `smoke_preemption.details.reason = "unsupported capability: docker start --checkpoint"`
- `smoke_validation.status = "unsupported"`
- `smoke_validation.classification = "smoke_not_supported"`

However, command-level details show the more specific root error:
- `docker_checkpoint_create` => **ok**
- `docker_start_checkpoint` => **error rc=1**, stderr includes:
  - `OCI runtime restore failed ... prestart hook #0 ...`
  - `nvidia-container-cli: mount error: ... /merged/proc/driver/nvidia: no such file or directory`

### Important interpretation
The label "unsupported capability: docker start --checkpoint" is a **classifier outcome** triggered by generic unsupported markers (including "no such file or directory").

The **actual restore failure mechanism** in this run is GPU runtime hook/mount reconstruction failure during restore (NVIDIA prestart hook path), not checkpoint creation failure.

### Additional host hint
`system-debug/docker-journal.txt` also contains checkpoint reader path errors (missing `cgroup.img` in checkpoint path), reinforcing restore/checkpoint artifact-path inconsistency during this run class.

---

## Where Evidence Lives (high-signal files)

Inside each 041925 archive:
- `artifacts/docker_criu_integration.json`
- `artifacts/smoke_preemption.json`
- `artifacts/smoke_validation.json`
- `artifacts/post_restore_probe.json`
- `artifacts/stage_events.jsonl`
- `full_debug_runner.log`
- `system-debug/error-summary.txt`
- `system-debug/docker-journal.txt`
- `system-debug/containerd-journal.txt`
- `system-debug/docker-events-v0.txt`
- `system-debug/checkpoint-log-paths.txt`

Key strings to grep:
- `unsupported capability: docker start --checkpoint`
- `smoke_not_supported`
- `nvidia-container-cli: mount error`
- `OCI runtime restore failed`
- `no such file or directory`

---

## Current State of Repository / Branch (for continuation)

Recent commit history includes the v0-focused fixes listed above. There are many unrelated modified/untracked files in workspace (multiple project areas), so **future commits should be carefully scoped to AI-edge v0 files only**.

---

## Known Operational Pain Points

1. **Long checkpoint + restore durations** remain a bottleneck.
2. Classification may over-compress distinct runtime failures into "unsupported".
3. Restore can pass command-level checks while application-level continuity remains unproven.
4. The 041925 run class shows GPU hook/mount restore issues during `docker start --checkpoint`.

---

## Recommended Next Steps (Immediate)

1. **Classify 041925 failure as NVIDIA restore hook/mount-path failure** (not generic unsupported) in analysis/reporting.
2. Add/adjust diagnostics around restore command stderr parsing so classifier can emit finer categories (e.g., `gpu_hook_mount_failure`).
3. Capture and preserve restore-phase runtime hook logs in the final debug bundle explicitly.
4. Re-run with latest debug runner hardening (`1fa3e85`) and compare if failure signature persists unchanged.
5. Keep proving post-restore readiness with explicit post-restore request path (already made default earlier).

---

## Repro/Collection Commands That Were Standardized

### Package selected logs (041925 style)
```bash
RUN_ID=ai-edge-v0-vllm-disk-20260612-041925
BASE=/home/ubuntu/ai-edge-runs/$RUN_ID
OUT=~/ai-edge-export/${RUN_ID}-unsupported-failure-logs-with-checkpoints.tar.gz
mkdir -p ~/ai-edge-export

EXTRA_PATHS=()
[ -d "$BASE/system-debug/checkpoint-files" ] && EXTRA_PATHS+=(system-debug/checkpoint-files)

tar -czf "$OUT" -C "$BASE" \
  artifacts/docker_criu_integration.json \
  artifacts/smoke_preemption.json \
  artifacts/smoke_validation.json \
  artifacts/post_restore_probe.json \
  artifacts/stage_events.jsonl \
  full_debug_runner.log \
  system-debug/error-summary.txt \
  system-debug/docker-journal.txt \
  system-debug/containerd-journal.txt \
  system-debug/docker-events-v0.txt \
  system-debug/v0-containers.txt \
  system-debug/v0-container-inspect.txt \
  system-debug/v0-checkpoints.txt \
  system-debug/checkpoint-log-paths.txt \
  system-debug/process-state.txt \
  system-debug/system-info.txt \
  "${EXTRA_PATHS[@]}"
```

### SCP (from Ubuntu `10.203.53.10` to local)
```bash
mkdir -p ~/Downloads/ai-edge-v0-debug
scp ubuntu@10.203.53.10:/home/ubuntu/ai-edge-export/ai-edge-v0-vllm-disk-20260612-041925-unsupported-failure-logs-with-checkpoints.tar.gz ~/Downloads/ai-edge-v0-debug/
```

---

## Open Questions to Resolve in Next Session

1. Should classifier taxonomy be expanded now, or keep current labels and document detailed root cause externally?
2. Do we need a restore-specific “GPU hook health check” stage before smoke validation classification?
3. For the paper/experiment framing: what minimum cross-architecture intermediate-state contract must be standardized next?

---

## Suggested Starter Prompt for New Session

Use this as first message in a new session:

> Continue from `ai-edge-v0-debug/SESSION_HANDOFF_2026-06-12.md`. Focus on the 041925 failure class where `docker start --checkpoint` fails with `nvidia-container-cli mount error ... /proc/driver/nvidia no such file or directory`. Implement precise failure classification and add targeted restore-phase diagnostics/log capture so this failure is no longer bucketed as generic unsupported. Keep commits scoped to AI-edge v0 files only.

---

## Final Continuation Note
You can safely assume:
- the foundational debug/runbook framework exists,
- post-restore probe defaults are already in place,
- latest unresolved blocker is **restore-time GPU hook/mount failure classification + diagnostics quality** for the 041925 failure family.
