# NVIDIA MPS Active Thread Percentage: Configuration Semantics & Constraints

## Executive Summary

**Question 1: Must the MPS daemon be pre-started?**  
**Answer: YES, absolutely required.** The MPS daemon (`nvidia-cuda-mps-server`) must be running before any client process attempts to use MPS. A client cannot connect to or initialize MPS without an active daemon. This is not optional.

**Question 2: Must `CUDA_MPS_ACTIVE_THREAD_PERCENTAGE` be set before CUDA context creation?**  
**Answer: YES, with critical nuance.** The timing depends on which configuration level you target:
- **Daemon level**: Must be set BEFORE daemon startup (via `nvidia-cuda-mps-control -d`)
- **Client process level**: Must be set BEFORE process starts (before any CUDA initialization)
- **Per-context level** (opt-in): Can be changed dynamically per-context via `CUDA_MPS_ENABLE_PER_CTX_DEVICE_MULTIPROCESSOR_PARTITIONING`

**Question 3: Is setting `CUDA_MPS_ACTIVE_THREAD_PERCENTAGE` from a Python process sufficient per-run?**  
**Answer: DEPENDS on strategy.** Setting the environment variable in your Python process is NOT sufficient for uniform partitioning (the default). However, with explicit opt-in, per-context dynamic configuration IS possible per-run.

---

## Three-Level Configuration Hierarchy

### Level 1: MPS Daemon Level (Global, Immutable per daemon lifetime)

**When to configure**: Before starting the daemon.

**How to configure**:
```bash
export CUDA_MPS_ACTIVE_THREAD_PERCENTAGE=50
nvidia-cuda-mps-control -d  # Start daemon with 50% thread allocation
```

**Characteristics**:
- Sets the global default for ALL clients connecting to this daemon
- Once the daemon is running, this env var has NO effect on existing or new clients
- Each GPU can only have ONE MPS daemon; all clients share the daemon-level setting
- Cannot be changed at runtime without restarting the daemon
- Clients can only FURTHER CONSTRAIN this limit, never exceed it

---

### Level 2: Client Process Level (Per-process, set at startup)

**When to configure**: Before the client process starts.

**How to configure**:
```python
import os
os.environ['CUDA_MPS_ACTIVE_THREAD_PERCENTAGE'] = '25'
# NOW initialize CUDA context
import pycuda.driver as cuda
cuda.init()
device = cuda.Device(0)
ctx = device.make_context()
```

**Characteristics**:
- Applies a further constraint to the daemon-level setting
- If daemon is set to 50%, client set to 25%, the client gets 25% (constrained by client setting)
- If daemon is set to 50%, client tries to set 75%, the client gets 50% (capped at daemon limit)
- Once set at process initialization, uniform partitioning is immutable for that process
- All CUDA contexts in the process share this partitioning

**Caveat**: Setting `CUDA_MPS_ACTIVE_THREAD_PERCENTAGE` AFTER the first CUDA context is created has NO effect on uniform partitioning (the default strategy).

---

### Level 3: Per-Context Level (Per-context, dynamic via opt-in)

**When to configure**: REQUIRES explicit opt-in environment variable, then configurable per-context.

**How to configure**:
```python
import os
# OPT-IN to per-context partitioning (set BEFORE any CUDA context creation)
os.environ['CUDA_MPS_ENABLE_PER_CTX_DEVICE_MULTIPROCESSOR_PARTITIONING'] = '1'
os.environ['CUDA_MPS_ACTIVE_THREAD_PERCENTAGE'] = '50'

import pycuda.driver as cuda
cuda.init()
device = cuda.Device(0)

# Create first context with 50%
ctx1 = device.make_context()
# This context gets 50% of available threads

# Create second context with different partitioning
os.environ['CUDA_MPS_ACTIVE_THREAD_PERCENTAGE'] = '25'
ctx2 = device.make_context()
# This new context gets 25% (dynamic per-context!)

ctx1.pop()  # Switch context; first context still has 50% reserved
ctx2.pop()
ctx1.push()  # First context resumes with 50%
```

**Characteristics**:
- Requires `CUDA_MPS_ENABLE_PER_CTX_DEVICE_MULTIPROCESSOR_PARTITIONING=1` set BEFORE first context creation
- Allows DIFFERENT thread allocations for DIFFERENT contexts within the SAME process
- Configuration persists per context (not per process)
- **This is the only mechanism that enables true per-run dynamic configuration within Python**
- Each context's allocation is independent; changing one context's setting doesn't affect others
- Volta+ GPUs only

---

## Direct Answers to Requirements

