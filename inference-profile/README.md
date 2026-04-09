# inference-profile

Standalone package for remote RAN inference profiling on OPT decoder layers via GPU acceleration.

This package profiles isolated OPT model layers (125M, 350M, 1.3B) on a remote DGX to measure:
- **Prefill performance**: Time to process input tokens with full attention
- **Decode performance**: Token-by-token generation with blockwise flash-decoding
- **PCIe overlap**: Hidden H2D transfer cost during decode

Output files are deterministically scheduled against LDPC/RAN control traces to predict
inference latency and resource consumption under realistic load.

## Installation

```bash
cd inference-profile
pip install -e .
```

## Project Layout

```
inference-profile/
├── README.md                              # This file
├── pyproject.toml                         # Package metadata
├── inference_profile/
│   ├── __init__.py
│   ├── cli.py                             # Stageable CLI (bootstrap → verify-bundle)
│   ├── run_orchestrator.py                # Pipeline stage orchestration
│   ├── bootstrap.py                       # Environment setup
│   ├── opt_assets.py                      # OPT model loading and introspection
│   ├── prefill_profile.py                 # Prefill GPU profiler (GEMM, attention)
│   ├── decode_profile.py                  # Decode GPU profiler (blockwise FA)
│   ├── pcie_profile.py                    # PCIe H2D overlap measurement
│   ├── profile_orchestrator.py            # Coordinate profiling sweep matrix
│   ├── profile_reducer.py                 # Reduce raw CSV → canonical summaries
│   ├── simulator.py                       # Deterministic greedy scheduler
│   ├── plots.py                           # Generate profiling plots (PNG)
│   ├── report.py                          # Generate markdown run report
│   ├── verify_bundle.py                   # Checksum/completeness verification
│   ├── trace_contract.py                  # LDPC/RAN trace validation
│   ├── manifests.py                       # Run manifest JSON handling
│   ├── paths.py                           # Path resolution (cache, runs)
│   ├── constants.py                       # Fixed model/layer IDs
│   └── worker_profile_point.py            # GPU kernel launch utilities
├── scripts/
│   └── deploy_and_run_remote.sh           # SSH/scp orchestration (sshpass-based)
├── tests/
│   ├── unit/                              # Unit tests (schema, logic, parsing)
│   ├── integration/                       # Integration tests (orchestration, fetch)
│   ├── gpu/                               # GPU smoke tests (requires CUDA)
│   └── fixtures/                          # Test data
└── runs/                                  # Local cache of remote profiling results
    └── <run_id>/
        ├── run_manifest.json              # Status of all pipeline stages
        ├── logs/                          # Per-stage logs
        ├── raw/                           # Raw profiling CSV files
        ├── derived/                       # Reduced/canonical summaries
        ├── checksums/                     # SHA256 checksums of all outputs
        ├── plots/                         # PNG plots
        └── report.md                      # Markdown report
```

## Usage: Local CLI

The local CLI stages are typically run remotely via `deploy_and_run_remote.sh`.

### Stage 1: Bootstrap Environment

Prepare remote working directory and validate dependencies.

```bash
python -m inference_profile.cli bootstrap-env --output-root /tmp/runs/run-001
```

**Acceptance**: Directory created with `.dependencies-ok` marker file.

### Stage 2: Validate Traces

Check LDPC and RAN control trace files for format and completeness.

```bash
python -m inference_profile.cli validate-traces \
  --ldpc-trace /mnt/data/traces/ldpc.csv \
  --ran-ctrl-trace /mnt/data/traces/ran_ctrl.csv \
  --output-root /tmp/runs/run-001
```

**Output**: `logs/validate-traces.log` with line counts and schema checks.

### Stage 3: Profile

Execute prefill, decode, and PCIe profiling across the sweep matrix:
`MODELS × CHUNK_SIZES × SEQUENCE_LENGTHS`.

```bash
python -m inference_profile.cli profile \
  --run-root /tmp/runs/run-001 \
  --models opt-125m opt-350m opt-1.3b \
  --chunk-sizes 32 64 \
  --sequence-lengths 128 256 512 \
  --gpu-id 0 \
  --cache-root /mnt/cache
```

**Output**:
- `raw/prefill_events.csv`: Per-sweep-point GEMM/attention timings
- `raw/decode_events.csv`: Per-block attention fetch/compute/reduction breakdown
- `raw/pcie_events.csv`: Transfer-only vs. overlapped transfer+compute
- `logs/profile.log`: Sweep progress and per-model warmup/iteration counts

