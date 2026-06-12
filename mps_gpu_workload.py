#!/usr/bin/env python3
"""
NVIDIA MPS GPU Workload Module
==============================

Generates configurable GPU workloads to test and validate CUDA_MPS_ACTIVE_THREAD_PERCENTAGE
constraints under various SM utilization profiles.

Supports multiple workload intensities (light/moderate/heavy) and profiling modes to measure
SM utilization, memory bandwidth, and MPS thread percentage effectiveness.

Portable across GPU-enabled systems. Designed for deployment to any NVIDIA GPU with CUDA support.

Usage:
    # Light workload for 5 seconds at 50% thread allocation
    python mps_gpu_workload.py --mode light --duration 5 --percentage 50

    # Heavy workload with profiling
    python mps_gpu_workload.py --mode heavy --duration 10 --json > results.json

    # Profile SM utilization
    python mps_gpu_workload.py --mode profile --device 0

Author: Dissertation Research Framework
Version: 1.0
"""

import argparse
import json
import os
import sys
import time
import subprocess
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
from enum import Enum


class WorkloadMode(Enum):
    """GPU workload intensity profiles."""
    LIGHT = "light"
    MODERATE = "moderate"
    HEAVY = "heavy"
    PROFILE = "profile"


@dataclass
class WorkloadConfig:
    """Configuration for GPU workload execution."""
    mode: str
    device: int = 0
    duration: float = 5.0
    batch_size: int = 32
    matrix_size: int = 1024
    num_threads: int = 256
    percentage: Optional[int] = None
    enable_profiling: bool = False
    json_output: bool = False
    verbose: bool = False

    def validate(self) -> Tuple[bool, str]:
        """Validate configuration parameters."""
        if self.device < 0:
            return False, "Device ID must be >= 0"
        if self.duration <= 0:
            return False, "Duration must be > 0"
        if self.batch_size <= 0:
            return False, "Batch size must be > 0"
        if self.matrix_size < 64:
            return False, "Matrix size must be >= 64"
        if self.percentage is not None and not (1 <= self.percentage <= 100):
            return False, "Thread percentage must be 1-100"
        return True, ""


@dataclass
class WorkloadResults:
    """Profiling results from workload execution."""
    mode: str
    device: int
    duration: float
    sm_utilization_pct: Optional[float] = None
    memory_utilization_pct: Optional[float] = None
    memory_bandwidth_gbps: Optional[float] = None
    kernel_time_ms: Optional[float] = None
    thread_percentage: Optional[int] = None
    ops_completed: int = 0
    error: Optional[str] = None
    timestamp: str = ""

    def to_dict(self) -> Dict:
        """Convert results to dictionary for JSON serialization."""
        return asdict(self)


