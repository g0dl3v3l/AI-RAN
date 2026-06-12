#!/bin/bash

set -euo pipefail

# ===== SCRIPT CONSTANTS =====

SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")") 
REPO_ROOT=$(realpath "${SCRIPT_DIR}/..")
SSHPASS_FILE="/mnt/data/dheeraj/dicertation/.ssh_pass"
REMOTE_USER="netsys"
REMOTE_HOST="192.168.1.20"
REMOTE_BASE="/home/netsys/dheeraj/inference-profile"
REMOTE_TARGET="${REMOTE_USER}@${REMOTE_HOST}"

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
  bootstrap - Create the remote run root and bootstrap .venv
  run       - Resume the remote pipeline from validate-traces after bootstrap
  fetch     - Download artifacts to local machine
  all       - Execute sync → bootstrap → run(validate-traces onward) → fetch

Examples:
  # Full end-to-end run
  bash deploy_and_run_remote.sh --stage all --run-id exp-001 \
    --models facebook/opt-125m facebook/opt-350m --chunk-sizes 64 --sequence-lengths 1024 2048 \
    --ldpc-trace /path/to/ldpc.csv --ran-ctrl-trace /path/to/ran.csv

  # Dry-run to inspect commands
  bash deploy_and_run_remote.sh --stage all --dry-run \
    --run-id exp-001 --models facebook/opt-125m --chunk-sizes 64 \
    --sequence-lengths 1024 --ldpc-trace /path/to/ldpc.csv \
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
  echo "$cmd" | sed "s|sshpass -f '[^']*'|sshpass -f <redacted>|g; s|sshpass -f [^ ]*|sshpass -f <redacted>|g"
}

render_command() {
  local rendered
  printf -v rendered '%q ' "$@"
  printf '%s' "${rendered% }"
}

shell_quote() {
  printf '%q' "$1"
}

join_shell_words() {
  local rendered
  printf -v rendered '%q ' "$@"
  printf '%s' "${rendered% }"
}

run_logged_command() {
  if [[ ${DRY_RUN} -eq 1 ]]; then
    log "DRY-RUN: $(redact_sshpass_command "$(render_command "$@")")"
    return 0
  fi
  "$@"
}

ensure_sshpass_ready() {
  if [[ ${DRY_RUN} -eq 1 ]]; then
    return 0
  fi

  [[ -f "${SSHPASS_FILE}" ]] || error "sshpass file not found: ${SSHPASS_FILE}"
  local mode
  mode=$(stat -c '%a' "${SSHPASS_FILE}")
  [[ "${mode}" == "600" ]] || error "sshpass file must have mode 600: ${SSHPASS_FILE}"
}

validate_run_id() {
  [[ "${RUN_ID}" =~ ^[A-Za-z0-9._-]+$ ]] || error "run-id must match ^[A-Za-z0-9._-]+$"
}

run_remote_command() {
  local remote_cmd="$1"
  local remote_shell_cmd="bash -lc $(shell_quote "$remote_cmd")"
  if [[ ${DRY_RUN} -eq 1 ]]; then
    log "DRY-RUN: $(redact_sshpass_command "sshpass -f ${SSHPASS_FILE} ssh -o StrictHostKeyChecking=yes ${REMOTE_TARGET} ${remote_shell_cmd}")"
    log "DRY-RUN REMOTE CMD: ${remote_cmd}"
    return 0
  fi
  sshpass -f "${SSHPASS_FILE}" ssh -o StrictHostKeyChecking=yes "${REMOTE_TARGET}" "${remote_shell_cmd}"
}

run_remote_scp() {
  local src="$1"
  local dst="$2"
  if [[ ${DRY_RUN} -eq 1 ]]; then
    log "DRY-RUN: $(redact_sshpass_command "sshpass -f ${SSHPASS_FILE} scp -o StrictHostKeyChecking=yes -r $(shell_quote "${src}") $(shell_quote "${dst}")")"
    return 0
  fi
  sshpass -f "${SSHPASS_FILE}" scp -o StrictHostKeyChecking=yes -r "${src}" "${dst}"
}

# ===== STAGE: SYNC =====

stage_sync() {
  log "Starting sync stage..."
  ensure_sshpass_ready

  local remote_cleanup="set -e; mkdir -p $(shell_quote "${REMOTE_BASE}"); if [[ -d $(shell_quote "${REMOTE_BASE}") ]]; then cd $(shell_quote "${REMOTE_BASE}"); rm -rf pyproject.toml README.md inference_profile/ scripts/ tests/; fi"
  local remote_extract="set -e; mkdir -p $(shell_quote "${REMOTE_BASE}"); cd $(shell_quote "${REMOTE_BASE}"); tar -xzf -"

  run_remote_command "${remote_cleanup}"

  local ssh_cmd=(sshpass -f "${SSHPASS_FILE}" ssh -o StrictHostKeyChecking=yes "${REMOTE_TARGET}" "bash -lc $(shell_quote "${remote_extract}")")
  if [[ ${DRY_RUN} -eq 1 ]]; then
    log "DRY-RUN: tar --exclude=runs --exclude=.git --exclude=__pycache__ --exclude=.pytest_cache -czf - -C $(shell_quote "${REPO_ROOT}") . | $(redact_sshpass_command "sshpass -f ${SSHPASS_FILE} ssh -o StrictHostKeyChecking=yes ${REMOTE_TARGET} bash -lc $(shell_quote "${remote_extract}")")"
  else
    tar --exclude=runs --exclude=.git --exclude=__pycache__ --exclude=.pytest_cache -czf - -C "${REPO_ROOT}" . | "${ssh_cmd[@]}"
  fi
  
  log "Sync stage completed"
}

