# inference-profile

Standalone package for remote RAN inference profiling on OPT decoder layers via GPU acceleration.

This package profiles isolated OPT model layers (125M, 350M, 1.3B, 2.7B, and 6.7B) on a remote DGX to measure:
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
        └── ran_inference_profiling_report.md  # Markdown report
```

## Usage: Local CLI

The local CLI stages are typically run remotely via `deploy_and_run_remote.sh`.

### Stage 1: Bootstrap Environment

Prepare remote working directory and validate dependencies.

```bash
python -m inference_profile.cli bootstrap-env --output-root /tmp/runs/run-001
```

Note: The CLI supports a versioned experiment selector for the revised DGX Spark
path. To run the revised experiment path use `--experiment-type ran-dgxspark-v1`.
When selected, revised runs default to a versioned run-root like
`runs/revised-ran-dgxspark-<timestamp>` and emit explicitly prefixed artifacts
(`revised_*.png`, `revised_*.html`) to avoid colliding with legacy bundles.

**Acceptance**: The run root is initialized, `.venv/` is created with system site packages enabled, and `environment.json` is written.

### Stage 2: Validate Traces

Check LDPC and RAN control trace files for format and completeness.

```bash
python -m inference_profile.cli validate-traces \
  --ldpc-trace /mnt/data/traces/ldpc.csv \
  --ran-ctrl-trace /mnt/data/traces/ran_ctrl.csv \
  --output-root /tmp/runs/run-001
```

**Outputs**:
- `raw/trace_inspection.json`: structural inspection of both trace files
- `derived/normalized_ldpc_trace.csv`: canonical scheduler input derived from the LDPC trace
- `raw/validation_errors.csv`: emitted only when the primary LDPC trace fails validation

Canonical example trace paths used by the project:

```
/mnt/raid0sata2/netsys/weaver-ext/ran/traces/e2e_2026030418/e2e_20260304_182034_tractor_ran_ctrl/ldpc_trace.csv
/mnt/raid0sata2/netsys/weaver-ext/ran/traces/e2e_2026030418/e2e_20260304_182034_tractor_ran_ctrl/ran_ctrl_trace.csv
```

### Stage 3: Profile

Execute prefill, decode, and PCIe profiling across the sweep matrix:
`MODELS × CHUNK_SIZES × SEQUENCE_LENGTHS`.

```bash
python -m inference_profile.cli profile \
  --output-root /tmp/runs/run-001 \
  --models facebook/opt-125m facebook/opt-350m facebook/opt-1.3b \
  --chunk-sizes 64 128 \
  --sequence-lengths 1024 2048 \
  --gpu-id 0 \
  --cache-root /mnt/cache
