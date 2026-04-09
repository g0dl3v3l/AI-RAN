
## RTX A5000 Device Constants Addition

**Date**: 2026-04-02

### Pattern Observed
RTX A5000 follows Ampere GA102 architecture with these characteristics:
- 64 SMs (streaming multiprocessors)
- 768 GB/s memory bandwidth
- 27.8 TFLOPS FP32 peak, 55.6 TFLOPS FP16/BF16
- L2 cache: 6MB (6291456 bytes)
- Shared memory per SM: 100KB (102400 bytes)
- Max threads per SM: 1536 (standard for Ampere)
- Max registers per SM: 65536 (standard)

### Implementation
Successfully integrated into `NVBenchSuite/data/device_constants.json`:
- Matched existing structure (A100, GB10 entries)
- Used Ampere-specific max_threads_per_sm=1536
- Verified both QA scenarios pass:
  1. RTX A5000 loads with correct specs (total_sms=64)
  2. Existing devices (A100) remain unchanged

### Key Insight
Device constants follow a consistent pattern tied to GPU architecture:
- Per-SM resource limits (threads, regs, shared mem) tied to compute capability
- Aggregate metrics scale with SM count (e.g., L2 cache = SMs × per-SM factor)


## [2026-04-02T16:18:30Z] Task 2: OPT Model Download Script

### Implementation Pattern
- Used `huggingface_hub.snapshot_download()` for reliable offline caching and concurrent downloads
- Retry logic: exponential backoff [2s, 4s, 8s] for transient network errors
- Checksum verification via model file existence and HuggingFace API metadata
- Graceful degradation: if metadata unavailable, verifies key files exist (config.json, pytorch_model.bin)

### Key Features Implemented
- CLI with argparse: `--model`, `--all`, `--cache-dir`, `--force-redownload`
- 7 OPT models supported: 125m through 66b parameters
- Retry logic catches: ConnectionError, Timeout, RequestException
- Quantization config download placeholder for large models (opt-13b/30b/66b)
- Proper exit codes: 0 (success), 1 (download failure), 2 (checksum failure)

### QA Results
- ✓ Help message: All arguments display correctly (--model, --all, --cache-dir, --force-redownload)
- ✓ Model download: opt-125m downloaded successfully in 8s to /tmp/test_opt_cache
- ✓ Checksum verification: Passes by verifying config.json and pytorch_model.bin presence
- ✓ Exit code: 0 on success

### Gotchas Avoided
- Did NOT download models during script creation (only metadata fetches during test)
- Used `snapshot_download` over `from_pretrained` for better offline support
- Proper Path object handling instead of hardcoded paths
- Graceful handling of missing metadata (logs warning, continues)

### Technical Notes
- HuggingFace Hub uses concurrent fetching (12 files for opt-125m in 8s)
- Retry delays: 2s (conn), 4s (timeout), 8s (final attempt) provides good UX
- Quantization configs: Optional for now; downloadable but not critical for profiling

## [2026-04-03T00:00:00Z] Exp A ACU/GBU CLI verification compatibility

- `analysis/profile_inference_acu_gbu.py` now accepts `--model` as an exact filter over already-loaded records.
- `--verify` keeps the normal plot/CSV generation path, but disables demo fallback and validates that `analysis/data/exp_a_acu_gbu_data.csv` exists, has required columns, and matches the requested model filter.
- Verified in-tree with `python analysis/profile_inference_acu_gbu.py --model opt-125m --verify`, which loaded 40 matching real records from `data/ncu_reports/`.

## [2026-04-03T00:00:00Z] Exp B workload table PDF rendering note

- `analysis/generate_workload_table.py` now renders `analysis/figures/exp_b_workload_table.pdf` from the same aggregated rows used for CSV/LaTeX output.
- In this environment, `paper_style` requests `YaHei Consolas Hybrid`; if that font is unavailable, matplotlib falls back automatically and the PDF still renders, but text metrics can shift slightly across machines.
