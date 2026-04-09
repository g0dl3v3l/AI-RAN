# Single-Layer OPT Prefill ACU/GBU Pipeline

## TL;DR
> **Summary**: Build a new layer-local OPT prefill profiling pipeline that instantiates and profiles only one selected OPT decoder layer by loading the selected layer’s checkpoint tensors and minimal config metadata, then profiles that isolated layer with nested NVTX ranges for requested sub-components, explicit duration metrics, and time-weighted ACU/GBU aggregation across OPT models through 6.7B.
> **Deliverables**:
> - one new capture/replay runner for single-layer prefill profiling
> - one new parser/summary path with duration-normalized, time-weighted ACU/GBU
> - one tidy long-form CSV and one per-model/component summary CSV
> - three fixed publication figures (micro-architecture, compute scaling, memory scaling)
> - targeted pytest coverage and one GPU smoke validation path
> **Effort**: Large
> **Parallel**: YES - 4 waves
> **Critical Path**: contracts/tests → layer capture/replay → duration-normalized aggregation → model sweep runner → figures

## Context
### Original Request
Design and implement a complete system to profile a pure OPT prefill pass at batch size 1 and maximum supported sequence length, isolate a single transformer layer, break that layer into Attention / KV Cache allocation / Normalization / FFN/MLP / Overall Layer, use time-weighted ACU/GBU aggregation only, compute single-layer parameter counts and min/max/mean ranges, and generate three publication-ready plots across OPT models including 6.7B.

### Interview Summary
- Existing repo infrastructure is reusable for whole-model loading, phase execution, NCU export, plotting style, and targeted pytest patterns.
- Existing repo infrastructure is **not** reusable as-is for single-layer attribution; a new layer-local experiment family is required.
- The user explicitly does **not** want to load the full pretrained model. The clean design must therefore shift to **checkpoint-sliced single-layer loading** with a separately defined input contract for the isolated layer.
- The isolated layer input source is fixed to **synthetic tensors generated from config-derived shapes**, not full-model captured activations.
- Default execution assumptions are fixed in this plan so the implementer does not need to make judgment calls.

### Metis Review (gaps addressed)
- Freeze exact component semantics before implementation.
- Freeze exact max-sequence rule, middle-layer rule, and failure policy.
- Treat `KV allocation` as its own measured range and define a cold/warm semantics policy.
- Normalize duration units explicitly before any time weighting.
- Store a dedicated `unattributed` bucket or fail on insufficient component coverage.
- Keep this pipeline separate from Exp A and all existing whole-model CSV schemas.
- Replace full-model capture/replay with a sliced-checkpoint loader and an explicit isolated-layer input source.

## Work Objectives
### Core Objective
Create a reproducible, GPU-executable profiling/analysis pipeline that outputs **time-weighted** ACU/GBU summaries and ranges for one isolated OPT decoder layer and its required sub-components during **prefill only**, across `facebook/opt-125m`, `facebook/opt-350m`, `facebook/opt-1.3b`, and `facebook/opt-6.7b`, without loading the full pretrained model in memory.

### Deliverables
- `NVBenchSuite/scripts/run_opt_single_layer_prefill_profile.py`
- `NVBenchSuite/python/nvbenchsuite/opt_single_layer_profile.py`
- `NVBenchSuite/analysis/plot_opt_single_layer_prefill.py`
- `NVBenchSuite/tests/python/test_opt_single_layer_capture_replay.py`
- `NVBenchSuite/tests/python/test_opt_single_layer_nvtx.py`
- `NVBenchSuite/tests/python/test_opt_single_layer_analysis.py`
- `NVBenchSuite/tests/python/test_opt_single_layer_runner.py`
- raw artifact root: `NVBenchSuite/data/opt_single_layer_prefill/raw/`
- summary data root: `NVBenchSuite/analysis/opt_single_layer_prefill/data/`
- figure root: `NVBenchSuite/analysis/opt_single_layer_prefill/figures/`