### ✅ Requirement 1: Daemon Required?
**YES.** No CUDA process using MPS can function without an active MPS daemon. The daemon must be running before ANY client initializes CUDA:

```bash
# Terminal 1: Start daemon first
nvidia-cuda-mps-control -d

# Terminal 2+: Run your Python code
python my_mps_app.py
```

Without a running daemon, MPS-based partitioning will silently fail or fall back to no partitioning.

---

### ✅ Requirement 2: Env Var Must Be Set Before CUDA Context?
**YES, with level-specific timing:**

| Level | Must be set before | Can be changed after? | Scope |
|-------|-------------------|----------------------|-------|
| **Daemon** | Daemon startup | NO (restart required) | All clients |
| **Client (uniform)** | Process/CUDA init | NO (immutable after first context) | All contexts in process |
| **Per-context (opt-in)** | First context creation | YES (per new context) | Individual context |

**Critical timing violations**:
```python
# ❌ WRONG: Setting AFTER first context creation (uniform partitioning, default)
import pycuda.driver as cuda
cuda.init()
device = cuda.Device(0)
ctx = device.make_context()  # <-- First context created here
os.environ['CUDA_MPS_ACTIVE_THREAD_PERCENTAGE'] = '25'  # <-- TOO LATE, has no effect
```

```python
# ✅ CORRECT: Setting BEFORE any context creation (uniform partitioning)
import os
os.environ['CUDA_MPS_ACTIVE_THREAD_PERCENTAGE'] = '25'
import pycuda.driver as cuda
cuda.init()
device = cuda.Device(0)
ctx = device.make_context()  # <-- Now respects the setting
```

```python
# ✅ CORRECT: Per-context dynamic configuration (opt-in)
import os
os.environ['CUDA_MPS_ENABLE_PER_CTX_DEVICE_MULTIPROCESSOR_PARTITIONING'] = '1'
os.environ['CUDA_MPS_ACTIVE_THREAD_PERCENTAGE'] = '50'
import pycuda.driver as cuda
cuda.init()
device = cuda.Device(0)
ctx1 = device.make_context()

# Now dynamic changes work per new context:
os.environ['CUDA_MPS_ACTIVE_THREAD_PERCENTAGE'] = '25'
ctx2 = device.make_context()  # <-- This context gets 25%
```

---

### ✅ Requirement 3: Is Per-Run Configuration from Python Sufficient?

**ANSWER: NO for uniform partitioning (default); YES for per-context partitioning (opt-in).**

#### Scenario A: Uniform Partitioning (Default)
```python
# ❌ NOT SUFFICIENT for per-run configuration
os.environ['CUDA_MPS_ACTIVE_THREAD_PERCENTAGE'] = '50'
import pycuda.driver as cuda
cuda.init()
device = cuda.Device(0)
ctx = device.make_context()  # Partitioning is now fixed for the process lifetime
```
**Why not sufficient**: Once set at process initialization, you cannot change it mid-run without restarting the process.

#### Scenario B: Per-Context Partitioning (Opt-in) ← **THIS ENABLES PER-RUN CONFIG**
```python
# ✅ SUFFICIENT for per-run dynamic configuration
import os
os.environ['CUDA_MPS_ENABLE_PER_CTX_DEVICE_MULTIPROCESSOR_PARTITIONING'] = '1'
import pycuda.driver as cuda
cuda.init()
device = cuda.Device(0)

# Run 1 with 50%
os.environ['CUDA_MPS_ACTIVE_THREAD_PERCENTAGE'] = '50'
ctx1 = device.make_context()
# ... kernel launches ...
ctx1.pop()

# Run 2 with 25% (same process, different allocation)
os.environ['CUDA_MPS_ACTIVE_THREAD_PERCENTAGE'] = '25'
ctx2 = device.make_context()
# ... kernel launches ...
ctx2.pop()
```
**Why sufficient**: Per-context partitioning allows different CUDA contexts within the same process to have different thread allocations.

---

## Critical Caveats & Pitfalls

### Caveat 1: MPS Daemon Restarts Clear Configuration
If you restart the MPS daemon, all client connections are severed. The daemon must be restarted with the desired env var set:
```bash
nvidia-cuda-mps-control -d quit  # Stop daemon
export CUDA_MPS_ACTIVE_THREAD_PERCENTAGE=75
nvidia-cuda-mps-control -d  # Restart with new setting
```

### Caveat 2: Percentage Constraints Are Soft (Threads, Not SMs)
`CUDA_MPS_ACTIVE_THREAD_PERCENTAGE` allocates a percentage of **threads**, not specific SMs:
- A 50% allocation does NOT mean "use half the SMs"
- It means "allocate 50% of available threads across SMs"
- Actual SM utilization depends on kernel characteristics and block scheduling
- Unlike Green Contexts (which pin specific SMs), MPS partitioning is virtualized

