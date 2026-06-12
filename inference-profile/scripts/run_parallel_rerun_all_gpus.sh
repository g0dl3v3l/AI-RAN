#!/usr/bin/env bash

set -euo pipefail

ROOT="/mnt/data/dheeraj/dicertation/inference-profile"
RUNS_DIR="${ROOT}/runs"
LOGS_BASE="${RUNS_DIR}/parallel_logs"
LDPC_TRACE="/mnt/raid0sata2/netsys/weaver-ext/ran/traces/e2e_2026030418/e2e_20260304_182034_tractor_ran_ctrl/ldpc_trace.csv"
RAN_CTRL_TRACE="/mnt/raid0sata2/netsys/weaver-ext/ran/traces/e2e_2026030418/e2e_20260304_182034_tractor_ran_ctrl/ran_ctrl_trace.csv"
TS="$(date +%Y%m%d-%H%M%S)"
LOG_DIR="${LOGS_BASE}/revised-rerun-${TS}"

mkdir -p "${LOG_DIR}"

run_cmd() {
  local gpu="$1"
  local run_root="$2"
  shift 2
  conda run -n mls python -m inference_profile.cli run-all \
    --run-root "${run_root}" \
    --ldpc-trace "${LDPC_TRACE}" \
    --ran-ctrl-trace "${RAN_CTRL_TRACE}" \
    --sequence-lengths 1024 2048 4096 8192 \
    --gpu-id "${gpu}" \
    --experiment-type ran-dgxspark-v1 \
    "$@"
}

echo "gpu,run_root,pid,exit_code" > "${LOG_DIR}/exit_status.csv"

RUN0="${RUNS_DIR}/revised-rerun-${TS}-g0-opt125m"
RUN1="${RUNS_DIR}/revised-rerun-${TS}-g1-opt350m"
RUN2="${RUNS_DIR}/revised-rerun-${TS}-g2-opt13b-c64-256"
RUN3="${RUNS_DIR}/revised-rerun-${TS}-g3-opt13b-c512-1024"
RUN4="${RUNS_DIR}/revised-rerun-${TS}-g4-opt27b-c64-256"
RUN5="${RUNS_DIR}/revised-rerun-${TS}-g5-opt27b-c512-1024"
RUN6="${RUNS_DIR}/revised-rerun-${TS}-g6-opt67b-c64-256"
RUN7="${RUNS_DIR}/revised-rerun-${TS}-g7-opt67b-c512-1024"

cd "${ROOT}"

run_cmd 0 "${RUN0}" --models facebook/opt-125m --chunk-sizes 64 128 256 512 1024 > "${LOG_DIR}/gpu0.log" 2>&1 & P0=$!
run_cmd 1 "${RUN1}" --models facebook/opt-350m --chunk-sizes 64 128 256 512 1024 > "${LOG_DIR}/gpu1.log" 2>&1 & P1=$!
run_cmd 2 "${RUN2}" --models facebook/opt-1.3b --chunk-sizes 64 128 256 > "${LOG_DIR}/gpu2.log" 2>&1 & P2=$!
run_cmd 3 "${RUN3}" --models facebook/opt-1.3b --chunk-sizes 512 1024 > "${LOG_DIR}/gpu3.log" 2>&1 & P3=$!
run_cmd 4 "${RUN4}" --models facebook/opt-2.7b --chunk-sizes 64 128 256 > "${LOG_DIR}/gpu4.log" 2>&1 & P4=$!
run_cmd 5 "${RUN5}" --models facebook/opt-2.7b --chunk-sizes 512 1024 > "${LOG_DIR}/gpu5.log" 2>&1 & P5=$!
run_cmd 6 "${RUN6}" --models facebook/opt-6.7b --chunk-sizes 64 128 256 > "${LOG_DIR}/gpu6.log" 2>&1 & P6=$!
run_cmd 7 "${RUN7}" --models facebook/opt-6.7b --chunk-sizes 512 1024 > "${LOG_DIR}/gpu7.log" 2>&1 & P7=$!

wait "$P0"; E0=$?; echo "0,${RUN0},${P0},${E0}" | tee -a "${LOG_DIR}/exit_status.csv"
wait "$P1"; E1=$?; echo "1,${RUN1},${P1},${E1}" | tee -a "${LOG_DIR}/exit_status.csv"
wait "$P2"; E2=$?; echo "2,${RUN2},${P2},${E2}" | tee -a "${LOG_DIR}/exit_status.csv"
wait "$P3"; E3=$?; echo "3,${RUN3},${P3},${E3}" | tee -a "${LOG_DIR}/exit_status.csv"
wait "$P4"; E4=$?; echo "4,${RUN4},${P4},${E4}" | tee -a "${LOG_DIR}/exit_status.csv"
wait "$P5"; E5=$?; echo "5,${RUN5},${P5},${E5}" | tee -a "${LOG_DIR}/exit_status.csv"
wait "$P6"; E6=$?; echo "6,${RUN6},${P6},${E6}" | tee -a "${LOG_DIR}/exit_status.csv"
wait "$P7"; E7=$?; echo "7,${RUN7},${P7},${E7}" | tee -a "${LOG_DIR}/exit_status.csv"

echo "LOG_DIR=${LOG_DIR}" | tee -a "${LOG_DIR}/summary.txt"
if [[ $((E0 + E1 + E2 + E3 + E4 + E5 + E6 + E7)) -eq 0 ]]; then
  echo "ALL_JOBS_SUCCEEDED" | tee -a "${LOG_DIR}/summary.txt"
else
  echo "ONE_OR_MORE_JOBS_FAILED" | tee -a "${LOG_DIR}/summary.txt"
  exit 1
fi
