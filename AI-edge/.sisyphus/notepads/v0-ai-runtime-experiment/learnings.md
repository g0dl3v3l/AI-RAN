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


## 2026-06-05 00:34:56Z

- Added a reusable Task-7 runtime contract with `RuntimeSession`, shared smoke-validation helpers, and a `VLLMRuntimeAdapter` that can resolve an existing OpenAI-compatible base URL, launch an experiment-owned localhost-only Docker vLLM server, or explicitly classify the runtime as `skipped` when nothing is configured.
- The vLLM adapter now emits `runtime_check` records plus an immediate smoke-validation classification for non-runnable states, including the required `smoke_not_attempted` path for the default-safe skipped mode.
- Added a stdlib-based `LLMSmokeClient` that appends `smoke_request.jsonl` and `smoke_response.jsonl` with a stable `request_id`, so later orchestration/preemption tasks can build on deterministic smoke artifacts without pulling in a full OpenAI SDK.


## 2026-06-05 00:49:06Z

- Task-8 smoke preemption now treats the Task-7 runtime session as the ownership gate: only `docker_server` sessions with both `container_name` and `container_id` reach checkpoint commands; external/no-container sessions cleanly return `smoke_preemption.status == skipped` with `outcome == not_attempted`.
- Reusing the Docker/CRIU command classifiers keeps checkpoint capability failures (`docker checkpoint create`, `docker start --checkpoint`) mapped to `unsupported` without crashing, while hard command errors still stay distinct for `smoke_failed_restore` classification.
- Smoke validation now derives publishable smoke outcomes from the preemption artifact shape: skipped → `smoke_not_attempted`, unsupported → `smoke_not_supported`, checkpoint/restore command errors → `smoke_failed_restore`, and successful restore defaults to `smoke_completed_after_restore` unless a later orchestrator marks replay.


## 2026-06-05 01:06:00Z

- Added `config.py` with a safe YAML loader, required-key validation, deterministic default filling for probe/runtime settings, and a `ResolvedConfig` contract that normalizes `output_dir`, `run_id`, and CLI dry-run overrides.
- Added `v0_orchestrator.py` to create the exact requested run directory, copy the resolved config to `config.yaml`, write `run_metadata.json`, run the Task-4 through Task-8 probe/runtime layers in sequence, and always emit the full V0 artifact set.
- Dry-run now bypasses Docker/GPU/vLLM entirely while still writing every required artifact, using deterministic skipped/not-attempted placeholder records for runtime, smoke request/response, preemption, and validation.


## 2026-06-05 02:00:00Z

- Added `experiments/tests/conftest.py` to gate `integration` and `gpu` tests centrally: they now skip by default unless `AI_EDGE_RUN_INTEGRATION=1` or `AI_EDGE_RUN_GPU=1` is set, while external vLLM smoke still requires `AI_EDGE_VLLM_BASE_URL`.
- Added four real-environment smoke tests that exercise the existing CLI entrypoints (`collect_hardware.py`, `check_docker_criu.py`, `check_cuda_container.py`, `run_smoke_request.py`) and validate emitted JSON/JSONL artifacts instead of inventing parallel test-only paths.
- Verified Task 10 behavior with pytest: the default suite still passes via `PYTHONPATH=experiments/src python -m pytest experiments/tests -m "not integration and not gpu" -v`, ungated smoke files skip cleanly by default, integration opt-in ran 2 passing tests, and GPU opt-in ran 1 passing CUDA smoke plus 1 skipped external-vLLM smoke when no URL was configured.


## 2026-06-05T01:17:59Z

- Added `experiments/README.md` with a Task-12-only V0 verification guide that separates dry-run artifact checks, live vLLM endpoint checks, and post-run artifact interpretation.
- Captured the important runtime nuance that `run_v0_probe.py` tears down any Docker-started vLLM container before exit, so `/v1/models` and `/v1/chat/completions` must be verified while a temporary runtime session is still up.
- Added `experiments/examples/v0_env_probe/verification_checklist.example.json` with machine-readable checks for the dry-run artifact contract, `docker_criu_integration.status`, `runtime_check.status`, `smoke_preemption.status`, and `smoke_validation.classification`, plus explicit classification meanings for later automation.


## 2026-06-05 12:20:00Z

- Added Task-11 docs under `experiments/README.md` with the exact repo-root command contract for unit tests, the default non-integration suite, the opt-in integration and GPU suite commands, dry-run, and a real host run.
- Added committed shape-only examples for `smoke_validation.json` and an unsupported `docker_criu_integration.json` record under `experiments/examples/v0_env_probe/`, using placeholder IDs and timestamps instead of host data.
- Documented the current Docker ownership gate in the runbook: destructive Docker CRIU actions require the `ai-edge-v0-criu-` prefix plus the `ai-edge-experiment`, `ai-edge-component`, and `ai-edge-run-id` labels before the harness will checkpoint or remove a container.


## 2026-06-05T03:15:39Z

- Extended `.gitignore` minimally to match the V0 governance rule that generated checkpoints, logs, and model artifacts stay untracked alongside `experiments/results/**`.
- Updated `LLMSmokeClient` so live `smoke_request.jsonl` and `smoke_response.jsonl` records now carry the same structured V0 metadata shape used elsewhere: `status`, `component`, and a `details` mapping with smoke runtime/base URL metadata (plus `reason` on failures).
- Tightened `experiments/tests/unit/test_llm_client.py` to prove both success and error smoke JSONL records preserve the structured request/response contract.