**Duration**: ~30 min (models) × 2 (chunk-size) × 3 (seq-length) × profiling time per point

### Stage 4: Simulate

Load profiling results and run deterministic greedy scheduler against LDPC/RAN traces.

```bash
python -m inference_profile.cli simulate --run-root /tmp/runs/run-001
```

**Output**: `derived/simulation_results.csv` with per-token latency and resource consumption.

### Stage 5: Report

Generate plots and markdown report from profiling + simulation outputs.

```bash
python -m inference_profile.cli report --run-root /tmp/runs/run-001
```

**Outputs**:
- `plots/prefill_time_vs_seq_length.png`
- `plots/decode_time_vs_kv_length.png`
- `plots/pcie_overlap_fraction.png`
- `plots/ttft_vs_model_size.png`
- `plots/tpot_vs_trace_load.png`
- `report.md`: Executive summary, metrics, and recommendations

### Stage 6: Verify Bundle

Validate completeness and checksums of run artifacts.

```bash
python -m inference_profile.cli verify-bundle --run-root /tmp/runs/run-001
```

**Acceptance**: All required files present and checksums match.

### Run All Stages (Single Command)

```bash
python -m inference_profile.cli run-all \
  --run-root /tmp/runs/run-001 \
  --ldpc-trace /mnt/data/traces/ldpc.csv \
  --ran-ctrl-trace /mnt/data/traces/ran_ctrl.csv \
  --models opt-125m opt-350m \
  --chunk-sizes 32 \
  --sequence-lengths 128 256 \
  --gpu-id 0
```

### Resume from Specific Stage

If a run fails at stage N, resume without rerunning earlier stages:

```bash
python -m inference_profile.cli run-all \
  --run-root /tmp/runs/run-001 \
  --ldpc-trace /mnt/data/traces/ldpc.csv \
  --ran-ctrl-trace /mnt/data/traces/ran_ctrl.csv \
  --models opt-125m opt-350m \
  --chunk-sizes 32 \
  --sequence-lengths 128 256 \
  --resume-from profile  # Skips bootstrap-env and validate-traces
```

**Valid resume stages** (immutable order):
1. `bootstrap-env`
2. `validate-traces`
3. `profile`
4. `simulate`
5. `report`
6. `verify-bundle`

## Usage: Remote Bash Script

The `deploy_and_run_remote.sh` script orchestrates SSH/scp operations to remote DGX.

### Prerequisites

- `.ssh_pass` file at `/mnt/data/dheeraj/dicertation/.ssh_pass` containing SSH password for `netsys@dheeraj`
- `sshpass` installed locally
- LDPC and RAN control trace files accessible locally

### Smoke Command

Minimal test run (single model, small matrix):

```bash
bash scripts/deploy_and_run_remote.sh \
  --stage all \
  --run-id smoke-001 \
  --models opt-125m \
  --chunk-sizes 32 \
  --sequence-lengths 128 \
  --ldpc-trace /mnt/data/traces/ldpc_embb_04_10.csv \
  --ran-ctrl-trace /mnt/data/traces/ran_ctrl_embb_04_10.csv
```

**Expected duration**: ~5 minutes (remote sync/bootstrap/profile/simulate/report/fetch)

### Full End-to-End Run

```bash
bash scripts/deploy_and_run_remote.sh \
  --stage all \
  --run-id exp-001-full \
  --models opt-125m opt-350m opt-1.3b \
  --chunk-sizes 32 64 128 \
  --sequence-lengths 128 256 512 1024 \
  --ldpc-trace /mnt/data/traces/ldpc_embb_04_10.csv \
  --ran-ctrl-trace /mnt/data/traces/ran_ctrl_embb_04_10.csv
```

**Expected duration**: ~90 minutes

### Dry-Run (Inspect Commands Without Execution)

```bash
bash scripts/deploy_and_run_remote.sh \
  --stage all \
  --run-id exp-001 \
  --models opt-125m \
  --chunk-sizes 32 \
  --sequence-lengths 128 \
  --ldpc-trace /mnt/data/traces/ldpc.csv \
  --ran-ctrl-trace /mnt/data/traces/ran_ctrl.csv \
  --dry-run
```

**Output**: Redacted shell commands (sshpass paths replaced with `<redacted>`).

### Stageable Execution

Execute individual stages or retry failed ones:

