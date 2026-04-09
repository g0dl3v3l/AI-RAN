# Learnings

## 2026-04-09T20:35:06Z Task: T1 scaffold research
- `/mnt/data/dheeraj/dicertation/inference-profile` exists and is empty, so T1 is a greenfield scaffold.
- Best local scaffold references are `DeviceEmulator/pyproject.toml` for `[tool.pytest.ini_options]`, `DeviceEmulator/morphling/entrypoint/cmdline.py` for `argparse` subparsers, and `NVBenchSuite/scripts/run_opt_single_layer_prefill_profile.py` plus `MobiCom26-Eval/evaluation/two-level-scheduling-simulator/run_full_sweep.py` for `main()` + `SystemExit` runner structure.
- No local implementation currently registers `gpu_smoke` or `remote_mock`; those markers must be added fresh in the new `pyproject.toml`.
- External packaging guidance supports `python -m inference_profile.cli` directly from `cli.py`; no package-level `__main__.py` is required for this plan.

# Learnings: T1 Package Scaffolding Research

## 1. Python Module Execution (`python -m package.cli`)

**Key Finding**: No `__main__.py` needed when using `python -m inference_profile.cli`

- `__main__.py` is only for package-level entry (`python -m package`)
- For module-level entry (`python -m package.cli`), Python executes `cli.py` directly with `__name__='__main__'`
- **Sources**: PEP 338, Python 3.14 __main__ docs (https://docs.python.org/3/library/__main__.html)

**Minimal Structure**:
```
inference_profile/
  __init__.py  ← Required (makes it a package)
  cli.py       ← Entry point (no __main__.py needed)
```

**In cli.py**:
```python
import argparse, sys

def main():
    # argparse setup and dispatch
    pass

if __name__ == '__main__':
    sys.exit(main())
```

---

## 2. pytest Markers in pyproject.toml

**Recommended** (pytest 9.0+, TOML-native):
```toml
[tool.pytest]
markers = [
    "gpu_smoke: mark tests as GPU smoke tests",
    "remote_mock: mark tests as remote-mocked integration tests",
]
```

**Best Practices**:
- Use underscores in marker names (not hyphens)
- Always include description after `:` for CLI help
- Set `addopts = ["--strict-markers"]` to catch typos
- **Source**: https://docs.pytest.org/en/stable/how-to/mark.html

---

## 3. argparse Subcommands Pattern

**Key Pattern**: `add_subparsers(dest='stage')` + `set_defaults(func=handler)` + dispatch via `args.func(args)`

**Minimal Example**:
```python
parser = argparse.ArgumentParser()
subparsers = parser.add_subparsers(dest='stage', required=True)

# Subcommand 1
inspect = subparsers.add_parser('inspect-model')
inspect.add_argument('--model', required=True)
inspect.set_defaults(func=handle_inspect)

# Dispatch
args = parser.parse_args()
sys.exit(args.func(args) or 0)
```

**Result**: Enables `python -m inference_profile.cli inspect-model --model X`

**Source**: Real Python (https://www.realpython.com/command-line-interfaces-python-argparse/)

---

## 4. T1 Scaffold Checklist

✓ Package structure: `__init__.py` + `cli.py`
✓ Module execution: `python -m inference_profile.cli --help` works
✓ Markers: `[tool.pytest]` with `gpu_smoke` and `remote_mock`
✓ Subcommands: Use `add_subparsers(dest='stage')` + `set_defaults(func=handler)`
✓ No `__main__.py` wrapper needed for module-level entry
✓ Dispatch pattern: `args.func(args)` with proper exit codes

---

## Official References Used

1. Python 3.14 `__main__` module: https://docs.python.org/3/library/__main__.html
2. PEP 338 (Executing modules as scripts): https://peps.python.org/pep-0338/
3. pytest markers how-to: https://docs.pytest.org/en/stable/how-to/mark.html
4. pytest pyproject.toml config: https://docs.pytest.org/en/stable/reference/customize.html
5. Python argparse stdlib: https://docs.python.org/3/library/argparse.html
6. Real Python argparse tutorial: https://www.realpython.com/command-line-interfaces-python-argparse/

## 2026-04-09T20:55:37Z Task: T1 scaffold implementation
- Created the greenfield `inference-profile/` root-package scaffold with `pyproject.toml`, a minimal README, `inference_profile/__init__.py`, `inference_profile/cli.py`, `inference_profile/constants.py`, and focused unit tests under `tests/unit/`.
- Kept the CLI contract intentionally honest: one `build_parser()` function with the eight fixed argparse subcommands, `raise SystemExit(main())` in the module guard, and a clear non-implemented exit path for actual subcommand execution so Task 1 does not pretend later stages already work.
- Registered pytest via `[tool.pytest.ini_options]` with `pythonpath = ["."]`, `--strict-markers`, and the new `gpu_smoke` plus `remote_mock` markers; encoded the fixed OPT sweep, remote paths, local fetch root, sshpass file, and remote trace defaults as module-level constants.

## 2026-04-09T21:05:00Z Task: T2 manifest/path research
- Best local manifest/status schema references are `NVBenchSuite/data/opt_single_layer_prefill/raw/gpu0/facebook_opt-125m/layer_manifest.json`, `NVBenchSuite/data/opt_single_layer_prefill/raw/gpu0/single_layer_event_manifest.csv`, `NVBenchSuite/data/profiling_manifest_20260402_170613.json`, and `NVBenchSuite/data/exp_a_wave_manifest.csv`.
- Best local per-run artifact layout references are `MobiCom26-Eval/evaluation/two-level-scheduling-simulator/run_trace_driven_eval.py`, `.../metrics_writer.py`, and the `results/<run-name>/` tree documented in `.../README.md`, but they do not provide the exact `logs/raw/derived/plots/checksums` split required by the plan.
- There is no existing local `run_manifest.json`, `environment.json`, `checksums/sha256sums.txt`, or self-excluding bundle checksum writer to reuse directly; Task 2 must introduce those contracts fresh.
- External guidance for T2 is straightforward: use `pathlib.Path`, sorted relative-path traversal for determinism, SHA256 over file bytes, and a two-space `sha256sum`-style manifest line format that excludes `checksums/sha256sums.txt` itself.

## 2026-04-09T21:20:00Z Task: T2 manifest/path implementation
- `paths.py` now treats the run bundle as a fixed `runs/<run_id>/` contract with canonical roots for `run_manifest.json`, `environment.json`, `ran_inference_profiling_report.md`, and `checksums/sha256sums.txt`, plus placeholder creation so later stages can overwrite them without changing names.
- `manifests.py` keeps the public status taxonomy frozen to the nine plan-approved terminal values, stores bundle layout as run-root-relative strings, and appends per-stage history entries instead of replacing prior attempts.
- Checksum writing is deterministic by expanding only caller-declared required files/directories, sorting by run-root-relative POSIX paths, hashing file bytes with SHA256, and always excluding `checksums/sha256sums.txt` from its own manifest.

## 2026-04-09T21:XX:XX Z Task: T3 shard-index parsing research

Real-world GitHub production examples researched for Task 3 (model asset loading with selective shard resolution).

### Top 5 Production References (by signal)

1. **AirLLM** (`split_and_save_layers()`) — PRIMARY REFERENCE
   - Parses `index['weight_map']` to map params → shard files
   - Selectively downloads only shard files containing target layer
   - Detects format: `pytorch_model.bin.index.json` vs `model.safetensors.index.json`
   - Uses `huggingface_hub.snapshot_download(allow_patterns=...)` for selective fetch
   - **Permalink**: https://github.com/lyogavin/airllm/blob/main/air_llm/airllm/utils.py#L207-L298
   - **Copy**: ✅ Index parsing, per-layer shard resolution, `allow_patterns` usage
   - **Avoid**: ❌ ModelPersister abstraction, quantization logic

2. **LlamaFactory** (`fsdp2.py` checkpoint loading) — FORMAT DETECTION
   - Robust existence checks for index files before parsing
   - Deduplicates shard names (multiple layers in one shard)
   - Safe pattern for format detection order
   - **Permalink**: https://github.com/hiyouga/LlamaFactory/blob/main/src/llamafactory/v1/plugins/trainer_plugins/distributed/fsdp2.py#L321-L340
   - **Copy**: ✅ Defensive checks, deduplication pattern
   - **Avoid**: ❌ FSDP/trainer logic, quantization

3. **Hugging Face Official** (`huggingface_hub` API docs) — STANDARD PATTERNS
   - `snapshot_download(repo_id, allow_patterns=[...])` standard for selective download
   - `hf_hub_download(repo_id, filename="config.json")` for individual files
   - **Source**: https://huggingface.co/docs/huggingface_hub/en/guides/download
   - **API Recommendation**: Fetch config + index first, then `snapshot_download` with `allow_patterns` for needed shards
   - **Copy**: ✅ Official API usage patterns

4. **PyTorch AO** (`create_weight_map.py`) — SCHEMA REFERENCE
   - Shows exact weight_map structure: `{param_name → shard_file}`
   - Confirms each param maps to EXACTLY ONE shard (deterministic)
   - **Permalink**: https://github.com/pytorch/ao/blob/main/scripts/create_weight_map.py
   - **Copy**: ✅ Schema understanding for robust parsing

5. **Exo** (`download_utils.py`) — LOCAL CACHING PATTERN
   - Index-aware file scanning (build file list from index, not directory)
   - Handles partial downloads gracefully
   - **Permalink**: https://github.com/exo-explore/exo/blob/main/src/exo/download/download_utils.py#L222-L290
   - **Copy**: ✅ Defensive detection, partial-download tracking for manifest

### Synthetic Fallback (No Prod Reference Found)

Plan requirement: "fall back to deterministic seeded FP16 layer tensors if index missing"

No production implementations found. Recommended approach:
- Use `torch.manual_seed(base_seed + layer_idx)` for determinism
- Generate layer shapes from `config.json` (hidden_size, num_hidden_layers, etc.)
- Record in manifest: `layer_source="synthetic_fallback"`, `seed=42`, `reason="monolithic_only"`

### Task 3 Implementation Path

```
1. Fetch config.json + index JSON (separate calls, avoid full-model download)
2. Parse index['weight_map'] → extract n_layers and layer→shard mapping
3. If index missing → SYNTHETIC FALLBACK path
4. If index exists → selective shard path:
   - Use snapshot_download(allow_patterns=[needed_shards, "config.json"])
   - Load shards with torch.load or safetensors.load_file
   - Filter by layer prefix "model.layers.{idx}."
5. Manifest: Track layer_source ("index_shard" vs "synthetic_fallback"), shard files, seed
```

### Key Takeaways

- **Weight_map parsing is the core pattern**: map params to shard files, dedup shard list, selective download only those files
- **`allow_patterns` is mandatory**: avoids full-model download (plan requirement: "never intentionally download full model monolith")
- **Format detection order matters**: Try `.safetensors.index.json` first, then `.pytorch_model.bin.index.json`
- **Layer count inference**: `len(set([int(k.split('.')[2]) for k in index.keys() if 'model.layers' in k]))`
- **Synthetic fallback is fresh implementation**: use config shapes + deterministic seed

### References Used

- PaddlePaddle/PaddleNLP (env.py) — Index file naming constants
- tinygrad (llama3.py) — Index detection pattern
- LLamaFactory (fsdp2.py) — Checkpoint loading pattern
- PyTorch AO — Schema reference
- Hugging Face official docs — API patterns
- Exo explore — Local scanning pattern

## 2026-04-09T21:35:00Z Task: T3 normalized implementation brief
- Best local code reuse for Task 3 is `NVBenchSuite/python/nvbenchsuite/opt_single_layer_profile.py` for middle-layer selection, index probing, shard-prefix filtering, and single-file HF fetch patterns; `DeviceEmulator/morphling/utils/hfparser.py` is the cleanest local source for OPT config field names.
- Official Hugging Face docs support `hf_hub_download(repo_id, filename="config.json")` for single-file config fetches and `snapshot_download(..., allow_patterns=[...])` for allow-listed shard downloads; full snapshot download is not required as the normal path.
- Task 3 must introduce fresh logic for the monolithic-checkpoint case: do not download a monolithic `.bin`/`.safetensors` file, generate deterministic seeded FP16 layer tensors instead, and record `synthetic_fallback` in the manifest/output.
- Best local test reuse comes from `NVBenchSuite/tests/python/test_opt_single_layer_capture_replay.py` and `test_inference.py` for config/layer derivation, plus `DeviceEmulator`/`MobiCom26-Eval` subprocess smoke patterns for the `inspect-model` CLI test.
- No local test currently asserts the exact `asset_source in {"layer_shard", "synthetic_fallback"}` policy or bans `full_model_download`; Task 3 must add that coverage from scratch.

## 2026-04-09T21:45:44Z Task: T3 inspect-model implementation
- `inference_profile/opt_assets.py` now keeps Task 3 fully config/index driven: `inspect_model()` always fetches `config.json`, probes `model.safetensors.index.json` before `pytorch_model.bin.index.json`, resolves `model.decoder.layers.{idx}.` first with `decoder.layers.{idx}.` fallback, and only calls `snapshot_download(..., allow_patterns=[...])` for the deduplicated target-layer shard filenames.
- Monolithic-only or unusable-index repos are handled truthfully as `synthetic_fallback`: no intentional `pytorch_model.bin` / `model.safetensors` download, `raw/asset_manifest.json` records the fallback reason, and the synthetic layer metadata stores deterministic FP16 tensor shapes plus a seeded parameter list (`seed = 42 + layer_index`).
- The analytical OPT byte math is deterministic from config alone: `layer_weight_bytes` counts one decoder layer (`4*h^2 + 2*h*ffn + ffn + 9*h` params), `total_weight_bytes_fp16` adds embeddings, optional project_in/project_out, all decoder layers, and the optional decoder final norm without double-counting the tied LM head, and `vram_ceiling_bytes` is `total_weight_bytes_fp16 + (4 * hidden_size * num_hidden_layers * max_position_embeddings)` so later decode-runway math can reuse the same ceiling.

## 2026-04-09T21:53:37Z Task: T3 verification fixes
- `inspect-model` now treats unsupported models as a user-facing CLI error instead of an uncaught traceback: `cli.py` wraps Task 3 input/config failures and exits with a short `Error: ...` line while leaving the other scaffolded subcommands on their existing not-implemented exit path.
- `vram_ceiling_bytes` is no longer derived from model demand; Task 3 now computes it as `floor(0.60 * total_gpu_memory_bytes)` from runtime GPU properties when CUDA is available, and falls back to `0` on the current local non-CUDA machine so the field stays present without inventing hardware capacity.
- The Task 3 tests now pin the corrected semantics explicitly: byte-estimator unit tests only lock the config-derived weight math, integration tests inject a deterministic GPU-memory value for shard/fallback cases, and a subprocess test asserts the unsupported-model CLI path prints a clean error with no Python traceback.

## 2026-04-09T22:05:00Z Task: T4 normalized implementation brief
- Best local strict parser/fail-fast reuse is `DeviceEmulator/morphling/runtime/ldpc_trace_adapter.py` plus `DeviceEmulator/scripts/validate_traces.py`: required-column checks, numeric coercion, NaN rejection, and non-decreasing `time_slot_sched_ns` validation already exist there.
- Best local interval-derivation reuse is `sionna-rk/scripts/analyze-ldpc-sm-timeline.py`: it uses `np.diff` and fills the last interval with a median delta, though Task 4 must add positive-delta filtering and fail-closed semantics instead of sorting or silently repairing traces.
- There is no local parser for schema A (`time_ms,sm_utilization`), no local `source_schema` tagging, and no existing code that emits `derived/normalized_ldpc_trace.csv`, `raw/trace_inspection.json`, or `raw/validation_errors.csv`; those are fresh Task 4 work.
- Local readers frequently rebase timestamps to `t0`; Task 4 must preserve the plan’s exact normalization rules, including schema-B `time_ms = time_slot_sched_ns / 1e6` and the plan-specific binary `sm_utilization` mapping.
- Best local test/fixture style comes from `DeviceEmulator/tests/python/unit/test_ldpc_adapter.py` for tiny CSV fixtures and `inference-profile/tests/integration/test_inspect_model_cli.py` for CLI success/failure smoke structure.
- No local fixture currently covers duplicate headers, BOM/corrupt encoding, or fail-closed assertions that `raw/validation_errors.csv` exists while `derived/normalized_ldpc_trace.csv` does not; Task 4 must add those fixtures from scratch under `inference-profile/tests/fixtures/`.

## 2026-04-09T22:30:00Z Task: T4 trace contract implementation
- The chosen Task 4 contract is fail-closed on primary-trace errors only: malformed `ldpc_trace.csv` writes `raw/validation_errors.csv`, always writes `raw/trace_inspection.json`, removes any stale `derived/normalized_ldpc_trace.csv`, and exits non-zero through the CLI.
- Primary normalization accepts only exact schema A (`time_ms,sm_utilization`) or exact schema B (`time_slot_sched_ns,sm_count`), preserves absolute schema-B timestamps via `time_slot_sched_ns / 1e6`, maps schema-B utilization to binary `0/100`, and derives the last `slot_duration_ms` from the median positive forward delta rather than rebasing or repairing rows.
- `ran_ctrl_trace.csv` is inspected structurally only (header, row count, monotonicity, and time-unit hints) with an explicit `used_for_scheduler_capacity = false` flag so secondary-trace problems are visible in inspection JSON but do not silently replace or repair the primary scheduler input.

## 2026-04-09T22:50:00Z Task: T5 normalized implementation brief
- Best local implementation references for Task 5 are `NVBenchSuite/scripts/run_exp_a_all_waves.py` for timeout/status orchestration, `NVBenchSuite/scripts/run_opt_single_layer_prefill_profile.py` for failure-manifest fields, and `MobiCom26-Eval/.../run_opt_single_layer_training_step_sweep.py` for CUDA OOM classification.
- There is no production-local explicit `multiprocessing.get_context("spawn")` worker runner to copy directly; Task 5 must introduce fresh spawn-only worker infrastructure.
- Best local test patterns are `inference-profile/tests/integration/test_validate_traces_cli.py` and `test_inspect_model_cli.py` for subprocess success/failure smoke, plus `DeviceEmulator/tests/python/integration/test_trace_analysis_smoke.py` for timeout-aware helper structure.
- Hidden-risk guardrail: the parent process should own final point status and use file-backed child artifacts/logs rather than queues/pipes, so timeouts, abnormal exits, and partial outputs remain unambiguous.
- Because the public status taxonomy is already frozen, timeout should remain a failure cause under `profile_failed` rather than a new public status.

## 2026-04-09 Task: T5 spawned worker contract
- `worker_profile_point.py` now keeps the parent/child boundary intentionally tiny and JSON-only: the parent writes one `*.worker-spec.json`, launches one fresh `multiprocessing.get_context("spawn")` child, and reads one file-backed `*.worker-result.json` plus `logs/*.stdout.log` / `logs/*.stderr.log` to decide the final public status.
- Child behavior is import-safe and testable without CUDA kernels because the spec carries a dotted callable path; top-level test helpers can write raw CSV rows through `RawCsvWriter`, raise `RuntimeError` or `torch.OutOfMemoryError`, or sleep for timeout coverage while the parent still preserves point id, public status, failure kind/cause, timeout flag, exit metadata, log paths, and any partial raw CSV evidence.

## 2026-04-09T23:30:00Z Task: T6 normalized implementation brief
- Best local implementation reuse for Task 6 is split across repos: `NVBenchSuite/python/nvbenchsuite/opt_single_layer_profile.py` for isolated OPT layer loading/decomposition, `MobiCom26-Eval/.../bench_gflops_per_sm.py` or `DeviceEmulator/scripts/bench_gflops_per_sm.py` for the CUDA-event timing loop, and `MobiCom26-Eval/.../run_opt_single_layer_training_step_sweep.py` for `reset_peak_memory_stats` / `max_memory_allocated` collection.
- Official PyTorch docs confirm the correct measurement sequence: `reset_peak_memory_stats()` before the point, create `torch.cuda.Event(enable_timing=True)` start/end, record around only the GPU op, `torch.cuda.synchronize()` before reading `elapsed_time()`, and read peak/current memory after synchronization.
- No local repo already emits a `raw/prefill_events.csv` with per-op `duration_us`, `dynamic_workspace_bytes`, and `output_bytes`; Task 6 must introduce the raw schema, GPU smoke tests, and all six direct op calls fresh.
- Strong T6 guardrail: if downstream code will add parked activation bytes separately, `dynamic_workspace_bytes` should represent transient workspace only (`peak - baseline - output_bytes`) or else raw rows must preserve enough fields (`baseline_vram_bytes`, `peak_vram_bytes`, `output_bytes`) to avoid double-counting later.
- Current package has no existing `tests/gpu/` or actual `gpu_smoke` usage, so Task 6 must create new GPU smoke coverage from scratch while reusing local `tmp_path`/subprocess/file-assertion style from current integration tests.

## 2026-04-10 Task: T6 prefill microbenchmark implementation
- `inference_profile/prefill_profile.py` stays import-safe in this package by reusing `opt_assets.derive_opt_config()` plus `build_synthetic_layer_metadata()` to construct deterministic FP16 `torch.nn.Linear` modules for `q_proj`, `k_proj`, `v_proj`, `out_proj`, `fc1`, and `fc2` without depending on `transformers`.
- The Task 6 raw contract is now explicit and reducer-friendly: each `prefill_events.csv` row keeps `baseline_vram_bytes`, `peak_vram_bytes`, `dynamic_workspace_bytes = peak - baseline`, and `output_bytes`, while parked activation remains separate analytical math and lands on `fc1` for the standard OPT configs.

## 2026-04-10 Task 7 research: Blockwise decode attention and reduction logic

### Production Reference Examples (5 High-Signal Sources)

1. **FlashAttention Official `flash_attn_with_kvcache()` (Dao-AILab)**
   - URL: https://github.com/Dao-AILab/flash-attention
   - PR #678: Paged KV cache support (merged into main)
   - Foundation: `flash_attn_with_kvcache(q, k_cache, v_cache, block_table, cache_seqlens, ...)`
   - Takeaway: Copy block table indexing + `cache_seqlens` per-sequence tracking; this is the decode API baseline
   - Avoid: Not a source for per-block m_i/l_i/o_i math

2. **vLLM PagedAttention (Kwon et al., 2023–2026)**
   - URL: https://github.com/vllm-project/vllm
   - Docs: https://docs.vllm.ai/en/latest/design/paged_attention/
   - Key pattern: `paged_attention_v1()` for seqlen≤8K, `paged_attention_v2()` for longer; uses partition size 512
   - Block table: `(num_seqs, max_blocks_per_seq)` logical→physical mapping
   - Takeaway: Copy partition-wise loop structure + per-block fetch boundary; block size fixed by kernel
   - Avoid: Full serving engine (scheduler, continuous batching); extract only attention forward logic

3. **FlashBlock (Chen et al., 2026) — PRIMARY SOURCE FOR BLOCK MATH**
   - arXiv: https://arxiv.org/abs/2602.05305v2 (Eqs 3–5 are core)
   - Per-block accumulators (log-space):
     ```
     Z_i,in  = Σ_{j∈J_in} exp(s_ij)                    # block norm (softmax denominator)
     U_i,in  = Σ_{j∈J_in} exp(s_ij) v_j               # block output (softmax numerator)
     Z_i,out = Σ_{j∈J_out} exp(s_ij)                   # cached external norm
     U_i,out = Σ_{j∈J_out} exp(s_ij) v_j              # cached external output
     a_i     = (U_i,out + U_i,in) / (Z_i,out + Z_i,in) # final per-query output (Eq. 5)
     ```
   - Single-token decode focus (matches Task 7 exactly)
   - Takeaway: Copy direct per-block m_i (max logit), l_i (sum exp), o_i (weighted sum) semantics; copy log-space composition for stability
   - Avoid: Diffusion-specific retraining; extract math only

4. **vLLM RFC #39076: Entropy-Gated Online KV Block Expiration (2026-04-06)**
   - URL: https://github.com/vllm-project/vllm/issues/39076
   - Phase A: LSE (log-sum-exp) extraction from FlashInfer for per-block attention mass
   - Shows production separation: `attention_fetch_compute` (block loop) vs `reduction_overhead` (final accumulation)
   - Takeaway: Copy LSE boundary as timing split signal; use as reduction intermediate
   - Avoid: Full entropy-gated eviction heuristics; focus only on LSE extraction point

5. **SwiftKV (2026 edge-accelerator)**
   - arXiv: https://arxiv.org/abs/2601.10953v1
   - Counter-example: per-token streaming without blockwise accumulation (Eqs 5–9)
   - Takeaway: Reference for what NOT to do; confirms Task 7's blockwise approach is orthogonal
   - Avoid: This design for Task 7; SwiftKV is for resource-constrained hardware

### Blockwise Decode Attention Math (Ready for Task 7 Implementation)

**Single-Query Blockwise Pattern** (adapted from FlashBlock + Dao et al. 2022):

Given: Q ∈ ℝ^{1×d}, K ∈ ℝ^{L×d}, V ∈ ℝ^{L×d}; K,V divided into B blocks (last block possibly partial)

```
# Phase 1: Per-Block Fetch + Compute (attention_fetch_compute_us bucket)
for block_idx in range(num_blocks):
    K_block, V_block = fetch_from_kv_cache(block_idx)  # (block_size, d_head)
    
    S_j = Q @ K_block^T / sqrt(d)                      # (1, block_size)
    m_j = max(S_j)                                      # Scalar
    P_j = exp(S_j - m_j)                                # (1, block_size)
    l_j = sum(P_j)                                      # Scalar
    o_j = P_j @ V_block                                 # (1, d_head)
    
    store(m_j, l_j, o_j)

# Phase 2: Final Reduction (reduction_overhead_us bucket)
m_global = max(m_1, m_2, ..., m_B)                     # B → 1
for i in range(num_blocks):
    α_i = exp(m_i - m_global)                           # Stability rescale
    l_global += l_i * α_i                               # Accumulate norms
    o_global += o_i * α_i                               # Accumulate outputs

output = o_global / l_global                            # Final output
```

**Timing Split Rationale**:
- `attention_fetch_compute_us` dominates: B blocks × (block_size × d_head FLOPs + KV memory BW)
- `reduction_overhead_us` negligible but non-zero: B scalars only, O(B) work

### What to Copy vs Avoid

**✅ COPY**:
- Block table indexing + cache_seqlens per-sequence (from FlashAttn + vLLM)
- Per-block m_i, l_i, o_i accumulators (from FlashBlock Eqs 3–5)
- Log-space composition (U_i,out + U_i,in) / (Z_i,out + Z_i,in) (from FlashBlock Eq. 5)
- Partition-wise loop structure (from vLLM PagedAttention v2)
- LSE as reduction intermediate and timing boundary (from vLLM RFC #39076)

**❌ AVOID**:
- Full serving engine (scheduler, continuous batching, preemption)
- Diffusion-specific logic (multi-step training, sparse patterns, video generation context)
- SwiftKV streaming approach (orthogonal single-pass design)
- Monolithic kernel fusion (Task 7 requires separate timing buckets, not fused)

### References for Task 7 Implementation

1. https://github.com/Dao-AILab/flash-attention (see flash_attn_with_kvcache in flash_attn/flash_attn_interface.py or equiv.)
2. https://github.com/vllm-project/vllm/blob/main/vllm/attention/ops/paged_attn.py (PagedAttention.forward_decode)
3. https://arxiv.org/abs/2602.05305v2 (FlashBlock paper; focus on Eqs 3–5 and Eq. 5 composition)
4. https://github.com/vllm-project/vllm/issues/39076 (RFC design doc for LSE extraction + timing separation)
5. https://github.com/Dao-AILab/flash-attention/pull/678 (Flash-Attention paged KV cache PR history)

---

**Core Insight**: Task 7's blockwise decode attention cleanly isolates **fetch/compute** (per-block loop over KV history) from **reduction** (final cross-block combination using m_i, l_i, o_i scalars). This separation directly maps to the plan's two timing buckets: `attention_fetch_compute_us` and `reduction_overhead_us`. FlashBlock (2026) provides the exact mathematical template; vLLM + official FlashAttention provide production block-table engineering patterns.

