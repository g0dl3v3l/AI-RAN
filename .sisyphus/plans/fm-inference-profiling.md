# FM Inference GPU Profiling Experiment Suite

## TL;DR

> **Quick Summary**: Extend NVBenchSuite to profile Foundation Model Inference workloads (Prefill/Decode phases) on RTX A5000, adapting Weaver paper methodology originally designed for FM Training. Generate ACU/GBU scatter plots, workload characteristic tables, utilization heatmaps, and VRAM footprint analysis.
> 
> **Deliverables**:
> - `python/nvbenchsuite/inference.py` - Layer 1 inference analysis module
> - RTX A5000 device constants in `data/device_constants.json`
> - NVTX-instrumented inference runner for phase separation
> - Experiment A: ACU vs GBU scatter plot (Prefill/Decode vs LDPC)
> - Experiment B: Workload characteristics summary table
> - Experiment C: Perplexity/Latency heatmaps across model/seq_len/batch sweeps
> - Experiment D: VRAM memory footprint timeseries
> - Full test suite (TDD approach)
> 
> **Estimated Effort**: Large (multiple modules, 4 experiments, full OPT model sweep)
> **Parallel Execution**: YES - 5 waves
> **Critical Path**: Device Constants → Inference Module → NVTX Wrapper → Profiling Scripts → Experiments A-D → Final Verification

---

## Context

### Original Request
Design and implement a comprehensive GPU profiling experiment suite for FM Inference workloads (Prefill and Decode phases), adapting the Weaver paper methodology which originally profiled FM Training workloads.

### Interview Summary
**Key Discussions**:
- Target GPU: NVIDIA RTX A5000 (24GB VRAM, 64 SMs)
- Test strategy: TDD approach (pytest, write tests first)
- Model family: OPT (125M → 66B) with INT8/INT4 quantization for large models
- Sequence lengths: Full sweep (128, 256, 512, 1024, 2048, 4096, 8192)
- Batch sizes: Full sweep (1, 4, 16, 32, 64, 128, 256)
- NVTX granularity: Phase-level (prefill/decode) now, per-layer as future extension
- Experiment C accuracy metric: Perplexity on WikiText-2

**Research Findings**:
- Prefill phase: Compute-bound (ACU 70-95%, GBU 30-50%), parallel KV cache computation
- Decode phase: Memory-bound (ACU 20-40%, GBU 60-85%), sequential token generation
- NVBenchSuite follows Layer 0/1/2 architecture pattern
- Existing profiling infrastructure: `compute_util_from_nsys.py`, `summarize_ncu.py`, `plot_utils.py`

### Metis Review
**Identified Gaps** (addressed):
- Batch size strategy: Added full sweep {1, 4, 16, 32, 64, 128, 256}
- NVTX granularity: Phase-level for Weaver comparison, per-layer as optional extension
- Experiment C definition: Accuracy = Perplexity, Latency = TTFT/tokens-per-sec
- Memory headroom check: Added utility before profiling large models
- ncu permission requirements: Added documentation task
- Model max sequence lengths: Build model→max_seq_len lookup table

---

## Work Objectives

### Core Objective
Extend NVBenchSuite to profile FM Inference workloads (Prefill and Decode phases) using ACU/GBU/SMU metrics, replicating Weaver paper Experiments 2 and 3 methodology for inference rather than training.

### Concrete Deliverables
- `python/nvbenchsuite/inference.py` - Inference analysis module (Layer 1)
- `python/nvbenchsuite/nvtx_utils.py` - NVTX wrapper utilities
- `python/nvbenchsuite/vram_monitor.py` - pynvml VRAM monitoring
- `data/device_constants.json` - Extended with RTX A5000 specs
- `analysis/profile_inference_acu_gbu.py` - Experiment A script
- `analysis/generate_workload_table.py` - Experiment B script  
- `analysis/generate_heatmaps.py` - Experiment C script
- `analysis/profile_vram.py` - Experiment D script
- `scripts/run_inference_profiling.sh` - Orchestration script
- `scripts/download_opt_models.py` - Model download automation
- `tests/python/test_inference.py` - TDD test suite
- PDF/PNG visualizations in `analysis/figures/`

### Definition of Done
- [x] `pytest tests/python/test_inference.py -v` passes all tests
- [x] `python analysis/profile_inference_acu_gbu.py --model=opt-125m --verify` generates valid CSV
- [x] Prefill data points show ACU > GBU (compute-bound)
- [x] Decode data points show GBU > ACU (memory-bound)
- [x] All 4 experiments produce output files in `analysis/figures/`
- [x] RTX A5000 constants load correctly from `device_constants.json`

### Must Have
- TDD: All implementation preceded by failing tests
- NVTX markers for prefill/decode phase separation
- Support for OPT-125M through OPT-66B (with quantization for large models)
- Batch size sweep: {1, 4, 16, 32, 64, 128, 256}
- Sequence length sweep: {128, 256, 512, 1024, 2048, 4096, 8192}
- pynvml VRAM monitoring at 100ms resolution
- Paper-quality visualizations using `plot_utils.py` conventions

### Must NOT Have (Guardrails)
- **NO FM Training profiling** - Inference ONLY (explicit user constraint)
- **NO Weaver Experiment 6** - Skip RAN-derived SM envelopes
- **NO multi-GPU support** - Single RTX A5000 only
- **NO models beyond OPT family** - No Llama, Mistral, etc.
- **NO modifications to existing modules** - Only extend, don't modify `ldpc.py`, `gemm.py`, etc.
- **NO profiling without memory headroom check** - Fail fast if insufficient VRAM
- **NO per-layer NVTX markers** - Phase-level only (per-layer is future extension)
- **NO real-time serving optimizations** - Profiling only, not optimization

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest in pyproject.toml)
- **Automated tests**: TDD approach (RED → GREEN → REFACTOR)
- **Framework**: pytest with parametrized tests
- **Pattern**: Follow `tests/python/test_ldpc_measurement.py` structure

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Python modules**: `pytest -v` with specific test file
- **CSV outputs**: Verify columns, row counts, value ranges via Python assertions
- **Plots**: Verify file existence, non-zero size, correct format (PDF/PNG)
- **Device constants**: Python import and key access verification

---

## Execution Strategy

### Profiling Execution Model

**Yes — the plan includes one primary top-level profiling super-script:**
`scripts/run_inference_profiling.sh`

This will be the **main user-facing entrypoint for profiling runs**. It is not intended to be a giant monolithic implementation file; instead, it coordinates smaller modules so runs are reproducible and individual stages can be retried without redoing everything.

**How profiling will be done**:

1. **Preparation**
   - Validate dependencies (`nsys`, `ncu`, Python packages, bitsandbytes when needed)
   - Validate GPU visibility and profiler permissions
   - Ensure model availability via `scripts/download_opt_models.py` or cached HuggingFace weights
   - Run memory headroom checks before execution

2. **Single-run execution**
   - `scripts/run_inference_nvtx.py` runs one profiled inference configuration
   - It inserts **phase-level NVTX markers** for `prefill` and `decode`
   - It supports one configuration at a time: model, seq-len, batch-size, quantization, max-new-tokens

3. **Profiler orchestration**
   - `scripts/run_inference_profiling.sh` wraps `run_inference_nvtx.py` with `nsys` and/or `ncu`
   - It supports targeted sweeps over models, sequence lengths, and batch sizes
   - It stores raw reports in `data/nsys_reports/` and `data/ncu_reports/`
   - It converts profiler outputs into CSV artifacts using the existing conversion scripts
   - It writes run metadata/manifests so experiments can be reproduced

