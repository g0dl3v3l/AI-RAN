## Initialized

## [2026-04-07T00:29Z] Task: T1
- `NVBenchSuite/analysis/profile_inference_acu_gbu.py` has a pre-existing Pyright diagnostic at line 204: `Counter[str]` receives a float weight. This did not block the Task 1 pytest pass but should be kept in mind when touching aggregation logic in later tasks.

## [2026-04-07T00:31Z] Task: T2
- The T2 verification command rewrites generated figure/data artifacts under `NVBenchSuite/analysis/figures/` and `NVBenchSuite/analysis/data/`; avoid confusing these verification side effects with the planned Task 9 regeneration deliverable.

## [2026-04-07T00:34Z] Task: T3/T4
- Importing `scripts/run_exp_a_all_waves.py` directly for ad-hoc verification requires the same `sys.modules[spec.name] = module` pattern used in the repo tests; otherwise Python 3.13 dataclass initialization fails during module exec.

## [2026-04-07T00:35Z] Task: T5/T6
- The repo’s planned QA selector `-k missing_duration` does not exactly match the current test name; use the full node id or the exact existing test name when verifying the missing-duration policy.

## [2026-04-07T00:39Z] Task: T7
- The pre-existing directory `NVBenchSuite/data/ncu_reports/expa_v2/merged_without_6_7b/` was insufficient for Task 7 because it only contained the six `opt-1.3b` CSVs and omitted all `opt-6.7b` pilot artifacts.
- The reused shard manifests still record pre-existing `timeout` statuses for `opt-6.7b_decode_bs1_seq128`, `opt-6.7b_decode_bs4_seq128`, and `opt-6.7b_decode_bs1_seq512`; however, their CSV/REP exports exist, carry duration metrics, and the merged analysis completed successfully.
- The required verification run again rewrote generated outputs under `NVBenchSuite/analysis/figures/` and `NVBenchSuite/analysis/data/`; treat those as expected analysis side effects rather than fresh recollection artifacts.

## [2026-04-07T01:57Z] Task: T8 cleanup
- The blocked recollection appended `ncu_exit_1` rows for the ten previously missing 6.7b configs and for the three pilot timeout decode configs, which made `data/expa_v2_manifests/*.csv` overstate canonical coverage relative to the actual shard artifact set.
- The external blocker chain on this host was: toolkit stub `libcuda.so` precedence for Nsight Compute, missing `torch` in base Python 3.13, missing Python 3.11 `_core` in `mls`, and then a `CXXABI_1.3.15` import failure even after rebuilding `_core` for `mls`.
- Historical non-canonical `NVBenchSuite/data/ncu_reports/opt-6.7b_*` files remain invalid `expa_v2` substitutes because they do not contain `gpu__time_duration.sum` or `gpu__time_duration.avg`.