```bash
# Stage 1: Sync and bootstrap only
bash scripts/deploy_and_run_remote.sh \
  --stage sync \
  --run-id exp-001 \
  --models opt-125m \
  --chunk-sizes 32 \
  --sequence-lengths 128 \
  --ldpc-trace /mnt/data/traces/ldpc.csv \
  --ran-ctrl-trace /mnt/data/traces/ran_ctrl.csv

# Stage 2: Bootstrap
bash scripts/deploy_and_run_remote.sh \
  --stage bootstrap \
  --run-id exp-001 \
  --models opt-125m \
  --chunk-sizes 32 \
  --sequence-lengths 128 \
  --ldpc-trace /mnt/data/traces/ldpc.csv \
  --ran-ctrl-trace /mnt/data/traces/ran_ctrl.csv

# Stage 3: Run profiling (this may take 30+ minutes)
bash scripts/deploy_and_run_remote.sh \
  --stage run \
  --run-id exp-001 \
  --models opt-125m \
  --chunk-sizes 32 \
  --sequence-lengths 128 \
  --ldpc-trace /mnt/data/traces/ldpc.csv \
  --ran-ctrl-trace /mnt/data/traces/ran_ctrl.csv

# Stage 4: Fetch results locally
bash scripts/deploy_and_run_remote.sh \
  --stage fetch \
  --run-id exp-001
```

### Script Stages

1. **sync**: Upload source code (preserves `/home/netsys/dheeraj/inference-profile/runs/`)
2. **bootstrap**: Create remote directory structure
3. **run**: Execute profiling on remote GPU
4. **fetch**: Download results to local `inference-profile/runs/<run_id>/`

## Output Directory Layout

After completion, local results are in `inference-profile/runs/<run_id>/`:

```
runs/<run_id>/
├── run_manifest.json              # {"run_id": "...", "status": "success", "stage_status": {...}}
├── logs/
│   ├── bootstrap-env.log
│   ├── validate-traces.log
│   ├── profile.log
│   ├── simulate.log
│   ├── report.log
│   └── verify-bundle.log
├── raw/
│   ├── prefill_events.csv         # (model_id, chunk_size, seq_len, layer_idx, us)
│   ├── decode_events.csv          # (model_id, block_size, seq_len, layer_idx, attention_us, reduction_us)
│   └── pcie_events.csv            # (model_id, block_size, kv_bytes, transfer_only_us, overlapped_us)
├── derived/
│   ├── model_constants.csv        # (model_id, hidden_size, num_heads, num_layers)
│   ├── prefill_summary.csv        # (model_id, chunk_size, seq_len, max_us, mean_us)
│   ├── decode_summary.csv         # (model_id, block_size, seq_len, attention_us, reduction_us)
│   ├── pcie_summary.csv           # (model_id, block_size, kv_bytes, exposed_us, fully_hidden_us)
│   └── simulation_results.csv     # (model_id, seq_len, trace_name, ttft_ms, tpot_ms_vram, tpot_ms_pcie_async)
├── checksums/
│   └── checksums.json             # {filename: sha256_hex, ...}
├── plots/
│   ├── prefill_time_vs_seq_length.png
│   ├── decode_time_vs_kv_length.png
│   ├── pcie_overlap_fraction.png
│   ├── ttft_vs_model_size.png
│   └── tpot_vs_trace_load.png
└── report.md                      # Executive summary and recommendations
```

## Status Taxonomy

The `run_manifest.json` captures pipeline progress via stage status values:

| Status | Meaning |
|--------|---------|
| `pending` | Stage not yet started |
| `running` | Stage in progress |
| `success` | Stage completed successfully |
| `failed` | Stage failed; see `logs/<stage>.log` |

**Run-level status** in manifest:
| Status | Meaning |
|--------|---------|
| `running` | Pipeline in progress |
| `success` | All stages completed successfully |
| `failed` | One or more stages failed |
| `fetch_failed` | Remote run succeeded but local verification failed (checksum/completeness) |

## Resume Rules

When using `--resume-from <stage>`:

1. **All prior stages** (if marked successful in manifest) are **skipped**
2. **Starting stage and all later stages** are **re-executed**
3. If a prior stage shows `failed` status, the run is **rejected** with an error
4. Manifests are **updated in-place** to avoid re-writing earlier stages

**Use case**: If `profile` stage times out, retry with:
```bash
python -m inference_profile.cli run-all \
  --run-root /tmp/runs/run-001 \
  --resume-from profile \
  ...
```

