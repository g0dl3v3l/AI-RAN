# Learnings



## 2026-06-04 23:00:14Z

- Created initial `experiments/` scaffold (package under `experiments/src/`, tests under `experiments/tests/`, configs/results/traces placeholders).
- Verified import contract via `PYTHONPATH=experiments/src` and a pytest smoke test.
- Added `.gitignore` rules to keep generated experiment artifacts out of git while retaining committed placeholders.


## 2026-06-04 23:17:46Z

- Added `ProbeStatus` + `SmokeClassification` enums and minimal probe record helpers (`make_probe_result`, `validate_probe_result`) with required V0 metadata fields.
- Implemented JSON artifact writers: `write_json` (temp-file + `os.replace`) and `append_jsonl` (line-delimited append).
- Added unit tests covering enum values, probe record shape, and JSONL append order/parseability.


## 2026-06-05 00:00:00Z

- Implemented safe subprocess runner `run_command` returning structured `CommandResult` (stdout/stderr capture, timeout handling, no shell by default, ProbeStatus mapping).
- Added deterministic run directory helper `ensure_run_dir` under an output root with explicit overwrite gate.
- Added UTC + monotonic timestamp helpers and best-effort git metadata capture utility.


## 2026-06-04 23:44:41Z

- Added Task-4 host probes that keep raw command outputs under `details.commands` while exposing lightweight parsed values under `details.extracted` for downstream orchestration.
- Verified that relying on Task-3 `run_command` keeps missing `nvidia-smi`/`docker` binaries classified as `unsupported` instead of crashing artifact collection.
- Real-host verification showed `docker version` and indented `nvidia-smi -q` output need permissive parsing to preserve best-effort version/GPU fields on production hosts.


## 2026-06-05 00:00:48Z

- Added a dedicated `docker_criu` probe package that keeps CRIU presence checks separate from Docker checkpoint integration results while still sharing the Task-2 probe artifact contract.
- Real-host verification showed `docker checkpoint --help` can succeed even when `docker checkpoint create` is still unsupported because the daemon lacks experimental checkpoint support; the integration artifact now classifies that case as `unsupported` instead of crashing.
- The CPU-only smoke path safely removed its own experiment-labelled BusyBox container after the unsupported checkpoint attempt, confirming the cleanup gate works for owned containers only.


## 2026-06-05 00:17:35Z

- Added Task-6 CUDA and MPS probes that keep per-command metadata under `details.commands` and extract lightweight runtime facts (`driver_version`, `cuda_version`, MPS binary/control-pipe presence) for downstream orchestration.
- Real-host verification showed the CUDA probe can pull and run `nvidia/cuda:12.4.1-base-ubuntu22.04` successfully on this host, producing `cuda_check.json.status == "ok"` with extracted driver `580.159.04` and CUDA `13.0`.
- The default MPS CLI path stays strictly read-only: it records `nvidia-cuda-mps-control` availability and control-pipe state without attempting daemon start/stop unless explicitly opted in.