### Definition of Done (verifiable conditions with commands)
- `python -m pytest NVBenchSuite/tests/python/test_opt_single_layer_capture_replay.py -q`
- `python -m pytest NVBenchSuite/tests/python/test_opt_single_layer_nvtx.py -q`
- `python -m pytest NVBenchSuite/tests/python/test_opt_single_layer_analysis.py -q`
- `python -m pytest NVBenchSuite/tests/python/test_opt_single_layer_runner.py -q`
- `python -m py_compile NVBenchSuite/scripts/run_opt_single_layer_prefill_profile.py NVBenchSuite/python/nvbenchsuite/opt_single_layer_profile.py NVBenchSuite/analysis/plot_opt_single_layer_prefill.py`
- `python NVBenchSuite/scripts/run_opt_single_layer_prefill_profile.py --model facebook/opt-125m --gpu-id 0 --layer-strategy middle --batch-size 1 --seq-len max --dtype float16 --output-root /tmp/opt_single_layer_smoke`
- `python NVBenchSuite/analysis/plot_opt_single_layer_prefill.py --input /tmp/opt_single_layer_smoke/aggregate/plot_ready_summary.csv --output-root /tmp/opt_single_layer_smoke/plots`

### Must Have
- pure prefill only (`batch_size=1`, exact max supported sequence length)
- single isolated decoder layer only
- synthetic hidden states / masks generated from model config and sequence length only
- requested sub-components only: `attention`, `kv_allocation`, `normalization`, `ffn_mlp`, `overall_layer`
- time-weighted ACU/GBU only
- direct single-layer parameter counts only
- range summaries (`min`, `max`, `mean`) for ACU and GBU per component and per overall layer
- three fixed figure families
- OPT models: `facebook/opt-125m`, `facebook/opt-350m`, `facebook/opt-1.3b`, `facebook/opt-6.7b`
- explicit failure artifact if 6.7B max-length capture is infeasible

### Must NOT Have
- no training workloads
- no decode-phase profiling
- no whole-model post hoc inference of one layer from phase CSVs
- no full-model load as the normal execution path
- no quantization fallback
- no offload/`device_map="auto"` fallback
- no demo/synthetic fallback for final outputs
- no silent omission of failed models
- no extra components beyond the requested public five buckets (QA-only `unattributed` bucket permitted internally)

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed.
- Test decision: TDD with fixture tests first, one GPU smoke run second
- QA policy: every task below ends in exact executable assertions
- Evidence: `.sisyphus/evidence/` paths listed per task are optional but recommended for logs/artifacts

## Execution Strategy
### Parallel Execution Waves
Wave 1: contract tests and schema decisions
Wave 2: sliced layer instantiation and nested NVTX component ranges
Wave 3: parser, duration normalization, time-weighted aggregation, and summaries
Wave 4: runner, model sweep, figures, and final validation

### Dependency Matrix (full, all tasks)
- T1 blocks T2, T3, T4
- T2 blocks T4 and T5
- T3 blocks T5 and T6
- T4 blocks T7
- T5 blocks T7 and T8
- T6 blocks T8
- T7 blocks T9
- T8 blocks T9
- T9 blocks F1-F4

### Agent Dispatch Summary
- Wave 1: 2 tasks → quick / unspecified-high
- Wave 2: 2 tasks → unspecified-high
- Wave 3: 2 tasks → unspecified-high / writing
- Wave 4: 3 tasks → deep / writing / unspecified-high

## TODOs
> Implementation + Test = ONE task. Never separate.

