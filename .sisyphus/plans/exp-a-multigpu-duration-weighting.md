# Exp A Multi-GPU Duration-Weighted Recollection

## TL;DR
> **Summary**: Expand Exp A coverage for larger OPT models by recollecting a new `expa_v2` dataset with shard-safe multi-GPU execution, fix dotted model parsing in analysis, and replace invocation-weighted aggregation with duration-based weighting for the new dataset only.
> **Deliverables**:
> - shard-safe multi-GPU Exp A sweep runner and manifests
> - dotted OPT filename parsing fix for `opt-1.3b` / `opt-6.7b`
> - duration-weighted ACU/GBU aggregation for `expa_v2`
> - expanded larger-model sweep coverage and regenerated Exp A outputs
> **Effort**: Large
> **Parallel**: YES - 4 waves
> **Critical Path**: Tests/specs → parser fix → shard-safe collection contract → duration metric plumbing → recollection/regeneration

## Context
### Original Request
Increase the number of sweeps for larger models, explore using multiple GPUs if possible, fix dotted model parsing (`opt-1.3b`/`opt-6.7b`), and switch Exp A from invocation-count weighting to time weighting.

### Interview Summary
- The current Exp A capture path is valid, but the phase-level point construction is coarse.
- Larger-model clustering is partly caused by reduced coverage and partly by invocation-weighted aggregation.
- The user is open to multi-GPU sharding and will choose the GPU set if needed.
- Simpler interpretation chosen here: multi-GPU means **many independent single-GPU shards**, not one model spread across multiple GPUs.

### Metis Review (gaps addressed)
- Treat this as `expa_v2`, not a silent tweak to the current dataset.
- Use deterministic sharding by unique `config_id`, never by overlapping wave names.
- Separate stable config identity from unique artifact/run identity.
- Add an explicit duration metric to recollection; do not retrofit “time weighting” onto legacy CSVs.
- Add parser, weighting, and shard-safety tests first.
- Keep legacy invocation-weighted outputs isolated from the new duration-weighted outputs.

## Work Objectives
### Core Objective
Produce a clean, reproducible `expa_v2` collection and analysis pipeline that (1) safely expands larger-model coverage across multiple GPUs, (2) parses dotted OPT model names correctly, and (3) computes phase-level Exp A points using duration-weighted ACU/GBU instead of invocation-weighted ACU/GBU.

### Deliverables
- `analysis/profile_inference_acu_gbu.py` supports exact dotted OPT parsing and duration-weighted aggregation for `expa_v2` inputs.
- `scripts/run_exp_a_all_waves.py` (or a successor with the same role) supports deterministic shard execution with separate manifests/output roots and explicit GPU pinning.
- New test modules for Exp A parsing/weighting and shard safety.
- `expa_v2` artifacts written under a separate root (for example `data/ncu_reports/expa_v2/`).
- Regenerated Exp A outputs (standard, presentation, labeled, model grid, large panel exports) from the new `expa_v2` dataset.

### Definition of Done (verifiable conditions with commands)
- `python -m pytest tests/python/test_profile_inference_acu_gbu.py -q`
- `python -m pytest tests/python/test_run_exp_a_all_waves.py -q`
- `python -m py_compile analysis/profile_inference_acu_gbu.py scripts/run_exp_a_all_waves.py`
- `python scripts/run_exp_a_all_waves.py --dry-run --gpu-ids 0,1,2,3 --output-root data/ncu_reports/expa_v2 --manifest-root data/expa_v2_manifests`
- Pilot recollection on a small subset completes with one visible GPU per shard and unique manifests/output roots.
- `python analysis/profile_inference_acu_gbu.py --input-dir data/ncu_reports/expa_v2/merged --output-dir analysis/figures`
- `analysis/data/exp_a_acu_gbu_data.csv` contains canonical dotted model names and metadata identifying `expa_v2` source artifacts.

### Must Have
- Deterministic sharding by unique `config_id`
- One visible GPU per worker process
- Separate output directories and manifests per shard
- Exact dotted model-name parsing for `opt-1.3b` and `opt-6.7b`
- Explicit duration metric in the new NCU schema
- Duration-weighted ACU/GBU for new `expa_v2` artifacts
- Expanded larger-model coverage using four OPT models: `opt-125m`, `opt-350m`, `opt-1.3b`, `opt-6.7b`
- Safe recollection boundary so legacy invocation-weighted artifacts are not mixed into the new dataset

