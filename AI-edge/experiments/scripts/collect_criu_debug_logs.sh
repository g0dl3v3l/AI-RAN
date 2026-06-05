#!/usr/bin/env bash
# Collect Docker/CRIU checkpoint-restore debug evidence for AI-edge V0.
#
# Usage:
#   bash experiments/scripts/collect_criu_debug_logs.sh [SINCE] [OUT_DIR]
#
# Examples:
#   bash experiments/scripts/collect_criu_debug_logs.sh
#   bash experiments/scripts/collect_criu_debug_logs.sh "2 hours ago" /tmp/criu-debug-logs
#   bash experiments/scripts/collect_criu_debug_logs.sh "2026-06-05 14:00:00" /tmp/criu-debug-logs
#
# Notes:
# - This script is evidence collection only. It does not restart Docker or delete containers.
# - Some files require sudo because Docker's data-root is root-owned.
# - Run before restarting Docker/containerd, otherwise useful evidence can disappear.

set -u

SINCE="${1:-2 hours ago}"
OUT_DIR="${2:-/tmp/criu-debug-logs-$(date +%Y%m%d-%H%M%S)}"
PER_CONTAINER_TIMEOUT_S="${CRIU_DEBUG_PER_CONTAINER_TIMEOUT_S:-3}"
MAX_CONTAINERS="${CRIU_DEBUG_MAX_CONTAINERS:-12}"
ARCHIVE="${OUT_DIR}.tar.gz"

mkdir -p "$OUT_DIR"

log() {
  printf '[%s] %s\n' "$(date -Is)" "$*"
}

run_capture() {
  local name="$1"
  shift
  log "collecting ${name}"
  {
    echo "===== ${name} ====="
    echo "COMMAND: $*"
    echo "SINCE: ${SINCE}"
    echo "TIME: $(date -Is)"
    "$@"
    local rc=$?
    echo "EXIT_CODE: ${rc}"
    return 0
  } >"${OUT_DIR}/${name}.txt" 2>&1
}

run_shell_capture() {
  local name="$1"
  local script="$2"
  log "collecting ${name}"
  {
    echo "===== ${name} ====="
    echo "SCRIPT: ${script}"
    echo "SINCE: ${SINCE}"
    echo "TIME: $(date -Is)"
    bash -lc "$script"
    local rc=$?
    echo "EXIT_CODE: ${rc}"
    return 0
  } >"${OUT_DIR}/${name}.txt" 2>&1
}

log "writing logs to ${OUT_DIR}"

# System / runtime versions.
run_shell_capture system-info '
  echo "===== docker version ====="
  docker version || true
  echo
  echo "===== docker info ====="
  docker info || true
  echo
  echo "===== criu version ====="
  criu --version || true
  echo
  echo "===== criu check --all ====="
  criu check --all || true
  echo
  echo "===== runc version ====="
  runc --version || true
  echo
  echo "===== uname ====="
  uname -a || true
  echo
  echo "===== os-release ====="
  cat /etc/os-release || true
'

# Docker/containerd journal logs. sudo may prompt depending on your machine.
run_shell_capture docker-journal "sudo journalctl -u docker --since '${SINCE}' --no-pager || journalctl -u docker --since '${SINCE}' --no-pager || true"
run_shell_capture containerd-journal "sudo journalctl -u containerd --since '${SINCE}' --no-pager || journalctl -u containerd --since '${SINCE}' --no-pager || true"

# Docker events. Use timeout so it cannot hang forever.
run_shell_capture docker-events-v0 "timeout 30 docker events --since '${SINCE}' --until \"$(date -Is)\" --filter label=ai-edge-experiment=v0 || true"
run_shell_capture docker-events-all "timeout 30 docker events --since '${SINCE}' --until \"$(date -Is)\" || true"

# V0 container inventory.
run_shell_capture v0-containers 'docker ps -a --filter label=ai-edge-experiment=v0 || true'
run_shell_capture v0-container-inspect "
  count=0
  for c in \$(docker ps -aq --filter label=ai-edge-experiment=v0); do
    count=\$((count + 1))
    if [ \$count -gt ${MAX_CONTAINERS} ]; then
      echo 'container inspection capped at ${MAX_CONTAINERS}'
      break
    fi
    echo \"===== \${c} =====\"
    timeout ${PER_CONTAINER_TIMEOUT_S} docker inspect \"\$c\" || echo \"inspect timed out for \${c}\"
    echo
  done