- [x] 1. Lock schema and math contracts with fixture tests

  **What to do**: Create test fixtures and pytest files that define the exact schema, duration normalization, time-weighted ACU/GBU math, middle-layer selection, single-layer parameter counting, and failure-manifest contract before runtime work starts.
  **Must NOT do**: Do not add runtime capture/replay code in this task.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: bounded test scaffolding with deterministic expected outputs
  - Skills: `[]`
  - Omitted: `['frontend-ui-ux']`

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 2,3,4 | Blocked By: none

  **References**:
  - Pattern: `NVBenchSuite/tests/python/test_profile_inference_acu_gbu.py` - fixture-based parser/math tests
  - Pattern: `NVBenchSuite/tests/python/test_run_exp_a_all_waves.py` - runner contract tests
  - Pattern: `NVBenchSuite/tests/python/test_inference.py` - config/metadata test style
  - Pattern: `NVBenchSuite/analysis/profile_inference_acu_gbu.py` - existing duration-weighting parser concepts

  **Acceptance Criteria**:
  - [ ] `NVBenchSuite/tests/python/test_opt_single_layer_analysis.py` exists with mixed-unit duration fixtures and exact time-weighted expected values
  - [ ] `NVBenchSuite/tests/python/test_opt_single_layer_runner.py` exists with failure-manifest and model-list expectations
  - [ ] `NVBenchSuite/tests/python/test_opt_single_layer_capture_replay.py` exists with middle-layer and parameter-count assertions

  **QA Scenarios**:
  ```
  Scenario: Mixed-unit normalization and weighted ACU/GBU math
    Tool: Bash
    Steps: Run `python -m pytest NVBenchSuite/tests/python/test_opt_single_layer_analysis.py -q -k "normalization or weighting"`
    Expected: Fixture rows with `1000 ns`, `2 us`, `0.003 ms` normalize identically and produce exact weighted outputs `acu=0.65`, `gbu=0.775`
    Evidence: .sisyphus/evidence/task-1-weighting.txt

  Scenario: Deterministic middle-layer selection and parameter counting
    Tool: Bash
    Steps: Run `python -m pytest NVBenchSuite/tests/python/test_opt_single_layer_capture_replay.py -q -k "middle_layer or param_count"`
    Expected: Layer index formula and `sum(p.numel())` over the selected layer match exact fixture expectations for all OPT models
    Evidence: .sisyphus/evidence/task-1-layer-selection.txt
  ```

  **Commit**: YES | Message: `test(single-layer): add schema and math fixtures` | Files: new `NVBenchSuite/tests/python/test_opt_single_layer_*.py`

- [x] 2. Implement sliced selected-layer loading and isolated execution core

  **What to do**: Add a new library module that loads only the selected OPT decoder layer’s weights and minimal config metadata from checkpoint shards, instantiates only that layer on one GPU, and executes it in isolation using synthetic hidden states and attention-mask inputs generated from config-derived shapes. Freeze the middle-layer rule as `layer_index = (num_hidden_layers - 1) // 2`.
  **Must NOT do**: Do not load the full pretrained model in the normal profiling path. Do not infer one layer from old phase-level CSVs.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: core capture/replay architecture
  - Skills: `[]`
  - Omitted: `['writing']`

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: 4,5 | Blocked By: 1

  **References**:
  - Pattern: `DeviceEmulator/morphling/utils/hfparser.py` - OPT module metadata and layer naming hints
  - Pattern: `NVBenchSuite/python/nvbenchsuite/inference.py` - OPT config metadata helpers
  - Pattern: `MobiCom26-Eval/evaluation/single-node-ran-control-training/analysis/eval_training_standalone.py` - layer slicing precedent

  **Acceptance Criteria**:
  - [ ] selected layer loader instantiates exactly one decoder layer with the correct weights, dtype, and backend metadata
  - [ ] isolated execution accepts synthetic config-derived inputs and produces numerically stable outputs for repeated runs

  **QA Scenarios**:
  ```
  Scenario: Sliced layer loads only selected tensors
    Tool: Bash
    Steps: Run `python -m pytest NVBenchSuite/tests/python/test_opt_single_layer_capture_replay.py -q -k sliced_loader`
    Expected: Only the selected layer module and its tensors are instantiated; no full-model module tree is loaded
    Evidence: .sisyphus/evidence/task-2-sliced-loader.txt

  Scenario: Smoke run emits isolated layer artifacts
    Tool: Bash
    Steps: Run `python NVBenchSuite/scripts/run_opt_single_layer_prefill_profile.py --model facebook/opt-125m --gpu-id 0 --layer-strategy middle --batch-size 1 --seq-len max --dtype float16 --output-root /tmp/opt_single_layer_smoke`
    Expected: `/tmp/opt_single_layer_smoke/facebook_opt-125m/layer_manifest.json` exists and raw layer-local profiling artifacts are non-empty
    Evidence: .sisyphus/evidence/task-2-smoke.txt
  ```

  **Commit**: YES | Message: `feat(single-layer): add sliced layer loader` | Files: `NVBenchSuite/python/nvbenchsuite/opt_single_layer_profile.py`, `NVBenchSuite/scripts/run_opt_single_layer_prefill_profile.py`

