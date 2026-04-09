#!/bin/bash

set -euo pipefail

# ===== SCRIPT CONSTANTS =====

SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")") 
REPO_ROOT=$(realpath "${SCRIPT_DIR}/..")
SSHPASS_FILE="/mnt/data/dheeraj/dicertation/.ssh_pass"
REMOTE_USER="netsys"
REMOTE_HOST="dheeraj"
REMOTE_BASE="/home/netsys/dheeraj/inference-profile"

# ===== GLOBAL STATE =====

STAGE="all"
RUN_ID=""
MODELS=()
CHUNK_SIZES=()
SEQUENCE_LENGTHS=()
LDPC_TRACE=""
RAN_CTRL_TRACE=""
GPU_ID=0
DRY_RUN=0

# ===== HELPER FUNCTIONS =====

usage() {
  cat <<'USAGE'
Usage: deploy_and_run_remote.sh [options]

Options:
  --stage {sync,bootstrap,run,fetch,all}   Stage to execute (default: all)
  --run-id <id>                             Run ID (default: auto-generated timestamp)
  --models <model1> [<model2> ...]          Model IDs to profile
  --chunk-sizes <size1> [<size2> ...]       Chunk sizes for profiling
  --sequence-lengths <len1> [<len2> ...]    Sequence lengths for profiling
  --ldpc-trace <path>                       Path to LDPC trace file
  --ran-ctrl-trace <path>                   Path to RAN control trace file
  --gpu-id <id>                             GPU ID on remote (default: 0)
  --dry-run                                 Print redacted commands without executing
  -h, --help                                Show this help

Stages:
  sync      - Upload source code and scripts, preserve runs/
  bootstrap - Bootstrap remote environment
  run       - Execute profiling run on remote
  fetch     - Download artifacts to local machine
  all       - Execute all stages in order (sync → bootstrap → run → fetch)

Examples:
  # Full end-to-end run
  bash deploy_and_run_remote.sh --stage all --run-id exp-001 \
    --models opt-125m opt-350m --chunk-sizes 32 --sequence-lengths 128 256 \
    --ldpc-trace /path/to/ldpc.csv --ran-ctrl-trace /path/to/ran.csv

  # Dry-run to inspect commands
  bash deploy_and_run_remote.sh --stage all --dry-run \
    --run-id exp-001 --models opt-125m --chunk-sizes 32 \
    --sequence-lengths 128 --ldpc-trace /path/to/ldpc.csv \
    --ran-ctrl-trace /path/to/ran.csv

  # Retry fetch after remote completed
  bash deploy_and_run_remote.sh --stage fetch --run-id exp-001

USAGE
}

log() {
  printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"
}

error() {
  printf '[ERROR] %s\n' "$*" >&2
  exit 1
}

redact_sshpass_command() {
  local cmd="$1"
  echo "$cmd" | sed "s|sshpass -f [^ ]*|sshpass -f <redacted>|g"
}

run_remote_command() {
  local remote_cmd="$1"
  local cmd="sshpass -f ${SSHPASS_FILE} ssh -o StrictHostKeyChecking=no ${REMOTE_USER}@${REMOTE_HOST} '${remote_cmd}'"
  
  if [[ ${DRY_RUN} -eq 1 ]]; then
    log "DRY-RUN: $(redact_sshpass_command "$cmd")"
  else
    eval "$cmd"
  fi
}

run_remote_scp() {
  local src="$1"
  local dst="$2"
  local cmd="sshpass -f ${SSHPASS_FILE} scp -o StrictHostKeyChecking=no -r ${src} ${dst}"
  
  if [[ ${DRY_RUN} -eq 1 ]]; then
    log "DRY-RUN: $(redact_sshpass_command "$cmd")"
  else
    eval "$cmd"
  fi
}

# ===== STAGE: SYNC =====

stage_sync() {
  log "Starting sync stage..."
  
  if [[ ${DRY_RUN} -eq 0 ]]; then
    [[ -f "${SSHPASS_FILE}" ]] || error "sshpass file not found: ${SSHPASS_FILE}"
  fi
  
  # Create tar stream of project files (excluding runs/)
  local tar_cmd="tar --exclude=runs --exclude=.git --exclude=__pycache__ --exclude=.pytest_cache -czf - -C '${REPO_ROOT}' ."
  
  # Remote cleanup: remove source/scripts/tests but preserve runs/
  local remote_cleanup="
    set -e
    if [[ -d '${REMOTE_BASE}' ]]; then
      cd '${REMOTE_BASE}'
      rm -rf pyproject.toml README.md inference_profile/ scripts/ tests/
    fi
    mkdir -p '${REMOTE_BASE}'
  "
  
  # Remote extract
  local remote_extract="
    set -e
    cd '${REMOTE_BASE}'
    tar -xzf -
  "
  
  local full_cmd="bash -c '${remote_cleanup}' && ${tar_cmd} | sshpass -f ${SSHPASS_FILE} ssh -o StrictHostKeyChecking=no ${REMOTE_USER}@${REMOTE_HOST} 'bash -c \"${remote_extract}\"'"
  
  if [[ ${DRY_RUN} -eq 1 ]]; then
    log "DRY-RUN: $(redact_sshpass_command "$full_cmd")"
  else
    eval "$full_cmd"
  fi
  
  log "Sync stage completed"
}