"
run_shell_capture v0-container-logs "
  count=0
  for c in \$(docker ps -aq --filter label=ai-edge-experiment=v0); do
    count=\$((count + 1))
    if [ \$count -gt ${MAX_CONTAINERS} ]; then
      echo 'container log collection capped at ${MAX_CONTAINERS}'
      break
    fi
    echo \"===== \${c} =====\"
    timeout ${PER_CONTAINER_TIMEOUT_S} docker logs \"\$c\" || echo \"logs timed out for \${c}\"
    echo
  done
"
run_shell_capture v0-checkpoints "
  count=0
  for c in \$(docker ps -aq --filter label=ai-edge-experiment=v0); do
    count=\$((count + 1))
    if [ \$count -gt ${MAX_CONTAINERS} ]; then
      echo 'checkpoint listing capped at ${MAX_CONTAINERS}'
      break
    fi
    echo \"===== \${c} =====\"
    timeout ${PER_CONTAINER_TIMEOUT_S} docker checkpoint ls \"\$c\" || echo \"checkpoint ls timed out for \${c}\"
    echo
  done
"

# Process-level state for stuck shims/runc/criu/dockerd.
run_shell_capture process-state "ps -eo pid,ppid,stat,comm,args | grep -E 'containerd-shim|runc|criu|dockerd|cri-dockerd' | grep -v grep || true"

# Docker data-root and checkpoint log discovery.
DOCKER_ROOT="$(docker info --format '{{.DockerRootDir}}' 2>/dev/null || true)"
if [ -z "$DOCKER_ROOT" ]; then
  DOCKER_ROOT="/mnt/raid0nvme1/docker"
fi
printf '%s\n' "$DOCKER_ROOT" >"${OUT_DIR}/docker-data-root.txt"
log "Docker data-root: ${DOCKER_ROOT}"

run_shell_capture checkpoint-log-paths "
  if [ -d '${DOCKER_ROOT}' ]; then
    sudo find '${DOCKER_ROOT}' \\( -path '*checkpoint*' -o -name '*.log' -o -name '*log*' \\) -type f 2>/dev/null || \
    find '${DOCKER_ROOT}' \\( -path '*checkpoint*' -o -name '*.log' -o -name '*log*' \\) -type f 2>/dev/null || true
  else
    echo 'Docker root not found: ${DOCKER_ROOT}'
  fi
"

mkdir -p "${OUT_DIR}/checkpoint-files"
if [ -s "${OUT_DIR}/checkpoint-log-paths.txt" ]; then
  log "copying checkpoint/log files when accessible"
  while IFS= read -r path; do
    case "$path" in
      =====*|COMMAND:*|SINCE:*|TIME:*|EXIT_CODE:*|'') continue ;;
    esac
    if [ -f "$path" ]; then
      sudo cp --parents "$path" "${OUT_DIR}/checkpoint-files/" 2>/dev/null || \
      cp --parents "$path" "${OUT_DIR}/checkpoint-files/" 2>/dev/null || true
    fi
  done <"${OUT_DIR}/checkpoint-log-paths.txt"
fi

# Error summary across everything collected.
log "creating error summary"
grep -RniE 'error|fail|warn|criu|checkpoint|restore|runc|containerd|timeout|cgroup|namespace|permission|denied|Operation not permitted|no such file|segfault|panic' \
  "$OUT_DIR" >"${OUT_DIR}/error-summary.txt" 2>/dev/null || true

log "creating archive ${ARCHIVE}"
tar -czf "$ARCHIVE" -C "$(dirname "$OUT_DIR")" "$(basename "$OUT_DIR")"

cat <<EOF

CRIU debug logs collected.

Directory: ${OUT_DIR}
Archive:   ${ARCHIVE}

Start by inspecting:
  ${OUT_DIR}/error-summary.txt
  ${OUT_DIR}/docker-journal.txt
  ${OUT_DIR}/containerd-journal.txt
  ${OUT_DIR}/docker-events-v0.txt
  ${OUT_DIR}/v0-containers.txt
  ${OUT_DIR}/checkpoint-log-paths.txt

EOF