```

**Output**:
- `raw/prefill_events.csv`: Per-sweep-point GEMM/attention timings
- `raw/decode_events.csv`: Per-block attention fetch/compute/reduction breakdown
- `raw/pcie_events.csv`: Transfer-only vs. overlapped transfer+compute
- `logs/profile-stage.log`: High-level stage progress
- `logs/profile-prefill.log`, `logs/profile-decode.log`, `logs/profile-pcie.log`: Family-specific progress
- `logs/<point-id>.stdout.log` and `logs/<point-id>.stderr.log`: Per-point worker logs

**Duration**: ~30 min (models) × 2 (chunk-size) × 3 (seq-length) × profiling time per point

### Stage 4: Simulate

Load profiling results and run the deterministic greedy scheduler against normalized LDPC idle gaps. The RAN control trace is validated and reported, but it is not used for scheduler capacity.

```bash
python -m inference_profile.cli simulate --run-root /tmp/runs/run-001
```

**Outputs**:
- `derived/simulation_inputs.csv`: Canonical simulation inputs assembled from successful profile summaries
- `derived/ran_inference_profiling_results.csv`: Deterministic latency/resource results keyed by `trace_sha256`
- `derived/schedule_timeline.csv`: Per-interval prefill/decode scheduling timeline

### Stage 5: Report

Generate plots and markdown report from profiling + simulation outputs.

```bash
python -m inference_profile.cli report --run-root /tmp/runs/run-001
```

**Outputs**:
- Legacy path:
  - `plots/01_ran_trace_interleaving.png`
  - `plots/01_ran_trace_interleaving_interactive.html` (interactive companion)
  - `plots/02_prefill_safety_boundary.png`
  - `plots/03_prefill_vram_composition.png`
  - `plots/04_ttft_vs_runway.png`
  - `plots/05_decode_tpot_degradation.png`
  - `plots/06_operation_level_microarchitecture_summary.png`
- Revised `ran-dgxspark-v1` path:
  - `telemetry/telemetry.jsonl`
  - `plots/revised_01_ran_trace_interleaving.png`
  - `plots/revised_01_ran_trace_interleaving_interactive.html`
  - `plots/revised_02_prefill_safety_boundary.png`
  - `plots/revised_03_prefill_vram_composition.png`
  - `plots/revised_04_ttft_vs_runway.png`
  - `plots/revised_05_decode_tpot_degradation.png`
  - `plots/revised_06_operation_level_microarchitecture_summary.png`
  - `plots/revised_07_hardware_utilization_profiling.png`
  - `plots/revised_08_decode_memory_consumption.png`
- `ran_inference_profiling_report.md`: Executive summary, metrics, and recommendations

**Telemetry tiers**:
- `baseline_nvml_pt`: direct PyTorch timings/memory plus coarse NVML sampling (`gpu_util`, memory used, clocks, power). This is the default revised path.
- `external_profiler`: optional external-profiler-backed tier for exact microscopic counters such as ACU / GBU / SMU when available.
- In baseline mode, microscopic ACU / GBU / SMU should be treated as unavailable or approximated, not as guaranteed exact measurements.

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
  --ldpc-trace /mnt/raid0sata2/netsys/weaver-ext/ran/traces/e2e_2026030418/e2e_20260304_182034_tractor_ran_ctrl/ldpc_trace.csv \
  --ran-ctrl-trace /mnt/raid0sata2/netsys/weaver-ext/ran/traces/e2e_2026030418/e2e_20260304_182034_tractor_ran_ctrl/ran_ctrl_trace.csv \
  --models facebook/opt-125m facebook/opt-350m \
  --chunk-sizes 64 \
  --sequence-lengths 1024 2048 \
  --gpu-id 0
```

### Resume from Specific Stage

If a run fails at stage N, resume without rerunning earlier stages:

```bash
python -m inference_profile.cli run-all \
  --run-root /tmp/runs/run-001 \
  --ldpc-trace /mnt/raid0sata2/netsys/weaver-ext/ran/traces/e2e_2026030418/e2e_20260304_182034_tractor_ran_ctrl/ldpc_trace.csv \
  --ran-ctrl-trace /mnt/raid0sata2/netsys/weaver-ext/ran/traces/e2e_2026030418/e2e_20260304_182034_tractor_ran_ctrl/ran_ctrl_trace.csv \
  --models facebook/opt-125m facebook/opt-350m \
  --chunk-sizes 64 \
  --sequence-lengths 1024 2048 \
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

- `.ssh_pass` file at `/mnt/data/dheeraj/dicertation/.ssh_pass` containing the SSH password for `netsys@192.168.1.20`
- `sshpass` installed locally
- LDPC and RAN control trace files accessible on the remote DGX at the paths passed to `--ldpc-trace` and `--ran-ctrl-trace`

### Smoke Command

Minimal test run (single model, small matrix):

```bash
bash scripts/deploy_and_run_remote.sh \
  --stage all \
  --run-id smoke-001 \
  --models facebook/opt-125m \
  --chunk-sizes 64 \
  --sequence-lengths 1024 \
  --ldpc-trace /mnt/raid0sata2/netsys/weaver-ext/ran/traces/e2e_2026030418/e2e_20260304_182034_tractor_ran_ctrl/ldpc_trace.csv \
  --ran-ctrl-trace /mnt/raid0sata2/netsys/weaver-ext/ran/traces/e2e_2026030418/e2e_20260304_182034_tractor_ran_ctrl/ran_ctrl_trace.csv