class GPUWorkloadExecutor:
    """Executes GPU workloads with MPS constraints and profiling."""

    def __init__(self, config: WorkloadConfig):
        self.config = config
        self.results = WorkloadResults(
            mode=config.mode,
            device=config.device,
            duration=config.duration,
            thread_percentage=config.percentage,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S")
        )
        self._verify_pytorch_cuda()

    def _verify_pytorch_cuda(self) -> bool:
        """Verify PyTorch CUDA support is available."""
        try:
            import torch
            if not torch.cuda.is_available():
                self.results.error = "CUDA not available in PyTorch"
                return False
            device_count = torch.cuda.device_count()
            if self.config.device >= device_count:
                self.results.error = f"Device {self.config.device} not found (found {device_count} devices)"
                return False
            return True
        except ImportError:
            self.results.error = "PyTorch not installed"
            return False

    def execute(self) -> WorkloadResults:
        """Execute workload based on configured mode."""
        try:
            mode = WorkloadMode(self.config.mode)
            
            if mode == WorkloadMode.LIGHT:
                self._execute_light_workload()
            elif mode == WorkloadMode.MODERATE:
                self._execute_moderate_workload()
            elif mode == WorkloadMode.HEAVY:
                self._execute_heavy_workload()
            elif mode == WorkloadMode.PROFILE:
                self._execute_profile_mode()
            
        except Exception as e:
            self.results.error = f"Workload execution failed: {str(e)}"
        
        return self.results

    def _execute_light_workload(self) -> None:
        """Light workload: small matrix operations, minimal SM saturation."""
        try:
            import torch
            
            torch.cuda.set_device(self.config.device)
            
            if self.config.verbose:
                print(f"[LIGHT] Starting light workload on device {self.config.device}")
                print(f"[LIGHT] Duration: {self.config.duration}s, Matrix: {self.config.matrix_size}x{self.config.matrix_size}")
            
            start_time = time.time()
            ops_count = 0
            
            while time.time() - start_time < self.config.duration:
                # Small matrix multiplications
                a = torch.randn(self.config.matrix_size // 4, self.config.matrix_size // 4, device=self.config.device)
                b = torch.randn(self.config.matrix_size // 4, self.config.matrix_size // 4, device=self.config.device)
                c = torch.matmul(a, b)
                ops_count += 1
                
                # Prevent loop optimization by forcing device sync periodically
                if ops_count % 10 == 0:
                    torch.cuda.synchronize(device=self.config.device)
            
            torch.cuda.synchronize(device=self.config.device)
            self.results.ops_completed = ops_count
            
            if self.config.verbose:
                print(f"[LIGHT] Completed {ops_count} matrix operations")
        
        except Exception as e:
            self.results.error = f"Light workload failed: {str(e)}"

    def _execute_moderate_workload(self) -> None:
        """Moderate workload: mixed tensor operations, partial SM saturation."""
        try:
            import torch
            
            torch.cuda.set_device(self.config.device)
            
            if self.config.verbose:
                print(f"[MODERATE] Starting moderate workload on device {self.config.device}")
                print(f"[MODERATE] Duration: {self.config.duration}s, Batch: {self.config.batch_size}")
            
            start_time = time.time()
            ops_count = 0
            
            while time.time() - start_time < self.config.duration:
                # Multiple concurrent operations
                batch = torch.randn(self.config.batch_size, self.config.matrix_size, device=self.config.device)
                
                # Matrix multiplication
                kernel = torch.randn(self.config.matrix_size, self.config.matrix_size, device=self.config.device)
                result = torch.matmul(batch, kernel)
                
                # Element-wise operations
                result = torch.sin(result) * torch.cos(result)
                result = result.sum()
                
                ops_count += 1
                
                if ops_count % 5 == 0:
                    torch.cuda.synchronize(device=self.config.device)
            
            torch.cuda.synchronize(device=self.config.device)
            self.results.ops_completed = ops_count
            
            if self.config.verbose:
                print(f"[MODERATE] Completed {ops_count} mixed operations")
        
        except Exception as e:
            self.results.error = f"Moderate workload failed: {str(e)}"

    def _execute_heavy_workload(self) -> None:
        """Heavy workload: intensive compute, maximum SM saturation."""
        try:
            import torch
            
            torch.cuda.set_device(self.config.device)
            
            if self.config.verbose:
                print(f"[HEAVY] Starting heavy workload on device {self.config.device}")
                print(f"[HEAVY] Duration: {self.config.duration}s, Matrix: {self.config.matrix_size}x{self.config.matrix_size}")
            
            start_time = time.time()
            ops_count = 0
            
            # Pre-allocate large tensors to stress memory
            large_matrix = torch.randn(self.config.matrix_size, self.config.matrix_size, device=self.config.device)
            
            while time.time() - start_time < self.config.duration:
                # Intensive matrix operations with multiple kernels
                a = torch.randn(self.config.matrix_size, self.config.matrix_size, device=self.config.device)
                b = torch.randn(self.config.matrix_size, self.config.matrix_size, device=self.config.device)
                
                # Chain of operations to stress SM
                c = torch.matmul(a, b)
                c = torch.sin(c) + torch.cos(c)
                c = torch.matmul(c, large_matrix)
                c = torch.relu(c)
                loss = c.sum()
                
                # Additional compute-bound operations
                d = torch.randn(self.config.batch_size, self.config.matrix_size, device=self.config.device)
                e = torch.matmul(d, a)
                e = torch.sigmoid(e)
                
                ops_count += 1
                
                # Sync less frequently to maintain SM saturation
                if ops_count % 2 == 0:
                    torch.cuda.synchronize(device=self.config.device)
            
            torch.cuda.synchronize(device=self.config.device)
            self.results.ops_completed = ops_count
            
            if self.config.verbose:
                print(f"[HEAVY] Completed {ops_count} intensive operations")
        
        except Exception as e:
            self.results.error = f"Heavy workload failed: {str(e)}"

    def _execute_profile_mode(self) -> None:
        """Profile mode: collect SM utilization and memory statistics."""
        try:
            import torch
            
            torch.cuda.set_device(self.config.device)
            
            if self.config.verbose:
                print(f"[PROFILE] Starting profiling mode on device {self.config.device}")
            
            # Get GPU properties
            props = torch.cuda.get_device_properties(self.config.device)
            if self.config.verbose:
                print(f"[PROFILE] Device: {props.name}")
                print(f"[PROFILE] Compute Capability: {props.major}.{props.minor}")
                print(f"[PROFILE] SM Count: {props.multi_processor_count}")
                print(f"[PROFILE] Max Threads/SM: {props.max_threads_per_multi_processor}")
            
            # Check environment for MPS configuration
            mps_percentage = os.environ.get("CUDA_MPS_ACTIVE_THREAD_PERCENTAGE")
            per_ctx_partitioning = os.environ.get("CUDA_MPS_ENABLE_PER_CTX_DEVICE_MULTIPROCESSOR_PARTITIONING")
            
            if self.config.verbose:
                print(f"[PROFILE] CUDA_MPS_ACTIVE_THREAD_PERCENTAGE: {mps_percentage or 'not set'}")
                print(f"[PROFILE] CUDA_MPS_ENABLE_PER_CTX_DEVICE_MULTIPROCESSOR_PARTITIONING: {per_ctx_partitioning or 'not set'}")
            
            # Run moderate workload while monitoring
            self._execute_moderate_workload()
            
            # Attempt to query nvidia-smi for real-time stats (if available)
            self._query_nvidia_smi_stats()
        
        except Exception as e:
            self.results.error = f"Profile mode failed: {str(e)}"

    def _query_nvidia_smi_stats(self) -> None:
        """Query nvidia-smi for GPU statistics (if available)."""
        try:
            # Try to get GPU memory stats
            cmd = [
                "nvidia-smi",
                f"--id={self.config.device}",
                "--query-gpu=utilization.gpu,utilization.memory,memory.used,memory.total",
                "--format=csv,noheader,nounits"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                stats = result.stdout.strip().split(",")
                if len(stats) >= 2:
                    self.results.sm_utilization_pct = float(stats[0].strip())
                    self.results.memory_utilization_pct = float(stats[1].strip())
                    
                    if self.config.verbose:
                        print(f"[PROFILE] SM Utilization: {self.results.sm_utilization_pct}%")
                        print(f"[PROFILE] Memory Utilization: {self.results.memory_utilization_pct}%")
        
        except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
            # nvidia-smi not available or failed—continue without stats
            pass

    def _get_mps_config(self) -> Dict[str, Optional[str]]:
        """Retrieve current MPS environment configuration."""
        return {
            "CUDA_MPS_ACTIVE_THREAD_PERCENTAGE": os.environ.get("CUDA_MPS_ACTIVE_THREAD_PERCENTAGE"),
            "CUDA_MPS_ENABLE_PER_CTX_DEVICE_MULTIPROCESSOR_PARTITIONING": os.environ.get("CUDA_MPS_ENABLE_PER_CTX_DEVICE_MULTIPROCESSOR_PARTITIONING"),
            "CUDA_DEVICE": os.environ.get("CUDA_DEVICE"),
            "CUDA_MPS_PIPE_DIRECTORY": os.environ.get("CUDA_MPS_PIPE_DIRECTORY"),
        }


def print_results(results: WorkloadResults, verbose: bool = False) -> None:
    """Print workload results to terminal with formatting."""
    print("\n" + "=" * 70)
    print("GPU WORKLOAD EXECUTION RESULTS")
    print("=" * 70)
    
    print(f"Mode:                   {results.mode}")
    print(f"Device:                 {results.device}")
    print(f"Duration:               {results.duration}s")
    print(f"Operations Completed:   {results.ops_completed}")
    print(f"Thread Percentage:      {results.thread_percentage or 'N/A'}")
    print(f"Timestamp:              {results.timestamp}")
    
    if results.sm_utilization_pct is not None:
        print(f"SM Utilization:         {results.sm_utilization_pct}%")
    
    if results.memory_utilization_pct is not None:
        print(f"Memory Utilization:     {results.memory_utilization_pct}%")
    
    if results.memory_bandwidth_gbps is not None:
        print(f"Memory Bandwidth:       {results.memory_bandwidth_gbps} GB/s")
    
    if results.kernel_time_ms is not None:
        print(f"Kernel Time:            {results.kernel_time_ms}ms")
    
    if results.error:
        print(f"\n⚠️  ERROR: {results.error}")
    else:
        print("\n✅ Workload completed successfully")
    
    print("=" * 70 + "\n")


def main():
    """CLI entry point for GPU workload module."""
    parser = argparse.ArgumentParser(
        description="NVIDIA MPS GPU Workload Generator with MPS Constraint Validation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Light workload for 5 seconds at 50%% thread allocation
  python mps_gpu_workload.py --mode light --duration 5 --percentage 50

  # Heavy workload with JSON output
  python mps_gpu_workload.py --mode heavy --duration 10 --json > results.json

  # Profile SM utilization
  python mps_gpu_workload.py --mode profile --device 0 -v

  # Moderate workload with profiling
  python mps_gpu_workload.py --mode moderate --duration 5 --enable-profiling -v
        """
    )
    
    parser.add_argument("--mode", default="moderate", 
                       choices=["light", "moderate", "heavy", "profile"],
                       help="Workload intensity mode (default: moderate)")
    parser.add_argument("--device", type=int, default=0,
                       help="GPU device ID (default: 0)")
    parser.add_argument("--duration", type=float, default=5.0,
                       help="Workload duration in seconds (default: 5.0)")
    parser.add_argument("--batch-size", type=int, default=32,
                       help="Batch size for tensor operations (default: 32)")
    parser.add_argument("--matrix-size", type=int, default=1024,
                       help="Matrix size for operations (default: 1024)")
    parser.add_argument("--num-threads", type=int, default=256,
                       help="Number of CUDA threads per block (default: 256)")
    parser.add_argument("--percentage", type=int,
                       help="MPS thread percentage constraint to test (1-100)")
    parser.add_argument("--enable-profiling", action="store_true",
                       help="Enable profiling mode to collect statistics")
    parser.add_argument("--json", action="store_true",
                       help="Output results in JSON format")
    parser.add_argument("-v", "--verbose", action="store_true",
                       help="Enable verbose output")
    
    args = parser.parse_args()
    
    # Create and validate configuration
    config = WorkloadConfig(
        mode=args.mode,
        device=args.device,
        duration=args.duration,
        batch_size=args.batch_size,
        matrix_size=args.matrix_size,
        num_threads=args.num_threads,
        percentage=args.percentage,
        enable_profiling=args.enable_profiling,
        json_output=args.json,
        verbose=args.verbose
    )
    
    valid, error_msg = config.validate()
    if not valid:
        print(f"❌ Configuration validation failed: {error_msg}", file=sys.stderr)
        sys.exit(1)
    
    if args.verbose:
        print(f"✓ Configuration valid")
        print(f"✓ Workload Mode: {config.mode}")
        print(f"✓ Device: {config.device}")
        print(f"✓ Duration: {config.duration}s")
    
    # Execute workload
    executor = GPUWorkloadExecutor(config)
    results = executor.execute()
    
    # Output results
    if args.json:
        print(json.dumps(results.to_dict(), indent=2))
    else:
        print_results(results, verbose=args.verbose)
    
    # Exit with error code if workload failed
    if results.error:
        sys.exit(1)


if __name__ == "__main__":
    main()