4. **Post-processing / experiment generation**
   - Profiling data is then consumed by experiment-specific scripts:
     - `analysis/profile_inference_acu_gbu.py` (Experiment A)
     - `analysis/generate_workload_table.py` (Experiment B)
     - `analysis/generate_heatmaps.py` (Experiment C)
     - `analysis/profile_vram.py` (Experiment D)

**Decision recorded in this plan**:
- There will be **one super-script for profiling orchestration**.
- There will **not** be one giant script that also hardcodes all analysis and plotting logic.
- Analysis remains modular so figures/tables can be regenerated **without rerunning GPU profiling**.

**Expected user workflow**:
```bash
# Step 1: prepare models (one-time or as needed)
python scripts/download_opt_models.py --model opt-125m

# Step 2: run profiling for one config or a sweep
bash scripts/run_inference_profiling.sh --model opt-125m --seq-len 512 --batch-size 1

# Step 3: generate experiment outputs from saved profiler data
python analysis/profile_inference_acu_gbu.py --input-dir data/ncu_reports/
python analysis/generate_workload_table.py --input analysis/data/exp_a_acu_gbu_data.csv
python analysis/generate_heatmaps.py --input-dir data/ncu_reports/
python analysis/profile_vram.py --model opt-125m --seq-len 512
```

**Why this structure was chosen**:
- Profiling runs are expensive and slow; analysis should be rerunnable independently
- Failed plots or table-generation should not require re-running `ncu`/`nsys`
- The super-script stays operationally simple while the analysis stays scientifically traceable

### Parallel Execution Waves

```
Wave 1 (Foundation — start immediately):
├── Task 1: Add RTX A5000 device constants [quick]
├── Task 2: Create model download automation script [quick]
├── Task 3: Create inference.py test stubs (RED phase) [quick]
└── Task 4: Create nvtx_utils.py test stubs (RED phase) [quick]

Wave 2 (Core Modules — after Wave 1):
├── Task 5: Implement inference.py module (GREEN phase) [deep]
├── Task 6: Implement nvtx_utils.py NVTX wrapper [deep]
├── Task 7: Implement vram_monitor.py pynvml utility [unspecified-high]
└── Task 8: Extend ncu/nsys parsing for transformer kernels [unspecified-high]

Wave 3 (Profiling Infrastructure — after Wave 2):
├── Task 9: Create NVTX-instrumented inference runner [deep]
├── Task 10: Create profiling orchestration script [quick]
└── Task 11: Add memory headroom check utility [quick]

Wave 4 (Experiments — after Wave 3, MAX PARALLEL):
├── Task 12: Experiment A - ACU vs GBU scatter plot [unspecified-high]
├── Task 13: Experiment B - Workload characteristics table [unspecified-high]
├── Task 14: Experiment C - Perplexity/Latency heatmaps [unspecified-high]
└── Task 15: Experiment D - VRAM footprint analysis [unspecified-high]

Wave 5 (Documentation — after Wave 4):
└── Task 16: Update README and add usage documentation [writing]

Wave FINAL (Verification — after ALL tasks):
├── Task F1: Plan compliance audit [oracle]
├── Task F2: Code quality review [unspecified-high]
├── Task F3: Real QA execution [unspecified-high]
└── Task F4: Scope fidelity check [deep]
-> Present results -> Get explicit user okay
```

### Dependency Matrix

| Task | Depends On | Blocks |
|------|------------|--------|
| 1 | — | 5, 7, 8, 9 |
| 2 | — | 9, 12-15 |
| 3 | — | 5 |
| 4 | — | 6 |
| 5 | 1, 3 | 9, 12-15 |
| 6 | 4 | 9 |
| 7 | 1 | 15 |
| 8 | — | 12, 13, 14 |
| 9 | 5, 6 | 10, 12-15 |
| 10 | 9 | 12-15 |
| 11 | 1 | 9, 12-15 |
| 12 | 8, 9, 10, 11 | 16, F1-F4 |
| 13 | 8, 9, 10 | 16, F1-F4 |
| 14 | 8, 9, 10 | 16, F1-F4 |
| 15 | 7, 9, 10 | 16, F1-F4 |
| 16 | 12-15 | F1-F4 |

### Agent Dispatch Summary

- **Wave 1**: 4 tasks — T1-T4 → `quick`
- **Wave 2**: 4 tasks — T5,T6 → `deep`, T7,T8 → `unspecified-high`
- **Wave 3**: 3 tasks — T9 → `deep`, T10,T11 → `quick`
- **Wave 4**: 4 tasks — T12-T15 → `unspecified-high`
- **Wave 5**: 1 task — T16 → `writing`
- **FINAL**: 4 tasks — F1 → `oracle`, F2-F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

> Implementation + Test = ONE Task. Never separate.
> EVERY task MUST have: Recommended Agent Profile + Parallelization info + QA Scenarios.

- [x] 1. Add RTX A5000 Device Constants

  **What to do**:
  - Add RTX A5000 specifications to `data/device_constants.json`
  - Include: total_sms (64), peak_bw_gbs (768), peak_fp32_tflops (27.8), peak_fp16_tflops (55.6)
  - Include: max_threads_per_sm (1536), max_regs_per_sm (65536), max_smem_per_sm (102400), l2_cache_bytes (6291456)
  - Write test to verify constants load correctly

  **Must NOT do**:
  - Do NOT modify existing device entries (A100, GB10)
  - Do NOT create a new JSON file (extend existing)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single file edit with known structure, low complexity
  - **Skills**: `[]`
    - No special skills needed for JSON editing

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3, 4)
  - **Blocks**: Tasks 5, 7, 8, 9
  - **Blocked By**: None (can start immediately)

  **References**:
  - `data/device_constants.json:1-50` - Existing device constants structure (A100, GB10 format)
  - `python/nvbenchsuite/utils.py:_load_device_constants()` - How constants are loaded
  - RTX A5000 specs: https://www.nvidia.com/en-us/design-visualization/rtx-a5000/

  **Acceptance Criteria**:
  - [ ] `data/device_constants.json` contains "NVIDIA RTX A5000" key
  - [ ] `python -c "from nvbenchsuite.utils import _load_device_constants; print(_load_device_constants()['devices']['NVIDIA RTX A5000']['total_sms'])"` outputs `64`

  **QA Scenarios**:
  ```
  Scenario: RTX A5000 constants load correctly
    Tool: Bash
    Preconditions: NVBenchSuite installed in editable mode
    Steps:
      1. Run: python -c "from nvbenchsuite.utils import _load_device_constants; d = _load_device_constants(); print(d['devices']['NVIDIA RTX A5000'])"
      2. Verify output contains: total_sms, peak_bw_gbs, peak_fp32_tflops
      3. Verify total_sms == 64
    Expected Result: JSON dict with all RTX A5000 specs printed
    Failure Indicators: KeyError, missing keys, wrong values
    Evidence: .sisyphus/evidence/task-1-device-constants.txt

  Scenario: Existing devices unchanged
    Tool: Bash
    Preconditions: None
    Steps:
      1. Run: python -c "from nvbenchsuite.utils import _load_device_constants; d = _load_device_constants(); print(d['devices']['NVIDIA A100-SXM4-80GB']['total_sms'])"
      2. Verify A100 total_sms unchanged (108)
    Expected Result: Output is 108
    Failure Indicators: KeyError, value != 108
    Evidence: .sisyphus/evidence/task-1-existing-devices.txt
  ```

  **Commit**: YES
  - Message: `feat(data): add RTX A5000 device constants for inference profiling`
  - Files: `data/device_constants.json`
  - Pre-commit: `python -c "from nvbenchsuite.utils import _load_device_constants; print('NVIDIA RTX A5000' in str(_load_device_constants()))"`

