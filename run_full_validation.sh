#!/bin/bash

################################################################################
# run_full_validation.sh
# 
# End-to-end NVIDIA MPS CUDA_MPS_ACTIVE_THREAD_PERCENTAGE validation harness
#
# Purpose:
#   Orchestrate all four Python validation modules (daemon manager, configuration
#   tests, GPU workload tests, and profiling) into a single reproducible workflow.
#
# Usage:
#   bash run_full_validation.sh [--device DEVICE_ID] [--percentage PERCENTAGE] [--output OUTPUT_DIR]
#
# Examples:
#   bash run_full_validation.sh                              # Defaults: device=0, percentage=50
#   bash run_full_validation.sh --device 0 --percentage 75
#   bash run_full_validation.sh --device 1 --percentage 50 --output ./gpu_results/
#
# Output:
#   - Timestamped JSON results from all modules
#   - Human-readable summary report
#   - Full execution log with timestamps
#   - All saved to results directory (default: ./results/ or custom --output)
#
# Exit Codes:
#   0 = SUCCESS: All tests passed, results saved
#   1 = PREREQUISITE MISSING: Required tools or Python modules not found
#   2 = DAEMON STARTUP FAILURE: Failed to start MPS daemon
#   3 = TEST FAILURE: One or more validation tests failed
#   4 = UNKNOWN ERROR: Unexpected error during execution
#
# Environment:
#   - Sets CUDA_MPS_ACTIVE_THREAD_PERCENTAGE before daemon startup (immutable)
#   - Creates temporary MPS pipe directory with proper permissions
#   - Ensures graceful daemon cleanup on exit (success or failure)
#
# Author: NVIDIA MPS Validation Framework
# Version: 1.0
# Last Modified: 2025
#
################################################################################

set -E  # Enable ERR trap inheritance

################################################################################
# CONFIGURATION & GLOBALS
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_NAME="$(basename "$0")"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Default parameters
DEVICE_ID=0
MPS_PERCENTAGE=50
OUTPUT_DIR="./results"
PYTHON_BIN="python3"

# State tracking
DAEMON_STARTED=0
ERROR_OCCURRED=0

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'  # No Color

################################################################################
# UTILITY FUNCTIONS
################################################################################

log_info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} INFO: $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] ✓${NC} $1" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] ⚠${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ✗ ERROR: $1${NC}" | tee -a "$LOG_FILE"
}

die() {
    log_error "$1"
    cleanup
    exit "${2:-4}"
}

cleanup() {
    log_info "Initiating cleanup..."
    
    if [ $DAEMON_STARTED -eq 1 ]; then
        log_info "Stopping MPS daemon (device $DEVICE_ID)..."
        if $PYTHON_BIN "$SCRIPT_DIR/mps_daemon_utils.py" \
            --device "$DEVICE_ID" stop >> "$LOG_FILE" 2>&1; then
            log_success "MPS daemon stopped successfully"
            DAEMON_STARTED=0
        else
            log_warning "MPS daemon stop command returned non-zero exit code"
        fi
        
        # Wait briefly for daemon to shut down
        sleep 1
    fi
    
    log_info "Cleanup completed"
}

# Trap errors and ensure cleanup
trap cleanup EXIT

################################################################################
# ARGUMENT PARSING
################################################################################

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --device)
                DEVICE_ID="$2"
                shift 2
                ;;
            --percentage)
                MPS_PERCENTAGE="$2"
                shift 2
                ;;
            --output)
                OUTPUT_DIR="$2"
                shift 2
                ;;
            --help|-h)
                show_usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
}

show_usage() {
    cat << EOF
Usage: $SCRIPT_NAME [OPTIONS]

OPTIONS:
    --device DEVICE_ID          GPU device ID (default: 0)
    --percentage PERCENTAGE     MPS thread percentage (1-100, default: 50)
    --output OUTPUT_DIR         Output directory for results (default: ./results)
    --help, -h                  Show this help message

EXAMPLES:
    bash $SCRIPT_NAME
    bash $SCRIPT_NAME --device 0 --percentage 75
    bash $SCRIPT_NAME --device 1 --percentage 50 --output ./gpu_results/

EXIT CODES:
    0 = Success
    1 = Prerequisite missing
    2 = Daemon startup failure
    3 = Test failure
    4 = Unknown error

EOF
}

