#!/usr/bin/env bash
set -euo pipefail

timestamp_utc() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

log_stage() {
  local stage="$1"
  shift
  local msg="$*"
  printf '[%s] [%s] %s\n' "$(timestamp_utc)" "$stage" "$msg" | tee -a "$MASTER_LOG"
}

CONFIG_PATH="/tmp/v0_vllm_cdi_restore.yaml"
CHECKPOINT_TARGET="ram"
CHECKPOINT_RAM_SIZE="80G"
CHECKPOINT_DIR_OVERRIDE=""
OUTPUT_ROOT="/tmp"
RUN_ID=""
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)
      CONFIG_PATH="$2"
      shift 2
      ;;
    --checkpoint-target)
      CHECKPOINT_TARGET="$2"
      shift 2
      ;;
    --checkpoint-ram-size)
      CHECKPOINT_RAM_SIZE="$2"
      shift 2
      ;;
    --checkpoint-dir)
      CHECKPOINT_DIR_OVERRIDE="$2"
      shift 2
      ;;
    --output-root)
      OUTPUT_ROOT="$2"
      shift 2
      ;;
    --run-id)
      RUN_ID="$2"
      shift 2
      ;;
    --repo-root)
      REPO_ROOT="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "$RUN_ID" ]]; then
  RUN_ID="ai-edge-v0-vllm-real-$(date -u +%Y%m%d-%H%M%S)"
fi

RUN_DIR="${OUTPUT_ROOT%/}/${RUN_ID}"
ARTIFACT_DIR="$RUN_DIR/artifacts"
MASTER_LOG="$RUN_DIR/full_debug_runner.log"
EFFECTIVE_CFG="$RUN_DIR/v0_effective.yaml"
SYSTEM_DEBUG_OUT="$RUN_DIR/system-debug"
FINAL_BUNDLE="/tmp/${RUN_ID}-debug.tar.gz"

mkdir -p "$RUN_DIR" "$ARTIFACT_DIR"
touch "$MASTER_LOG"

log_stage "init" "run_id=$RUN_ID"
log_stage "init" "repo_root=$REPO_ROOT"
log_stage "init" "config_path=$CONFIG_PATH"
log_stage "init" "artifact_dir=$ARTIFACT_DIR"

if [[ ! -f "$CONFIG_PATH" ]]; then
  log_stage "error" "config not found: $CONFIG_PATH"
  exit 1
fi

cd "$REPO_ROOT"

log_stage "sudo" "refreshing sudo credentials (interactive prompt allowed)"
sudo -v

log_stage "criu_config" "writing /etc/criu/runc.conf"
cat <<'EOF' | sudo tee /etc/criu/runc.conf >/dev/null
libdir /usr/local/lib/criu
ext-mount-map auto
external mnt[]
enable-external-masters
tcp-established
link-remap
file-locks
ghost-limit 1073741824
EOF

log_stage "cleanup" "removing previous experiment containers and occupied ports"
CONTAINER_IDS="$(docker ps -aq --filter "name=ai-edge-v0-" || true)"
if [[ -n "$CONTAINER_IDS" ]]; then
  docker rm -f $CONTAINER_IDS >/dev/null 2>&1 || true
fi
sudo fuser -k 8000/tcp 8013/tcp >/dev/null 2>&1 || true

CHECKPOINT_DIR=""
if [[ -n "$CHECKPOINT_DIR_OVERRIDE" ]]; then
  CHECKPOINT_DIR="$CHECKPOINT_DIR_OVERRIDE"
elif [[ "$CHECKPOINT_TARGET" == "ram" ]]; then
  CHECKPOINT_DIR="/mnt/ckpt-ram/$RUN_ID"
fi

if [[ "$CHECKPOINT_TARGET" == "ram" ]]; then
  log_stage "checkpoint_target" "configuring RAM-backed checkpoint dir"
  sudo mkdir -p /mnt/ckpt-ram
  if ! mountpoint -q /mnt/ckpt-ram; then
    sudo mount -t tmpfs -o "size=$CHECKPOINT_RAM_SIZE" tmpfs /mnt/ckpt-ram
  fi
  sudo mkdir -p "$CHECKPOINT_DIR"
  sudo chown "$(id -u):$(id -g)" "$CHECKPOINT_DIR" || true
elif [[ "$CHECKPOINT_TARGET" == "disk" ]]; then
  log_stage "checkpoint_target" "using disk-backed checkpoint path"
  if [[ -n "$CHECKPOINT_DIR" ]]; then
    mkdir -p "$CHECKPOINT_DIR"
  fi
else
  log_stage "error" "invalid --checkpoint-target: $CHECKPOINT_TARGET (use ram|disk)"
  exit 1
fi

log_stage "telemetry" "capturing pre-run host memory/VRAM snapshots"
free -h > "$RUN_DIR/host_memory_pre.txt" || true
nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv,noheader > "$RUN_DIR/gpu_memory_pre.csv" || true
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader > "$RUN_DIR/gpu_process_pre.csv" || true