```

**Expected duration**: ~5 minutes (remote sync/bootstrap/profile/simulate/report/fetch)

### Full End-to-End Run

```bash
bash scripts/deploy_and_run_remote.sh \
  --stage all \
  --run-id exp-001-full \
  --models facebook/opt-125m facebook/opt-350m facebook/opt-1.3b facebook/opt-2.7b facebook/opt-6.7b \
  --chunk-sizes 64 128 256 512 1024 \
  --sequence-lengths 1024 2048 4096 8192 \
  --ldpc-trace /mnt/raid0sata2/netsys/weaver-ext/ran/traces/e2e_2026030418/e2e_20260304_182034_tractor_ran_ctrl/ldpc_trace.csv \
  --ran-ctrl-trace /mnt/raid0sata2/netsys/weaver-ext/ran/traces/e2e_2026030418/e2e_20260304_182034_tractor_ran_ctrl/ran_ctrl_trace.csv
```

**Expected duration**: ~90 minutes

### Dry-Run (Inspect Commands Without Execution)

```bash
bash scripts/deploy_and_run_remote.sh \
  --stage all \
  --run-id exp-001 \
  --models facebook/opt-125m \
  --chunk-sizes 64 \
  --sequence-lengths 1024 \
  --ldpc-trace /mnt/raid0sata2/netsys/weaver-ext/ran/traces/e2e_2026030418/e2e_20260304_182034_tractor_ran_ctrl/ldpc_trace.csv \
  --ran-ctrl-trace /mnt/raid0sata2/netsys/weaver-ext/ran/traces/e2e_2026030418/e2e_20260304_182034_tractor_ran_ctrl/ran_ctrl_trace.csv \
  --dry-run
```

**Output**: Redacted shell commands (sshpass paths replaced with `<redacted>`).

### Stageable Execution

Execute individual stages or retry failed ones:

```bash
# Stage 1: Sync source tree to the remote project root
bash scripts/deploy_and_run_remote.sh \
  --stage sync \
  --run-id exp-001 \
  --models facebook/opt-125m \
  --chunk-sizes 64 \
  --sequence-lengths 1024 \
  --ldpc-trace /mnt/raid0sata2/netsys/weaver-ext/ran/traces/e2e_2026030418/e2e_20260304_182034_tractor_ran_ctrl/ldpc_trace.csv \
  --ran-ctrl-trace /mnt/raid0sata2/netsys/weaver-ext/ran/traces/e2e_2026030418/e2e_20260304_182034_tractor_ran_ctrl/ran_ctrl_trace.csv

# Stage 2: Bootstrap
bash scripts/deploy_and_run_remote.sh \
  --stage bootstrap \
  --run-id exp-001 \
  --models facebook/opt-125m \
  --chunk-sizes 64 \
  --sequence-lengths 1024 \
  --ldpc-trace /mnt/raid0sata2/netsys/weaver-ext/ran/traces/e2e_2026030418/e2e_20260304_182034_tractor_ran_ctrl/ldpc_trace.csv \
  --ran-ctrl-trace /mnt/raid0sata2/netsys/weaver-ext/ran/traces/e2e_2026030418/e2e_20260304_182034_tractor_ran_ctrl/ran_ctrl_trace.csv