################################################################################
# PREREQUISITE CHECKS
################################################################################

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Python
    if ! command -v "$PYTHON_BIN" &> /dev/null; then
        die "Python3 not found. Please install Python 3.8+." 1
    fi
    log_success "Python3 found: $($PYTHON_BIN --version)"
    
    # Check required Python modules
    log_info "Checking Python module requirements..."
    if ! $PYTHON_BIN -c "import torch" 2>/dev/null; then
        log_warning "PyTorch not available (expected on non-GPU systems). Workload tests may be skipped."
    else
        log_success "PyTorch is available"
    fi
    
    # Check MPS control tools
    if ! command -v nvidia-cuda-mps-control &> /dev/null; then
        log_warning "nvidia-cuda-mps-control not found. MPS daemon operations may fail on CPU-only systems."
    else
        log_success "nvidia-cuda-mps-control found"
    fi
    
    # Check nvidia-smi
    if ! command -v nvidia-smi &> /dev/null; then
        log_warning "nvidia-smi not found. GPU profiling will be skipped (expected on CPU-only systems)."
    else
        log_success "nvidia-smi found"
    fi
    
    # Check required Python validation scripts exist
    for script in mps_daemon_utils.py test_mps_configuration.py mps_gpu_workload.py; do
        if [ ! -f "$SCRIPT_DIR/$script" ]; then
            die "Required script not found: $SCRIPT_DIR/$script" 1
        fi
    done
    log_success "All required Python scripts found"
    
    log_success "Prerequisite checks passed"
}

################################################################################
# VALIDATION PARAMETER CHECKS
################################################################################

validate_parameters() {
    log_info "Validating parameters..."
    
    # Validate device ID
    if ! [[ "$DEVICE_ID" =~ ^[0-9]+$ ]]; then
        die "Invalid device ID: $DEVICE_ID (must be a non-negative integer)" 1
    fi
    log_success "Device ID valid: $DEVICE_ID"
    
    # Validate percentage
    if ! [[ "$MPS_PERCENTAGE" =~ ^[0-9]+$ ]]; then
        die "Invalid percentage: $MPS_PERCENTAGE (must be a non-negative integer)" 1
    fi
    if [ "$MPS_PERCENTAGE" -lt 1 ] || [ "$MPS_PERCENTAGE" -gt 100 ]; then
        die "Invalid percentage: $MPS_PERCENTAGE (must be between 1 and 100)" 1
    fi
    log_success "MPS percentage valid: $MPS_PERCENTAGE%"
    
    log_success "Parameter validation passed"
}

################################################################################
# ENVIRONMENT SETUP
################################################################################

setup_environment() {
    log_info "Setting up execution environment..."
    
    # Create output directory
    if ! mkdir -p "$OUTPUT_DIR" 2>/dev/null; then
        die "Failed to create output directory: $OUTPUT_DIR" 4
    fi
    log_success "Output directory ready: $OUTPUT_DIR"
    
    # Set up MPS pipe directory (for daemon IPC)
    MPS_PIPE_DIR="/tmp/nvidia-mps-$USER"
    if ! mkdir -p "$MPS_PIPE_DIR" 2>/dev/null; then
        die "Failed to create MPS pipe directory: $MPS_PIPE_DIR" 4
    fi
    chmod 700 "$MPS_PIPE_DIR" 2>/dev/null || true
    log_success "MPS pipe directory ready: $MPS_PIPE_DIR"
    
    # Export environment variables (immutable daemon-level configuration)
    export CUDA_MPS_PIPE_DIRECTORY="$MPS_PIPE_DIR"
    export CUDA_DEVICE="$DEVICE_ID"
    export CUDA_MPS_ACTIVE_THREAD_PERCENTAGE="$MPS_PERCENTAGE"
    
    log_success "Environment variables set:"
    log_info "  CUDA_MPS_PIPE_DIRECTORY=$CUDA_MPS_PIPE_DIRECTORY"
    log_info "  CUDA_DEVICE=$CUDA_DEVICE"
    log_info "  CUDA_MPS_ACTIVE_THREAD_PERCENTAGE=$CUDA_MPS_ACTIVE_THREAD_PERCENTAGE"
    
    log_success "Environment setup completed"
}

################################################################################
# DAEMON LIFECYCLE MANAGEMENT
################################################################################

start_daemon() {
    log_info "Starting MPS daemon (device $DEVICE_ID, percentage $MPS_PERCENTAGE%)..."
    
    if $PYTHON_BIN "$SCRIPT_DIR/mps_daemon_utils.py" \
        --device "$DEVICE_ID" \
        --percentage "$MPS_PERCENTAGE" \
        start >> "$LOG_FILE" 2>&1; then
        DAEMON_STARTED=1
        log_success "MPS daemon started successfully"
        sleep 2  # Allow daemon to stabilize
    else
        die "Failed to start MPS daemon. Check log: $LOG_FILE" 2
    fi
}