DOCKER_ROOT="$(docker info --format '{{.DockerRootDir}}' 2>/dev/null || true)"
echo "$DOCKER_ROOT" > "$RUN_DIR/docker_root_dir.txt"
if [[ -n "$DOCKER_ROOT" ]]; then
  findmnt -no TARGET,SOURCE,FSTYPE,OPTIONS "$DOCKER_ROOT" > "$RUN_DIR/docker_root_mount.txt" || true
fi
if [[ -n "$CHECKPOINT_DIR" ]]; then
  findmnt -no TARGET,SOURCE,FSTYPE,OPTIONS "$CHECKPOINT_DIR" > "$RUN_DIR/checkpoint_dir_mount.txt" || true
fi

log_stage "config" "building effective config with checkpoint and post-restore probe settings"
python3 - "$CONFIG_PATH" "$EFFECTIVE_CFG" "$ARTIFACT_DIR" "$CHECKPOINT_DIR" <<'PY'
import sys
from pathlib import Path
import yaml

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
artifact_dir = sys.argv[3]
checkpoint_dir = sys.argv[4]

cfg = yaml.safe_load(src.read_text(encoding="utf-8"))
if not isinstance(cfg, dict):
    raise SystemExit("config root must be mapping")

cfg["output_dir"] = artifact_dir

probe = cfg.setdefault("probe_options", {})
if not isinstance(probe, dict):
    raise SystemExit("probe_options must be mapping")

pre = probe.setdefault("preemption", {})
if not isinstance(pre, dict):
    raise SystemExit("probe_options.preemption must be mapping")
pre["criu_config_mode"] = pre.get("criu_config_mode") or "cdi_restore_compat"
pre["criu_config_allow_sudo"] = True
pre["capture_memory_telemetry"] = True
if checkpoint_dir:
    pre["checkpoint_dir"] = checkpoint_dir

dci = probe.setdefault("docker_criu_integration", {})
if not isinstance(dci, dict):
    raise SystemExit("probe_options.docker_criu_integration must be mapping")
if checkpoint_dir:
    dci["checkpoint_dir"] = checkpoint_dir

workload = cfg.setdefault("workload", {})
if not isinstance(workload, dict):
    raise SystemExit("workload must be mapping")
workload.setdefault("post_restore_probe_enabled", True)
workload.setdefault("post_restore_readiness_timeout_s", 120.0)
workload.setdefault("post_restore_readiness_poll_interval_s", 1.0)

dst.parent.mkdir(parents=True, exist_ok=True)
dst.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
PY

log_stage "probe_run" "starting run_v0_probe.py (live stage output expected)"
set +e
PYTHONPATH=experiments/src python -u experiments/scripts/run_v0_probe.py \
  --config "$EFFECTIVE_CFG" \
  --output-dir "$ARTIFACT_DIR" \
  2>&1 | tee -a "$MASTER_LOG"
PROBE_RC=${PIPESTATUS[0]}
set -e
log_stage "probe_run" "run_v0_probe.py finished rc=$PROBE_RC"

log_stage "telemetry" "capturing post-run host memory/VRAM snapshots"
free -h > "$RUN_DIR/host_memory_post.txt" || true
nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv,noheader > "$RUN_DIR/gpu_memory_post.csv" || true
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader > "$RUN_DIR/gpu_process_post.csv" || true

if [[ -n "$CHECKPOINT_DIR" ]]; then
  du -sh "$CHECKPOINT_DIR" > "$RUN_DIR/checkpoint_dir_size.txt" 2>/dev/null || true
  find "$CHECKPOINT_DIR" -type f -printf '%s %p\n' 2>/dev/null | sort -nr | head -40 > "$RUN_DIR/checkpoint_largest_files.txt" || true
fi

log_stage "system_debug" "collecting host docker/containerd/criu diagnostics"
bash experiments/scripts/collect_criu_debug_logs.sh "2 hours ago" "$SYSTEM_DEBUG_OUT" 2>&1 | tee -a "$MASTER_LOG" || true

log_stage "bundle" "creating final compressed bundle"
tar -czf "$FINAL_BUNDLE" -C "$RUN_DIR" . 2>/dev/null || true

log_stage "complete" "artifact_dir=$ARTIFACT_DIR"
log_stage "complete" "runner_log=$MASTER_LOG"
log_stage "complete" "system_debug_dir=$SYSTEM_DEBUG_OUT"
log_stage "complete" "final_bundle=$FINAL_BUNDLE"

printf 'FINAL_ARTIFACT_DIR=%s\n' "$ARTIFACT_DIR"
printf 'FINAL_RUNNER_LOG=%s\n' "$MASTER_LOG"
printf 'FINAL_SYSTEM_DEBUG_DIR=%s\n' "$SYSTEM_DEBUG_OUT"
printf 'FINAL_BUNDLE=%s\n' "$FINAL_BUNDLE"

exit "$PROBE_RC"