# Stage 3: Run the remaining pipeline remotely (validate-traces → verify-bundle)
bash scripts/deploy_and_run_remote.sh \
  --stage run \
  --run-id exp-001 \
  --models facebook/opt-125m \
  --chunk-sizes 64 \
  --sequence-lengths 1024 \
  --ldpc-trace /mnt/raid0sata2/netsys/weaver-ext/ran/traces/e2e_2026030418/e2e_20260304_182034_tractor_ran_ctrl/ldpc_trace.csv \
  --ran-ctrl-trace /mnt/raid0sata2/netsys/weaver-ext/ran/traces/e2e_2026030418/e2e_20260304_182034_tractor_ran_ctrl/ran_ctrl_trace.csv

# Stage 4: Fetch results locally
bash scripts/deploy_and_run_remote.sh \
  --stage fetch \
  --run-id exp-001
```

### Script Stages

1. **sync**: Upload source code (preserves `/home/netsys/dheeraj/inference-profile/runs/`)
2. **bootstrap**: Create the remote run root and bootstrap its `.venv`
3. **run**: Resume the remote pipeline from `validate-traces` onward for an already-bootstrapped `run_id`
4. **fetch**: Download results to local `inference-profile/runs/<run_id>/`

## Output Directory Layout

After completion, local results are in `inference-profile/runs/<run_id>/`:

```
runs/<run_id>/
├── run_manifest.json              # canonical manifest (see inference_profile.manifests.FINAL_STATUSES)
├── environment.json               # bootstrap + profile environment snapshot
├── logs/
│   ├── profile-stage.log
│   ├── profile-inspect-model.log
│   ├── profile-prefill.log
│   ├── profile-decode.log
│   ├── profile-pcie.log
│   ├── profile-reducer.log
│   └── <point-id>.{worker-spec.json,worker-result.json,stdout.log,stderr.log}
├── raw/
│   ├── trace_inspection.json
│   ├── validation_errors.csv      # only when LDPC validation fails
│   ├── prefill_events.csv
│   ├── prefill_events_status.csv
│   ├── decode_events.csv
│   ├── decode_events_status.csv
│   ├── pcie_events.csv
│   └── pcie_events_status.csv
├── derived/
│   ├── normalized_ldpc_trace.csv
│   ├── model_constants.csv
│   ├── prefill_summary.csv
│   ├── decode_summary.csv
│   ├── pcie_summary.csv
│   ├── simulation_inputs.csv
│   ├── ran_inference_profiling_results.csv     # includes `trace_sha256`, TTFT, TPOT, and VRAM runway metrics
│   └── schedule_timeline.csv
├── checksums/
│   └── sha256sums.txt             # textual sha256 manifest with run-root relative paths
├── plots/
│   ├── 01_ran_trace_interleaving.png
│   ├── 01_ran_trace_interleaving_interactive.html
│   ├── 02_prefill_safety_boundary.png
│   ├── 03_prefill_vram_composition.png
│   ├── 04_ttft_vs_runway.png
│   ├── 05_decode_tpot_degradation.png
│   ├── 06_operation_level_microarchitecture_summary.png
│   ├── revised_01_ran_trace_interleaving.png          # revised experiment only
│   ├── revised_01_ran_trace_interleaving_interactive.html
│   ├── revised_02_prefill_safety_boundary.png
│   ├── revised_03_prefill_vram_composition.png
│   ├── revised_04_ttft_vs_runway.png
│   ├── revised_05_decode_tpot_degradation.png
│   ├── revised_06_operation_level_microarchitecture_summary.png
│   └── revised_07_hardware_utilization_profiling.png
│   └── revised_08_decode_memory_consumption.png
├── telemetry/
│   └── telemetry.jsonl                                # revised experiment only
└── ran_inference_profiling_report.md                      # Executive summary and recommendations
```

## Status Taxonomy

The project uses a canonical manifest schema and final status taxonomy defined in `inference_profile.manifests.FINAL_STATUSES`.

Run-level `final_status` values (as implemented):

- `bootstrap_failed`
- `validation_failed`
- `profile_oom`
- `profile_failed`
- `simulate_failed`
- `report_failed`
- `ssh_failed`
- `fetch_failed`
- `success`

Per-stage progress is recorded under the `stages` object in the manifest. Each stage entry contains `latest_status`, `updated_at`, and a `history` list with timestamped status entries. Stages that have never run are absent from the manifest rather than being encoded as `pending` or `running`.

## Resume Rules

When using `--resume-from <stage>`:

1. **All prior stages** (if marked successful in manifest) are **skipped**
2. **Starting stage and all later stages** are **re-executed**
3. If a prior stage is missing or does not have `latest_status == success`, the resume request is **rejected** with an error
4. Manifests are **updated in-place** to avoid re-writing earlier stages

**Use case**: If `profile` stage times out, retry with:
```bash
python -m inference_profile.cli run-all \
  --run-root /tmp/runs/run-001 \
  --resume-from profile \
  ...