- [x] 3. Add nested NVTX component boundaries and component semantics

  **What to do**: Instrument the isolated layer replay with nested NVTX ranges for `overall_layer`, `attention`, `kv_allocation`, `normalization`, and `ffn_mlp`. Define `normalization` as the union of both layer norms; define `attention` as the attention block excluding the nested `kv_allocation` subrange; define `ffn_mlp` as `fc1 + activation + fc2`; define `kv_allocation` as the explicit cache materialization/update subrange under `use_cache=True` in cold-start replay. Add internal `unattributed` accounting for kernels inside `overall_layer` that are outside the four public child ranges.
  **Must NOT do**: Do not rely on regex-only attribution as the primary component boundary. Do not expose `unattributed` as a public requested component unless coverage fails.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: precise instrumentation and semantics boundary work
  - Skills: `[]`
  - Omitted: `['frontend-ui-ux']`

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: 5 | Blocked By: 1,2

  **References**:
  - Pattern: `NVBenchSuite/python/nvbenchsuite/nvtx_utils.py` - hierarchical NVTX helper and parser behavior
  - Pattern: `NVBenchSuite/tests/python/test_nvtx_utils.py` - hierarchical range parsing examples
  - Pattern: `DeviceEmulator/morphling/utils/hfparser.py` - attention/MLP decomposition hints for OPT modules

  **Acceptance Criteria**:
  - [ ] every measured kernel under `overall_layer` is attributable to a public component or `unattributed`
  - [ ] `unattributed_duration_us / overall_layer_duration_us <= 0.05` for successful runs; otherwise run status becomes invalid with explicit reason

  **QA Scenarios**:
  ```
  Scenario: NVTX hierarchy is balanced and parseable
    Tool: Bash
    Steps: Run `python -m pytest NVBenchSuite/tests/python/test_opt_single_layer_nvtx.py -q`
    Expected: Balanced nested ranges and deterministic ancestry-based mapping to the five buckets
    Evidence: .sisyphus/evidence/task-3-nvtx.txt

  Scenario: Component coverage threshold is enforced
    Tool: Bash
    Steps: Run `python -m pytest NVBenchSuite/tests/python/test_opt_single_layer_analysis.py -q -k unattributed`
    Expected: Runs fail closed when unattributed duration exceeds the threshold
    Evidence: .sisyphus/evidence/task-3-coverage.txt
  ```

  **Commit**: YES | Message: `feat(single-layer): add component nvtx ranges` | Files: `NVBenchSuite/python/nvbenchsuite/opt_single_layer_profile.py`, tests

- [x] 4. Implement parser, duration normalization, and time-weighted aggregation

  **What to do**: Add a new analysis path that parses the new layer-local NCU CSVs, normalizes duration units to microseconds, computes time-weighted ACU/GBU only, and emits raw per-kernel rows plus component-level summaries. Store both `overall_layer_wall_time_us` and `sum_component_kernel_time_us` in summaries.
  **Must NOT do**: Do not allow simple mean or invocation-count mean paths. Do not silently coerce missing durations.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: aggregation semantics and schema creation
  - Skills: `[]`
  - Omitted: `['artistry']`

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 6,7 | Blocked By: 1,2,3

  **References**:
  - Pattern: `NVBenchSuite/analysis/profile_inference_acu_gbu.py` - current ACU/GBU parsing and plot conventions
  - Pattern: `NVBenchSuite/analysis/compute_util_from_nsys.py` - time-weighting concept

  **Acceptance Criteria**:
  - [ ] mixed-unit duration rows normalize to one canonical unit before weighting
  - [ ] public summaries contain exact columns for parameter count, component, acu_min/max/mean, gbu_min/max/mean, duration totals, and status

  **QA Scenarios**:
  ```
  Scenario: Analysis parser enforces duration-only weighting
    Tool: Bash
    Steps: Run `python -m pytest NVBenchSuite/tests/python/test_opt_single_layer_analysis.py -q -k duration_only`
    Expected: Parser rejects missing/invalid duration rows and computes exact weighted values for fixtures
    Evidence: .sisyphus/evidence/task-4-duration-only.txt

  Scenario: Summary schema is stable
    Tool: Bash
    Steps: Run `python -m pytest NVBenchSuite/tests/python/test_opt_single_layer_analysis.py -q -k summary_schema`
    Expected: Summary CSV contains the exact required fields with canonical units
    Evidence: .sisyphus/evidence/task-4-schema.txt
  ```

  **Commit**: YES | Message: `feat(single-layer): add duration weighted parser` | Files: `NVBenchSuite/analysis/plot_opt_single_layer_prefill.py` and/or companion analysis module, tests