- [x] 2. Create OPT Model Download Automation Script

  **What to do**:
  - Create `scripts/download_opt_models.py` for HuggingFace OPT model download
  - Support models: opt-125m, opt-350m, opt-1.3b, opt-6.7b, opt-13b, opt-30b, opt-66b
  - Implement checksum verification after download
  - Add CLI arguments: --model (or --all), --cache-dir, --force-redownload
  - Handle download failures with retry logic (3 retries, exponential backoff)
  - For opt-13b/30b/66b, also download bitsandbytes quantization configs

  **Must NOT do**:
  - Do NOT download models during script creation (only on explicit run)
  - Do NOT store models in repo (use HuggingFace cache)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single utility script, well-defined scope
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3, 4)
  - **Blocks**: Tasks 9, 12-15
  - **Blocked By**: None

  **References**:
  - HuggingFace OPT: https://huggingface.co/facebook/opt-125m
  - `transformers.AutoModelForCausalLM.from_pretrained()` - Model loading API
  - `huggingface_hub.snapshot_download()` - Direct download API

  **Acceptance Criteria**:
  - [ ] `python scripts/download_opt_models.py --help` shows usage
  - [ ] `python scripts/download_opt_models.py --model opt-125m --cache-dir ./test_cache` downloads model
  - [ ] Script handles network errors gracefully with retry

  **QA Scenarios**:
  ```
  Scenario: Help message displays correctly
    Tool: Bash
    Preconditions: None
    Steps:
      1. Run: python scripts/download_opt_models.py --help
      2. Verify output contains: --model, --cache-dir, --force-redownload
    Expected Result: Help text with all arguments listed
    Failure Indicators: Script error, missing arguments in help
    Evidence: .sisyphus/evidence/task-2-help-output.txt

  Scenario: Model download works (opt-125m)
    Tool: Bash
    Preconditions: Internet connection available
    Steps:
      1. Run: python scripts/download_opt_models.py --model opt-125m --cache-dir /tmp/test_opt_cache
      2. Verify exit code is 0
      3. Verify cache directory contains model files
    Expected Result: Model downloaded to cache, script exits successfully
    Failure Indicators: Non-zero exit code, empty cache directory
    Evidence: .sisyphus/evidence/task-2-download-opt125m.txt
  ```

  **Commit**: YES
  - Message: `feat(scripts): add OPT model download automation with retry logic`
  - Files: `scripts/download_opt_models.py`
  - Pre-commit: `python scripts/download_opt_models.py --help`

- [x] 3. Create inference.py Test Stubs (TDD RED Phase)

  **What to do**:
  - Create `tests/python/test_inference.py` with failing test stubs
  - Test cases for: `classify_transformer_kernel()`, `parse_inference_ncu_csv()`, `compute_phase_utilization()`
  - Test cases for: `get_opt_model_config()`, `validate_profiling_config()`
  - Follow `test_ldpc_measurement.py` structure (class-based, parametrized)
  - All tests should FAIL initially (RED phase of TDD)

  **Must NOT do**:
  - Do NOT implement `inference.py` yet (tests first!)
  - Do NOT skip any planned function

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Test stub creation, follows existing patterns
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 4)
  - **Blocks**: Task 5
  - **Blocked By**: None

  **References**:
  - `tests/python/test_ldpc_measurement.py` - Test structure pattern to follow
  - `tests/python/conftest.py` - Pytest fixtures and CUDA skip patterns
  - `python/nvbenchsuite/ldpc.py` - Function signatures to mirror for inference

  **Acceptance Criteria**:
  - [ ] `tests/python/test_inference.py` exists with 5+ test functions
  - [ ] `pytest tests/python/test_inference.py -v` runs but shows FAILURES (RED phase)
  - [ ] Test names clearly indicate what they test

  **QA Scenarios**:
  ```
  Scenario: Test file runs with expected failures
    Tool: Bash
    Preconditions: pytest installed
    Steps:
      1. Run: pytest tests/python/test_inference.py -v --tb=short 2>&1 | tail -20
      2. Verify output shows test collection succeeded
      3. Verify tests FAIL (not error) due to ImportError or NotImplementedError
    Expected Result: Tests collected, all fail with import/implementation errors
    Failure Indicators: Test collection error, syntax errors
    Evidence: .sisyphus/evidence/task-3-test-stubs-red.txt

  Scenario: Test structure follows patterns
    Tool: Bash
    Preconditions: None
    Steps:
      1. Run: grep -c "def test_" tests/python/test_inference.py
      2. Verify count >= 5
      3. Run: grep -c "@pytest.mark.parametrize" tests/python/test_inference.py
      4. Verify parametrized tests exist
    Expected Result: 5+ test functions, parametrized patterns used
    Failure Indicators: Count < 5, no parametrize decorators
    Evidence: .sisyphus/evidence/task-3-test-structure.txt
  ```

  **Commit**: YES
  - Message: `test(inference): add TDD test stubs for inference module (RED phase)`
  - Files: `tests/python/test_inference.py`
  - Pre-commit: `python -m py_compile tests/python/test_inference.py`

- [x] 4. Create nvtx_utils.py Test Stubs (TDD RED Phase)

  **What to do**:
  - Create `tests/python/test_nvtx_utils.py` with failing test stubs
  - Test cases for: `nvtx_phase_context()`, `NVTXInferenceWrapper`, `get_phase_from_nvtx_range()`
  - Test mocking for NVTX when CUDA unavailable
  - All tests should FAIL initially (RED phase)

  **Must NOT do**:
  - Do NOT implement `nvtx_utils.py` yet
  - Do NOT require actual GPU for tests (use mocks)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Test stub creation, follows patterns
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3)
  - **Blocks**: Task 6
  - **Blocked By**: None

  **References**:
  - `tests/python/conftest.py` - Mock patterns for CUDA-dependent code
  - `torch.cuda.nvtx` - NVTX API to wrap
  - `tests/python/test_ldpc_measurement.py` - Test organization pattern

  **Acceptance Criteria**:
  - [ ] `tests/python/test_nvtx_utils.py` exists with 3+ test functions
  - [ ] `pytest tests/python/test_nvtx_utils.py -v` runs but shows FAILURES

  **QA Scenarios**:
  ```
  Scenario: NVTX test stubs run with expected failures
    Tool: Bash
    Preconditions: pytest installed
    Steps:
      1. Run: pytest tests/python/test_nvtx_utils.py -v --tb=short 2>&1 | tail -15
      2. Verify tests collected
      3. Verify tests fail (RED phase)
    Expected Result: Tests collected and fail
    Failure Indicators: Collection errors, syntax errors
    Evidence: .sisyphus/evidence/task-4-nvtx-test-stubs.txt
  ```

  **Commit**: YES
  - Message: `test(nvtx): add TDD test stubs for NVTX utilities (RED phase)`
  - Files: `tests/python/test_nvtx_utils.py`
  - Pre-commit: `python -m py_compile tests/python/test_nvtx_utils.py`

