## Initialized

## [2026-04-07T00:29Z] Task: T1
- The actual codebase for this plan lives under `NVBenchSuite/`, not the workspace root.
- `NVBenchSuite/tests/python/test_profile_inference_acu_gbu.py` already exists and covers dotted OPT parsing, canonical `config_id` / `config_label`, duration weighting, and missing-duration rejection.
- Existing test style in `NVBenchSuite/tests/python/` uses dynamic imports via `importlib.util.spec_from_file_location(...)`, builtin fixtures like `tmp_path`, and small module-local helpers rather than shared pytest fixtures.
- `python -m pytest tests/python/test_profile_inference_acu_gbu.py -q` passes in `NVBenchSuite/`.

## [2026-04-07T00:31Z] Task: T2
- `NVBenchSuite/analysis/profile_inference_acu_gbu.py` already uses `fullmatch()` with dotted-model regexes for both phased and legacy filenames.
- `python analysis/profile_inference_acu_gbu.py --input-dir data/ncu_reports --model opt-1.3b --verify` succeeds and produces canonical `opt-1.3b` labels in `analysis/data/exp_a_acu_gbu_data.csv`.
- The real verification run emits many matplotlib font warnings for missing `YaHei Consolas Hybrid`, but the analysis still completes and writes figures/data.

## [2026-04-07T00:34Z] Task: T3/T4
- `NVBenchSuite/scripts/run_exp_a_all_waves.py` already defaults to `data/ncu_reports/expa_v2` and `data/expa_v2_manifests`.
- The runner already implements the fixed duration metric preference order: `gpu__time_duration.sum` when available, else `gpu__time_duration.avg`, with no third fallback.
- Existing `expa_v2` shard CSVs contain `gpu__time_duration.avg`, satisfying the explicit-duration-field contract.
- Existing runner tests already cover parser args, disjoint sharding, unique shard roots/manifests, and skip behavior; `python -m pytest tests/python/test_run_exp_a_all_waves.py -q` passes.
- Dry-run with `--gpu-ids 0,1,2,3` shows deterministic shard-local output roots and manifest paths.

## [2026-04-07T00:35Z] Task: T5/T6
- `NVBenchSuite/analysis/profile_inference_acu_gbu.py` already implements duration weighting using `gpu__time_duration.sum` first, then `gpu__time_duration.avg * Invocations`, and rejects missing-duration cases.
- The existing analysis tests already verify duration-weighted math and explicit rejection when duration weighting is requested without duration metrics.
- `NVBenchSuite/scripts/run_exp_a_all_waves.py:build_configs()` already matches the planned four-model matrix exactly.
- A direct VRAM-cap check with `estimate_vram_gb()` confirms the planned `opt-6.7b` configs stay within the current 20 GB guardrail used by the runner.

## [2026-04-07T00:39Z] Task: T7
- Existing pilot artifacts under `NVBenchSuite/data/ncu_reports/expa_v2/shard-0-gpu-0/` and `NVBenchSuite/data/ncu_reports/expa_v2/shard-1-gpu-1/` already covered both required models, `opt-1.3b` and `opt-6.7b`, so Task 7 did not require a fresh recollection.
- `NVBenchSuite/data/expa_v2_manifests/shard-0-gpu-0.csv` contains only `shard_index=0,gpu_id=0` rows and `shard-1-gpu-1.csv` contains only `shard_index=1,gpu_id=1` rows, which proved shard-local manifests with one visible GPU per shard.
- The deterministic merge into `NVBenchSuite/data/ncu_reports/expa_v2/merged/` produced 24 unique files (12 CSV + 12 `.ncu-rep`) with zero cross-shard filename collisions.
- All 12 merged CSVs expose `gpu__time_duration.avg`; representative evidence is `opt-1.3b_decode_bs1_seq128.csv:4` and `opt-6.7b_prefill_bs1_seq128.csv:4`.
- `python analysis/profile_inference_acu_gbu.py --input-dir data/ncu_reports/expa_v2/merged --output-dir analysis/figures` succeeded and regenerated `NVBenchSuite/analysis/data/exp_a_acu_gbu_data.csv` with 12 records spanning both models and both phases.

## [2026-04-07T01:57Z] Task: T8 cleanup
- Truthful canonical coverage for Task 8 has to be computed from actual `data/ncu_reports/expa_v2/shard-*` artifact pairs, not from manifest history alone; failed recollection attempts can append terminal rows even when no new `.ncu-rep`/CSV pair was produced.
- On this host, recollection failure was a runtime stack issue rather than a config-selection issue: `ncu` first hit a stub-driver path problem, base Python 3.13 lacked `torch`, and the only torch-capable env (`mls`) needed a Python 3.11 `_core` binding.
- Rebuilding `_core.cpython-311-x86_64-linux-gnu.so` for `mls` succeeded, but the repaired runner still could not execute because the host-loaded `/usr/lib/x86_64-linux-gnu/libstdc++.so.6` is missing `CXXABI_1.3.15`, so Task 8 recollection remained externally blocked.