- [x] 5. Implement runner, manifest contract, and explicit failure policy

  **What to do**: Build a dedicated runner for the single-layer family that executes one model at a time on one GPU, records environment metadata, and writes append-only event manifests plus a deduplicated final summary. If 6.7B max-length capture fails, emit an explicit failed summary row with attempted settings and error class; do not fall back to quantization/offload.
  **Must NOT do**: Do not reuse Exp A shard manifests or filename-only metadata.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: runner/failure policy and artifact-management contract
  - Skills: `[]`
  - Omitted: `['frontend-ui-ux']`

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: 7 | Blocked By: 1,2,3,4

  **References**:
  - Pattern: `NVBenchSuite/scripts/run_exp_a_all_waves.py` - manifest and status patterns
  - Pattern: `NVBenchSuite/scripts/ncu_rep_to_csv.sh` - NCU export convention

  **Acceptance Criteria**:
  - [ ] every attempted model writes a terminal status row (`completed`, `failed_constraint`, or `failed_runtime`)
  - [ ] no run silently changes precision, backend, or sequence length

  **QA Scenarios**:
  ```
  Scenario: Failure path for 6.7B is explicit
    Tool: Bash
    Steps: Run `python -m pytest NVBenchSuite/tests/python/test_opt_single_layer_runner.py -q -k failure_path`
    Expected: Failure row preserves requested model, seq_len, dtype, backend, and non-empty failure reason
    Evidence: .sisyphus/evidence/task-5-failure-path.txt

  Scenario: Runner smoke emits all core artifacts
    Tool: Bash
    Steps: Run `python NVBenchSuite/scripts/run_opt_single_layer_prefill_profile.py --model facebook/opt-125m --gpu-id 0 --layer-strategy middle --batch-size 1 --seq-len max --dtype float16 --output-root /tmp/opt_single_layer_smoke`
    Expected: raw report, exported CSV, manifest, tidy raw CSV, and summary CSV all exist
    Evidence: .sisyphus/evidence/task-5-runner-smoke.txt
  ```

  **Commit**: YES | Message: `feat(single-layer): add runner and failure manifests` | Files: runner + tests