- [x] 5. Implement inference.py Module (TDD GREEN Phase)

  **What to do**:
  - Create `python/nvbenchsuite/inference.py` as Layer 1 module
  - Implement `classify_transformer_kernel(kernel_name: str) -> str` - classify as attention/matmul/layernorm/other
  - Implement `parse_inference_ncu_csv(csv_path: Path) -> pd.DataFrame` - parse NCU output for transformer workloads
  - Implement `compute_phase_utilization(df: pd.DataFrame, phase: str) -> dict` - compute ACU/GBU/SMU for phase
  - Implement `get_opt_model_config(model_name: str) -> dict` - return model specs (params, layers, hidden_dim)
  - Implement `validate_profiling_config(model: str, seq_len: int, batch_size: int, device_mem_gb: float) -> bool`
  - Add to `__init__.py` exports
  - Make all tests from Task 3 PASS (GREEN phase)

  **Must NOT do**:
  - Do NOT modify existing modules (ldpc.py, gemm.py, etc.)
  - Do NOT add GPU-dependent code that can't be mocked

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Core module implementation, requires understanding Layer 1 patterns
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (within Wave 2)
  - **Parallel Group**: Wave 2 (with Tasks 6, 7, 8)
  - **Blocks**: Tasks 9, 12-15
  - **Blocked By**: Tasks 1, 3

  **References**:
  - `python/nvbenchsuite/ldpc.py` - Layer 1 module pattern to follow
  - `python/nvbenchsuite/utils.py` - Device utilities to use
  - `analysis/ldpc_colocation/summarize_ncu.py:parse_ncu_csv()` - NCU parsing pattern
  - `python/nvbenchsuite/__init__.py` - Export pattern

  **Acceptance Criteria**:
  - [ ] `python/nvbenchsuite/inference.py` exists with all 5 functions
  - [ ] `pytest tests/python/test_inference.py -v` all tests PASS (GREEN phase)
  - [ ] `python -c "from nvbenchsuite import classify_transformer_kernel"` works

  **QA Scenarios**:
  ```
  Scenario: All inference tests pass (GREEN phase)
    Tool: Bash
    Preconditions: Task 3 test stubs exist
    Steps:
      1. Run: pytest tests/python/test_inference.py -v
      2. Verify all tests pass
      3. Verify no warnings about missing implementations
    Expected Result: All tests pass (GREEN)
    Failure Indicators: Any test failures, import errors
    Evidence: .sisyphus/evidence/task-5-inference-green.txt

  Scenario: Kernel classification works correctly
    Tool: Bash
    Preconditions: inference.py implemented
    Steps:
      1. Run: python -c "from nvbenchsuite.inference import classify_transformer_kernel; print(classify_transformer_kernel('volta_fp16_s1688gemm_fp16_256x128_ldg8_f2f_tn'))"
      2. Verify output is 'matmul' or 'gemm'
      3. Run: python -c "from nvbenchsuite.inference import classify_transformer_kernel; print(classify_transformer_kernel('fused_attention_kernel'))"
      4. Verify output is 'attention'
    Expected Result: Correct kernel classifications
    Failure Indicators: Wrong classification, KeyError
    Evidence: .sisyphus/evidence/task-5-kernel-classify.txt

  Scenario: OPT model configs are correct
    Tool: Bash
    Preconditions: inference.py implemented
    Steps:
      1. Run: python -c "from nvbenchsuite.inference import get_opt_model_config; print(get_opt_model_config('opt-1.3b'))"
      2. Verify output contains: num_params, num_layers, hidden_dim
      3. Verify num_params ~= 1.3e9
    Expected Result: Correct OPT-1.3B config dict
    Failure Indicators: Wrong values, missing keys
    Evidence: .sisyphus/evidence/task-5-opt-config.txt
  ```

  **Commit**: YES
  - Message: `feat(inference): implement inference analysis module (TDD GREEN phase)`
  - Files: `python/nvbenchsuite/inference.py`, `python/nvbenchsuite/__init__.py`
  - Pre-commit: `pytest tests/python/test_inference.py -v`

- [x] 6. Implement nvtx_utils.py NVTX Wrapper

  **What to do**:
  - Create `python/nvbenchsuite/nvtx_utils.py` for NVTX phase instrumentation
  - Implement `nvtx_phase_context(phase_name: str)` - context manager for NVTX range
  - Implement `NVTXInferenceWrapper` class - wraps HuggingFace model with NVTX markers
  - Implement `get_phase_from_nvtx_range(range_name: str) -> str` - parse "prefill"/"decode" from range
  - Handle graceful fallback when CUDA/NVTX unavailable (no-op context manager)
  - Make all tests from Task 4 PASS

  **Must NOT do**:
  - Do NOT require GPU for import (graceful fallback)
  - Do NOT add per-layer markers (phase-level only per user decision)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: CUDA integration, requires understanding of NVTX API
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (within Wave 2)
  - **Parallel Group**: Wave 2 (with Tasks 5, 7, 8)
  - **Blocks**: Task 9
  - **Blocked By**: Task 4

  **References**:
  - `torch.cuda.nvtx.range_push()`, `range_pop()` - Core NVTX API
  - HuggingFace `generate()` internals - Where to inject markers
  - `tests/python/conftest.py` - CUDA availability patterns

  **Acceptance Criteria**:
  - [ ] `python/nvbenchsuite/nvtx_utils.py` exists
  - [ ] `pytest tests/python/test_nvtx_utils.py -v` all tests PASS
  - [ ] Import works without GPU: `python -c "from nvbenchsuite.nvtx_utils import nvtx_phase_context"`

  **QA Scenarios**:
  ```
  Scenario: NVTX utilities tests pass
    Tool: Bash
    Preconditions: Task 4 test stubs exist
    Steps:
      1. Run: pytest tests/python/test_nvtx_utils.py -v
      2. Verify all tests pass
    Expected Result: All tests pass
    Failure Indicators: Test failures
    Evidence: .sisyphus/evidence/task-6-nvtx-green.txt

  Scenario: Graceful fallback without CUDA
    Tool: Bash
    Preconditions: May not have GPU
    Steps:
      1. Run: CUDA_VISIBLE_DEVICES="" python -c "from nvbenchsuite.nvtx_utils import nvtx_phase_context; print('import ok')"
      2. Verify no error, prints 'import ok'
    Expected Result: Import succeeds even without CUDA
    Failure Indicators: ImportError, CUDA errors
    Evidence: .sisyphus/evidence/task-6-no-cuda-fallback.txt
  ```

  **Commit**: YES
  - Message: `feat(nvtx): implement NVTX phase instrumentation utilities`
  - Files: `python/nvbenchsuite/nvtx_utils.py`, `python/nvbenchsuite/__init__.py`
  - Pre-commit: `pytest tests/python/test_nvtx_utils.py -v`

- [x] 7. Implement vram_monitor.py pynvml Utility

  **What to do**:
  - Create `python/nvbenchsuite/vram_monitor.py` for continuous VRAM monitoring
  - Implement `VRAMMonitor` class with start/stop/get_samples() methods
  - Use pynvml for GPU memory queries at 100ms resolution
  - Record: timestamp_ms, vram_used_mb, vram_total_mb, phase (if NVTX active)
  - Implement `save_vram_trace(samples: list, output_path: Path)` - save to CSV
  - Handle graceful fallback when pynvml unavailable

  **Must NOT do**:
  - Do NOT require GPU for import
  - Do NOT block main thread (use threading)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Threading, pynvml integration, non-trivial
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (within Wave 2)
  - **Parallel Group**: Wave 2 (with Tasks 5, 6, 8)
  - **Blocks**: Task 15
  - **Blocked By**: Task 1

  **References**:
  - `pynvml.nvmlDeviceGetMemoryInfo()` - Core API
  - `pynvml.nvmlInit()`, `nvmlShutdown()` - Lifecycle
  - threading module - Background monitoring

  **Acceptance Criteria**:
  - [ ] `python/nvbenchsuite/vram_monitor.py` exists
  - [ ] `pytest tests/python/test_vram_monitor.py -v` passes
  - [ ] Monitor captures samples at ~100ms intervals

  **QA Scenarios**:
  ```
  Scenario: VRAM monitor captures samples (with GPU)
    Tool: Bash
    Preconditions: GPU available, pynvml installed
    Steps:
      1. Run: python -c "from nvbenchsuite.vram_monitor import VRAMMonitor; m = VRAMMonitor(); m.start(); import time; time.sleep(0.5); m.stop(); print(len(m.get_samples()))"
      2. Verify output >= 4 (at least 4 samples in 500ms at 100ms rate)
    Expected Result: 4+ samples captured
    Failure Indicators: 0 samples, exceptions
    Evidence: .sisyphus/evidence/task-7-vram-samples.txt

  Scenario: Graceful fallback without pynvml
    Tool: Bash
    Preconditions: None
    Steps:
      1. Run: python -c "import sys; sys.modules['pynvml'] = None; from nvbenchsuite.vram_monitor import VRAMMonitor; print('ok')"
      2. Verify import succeeds
    Expected Result: Import works, monitor in no-op mode
    Failure Indicators: ImportError
    Evidence: .sisyphus/evidence/task-7-no-pynvml.txt
  ```

  **Commit**: YES
  - Message: `feat(vram): implement pynvml VRAM monitoring utility`
  - Files: `python/nvbenchsuite/vram_monitor.py`, `tests/python/test_vram_monitor.py`
  - Pre-commit: `pytest tests/python/test_vram_monitor.py -v`