### Must NOT Have
- No sharding by overlapping wave names
- No shared append-only manifest across parallel GPU workers
- No shared output root for concurrent shards
- No CPU/disk offload or multi-GPU placement for a supposedly single-GPU shard run
- No fallback to invocation weighting when `--weighting duration` is requested on legacy CSVs
- No silent renaming or truncation of dotted model names
- No mixing of `expa_v1` and `expa_v2` artifacts in one analysis run

## Verification Strategy
> ZERO HUMAN INTERVENTION — all verification is agent-executed.
- Test decision: tests-after + targeted TDD additions in pytest
- QA policy: every implementation task below includes an automated validation step
- Evidence: `.sisyphus/evidence/` paths may be used by the executor for logs and screenshots if desired

## Execution Strategy
### Parallel Execution Waves
Wave 1: parser/aggregation test scaffolding + shard contract scaffolding
Wave 2: dotted-name parser fix + duration metric/schema plumbing + explicit GPU isolation
Wave 3: shard-safe multi-GPU recollection pilot + merge path + analysis updates
Wave 4: expanded larger-model recollection + Exp A regeneration + final validation

### Dependency Matrix (full, all tasks)
- T1 blocks T2, T3, T4
- T2 blocks T5
- T3 blocks T5 and T6
- T4 blocks T6
- T5 blocks T7
- T6 blocks T7
- T7 blocks T8 and T9
- T8 blocks T10
- T9 blocks T10

### Agent Dispatch Summary
- Wave 1: 2 tasks → quick / unspecified-high
- Wave 2: 3 tasks → quick / unspecified-high
- Wave 3: 2 tasks → unspecified-high / deep
- Wave 4: 3 tasks → unspecified-high / writing

## TODOs
> Implementation + Test = ONE task. Never separate.

- [x] 1. Add Exp A parser and weighting fixture tests

  **What to do**: Create pytest coverage for `analysis/profile_inference_acu_gbu.py` using small synthetic CSV fixtures. Cover dotted filename parsing, unique `config_id` creation, duration-weighting math, and explicit failure/fallback behavior for legacy CSVs without duration.
  **Must NOT do**: Do not touch collection/orchestration yet. Do not rely on real GPU runs for these tests.

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: bounded test-file addition with clear target behavior
  - Skills: `[]`
  - Omitted: `['frontend-ui-ux']` — not relevant

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 2,3,4 | Blocked By: none

  **References**:
  - Pattern: `tests/python/test_inference.py` — existing pytest style in this repo
  - Pattern: `analysis/profile_inference_acu_gbu.py` — parser and weighting logic under test
  - API/Type: `analysis/profile_inference_acu_gbu.py:_PHASED_FILENAME_RE` — current parser bug location
  - API/Type: `analysis/profile_inference_acu_gbu.py:_parse_ncu_csv` — current invocation-weighted aggregator

  **Acceptance Criteria**:
  - [ ] `tests/python/test_profile_inference_acu_gbu.py` exists and covers dotted OPT names and duration weighting
  - [ ] `python -m pytest tests/python/test_profile_inference_acu_gbu.py -q` exits 0

  **QA Scenarios**:
  ```
  Scenario: Parser accepts dotted OPT names
    Tool: Bash
    Steps: Run `python -m pytest tests/python/test_profile_inference_acu_gbu.py -k dotted_model_parsing -q`
    Expected: Tests pass for `opt-1.3b` and `opt-6.7b` fixture names
    Evidence: .sisyphus/evidence/task-1-parser-tests.txt

  Scenario: Duration weighting differs from invocation weighting on fixture
    Tool: Bash
    Steps: Run `python -m pytest tests/python/test_profile_inference_acu_gbu.py -k duration_weighting -q`
    Expected: Duration-weighted expected values match fixture hand calculations
    Evidence: .sisyphus/evidence/task-1-duration-tests.txt
  ```

  **Commit**: YES | Message: `test(exp-a): add parser and weighting fixtures` | Files: `tests/python/test_profile_inference_acu_gbu.py`