### Caveat 3: Volta+ Only
`CUDA_MPS_ACTIVE_THREAD_PERCENTAGE` only works on Volta and newer GPUs. Pre-Volta MPS supports up to 16 contexts without percentage partitioning.

### Caveat 4: Client Constraints Cannot Exceed Daemon Default
If the daemon is set to 40% and you try to set a client to 60%, the client gets 40%:
```python
# Daemon started with CUDA_MPS_ACTIVE_THREAD_PERCENTAGE=40
os.environ['CUDA_MPS_ACTIVE_THREAD_PERCENTAGE'] = '60'  # Client tries 60%
# Result: Client gets 40% (capped at daemon limit)
```

### Caveat 5: Uniform Partitioning is Process-Scoped
All CUDA contexts in a process share the same thread allocation (uniform partitioning). Creating multiple contexts doesn't give you independent allocations unless you opt into per-context partitioning.

---

## Practical Implementation Patterns

### Pattern 1: Standard Deployment (Uniform Partitioning)
```bash
#!/bin/bash
# Start MPS daemon once (system-level or container init)
export CUDA_DEVICE_ORDER=PCI_BUS_ID
export CUDA_MPS_ACTIVE_THREAD_PERCENTAGE=50
nvidia-cuda-mps-control -d
```

```python
# Your application (no env var needed; inherits daemon default)
import pycuda.driver as cuda
cuda.init()
device = cuda.Device(0)
ctx = device.make_context()
# Process gets 50% of threads (set at daemon level)
```

### Pattern 2: Per-Run Dynamic Configuration (Per-Context Partitioning)
```python
import os
os.environ['CUDA_MPS_ENABLE_PER_CTX_DEVICE_MULTIPROCESSOR_PARTITIONING'] = '1'

import pycuda.driver as cuda
cuda.init()
device = cuda.Device(0)

def run_with_allocation(thread_percentage):
    """Create and execute with specific thread allocation."""
    os.environ['CUDA_MPS_ACTIVE_THREAD_PERCENTAGE'] = str(thread_percentage)
    ctx = device.make_context()
    try:
        # Your kernels here
        pass
    finally:
        ctx.pop()

# Multiple runs with different allocations
run_with_allocation(50)   # First run: 50% threads
run_with_allocation(25)   # Second run: 25% threads
run_with_allocation(75)   # Third run: 75% threads
```

### Pattern 3: Verify Configuration (Using nvidia-cuda-mps-control)
```bash
# List all clients and their allocations
nvidia-cuda-mps-control
> get_device_client_list

# Query specific process allocation
get_active_thread_percentage <PID>

# Check daemon default
get_default_active_thread_percentage
```

---

## Verification & Profiling

### Verify MPS Daemon is Running
```bash
nvidia-cuda-mps-control
# If daemon is running, you get an interactive prompt
# If not: "nvidia-cuda-mps-control: error: Daemon not available"
```

### Verify Active Thread Percentage is Applied
```bash
# While your Python process is running:
nvidia-smi
# Look for MPS processes in the output

# More detailed (in another terminal):
nvidia-cuda-mps-control
> get_active_thread_percentage <YOUR_PID>
# Returns the active percentage for your process
```

### Profile Actual SM Utilization
```bash
# nvprof can measure actual SM utilization (what the % constraint affects):
nvprof --metrics smsp_efficiency python your_script.py
```

**Note**: `nvidia-smi` shows kernel execution time, NOT SM partitioning. Use `nvprof` or similar profilers to verify the thread percentage constraint is actually limiting compute.

---

## Summary Table

| Aspect | Answer | Evidence |
|--------|--------|----------|
| **Daemon required?** | YES | CUDA cannot initialize under MPS without active daemon |
| **Env var before context?** | YES (timing depends on level) | Uniform: before process init; Per-context: before each context creation |
| **Per-run config sufficient?** | NO (uniform); YES (per-context opt-in) | Uniform is immutable after first context; per-context allows dynamic changes per new context |
| **Volta+ required?** | YES | Percentage-based partitioning not supported on pre-Volta |
| **Daemon restart clears settings?** | YES | Daemon must be restarted with env var to change daemon-level allocation |

---

## References

- **NVIDIA MPS Documentation**: https://docs.nvidia.com/deploy/mps/
- **CUDA C Programming Guide**: https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html
- **MPS Control Daemon**: https://docs.nvidia.com/deploy/mps/#controlling-mps-via-the-mps-control-daemon