- [x] 8. Extend NCU/Nsys Parsing for Transformer Kernels

  **What to do**:
  - Extend `inference.py` with transformer-specific kernel classification
  - Add kernel patterns for: FlashAttention, cuBLAS GEMM, LayerNorm, Softmax, GELU
  - Add bitsandbytes INT8/INT4 kernel patterns for quantized models
  - Implement `aggregate_by_phase(df: pd.DataFrame) -> dict` - group metrics by prefill/decode
  - Add unit tests for new kernel patterns

  **Must NOT do**:
  - Do NOT modify existing `summarize_ncu.py` (create new functions in inference.py)
  - Do NOT assume specific kernel names (use regex patterns)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Requires understanding NCU output format and kernel naming conventions
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (within Wave 2)
  - **Parallel Group**: Wave 2 (with Tasks 5, 6, 7)
  - **Blocks**: Tasks 12, 13, 14
  - **Blocked By**: None

  **References**:
  - `analysis/ldpc_colocation/summarize_ncu.py` - NCU parsing pattern
  - FlashAttention kernel names: `flash_attn_*`, `fmha_*`
  - cuBLAS patterns: `volta_*gemm*`, `ampere_*gemm*`, `sm80_*`
  - bitsandbytes: `int8_*`, `quantize_*`, `dequantize_*`

  **Acceptance Criteria**:
  - [ ] `classify_transformer_kernel()` handles 10+ kernel patterns
  - [ ] `aggregate_by_phase()` correctly groups by NVTX phase
  - [ ] Tests cover FlashAttention, cuBLAS, bitsandbytes patterns

  **QA Scenarios**:
  ```
  Scenario: Kernel classification covers transformer ops
    Tool: Bash
    Preconditions: inference.py implemented
    Steps:
      1. Run: python -c "from nvbenchsuite.inference import classify_transformer_kernel as c; print([c('flash_attn_fwd'), c('volta_fp16_s1688gemm'), c('layer_norm_kernel'), c('int8_mm_kernel')])"
      2. Verify output: ['attention', 'matmul', 'layernorm', 'quantized_matmul']
    Expected Result: Correct classifications for all patterns
    Failure Indicators: 'unknown' for known patterns
    Evidence: .sisyphus/evidence/task-8-kernel-patterns.txt
  ```

  **Commit**: YES
  - Message: `feat(inference): extend NCU parsing for transformer and quantized kernels`
  - Files: `python/nvbenchsuite/inference.py`, `tests/python/test_inference.py`
  - Pre-commit: `pytest tests/python/test_inference.py -v`

- [x] 9. Create NVTX-Instrumented Inference Runner

  **What to do**:
  - Create `scripts/run_inference_nvtx.py` - main profiling entry point
  - Load OPT model from HuggingFace (with quantization for large models)
  - Wrap inference with NVTX markers using `NVTXInferenceWrapper`
  - Separate prefill (first forward pass) from decode (subsequent tokens)
  - CLI args: --model, --seq-len, --batch-size, --max-new-tokens, --quantize (int8/int4/none)
  - Output: NVTX-annotated execution for nsys/ncu capture

  **Must NOT do**:
  - Do NOT run profiling automatically (just prepare NVTX-annotated execution)
  - Do NOT implement per-layer markers (phase-level only)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Core profiling infrastructure, HuggingFace integration
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (sequential after Wave 2)
  - **Blocks**: Tasks 10, 12-15
  - **Blocked By**: Tasks 5, 6

  **References**:
  - `python/nvbenchsuite/nvtx_utils.py` - NVTX wrapper to use
  - HuggingFace OPT: `AutoModelForCausalLM.from_pretrained("facebook/opt-125m")`
  - bitsandbytes: `load_in_8bit=True`, `load_in_4bit=True`

  **Acceptance Criteria**:
  - [ ] `python scripts/run_inference_nvtx.py --help` shows all options
  - [ ] `python scripts/run_inference_nvtx.py --model opt-125m --seq-len 128 --batch-size 1` runs successfully
  - [ ] NVTX ranges visible when profiled with nsys

  **QA Scenarios**:
  ```
  Scenario: Inference runner executes OPT-125M
    Tool: Bash
    Preconditions: OPT-125M downloaded, GPU available
    Steps:
      1. Run: python scripts/run_inference_nvtx.py --model opt-125m --seq-len 128 --batch-size 1 --max-new-tokens 10
      2. Verify exit code 0
      3. Verify output shows prefill and decode timings
    Expected Result: Successful inference with timing output
    Failure Indicators: OOM, CUDA errors, non-zero exit
    Evidence: .sisyphus/evidence/task-9-inference-run.txt

  Scenario: Quantization mode works (INT8)
    Tool: Bash
    Preconditions: bitsandbytes installed
    Steps:
      1. Run: python scripts/run_inference_nvtx.py --model opt-1.3b --seq-len 128 --batch-size 1 --quantize int8
      2. Verify model loads in INT8 mode (check VRAM < 3GB)
    Expected Result: INT8 model loads and runs
    Failure Indicators: Full FP16 VRAM usage, quantization errors
    Evidence: .sisyphus/evidence/task-9-int8-mode.txt
  ```

  **Commit**: YES
  - Message: `feat(scripts): add NVTX-instrumented inference runner for profiling`
  - Files: `scripts/run_inference_nvtx.py`
  - Pre-commit: `python scripts/run_inference_nvtx.py --help`

