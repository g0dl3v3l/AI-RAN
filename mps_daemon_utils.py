#!/usr/bin/env python3
"""
MPS Daemon Management Utilities

Provides safe, production-ready lifecycle management for NVIDIA CUDA MPS daemon.
Handles: daemon startup, shutdown, configuration validation, state verification,
and permission/error recovery.

Usage:
    from mps_daemon_utils import MPSDaemonManager
    
    manager = MPSDaemonManager(gpu_device=0)
    manager.start_daemon(active_thread_percentage=50)
    manager.verify_daemon_running()
    manager.stop_daemon()
"""

import os
import sys
import subprocess
import time
import signal
import tempfile
from pathlib import Path
from typing import Tuple, Optional, Dict, List
from dataclasses import dataclass
from enum import Enum


class DaemonState(Enum):
    """MPS daemon operational state."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class DaemonConfig:
    """MPS daemon configuration parameters."""
    gpu_device: int = 0
    active_thread_percentage: int = 50  # 1-100
    enable_per_ctx_partitioning: bool = False
    log_file: Optional[str] = None
    temp_dir: Optional[str] = None
    
    def validate(self) -> Tuple[bool, str]:
        """Validate configuration parameters."""
        if not 1 <= self.active_thread_percentage <= 100:
            return False, f"active_thread_percentage must be 1-100, got {self.active_thread_percentage}"
        if self.gpu_device < 0:
            return False, f"gpu_device must be >= 0, got {self.gpu_device}"
        return True, "Configuration valid"


class MPSDaemonManager:
    """
    Safe lifecycle manager for NVIDIA CUDA MPS daemon.
    
    Handles daemon startup, shutdown, configuration, and state verification.
    Provides error recovery and permission handling.
    """
    
    def __init__(self, gpu_device: int = 0, log_file: Optional[str] = None):
        """
        Initialize MPS daemon manager.
        
        Args:
            gpu_device: GPU device index (default: 0)
            log_file: Optional log file path for daemon output
        """
        self.gpu_device = gpu_device
        self.log_file = log_file or f"/tmp/mps_daemon_gpu{gpu_device}.log"
        self.mps_control_socket = f"/tmp/nvidia-mps/control_{gpu_device}"
        self.daemon_pid = None
        self.state = DaemonState.STOPPED
        
    def _check_prerequisites(self) -> Tuple[bool, str]:
        """Check system prerequisites for MPS operation."""
        # Check nvidia-cuda-mps-control availability
        try:
            result = subprocess.run(
                ["which", "nvidia-cuda-mps-control"],
                capture_output=True,
                timeout=5,
                text=True
            )
            if result.returncode != 0:
                return False, "nvidia-cuda-mps-control not found in PATH"
        except subprocess.TimeoutExpired:
            return False, "Timeout checking for nvidia-cuda-mps-control"
        except Exception as e:
            return False, f"Error checking prerequisites: {e}"
        
        # Check nvidia-smi availability
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=index,name", "--format=csv,noheader"],
                capture_output=True,
                timeout=5,
                text=True
            )
            if result.returncode != 0:
                return False, "nvidia-smi not available or no NVIDIA GPU detected"
            
            # Check if target GPU exists
            output_lines = result.stdout.strip().split('\n')
            if self.gpu_device >= len(output_lines):
                return False, f"GPU device {self.gpu_device} not available (only {len(output_lines)} device(s) found)"
        except subprocess.TimeoutExpired:
            return False, "Timeout checking nvidia-smi"
        except Exception as e:
            return False, f"Error checking GPU availability: {e}"
        
        return True, "Prerequisites satisfied"
    
    def _get_mps_control_path(self) -> str:
        """Get path to nvidia-cuda-mps-control executable."""
        try:
            result = subprocess.run(
                ["which", "nvidia-cuda-mps-control"],
                capture_output=True,
                timeout=5,
                text=True
            )
            return result.stdout.strip()
        except Exception:
            return "nvidia-cuda-mps-control"
    
    def _run_mps_command(self, command: str) -> Tuple[bool, str]:
        """
        Run nvidia-cuda-mps-control command.
        
        Args:
            command: Command to send to mps-control (e.g., "get_device_count")
        
        Returns:
            (success: bool, output: str)
        """
        try:
            # Create environment with CUDA_MPS_PIPE_DIRECTORY set
            env = os.environ.copy()
            env["CUDA_MPS_PIPE_DIRECTORY"] = f"/tmp/nvidia-mps"
            env["CUDA_DEVICE"] = str(self.gpu_device)
            
            mps_control = self._get_mps_control_path()
            
            # Use echo + pipe to send command to mps-control
            proc_echo = subprocess.Popen(
                ["echo", command],
                stdout=subprocess.PIPE,
                env=env
            )
            proc_mps = subprocess.Popen(
                [mps_control],
                stdin=proc_echo.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
                timeout=10
            )
            proc_echo.stdout.close()
            
            stdout, stderr = proc_mps.communicate(timeout=10)
            
            if proc_mps.returncode != 0:
                return False, f"Command failed: {stderr}"
            
            return True, stdout.strip()
        except subprocess.TimeoutExpired:
            return False, f"MPS command timeout: {command}"
        except Exception as e:
            return False, f"Error running MPS command: {e}"
    
    def start_daemon(
        self,
        active_thread_percentage: int = 50,
        enable_per_ctx_partitioning: bool = False,
        timeout: int = 10
    ) -> Tuple[bool, str]:
        """
        Start NVIDIA CUDA MPS daemon with specified configuration.
        
        **CRITICAL**: Environment variables must be set BEFORE daemon startup.
        This function sets them and spawns the daemon.
        
        Args:
            active_thread_percentage: Percentage of SMs available to MPS clients (1-100)
            enable_per_ctx_partitioning: Enable per-context SM partitioning
            timeout: Seconds to wait for daemon startup
        
        Returns:
            (success: bool, message: str)
        """
        # Validate configuration
        config = DaemonConfig(
            gpu_device=self.gpu_device,
            active_thread_percentage=active_thread_percentage,
            enable_per_ctx_partitioning=enable_per_ctx_partitioning,
            log_file=self.log_file
        )
        valid, msg = config.validate()
        if not valid:
            return False, f"Configuration invalid: {msg}"
        
        # Check prerequisites
        prereq_ok, prereq_msg = self._check_prerequisites()
        if not prereq_ok:
            return False, f"Prerequisites not satisfied: {prereq_msg}"
        
        # If daemon already running, stop it first
        if self.state == DaemonState.RUNNING:
            stop_ok, stop_msg = self.stop_daemon()
            if not stop_ok:
                return False, f"Could not stop existing daemon: {stop_msg}"
            time.sleep(1)  # Wait for clean shutdown
        
        try:
            self.state = DaemonState.STARTING
            
            # Create MPS pipe directory if needed
            mps_dir = Path("/tmp/nvidia-mps")
            mps_dir.mkdir(mode=0o777, parents=True, exist_ok=True)
            
            # Set up environment for daemon startup
            env = os.environ.copy()
            env["CUDA_DEVICE"] = str(self.gpu_device)
            env["CUDA_MPS_ACTIVE_THREAD_PERCENTAGE"] = str(active_thread_percentage)
            env["CUDA_MPS_PIPE_DIRECTORY"] = "/tmp/nvidia-mps"
            
            if enable_per_ctx_partitioning:
                env["CUDA_MPS_ENABLE_PER_CTX_DEVICE_MULTIPROCESSOR_PARTITIONING"] = "1"
            
            # Start daemon with -d flag (background)
            mps_control = self._get_mps_control_path()
            
            with open(self.log_file, 'w') as log_fh:
                proc = subprocess.Popen(
                    [mps_control, "-d"],
                    env=env,
                    stdout=log_fh,
                    stderr=log_fh,
                    text=True
                )
            
            self.daemon_pid = proc.pid
            
            # Wait for daemon to be ready
            start_time = time.time()
            while time.time() - start_time < timeout:
                ok, msg = self.verify_daemon_running()
                if ok:
                    self.state = DaemonState.RUNNING
                    return True, f"MPS daemon started successfully on GPU {self.gpu_device} with {active_thread_percentage}% thread allocation"
                time.sleep(0.5)
            
            self.state = DaemonState.ERROR
            return False, f"MPS daemon did not become ready within {timeout}s"
        
        except Exception as e:
            self.state = DaemonState.ERROR
            return False, f"Error starting MPS daemon: {e}"
    
    def stop_daemon(self, timeout: int = 10) -> Tuple[bool, str]:
        """
        Stop running NVIDIA CUDA MPS daemon.
        
        Args:
            timeout: Seconds to wait for daemon shutdown
        
        Returns:
            (success: bool, message: str)
        """
        if self.state == DaemonState.STOPPED:
            return True, "Daemon already stopped"
        
        try:
            self.state = DaemonState.STOPPING
            
            # Send quit command to daemon
            ok, msg = self._run_mps_command("quit")
            
            if not ok:
                # Force kill if graceful shutdown fails
                if self.daemon_pid:
                    try:
                        os.kill(self.daemon_pid, signal.SIGTERM)
                        time.sleep(1)
                    except ProcessLookupError:
                        pass  # Process already terminated
            
            # Verify daemon stopped
            start_time = time.time()
            while time.time() - start_time < timeout:
                ok, msg = self.verify_daemon_running()
                if not ok:
                    self.state = DaemonState.STOPPED
                    self.daemon_pid = None
                    return True, "MPS daemon stopped successfully"
                time.sleep(0.5)
            
            self.state = DaemonState.ERROR
            return False, f"MPS daemon did not stop within {timeout}s"
        
        except Exception as e:
            self.state = DaemonState.ERROR
            return False, f"Error stopping MPS daemon: {e}"
    
    def verify_daemon_running(self) -> Tuple[bool, str]:
        """
        Verify that MPS daemon is currently running.
        
        Returns:
            (success: bool, message: str)
        """
        try:
            ok, msg = self._run_mps_command("get_device_count")
            if ok:
                return True, f"MPS daemon is running: {msg}"
            else:
                return False, f"MPS daemon not responding: {msg}"
        except Exception as e:
            return False, f"Error verifying daemon: {e}"
    
    def get_daemon_status(self) -> Dict[str, str]:
        """
        Get detailed status of running MPS daemon.
        
        Returns:
            Dictionary with daemon status information
        """
        status = {
            "state": self.state.value,
            "gpu_device": str(self.gpu_device),
            "log_file": self.log_file,
            "daemon_pid": str(self.daemon_pid) if self.daemon_pid else "None"
        }
        
        ok, msg = self.verify_daemon_running()
        status["running"] = "Yes" if ok else "No"
        status["status_message"] = msg
        
        if ok:
            ok_dev, msg_dev = self._run_mps_command("get_device_count")
            if ok_dev:
                status["device_count"] = msg_dev
        
        return status
    
    def get_current_config(self) -> Dict[str, str]:
        """
        Get current MPS configuration from environment.
        
        Returns:
            Dictionary with active configuration
        """
        return {
            "CUDA_MPS_ACTIVE_THREAD_PERCENTAGE": os.environ.get("CUDA_MPS_ACTIVE_THREAD_PERCENTAGE", "Not set"),
            "CUDA_MPS_ENABLE_PER_CTX_DEVICE_MULTIPROCESSOR_PARTITIONING": os.environ.get("CUDA_MPS_ENABLE_PER_CTX_DEVICE_MULTIPROCESSOR_PARTITIONING", "Not set"),
            "CUDA_DEVICE": os.environ.get("CUDA_DEVICE", "Not set"),
            "CUDA_MPS_PIPE_DIRECTORY": os.environ.get("CUDA_MPS_PIPE_DIRECTORY", "Not set")
        }
    
    def cleanup(self) -> Tuple[bool, str]:
        """
        Clean up daemon and temporary resources.
        
        Returns:
            (success: bool, message: str)
        """
        # Stop daemon if running
        if self.state == DaemonState.RUNNING:
            ok, msg = self.stop_daemon()
            if not ok:
                return False, f"Could not stop daemon during cleanup: {msg}"
        
        # Clean up log file
        try:
            if Path(self.log_file).exists():
                Path(self.log_file).unlink()
        except Exception as e:
            return False, f"Error cleaning up log file: {e}"
        
        return True, "Cleanup completed successfully"


def main():
    """Command-line interface for MPS daemon management."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="NVIDIA CUDA MPS Daemon Manager"
    )
    parser.add_argument("--device", type=int, default=0, help="GPU device index")
    parser.add_argument("--percentage", type=int, default=50, help="Active thread percentage (1-100)")
    parser.add_argument("--per-ctx", action="store_true", help="Enable per-context partitioning")
    parser.add_argument("--log-file", help="Daemon log file path")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    subparsers.add_parser("start", help="Start MPS daemon")
    subparsers.add_parser("stop", help="Stop MPS daemon")
    subparsers.add_parser("status", help="Get daemon status")
    subparsers.add_parser("verify", help="Verify daemon is running")
    
    args = parser.parse_args()
    
    manager = MPSDaemonManager(gpu_device=args.device, log_file=args.log_file)
    
    if args.command == "start":
        ok, msg = manager.start_daemon(
            active_thread_percentage=args.percentage,
            enable_per_ctx_partitioning=args.per_ctx
        )
        print(f"{'✓' if ok else '✗'} {msg}")
        sys.exit(0 if ok else 1)
    
    elif args.command == "stop":
        ok, msg = manager.stop_daemon()
        print(f"{'✓' if ok else '✗'} {msg}")
        sys.exit(0 if ok else 1)
    
    elif args.command == "status":
        status = manager.get_daemon_status()
        print("\n=== MPS Daemon Status ===")
        for key, value in status.items():
            print(f"{key:30s}: {value}")
        
        print("\n=== Current Configuration ===")
        config = manager.get_current_config()
        for key, value in config.items():
            print(f"{key:50s}: {value}")
    
    elif args.command == "verify":
        ok, msg = manager.verify_daemon_running()
        print(f"{'✓' if ok else '✗'} {msg}")
        sys.exit(0 if ok else 1)
    
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