# ===== STAGE: BOOTSTRAP =====

stage_bootstrap() {
  log "Starting bootstrap stage..."
  
  local remote_bootstrap_cmd="
    cd '${REMOTE_BASE}' && \
    python -m inference_profile.cli bootstrap-env --output-root '${REMOTE_BASE}/runs/${RUN_ID}'
  "
  
  run_remote_command "$remote_bootstrap_cmd"
  
  log "Bootstrap stage completed"
}

# ===== STAGE: RUN =====

stage_run() {
  log "Starting run stage..."
  
  local models_str=$(printf '"%s" ' "${MODELS[@]}")
  local chunk_sizes_str=$(printf '%s ' "${CHUNK_SIZES[@]}")
  local seq_lengths_str=$(printf '%s ' "${SEQUENCE_LENGTHS[@]}")
  
  local remote_run_cmd="
    cd '${REMOTE_BASE}' && \
    python -m inference_profile.cli run-all \
      --run-root '${REMOTE_BASE}/runs/${RUN_ID}' \
      --models ${models_str} \
      --chunk-sizes ${chunk_sizes_str} \
      --sequence-lengths ${seq_lengths_str} \
      --ldpc-trace '${LDPC_TRACE}' \
      --ran-ctrl-trace '${RAN_CTRL_TRACE}' \
      --gpu-id ${GPU_ID}
  "
  
  run_remote_command "$remote_run_cmd"
  
  log "Run stage completed"
}

# ===== STAGE: FETCH =====

stage_fetch() {
  log "Starting fetch stage..."
  
  local local_run_root="${REPO_ROOT}/runs/${RUN_ID}"
  mkdir -p "${local_run_root}"
  
  # Fetch manifest, logs, checksums
  local remote_source="${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_BASE}/runs/${RUN_ID}/"
  
  run_remote_scp "${remote_source}" "${local_run_root}/"
  
  # Verify bundle locally
  log "Verifying bundle integrity..."
  local verify_cmd="python -m inference_profile.cli verify-bundle --run-root '${local_run_root}'"
  
  if [[ ${DRY_RUN} -eq 0 ]]; then
    if ! cd "${REPO_ROOT}" && eval "$verify_cmd"; then
      log "WARNING: Verification failed, marking fetch_failed in manifest"
      # Mark manifest as fetch_failed if verification fails
      if [[ -f "${local_run_root}/run_manifest.json" ]]; then
        # Update manifest status using Python
        python3 << PYEOF
import json
with open('${local_run_root}/run_manifest.json', 'r') as f:
    manifest = json.load(f)
manifest['status'] = 'fetch_failed'
with open('${local_run_root}/run_manifest.json', 'w') as f:
    json.dump(manifest, f, indent=2)
PYEOF
      fi
      exit 1
    fi
  fi
  
  log "Fetch stage completed"
}

# ===== ARGUMENT PARSING =====

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --stage)
        STAGE="$2"
        shift 2
        ;;
      --run-id)
        RUN_ID="$2"
        shift 2
        ;;
      --models)
        shift
        while [[ $# -gt 0 ]] && [[ "$1" != --* ]]; do
          MODELS+=("$1")
          shift
        done
        ;;
      --chunk-sizes)
        shift
        while [[ $# -gt 0 ]] && [[ "$1" != --* ]]; do
          CHUNK_SIZES+=("$1")
          shift
        done
        ;;
      --sequence-lengths)
        shift
        while [[ $# -gt 0 ]] && [[ "$1" != --* ]]; do
          SEQUENCE_LENGTHS+=("$1")
          shift
        done
        ;;
      --ldpc-trace)
        LDPC_TRACE="$2"
        shift 2
        ;;
      --ran-ctrl-trace)
        RAN_CTRL_TRACE="$2"
        shift 2
        ;;
      --gpu-id)
        GPU_ID="$2"
        shift 2
        ;;
      --dry-run)
        DRY_RUN=1
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        error "Unknown option: $1"
        ;;
    esac
  done
}

# ===== MAIN =====

main() {
  parse_args "$@"
  
  # Auto-generate run-id if not provided
  if [[ -z "${RUN_ID}" ]]; then
    RUN_ID="run-$(date +%s)"
  fi
  
  log "Deploy and Run Remote - RAN Inference Profiling"
  log "Run ID: ${RUN_ID}"
  log "Stage: ${STAGE}"
  
  case "${STAGE}" in
    sync)
      stage_sync
      ;;
    bootstrap)
      stage_bootstrap
      ;;
    run)
      stage_run
      ;;
    fetch)
      stage_fetch
      ;;
    all)
      stage_sync
      stage_bootstrap
      stage_run
      stage_fetch
      ;;
    *)
      error "Unknown stage: ${STAGE}"
      ;;
  esac
  
  log "Stage '${STAGE}' completed successfully"
}

main "$@"