- [x] 10. Create Profiling Orchestration Script

  **What to do**:
  - Create `scripts/run_inference_profiling.sh` - primary user-facing super-script for profiling orchestration
  - Wrap `run_inference_nvtx.py` with nsys for timeline capture
  - Wrap with ncu for detailed metrics (ACU, GBU, SM utilization)
  - Support sweep modes: --sweep-models, --sweep-seq-lens, --sweep-batch-sizes
  - Output nsys reports to `data/nsys_reports/`, ncu to `data/ncu_reports/`
  - Convert reports to CSV using existing `nsys_rep_to_csv.sh`, `ncu_rep_to_csv.sh`
  - Write run metadata/manifest per profiling batch so experiments can be reproduced later

  **Must NOT do**:
  - Do NOT hardcode paths (use variables)
  - Do NOT run all sweeps by default (explicit flags)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Shell script, follows existing patterns
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (within Wave 3)
  - **Parallel Group**: Wave 3 (with Tasks 9, 11)
  - **Blocks**: Tasks 12-15
  - **Blocked By**: Task 9

  **References**:
  - `scripts/run_benchmarks.sh` - Existing profiling orchestration pattern
  - `scripts/profile_ldpc_gb10.sh` - LDPC-specific profiling example
  - `scripts/nsys_rep_to_csv.sh`, `scripts/ncu_rep_to_csv.sh` - Report conversion

  **Acceptance Criteria**:
  - [ ] `bash scripts/run_inference_profiling.sh --help` shows usage
  - [ ] Single model profiling works: `bash scripts/run_inference_profiling.sh --model opt-125m --seq-len 128`
  - [ ] nsys/ncu reports generated in correct directories
  - [ ] run metadata/manifest file generated for each profiling batch

  **QA Scenarios**:
  ```
  Scenario: Single model profiling generates reports
    Tool: Bash
    Preconditions: nsys/ncu installed, OPT-125M available
    Steps:
      1. Run: bash scripts/run_inference_profiling.sh --model opt-125m --seq-len 128 --batch-size 1
      2. Verify data/nsys_reports/ contains .nsys-rep file
      3. Verify data/ncu_reports/ contains .ncu-rep file
    Expected Result: Both report types generated
    Failure Indicators: Missing reports, profiler errors
    Evidence: .sisyphus/evidence/task-10-profiling-reports.txt
  ```

  **Commit**: YES
  - Message: `feat(scripts): add inference profiling orchestration script`
  - Files: `scripts/run_inference_profiling.sh`
  - Pre-commit: `bash scripts/run_inference_profiling.sh --help`

- [x] 11. Add Memory Headroom Check Utility

  **What to do**:
  - Add `check_memory_headroom(model: str, seq_len: int, batch_size: int, quantize: str) -> bool` to inference.py
  - Estimate required VRAM based on model size, sequence length, batch size
  - Query available VRAM via pynvml
  - Return True if sufficient headroom (>10% margin), False otherwise
  - Integrate into `run_inference_nvtx.py` as pre-flight check

  **Must NOT do**:
  - Do NOT proceed with profiling if headroom check fails
  - Do NOT underestimate memory (use conservative estimates)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single utility function, straightforward logic
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (within Wave 3)
  - **Parallel Group**: Wave 3 (with Tasks 9, 10)
  - **Blocks**: Tasks 12-15
  - **Blocked By**: Task 1

  **References**:
  - OPT memory estimates from librarian research
  - `python/nvbenchsuite/vram_monitor.py` - pynvml usage pattern
  - bitsandbytes memory reduction: INT8 ~50%, INT4 ~75%

  **Acceptance Criteria**:
  - [ ] `check_memory_headroom("opt-6.7b", 2048, 1, "none")` returns False on 24GB GPU
  - [ ] `check_memory_headroom("opt-6.7b", 512, 1, "int8")` returns True on 24GB GPU
  - [ ] Function integrated into inference runner pre-flight

  **QA Scenarios**:
  ```
  Scenario: Headroom check rejects OOM config
    Tool: Bash
    Preconditions: GPU available
    Steps:
      1. Run: python -c "from nvbenchsuite.inference import check_memory_headroom; print(check_memory_headroom('opt-30b', 2048, 1, 'none'))"
      2. Verify output is False (30B model won't fit in FP16)
    Expected Result: False
    Failure Indicators: True (would cause OOM)
    Evidence: .sisyphus/evidence/task-11-headroom-reject.txt

  Scenario: Headroom check accepts valid config
    Tool: Bash
    Preconditions: GPU available
    Steps:
      1. Run: python -c "from nvbenchsuite.inference import check_memory_headroom; print(check_memory_headroom('opt-125m', 512, 1, 'none'))"
      2. Verify output is True
    Expected Result: True
    Failure Indicators: False for small model
    Evidence: .sisyphus/evidence/task-11-headroom-accept.txt
  ```

  **Commit**: YES
  - Message: `feat(inference): add memory headroom check utility`
  - Files: `python/nvbenchsuite/inference.py`, `scripts/run_inference_nvtx.py`
  - Pre-commit: `pytest tests/python/test_inference.py -v`

- [x] 12. Experiment A: ACU vs GBU Scatter Plot

  **What to do**:
  - Create `analysis/profile_inference_acu_gbu.py` - generates Weaver Exp. 2 style scatter
  - Parse NCU CSV outputs from profiling runs
  - Extract ACU (`sm__throughput.avg.pct_of_peak_sustained_elapsed`) and GBU (`dram__throughput.avg.pct_of_peak_sustained_elapsed`)
  - Group data points by phase (prefill/decode) using NVTX markers
  - Include LDPC data points for comparison (from existing profiling)
  - Generate scatter plot: X=GBU%, Y=ACU%, color=workload_type (prefill/decode/LDPC)
  - Use `plot_utils.py` `paper_style()` and `WONG_PALETTE` for Weaver-style visualization
  - Output: PDF + PNG to `analysis/figures/exp_a_acu_gbu_scatter.{pdf,png}`
  - Output: CSV to `analysis/data/exp_a_acu_gbu_data.csv`

  **Must NOT do**:
  - Do NOT include training workloads
  - Do NOT modify plot_utils.py

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Data processing, visualization, Weaver methodology replication
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (within Wave 4)
  - **Parallel Group**: Wave 4 (with Tasks 13, 14, 15)
  - **Blocks**: Task 16, F1-F4
  - **Blocked By**: Tasks 8, 9, 10, 11

  **References**:
  - `analysis/plot_ncu_flops_bw.py` - Similar scatter plot pattern
  - `analysis/plot_utils.py:paper_style()`, `WONG_PALETTE` - Styling
  - Weaver paper Figure X - ACU vs GBU scatter reference
  - `analysis/ldpc_colocation/summarize_ncu.py` - NCU CSV parsing

  **Acceptance Criteria**:
  - [ ] `analysis/figures/exp_a_acu_gbu_scatter.pdf` exists and is non-empty
  - [ ] `analysis/data/exp_a_acu_gbu_data.csv` has columns: model, phase, acu_pct, gbu_pct, seq_len, batch_size
  - [ ] Prefill points cluster in high-ACU region (ACU > GBU)
  - [ ] Decode points cluster in high-GBU region (GBU > ACU)

  **QA Scenarios**:
  ```
  Scenario: Scatter plot generated with correct data
    Tool: Bash
    Preconditions: Profiling data exists in data/ncu_reports/
    Steps:
      1. Run: python analysis/profile_inference_acu_gbu.py --input-dir data/ncu_reports/ --output-dir analysis/figures/
      2. Verify: ls -la analysis/figures/exp_a_acu_gbu_scatter.pdf
      3. Verify file size > 10KB
      4. Run: head -5 analysis/data/exp_a_acu_gbu_data.csv
      5. Verify columns: model,phase,acu_pct,gbu_pct,seq_len,batch_size
    Expected Result: PDF generated, CSV has correct structure
    Failure Indicators: Missing file, empty file, wrong columns
    Evidence: .sisyphus/evidence/task-12-scatter-output.txt

  Scenario: Phase separation shows expected characteristics
    Tool: Bash
    Preconditions: exp_a_acu_gbu_data.csv exists
    Steps:
      1. Run: python -c "import pandas as pd; df=pd.read_csv('analysis/data/exp_a_acu_gbu_data.csv'); prefill=df[df.phase=='prefill']; print(f'Prefill mean ACU:{prefill.acu_pct.mean():.1f} GBU:{prefill.gbu_pct.mean():.1f}')"
      2. Verify prefill ACU > GBU (compute-bound)
      3. Run similar for decode, verify GBU > ACU (memory-bound)
    Expected Result: Prefill ACU>GBU, Decode GBU>ACU
    Failure Indicators: Reversed characteristics
    Evidence: .sisyphus/evidence/task-12-phase-characteristics.txt
  ```

  **Commit**: YES
  - Message: `feat(analysis): add Experiment A - ACU vs GBU scatter plot`
  - Files: `analysis/profile_inference_acu_gbu.py`, `tests/python/test_experiments.py`
  - Pre-commit: `python -m py_compile analysis/profile_inference_acu_gbu.py`