- [x] 6. Compute single-layer parameter counts and range summaries across models

  **What to do**: Add the summary stage that enumerates parameters directly from the selected layer module, then computes `acu_min/max/mean` and `gbu_min/max/mean` per `(model, component)` over the chosen population: per-kernel rows within the selected layer replay, aggregated over repeated profiling runs for that model/component. Freeze repeats to `n=3` per model/component.
  **Must NOT do**: Do not compute parameter size from total-model counts. Do not mix ranges across different models.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: deterministic summary math once raw parser exists
  - Skills: `[]`
  - Omitted: `['writing']`

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: 7 | Blocked By: 4,5

  **References**:
  - Pattern: `NVBenchSuite/python/nvbenchsuite/inference.py` - OPT config metadata helpers
  - Pattern: `DeviceEmulator/morphling/utils/hfparser.py` - architecture sanity cross-checks

  **Acceptance Criteria**:
  - [ ] parameter counts come from direct selected-layer module enumeration only
  - [ ] summary rows contain three-run min/max/mean fields for ACU and GBU

  **QA Scenarios**:
  ```
  Scenario: Parameter count parity
    Tool: Bash
    Steps: Run `python -m pytest NVBenchSuite/tests/python/test_opt_single_layer_capture_replay.py -q -k parameter_count`
    Expected: Direct layer parameter enumeration matches expected counts for fixture models
    Evidence: .sisyphus/evidence/task-6-param-count.txt

  Scenario: Range summary population is exact
    Tool: Bash
    Steps: Run `python -m pytest NVBenchSuite/tests/python/test_opt_single_layer_analysis.py -q -k range_summary`
    Expected: Summary min/max/mean values match hand-checked fixture runs over `n=3`
    Evidence: .sisyphus/evidence/task-6-ranges.txt
  ```

  **Commit**: YES | Message: `feat(single-layer): add param and range summaries` | Files: summary stage + tests

- [x] 7. Generate the three fixed publication plots

  **What to do**: Create exactly three figure families, all using `NVBenchSuite/analysis/plot_utils.py` styles:
  1. `micro_architecture_opt-1.3b_layer{layer_index}`: ACU vs GBU scatter with mean point and min/max whiskers for `overall_layer`, `attention`, `kv_allocation`, `normalization`, `ffn_mlp`.
  2. `compute_scaling_acu_vs_single_layer_params`: X = `single_layer_param_count`, Y = `acu_mean`, one series per public component, min/max whiskers.
  3. `memory_scaling_gbu_vs_single_layer_params`: X = `single_layer_param_count`, Y = `gbu_mean`, one series per public component, min/max whiskers.
  Save both PNG and PDF for each.
  **Must NOT do**: Do not add extra charts. Do not generate figures from demo data.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: figure contract and publication outputs
  - Skills: `[]`
  - Omitted: `['quick']`

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: 8 | Blocked By: 4,6

  **References**:
  - Pattern: `NVBenchSuite/analysis/plot_utils.py` - paper style and dual output
  - Pattern: `NVBenchSuite/analysis/profile_inference_acu_gbu.py` - scatter/model-grid output conventions

  **Acceptance Criteria**:
  - [ ] exactly three basenames are generated, each as PDF and PNG
  - [ ] basenames and axes match this plan exactly

  **QA Scenarios**:
  ```
  Scenario: Plot generation produces the exact figure set
    Tool: Bash
    Steps: Run `python NVBenchSuite/analysis/plot_opt_single_layer_prefill.py --input /tmp/opt_single_layer_smoke/aggregate/plot_ready_summary.csv --output-root /tmp/opt_single_layer_smoke/plots`
    Expected: The six files exist and are each > 10 KB:
      /tmp/opt_single_layer_smoke/plots/micro_architecture_opt-1.3b_layer11.pdf
      /tmp/opt_single_layer_smoke/plots/micro_architecture_opt-1.3b_layer11.png
      /tmp/opt_single_layer_smoke/plots/compute_scaling_acu_vs_single_layer_params.pdf
      /tmp/opt_single_layer_smoke/plots/compute_scaling_acu_vs_single_layer_params.png
      /tmp/opt_single_layer_smoke/plots/memory_scaling_gbu_vs_single_layer_params.pdf
      /tmp/opt_single_layer_smoke/plots/memory_scaling_gbu_vs_single_layer_params.png
    Evidence: .sisyphus/evidence/task-7-plots.txt

  Scenario: Plot basenames are fixed
    Tool: Bash
    Steps: Run `python -m pytest NVBenchSuite/tests/python/test_opt_single_layer_analysis.py -q -k plot_contract`
    Expected: Plot contract tests assert exact basenames and required columns
    Evidence: .sisyphus/evidence/task-7-plot-contract.txt
  ```

  **Commit**: YES | Message: `feat(single-layer): add publication plots` | Files: plot script + tests