- [x] 2. Fix dotted OPT filename parsing in Exp A analysis

  **What to do**: Update `analysis/profile_inference_acu_gbu.py` so the phased and legacy filename parsing preserves dotted OPT model names and uses anchored/full matching rather than substring search. Ensure downstream `model`, `config_id`, and `config_label` use canonical names.
  **Must NOT do**: Do not widen into unrelated naming cleanup across the repo.

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: localized parser correction
  - Skills: `[]`
  - Omitted: `['writing']` — not needed

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: 5 | Blocked By: 1

  **References**:
  - Pattern: `analysis/profile_inference_acu_gbu.py:103-112` — current regex definitions
  - Evidence: `analysis/data/exp_a_acu_gbu_data.csv` — current `3b` / `7b` corruption

  **Acceptance Criteria**:
  - [ ] `opt-1.3b_*` and `opt-6.7b_*` parse exactly to those names
  - [ ] existing `opt-125m` and `opt-350m` parsing remains unchanged

  **QA Scenarios**:
  ```
  Scenario: Dotted names preserved end-to-end
    Tool: Bash
    Steps: Run `python -m pytest tests/python/test_profile_inference_acu_gbu.py -k dotted_model_parsing -q`
    Expected: Canonical model names appear in parsed records
    Evidence: .sisyphus/evidence/task-2-dotted-parser.txt

  Scenario: Real filtered run accepts dotted model
    Tool: Bash
    Steps: Run `python analysis/profile_inference_acu_gbu.py --input-dir data/ncu_reports --model opt-1.3b --verify`
    Expected: Script exits 0 and writes valid filtered CSV output
    Evidence: .sisyphus/evidence/task-2-verify-opt13b.txt
  ```

  **Commit**: YES | Message: `fix(exp-a): preserve dotted opt model names` | Files: `analysis/profile_inference_acu_gbu.py`

- [x] 3. Add duration metric collection and schema versioning to Exp A sweep

  **What to do**: Extend the NCU metric set in `scripts/run_exp_a_all_waves.py` to collect one explicit kernel duration metric for `expa_v2`, version the output root/schema, and ensure exported CSVs contain the duration column required by the new weighting path. Metric preference order is fixed: use `gpu__time_duration.sum` if the installed NCU version exports it; otherwise use `gpu__time_duration.avg` and convert it to total kernel duration with `Invocations`. No third fallback is allowed.
  **Must NOT do**: Do not guess duration from invocation count alone. Do not overwrite legacy `data/ncu_reports/` by default.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: impacts collection contract and downstream analysis semantics
  - Skills: `[]`
  - Omitted: `['frontend-ui-ux']`

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 5,6 | Blocked By: 1

  **References**:
  - Pattern: `scripts/run_exp_a_all_waves.py:18-24` — current metric set
  - Pattern: `analysis/profile_inference_acu_gbu.py:_parse_ncu_csv` — new duration field consumer

  **Acceptance Criteria**:
  - [ ] new `expa_v2` CSVs contain an explicit duration metric field following the fixed preference order
  - [ ] legacy artifacts remain separate from `expa_v2`

  **QA Scenarios**:
  ```
  Scenario: Dry-run advertises expa_v2 output roots
    Tool: Bash
    Steps: Run `python scripts/run_exp_a_all_waves.py --dry-run --output-root data/ncu_reports/expa_v2 --manifest-root data/expa_v2_manifests`
    Expected: Dry-run exits 0 and references the new output/manifests without collecting data
    Evidence: .sisyphus/evidence/task-3-dry-run.txt

  Scenario: Export schema contains duration metric on pilot recollection
    Tool: Bash
    Steps: Recollect one pilot config in expa_v2 and inspect exported CSV header/rows
    Expected: Duration metric is present and parseable
    Evidence: .sisyphus/evidence/task-3-duration-schema.txt
  ```

  **Commit**: YES | Message: `feat(exp-a): add duration metric for expa v2` | Files: `scripts/run_exp_a_all_waves.py`