```

## Checksum Verification Flow

1. After `report` stage completes, a textual SHA256 manifest is written at `checksums/sha256sums.txt` containing lines of the form: `<hexsum>  <relative/path/to/file>`
2. During `verify-bundle` stage:
   - Completeness check: All required files present?
   - Checksum check: All required files and fetched `logs/` artifacts match stored SHA256s?
3. If verification succeeds: manifest final_status set to `success`
4. If verification fails after fetch: `verify-bundle` reports `fetch_failed`, the fetched bundle is preserved for debugging, and the fetched `run_manifest.json` is left unchanged

**To re-verify** an existing run bundle locally:
```bash
python -m inference_profile.cli verify-bundle --run-root runs/exp-001
```

## Metrics Glossary

### Timing Metrics (in milliseconds or microseconds per CSV column)

| Metric | Units | Meaning |
|--------|-------|---------|
| `us` | microseconds | Wall-clock time per CUDA event (kernel execution) |
| `ttft_ms` | milliseconds | Time-to-First-Token = latency from first prefill dispatch to prefill completion (ms) |
| `tpot_ms_vram` | milliseconds | Time-Per-Output-Token = decode latency (VRAM-bound estimate) |
| `tpot_ms_pcie_async` | milliseconds | Time-Per-Output-Token = decode latency (async PCIe overlap model) |

### Resource Metrics

| Metric | Meaning |
|--------|---------|
| `survival_vram_bytes` | Remaining VRAM headroom after weights and the larger of prefill/decode workspace + parked activations (bytes) |
| `decode_runway_bytes` | Remaining decode-time VRAM headroom after weights, the bulk KV cache accumulated by prefill, and decode workspace + parked activations (bytes) |
| `decode_runway_tokens` | Additional decode tokens that could still fit after prefill, given the remaining decode-time VRAM headroom and the KV-cache bytes per token |
| `kv_bytes_per_token_all_layers` | Incremental KV-cache growth per output token aggregated across all decoder layers (bytes) |

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

- The password is **stored in a local file** (`.ssh_pass`) and the wrapper requires mode `600`
- SSH host key verification remains enabled, so the remote host must already be trusted in `~/.ssh/known_hosts`
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
  --models facebook/opt-125m \
  --chunk-sizes 64 \
  --sequence-lengths 1024 2048
```

### Checksum Verification Fails After Fetch

Check that:
1. All files were fetched from remote (verify file counts in `runs/<run_id>/`)
2. Local `.ssh_pass` permission is correct (600)
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

Run the targeted suites you need locally; GPU smoke tests require CUDA hardware.

## References

- **Blockwise FlashAttention**: arXiv:2602.05305v2 — Per-block score aggregation (m_i, l_i, o_i)
- **vLLM PagedAttention**: Block-table-based KV cache management (cited for reference)
- **CUDA Event Timing**: NVIDIA CUDA C++ Programming Guide (synchronization + reset_peak_memory)

## License

Internal dissertation project. Not for public distribution.