- [x] 8. Run the model family sweep and produce final aggregate artifacts

  **What to do**: Execute the runner across `facebook/opt-125m`, `facebook/opt-350m`, `facebook/opt-1.3b`, and `facebook/opt-6.7b` on one GPU per run, three repeated runs per model. Emit raw CSVs, manifests, per-kernel tidy outputs, model/component summaries, and three figures. If 6.7B max-length capture fails, emit explicit failed status and include that in summary metadata.
  **Must NOT do**: Do not hide failed models. Do not reduce sequence length or precision to make a run pass.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: real GPU execution and artifact generation
  - Skills: `[]`
  - Omitted: `['frontend-ui-ux']`

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: 9 | Blocked By: 5,6,7

  **References**:
  - Pattern: runner/manifests from task 5
  - Output roots from this plan

  **Acceptance Criteria**:
  - [ ] successful models emit complete artifacts; failed models emit explicit failure rows only
  - [ ] aggregate summary and figures are generated from the new experiment family only

  **QA Scenarios**:
  ```
  Scenario: Full family sweep produces terminal rows
    Tool: Bash
    Steps: Run the family sweep command with all four models and inspect the final manifest
    Expected: Every model has exactly three terminal attempts or explicit failure rows with no silent omission
    Evidence: .sisyphus/evidence/task-8-family-sweep.txt

  Scenario: Aggregate plot-ready summary is non-empty
    Tool: Bash
    Steps: Inspect the generated plot-ready summary CSV after the sweep
    Expected: Successful models populate all five public components; failed models are represented in status metadata
    Evidence: .sisyphus/evidence/task-8-summary.txt
  ```

  **Commit**: NO | Message: `n/a` | Files: raw outputs, manifests, summaries, figures

- [x] 9. Final regression and compliance audit

  **What to do**: Re-run all targeted tests, one smallest-model GPU smoke, schema validation, and figure validation. Confirm no demo fallbacks, no silent precision changes, and no missing required artifacts.
  **Must NOT do**: Do not mark complete if any public component is missing without an explicit invalid/failed status.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: cross-cutting verification
  - Skills: `[]`
  - Omitted: `['artistry']`

  **Parallelization**: Can Parallel: NO | Wave Final | Blocks: none | Blocked By: 8

  **References**:
  - Tests from tasks 1–7
  - Final summary and figure roots

  **Acceptance Criteria**:
  - [ ] all test commands pass
  - [ ] smoke command passes
  - [ ] figure outputs match exact contract

  **QA Scenarios**:
  ```
  Scenario: Full regression suite
    Tool: Bash
    Steps: Run all four pytest modules plus the smoke and plot commands from this plan
    Expected: Every command exits 0 and no extra figures beyond the six required files are produced
    Evidence: .sisyphus/evidence/task-9-regression.txt

  Scenario: No silent fallback audit
    Tool: Bash
    Steps: Inspect final manifests and summary metadata
    Expected: Dtype/backend/seq_len requested values are preserved exactly in all terminal rows
    Evidence: .sisyphus/evidence/task-9-no-fallback.txt
  ```

  **Commit**: YES | Message: `test(single-layer): validate final pipeline` | Files: tests/logs/summary metadata as appropriate

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
- [x] F1. Plan Compliance Audit — oracle
- [x] F2. Code Quality Review — unspecified-high
- [x] F3. Real Manual QA — unspecified-high (+ playwright if UI)
- [x] F4. Scope Fidelity Check — deep

## Commit Strategy
- Commit 1: contract and fixture tests
- Commit 2: selected-layer capture/replay core
- Commit 3: nested NVTX component ranges and coverage handling
- Commit 4: duration-normalized parser + time-weighted aggregation
- Commit 5: runner + manifest/failure policy + parameter/range summaries
- Commit 6: fixed figure generation and final validation

## Success Criteria
- one new OPT-only experiment family exists for single-layer prefill profiling
- all ACU/GBU values are duration-weighted with normalized time units
- single-layer parameter counts are direct layer counts, not total-model counts
- the three requested figures exist in PDF/PNG and are generated from real experiment outputs only
- 6.7B is attempted under the same rules as smaller models, with explicit failure recording if infeasible