- [x] 4. Make the sweep shard-safe across multiple GPUs

  **What to do**: Refactor Exp A collection so each shard owns a deterministic subset of unique `config_id`s, has one visible GPU, writes to a shard-local output root and shard-local manifest, and merges only after shard completion.
  **Must NOT do**: Do not shard by wave names. Do not use a shared append-only manifest for live workers.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: orchestration/race correctness
  - Skills: `[]`
  - Omitted: `['writing']`

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: 6,7 | Blocked By: 1

  **References**:
  - Pattern: `scripts/run_exp_a_all_waves.py:41-104` — overlapping wave definitions and de-duplication
  - Pattern: `scripts/run_exp_a_all_waves.py:137-160` — append-only manifest writer
  - Pattern: `scripts/run_inference_nvtx.py:35-71` — current generic CUDA placement

  **Acceptance Criteria**:
  - [ ] one shard writes only to its own output/manifest roots
  - [ ] duplicate `config_id` collisions are impossible across shards by construction
  - [ ] GPU assignment is explicit and logged per shard

  **QA Scenarios**:
  ```
  Scenario: Parallel shard dry-run yields disjoint config sets
    Tool: Bash
    Steps: Run two shard dry-runs and compare emitted config lists
    Expected: No overlapping `config_id`s between shards
    Evidence: .sisyphus/evidence/task-4-shard-diff.txt

  Scenario: Resume only touches one shard
    Tool: Bash
    Steps: Simulate an interrupted shard manifest and rerun the same shard
    Expected: Only incomplete configs in that shard rerun; no cross-shard duplication
    Evidence: .sisyphus/evidence/task-4-resume.txt
  ```

  **Commit**: YES | Message: `feat(exp-a): shard sweep outputs by gpu` | Files: `scripts/run_exp_a_all_waves.py`, related helper/test files

- [x] 5. Implement duration-weighted ACU/GBU aggregation

  **What to do**: Update `analysis/profile_inference_acu_gbu.py` so `expa_v2` inputs are aggregated by explicit duration weighting rather than invocation count. Define and enforce the behavior for legacy CSVs without duration (recommended: reject when duration weighting is requested).
  **Must NOT do**: Do not silently mix invocation-weighted and duration-weighted semantics.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: analysis semantics change with regression risk
  - Skills: `[]`
  - Omitted: `['frontend-ui-ux']`

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: 7 | Blocked By: 1,2,3

  **References**:
  - Pattern: `analysis/profile_inference_acu_gbu.py:162-193` — current invocation-weighted aggregation
  - Pattern: representative NCU CSVs in `data/ncu_reports/` — current per-kernel schema shape

  **Acceptance Criteria**:
  - [ ] duration-weighted fixture tests pass
  - [ ] analysis refuses or explicitly handles legacy artifacts without duration

  **QA Scenarios**:
  ```
  Scenario: Duration weighting matches fixture math
    Tool: Bash
    Steps: Run `python -m pytest tests/python/test_profile_inference_acu_gbu.py -k duration_weighting -q`
    Expected: Tests pass with hand-checked expected values
    Evidence: .sisyphus/evidence/task-5-duration-math.txt

  Scenario: Legacy CSV policy is explicit
    Tool: Bash
    Steps: Run `python -m pytest tests/python/test_profile_inference_acu_gbu.py -k missing_duration -q`
    Expected: Legacy artifacts either fail clearly or follow the planned fallback behavior exactly
    Evidence: .sisyphus/evidence/task-5-legacy-policy.txt
  ```

  **Commit**: YES | Message: `feat(exp-a): use duration weighted aggregation` | Files: `analysis/profile_inference_acu_gbu.py`

- [x] 6. Expand larger-model sweep matrix for `expa_v2`

  **What to do**: Define the exact larger-model matrix for the four-model Exp A recollection: use `opt-125m`, `opt-350m`, `opt-1.3b`, and `opt-6.7b`. Keep `opt-6.7b` sparse enough to fit 24 GB A5000 constraints and recollection runtime. Default matrix for execution: `125m/350m -> seq {128,256,512,1024,2048}, batch {1,4,8,16}`; `1.3b -> seq {128,256,512,1024,2048}, batch {1,4,8}`; `6.7b -> seq {128,512,1024,2048}, batch {1,4}`.
  **Must NOT do**: Do not add `13b+` into this plan; the current 24 GB VRAM and `estimate_vram_gb` evidence make that a separate decision.

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: bounded config-list update after safety changes land
  - Skills: `[]`
  - Omitted: `['artistry']`

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 7 | Blocked By: 4

  **References**:
  - Pattern: `scripts/run_exp_a_all_waves.py:45-83` — current wave definitions
  - API/Type: `python/nvbenchsuite/inference.py:estimate_vram_gb` — VRAM guardrail source

  **Acceptance Criteria**:
  - [ ] dry-run emits the exact planned matrix and nothing else
  - [ ] `6.7b` configs remain under the chosen A5000 safety cap or are explicitly excluded

  **QA Scenarios**:
  ```
  Scenario: Expanded config enumeration matches plan
    Tool: Bash
    Steps: Run `python scripts/run_exp_a_all_waves.py --dry-run --gpu-ids 0,1,2,3 --output-root data/ncu_reports/expa_v2 --manifest-root data/expa_v2_manifests`
    Expected: Output lists the four-model matrix exactly as planned
    Evidence: .sisyphus/evidence/task-6-dry-matrix.txt

  Scenario: Largest planned configs respect VRAM cap
    Tool: Bash
    Steps: Run a small Python check over `estimate_vram_gb()` for the planned matrix
    Expected: Any over-cap workload is explicitly excluded before recollection
    Evidence: .sisyphus/evidence/task-6-vram-cap.txt
  ```

  **Commit**: YES | Message: `feat(exp-a): expand four-model sweep matrix` | Files: `scripts/run_exp_a_all_waves.py`

