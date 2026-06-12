Title: Docker checkpoint/restore (CPU-only) — minimal safe sequence
Date: 2026-06-05

Purpose
- Concise design for a CPU-only smoke test using Docker checkpoint/create and docker start --checkpoint.
- Produce a minimal robust sequence and practical caveats for a Python CLI wrapper.

Assumptions (for this spec)
- Kernel/CRIU compatibility exists on the host (same machine, same kernel version)
- CPU-only: no GPU toolkits required
- No live network/socket reconnections required (the smoke test will avoid network-dependent resources)
- Filesystem mounts used by the container are not mutated between checkpoint and restore

Minimal safe sequence (exact commands)
1) Ensure container is in a quiescent state (flush critical state to disk):
   - run: docker exec <C> sync || true
   - optionally instruct the app to stop accepting new work and close external FDs

2) Create checkpoint (synchronous):
   - docker checkpoint create <container> <checkpoint-name>
   - note: this leaves the container running by default; the checkpoint is stored under Docker-managed checkpoints path

3) Stop the original container (prepare for restore target):
   - docker stop <container>
   - verify it is stopped: docker inspect -f '{{.State.Status}}' <container>  -> should be "exited"

4) Prepare a restore target container with identical runtime config
   Option A: reuse the same container (preferred when checkpoint lives under the same container dir):
     - If you stopped the same container in step 3, you can simply run:
       docker start --checkpoint <checkpoint-name> <container>
     - Note: docker start accepts --checkpoint only when the checkpoint directory is present for that container

   Option B: restore into a fresh container (when migrating checkpoint or using custom checkpoint dir):
     - Create a new container with the same image, mounts, env, command, etc but do not start it:
       docker create --name <restarget> --volume ... --env ... <image> <cmd>
     - Move or make the checkpoint available at the new container's checkpoints path, or pass --checkpoint-dir to docker start
     - Start with: docker start --checkpoint-dir /path/to/checkpoints --checkpoint <checkpoint-name> <restarget>

5) Run minimal smoke verification inside the restored container
   - docker exec <restarget> -- <smoke-command>
   - Keep smoke-command CPU-only and non-networked (e.g., verify a counter, hash sum, or simple Python loop resumed state)

Practical notes & caveats (short)
- CRIU/Kernel: CRIU must be compatible with the running kernel. Check 'criu --version' and kernel version. Mismatch → restore failure.
- Container config must match: same mounts, devices, seccomp/apparmor/capabilities and cgroup layout. Differences can cause restore errors.
- File descriptors: sockets, pipes, and epoll state to external endpoints will not reconnect. Close or avoid them before checkpoint.
- Network namespaces: NAT/host-networked sockets may not survive restore; prefer no-network smoke test or pre-close listeners and re-open after restore.
- PID and in-container process identity: PIDs inside the container will be restored, but external process relationships (on host) are irrelevant.
- Timers and monotonic clocks: some timers may not resume exactly — ensure app tolerates small timer jumps.
- Overlay/union FS: do not change files under overlay-backed mounts between checkpoint and restore; maintain identical filesystem state.
- Checkpoint storage: when moving checkpoints between hosts or nodes, copy the checkpoint directory and use --checkpoint-dir on restore.
- Docker engine: docker checkpoint/restore uses CRIU and may require experimental features enabled depending on Docker version. Verify 'docker info' supports checkpoints.

Python CLI wrapper (minimal pattern)
- Wrap the following steps with robust error handling and retries:
  1) docker exec C sync
  2) docker checkpoint create C NAME  (capture stdout/stderr/exit)
  3) docker stop C
  4) If restoring to same container: docker start --checkpoint NAME C
     Else: docker create ... -> ensure checkpoint files visible -> docker start --checkpoint NAME NEW
  5) docker exec NEW smoke-command (timeout + output capture)

- Implementation tips:
  - Use subprocess.run([...], check=True, capture_output=True) and return explicit structured errors.
  - Make all Docker calls idempotent: if checkpoint already exists, allow --force-like logic (delete and recreate).
  - Validate prerequisites before attempting restore: kernel/CRIU check, docker daemon reachable, container present and stopped.
  - Timeouts: checkpointing may block; set a reasonable timeout and capture logs on failure.
  - Logging: persist stdout/stderr + docker events around the checkpoint window for post-mortem.

Edge cases to detect & fail fast
- "CRIU incompatible" errors: surface to user with suggestion to check kernel/CRIU versions
- "checkpoint not found" on start: list container checkpoints path and show expected locations
- "restore failed" with cgroups/namespace errors: include container config diff and suggest using same runtime config

Deliverable: a small Python function sketch (pseudocode)

```python
import subprocess, shlex

def run(cmd, timeout=30):
    return subprocess.run(shlex.split(cmd), capture_output=True, text=True, timeout=timeout)

def checkpoint_and_restore(container, ckpt, smoke_cmd, restarget=None):
    run(f"docker exec {container} sync", timeout=10)
    run(f"docker checkpoint create {container} {ckpt}")
    run(f"docker stop {container}")
    target = restarget or container
    run(f"docker start --checkpoint {ckpt} {target}")
    out = run(f"docker exec {target} {smoke_cmd}")
    return out.stdout
```

User review
- This spec assumes no network/IPC restore requirements and same-host restore. If you need network or socket reconnection semantics, request that explicitly and I will expand the plan.

---
Spec complete. Reviewed for placeholders and internal consistency.