# ===== STAGE: BOOTSTRAP =====

stage_bootstrap() {
  log "Starting bootstrap stage..."
  ensure_sshpass_ready

  # Use python3 for bootstrap on remote hosts where 'python' may be unavailable
  local remote_bootstrap_cmd="cd $(shell_quote "${REMOTE_BASE}") && python3 -m inference_profile.cli bootstrap-env --output-root $(shell_quote "${REMOTE_BASE}/runs/${RUN_ID}")"

  run_remote_command "$remote_bootstrap_cmd"
  
  log "Bootstrap stage completed"
}

# ===== STAGE: RUN =====

stage_run() {
  log "Starting run stage..."
  ensure_sshpass_ready

  local models_str
  models_str=$(join_shell_words "${MODELS[@]}")
  local chunk_sizes_str
  chunk_sizes_str=$(join_shell_words "${CHUNK_SIZES[@]}")
  local seq_lengths_str
  seq_lengths_str=$(join_shell_words "${SEQUENCE_LENGTHS[@]}")
  local remote_run_root="${REMOTE_BASE}/runs/${RUN_ID}"
  local remote_manifest_path="${remote_run_root}/run_manifest.json"
  local remote_python="${remote_run_root}/.venv/bin/python"

  local remote_run_cmd="test -x $(shell_quote "${remote_python}") || { printf >&2 'Missing bootstrap virtualenv at %s\\n' $(shell_quote "${remote_python}"); exit 1; }; cd $(shell_quote "${REMOTE_BASE}") && $(shell_quote "${remote_python}") -m inference_profile.cli run-all --run-root $(shell_quote "${remote_run_root}") --models ${models_str} --chunk-sizes ${chunk_sizes_str} --sequence-lengths ${seq_lengths_str} --ldpc-trace $(shell_quote "${LDPC_TRACE}") --ran-ctrl-trace $(shell_quote "${RAN_CTRL_TRACE}") --gpu-id $(shell_quote "${GPU_ID}") --resume-from validate-traces && $(shell_quote "${remote_python}") -c $(shell_quote "import json, pathlib, sys; manifest = json.loads(pathlib.Path(${remote_manifest_path@Q}).read_text(encoding='utf-8')); final_status = manifest.get('final_status'); sys.exit(0 if final_status == 'success' else (sys.stderr.write(f'Remote manifest final_status={final_status!r}') or 1))")"

  run_remote_command "$remote_run_cmd"
  
  log "Run stage completed"
}

# ===== STAGE: FETCH =====

stage_fetch() {
  log "Starting fetch stage..."
  ensure_sshpass_ready

  local local_runs_root="${REPO_ROOT}/runs"
  local local_run_root="${local_runs_root}/${RUN_ID}"
  local local_backup_root="${local_runs_root}/.${RUN_ID}.previous"
  local remote_source="${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_BASE}/runs/${RUN_ID}/."
  mkdir -p "${local_runs_root}"

  if [[ ${DRY_RUN} -eq 1 ]]; then
    run_remote_scp "${remote_source}" "${local_run_root}/"
    log "Fetch stage completed"
    return
  fi

  local local_fetch_root
  local_fetch_root=$(mktemp -d "${local_runs_root}/.${RUN_ID}.fetch.XXXXXX")

  run_remote_scp "${remote_source}" "${local_fetch_root}/"

  rm -rf "${local_backup_root}"
  if [[ -e "${local_run_root}" ]]; then
    mv "${local_run_root}" "${local_backup_root}"
  fi
  mv "${local_fetch_root}" "${local_run_root}"

  log "Verifying bundle integrity..."
  if ! (cd "${REPO_ROOT}" && python -m inference_profile.cli verify-bundle --run-root "${local_run_root}"); then
    log "WARNING: Verification failed; preserving fetched bundle for inspection"
    exit 1
  fi

  rm -rf "${local_backup_root}"

  log "Fetch stage completed"
}

validate_args() {
  validate_run_id
  case "${STAGE}" in
    run|all)
      [[ ${#MODELS[@]} -gt 0 ]] || error "--models is required for stage ${STAGE}"
      [[ ${#CHUNK_SIZES[@]} -gt 0 ]] || error "--chunk-sizes is required for stage ${STAGE}"
      [[ ${#SEQUENCE_LENGTHS[@]} -gt 0 ]] || error "--sequence-lengths is required for stage ${STAGE}"
      [[ -n "${LDPC_TRACE}" ]] || error "--ldpc-trace is required for stage ${STAGE}"
      [[ -n "${RAN_CTRL_TRACE}" ]] || error "--ran-ctrl-trace is required for stage ${STAGE}"
      ;;
  esac
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
  validate_args
  
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
