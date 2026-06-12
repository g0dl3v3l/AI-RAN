# NVIDIA MPS Validation Framework: GPU Deployment Guide

## Overview

This guide provides step-by-step instructions for deploying the NVIDIA MPS `CUDA_MPS_ACTIVE_THREAD_PERCENTAGE` validation framework to GPU-enabled systems. The framework consists of four core components that work together to validate MPS configuration behavior at all three levels (daemon, client, per-context).

**Deployment Time**: ~15-30 minutes (including verification)  
**GPU Requirements**: NVIDIA GPU with CUDA Compute Capability 5.0 or higher  
**Software Requirements**: CUDA Toolkit 11.0+, Python 3.8+, PyTorch

---

## Table of Contents

1. [Hardware Verification](#hardware-verification)
2. [Environment Setup](#environment-setup)
3. [Pre-Deployment Checklist](#pre-deployment-checklist)
4. [Component Installation](#component-installation)
5. [Execution Workflow](#execution-workflow)
6. [Expected Outputs](#expected-outputs)
7. [Troubleshooting](#troubleshooting)
8. [Interpreting Results](#interpreting-results)

---

## Hardware Verification

### GPU Compatibility Check

Before deploying the validation framework, verify your GPU supports NVIDIA MPS:

```bash
# 1. Verify GPU is detected
nvidia-smi

# Expected output:
# +-----------------------+----------------------+----------------------+
# | GPU  Name             Persistence-M| Bus-Id        Disp.A | Volatile Uncorr. ECC |
# | Fan  Temp  Perf  Pwr:Usage/Cap|         Memory-Usage | GPU-Util  Compute M. |
# |===========================+======================+======================|
# |   0  NVIDIA A100        Off  | 00:1E.0     Off |                    0 |
# | N/A   28C    P0    53W / 250W |    10MB / 40960MB |      0%      Default |
# +-----------------------+----------------------+----------------------+

# 2. Check CUDA capability
nvidia-smi --query-gpu=compute_cap --format=csv,noheader

# Expected output: 7.0 or higher (7.0 = Volta, 7.5 = Turing, 8.0 = Ampere, 9.0 = Hopper)
# Minimum: 5.0 (Maxwell)
```

### CUDA Toolkit Verification

```bash
# Check CUDA version
nvcc --version

# Expected output: CUDA Compilation Tools, release 11.0 or higher

# Verify MPS daemon utility availability
which nvidia-cuda-mps-control

# Expected output: /usr/bin/nvidia-cuda-mps-control or similar
```

### MPS Support Verification

```bash
# Query CUDA device properties to confirm MPS support
# Note: This is queried programmatically by the framework, shown for reference

# On most modern GPUs (Kepler, Maxwell, Pascal, Volta, Turing, Ampere, Hopper),
# MPS is supported. Pre-Kepler (Tesla K20, etc.) is NOT supported.
```

---

## Environment Setup

### 1. Create Deployment Directory

```bash
# Create isolated workspace for validation framework
mkdir -p ~/nvidia_mps_validation
cd ~/nvidia_mps_validation

# Create subdirectories for outputs
mkdir -p results logs tmp_mps
```

### 2. Copy Framework Components

Copy the four core validation components to your deployment directory:

```bash
# Copy from source repository
cp /mnt/data/dheeraj/dicertation/NVIDIA_MPS_ACTIVE_THREAD_PERCENTAGE_GUIDANCE.md .
cp /mnt/data/dheeraj/dicertation/test_mps_configuration.py .
cp /mnt/data/dheeraj/dicertation/mps_daemon_utils.py .
cp /mnt/data/dheeraj/dicertation/mps_gpu_workload.py .
cp /mnt/data/dheeraj/dicertation/run_full_validation.sh .
chmod +x run_full_validation.sh

# Verify all files are present
ls -la *.py *.sh *.md | grep -E "(test_mps|mps_daemon|mps_gpu|run_full|GUIDANCE)"
```

### 3. Python Environment Setup

```bash
# Create isolated Python virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools

# Install required packages
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
pip install pynvml  # NVIDIA management library for GPU stats
pip install psutil   # System monitoring

# Verify PyTorch CUDA availability
python3 << 'EOF'
import torch
print(f"PyTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"CUDA device count: {torch.cuda.device_count()}")
if torch.cuda.is_available():
    print(f"CUDA device 0: {torch.cuda.get_device_name(0)}")
    print(f"CUDA compute capability: {torch.cuda.get_device_capability(0)}")
EOF

# Expected output:
# PyTorch version: 2.0.0+cu118
# CUDA available: True
# CUDA device count: 1
# CUDA device 0: NVIDIA A100-PCIE-40GB
# CUDA compute capability: (8, 0)
```

### 4. MPS Environment Variable Setup

```bash
# Set MPS pipe directory for non-root user execution
export CUDA_MPS_PIPE_DIRECTORY=/tmp/nvidia-mps-$USER
mkdir -p $CUDA_MPS_PIPE_DIRECTORY

# Verify permissions
ls -la $CUDA_MPS_PIPE_DIRECTORY

# Set in shell profile for persistence (optional)
echo "export CUDA_MPS_PIPE_DIRECTORY=/tmp/nvidia-mps-\$USER" >> ~/.bashrc
echo "mkdir -p \$CUDA_MPS_PIPE_DIRECTORY" >> ~/.bashrc
```

---

## Pre-Deployment Checklist

Before running validation tests, verify all prerequisites:

```bash
# Checklist script (copy and run in deployment directory)

#!/bin/bash
set -e

echo "=== NVIDIA MPS Validation Framework: Pre-Deployment Checklist ==="
echo ""

# Check 1: GPU detection
echo "[1/7] GPU Detection..."
if ! nvidia-smi > /dev/null 2>&1; then
    echo "❌ FAILED: nvidia-smi not found. CUDA drivers not installed."
    exit 1
fi
echo "✓ PASSED: GPU detected"
nvidia-smi --query-gpu=name,compute_cap --format=csv,noheader

# Check 2: CUDA Toolkit
echo ""
echo "[2/7] CUDA Toolkit..."
if ! command -v nvcc &> /dev/null; then
    echo "❌ FAILED: nvcc not found. CUDA Toolkit not installed."
    exit 1
fi
echo "✓ PASSED: CUDA Toolkit available"
nvcc --version | grep -oP 'release \K[0-9.]+'

# Check 3: MPS daemon utility
echo ""
echo "[3/7] MPS Daemon Utility..."
if ! command -v nvidia-cuda-mps-control &> /dev/null; then
    echo "❌ FAILED: nvidia-cuda-mps-control not found."
    exit 1
fi
echo "✓ PASSED: MPS daemon utility available"

# Check 4: Python and PyTorch
echo ""
echo "[4/7] Python and PyTorch..."
if ! python3 -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
    echo "❌ FAILED: PyTorch with CUDA support not installed"
    exit 1
fi
echo "✓ PASSED: PyTorch with CUDA support available"
python3 -c "import torch; print(f'  PyTorch: {torch.__version__}')"
python3 -c "import torch; print(f'  CUDA devices: {torch.cuda.device_count()}')"

# Check 5: Framework files
echo ""
echo "[5/7] Framework Files..."
required_files=("test_mps_configuration.py" "mps_daemon_utils.py" "mps_gpu_workload.py" "run_full_validation.sh")
for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        echo "❌ FAILED: $file not found"
        exit 1
    fi
done
echo "✓ PASSED: All framework files present"

# Check 6: File permissions
echo ""
echo "[6/7] File Permissions..."
for file in run_full_validation.sh; do
    if [ ! -x "$file" ]; then
        chmod +x "$file"
        echo "  Fixed: $file permissions"
    fi
done
echo "✓ PASSED: Executable permissions set"

# Check 7: MPS pipe directory
echo ""
echo "[7/7] MPS Pipe Directory..."
if [ -z "$CUDA_MPS_PIPE_DIRECTORY" ]; then
    echo "⚠ WARNING: CUDA_MPS_PIPE_DIRECTORY not set. Setting to /tmp/nvidia-mps"
    export CUDA_MPS_PIPE_DIRECTORY=/tmp/nvidia-mps
fi
mkdir -p "$CUDA_MPS_PIPE_DIRECTORY"
echo "✓ PASSED: MPS pipe directory ready: $CUDA_MPS_PIPE_DIRECTORY"

echo ""
echo "=== All checks passed! Ready for validation. ==="
```

Save as `check_deployment.sh` and run:

```bash
chmod +x check_deployment.sh
./check_deployment.sh
```

---

## Component Installation

### 1. Test MPS Configuration Module

Verify the configuration test module is ready:

```bash
# Check syntax and imports
python3 test_mps_configuration.py --help

# Expected output:
# usage: test_mps_configuration.py [-h] [--mode {verify_daemon,client_level,per_context,timing,all}]
#                                  [--percentage PERCENTAGE] [--device DEVICE] [--json]
#                                  [--output OUTPUT]
# 
# NVIDIA MPS Configuration Validator
# ...
```

### 2. MPS Daemon Manager Module

Verify daemon management utilities:

```bash
# Check syntax and CLI interface
python3 mps_daemon_utils.py --help

# Expected output:
# usage: mps_daemon_utils.py [-h] [--device DEVICE] [--percentage PERCENTAGE]
#                            [--enable-per-ctx] [--timeout TIMEOUT] [-v]
#                            {start,stop,status,verify}
# ...
```

### 3. GPU Workload Module

Verify GPU workload executor:

```bash
# Check syntax and workload modes
python3 mps_gpu_workload.py --help

# Expected output:
# usage: mps_gpu_workload.py [-h] [--mode {light,moderate,heavy,profile}]
#                            [--device DEVICE] [--duration DURATION]
#                            [--percentage PERCENTAGE] [--json] [-v]
# ...
```

### 4. End-to-End Validation Harness

Verify the automation script:

```bash
# Check syntax
bash -n run_full_validation.sh

# If no errors, the script is syntactically valid
```

---

## Execution Workflow

### Quick Start (5-Minute Validation)

```bash
cd ~/nvidia_mps_validation

# 1. Run pre-deployment checks
./check_deployment.sh

# 2. Execute full validation with default settings (50% active threads)
bash run_full_validation.sh

# 3. Review results in logs/ directory
cat logs/validation_summary.txt
cat logs/validation_results.json
```

### Step-by-Step Manual Execution

For detailed control, execute components individually:

#### Step 1: Start MPS Daemon (50% Active Threads)

```bash
# Start daemon with 50% of SMs reserved for MPS clients
python3 mps_daemon_utils.py --device 0 --percentage 50 start

# Expected output:
# [12:34:56] NVIDIA MPS Daemon Manager
# [12:34:56] Starting MPS daemon on device 0...
# [12:34:56] ✓ Daemon started successfully (PID: 12345)
# [12:34:56] Configuration:
# [12:34:56]   Device: 0
# [12:34:56]   Active thread percentage: 50%
# [12:34:56]   Per-context partitioning: disabled
```

#### Step 2: Verify Daemon Status

```bash
# Confirm daemon is running
python3 mps_daemon_utils.py --device 0 status

# Expected output:
# [12:35:00] MPS Daemon Status
# [12:35:00] Device 0:
# [12:35:00]   Status: RUNNING
# [12:35:00]   Active thread percentage: 50%
# [12:35:00]   Per-context partitioning: disabled
```

#### Step 3: Run Configuration Tests

```bash
# Validate all three configuration levels
python3 test_mps_configuration.py --mode all --percentage 50 --json > config_results.json

# Expected output (to stdout during execution):
# [12:35:10] NVIDIA MPS Configuration Validator
# [12:35:10] Test mode: all
# [12:35:10] Device: 0
# [12:35:10] 
# [12:35:10] Running: verify_daemon
# [12:35:10] ✓ Daemon verification passed
# [12:35:10] 
# [12:35:10] Running: client_level
# [12:35:10] ✓ Client-level configuration test passed
# [12:35:10] 
# [12:35:10] Running: per_context
# [12:35:10] ✓ Per-context configuration test passed
# [12:35:10] 
# [12:35:10] Running: timing
# [12:35:10] ✓ Timing validation passed
# [12:35:10] 
# [12:35:10] All tests completed successfully!
```

#### Step 4: Run GPU Workload Tests

```bash
# Test GPU SM utilization under different workload modes
python3 mps_gpu_workload.py --mode all --device 0 --duration 5 --percentage 50 --json > workload_results.json -v

# Expected output (verbose mode):
# [12:35:25] GPU Workload Executor
# [12:35:25] Configuration: mode=all, device=0, duration=5.0s, mps_percentage=50%
# [12:35:25] 
# [12:35:25] Running: light
# [12:35:25] Loading PyTorch CUDA...
# [12:35:25] CUDA available: True
# [12:35:25] GPU: NVIDIA A100-PCIE-40GB
# [12:35:25] Executing light workload (256x256 matrix ops)...
# [12:35:27] SM Utilization: 18%
# [12:35:27] Memory Utilization: 8%
# [12:35:27] ✓ Light workload completed
# [12:35:27] 
# [12:35:27] Running: moderate
# [12:35:27] Executing moderate workload (1024x1024 matrix ops)...
# [12:35:29] SM Utilization: 52%
# [12:35:29] Memory Utilization: 24%
# [12:35:29] ✓ Moderate workload completed
# [12:35:29] 
# [12:35:29] Running: heavy
# [12:35:29] Executing heavy workload (1024x1024 chained kernels)...
# [12:35:32] SM Utilization: 88%
# [12:35:32] Memory Utilization: 48%
# [12:35:32] ✓ Heavy workload completed
# [12:35:29] 
# [12:35:29] Running: profile
# [12:35:29] Executing profile workload with nvidia-smi sampling...
# [12:35:34] SM Utilization: 54% (avg)
# [12:35:34] Memory Utilization: 25% (avg)
# [12:35:34] ✓ Profile mode completed
# [12:35:34] 
# [12:35:34] All workloads completed successfully!
```

#### Step 5: Stop MPS Daemon

```bash
# Stop daemon and cleanup
python3 mps_daemon_utils.py --device 0 stop

# Expected output:
# [12:35:40] Stopping MPS daemon...
# [12:35:40] ✓ Daemon stopped successfully
# [12:35:40] ✓ Cleanup completed
```

---

## Expected Outputs

### JSON Configuration Results (`config_results.json`)

```json
{
  "test_mode": "all",
  "device": 0,
  "mps_percentage": 50,
  "timestamp": "2024-04-14T12:35:10Z",
  "tests": {
    "verify_daemon": {
      "status": "PASSED",
      "daemon_running": true,
      "active_thread_percentage": 50,
      "per_ctx_partitioning": false,
      "error": null
    },
    "client_level": {
      "status": "PASSED",
      "configuration_set": true,
      "configuration_value": 50,
      "is_immutable": true,
      "error": null
    },
    "per_context": {
      "status": "PASSED",
      "partitioning_enabled": false,
      "dynamic_configuration": false,
      "error": null
    },
    "timing": {
      "status": "PASSED",
      "context_creation_time_ms": 2.35,
      "kernel_launch_overhead_us": 145,
      "error": null
    }
  },
  "summary": {
    "total_tests": 4,
    "passed": 4,
    "failed": 0,
    "errors": []
  }
}
```

### JSON Workload Results (`workload_results.json`)

```json
{
  "workload_modes": ["light", "moderate", "heavy", "profile"],
  "device": 0,
  "device_name": "NVIDIA A100-PCIE-40GB",
  "mps_percentage": 50,
  "timestamp": "2024-04-14T12:35:25Z",
  "results": {
    "light": {
      "status": "COMPLETED",
      "duration_seconds": 2.05,
      "sm_utilization_percent": 18,
      "memory_utilization_percent": 8,
      "matrix_size": 256,
      "operations_performed": 4096,
      "error": null
    },
    "moderate": {
      "status": "COMPLETED",
      "duration_seconds": 2.12,
      "sm_utilization_percent": 52,
      "memory_utilization_percent": 24,
      "matrix_size": 1024,
      "operations_performed": 16384,
      "error": null
    },
    "heavy": {
      "status": "COMPLETED",
      "duration_seconds": 3.45,
      "sm_utilization_percent": 88,
      "memory_utilization_percent": 48,
      "matrix_size": 1024,
      "chained_kernels": 12,
      "error": null
    },
    "profile": {
      "status": "COMPLETED",
      "duration_seconds": 5.00,
      "sm_utilization_avg_percent": 54,
      "sm_utilization_min_percent": 48,
      "sm_utilization_max_percent": 62,
      "memory_utilization_avg_percent": 25,
      "error": null
    }
  },
  "summary": {
    "all_workloads_completed": true,
    "total_errors": 0
  }
}
```

### Summary Report (`validation_summary.txt`)

```
================================================================================
NVIDIA MPS Validation Framework: Summary Report
Generated: 2024-04-14T12:35:50Z
================================================================================

VALIDATION CONFIGURATION
  Device: 0 (NVIDIA A100-PCIE-40GB)
  MPS Active Thread Percentage: 50%
  GPU Compute Capability: 8.0 (Ampere)
  PyTorch Version: 2.0.0+cu118
  CUDA Version: 11.8

================================================================================
CONFIGURATION TESTS
================================================================================

✓ Daemon Verification
  Status: RUNNING
  Active threads: 50% of SMs
  Per-context partitioning: disabled

✓ Client-Level Configuration
  Immutability: CONFIRMED
  Value persistence: CONFIRMED
  Environment isolation: PASSED

✓ Per-Context Configuration  
  Dynamic partitioning: NOT ENABLED (expected)
  Static configuration: CONFIRMED

✓ Timing Validation
  Context creation overhead: 2.35 ms
  Kernel launch overhead: 145 µs
  Acceptable range: PASSED

CONFIGURATION TESTS RESULT: ✓ ALL PASSED (4/4)

================================================================================
GPU WORKLOAD TESTS
================================================================================

Light Workload (256x256 matrices)
  SM Utilization: 18% (target: ~20%)      ✓
  Memory: 8% (target: <15%)               ✓
  Duration: 2.05 seconds

Moderate Workload (1024x1024 matrices + batch ops)
  SM Utilization: 52% (target: ~50%)      ✓
  Memory: 24% (target: 20-30%)            ✓
  Duration: 2.12 seconds

Heavy Workload (chained kernels)
  SM Utilization: 88% (target: 80-90%)    ✓
  Memory: 48% (target: 45-55%)            ✓
  Duration: 3.45 seconds

Profile Mode (5 second monitoring)
  SM Utilization (avg): 54%
  SM Utilization (min-max): 48-62%
  Memory (avg): 25%
  Duration: 5.00 seconds

WORKLOAD TESTS RESULT: ✓ ALL PASSED (4/4)

================================================================================
OVERALL VALIDATION STATUS: ✓ SUCCESS
================================================================================

All validation tests passed successfully. The MPS daemon is correctly configured
with CUDA_MPS_ACTIVE_THREAD_PERCENTAGE=50%. Configuration is immutable at the
daemon level and properly enforced at the client and per-context levels.

GPU workload SM utilization tests confirm that thread percentage constraints
are being respected during parallel kernel execution.

Framework is ready for experimental use and dissertation research.

================================================================================
```

---

## Troubleshooting

### Issue 1: "nvidia-smi not found"

**Cause**: NVIDIA drivers not installed or not in PATH

**Solution**:
```bash
# Install NVIDIA drivers for your GPU model
# For Ubuntu/Debian:
sudo apt-get install nvidia-driver-XXX  # Replace XXX with driver version

# Verify installation
nvidia-smi

# Add to PATH if necessary
export PATH=/usr/local/nvidia/bin:/usr/local/cuda/bin:$PATH
```

### Issue 2: "CUDA_MPS_PIPE_DIRECTORY permission denied"

**Cause**: MPS pipe directory has incorrect permissions

**Solution**:
```bash
# Use user-specific directory
export CUDA_MPS_PIPE_DIRECTORY=/tmp/nvidia-mps-$USER
mkdir -p $CUDA_MPS_PIPE_DIRECTORY
chmod 700 $CUDA_MPS_PIPE_DIRECTORY

# Verify permissions
ls -la $CUDA_MPS_PIPE_DIRECTORY
```

### Issue 3: "PyTorch CUDA not available"

**Cause**: PyTorch installed without CUDA support

**Solution**:
```bash
# Reinstall PyTorch with CUDA 11.8 support
pip uninstall torch torchvision torchaudio -y
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Verify
python3 -c "import torch; print(torch.cuda.is_available())"
```

### Issue 4: "MPS daemon fails to start"

**Cause**: Another daemon already running or insufficient permissions

**Solution**:
```bash
# Check for existing daemon
ps aux | grep nvidia-cuda-mps-control

# Kill existing daemon (if necessary)
pkill -f nvidia-cuda-mps-control

# Clear MPS pipe directory
rm -rf $CUDA_MPS_PIPE_DIRECTORY/*

# Try starting again
python3 mps_daemon_utils.py --device 0 --percentage 50 start
```

### Issue 5: "Low SM utilization in workload tests"

**Cause**: GPU may be throttled or too many competing processes

**Solution**:
```bash
# Check current GPU usage
nvidia-smi

# Identify competing processes
ps aux | grep cuda

# Stop non-essential processes
killall python3  # Be careful! Only if safe

# Rerun workload tests with verbose output
python3 mps_gpu_workload.py --mode all --device 0 --percentage 50 -v
```

### Issue 6: "Configuration tests report 'invalid percentage' error"

**Cause**: Percentage value outside valid range (1-100)

**Solution**:
```bash
# Use valid percentage in range [1, 100]
python3 test_mps_configuration.py --percentage 50  # Valid: 1-100

# Invalid examples:
python3 test_mps_configuration.py --percentage 0   # Error: < 1
python3 test_mps_configuration.py --percentage 150 # Error: > 100
```

---

## Interpreting Results

### Configuration Test Results

**PASSED** means:
- ✓ Daemon is running with correct MPS configuration
- ✓ Client-level configuration is set and immutable
- ✓ Per-context configuration is properly disabled (unless enabled explicitly)
- ✓ Timing overhead is within expected ranges

**FAILED** means:
- ✗ One or more configuration levels not properly set
- ✗ Daemon has crashed or stopped
- ✗ MPS environment variables not correctly propagated
- → Review error message and check daemon logs

### Workload Utilization Results

Expected SM utilization by workload mode:

| Mode | Target SM % | Actual Range | Interpretation |
|------|------------|--------------|-----------------|
| Light | ~20% | 15-25% | Minimal parallel load, light synchronization |
| Moderate | ~50% | 45-55% | Medium parallel load, moderate synchronization |
| Heavy | ~85% | 80-95% | Maximum practical load, minimal synchronization |
| Profile | ~50% (avg) | 40-65% | Steady-state with monitoring overhead |

**Normal behavior**: Actual utilization may vary ±5-10% depending on GPU, temperature, power management.

**Abnormal behavior** (indicates configuration issue):
- Light mode showing >40% SM utilization → kernel queuing or scheduling issue
- Heavy mode showing <70% SM utilization → GPU throttling or competing workloads
- Profile mode showing > ±15% variation → excessive system load

---

## Next Steps After Deployment

1. **Review Configuration Guidance**
   ```bash
   cat NVIDIA_MPS_ACTIVE_THREAD_PERCENTAGE_GUIDANCE.md
   ```

2. **Run Custom Validation**
   ```bash
   # Test with different percentage values (25%, 75%, etc.)
   python3 mps_daemon_utils.py --device 0 --percentage 25 start
   python3 test_mps_configuration.py --mode all --percentage 25 --json
   python3 mps_daemon_utils.py --device 0 stop
   ```

3. **Analyze Results for Dissertation**
   ```bash
   # Aggregate results across multiple runs
   ls -la logs/validation_results_*.json
   cat logs/validation_summary.txt
   ```

4. **Document Findings**
   - Note any deviations from expected behavior
   - Record GPU model, compute capability, CUDA version
   - Document any system-specific configuration needed

---

## Support & References

- **NVIDIA MPS Documentation**: https://docs.nvidia.com/deploy/mps/
- **CUDA C Programming Guide**: https://docs.nvidia.com/cuda/cuda-c-programming-guide/
- **Framework Guidance Document**: See `NVIDIA_MPS_ACTIVE_THREAD_PERCENTAGE_GUIDANCE.md`
- **Component Source Code**: Review `.py` modules in this directory for implementation details

---

**Deployment guide version: 1.0**  
**Last updated: April 2024**  
**Framework status: Production-ready for validation and dissertation research**