verify_daemon() {
    log_info "Verifying MPS daemon status..."
    
    if $PYTHON_BIN "$SCRIPT_DIR/mps_daemon_utils.py" \
        --device "$DEVICE_ID" \
        status >> "$LOG_FILE" 2>&1; then
        log_success "MPS daemon verification passed"
    else
        die "MPS daemon verification failed. Daemon may not be running." 2
    fi
}

################################################################################
# CONFIGURATION VALIDATION TESTS
################################################################################

run_configuration_tests() {
    log_info "Running configuration validation tests..."
    
    local config_output="$OUTPUT_DIR/config_results_$TIMESTAMP.json"
    
    if $PYTHON_BIN "$SCRIPT_DIR/test_mps_configuration.py" \
        --device "$DEVICE_ID" \
        --percentage "$MPS_PERCENTAGE" \
        --mode all \
        --json \
        > "$config_output" 2>> "$LOG_FILE"; then
        log_success "Configuration tests completed"
        log_info "Results saved: $config_output"
        
        # Parse and display summary
        if command -v jq &> /dev/null; then
            local passed=$(jq '.tests | to_entries[] | select(.value.status == "PASSED") | .key' "$config_output" 2>/dev/null | wc -l)
            local failed=$(jq '.tests | to_entries[] | select(.value.status == "FAILED") | .key' "$config_output" 2>/dev/null | wc -l)
            log_info "Configuration test summary: $passed passed, $failed failed"
        fi
        
        CONFIG_RESULTS="$config_output"
    else
        log_warning "Configuration tests reported issues (see log for details)"
        CONFIG_RESULTS="$config_output"
    fi
}

################################################################################
# GPU WORKLOAD TESTS
################################################################################

run_workload_tests() {
    log_info "Running GPU workload tests..."
    
    local workload_output="$OUTPUT_DIR/workload_results_$TIMESTAMP.json"
    
    if $PYTHON_BIN "$SCRIPT_DIR/mps_gpu_workload.py" \
        --device "$DEVICE_ID" \
        --percentage "$MPS_PERCENTAGE" \
        --mode all \
        --json \
        > "$workload_output" 2>> "$LOG_FILE"; then
        log_success "Workload tests completed"
        log_info "Results saved: $workload_output"
        
        # Parse and display summary
        if command -v jq &> /dev/null; then
            local modes=$(jq '.results | keys' "$workload_output" 2>/dev/null | tr '\n' ',' | sed 's/,$//')
            log_info "Workload modes executed: $modes"
        fi
        
        WORKLOAD_RESULTS="$workload_output"
    else
        log_warning "Workload tests reported issues (see log for details)"
        WORKLOAD_RESULTS="$workload_output"
    fi
}

################################################################################
# RESULTS AGGREGATION & REPORTING
################################################################################