- [x] 7. Pilot multi-GPU recollection on a subset

  **What to do**: Run a 2-GPU pilot on a deterministic subset that includes one dotted model and the largest intended model. Validate shard-safe execution, parser correctness, duration availability, and duration-weighted output generation before the full recollection.
  **Must NOT do**: Do not launch the full 8-GPU recollection before the pilot passes.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: real-world validation of orchestration and analysis interaction
  - Skills: `[]`
  - Omitted: `['frontend-ui-ux']`

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: 8,9 | Blocked By: 4,5,6

  **References**:
  - Pattern: shard-safe manifests/output roots from tasks 3 and 4
  - Output: `data/ncu_reports/expa_v2/`
  - Output: `data/expa_v2_manifests/`

  **Acceptance Criteria**:
  - [ ] 2-GPU pilot completes without artifact collisions
  - [ ] merged pilot analysis shows canonical dotted names and duration-weighted points

  **QA Scenarios**:
  ```
  Scenario: Two shards produce disjoint artifacts
    Tool: Bash
    Steps: Run the pilot on GPUs 0 and 1 with separate shard roots, then merge manifests
    Expected: No duplicate `config_id`s and no overwritten outputs
    Evidence: .sisyphus/evidence/task-7-pilot-merge.txt

  Scenario: Pilot Exp A regeneration succeeds
    Tool: Bash
    Steps: Run `python analysis/profile_inference_acu_gbu.py --input-dir data/ncu_reports/expa_v2/merged --output-dir analysis/figures`
    Expected: Exp A outputs regenerate successfully from the pilot dataset
    Evidence: .sisyphus/evidence/task-7-pilot-plot.txt
  ```

  **Commit**: NO | Message: `n/a` | Files: `data/ncu_reports/expa_v2/**`, `data/expa_v2_manifests/**`

- [ ] 8. Run full recollection across the chosen GPU set

  **What to do**: Execute the full four-model `expa_v2` recollection across the selected GPU indices, one visible GPU per shard, using the tested shard-safe contract.
  **Must NOT do**: Do not mix `expa_v1` and `expa_v2` directories.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: orchestration-heavy execution with monitoring
  - Skills: `[]`
  - Omitted: `['writing']`

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: 10 | Blocked By: 7

  **References**:
  - Pilot shard contract from task 7
  - GPU selection: default assumption `0,1,2,3` unless the user overrides

  **Acceptance Criteria**:
  - [ ] all planned `expa_v2` configs finish, skip by policy, or fail with explicit reason
  - [ ] manifests and merged output are internally consistent

  **QA Scenarios**:
  ```
  Scenario: Full recollection reaches terminal state
    Tool: Bash
    Steps: Monitor shard manifests/logs until all planned configs are terminal
    Expected: Every planned config is accounted for exactly once in the merged state
    Evidence: .sisyphus/evidence/task-8-full-merge.txt

  Scenario: Postprocess regeneration is automatic or scripted
    Tool: Bash
    Steps: Trigger the Exp A regeneration step on the merged expa_v2 dataset
    Expected: Updated Exp A outputs exist and are non-empty
    Evidence: .sisyphus/evidence/task-8-regenerated.txt
  ```

  **Commit**: NO | Message: `n/a` | Files: `data/ncu_reports/expa_v2/**`, `data/expa_v2_manifests/**`