## Checksum Verification Flow

1. After `report` stage completes, SHA256 checksums are computed for all artifact files
2. During `verify-bundle` stage:
   - Completeness check: All required files present?
   - Checksum check: All files match stored SHA256s?
3. If verification succeeds: manifest status = `success`
4. If verification fails: manifest status = `fetch_failed`, all files preserved for debugging

**To re-verify** an existing run bundle locally:
```bash
python -m inference_profile.cli verify-bundle --run-root runs/exp-001
```

## Metrics Glossary

### Timing Metrics (in milliseconds or microseconds per CSV column)

| Metric | Units | Meaning |
|--------|-------|---------|
| `us` | microseconds | Wall-clock time per CUDA event (kernel execution) |
| `ttft_ms` | milliseconds | Time-to-First-Token = prefill latency for entire prompt |
| `tpot_ms_vram` | milliseconds | Time-Per-Output-Token = decode latency (VRAM-bound estimate) |
| `tpot_ms_pcie_async` | milliseconds | Time-Per-Output-Token = decode latency (async PCIe overlap model) |

### Resource Metrics

| Metric | Meaning |
|--------|---------|
| `survival_vram_bytes` | Peak KV-cache footprint at decoder input (bytes) |
| `decode_runway_bytes` | Maximum KV bytes that fit in GPU memory before OOM |
| `kv_bytes_per_token` | Incremental KV-cache growth per output token |

### Profiling Breakdown (Decode)

| Metric | Meaning |
|--------|---------|
| `attention_fetch_compute_us` | Time to fetch KV block from main mem + compute attention |
| `reduction_overhead_us` | Time for per-block score reduction and LSE updates |

### Profiling Breakdown (PCIe)

| Metric | Meaning |
|--------|---------|
| `transfer_only_us` | H2D PCIe transfer time when no compute overlap |
| `overlapped_us` | H2D PCIe transfer time when hidden by concurrent compute |

## Security Note: sshpass

This package intentionally uses `sshpass` for remote SSH authentication **because the user request explicitly requires it**. 

- The password is **stored in a file** (`.ssh_pass`) with restricted read permissions (`600`)
- The password file path is **never logged** (script uses `sed` to redact it from debug output)
- `--dry-run` prints redacted commands to allow inspection without exposing secrets

**Do not commit the `.ssh_pass` file to version control.**

## Troubleshooting

### Remote Profiling Runs Out of Time

Reduce the sweep matrix:
```bash
bash scripts/deploy_and_run_remote.sh \
  --stage all \
  --run-id quick-test \
  --models opt-125m \
  --chunk-sizes 32 \
  --sequence-lengths 128 256
```

### Checksum Verification Fails After Fetch

Check that:
1. All files were fetched from remote (verify file counts in `runs/<run_id>/`)
2. Remote `.ssh_pass` permission is correct (600)
3. Re-attempt fetch: `bash scripts/deploy_and_run_remote.sh --stage fetch --run-id <run_id>`

### GPU Out of Memory During Profile Stage

Remote GPU may have insufficient VRAM. Check:
1. Remote VRAM availability: `nvidia-smi` on remote DGX
2. Reduce `sequence-lengths`: profile longest sequences first to identify breaking point
3. Profile one model at a time instead of sweep

### Manifest Shows `fetch_failed` But Logs Exist

Local verification did not pass. The remote run succeeded but:
- Checksum mismatch: Files were corrupted during `scp` transfer (retry with `--stage fetch`)
- Missing files: Manifest or logs/ did not copy (check scp errors in script output)
- Partial run: Remote run stopped before `verify-bundle` (see `logs/` for failure point)

All files are **preserved** for forensics. Check `logs/` for stage-specific errors.

## Testing

```bash
# Unit tests (fast)
pytest tests/unit -v

# Integration tests (no GPU required)
pytest tests/integration -v

# GPU smoke tests (requires CUDA)
pytest tests/gpu -v

# Full test suite
pytest tests/ -v
```

**All tests passing**: 117 unit + integration tests (GPU tests require CUDA hardware)

## References

- **Blockwise FlashAttention**: arXiv:2602.05305v2 — Per-block score aggregation (m_i, l_i, o_i)
- **vLLM PagedAttention**: Block-table-based KV cache management (cited for reference)
- **CUDA Event Timing**: NVIDIA CUDA C++ Programming Guide (synchronization + reset_peak_memory)

## License

Internal dissertation project. Not for public distribution.

