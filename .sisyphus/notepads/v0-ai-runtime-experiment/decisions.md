# Decisions



## 2026-06-04 23:00:14Z

- Packaging: setuptools backend with PEP 621 metadata in root `pyproject.toml`; package dir mapped to `experiments/src`; version pinned to `0.1.0`.
- Testing: pytest configuration stored in `pyproject.toml` with `--strict-markers` and initial `integration`/`gpu` markers declared.
- Config: `experiments/configs/v0_env_probe.yaml` is a minimal skeleton (no probe logic yet) with `output_dir: experiments/results`.


## 2026-06-04 23:17:46Z

- Schema contract: probe artifact records are plain dicts with keys `schema_version`, `run_id`, `status`, `component`, `timestamp_utc`, `monotonic_ns`, `details`; enums are serialized to their `.value` strings.
- Timestamps: `timestamp_utc` uses ISO-8601 UTC strings with `Z` suffix; `monotonic_ns` uses `time.monotonic_ns()` (overrideable for deterministic tests).
- Writers: JSON uses temp-file replace for atomic-ish writes; JSONL appends one JSON object per line (`json.dumps(sort_keys=True)`) for deterministic, parseable logs.


## 2026-06-05 00:00:00Z

- Command runner status mapping: returncode==0 → ok; non-zero → error; TimeoutExpired → timeout; FileNotFoundError → unsupported.
- Run directory contract: `run_dir = Path(output_root) / run_id`; refuse existing directory unless `overwrite=True` (rmtree + recreate).


## 2026-06-04 23:44:41Z

- Task-4 artifact contract: `hardware.json` aggregates `uname -a`, `python --version`, `nvidia-smi`, and `nvidia-smi -q`; `docker.json` records `docker version`; both preserve serialized per-command metadata in `details.commands`.
- Overall probe status precedence for aggregated host hardware is `error` → `timeout` → `unsupported` → `skipped` → `ok`, with a human-readable `details.reason` when the overall status is not `ok`.
- Docker version extraction is line-based instead of strict section regexes so both `Client:` and `Client: Docker Engine - Community` formats produce best-effort `client_version`/`server_version` fields.


## 2026-06-05 00:00:48Z

- Task-5 component names follow artifact filenames: the CRIU presence probe writes component `criu_check`, and the Docker integration smoke writes component `docker_criu_integration`.
- Destructive Docker actions in Task 5 require both the `ai-edge-v0-criu-` name prefix and the labels `ai-edge-experiment=v0`, `ai-edge-component=docker-criu`, and a non-empty `ai-edge-run-id`; failing that gate returns an error record and skips checkpoint/remove.
- `check_docker_criu.py` reuses the requested output directory directly when it already exists and otherwise creates that exact path via Task-3 `ensure_run_dir`, so the CLI keeps the expected artifact location while still using the shared path utility.


## 2026-06-05 00:17:35Z

- Task-6 CUDA probing is configurable via probe/CLI image parameter, but its default image is fixed to `nvidia/cuda:12.4.1-base-ubuntu22.04` so the command contract stays stable without modifying `experiments/configs/v0_env_probe.yaml`.
- Task-6 MPS probing defaults to `mode: read_only`; lifecycle mutation is gated behind `allow_start_stop=True`, and even then the probe refuses start/stop if a pre-existing `/tmp/nvidia-mps/control` pipe is present.
- Both new CLIs follow the Task-5 output-dir contract: reuse an existing target directory when present, otherwise create the requested exact path via `ensure_run_dir` before writing `cuda_check.json` or `mps_check.json`.


## 2026-06-05 00:34:56Z

- Task-7 runtime config is intentionally minimal and mapping-based until the later orchestrator/config task lands: `external_server.base_url` is enough to use an existing server, while `docker_server.enabled` is the explicit opt-in gate for starting an experiment-owned vLLM container.
- Docker vLLM startup binds only `127.0.0.1:<port>:8000` on the host while serving on `0.0.0.0` inside the container, preserving localhost-only exposure without blocking OpenAI-compatible requests from the smoke client.
- Non-runnable runtime states are converted immediately into smoke-validation records in the adapter layer: `skipped -> smoke_not_attempted`, `unsupported -> smoke_not_supported`, `error -> smoke_runtime_failed`, and `timeout -> smoke_hung`.


## 2026-06-05 00:49:06Z

- Task 8 stays deliberately split into two pure helper layers: `preemption.smoke.collect_smoke_preemption(...)` produces the raw checkpoint/restore attempt artifact, and `validation.smoke.classify_smoke_validation(...)` maps that artifact (or a pre-existing runtime validation) into the final smoke classification.
- Unsupported Docker/CRIU prerequisites are preserved as `smoke_preemption.status == unsupported`, but all other non-attempted prerequisites (missing record, runtime not OK, no runtime-owned container) are normalized to `status == skipped` so later orchestration can distinguish "cannot attempt" from "attempted and failed".
- Task-7 runtime-level smoke validation remains authoritative when present; Task-8 validation reuses that record verbatim instead of overwriting `smoke_not_supported`/`smoke_runtime_failed` decisions for runtimes that never became preemptible.


## 2026-06-05 01:06:00Z

- Task 9 treats the configured `output_dir` as the exact run-directory path: the orchestrator still uses Task-3 `ensure_run_dir`, but splits the path into parent/name so CLI overrides like `/tmp/ai-edge-v0-dry-run` produce artifacts directly in that directory.
- Resolved config output is now an explicit artifact contract: `config.yaml` stores the normalized/override-applied config (including `run_id`, absolute `output_dir`, and `dry_run`) so later validation tasks can reproduce a run without re-deriving CLI state.
- Unsupported or skipped subprobes never abort orchestration; the overall run is marked `completed` in `run_metadata.json` as long as the orchestrator itself finishes and every required artifact file is written.