- [x] 13. Experiment B: Workload Characteristics Table

  **What to do**:
  - Create `analysis/generate_workload_table.py` - generates Weaver Exp. 3 style table
  - Aggregate profiling data to compute summary statistics per workload type
  - Columns (matching Weaver Table 2): Workload, Dominant Op, Compute %, Bandwidth %, SM %
  - Rows: Prefill (various models), Decode (various models), LDPC (for comparison)
  - Identify dominant operation per phase (attention vs matmul vs memory)
  - Output: CSV table to `analysis/data/exp_b_workload_table.csv`
  - Output: LaTeX table to `analysis/data/exp_b_workload_table.tex` (for paper)
  - Output: Rendered PDF to `analysis/figures/exp_b_workload_table.pdf`

  **Must NOT do**:
  - Do NOT include training workloads
  - Do NOT hardcode values (compute from profiling data)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Data aggregation, LaTeX generation
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (within Wave 4)
  - **Parallel Group**: Wave 4 (with Tasks 12, 14, 15)
  - **Blocks**: Task 16, F1-F4
  - **Blocked By**: Tasks 8, 9, 10

  **References**:
  - Weaver paper Table 2 - Workload characteristics reference
  - `analysis/data/exp_a_acu_gbu_data.csv` - Source data
  - pandas `groupby()`, `agg()` for aggregation

  **Acceptance Criteria**:
  - [ ] `analysis/data/exp_b_workload_table.csv` exists with correct columns
  - [ ] CSV has rows for: prefill, decode, LDPC
  - [ ] Compute % + Bandwidth % values are in valid range [0, 100]

  **QA Scenarios**:
  ```
  Scenario: Workload table generated correctly
    Tool: Bash
    Preconditions: Experiment A data exists
    Steps:
      1. Run: python analysis/generate_workload_table.py --input analysis/data/exp_a_acu_gbu_data.csv --output analysis/data/exp_b_workload_table.csv
      2. Run: cat analysis/data/exp_b_workload_table.csv
      3. Verify columns: workload,dominant_op,compute_pct,bandwidth_pct,sm_pct
      4. Verify prefill row exists with dominant_op containing 'matmul' or 'attention'
    Expected Result: Valid CSV with expected structure
    Failure Indicators: Missing columns, invalid values
    Evidence: .sisyphus/evidence/task-13-workload-table.txt

  Scenario: LaTeX output compiles
    Tool: Bash
    Preconditions: exp_b_workload_table.tex exists
    Steps:
      1. Run: cat analysis/data/exp_b_workload_table.tex | head -20
      2. Verify contains \begin{tabular}
    Expected Result: Valid LaTeX table markup
    Failure Indicators: Invalid LaTeX syntax
    Evidence: .sisyphus/evidence/task-13-latex-output.txt
  ```

  **Commit**: YES
  - Message: `feat(analysis): add Experiment B - workload characteristics table`
  - Files: `analysis/generate_workload_table.py`
  - Pre-commit: `python -m py_compile analysis/generate_workload_table.py`

- [x] 14. Experiment C: Perplexity/Latency Heatmaps

  **What to do**:
  - Create `analysis/generate_heatmaps.py` - generates utilization heatmaps
  - Heatmap 1: Perplexity vs Model Size vs Quantization (accuracy impact)
  - Heatmap 2: TTFT (Time to First Token) vs Seq Length vs Batch Size (prefill latency)
  - Heatmap 3: Tokens/sec vs Seq Length vs Batch Size (decode throughput)
  - Heatmap 4: ACU vs Seq Length vs Model Size (compute utilization)
  - Heatmap 5: GBU vs Seq Length vs Model Size (bandwidth utilization)
  - Compute perplexity using WikiText-2 evaluation
  - Use seaborn heatmap with `plot_utils.py` styling
  - Output: PDF + PNG for each heatmap to `analysis/figures/exp_c_heatmap_*.{pdf,png}`

  **Must NOT do**:
  - Do NOT include training metrics
  - Do NOT use random/synthetic data (real profiling results only)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Multiple visualizations, perplexity evaluation
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (within Wave 4)
  - **Parallel Group**: Wave 4 (with Tasks 12, 13, 15)
  - **Blocks**: Task 16, F1-F4
  - **Blocked By**: Tasks 8, 9, 10

  **References**:
  - `analysis/plot_compute_util_heatmap.py` - Existing heatmap pattern
  - `analysis/plot_utils.py` - Styling utilities
  - `lm_eval` or HuggingFace `evaluate` - Perplexity computation
  - seaborn `heatmap()` - Visualization

  **Acceptance Criteria**:
  - [ ] 5 heatmap PDFs generated in `analysis/figures/exp_c_heatmap_*.pdf`
  - [ ] Perplexity values are reasonable (< 50 for good models)
  - [ ] Latency values show expected trends (longer seq = slower)

  **QA Scenarios**:
  ```
  Scenario: Heatmaps generated for all metrics
    Tool: Bash
    Preconditions: Profiling data exists
    Steps:
      1. Run: python analysis/generate_heatmaps.py --input-dir data/ncu_reports/ --output-dir analysis/figures/
      2. Run: ls analysis/figures/exp_c_heatmap_*.pdf | wc -l
      3. Verify count >= 5
    Expected Result: 5+ heatmap PDFs generated
    Failure Indicators: Fewer than 5 files
    Evidence: .sisyphus/evidence/task-14-heatmap-count.txt

  Scenario: Perplexity values are valid
    Tool: Bash
    Preconditions: Heatmap data generated
    Steps:
      1. Run: python -c "import pandas as pd; df=pd.read_csv('analysis/data/exp_c_perplexity.csv'); print(df.perplexity.describe())"
      2. Verify mean perplexity < 100, min > 1
    Expected Result: Reasonable perplexity range
    Failure Indicators: Infinite, NaN, or extreme values
    Evidence: .sisyphus/evidence/task-14-perplexity-values.txt
  ```

  **Commit**: YES
  - Message: `feat(analysis): add Experiment C - perplexity/latency heatmaps`
  - Files: `analysis/generate_heatmaps.py`
  - Pre-commit: `python -m py_compile analysis/generate_heatmaps.py`