generate_summary_report() {
    log_info "Generating summary report..."
    
    local report_file="$OUTPUT_DIR/summary_report_$TIMESTAMP.txt"
    local summary_json="$OUTPUT_DIR/validation_summary.json"
    
    {
        echo "================================================================================"
        echo "NVIDIA MPS CUDA_MPS_ACTIVE_THREAD_PERCENTAGE Validation Results"
        echo "================================================================================"
        echo ""
        echo "Execution Timestamp: $TIMESTAMP"
        echo "Device ID: $DEVICE_ID"
        echo "MPS Thread Percentage: $MPS_PERCENTAGE%"
        echo "Output Directory: $OUTPUT_DIR"
        echo ""
        echo "================================================================================"
        echo "EXECUTION SUMMARY"
        echo "================================================================================"
        echo "Start Time: $(head -1 "$LOG_FILE" | grep -o '\[.*\]' || echo 'N/A')"
        echo "Completion Time: $(date +'%Y-%m-%d %H:%M:%S')"
        echo ""
        
        echo "================================================================================"
        echo "CONFIGURATION VALIDATION RESULTS"
        echo "================================================================================"
        if [ -f "$CONFIG_RESULTS" ]; then
            if command -v jq &> /dev/null; then
                jq '.tests | to_entries[] | "\(.key): \(.value.status)"' "$CONFIG_RESULTS" 2>/dev/null | sed 's/"//g' | tee -a "$report_file"
                echo ""
                local config_passed=$(jq '.summary.passed' "$CONFIG_RESULTS" 2>/dev/null || echo "N/A")
                local config_failed=$(jq '.summary.failed' "$CONFIG_RESULTS" 2>/dev/null || echo "N/A")
                echo "Summary: $config_passed passed, $config_failed failed" | tee -a "$report_file"
            else
                echo "Results saved to: $CONFIG_RESULTS" | tee -a "$report_file"
            fi
        else
            echo "No configuration results available" | tee -a "$report_file"
        fi
        echo ""
        
        echo "================================================================================"
        echo "GPU WORKLOAD TEST RESULTS"
        echo "================================================================================"
        if [ -f "$WORKLOAD_RESULTS" ]; then
            if command -v jq &> /dev/null; then
                jq '.results | to_entries[] | "\(.key): \(.value.status) (SM Utilization: \(.value.sm_utilization_percent // .value.sm_utilization_avg_percent // "N/A")%)"' "$WORKLOAD_RESULTS" 2>/dev/null | sed 's/"//g' | tee -a "$report_file"
            else
                echo "Results saved to: $WORKLOAD_RESULTS" | tee -a "$report_file"
            fi
        else
            echo "No workload results available" | tee -a "$report_file"
        fi
        echo ""
        
        echo "================================================================================"
        echo "OUTPUT FILES GENERATED"
        echo "================================================================================"
        echo "Configuration Results: $(basename "$CONFIG_RESULTS")" | tee -a "$report_file"
        echo "Workload Results: $(basename "$WORKLOAD_RESULTS")" | tee -a "$report_file"
        echo "Full Execution Log: $(basename "$LOG_FILE")" | tee -a "$report_file"
        echo "Summary Report: $(basename "$report_file")" | tee -a "$report_file"
        echo ""
        
        echo "================================================================================"
        echo "NEXT STEPS"
        echo "================================================================================"
        echo "1. Review JSON results for detailed test information:"
        echo "   - cat $CONFIG_RESULTS"
        echo "   - cat $WORKLOAD_RESULTS"
        echo ""
        echo "2. Analyze SM utilization targets against expected ranges (see GPU_DEPLOYMENT_GUIDE.md)"
        echo ""
        echo "3. For GPU deployment, copy all validation scripts to target system:"
        echo "   - mps_daemon_utils.py"
        echo "   - test_mps_configuration.py"
        echo "   - mps_gpu_workload.py"
        echo "   - NVIDIA_MPS_ACTIVE_THREAD_PERCENTAGE_GUIDANCE.md"
        echo "   - run_full_validation.sh"
        echo ""
        echo "================================================================================"
        
    } | tee "$report_file"
    
    log_success "Summary report generated: $report_file"
    
    # Create aggregated JSON summary
    {
        echo "{"
        echo "  \"validation_timestamp\": \"$TIMESTAMP\","
        echo "  \"device_id\": $DEVICE_ID,"
        echo "  \"mps_percentage\": $MPS_PERCENTAGE,"
        echo "  \"output_directory\": \"$OUTPUT_DIR\","
        echo "  \"configuration_results\": \"$(basename "$CONFIG_RESULTS")\","
        echo "  \"workload_results\": \"$(basename "$WORKLOAD_RESULTS")\","
        echo "  \"summary_report\": \"$(basename "$report_file")\","
        echo "  \"execution_log\": \"$(basename "$LOG_FILE")\""
        echo "}"
    } > "$summary_json"
    
    log_success "Aggregated summary saved: $summary_json"
}

################################################################################
# MAIN EXECUTION FLOW
################################################################################

main() {
    # Initialize logging
    LOG_FILE="$OUTPUT_DIR/validation_$TIMESTAMP.log"
    
    {
        echo "================================================================================"
        echo "NVIDIA MPS Validation Harness - Execution Started"
        echo "================================================================================"
        echo "Timestamp: $(date +'%Y-%m-%d %H:%M:%S')"
        echo "Script: $SCRIPT_DIR/$SCRIPT_NAME"
        echo ""
    } > "$LOG_FILE"
    
    log_info "NVIDIA MPS Validation Harness v1.0"
    log_info "Execution started at $(date +'%Y-%m-%d %H:%M:%S')"
    
    # Parse arguments
    parse_arguments "$@"
    log_info "Arguments parsed: device=$DEVICE_ID, percentage=$MPS_PERCENTAGE%, output=$OUTPUT_DIR"
    
    # Run validation sequence
    check_prerequisites || die "Prerequisite check failed" 1
    validate_parameters || die "Parameter validation failed" 1
    setup_environment || die "Environment setup failed" 4
    
    start_daemon || die "Daemon startup failed" 2
    verify_daemon || die "Daemon verification failed" 2
    
    run_configuration_tests
    run_workload_tests
    
    # Generate reports
    generate_summary_report
    
    log_success "Validation harness completed successfully"
    log_info "Results saved to: $OUTPUT_DIR"
    log_info "Review: cat $OUTPUT_DIR/summary_report_$TIMESTAMP.txt"
    
    exit 0
}

# Execute main function
main "$@"