- [ ] 9. Regenerate Exp A outputs and validate clustering changes

  **What to do**: Regenerate all Exp A outputs from the merged `expa_v2` dataset, then compare the larger-model point spread against the prior invocation-weighted plot. Record the semantic change clearly.
  **Must NOT do**: Do not overwrite or mislabel historical `expa_v1` interpretation as duration-weighted.

  **Recommended Agent Profile**:
  - Category: `writing` — Reason: combines regeneration with explanatory output change notes
  - Skills: `[]`
  - Omitted: `['quick']`

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: 10 | Blocked By: 7,8

  **References**:
  - Output: `analysis/profile_inference_acu_gbu.py`
  - Output: `analysis/figures/exp_a_*`
  - Output: `analysis/data/exp_a_acu_gbu_data.csv`

  **Acceptance Criteria**:
  - [ ] standard, presentation, labeled, model-grid, and panel outputs regenerate from `expa_v2`
  - [ ] exported CSV contains canonical model names and source artifact metadata

  **QA Scenarios**:
  ```
  Scenario: Exp A output set regenerates from expa_v2
    Tool: Bash
    Steps: Run `python analysis/profile_inference_acu_gbu.py --input-dir data/ncu_reports/expa_v2/merged --output-dir analysis/figures`
    Expected: All Exp A output files exist and are non-zero
    Evidence: .sisyphus/evidence/task-9-expa-outputs.txt

  Scenario: Larger-model labels are correct
    Tool: Bash
    Steps: Inspect `analysis/data/exp_a_acu_gbu_data.csv` for `opt-1.3b` and `opt-6.7b`
    Expected: No `3b` or `7b` model truncations remain in expa_v2 output
    Evidence: .sisyphus/evidence/task-9-dotted-models.txt
  ```

  **Commit**: YES/NO | Message: `chore(exp-a): regenerate duration weighted outputs` | Files: `analysis/figures/exp_a_*`, `analysis/data/exp_a_acu_gbu_data.csv`

- [ ] 10. Final regression and compliance audit

  **What to do**: Re-run targeted tests and smoke commands, verify no shared-output races remain, verify parser correctness, verify duration weighting on sample configs, and confirm the final selected GPU strategy is documented.
  **Must NOT do**: Do not declare completion if the merged dataset still contains duplicate config IDs or mixed schema versions.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: cross-cutting audit of execution + analysis semantics
  - Skills: `[]`
  - Omitted: `['frontend-ui-ux']`

  **Parallelization**: Can Parallel: NO | Wave Final | Blocks: none | Blocked By: 8,9

  **References**:
  - Tests: `tests/python/test_profile_inference_acu_gbu.py`
  - Tests: `tests/python/test_run_exp_a_all_waves.py`
  - Manifests: `data/expa_v2_manifests/**`
  - Outputs: `analysis/data/exp_a_acu_gbu_data.csv`, `analysis/figures/exp_a_*`

  **Acceptance Criteria**:
  - [ ] all targeted tests pass
  - [ ] no duplicate merged `config_id`s remain
  - [ ] all final outputs are version-consistent and generated from `expa_v2`

  **QA Scenarios**:
  ```
  Scenario: Full regression suite for Exp A changes
    Tool: Bash
    Steps: Run `python -m pytest tests/python/test_profile_inference_acu_gbu.py tests/python/test_run_exp_a_all_waves.py -q`
    Expected: All tests pass
    Evidence: .sisyphus/evidence/task-10-regression.txt

  Scenario: Merged manifest is unique and complete
    Tool: Bash
    Steps: Run a manifest uniqueness check over merged expa_v2 artifacts
    Expected: Every planned config appears exactly once or is excluded by explicit policy
    Evidence: .sisyphus/evidence/task-10-merged-uniqueness.txt
  ```

  **Commit**: YES | Message: `test(exp-a): validate multigpu duration weighted pipeline` | Files: tests, manifests, final logs as appropriate

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
- [ ] F1. Plan Compliance Audit — oracle
- [ ] F2. Code Quality Review — unspecified-high
- [ ] F3. Real Manual QA — unspecified-high (+ playwright if UI)
- [ ] F4. Scope Fidelity Check — deep

## Commit Strategy
- Commit 1: parser/weighting/shard safety tests
- Commit 2: dotted-name parser fix
- Commit 3: shard-safe sweep contract and explicit GPU isolation
- Commit 4: duration metric plumbing + duration-weighted aggregation
- Commit 5: expanded matrix + regenerated `expa_v2` outputs + regression audit

## Success Criteria
- `expa_v2` recollection can run safely across multiple GPUs using one visible GPU per shard
- `opt-1.3b` and `opt-6.7b` appear with correct canonical names throughout Exp A outputs
- Duration-weighted Exp A outputs are clearly separated from legacy invocation-weighted outputs
- Larger-model point spread in Exp A is based on increased coverage plus duration-weighted aggregation rather than the previous invocation-weighted compression
- Final artifacts are reproducible, merge-safe, and regression-tested