- [x] 15. Experiment D: VRAM Footprint Analysis

  **What to do**:
  - Create `analysis/profile_vram.py` - VRAM memory usage analysis
  - Use `VRAMMonitor` to capture VRAM timeseries during inference
  - Generate timeseries plot: X=time(ms), Y=VRAM_used(MB), color=phase
  - Show clear prefill→decode transition point
  - Compute metrics: peak VRAM, mean VRAM, VRAM growth rate (MB/token)
  - Compare VRAM across models and quantization modes
  - Output: Timeseries plot to `analysis/figures/exp_d_vram_timeseries.pdf`
  - Output: Summary table to `analysis/data/exp_d_vram_summary.csv`

  **Must NOT do**:
  - Do NOT report theoretical estimates (measure actual usage)
  - Do NOT aggregate away phase transitions (show them clearly)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Real-time monitoring integration, analysis
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (within Wave 4)
  - **Parallel Group**: Wave 4 (with Tasks 12, 13, 14)
  - **Blocks**: Task 16, F1-F4
  - **Blocked By**: Tasks 7, 9, 10

  **References**:
  - `python/nvbenchsuite/vram_monitor.py` - Monitoring utility
  - matplotlib timeseries plotting
  - `analysis/plot_utils.py` - Styling

  **Acceptance Criteria**:
  - [ ] `analysis/figures/exp_d_vram_timeseries.pdf` shows clear phase transition
  - [ ] `analysis/data/exp_d_vram_summary.csv` has columns: model, quantize, peak_vram_mb, mean_vram_mb, growth_rate_mb_per_token
  - [ ] Peak VRAM for OPT-125M < 2GB

  **QA Scenarios**:
  ```
  Scenario: VRAM timeseries shows phase transition
    Tool: Bash
    Preconditions: OPT-125M available, GPU available
    Steps:
      1. Run: python analysis/profile_vram.py --model opt-125m --seq-len 256 --output analysis/figures/exp_d_vram_timeseries.pdf
      2. Verify PDF exists and size > 10KB
      3. Run: head -5 analysis/data/exp_d_vram_summary.csv
      4. Verify columns present
    Expected Result: PDF with timeseries, CSV with summary
    Failure Indicators: Flat line (no transition), missing data
    Evidence: .sisyphus/evidence/task-15-vram-timeseries.txt

  Scenario: VRAM values are plausible
    Tool: Bash
    Preconditions: exp_d_vram_summary.csv exists
    Steps:
      1. Run: python -c "import pandas as pd; df=pd.read_csv('analysis/data/exp_d_vram_summary.csv'); opt125=df[df.model=='opt-125m']; print(f'Peak: {opt125.peak_vram_mb.values[0]:.0f}MB')"
      2. Verify OPT-125M peak < 2000 MB
    Expected Result: Peak VRAM ~500-1500MB for OPT-125M
    Failure Indicators: 0, negative, or > 10GB
    Evidence: .sisyphus/evidence/task-15-vram-values.txt
  ```

  **Commit**: YES
  - Message: `feat(analysis): add Experiment D - VRAM footprint analysis`
  - Files: `analysis/profile_vram.py`
  - Pre-commit: `python -m py_compile analysis/profile_vram.py`

- [x] 16. Update README and Documentation

  **What to do**:
  - Update `README.md` with inference profiling usage instructions
  - Add section: "FM Inference Profiling" with quick-start guide
  - Document all new CLI tools: `download_opt_models.py`, `run_inference_nvtx.py`, `run_inference_profiling.sh`
  - Document experiment scripts and expected outputs
  - Add troubleshooting section for common issues (OOM, ncu permissions, missing models)
  - Update CLAUDE.md if needed (add inference module to function graph)

  **Must NOT do**:
  - Do NOT remove existing documentation
  - Do NOT document unimplemented features

  **Recommended Agent Profile**:
  - **Category**: `writing`
    - Reason: Documentation task
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 5 (after all experiments)
  - **Blocks**: F1-F4
  - **Blocked By**: Tasks 12-15

  **References**:
  - `README.md` - Existing documentation structure
  - `CLAUDE.md` - AI guidance document
  - All new scripts and their --help outputs

  **Acceptance Criteria**:
  - [ ] README.md contains "FM Inference Profiling" section
  - [ ] All new CLI tools documented with examples
  - [ ] Troubleshooting section exists

  **QA Scenarios**:
  ```
  Scenario: README has inference profiling section
    Tool: Bash
    Preconditions: None
    Steps:
      1. Run: grep -c "FM Inference Profiling" README.md
      2. Verify count >= 1
      3. Run: grep -c "run_inference_nvtx.py" README.md
      4. Verify documented
    Expected Result: Section exists, tools documented
    Failure Indicators: grep returns 0
    Evidence: .sisyphus/evidence/task-16-readme-check.txt
  ```

  **Commit**: YES
  - Message: `docs: add FM inference profiling documentation`
  - Files: `README.md`, `CLAUDE.md`
  - Pre-commit: N/A

---

## Final Verification Wave

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, run command). For each "Must NOT Have": search codebase for forbidden patterns. Check evidence files exist in `.sisyphus/evidence/`. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run `python -m py_compile python/nvbenchsuite/inference.py` + linter + `pytest tests/python/test_inference.py -v`. Review all new files for: type hints, docstrings, error handling. Check for AI slop: excessive comments, over-abstraction.
  Output: `Compile [PASS/FAIL] | Tests [N pass/N fail] | Quality [N issues] | VERDICT`

- [x] F3. **Real QA Execution** — `unspecified-high` (+ `playwright` if needed)
  Start from clean state. Run OPT-125M profiling end-to-end. Execute QA scenarios from Tasks 12-15. Verify CSV outputs have expected columns and value ranges. Verify plots generated in `analysis/figures/`.
  Output: `Scenarios [N/N pass] | Files Generated [N/N] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", verify actual implementation matches. Check "Must NOT do" compliance (no training code, no multi-GPU, no per-layer NVTX). Flag any scope creep.
  Output: `Tasks [N/N compliant] | Guardrails [N/N respected] | VERDICT`

---

## Commit Strategy

| Commit | Scope | Files | Pre-commit Check |
|--------|-------|-------|------------------|
| 1 | Device constants | `data/device_constants.json` | `python -c "from nvbenchsuite.utils import _load_device_constants; print('RTX A5000' in str(_load_device_constants()))"` |
| 2 | Model download | `scripts/download_opt_models.py` | `python scripts/download_opt_models.py --help` |
| 3 | Test stubs | `tests/python/test_inference.py` | `pytest tests/python/test_inference.py -v` (expect failures) |
| 4 | inference.py | `python/nvbenchsuite/inference.py` | `pytest tests/python/test_inference.py -v` |
| 5 | NVTX utils | `python/nvbenchsuite/nvtx_utils.py` | `pytest tests/python/test_nvtx_utils.py -v` |
| 6 | VRAM monitor | `python/nvbenchsuite/vram_monitor.py` | `pytest tests/python/test_vram_monitor.py -v` |
| 7 | NCU/nsys extensions | `python/nvbenchsuite/inference.py` | `pytest tests/python/test_inference.py -v` |
| 8 | Inference runner | `scripts/run_inference_nvtx.py` | `python scripts/run_inference_nvtx.py --help` |
| 9 | Experiments A-D | `analysis/profile_inference_*.py`, `analysis/generate_*.py` | `pytest tests/python/test_experiments.py -v` |
| 10 | Documentation | `README.md`, `docs/` | N/A |

---

## Success Criteria

### Verification Commands
```bash
# Device constants
python -c "from nvbenchsuite.utils import _load_device_constants; d = _load_device_constants(); print(d['devices']['NVIDIA RTX A5000']['total_sms'])"
# Expected: 64

# Test suite
pytest tests/python/test_inference.py tests/python/test_nvtx_utils.py tests/python/test_vram_monitor.py -v
# Expected: All tests pass

# Experiment A output
python analysis/profile_inference_acu_gbu.py --model=opt-125m --seq-len=512 --batch-size=1 --output=test_acu_gbu.csv
# Expected: CSV with columns [model, phase, acu_pct, gbu_pct, seq_len, batch_size]

# Plot generation
ls analysis/figures/exp_a_acu_gbu_scatter.pdf analysis/figures/exp_b_workload_table.pdf
# Expected: Both files exist
```

### Final Checklist
- [x] All "Must Have" features implemented and tested
- [x] All "Must NOT Have" guardrails respected (no training, no multi-GPU, etc.)
- [x] All 4 experiments produce valid outputs
- [x] Prefill shows ACU > GBU (compute-bound characteristic)
- [x] Decode shows GBU > ACU (memory-bound characteristic)
- [x] All tests pass with TDD methodology followed
