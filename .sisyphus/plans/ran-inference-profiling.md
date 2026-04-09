# Remote RAN Inference Profiling and Trace-Simulation Pipeline

## TL;DR
> **Summary**: Build a new standalone `inference-profile` package that profiles one isolated OPT decoder layer per model on the remote DGX Spark node using `torch.cuda.Event`, converts those measurements into deterministic whole-model service atoms, runs a math-only greedy scheduler over the primary RAN trace, and returns a timestamped run bundle containing raw CSVs, derived metrics, plots, checksums, and a Markdown report.
> **Deliverables**:
> - stageable Python CLI for bootstrap, model inspection, trace validation, profiling, simulation, reporting, bundle verification, and `run-all`
> - remote-safe OPT layer asset loader that downloads `config.json` plus only layer-relevant checkpoint artifacts when possible and never downloads a full model monolith intentionally
> - CUDA-event microbenchmarks for prefill, decode, and PCIe overlap with subprocess isolation and OOM-safe cleanup
> - deterministic greedy trace simulator exporting `ran_inference_profiling_results.csv`
> - five PNG plots plus `ran_inference_profiling_report.md`
> - `sshpass`-driven deployment/fetch Bash automation for `netsys@192.168.1.20`
> **Effort**: XL
> **Parallel**: YES - 4 waves
> **Critical Path**: contracts/scaffold → layer+trace loaders → CUDA-event profilers → profile reducer → greedy simulator → plots/report → remote orchestration

## Context
### Original Request
Create a robust end-to-end PyTorch profiling suite for decentralized OPT inference on telecommunications edge hardware, execute it remotely on `netsys@192.168.1.20`, use only the RAN idle gaps from the primary remote `ldpc_trace.csv` for a math-only scheduler, and fetch CSV/plot/report artifacts back to `/mnt/data/dheeraj/dicertation/inference-profile`.

### Interview Summary
- Target repo path is `/mnt/data/dheeraj/dicertation/inference-profile`; it currently exists but is empty, so the implementation must be a new standalone package there.
- Reuse patterns from `NVBenchSuite` for phase naming, isolated layer decomposition, manifests, and local orchestration; reuse patterns from `MobiCom26-Eval` for trace loading/validation and result writing.
- Remote connection policy is fixed: every remote `ssh`/`scp` operation must use `sshpass -f /mnt/data/dheeraj/dicertation/.ssh_pass` against `netsys@192.168.1.20`.
- Remote project root is fixed to `/home/netsys/dheeraj/inference-profile`; local fetched bundles land under `/mnt/data/dheeraj/dicertation/inference-profile/runs/<run_id>/`.
- Artifact policy is fixed: timestamped run directories on remote and local, no overwrite-in-place, and local verification after fetch.
- Test policy is fixed: TDD with deterministic unit/schema tests first, then GPU smoke tests, then mocked/real stage integration.
- Trace policy is fixed: inspect both remote traces, but only `ldpc_trace.csv` feeds SLA simulation; invalid or malformed primary trace aborts the run.
- Model asset policy is fixed: fetch `config.json` plus layer-specific checkpoint artifacts when possible; never intentionally download a whole-model checkpoint monolith; if a model repository only exposes a monolithic checkpoint, fall back to deterministic seeded FP16 layer tensors and record the fallback in the manifest.
- Layer profiling policy is fixed: isolate one representative decoder layer at index `(num_hidden_layers - 1) // 2`, use actual layer weights when obtainable, batch size `1`, dtype `float16`, and `torch.cuda.Event` timing only.
- Simulation policy is fixed: deterministic greedy scheduler, actual trace timestamps only, no modulo replay, no random offsets, no actual tensor execution in the simulation stage.
- Remote bootstrap policy is fixed: create a user-space `.venv` with `--system-site-packages`, install project Python dependencies there, validate CUDA-enabled PyTorch, but do not attempt to install system/CUDA packages.

### Metis Review (gaps addressed)
- Freeze six contracts before implementation: transport, trace schema, raw profile schema, scheduler semantics, run manifest, and run directory layout.
- Keep profiler timing domains pure: raw performance metrics come from CUDA events only; host wall clock may appear only in orchestration logs.
- Treat profile output and simulator input as separate schemas bridged by an explicit reducer so training-oriented MobiCom fields are not overloaded.
- Use spawned subprocess isolation for every benchmark point; `torch.cuda.empty_cache()` alone is not trusted as the primary allocator reset mechanism.
- Add failure-path acceptance criteria for malformed CSVs, non-monotonic trace timestamps, `sm_count > total_sms`, OOM, SSH timeout, partial fetch, and checksum mismatch.
- Require remote success to mean: remote stage passed, all required artifacts exist, local fetch succeeded, and checksum verification succeeded.

## Work Objectives
### Core Objective
Produce a decision-complete implementation plan for a new `inference-profile` codebase that can, on a remote DGX Spark-class host, (1) profile isolated OPT layer prefill/decode/PCIe microbenchmarks, (2) reduce those measurements into deterministic whole-model timing/VRAM summaries, (3) simulate prefill and decode scheduling against real RAN idle gaps without running model compute during the simulation step, and (4) return SRE-grade CSV/report/plot artifacts locally.

### Deliverables
- `inference-profile/pyproject.toml`
- `inference-profile/README.md`
- `inference-profile/inference_profile/__init__.py`
- `inference-profile/inference_profile/cli.py`
- `inference-profile/inference_profile/constants.py`
- `inference-profile/inference_profile/manifests.py`
- `inference-profile/inference_profile/paths.py`
- `inference-profile/inference_profile/bootstrap.py`
- `inference-profile/inference_profile/opt_assets.py`
- `inference-profile/inference_profile/prefill_profile.py`
- `inference-profile/inference_profile/decode_profile.py`
- `inference-profile/inference_profile/pcie_profile.py`
- `inference-profile/inference_profile/profile_reducer.py`
- `inference-profile/inference_profile/trace_contract.py`
- `inference-profile/inference_profile/simulator.py`
- `inference-profile/inference_profile/plots.py`
- `inference-profile/inference_profile/report.py`
- `inference-profile/inference_profile/verify_bundle.py`
- `inference-profile/inference_profile/worker_profile_point.py`
- `inference-profile/scripts/deploy_and_run_remote.sh`
- `inference-profile/tests/unit/*.py`
- `inference-profile/tests/gpu/*.py`
- `inference-profile/tests/integration/*.py`
- remote run bundle root: `/home/netsys/dheeraj/inference-profile/runs/<run_id>/`
- local fetched bundle root: `/mnt/data/dheeraj/dicertation/inference-profile/runs/<run_id>/`

### Definition of Done (verifiable conditions with commands)
- `python -m pytest tests/unit tests/integration -q`
- `python -m pytest -m gpu_smoke tests/gpu/test_prefill_profile_smoke.py tests/gpu/test_decode_profile_smoke.py tests/gpu/test_pcie_profile_smoke.py -q`
- `python -m inference_profile.cli inspect-model --model facebook/opt-125m --output-root /tmp/ip-inspect`
- `python -m inference_profile.cli validate-traces --ldpc-trace /tmp/ldpc_trace_valid.csv --ran-ctrl-trace /tmp/ran_ctrl_trace_valid.csv --output-root /tmp/ip-trace-validate`
- `python -m inference_profile.cli profile --models facebook/opt-125m --chunk-sizes 64 --sequence-lengths 1024 --warmup 3 --iterations 5 --gpu-id 0 --output-root /tmp/ip-profile`
- `python -m inference_profile.cli simulate --run-root /tmp/ip-profile --output-root /tmp/ip-sim`
- `python -m inference_profile.cli report --run-root /tmp/ip-sim --output-root /tmp/ip-report`
- `python -m inference_profile.cli verify-bundle --run-root /tmp/ip-report`
- `bash scripts/deploy_and_run_remote.sh --stage all --run-id smoke --models facebook/opt-125m --chunk-sizes 64 --sequence-lengths 1024 --ldpc-trace /mnt/raid0sata2/netsys/weaver-ext/ran/traces/e2e_2026030418/e2e_20260304_182034_tractor_ran_ctrl/ldpc_trace.csv --ran-ctrl-trace /mnt/raid0sata2/netsys/weaver-ext/ran/traces/e2e_2026030418/e2e_20260304_182034_tractor_ran_ctrl/ran_ctrl_trace.csv`

### Must Have
- model sweep fixed to `facebook/opt-125m`, `facebook/opt-350m`, `facebook/opt-1.3b`, `facebook/opt-2.7b`, `facebook/opt-6.7b`
- prefill chunk sizes fixed to `64, 128, 256, 512, 1024`
- decode sequence lengths fixed to `1024, 2048, 4096, 8192`
- single representative OPT decoder layer at index `(num_hidden_layers - 1) // 2`
- `float16` profiling on GPU with `torch.cuda.Event(enable_timing=True)`
- batch size fixed to `1`
- subprocess isolation per benchmark point using `spawn`
- explicit `torch.cuda.synchronize()` before reading event timing
- explicit `torch.cuda.empty_cache()` after every point and on worker teardown
- trace inspection of both `ldpc_trace.csv` and `ran_ctrl_trace.csv`
- fail-fast on malformed or missing primary `ldpc_trace.csv`
- normalized internal trace columns `time_ms`, `sm_utilization`, `slot_duration_ms`, `source_schema`
- deterministic greedy scheduler using actual trace timestamps and idle-gap intervals only
- five fixed PNG plots and one Markdown report generated on the remote host
- raw CSVs, derived CSVs, JSON manifests, log files, and checksums in every run bundle
- remote bootstrap via `.venv` with `--system-site-packages`
- local fetch verification with checksums before declaring success
- `sshpass -f /mnt/data/dheeraj/dicertation/.ssh_pass` for every remote connection

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- no full-model `transformers.generate()` loops for profiling
- no full-model checkpoint download as an intentional execution path
- no simulation step that executes PyTorch kernels or model inference
- no mixed timing domains inside raw or derived performance metrics
- no silent fallback from invalid `ldpc_trace.csv` to `trace_random.csv`, `ran_ctrl_trace.csv`, or any bundled trace
- no modulo replay, random offsets, or non-deterministic scheduler tie-breaking
- no hardcoded SM count, total GPU memory, or PCIe bandwidth assumptions in code
- no system package installation, `apt`, `yum`, or CUDA toolkit mutation on the remote host
- no local regeneration of remote plots/report after fetch for the canonical bundle
- no password logging, command echoing with secrets, or storing `.ssh_pass` contents in manifests/logs
- no success state based only on remote exit code

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed.
- Test decision: **TDD** (`unit/schema → mocked integration → GPU smoke → remote stage smoke`)
- QA policy: every task below includes concrete agent-executable scenarios and file assertions
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`
- Timing evidence: raw CSVs must contain only event-timed microbenchmark metrics in microseconds and bytes
- Bundle evidence: every complete run must include `run_manifest.json`, `checksums/sha256sums.txt`, `logs/`, `raw/`, `derived/`, `plots/`, and `ran_inference_profiling_report.md`; `sha256sums.txt` must cover every required bundle artifact except itself

## Execution Strategy
### Parallel Execution Waves
> Target: 5 tasks per wave. Shared contracts land first; profiling, simulation, and remote delivery then fan out.

Wave 1: scaffold, manifests, model assets, trace contracts, subprocess isolation

Wave 2: prefill/decode/PCIe profilers, profile reducers, profiling CLI orchestration

Wave 3: trace-validation CLI, greedy simulator, derived metrics export, plots, report/bundle verification

Wave 4: remote bootstrap, sshpass deployment, remote `run-all`, fetch verification, README/runbook

### Dependency Matrix (full, all tasks)
| Task | Depends On | Blocks |
|------|------------|--------|
| T1 | — | T2-T20 |
| T2 | T1 | T10-T20 |
| T3 | T1 | T6-T15 |
| T4 | T1 | T11-T20 |
| T5 | T1 | T6-T10, T18 |
| T6 | T3, T5 | T9-T15, T18 |
| T7 | T3, T5 | T9-T15, T18 |
| T8 | T3, T5 | T9-T15, T18 |
| T9 | T6, T7, T8 | T10-T15, T18 |
| T10 | T2, T9 | T11-T15, T18-T19 |
| T11 | T2, T4, T9, T10 | T12-T15, T18-T19 |
| T12 | T11 | T13-T15, T18-T19 |
| T13 | T12 | T14-T15, T18-T20 |
| T14 | T13 | T15, T18-T20 |
| T15 | T13, T14 | T18-T20 |
| T16 | T1, T4 | T17-T20 |
| T17 | T16 | T18-T19 |
| T18 | T10, T15, T16, T17 | T19-T20, F1-F4 |
| T19 | T15, T17, T18 | T20, F1-F4 |
| T20 | T15, T19 | F1-F4 |

### Agent Dispatch Summary (wave → task count → categories)
- Wave 1 → 5 tasks → `quick`, `unspecified-high`, `deep`
- Wave 2 → 5 tasks → `deep`, `unspecified-high`
- Wave 3 → 5 tasks → `deep`, `ultrabrain`, `visual-engineering`, `writing`
- Wave 4 → 5 tasks → `unspecified-high`, `quick`, `deep`, `writing`

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task includes the exact files to touch, fixed output names, and executable QA scenarios.
> Execute strictly by task number and the dependency matrix.

- [ ] 17. Create the `sshpass` deployment script with deterministic sync and stage controls

  **What to do**: Add `scripts/deploy_and_run_remote.sh` with `set -euo pipefail`. Parse `--stage {sync,bootstrap,run,fetch,all}`, `--run-id`, `--models`, `--chunk-sizes`, `--sequence-lengths`, `--ldpc-trace`, `--ran-ctrl-trace`, `--gpu-id`, and `--dry-run`. Every remote connection must use `sshpass -f /mnt/data/dheeraj/dicertation/.ssh_pass`. The `sync` stage must upload only `pyproject.toml`, `README.md`, `inference_profile/`, `scripts/`, and `tests/` via a tar stream over SSH, after removing only those same tracked paths from `/home/netsys/dheeraj/inference-profile` while preserving `runs/`. The script must never echo the password or the full `sshpass` command in logs; `--dry-run` prints redacted commands only.
  **Must NOT do**: Do not rely on interactive SSH prompts. Do not delete `/home/netsys/dheeraj/inference-profile/runs/` during sync.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: bounded shell automation with fixed flags and safety rules
  - Skills: `[]` - no extra skill injection is required
  - Omitted: `[]` - no specialized skill adds value here

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: T18-T19 | Blocked By: T16

  **References**:
  - Pattern: `sionna-rk/scripts/run-tractor-e2e.sh` - shell-based experiment orchestration and manifest-aware logging style
  - Pattern: `NVBenchSuite/scripts/run_inference_profiling.sh` - argument-driven profiling shell wrapper pattern

  **Acceptance Criteria**:
  - [ ] `bash -n scripts/deploy_and_run_remote.sh` succeeds
  - [ ] `--dry-run` prints redacted `ssh`/`scp` actions without exposing `.ssh_pass` contents
  - [ ] `sync` preserves `runs/` while replacing only project source, scripts, tests, and top-level metadata

  **QA Scenarios**:
  ```
  Scenario: Shell script syntax and option parsing
    Tool: Bash
    Steps: Run `bash -n scripts/deploy_and_run_remote.sh && python -m pytest tests/integration/test_remote_script_render.py -q`
    Expected: Script is syntactically valid and tests verify stage parsing plus redacted dry-run output
    Evidence: .sisyphus/evidence/task-17-remote-script.txt

  Scenario: Sync contract preserves remote runs directory
    Tool: Bash
    Steps: Run `python -m pytest tests/integration/test_remote_sync_contract.py -q`
    Expected: Tests verify the generated remote cleanup command removes only source paths and never deletes `runs/`
    Evidence: .sisyphus/evidence/task-17-sync-contract.txt
  ```

  **Commit**: YES | Message: `feat(remote): add sshpass deployment script` | Files: `inference-profile/scripts/deploy_and_run_remote.sh`, `inference-profile/tests/integration/test_remote_script_render.py`, `inference-profile/tests/integration/test_remote_sync_contract.py`

- [ ] 18. Wire remote `run-all` orchestration and resumable stage execution

  **What to do**: Implement `python -m inference_profile.cli run-all` so it runs the fixed stage order `bootstrap-env → validate-traces → profile → simulate → report → verify-bundle` into one remote run root `runs/<run_id>/`. Add `--resume-from {bootstrap-env,validate-traces,profile,simulate,report,verify-bundle}` so failed runs can resume without recomputing prior successful stages. Update the Bash script’s `run` stage to invoke this remote CLI with the user-provided trace paths, selected models, and profile matrix. Remote success means the manifest’s final status is `success`; remote exit `0` alone is insufficient.
  **Must NOT do**: Do not rerun successful earlier stages when `--resume-from` is used. Do not declare remote success if `verify-bundle` fails.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: this task couples all stage boundaries, resume semantics, and remote success criteria
  - Skills: `[]` - no extra skill injection is required
  - Omitted: `[]` - no specialized skill adds value here

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: T19-T20, F1-F4 | Blocked By: T10, T15, T16, T17

  **References**:
  - Pattern: `MobiCom26-Eval/evaluation/two-level-scheduling-simulator/run_trace_driven_eval.py` - config-first execution stage ordering
  - Pattern: `NVBenchSuite/scripts/run_exp_a_all_waves.py` - stage bookkeeping and resumable run-state patterns

  **Acceptance Criteria**:
  - [ ] `run-all` updates manifest stage statuses in order and stops immediately on the first failing stage
  - [ ] `--resume-from` skips already successful prior stages and restarts from the requested one
  - [ ] the remote Bash `run` stage checks final manifest status, not just SSH exit status

  **QA Scenarios**:
  ```
  Scenario: Run-all stage ordering and resume contract
    Tool: Bash
    Steps: Run `python -m pytest tests/integration/test_run_all_resume.py -q`
    Expected: Tests verify ordered stage execution, correct resume behavior, and failure short-circuiting
    Evidence: .sisyphus/evidence/task-18-run-all.txt

  Scenario: Remote smoke command is rendered correctly
    Tool: Bash
    Steps: Run `python -m pytest tests/integration/test_remote_run_command.py -q`
    Expected: Tests verify the Bash wrapper passes the actual user-specified remote trace paths and run root to `python -m inference_profile.cli run-all`
    Evidence: .sisyphus/evidence/task-18-remote-command.txt
  ```

  **Commit**: YES | Message: `feat(remote): add remote run-all orchestration` | Files: `inference-profile/inference_profile/cli.py`, `inference-profile/tests/integration/test_run_all_resume.py`, `inference-profile/tests/integration/test_remote_run_command.py`

- [ ] 19. Fetch artifacts locally, verify checksums, and preserve failure evidence

  **What to do**: Add fetch logic to `scripts/deploy_and_run_remote.sh` so `--stage fetch` copies `/home/netsys/dheeraj/inference-profile/runs/<run_id>/` into `/mnt/data/dheeraj/dicertation/inference-profile/runs/<run_id>/` via `sshpass` + `scp -r`. Always fetch `run_manifest.json`, `logs/`, and `checksums/` even after remote failure. After fetch, run `python -m inference_profile.cli verify-bundle --run-root <local_run_root>`; if verification fails, update the local manifest copy to `fetch_failed`, preserve all fetched files, and exit non-zero. Support repeated fetch attempts without rerunning remote compute.
  **Must NOT do**: Do not delete partial local bundles on failure. Do not mark fetch success when checksums mismatch.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: artifact integrity and failure recovery are operationally critical
  - Skills: `[]` - no extra skill injection is required
  - Omitted: `[]` - no specialized skill adds value here

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: T20, F1-F4 | Blocked By: T15, T17, T18

  **References**:
  - Pattern: `MobiCom26-Eval/.sisyphus/evidence/task-11-single-site-results.json` - failure-preserving evidence mindset
  - Pattern: `MobiCom26-Eval/evaluation/two-level-scheduling-simulator/validate_simulation.py` - post-run validation as a gating step

  **Acceptance Criteria**:
  - [ ] `fetch` copies the remote run directory locally into the fixed timestamped location
  - [ ] checksum or completeness failures produce local status `fetch_failed` and preserve all fetched logs/artifacts
  - [ ] repeated `--stage fetch` works for an existing remote `run_id` without rerunning `run-all`

  **QA Scenarios**:
  ```
  Scenario: Fetch verification contract
    Tool: Bash
    Steps: Run `python -m pytest tests/integration/test_fetch_manifest.py tests/integration/test_fetch_checksum_failure.py -q`
    Expected: Tests verify success on complete bundles and typed `fetch_failed` on checksum mismatch or missing required artifacts
    Evidence: .sisyphus/evidence/task-19-fetch.txt

  Scenario: Partial remote failure still retrieves logs
    Tool: Bash
    Steps: Run `python -m pytest tests/integration/test_fetch_partial_failure_logs.py -q`
    Expected: Tests verify that manifests and logs are fetched even when the remote run stops before report generation
    Evidence: .sisyphus/evidence/task-19-fetch-failures.txt
  ```

  **Commit**: YES | Message: `feat(remote): add fetch verification and recovery` | Files: `inference-profile/scripts/deploy_and_run_remote.sh`, `inference-profile/tests/integration/test_fetch_manifest.py`, `inference-profile/tests/integration/test_fetch_checksum_failure.py`, `inference-profile/tests/integration/test_fetch_partial_failure_logs.py`

- [ ] 20. Document the runbook, smoke commands, and failure taxonomy in `README.md`

  **What to do**: Update `inference-profile/README.md` with: project layout, local CLI stages, remote Bash stages, smoke commands, the exact remote trace paths from the user request, output directory layout, status taxonomy, resume rules, checksum verification flow, and a short security note explaining that `sshpass` is intentionally used because the request requires it. Include one copy-pasteable smoke command and one full run command. Document the fixed plot filenames and the meaning of `survival_vram_bytes`, `decode_runway_bytes`, `ttft_ms`, `tpot_ms_vram`, and `tpot_ms_pcie_async`.
  **Must NOT do**: Do not include the password contents or suggest manual file editing after fetch. Do not document unsupported fallback traces.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: this is documentation and runbook hardening tied to the final operator workflow
  - Skills: `[]` - no extra skill injection is required
  - Omitted: `[]` - no specialized skill adds value here

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: F1-F4 | Blocked By: T15, T19

  **References**:
  - Pattern: `NVBenchSuite/README.md` - benchmark/runbook documentation structure
  - Pattern: `MobiCom26-Eval/evaluation/single-node-ran-control-training/provenance/EXTRACTION_REPORT.md` - provenance-oriented documentation tone

  **Acceptance Criteria**:
  - [ ] `README.md` includes the exact smoke and full-run commands for the stageable CLI and Bash wrapper
  - [ ] documented status values match the implementation’s manifest taxonomy exactly
  - [ ] README explains output file locations and metric definitions without contradicting the generated report fields

  **QA Scenarios**:
  ```
  Scenario: README command strings stay in sync with CLI and script flags
    Tool: Bash
    Steps: Run `python -m pytest tests/integration/test_readme_commands.py -q`
    Expected: Tests verify the README contains the actual supported subcommands, Bash flags, and user-provided trace-path examples
    Evidence: .sisyphus/evidence/task-20-readme.txt

  Scenario: Metric glossary matches result schema
    Tool: Bash
    Steps: Run `python -m pytest tests/unit/test_readme_metric_glossary.py -q`
    Expected: Tests verify README definitions align exactly with `ran_inference_profiling_results.csv` column names
    Evidence: .sisyphus/evidence/task-20-readme-metrics.txt
  ```

  **Commit**: YES | Message: `docs(profile): add remote runbook and metric glossary` | Files: `inference-profile/README.md`, `inference-profile/tests/integration/test_readme_commands.py`, `inference-profile/tests/unit/test_readme_metric_glossary.py`

- [ ] 13. Wire the `simulate` CLI and export canonical derived results

  **What to do**: Connect `python -m inference_profile.cli simulate` to `simulation_inputs.csv` and the greedy scheduler. Emit `derived/ran_inference_profiling_results.csv` with one row per successful or failed `model × N × L` and the fixed columns `model_id,chunk_tokens,sequence_length,weight_bytes,vram_ceiling_bytes,prefill_max_gemm_us,prefill_workspace_bytes,prefill_parked_activation_bytes,decode_max_gemv_us,attention_fetch_compute_us,reduction_overhead_us,pcie_exposed_us,survival_vram_bytes,decode_runway_bytes,decode_runway_tokens,ttft_ms,tpot_ms_vram,tpot_ms_pcie_async,trace_sha256,status`. Compute `survival_vram_bytes = vram_ceiling_bytes - weight_bytes - max(prefill_workspace_bytes + prefill_parked_activation_bytes, decode_workspace_bytes + decode_parked_activation_bytes)`. Also emit `derived/schedule_timeline.csv` with every scheduled prefill/decode interval needed for the interleaving plot.
  **Must NOT do**: Do not generate plots or markdown here. Do not drop failed rows from `ran_inference_profiling_results.csv`; mark them with typed status instead.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: this stage converts simulator outputs into the canonical artifact consumed by the report and plots
  - Skills: `[]` - no extra skill injection is required
  - Omitted: `[]` - no specialized skill adds value here

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: T14-T15, T18-T20 | Blocked By: T12

  **References**:
  - Pattern: `MobiCom26-Eval/evaluation/two-level-scheduling-simulator/metrics_writer.py` - canonical derived-metrics export behavior
  - Pattern: `MobiCom26-Eval/evaluation/two-level-scheduling-simulator/results/single_site/trace_selection.json` - metadata file accompanying derived simulator outputs

  **Acceptance Criteria**:
  - [ ] `derived/ran_inference_profiling_results.csv` exists with the fixed column order and one row per `model × N × L`
  - [ ] failed rows remain in the results CSV with typed `status` values and blank or null SLA fields where appropriate
  - [ ] `derived/schedule_timeline.csv` exists and contains start/end timestamps for every scheduled prefill/decode interval used later in Plot 1

  **QA Scenarios**:
  ```
  Scenario: Simulation CLI exports canonical results CSV
    Tool: Bash
    Steps: Run `python -m inference_profile.cli simulate --run-root tests/fixtures/minimal_run_bundle --output-root /tmp/ip-sim`
    Expected: `/tmp/ip-sim/derived/ran_inference_profiling_results.csv` and `/tmp/ip-sim/derived/schedule_timeline.csv` exist with the fixed schema
    Evidence: .sisyphus/evidence/task-13-sim-cli.txt

  Scenario: Survival VRAM and runway math are exact
    Tool: Bash
    Steps: Run `python -m pytest tests/unit/test_result_metrics_math.py -q`
    Expected: Tests verify `survival_vram_bytes`, `decode_runway_bytes`, and `decode_runway_tokens` against fixed fixtures
    Evidence: .sisyphus/evidence/task-13-metrics-math.txt
  ```

  **Commit**: YES | Message: `feat(sim): export canonical results csv` | Files: `inference-profile/inference_profile/cli.py`, `inference-profile/inference_profile/simulator.py`, `inference-profile/tests/unit/test_result_metrics_math.py`, `inference-profile/tests/integration/test_simulate_cli.py`, `inference-profile/tests/fixtures/minimal_run_bundle/*`

- [ ] 14. Generate the five required plots with deterministic selection rules

  **What to do**: Add `inference_profile/plots.py` using matplotlib/seaborn with one internal `_apply_plot_style()` helper instead of importing broken external styling. Emit exactly five files under `plots/`: `01_ran_trace_interleaving.png`, `02_prefill_safety_boundary.png`, `03_prefill_vram_composition.png`, `04_ttft_vs_runway.png`, `05_decode_tpot_degradation.png`. Plot 1 must choose one deterministic exemplar configuration: sort successful result rows by `ttft_ms ASC`, then by model-size rank DESC, chunk size DESC, sequence length DESC, and pick the first row; overlay its scheduled intervals from `schedule_timeline.csv` on the normalized trace square wave and draw a TTFT vertical line. Plot 5 must be a five-panel figure (one panel per model) and, within each panel, use the largest successful chunk size for that model, with two lines: VRAM-only TPOT vs PCIe-async TPOT across `L`.
  **Must NOT do**: Do not require manual figure editing. Do not depend on `NVBenchSuite/analysis/plot_utils.py` or its missing `analysis_style` helper.

  **Recommended Agent Profile**:
  - Category: `visual-engineering` - Reason: this is deterministic data visualization with fixed layout and comparative readability requirements
  - Skills: `[]` - no extra skill injection is required
  - Omitted: `[]` - no specialized skill adds value here

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: T15, T18-T20 | Blocked By: T13

  **References**:
  - Pattern: `NVBenchSuite/analysis/generate_heatmaps.py` - multi-panel analysis figure generation pattern
  - Pattern: `NVBenchSuite/analysis/plot_opt_single_layer_prefill.py` - publication-style summary plotting and fixed figure output names
  - Pattern: `NVBenchSuite/analysis/generate_workload_table.py` - report-oriented summary artifacts to align with

  **Acceptance Criteria**:
  - [ ] all five PNG files are created with non-zero size under `plots/`
  - [ ] Plot 1 uses the deterministic exemplar selection rule and records the chosen row in `derived/plot_selection.json`
  - [ ] Plot 5 is rendered as a five-panel figure, one panel per OPT model, with exactly two lines in each panel

  **QA Scenarios**:
  ```
  Scenario: Plot generation smoke from fixture results
    Tool: Bash
    Steps: Run `python -m pytest tests/integration/test_plot_generation.py -q`
    Expected: Tests verify creation of all five PNGs plus `derived/plot_selection.json` from fixture result tables
    Evidence: .sisyphus/evidence/task-14-plots.txt

  Scenario: Empty and single-row inputs fail clearly
    Tool: Bash
    Steps: Run `python -m pytest tests/unit/test_plot_failure_modes.py -q`
    Expected: Empty input raises a typed error; single-row input either plots validly or emits a deterministic message depending on the figure contract
    Evidence: .sisyphus/evidence/task-14-plot-failures.txt
  ```

  **Commit**: YES | Message: `feat(report): add deterministic plot generation` | Files: `inference-profile/inference_profile/plots.py`, `inference-profile/tests/integration/test_plot_generation.py`, `inference-profile/tests/unit/test_plot_failure_modes.py`

- [ ] 15. Generate the Markdown report and verify bundle completeness locally and remotely

  **What to do**: Add `inference_profile/report.py` and `inference_profile/verify_bundle.py`. `report.py` must create `ran_inference_profiling_report.md` at the run root with sections for environment, model constants, trace inspection, raw-profile summary tables, SLA tables, per-model scaling analysis, and the five embedded plot images using relative paths `plots/<filename>.png`. `verify_bundle.py` must confirm the presence, non-zero size, and checksum coverage of the canonical artifact set: `run_manifest.json`, `environment.json`, all raw CSVs, all derived CSVs, `plots/*.png`, and `ran_inference_profiling_report.md`; `checksums/sha256sums.txt` must exist and list every required artifact except itself.
  **Must NOT do**: Do not rewrite plots or results during verification. Do not accept missing images or missing checksum entries.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: report structure and bundle-verification prose/data presentation dominate this task
  - Skills: `[]` - no extra skill injection is required
  - Omitted: `[]` - no specialized skill adds value here

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: T18-T20 | Blocked By: T13, T14

  **References**:
  - Pattern: `NVBenchSuite/analysis/opt_single_layer_prefill/acu_gbu_subprocess_report.md` - existing generated Markdown report structure to emulate
  - Pattern: `MobiCom26-Eval/evaluation/two-level-scheduling-simulator/results/validation_report.txt` - validation-style summary writing pattern

  **Acceptance Criteria**:
  - [ ] `ran_inference_profiling_report.md` embeds all five plots with working relative links
  - [ ] `verify-bundle` fails when any required artifact is missing, zero-byte, or absent from `sha256sums.txt`
  - [ ] report summary tables include at least one row for every successful model and clearly list failed rows separately

  **QA Scenarios**:
  ```
  Scenario: Report bundle builds and verifies
    Tool: Bash
    Steps: Run `python -m inference_profile.cli report --run-root tests/fixtures/minimal_run_bundle --output-root /tmp/ip-report && python -m inference_profile.cli verify-bundle --run-root /tmp/ip-report`
    Expected: Report is created, images resolve by relative path, and bundle verification exits `0`
    Evidence: .sisyphus/evidence/task-15-report-verify.txt

  Scenario: Verification fails on missing artifact
    Tool: Bash
    Steps: Run `python -m pytest tests/integration/test_verify_bundle_failures.py -q`
    Expected: Tests verify missing or zero-byte artifacts trigger typed verification failures
    Evidence: .sisyphus/evidence/task-15-verify-failures.txt
  ```

  **Commit**: YES | Message: `feat(report): add markdown report and bundle verification` | Files: `inference-profile/inference_profile/report.py`, `inference-profile/inference_profile/verify_bundle.py`, `inference-profile/tests/integration/test_report_bundle.py`, `inference-profile/tests/integration/test_verify_bundle_failures.py`

- [ ] 16. Implement remote bootstrap and environment validation for the DGX host

  **What to do**: Add `inference_profile/bootstrap.py` and wire `python -m inference_profile.cli bootstrap-env`. On the remote host it must: create `.venv` with `python3 -m venv --system-site-packages .venv`, install the project in editable mode plus Python-only dependencies, validate `torch`, `torch.cuda.is_available()`, `torch.cuda.get_device_properties(gpu_id)`, free disk space, and writable cache/output directories, then write `environment.json` and update the manifest. Record the actual `total_memory_bytes`, driver/runtime versions, and GPU name discovered at runtime.
  **Must NOT do**: Do not attempt `apt`, `yum`, CUDA toolkit installs, or driver mutation. Do not hardcode GPU memory or SM count.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: remote validation correctness gates the entire orchestration path
  - Skills: `[]` - no extra skill injection is required
  - Omitted: `[]` - no specialized skill adds value here

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: T17-T20 | Blocked By: T1, T4

  **References**:
  - Pattern: `MobiCom26-Eval/evaluation/two-level-scheduling-simulator/validate_prerequisites.py` - prerequisite validation and fail-fast output pattern
  - Pattern: `NVBenchSuite/scripts/run_tests.sh` - environment-sensitive execution gating pattern

  **Acceptance Criteria**:
  - [ ] `bootstrap-env` writes `environment.json` with runtime-discovered GPU and CUDA properties
  - [ ] lack of CUDA-enabled torch or unwritable output/cache paths produces `bootstrap_failed`
  - [ ] bootstrap never installs or mutates system packages

  **QA Scenarios**:
  ```
  Scenario: Local bootstrap contract tests
    Tool: Bash
    Steps: Run `python -m pytest tests/unit/test_bootstrap_contract.py tests/integration/test_bootstrap_failures.py -q`
    Expected: Tests verify runtime discovery fields, failure taxonomy, and the use of `--system-site-packages`
    Evidence: .sisyphus/evidence/task-16-bootstrap.txt

  Scenario: Bootstrap CLI writes environment snapshot
    Tool: Bash
    Steps: Run `python -m inference_profile.cli bootstrap-env --gpu-id 0 --output-root /tmp/ip-bootstrap`
    Expected: `/tmp/ip-bootstrap/environment.json` exists and manifest stage `bootstrap` is `success` on a CUDA-capable machine
    Evidence: .sisyphus/evidence/task-16-bootstrap-cli.txt
  ```

  **Commit**: YES | Message: `feat(remote): add bootstrap environment validation` | Files: `inference-profile/inference_profile/bootstrap.py`, `inference-profile/tests/unit/test_bootstrap_contract.py`, `inference-profile/tests/integration/test_bootstrap_failures.py`


- [ ] 9. Reduce raw profiling events into canonical prefill/decode/PCIe summaries

  **What to do**: Add `inference_profile/profile_reducer.py` to convert raw event rows into four canonical summary files: `derived/model_constants.csv`, `derived/prefill_summary.csv`, `derived/decode_summary.csv`, and `derived/pcie_summary.csv`. Use exact summary rules: `prefill_max_gemm_us = max(duration_us)` across all six prefill ops and timed iterations per `model × N`; `prefill_workspace_bytes = max(dynamic_workspace_bytes)` across the same rows; `prefill_parked_activation_bytes = max(output_bytes)` across the same rows; `decode_max_gemv_us = max(duration_us)` across the six linear decode ops per `model × N × L`; `attention_fetch_compute_us` and `reduction_overhead_us` come from their dedicated timing buckets; `decode_workspace_bytes = max(dynamic_workspace_bytes)` across all decode rows; `decode_parked_activation_bytes = max(output_bytes)` across all decode rows; `pcie_exposed_us` uses the formula fixed in T8; `effective_gbps = (kv_block_bytes / 1e9) / (transfer_only_us / 1e6)` is written only to `derived/pcie_summary.csv`. Preserve only microseconds and bytes in raw outputs.
  **Must NOT do**: Do not carry host wall-clock values into the summary tables. Do not mix raw rows from failed points into successful summaries.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: this is the contract bridge between raw profiler outputs and the simulator
  - Skills: `[]` - no extra skill injection is required
  - Omitted: `[]` - no specialized skill adds value here

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: T10-T15, T18 | Blocked By: T6, T7, T8

  **References**:
  - Pattern: `NVBenchSuite/analysis/profile_inference_acu_gbu.py` - structured reduction of profiler CSVs into analysis-ready summaries
  - Pattern: `NVBenchSuite/analysis/plot_opt_single_layer_prefill.py` - repeated-run aggregation and plot-ready summary creation

  **Acceptance Criteria**:
  - [ ] the four canonical summary files are emitted with fixed column order and units
  - [ ] successful and failed point summaries are separated deterministically by manifest status
  - [ ] derived summary values match raw event maxima for fixture inputs

  **QA Scenarios**:
  ```
  Scenario: Reducer computes exact maxima and workspace values
    Tool: Bash
    Steps: Run `python -m pytest tests/unit/test_profile_reducer.py -q`
    Expected: Fixture raw events reduce to exact expected `prefill_max_gemm_us`, `decode_max_gemv_us`, and workspace/activation byte maxima
    Evidence: .sisyphus/evidence/task-9-reducer.txt

  Scenario: Failed raw points do not contaminate summaries
    Tool: Bash
    Steps: Run `python -m pytest tests/integration/test_profile_reducer_failure_filter.py -q`
    Expected: Rows from `profile_oom` and `profile_failed` points are excluded from success summaries and tracked separately
    Evidence: .sisyphus/evidence/task-9-reducer-failures.txt
  ```

  **Commit**: YES | Message: `feat(profile): add raw event reducer` | Files: `inference-profile/inference_profile/profile_reducer.py`, `inference-profile/tests/unit/test_profile_reducer.py`, `inference-profile/tests/integration/test_profile_reducer_failure_filter.py`

- [ ] 10. Implement the `profile` CLI stage and local profiling bundle orchestration

  **What to do**: Wire `python -m inference_profile.cli profile` so it: (1) ensures `inspect-model` results exist for each model, (2) launches subprocess-isolated prefill/decode/PCIe points, (3) writes raw event CSVs into `raw/`, (4) reduces them into the canonical summary CSVs, and (5) updates `run_manifest.json` after every point and stage. The command must accept `--models`, `--chunk-sizes`, `--sequence-lengths`, `--warmup`, `--iterations`, `--gpu-id`, `--cache-root`, and `--output-root`. The parent process must create `logs/profile-*.log` files and emit `environment.json` once per run.
  **Must NOT do**: Do not execute simulation, plotting, or remote SSH in this task. Do not hide failed points by returning overall success when summaries are incomplete.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: this is the main local execution stage tying together assets, workers, reducers, and manifests
  - Skills: `[]` - no extra skill injection is required
  - Omitted: `[]` - no specialized skill adds value here

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: T11-T15, T18-T19 | Blocked By: T2, T9

  **References**:
  - Pattern: `NVBenchSuite/scripts/run_inference_profiling.sh` - profiling-run orchestration pattern to adapt
  - Pattern: `NVBenchSuite/scripts/run_exp_a_all_waves.py` - per-point execution bookkeeping and manifest-style status handling
  - Pattern: `MobiCom26-Eval/evaluation/two-level-scheduling-simulator/metrics_writer.py` - stage summary writing responsibilities

  **Acceptance Criteria**:
  - [ ] `profile` produces `raw/prefill_events.csv`, `raw/decode_events.csv`, `raw/pcie_events.csv`, and the four canonical summary CSVs
  - [ ] `run_manifest.json` records per-point counts for successes, OOMs, and failures
  - [ ] one local smoke run (`opt-125m`, `N=64`, `L=1024`) completes end-to-end without invoking simulation or report generation

  **QA Scenarios**:
  ```
  Scenario: Local profiling smoke bundle is complete
    Tool: Bash
    Steps: Run `python -m inference_profile.cli profile --models facebook/opt-125m --chunk-sizes 64 --sequence-lengths 1024 --warmup 3 --iterations 5 --gpu-id 0 --output-root /tmp/ip-profile`
    Expected: `/tmp/ip-profile/raw/` contains all three raw CSVs, `/tmp/ip-profile/derived/` contains all four summary CSVs, and `run_manifest.json` shows stage `profile=success`
    Evidence: .sisyphus/evidence/task-10-profile-smoke.txt

  Scenario: Profiling stage preserves partial failures
    Tool: Bash
    Steps: Run `python -m pytest tests/integration/test_profile_cli_partial_failures.py -q`
    Expected: Failed points remain visible in the manifest and logs while successful points still produce summary rows
    Evidence: .sisyphus/evidence/task-10-profile-failures.txt
  ```

  **Commit**: YES | Message: `feat(profile): add profiling stage orchestration` | Files: `inference-profile/inference_profile/cli.py`, `inference-profile/tests/integration/test_profile_cli_smoke.py`, `inference-profile/tests/integration/test_profile_cli_partial_failures.py`

- [ ] 11. Assemble normalized trace inputs and profile summaries into simulator-ready tables

  **What to do**: Extend `validate-traces` and add a simulator-input assembly helper that reads `derived/model_constants.csv`, `derived/prefill_summary.csv`, `derived/decode_summary.csv`, `derived/pcie_summary.csv`, and `derived/normalized_ldpc_trace.csv`, then writes `derived/simulation_inputs.csv` plus `raw/trace_inspection.json`. `simulation_inputs.csv` must include one row per `model × N × L` with all profile summaries, `total_memory_bytes`, `vram_ceiling_bytes`, and `kv_bytes_per_token_all_layers = 4 * hidden_size * num_hidden_layers`. This task also fixes the exact interval semantics used later by the simulator: every row in `normalized_ldpc_trace.csv` represents the interval `[time_ms, time_ms + slot_duration_ms)`.
  **Must NOT do**: Do not run the greedy scheduler here. Do not infer missing summary fields from unrelated rows.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: the simulator-ready adapter locks the exact bridge between traces, profiles, and hardware ceilings
  - Skills: `[]` - no extra skill injection is required
  - Omitted: `[]` - no specialized skill adds value here

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: T12-T15, T18-T19 | Blocked By: T2, T4, T9, T10

  **References**:
  - Pattern: `MobiCom26-Eval/evaluation/two-level-scheduling-simulator/trace_loader.py` - interval semantics and row-driven time progression
  - Pattern: `MobiCom26-Eval/evaluation/two-level-scheduling-simulator/metrics_writer.py` - simulator input/output handoff responsibilities

  **Acceptance Criteria**:
  - [ ] `simulation_inputs.csv` exists and contains every successful `model × N × L` row with all required profile and VRAM fields
  - [ ] `kv_bytes_per_token_all_layers` equals `4 * hidden_size * num_hidden_layers`
  - [ ] `normalized_ldpc_trace.csv` rows are treated as half-open time intervals with deterministic `slot_duration_ms`

  **QA Scenarios**:
  ```
  Scenario: Simulation input table is complete and deterministic
    Tool: Bash
    Steps: Run `python -m pytest tests/unit/test_simulation_inputs.py tests/integration/test_simulation_input_cli.py -q`
    Expected: Tests verify the exact joined columns, row counts, and `kv_bytes_per_token_all_layers` formula
    Evidence: .sisyphus/evidence/task-11-sim-inputs.txt

  Scenario: Trace interval semantics are fixed
    Tool: Bash
    Steps: Run `python -m pytest tests/unit/test_trace_interval_semantics.py -q`
    Expected: Tests confirm that each normalized trace row maps to `[time_ms, time_ms + slot_duration_ms)` and the last row uses the median positive delta
    Evidence: .sisyphus/evidence/task-11-trace-intervals.txt
  ```

  **Commit**: YES | Message: `feat(sim): add simulation input assembly` | Files: `inference-profile/inference_profile/trace_contract.py`, `inference-profile/inference_profile/profile_reducer.py`, `inference-profile/tests/unit/test_simulation_inputs.py`, `inference-profile/tests/unit/test_trace_interval_semantics.py`, `inference-profile/tests/integration/test_simulation_input_cli.py`

- [ ] 12. Implement the deterministic greedy scheduler for TTFT, TPOT, and VRAM runway

  **What to do**: Add `inference_profile/simulator.py` implementing a math-only discrete-event scheduler over `normalized_ldpc_trace.csv`. Idle gaps are intervals where `sm_utilization == 0`. For prefill, set `chunk_count = ceil(4096 / N)` and `prefill_atom_count = 6 * num_hidden_layers` per chunk; each atom consumes `prefill_max_gemm_us`. Schedule those atoms greedily across idle gaps. If a chunk is interrupted because a gap closes, require `weight_bytes + prefill_parked_activation_bytes <= vram_ceiling_bytes`; otherwise mark the row failed with `parked_activation_oom`. TTFT is the simulation timestamp when the last prefill atom of the last chunk finishes. For decode at each `L`, define per-token atoms as, per layer: six GEMV atoms at `decode_max_gemv_us`, one `attention_fetch_compute_us` atom, one `reduction_overhead_us` atom, and for PCIe mode `ceil(L / N)` exposed transfer atoms at `pcie_exposed_us`. Compute `decode_runway_bytes = max(0, vram_ceiling_bytes - weight_bytes - decode_workspace_bytes - decode_parked_activation_bytes)` and `decode_runway_tokens = floor(decode_runway_bytes / kv_bytes_per_token_all_layers)`. Export both `tpot_ms_vram` and `tpot_ms_pcie_async` as the simulated elapsed milliseconds to fit one decode token after TTFT.
  **Must NOT do**: Do not run PyTorch ops or allocate tensors in this task. Do not average across trace rows or replace gaps with a synthetic mean-gap model.

  **Recommended Agent Profile**:
  - Category: `ultrabrain` - Reason: this task locks the exact event model and SLA math for the whole pipeline
  - Skills: `[]` - no extra skill injection is required
  - Omitted: `[]` - no specialized skill adds value here

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: T13-T15, T18-T19 | Blocked By: T11

  **References**:
  - Pattern: `MobiCom26-Eval/evaluation/two-level-scheduling-simulator/run_trace_driven_eval.py` - trace-driven stepping and output expectations to adapt, minus modulo replay/randomness
  - Pattern: `MobiCom26-Eval/evaluation/two-level-scheduling-simulator/validate_simulation.py` - simulation validation mindset and summary checks

  **Acceptance Criteria**:
  - [ ] simulator code imports without torch/cuda dependencies
  - [ ] TTFT is emitted as the timestamp of the final prefill atom completion
  - [ ] `decode_runway_bytes`, `decode_runway_tokens`, `tpot_ms_vram`, and `tpot_ms_pcie_async` are exported for every successful `model × N × L` row

  **QA Scenarios**:
  ```
  Scenario: Scheduler semantics on a tiny synthetic trace
    Tool: Bash
    Steps: Run `python -m pytest tests/unit/test_scheduler_semantics.py -q`
    Expected: Fixtures verify greedy gap fitting, TTFT timestamping, and decode-token timing for both VRAM and PCIe modes
    Evidence: .sisyphus/evidence/task-12-scheduler.txt

  Scenario: Simulation fails closed on impossible parking
    Tool: Bash
    Steps: Run `python -m pytest tests/integration/test_simulation_failfast.py -q`
    Expected: A fixture with `weight_bytes + prefill_parked_activation_bytes > vram_ceiling_bytes` produces a typed failure row and no false TTFT/TPOT success values
    Evidence: .sisyphus/evidence/task-12-simulation-failfast.txt
  ```

  **Commit**: YES | Message: `feat(sim): add deterministic greedy scheduler` | Files: `inference-profile/inference_profile/simulator.py`, `inference-profile/tests/unit/test_scheduler_semantics.py`, `inference-profile/tests/integration/test_simulation_failfast.py`


- [x] 5. Build the spawned profiling worker and failure taxonomy

  **What to do**: Add `inference_profile/worker_profile_point.py` and a parent helper that serializes one benchmark-point spec to JSON, launches a fresh `spawn` worker process, captures stdout/stderr to `logs/`, enforces per-point timeouts, and maps exceptions to typed statuses. The worker must always `torch.cuda.synchronize()`, flush its raw CSV rows, call `torch.cuda.empty_cache()`, and exit. The parent must mark `profile_oom` specifically for CUDA OOM and `profile_failed` for any other worker exception.
  **Must NOT do**: Do not run multiple `(model, N, L, phase)` points in the same long-lived CUDA process. Do not swallow worker exceptions.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: process isolation, timeout handling, and typed failure semantics are operationally critical
  - Skills: `[]` - no extra skill injection is required
  - Omitted: `[]` - no specialized skill adds value here

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: T6-T10, T18 | Blocked By: T1

  **References**:
  - Pattern: `NVBenchSuite/scripts/run_exp_a_all_waves.py` - subprocess-oriented orchestration and per-run status handling
  - Pattern: `NVBenchSuite/scripts/run_opt_single_layer_prefill_profile.py` - per-run raw event/final summary flow

  **Acceptance Criteria**:
  - [ ] a worker spec can launch a fresh subprocess and return structured success/failure payloads
  - [ ] CUDA OOM is classified as `profile_oom` and preserves partial logs
  - [ ] parent orchestration records timeout, exit code, and stderr path for failed points

  **QA Scenarios**:
  ```
  Scenario: Mocked worker exception preserves typed failure
    Tool: Bash
    Steps: Run `python -m pytest tests/unit/test_worker_runner.py tests/integration/test_worker_failure_capture.py -q`
    Expected: Tests verify `profile_oom`, `profile_failed`, and timeout status mapping with preserved log paths
    Evidence: .sisyphus/evidence/task-5-worker-failures.txt

  Scenario: Spawned worker path is used instead of in-process execution
    Tool: Bash
    Steps: Run `python -m pytest tests/unit/test_spawn_isolation.py -q`
    Expected: Test asserts the parent uses `spawn` and never invokes the profiling callable inline
    Evidence: .sisyphus/evidence/task-5-spawn.txt
  ```

  **Commit**: YES | Message: `feat(profile): add spawned profiling worker` | Files: `inference-profile/inference_profile/worker_profile_point.py`, `inference-profile/tests/unit/test_worker_runner.py`, `inference-profile/tests/unit/test_spawn_isolation.py`, `inference-profile/tests/integration/test_worker_failure_capture.py`

- [x] 6. Implement the prefill CUDA-event microbenchmark for six layer GEMMs

  **What to do**: Add `inference_profile/prefill_profile.py` to profile one isolated OPT layer at batch size `1` for each `N ∈ {64,128,256,512,1024}`. Materialize deterministic FP16 inputs of shape `[1, N, hidden_size]`, then time the six primary linear ops individually: `q_proj`, `k_proj`, `v_proj`, `out_proj`, `fc1`, `fc2`. Use `torch.cuda.Event(enable_timing=True)` start/end pairs per timed iteration, `torch.cuda.synchronize()` before reading elapsed time, and `torch.cuda.reset_peak_memory_stats()` plus `torch.cuda.max_memory_allocated()` to compute `dynamic_workspace_bytes = peak - baseline`. Record raw rows to `raw/prefill_events.csv`; the reducer will later compute `prefill_max_gemm_us = max(duration_us)` across all six ops and timed iterations. Compute `parked_activation_bytes` deterministically as `max(output.numel() * output.element_size())`, which should be the `fc1` output `[1, N, ffn_dim]` for successful runs.
  **Must NOT do**: Do not run full self-attention, softmax, or whole-layer forward passes here. Do not use host `perf_counter` for microbenchmark values.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: CUDA-event timing and exact per-op memory accounting must be correct
  - Skills: `[]` - no extra skill injection is required
  - Omitted: `[]` - no specialized skill adds value here

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: T9-T15, T18 | Blocked By: T3, T5

  **References**:
  - Pattern: `NVBenchSuite/scripts/run_inference_nvtx.py` - warmup, synchronization, and deterministic phase execution structure
  - Pattern: `NVBenchSuite/python/nvbenchsuite/opt_single_layer_profile.py` - isolated OPT layer decomposition to follow for tensor shapes

  **Acceptance Criteria**:
  - [ ] `raw/prefill_events.csv` contains one row per `model × N × op_name × timed_iteration`
  - [ ] every row records `duration_us`, `baseline_vram_bytes`, `peak_vram_bytes`, `dynamic_workspace_bytes`, and `output_bytes`
  - [ ] a 125M smoke run completes for `N=64` without whole-layer forward execution

  **QA Scenarios**:
  ```
  Scenario: GPU smoke for one prefill point
    Tool: Bash
    Steps: Run `python -m pytest -m gpu_smoke tests/gpu/test_prefill_profile_smoke.py -q`
    Expected: The smoke test emits non-empty `raw/prefill_events.csv` rows with positive `duration_us` and non-negative workspace bytes
    Evidence: .sisyphus/evidence/task-6-prefill-smoke.txt

  Scenario: Prefill schema and parked activation math
    Tool: Bash
    Steps: Run `python -m pytest tests/unit/test_prefill_schema.py tests/unit/test_prefill_parked_activation.py -q`
    Expected: Tests verify all six op names, exact CSV columns, and `fc1`-sized parked activation bytes for fixed fixtures
    Evidence: .sisyphus/evidence/task-6-prefill-schema.txt
  ```

  **Commit**: YES | Message: `feat(profile): add prefill cuda-event microbenchmark` | Files: `inference-profile/inference_profile/prefill_profile.py`, `inference-profile/tests/unit/test_prefill_schema.py`, `inference-profile/tests/unit/test_prefill_parked_activation.py`, `inference-profile/tests/gpu/test_prefill_profile_smoke.py`

- [ ] 7. Implement the decode CUDA-event microbenchmark with blockwise flash-decoding reduction

  **What to do**: Add `inference_profile/decode_profile.py` to profile one-token decode at batch size `1` for every `L ∈ {1024,2048,4096,8192}` and every block size `N ∈ {64,128,256,512,1024}`. Time the six standard linear ops individually (`q_proj`, `k_proj`, `v_proj`, `out_proj`, `fc1`, `fc2`) on `[1,1,hidden_size]` inputs. Separately time a flash-decoding-style block loop over a resident KV cache shaped `[num_heads, L, head_dim]` using block size `N`: for each block compute `m_i`, `l_i`, and `o_i` from `q·k_block^T`; then time the final reduction phase that combines block statistics into one context vector. Emit raw rows to `raw/decode_events.csv` with op type `gemv`, `attention_fetch_compute`, or `reduction_overhead`. Record `decode_workspace_bytes` as the maximum `dynamic_workspace_bytes` observed across all decode operations and `decode_parked_activation_bytes` as the final `[1,1,hidden_size]` output size.
  **Must NOT do**: Do not call `generate()` or autoregressive loops. Do not collapse attention and reduction into one timing bucket.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: blockwise attention timing and reduction semantics are the hardest profiling component
  - Skills: `[]` - no extra skill injection is required
  - Omitted: `[]` - no specialized skill adds value here

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: T9-T15, T18 | Blocked By: T3, T5

  **References**:
  - Pattern: `NVBenchSuite/scripts/run_inference_nvtx.py` - decode-stage isolation and reuse of prepared KV state
  - Pattern: `NVBenchSuite/python/nvbenchsuite/opt_single_layer_profile.py` - layer-local tensor decomposition pattern

  **Acceptance Criteria**:
  - [ ] `raw/decode_events.csv` contains rows for all six linear ops plus `attention_fetch_compute` and `reduction_overhead`
  - [ ] `decode_max_gemv_us` is derivable as `max(duration_us)` over the six linear ops only
  - [ ] a 125M smoke run completes for `(N=64, L=1024)` and records separate attention/reduction durations

  **QA Scenarios**:
  ```
  Scenario: GPU smoke for one decode point
    Tool: Bash
    Steps: Run `python -m pytest -m gpu_smoke tests/gpu/test_decode_profile_smoke.py -q`
    Expected: The smoke test emits separate `gemv`, `attention_fetch_compute`, and `reduction_overhead` rows with positive `duration_us`
    Evidence: .sisyphus/evidence/task-7-decode-smoke.txt

  Scenario: Flash-decoding reduction math is stable
    Tool: Bash
    Steps: Run `python -m pytest tests/unit/test_decode_reduction_contract.py tests/unit/test_decode_schema.py -q`
    Expected: Tests verify blockwise `m_i/l_i/o_i` aggregation shape contracts and the exact raw CSV schema
    Evidence: .sisyphus/evidence/task-7-decode-schema.txt
  ```

  **Commit**: YES | Message: `feat(profile): add decode cuda-event microbenchmark` | Files: `inference-profile/inference_profile/decode_profile.py`, `inference-profile/tests/unit/test_decode_reduction_contract.py`, `inference-profile/tests/unit/test_decode_schema.py`, `inference-profile/tests/gpu/test_decode_profile_smoke.py`

- [ ] 8. Implement the PCIe overlap profiler for per-layer KV block transfers

  **What to do**: Add `inference_profile/pcie_profile.py` to profile effective H2D DMA for one per-layer KV block of `N` tokens, where `kv_block_bytes = 2 * N * num_attention_heads * head_dim * 2` for K/V FP16 tensors. Allocate the host tensor with pinned memory, issue the H2D copy on a dedicated transfer stream with `non_blocking=True`, and time it with CUDA events. Then time an overlapped copy+compute run using a separate compute stream running a dummy `fc1`-shaped GEMV (`[1, hidden_size] × [hidden_size, ffn_dim]`) so the pipeline can derive `transfer_only_us`, `overlap_total_us`, `dummy_compute_us`, and `exposed_transfer_us = max(0, overlap_total_us - dummy_compute_us)`. Emit rows to `raw/pcie_events.csv`; compute `effective_gbps` later in `derived/pcie_summary.csv` only.
  **Must NOT do**: Do not claim PCIe link utilization from CUDA events. Do not use pageable host memory.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: stream overlap and transfer accounting are precision-sensitive but operationally bounded
  - Skills: `[]` - no extra skill injection is required
  - Omitted: `[]` - no specialized skill adds value here

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: T9-T15, T18 | Blocked By: T3, T5

  **References**:
  - Pattern: `DeviceEmulator/tests/python/bench/bench_greenctx_throughput.py` - benchmark-style measurement organization
  - Pattern: `NVBenchSuite/scripts/run_inference_nvtx.py` - synchronization discipline around CUDA work

  **Acceptance Criteria**:
  - [ ] `raw/pcie_events.csv` contains `transfer_only_us`, `overlap_total_us`, `dummy_compute_us`, and `exposed_transfer_us`
  - [ ] host tensors are pinned and copies use `non_blocking=True`
  - [ ] a 125M smoke run completes for `N=64` and reports non-negative exposed transfer time

  **QA Scenarios**:
  ```
  Scenario: GPU smoke for one PCIe overlap point
    Tool: Bash
    Steps: Run `python -m pytest -m gpu_smoke tests/gpu/test_pcie_profile_smoke.py -q`
    Expected: The smoke test emits non-empty `raw/pcie_events.csv` rows with pinned-memory transfer metadata and positive transfer timing
    Evidence: .sisyphus/evidence/task-8-pcie-smoke.txt

  Scenario: PCIe schema and exposed-latency math
    Tool: Bash
    Steps: Run `python -m pytest tests/unit/test_pcie_schema.py tests/unit/test_pcie_exposed_latency.py -q`
    Expected: Tests verify the KV block byte formula and `exposed_transfer_us = max(0, overlap_total_us - dummy_compute_us)`
    Evidence: .sisyphus/evidence/task-8-pcie-schema.txt
  ```

  **Commit**: YES | Message: `feat(profile): add pcie overlap profiler` | Files: `inference-profile/inference_profile/pcie_profile.py`, `inference-profile/tests/unit/test_pcie_schema.py`, `inference-profile/tests/unit/test_pcie_exposed_latency.py`, `inference-profile/tests/gpu/test_pcie_profile_smoke.py`


- [x] 1. Scaffold the standalone `inference-profile` package and stageable CLI

  **What to do**: Populate the empty project root with `pyproject.toml`, `README.md`, `inference_profile/__init__.py`, `inference_profile/cli.py`, `inference_profile/constants.py`, and the initial `tests/` tree. Use standard-library `argparse` for subcommands `bootstrap-env`, `inspect-model`, `validate-traces`, `profile`, `simulate`, `report`, `verify-bundle`, and `run-all`. Encode the fixed model list, chunk sizes, sequence lengths, remote host, remote root, local fetch root, and `sshpass` file path in `constants.py`.
  **Must NOT do**: Do not implement profiling, simulation, or remote execution logic in this task.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: bounded scaffold and CLI contract work with deterministic tests
  - Skills: `[]` - no extra skill injection is required
  - Omitted: `[]` - no specialized skill adds value here

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: T2-T20 | Blocked By: none

  **References**:
  - Pattern: `NVBenchSuite/README.md` - repo-level benchmark suite layout and entrypoint conventions
  - Pattern: `NVBenchSuite/scripts/run_opt_single_layer_prefill_profile.py` - argument parsing and run-oriented CLI style
  - Pattern: `MobiCom26-Eval/evaluation/two-level-scheduling-simulator/run_trace_driven_eval.py` - stageable config-first simulation CLI pattern

  **Acceptance Criteria**:
  - [ ] `python -m inference_profile.cli --help` lists the eight fixed subcommands
  - [ ] `constants.py` contains the exact requested OPT model IDs, chunk sizes, sequence lengths, remote host, and remote trace defaults
  - [ ] `pyproject.toml` registers pytest markers `gpu_smoke` and `remote_mock`

  **QA Scenarios**:
  ```
  Scenario: CLI contract is present and stable
    Tool: Bash
    Steps: Run `python -m inference_profile.cli --help`
    Expected: Help text includes `bootstrap-env`, `inspect-model`, `validate-traces`, `profile`, `simulate`, `report`, `verify-bundle`, and `run-all`
    Evidence: .sisyphus/evidence/task-1-cli-help.txt

  Scenario: Scaffold tests enforce fixed constants
    Tool: Bash
    Steps: Run `python -m pytest tests/unit/test_cli_contract.py tests/unit/test_constants.py -q`
    Expected: Tests pass and assert the exact model/chunk/sequence defaults plus remote path constants
    Evidence: .sisyphus/evidence/task-1-scaffold-tests.txt
  ```

  **Commit**: YES | Message: `chore(profile): scaffold package and cli contracts` | Files: `inference-profile/pyproject.toml`, `inference-profile/inference_profile/cli.py`, `inference-profile/inference_profile/constants.py`, `inference-profile/tests/unit/test_cli_contract.py`, `inference-profile/tests/unit/test_constants.py`

- [x] 2. Define the run-bundle layout, manifest schema, and status taxonomy

  **What to do**: Implement `inference_profile/paths.py` and `inference_profile/manifests.py` to create `runs/<run_id>/{logs,raw,derived,plots,checksums}` plus root files `run_manifest.json`, `environment.json`, `ran_inference_profiling_report.md`, and `checksums/sha256sums.txt`. Freeze status values to `bootstrap_failed`, `validation_failed`, `profile_oom`, `profile_failed`, `simulate_failed`, `report_failed`, `ssh_failed`, `fetch_failed`, `success`. Add helpers that atomically update manifest stage status and write deterministic SHA256 manifests.
  **Must NOT do**: Do not place any output outside the run root. Do not compute checksums from mutable temp files.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: contract-heavy artifact and status design work
  - Skills: `[]` - no extra skill injection is required
  - Omitted: `[]` - no specialized skill adds value here

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: T10-T20 | Blocked By: T1

  **References**:
  - Pattern: `NVBenchSuite/data/opt_single_layer_prefill/raw/gpu0/facebook_opt-125m/layer_manifest.json` - existing run-manifest shape to adapt
  - Pattern: `MobiCom26-Eval/evaluation/two-level-scheduling-simulator/metrics_writer.py` - metrics/output writer responsibilities
  - Pattern: `MobiCom26-Eval/evaluation/two-level-scheduling-simulator/results/validation_report.txt` - validation artifact naming pattern

  **Acceptance Criteria**:
  - [ ] `init_run_bundle()` creates the fixed directory tree and root manifest files under a timestamped `run_id`
  - [ ] `run_manifest.json` records status transitions without overwriting prior stage history
  - [ ] `sha256sums.txt` is reproducible for identical file contents and relative paths

  **QA Scenarios**:
  ```
  Scenario: Bundle layout is deterministic
    Tool: Bash
    Steps: Run `python -m pytest tests/unit/test_paths.py tests/unit/test_manifest_schema.py -q`
    Expected: Tests confirm the exact directory tree, file names, and status taxonomy
    Evidence: .sisyphus/evidence/task-2-bundle-layout.txt

  Scenario: Checksum manifest is stable
    Tool: Bash
    Steps: Run `python -m pytest tests/unit/test_checksums.py -q`
    Expected: Same files always produce the same relative-path `sha256sums.txt` entries in sorted order
    Evidence: .sisyphus/evidence/task-2-checksums.txt
  ```

  **Commit**: YES | Message: `feat(profile): add run bundle manifests and paths` | Files: `inference-profile/inference_profile/paths.py`, `inference-profile/inference_profile/manifests.py`, `inference-profile/tests/unit/test_paths.py`, `inference-profile/tests/unit/test_manifest_schema.py`, `inference-profile/tests/unit/test_checksums.py`

- [x] 3. Implement OPT config inspection, layer-only asset resolution, and weight-byte estimation

  **What to do**: Add `inference_profile/opt_assets.py` with one public flow: `inspect_model(model_id, cache_root, output_root)`. It must download `config.json`; then attempt to fetch `model.safetensors.index.json` or `pytorch_model.bin.index.json`; resolve the middle decoder layer key prefix `model.decoder.layers.{layer_index}.`; fetch only the referenced shard files when indexed shards exist; instantiate just that layer in FP16 on CPU first, then move to GPU inside profiling workers. If the repo only exposes a monolithic checkpoint, do not download it; instead generate deterministic seeded FP16 tensors with the exact layer shapes and write `asset_source="synthetic_fallback"` plus a reason into the manifest. Also compute full-model analytical FP16 weight bytes from config (`embeddings + optional project_in/project_out + all decoder layers + final norms`, with tied LM head not double-counted).
  **Must NOT do**: Do not call `AutoModel.from_pretrained()` or `generate()`. Do not intentionally download a whole-model monolithic checkpoint file.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: Hugging Face asset resolution, exact OPT shape math, and fallback policy must be locked down
  - Skills: `[]` - no extra skill injection is required
  - Omitted: `[]` - no specialized skill adds value here

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: T6-T15 | Blocked By: T1

  **References**:
  - Pattern: `NVBenchSuite/python/nvbenchsuite/opt_single_layer_profile.py` - isolated OPT layer structure and middle-layer strategy
  - Pattern: `NVBenchSuite/python/nvbenchsuite/inference.py` - model metadata helpers and VRAM estimation ideas
  - External: `https://huggingface.co/facebook/opt-125m/blob/main/config.json` - required config metadata source shape

  **Acceptance Criteria**:
  - [ ] `inspect-model` writes `raw/model_constants.json` with `num_hidden_layers`, `hidden_size`, `num_attention_heads`, `ffn_dim`, `layer_index`, `layer_weight_bytes`, `total_weight_bytes_fp16`, and `vram_ceiling_bytes`
  - [ ] indexed-shard repositories download only config/index plus referenced layer shard files
  - [ ] monolithic-checkpoint repositories produce `synthetic_fallback` manifest entries instead of downloading full model weights

  **QA Scenarios**:
  ```
  Scenario: Model inspection exports exact constants without full-model load
    Tool: Bash
    Steps: Run `python -m inference_profile.cli inspect-model --model facebook/opt-125m --output-root /tmp/ip-inspect`
    Expected: `/tmp/ip-inspect/raw/model_constants.json` exists and the manifest records either `layer_shard` or `synthetic_fallback`, never `full_model_download`
    Evidence: .sisyphus/evidence/task-3-inspect-model.txt

  Scenario: Analytical byte estimator is reproducible
    Tool: Bash
    Steps: Run `python -m pytest tests/unit/test_opt_config_derivation.py tests/unit/test_weight_byte_estimator.py -q`
    Expected: Tests verify layer index selection, exact head dimension math, and stable FP16 weight-byte estimates for the fixed OPT list
    Evidence: .sisyphus/evidence/task-3-weight-estimator.txt
  ```

  **Commit**: YES | Message: `feat(profile): add opt asset inspection and byte estimation` | Files: `inference-profile/inference_profile/opt_assets.py`, `inference-profile/tests/unit/test_opt_config_derivation.py`, `inference-profile/tests/unit/test_weight_byte_estimator.py`, `inference-profile/tests/integration/test_inspect_model_cli.py`

- [x] 4. Define the trace contract, primary/secondary inspection rules, and fail-fast normalization

  **What to do**: Add `inference_profile/trace_contract.py` with two accepted primary `ldpc_trace.csv` shapes: (A) already normalized columns `time_ms,sm_utilization`; (B) simulator-style columns `time_slot_sched_ns,sm_count`. Normalize both into `derived/normalized_ldpc_trace.csv` with columns `time_ms,sm_utilization,slot_duration_ms,source_schema`. For schema B use `time_ms = time_slot_sched_ns / 1e6` and `sm_utilization = 100 if sm_count > 0 else 0`. Compute `slot_duration_ms` from forward differences; for the last row use the median positive delta from the trace. Inspect `ran_ctrl_trace.csv` separately for header, row count, monotonicity, and time-unit hints, but never use it in SLA metrics. Emit `raw/trace_inspection.json` plus `raw/validation_errors.csv` on failure.
  **Must NOT do**: Do not auto-repair malformed traces. Do not silently fall back to any bundled local trace. Do not use `ran_ctrl_trace.csv` for simulator capacity.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: schema normalization and failure semantics directly control simulator correctness
  - Skills: `[]` - no extra skill injection is required
  - Omitted: `[]` - no specialized skill adds value here

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: T11-T20 | Blocked By: T1

  **References**:
  - Pattern: `MobiCom26-Eval/evaluation/two-level-scheduling-simulator/trace_loader.py` - minimal trace contract and monotonic time assumptions
  - Pattern: `DeviceEmulator/morphling/runtime/ldpc_trace_adapter.py` - example of adapting richer trace formats into a simpler internal form
  - Pattern: `sionna-rk/plugins/ldpc_cuda/src/nr_ldpc_cuda.c` - producer-side LDPC trace context
  - Pattern: `sionna-rk/ext/openairinterface5g/openair2/LAYER2/NR_MAC_gNB/gNB_scheduler_ulsch.c` - producer-side ran-control trace context

  **Acceptance Criteria**:
  - [ ] `validate-traces` accepts only schema A or schema B for the primary trace and emits `normalized_ldpc_trace.csv`
  - [ ] non-monotonic timestamps, missing required columns, duplicate headers, BOM/corrupt encoding, or negative deltas produce `validation_failed`
  - [ ] `trace_inspection.json` records both primary and secondary trace summaries and whether each is structurally usable

  **QA Scenarios**:
  ```
  Scenario: Valid simulator-style trace normalizes correctly
    Tool: Bash
    Steps: Run `python -m inference_profile.cli validate-traces --ldpc-trace tests/fixtures/ldpc_trace_valid.csv --ran-ctrl-trace tests/fixtures/ran_ctrl_trace_valid.csv --output-root /tmp/ip-trace-ok`
    Expected: `/tmp/ip-trace-ok/derived/normalized_ldpc_trace.csv` exists with `time_ms`, `sm_utilization`, and `slot_duration_ms`; status is `success`
    Evidence: .sisyphus/evidence/task-4-trace-ok.txt

  Scenario: Malformed primary trace fails closed
    Tool: Bash
    Steps: Run `python -m inference_profile.cli validate-traces --ldpc-trace tests/fixtures/ldpc_trace_missing_column.csv --ran-ctrl-trace tests/fixtures/ran_ctrl_trace_valid.csv --output-root /tmp/ip-trace-bad`
    Expected: Command exits non-zero, writes `raw/validation_errors.csv`, and does not create `derived/normalized_ldpc_trace.csv`
    Evidence: .sisyphus/evidence/task-4-trace-bad.txt
  ```

  **Commit**: YES | Message: `feat(profile): add trace contract and normalization` | Files: `inference-profile/inference_profile/trace_contract.py`, `inference-profile/tests/unit/test_trace_contract.py`, `inference-profile/tests/integration/test_validate_traces_cli.py`, `inference-profile/tests/fixtures/ldpc_trace_valid.csv`, `inference-profile/tests/fixtures/ldpc_trace_missing_column.csv`, `inference-profile/tests/fixtures/ran_ctrl_trace_valid.csv`


## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.
- [ ] F1. Plan Compliance Audit — oracle

  **Acceptance Criteria**:
  - [ ] Oracle audits the completed implementation diff and run bundle against T1-T20, Must Have, and Must NOT Have requirements
  - [ ] the audit produces zero unresolved deviations before user approval is requested

  **QA Scenario**:
  ```
  Scenario: Oracle plan-compliance audit
    Tool: Task (oracle)
    Steps: Run an oracle review against the completed implementation diff and final run bundle, using `.sisyphus/plans/ran-inference-profiling.md` as the contract source
    Expected: Oracle returns a pass/fail markdown audit with one line per task and no unresolved deviations
    Evidence: .sisyphus/evidence/f1-plan-compliance.md
  ```

- [ ] F2. Code Quality Review — unspecified-high

  **Acceptance Criteria**:
  - [ ] reviewer checks all changed Python and Bash files for error handling, status propagation, path safety, checksum coverage, secret handling, and timing-domain purity
  - [ ] approval requires zero high-severity findings

  **QA Scenario**:
  ```
  Scenario: Code-quality review
    Tool: Task (unspecified-high)
    Steps: Run a code review over all changed Python and Bash files, explicitly checking the `sshpass -f /mnt/data/dheeraj/dicertation/.ssh_pass` routing, manifest propagation, and timing-domain purity
    Expected: Reviewer returns an approve/reject markdown summary with concrete file-level findings and no high-severity issues on approval
    Evidence: .sisyphus/evidence/f2-code-quality.md
  ```

- [ ] F3. Real Manual QA — unspecified-high (+ playwright if UI is ever introduced; not expected for v1)

  **Acceptance Criteria**:
  - [ ] the full local verification stack passes
  - [ ] the remote smoke command using the user-provided trace paths fetches a local bundle and `verify-bundle` exits `0`

  **QA Scenario**:
  ```
  Scenario: End-to-end QA execution
    Tool: Bash
    Steps: Run the full local verification stack (`python -m pytest tests/unit tests/integration -q`, GPU smoke tests, `inspect-model`, `validate-traces`, `profile`, `simulate`, `report`, `verify-bundle`) and the README remote smoke command using the actual user-provided trace paths
    Expected: All local commands pass, the remote smoke run fetches a bundle locally, and final bundle verification exits `0`
    Evidence: .sisyphus/evidence/f3-real-qa.txt
  ```

- [ ] F4. Scope Fidelity Check — deep

  **Acceptance Criteria**:
  - [ ] reviewer confirms the implementation remains OPT-only, math-only in the simulation stage, and limited to the requested CSV/report/PNG outputs
  - [ ] reviewer confirms there are no alternate trace fallbacks, production-serving features, or full-model downloads

  **QA Scenario**:
  ```
  Scenario: Scope-fidelity review
    Tool: Task (deep)
    Steps: Run a deep review comparing the completed codebase and final artifacts against the original request and the plan’s scope boundaries only
    Expected: Reviewer returns approval only if all scope boundaries remain intact and no out-of-scope work is present
    Evidence: .sisyphus/evidence/f4-scope-fidelity.md
  ```

## Commit Strategy
- `chore(profile): scaffold package and contracts`
- `feat(profile): add manifests, trace validation, and model inspection`
- `feat(profile): add event-timed prefill/decode/pcie profilers`
- `feat(profile): add profile reducer and deterministic simulator`
- `feat(report): add csv export, plots, and markdown report`
- `feat(remote): add bootstrap and sshpass deployment flow`
- `feat(remote): add remote run-all and checksum-verified fetch`
- `docs(profile): add runbook and smoke commands`

## Success Criteria
- All five requested models complete local inspection successfully and emit model constants without intentional whole-model downloads.
- Raw profiling CSVs exist for prefill, decode, and PCIe overlap and contain microsecond event timings plus byte-level VRAM/transfer measurements.
- `derived/ran_inference_profiling_results.csv` exists and includes `survival_vram_bytes`, `decode_runway_bytes`, `decode_runway_tokens`, `ttft_ms`, `tpot_ms_vram`, and `tpot_ms_pcie_async` for every successful `model × N × L` configuration.
- The bundle contains all five PNG plots and `ran_inference_profiling_report.md` with working relative image links.
- The remote smoke run using the user-provided trace paths fetches a complete run directory locally and passes checksum verification.
- Failures are explicit, typed, and preserved in manifests/logs; no silent fallback artifacts are generated.
