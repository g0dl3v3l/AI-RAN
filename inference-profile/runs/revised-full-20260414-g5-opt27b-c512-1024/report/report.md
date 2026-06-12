# RAN Inference Profiling Report

Run root: `/mnt/data/dheeraj/dicertation/inference-profile/runs/revised-full-20260414-g5-opt27b-c512-1024`

## Environment

| field | value |
| --- | --- |
| cache_root | n/a |
| captured_at | 2026-04-14T11:52:43Z |
| chunk_sizes | [512, 1024] |
| cuda_available | true |
| cuda_device_count | 8 |
| cwd | /mnt/data/dheeraj/dicertation/inference-profile |
| decode_modes | ["vram", "pcie_async"] |
| experiment_type | ran-dgxspark-v1 |
| gpu_id | 5 |
| l_out | 1024 |
| models | ["facebook/opt-2.7b"] |
| platform | Linux-6.8.0-106-generic-x86_64-with-glibc2.35 |
| python_executable | /home/dheeraj/miniconda3/envs/mls/bin/python |
| python_version | 3.11.14 |
| run_root | /mnt/data/dheeraj/dicertation/inference-profile/runs/revised-full-20260414-g5-opt27b-c512-1024 |
| scheduler | envelope_v1 |
| schema_version | ran_dgxspark_v1 |
| sequence_lengths | [1024, 2048, 4096, 8192] |
| sm_ai_cap | 32 |
| sm_ai_partition | 100 |
| sm_ai_partitions | [8, 16, 24, 32] |
| stage | profile |
| telemetry_tier | baseline_nvml_pt |
| timed_iterations | 5 |
| torch_available | true |
| torch_version | 2.10.0+cu128 |
| warmup_iterations | 3 |

## Model Constants

| model_id | sm_ai_partition | num_hidden_layers | hidden_size | num_attention_heads | ffn_dim | layer_index | layer_weight_bytes | total_weight_bytes_fp16 | vram_ceiling_bytes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| facebook/opt-2.7b | 100 | 32 | 2560 | 32 | 10240 | 15 | 157352960 | 5303193600 | 15170115993 |

## Trace Inspection

### Primary trace

| field | value |
| --- | --- |
| errors | [] |
| header | ["frame", "slot", "time_slot_sched_ns", "time_decode_start_est_ns", "time_decode_end_est_ns", "time_decode_start_actual_ns", "time_decode_end_actual_ns", "decode_dur_us", "deadline_met", "target_sm", "profile_idx", "sm_count", "num_pusch", "sum_prb", "sum_tbs_bytes", "max_mcs"] |
| median_positive_delta_ms | 5.6997 |
| monotonicity.checked_column | time_slot_sched_ns |
| monotonicity.is_non_decreasing | true |
| monotonicity.negative_delta_count | 0 |
| monotonicity.positive_delta_count | 28377 |
| monotonicity.zero_delta_count | 0 |
| normalization.last_row_duration_policy | median_positive_forward_delta_ms |
| normalization.output_columns | ["time_ms", "sm_utilization", "slot_duration_ms", "source_schema", "sm_count"] |
| normalization.output_relative_path | derived/normalized_ldpc_trace.csv |
| normalized_row_count | 28378 |
| path | /mnt/raid0sata2/netsys/weaver-ext/ran/traces/e2e_2026030418/e2e_20260304_182034_tractor_ran_ctrl/ldpc_trace.csv |
| row_count | 28378 |
| schema_detected | schema_b |
| time_unit_hint | ns |
| usable | true |
| usage_policy | primary_only |
| used_for_scheduler_capacity | true |

### Secondary trace

| field | value |
| --- | --- |
| errors | ["ran_ctrl_trace.csv line 182958 has 9 field(s); expected 12"] |
| header | ["frame", "slot", "sm_available", "prbs_available", "prbs_allocated", "w_avg_mcs_prev", "w_avg_mcs_curr", "slots_since_underutil", "ramp_up_count", "num_ue_sched", "max_ue_backlog", "sum_ue_backlog"] |
| monotonicity.checked_column | n/a |
| monotonicity.is_non_decreasing | n/a |
| monotonicity.negative_delta_count | n/a |
| path | /mnt/raid0sata2/netsys/weaver-ext/ran/traces/e2e_2026030418/e2e_20260304_182034_tractor_ran_ctrl/ran_ctrl_trace.csv |
| row_count | 182956 |
| time_unit_hints | [] |
| usable | false |
| usage_policy | structural_only |
| used_for_scheduler_capacity | false |

## Raw-Profile Summary Tables

### Prefill profile summary

Source raw rows: `raw/prefill_events.csv` = 280. Summary artifact: `derived/prefill_summary.csv`.

| model_id | chunk_tokens | sm_ai_partition | max_input_tokens | prefill_max_gemm_us | prefill_workspace_bytes | prefill_parked_activation_bytes | telemetry_tier | telemetry_provider | telemetry_status | nvml_available | gpu_util | gpu_mem_used_mb | sm_clock_mhz | mem_clock_mhz | power_w | pt_step_ms | pt_mem_alloc_mb | pt_mem_reserved_mb | pt_workspace_mb | acu_pct | gbu_pct | smu_pct | microscopic_telemetry_status | microscopic_error |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| facebook/opt-2.7b | 512 | 8 | 1024 | 365.344 | 10485760 | 10485760 | baseline_nvml_pt | nvidia-smi | ok | true | 1 | 5 | 1695 | 7601 | 61.51 | 0.3653 | 189.1689 | 189.1689 | 10 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 512 | 16 | 1024 | 364.832 | 10485760 | 10485760 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 61.68 | 0.3648 | 189.1689 | 189.1689 | 10 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 512 | 24 | 1024 | 365.6 | 10485760 | 10485760 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 61.75 | 0.3656 | 189.1689 | 189.1689 | 10 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 512 | 32 | 1024 | 365.504 | 10485760 | 10485760 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 61.68 | 0.3655 | 189.1689 | 189.1689 | 10 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 1024 | 8 | 1024 | 681.792 | 20971520 | 20971520 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 63.73 | 0.6818 | 219.1689 | 219.1689 | 20 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 1024 | 16 | 1024 | 699.392 | 20971520 | 20971520 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 8001 | 63.96 | 0.6994 | 219.1689 | 219.1689 | 20 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 1024 | 24 | 1024 | 681.984 | 20971520 | 20971520 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 63.98 | 0.682 | 219.1689 | 219.1689 | 20 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 1024 | 32 | 1024 | 684.768 | 20971520 | 20971520 | baseline_nvml_pt | nvidia-smi | ok | true | 2 | 5 | 1695 | 7601 | 64.35 | 0.6848 | 219.1689 | 219.1689 | 20 | n/a | n/a | n/a | unavailable | n/a |

### Decode profile summary

Source raw rows: `raw/decode_events.csv` = 2560. Summary artifact: `derived/decode_summary.csv`.

| model_id | sequence_length | block_size | sm_ai_partition | decode_mode | decode_max_gemv_us | attention_fetch_compute_us | reduction_overhead_us | decode_workspace_bytes | decode_parked_activation_bytes | telemetry_tier | telemetry_provider | telemetry_status | nvml_available | gpu_util | gpu_mem_used_mb | sm_clock_mhz | mem_clock_mhz | power_w | pt_step_ms | pt_mem_alloc_mb | pt_mem_reserved_mb | pt_workspace_mb | acu_pct | gbu_pct | smu_pct | microscopic_telemetry_status | microscopic_error |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| facebook/opt-2.7b | 1024 | 512 | 8 | pcie_async | 149.504 | 298.9696 | 193.2096 | 137728 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 61.87 | 0.3043 | 169.2046 | 169.2046 | 0.1313 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 1024 | 512 | 8 | vram | 148.48 | 299.7504 | 187.7504 | 137728 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 6 | 5 | 1695 | 7601 | 61.27 | 0.3297 | 169.2046 | 169.2046 | 0.1313 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 1024 | 512 | 16 | pcie_async | 156.672 | 295.5264 | 197.1584 | 137728 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 1 | 5 | 1695 | 7601 | 61.56 | 0.3113 | 169.2046 | 169.2046 | 0.1313 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 1024 | 512 | 16 | vram | 147.2 | 283.4688 | 192.0704 | 137728 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 6 | 5 | 1695 | 7601 | 61.34 | 0.2991 | 169.2046 | 169.2046 | 0.1313 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 1024 | 512 | 24 | pcie_async | 544.64 | 321.0752 | 228.2368 | 137728 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 61.86 | 0.5446 | 169.2046 | 169.2046 | 0.1313 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 1024 | 512 | 24 | vram | 147.456 | 299.5456 | 194.3296 | 137728 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 1 | 5 | 1695 | 7601 | 61.66 | 0.3083 | 169.2046 | 169.2046 | 0.1313 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 1024 | 512 | 32 | pcie_async | 152.576 | 292.7872 | 201.3312 | 137728 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 61.99 | 0.299 | 169.2046 | 169.2046 | 0.1313 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 1024 | 512 | 32 | vram | 157.696 | 299.4432 | 197.7152 | 137728 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 8001 | 62.35 | 0.3218 | 169.2046 | 169.2046 | 0.1313 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 1024 | 1024 | 8 | pcie_async | 167.072 | 189.6 | 187.1232 | 197120 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 3 | 5 | 1695 | 7601 | 61.87 | 0.214 | 169.2612 | 169.2612 | 0.188 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 1024 | 1024 | 8 | vram | 148.48 | 173.6192 | 169.7088 | 197120 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 62.29 | 0.178 | 169.2612 | 169.2612 | 0.188 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 1024 | 1024 | 16 | pcie_async | 146.432 | 173.9136 | 171.8656 | 197120 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 62.26 | 0.1792 | 169.2612 | 169.2612 | 0.188 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 1024 | 1024 | 16 | vram | 295.872 | 214.208 | 198.8864 | 197120 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 61.97 | 0.2972 | 169.2612 | 169.2612 | 0.188 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 1024 | 1024 | 24 | pcie_async | 161.504 | 182.8928 | 174.9184 | 197120 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 5 | 5 | 1695 | 7601 | 62.13 | 0.2017 | 169.2612 | 169.2612 | 0.188 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 1024 | 1024 | 24 | vram | 147.424 | 188.5696 | 181.5232 | 197120 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 62.36 | 0.2028 | 169.2612 | 169.2612 | 0.188 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 1024 | 1024 | 32 | pcie_async | 158.72 | 181.7152 | 177.8368 | 197120 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 62.31 | 0.1916 | 169.2612 | 169.2612 | 0.188 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 1024 | 1024 | 32 | vram | 150.528 | 192.9728 | 195.5648 | 197120 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 5 | 5 | 1695 | 8001 | 62.57 | 0.2232 | 169.2612 | 169.2612 | 0.188 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 2048 | 512 | 8 | pcie_async | 145.408 | 506.0096 | 256.4736 | 150016 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 62.47 | 0.5192 | 178.3413 | 178.3413 | 0.1431 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 2048 | 512 | 8 | vram | 148.672 | 524.2048 | 266.4256 | 150016 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 7 | 5 | 1695 | 7601 | 62.76 | 0.5436 | 178.3413 | 178.3413 | 0.1431 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 2048 | 512 | 16 | pcie_async | 153.6 | 501.7216 | 256.3072 | 150016 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 8 | 5 | 1695 | 7601 | 62.5 | 0.5212 | 178.3413 | 178.3413 | 0.1431 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 2048 | 512 | 16 | vram | 173.952 | 517.088 | 267.0784 | 150016 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 9 | 5 | 1695 | 7601 | 62.83 | 0.5416 | 178.3413 | 178.3413 | 0.1431 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 2048 | 512 | 24 | pcie_async | 149.504 | 516.3264 | 274.432 | 150016 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 9 | 5 | 1695 | 7601 | 62.18 | 0.5286 | 178.3413 | 178.3413 | 0.1431 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 2048 | 512 | 24 | vram | 146.432 | 513.3504 | 258.592 | 150016 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 62.35 | 0.5212 | 178.3413 | 178.3413 | 0.1431 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 2048 | 512 | 32 | pcie_async | 148.48 | 522.0224 | 261.9328 | 150016 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 2 | 5 | 1695 | 7601 | 63.15 | 0.5437 | 178.3413 | 178.3413 | 0.1431 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 2048 | 512 | 32 | vram | 194.56 | 618.0928 | 490.08 | 150016 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 62.51 | 1.026 | 178.3413 | 178.3413 | 0.1431 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 2048 | 1024 | 8 | pcie_async | 147.392 | 292.48 | 190.2528 | 268800 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 5 | 5 | 1695 | 7601 | 63.06 | 0.2981 | 178.4546 | 178.4546 | 0.2563 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 2048 | 1024 | 8 | vram | 150.528 | 301.664 | 190.8672 | 268800 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 8001 | 63.41 | 0.3103 | 178.4546 | 178.4546 | 0.2563 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 2048 | 1024 | 16 | pcie_async | 147.456 | 293.1264 | 194.4704 | 268800 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 1 | 5 | 1695 | 7601 | 63.42 | 0.3039 | 178.4546 | 178.4546 | 0.2563 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 2048 | 1024 | 16 | vram | 153.6 | 300.16 | 191.0464 | 268800 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 2 | 5 | 1695 | 7601 | 63.44 | 0.3029 | 178.4546 | 178.4546 | 0.2563 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 2048 | 1024 | 24 | pcie_async | 151.552 | 304.1408 | 199.424 | 268800 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 63.12 | 0.3143 | 178.4546 | 178.4546 | 0.2563 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 2048 | 1024 | 24 | vram | 149.28 | 292.3072 | 191.232 | 268800 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 63.08 | 0.3029 | 178.4546 | 178.4546 | 0.2563 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 2048 | 1024 | 32 | pcie_async | 151.648 | 296.6912 | 200.5632 | 268800 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 63.36 | 0.3028 | 178.4546 | 178.4546 | 0.2563 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 2048 | 1024 | 32 | vram | 164.864 | 303.5712 | 203.744 | 268800 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 1 | 5 | 1695 | 7601 | 63.15 | 0.3092 | 178.4546 | 178.4546 | 0.2563 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 4096 | 512 | 8 | pcie_async | 150.272 | 970.7712 | 414.9248 | 174592 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 9 | 5 | 1695 | 7601 | 63.49 | 0.9841 | 198.3647 | 198.3647 | 0.1665 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 4096 | 512 | 8 | vram | 147.456 | 951.5008 | 393.3568 | 174592 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 63.88 | 0.9615 | 198.3647 | 198.3647 | 0.1665 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 4096 | 512 | 16 | pcie_async | 147.456 | 939.4816 | 386.1952 | 174592 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 2 | 5 | 1695 | 7601 | 63.85 | 0.9492 | 198.3647 | 198.3647 | 0.1665 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 4096 | 512 | 16 | vram | 168.096 | 1002.7072 | 438.016 | 174592 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 7 | 5 | 1695 | 7601 | 63.17 | 1.0189 | 198.3647 | 198.3647 | 0.1665 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 4096 | 512 | 24 | pcie_async | 148.416 | 964.5952 | 414.4512 | 174592 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 63.42 | 0.9778 | 198.3647 | 198.3647 | 0.1665 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 4096 | 512 | 24 | vram | 149.44 | 1016.4096 | 418.7712 | 174592 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 63.75 | 1.1837 | 198.3647 | 198.3647 | 0.1665 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 4096 | 512 | 32 | pcie_async | 145.408 | 919.168 | 379.2896 | 174592 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 2 | 5 | 1695 | 7601 | 63.72 | 0.9247 | 198.3647 | 198.3647 | 0.1665 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 4096 | 512 | 32 | vram | 147.456 | 943.9168 | 392.4032 | 174592 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 7 | 5 | 1695 | 7601 | 63.42 | 0.9656 | 198.3647 | 198.3647 | 0.1665 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 4096 | 1024 | 8 | pcie_async | 148.48 | 509.952 | 264.32 | 281088 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 63.56 | 0.5192 | 198.4663 | 198.4663 | 0.2681 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 4096 | 1024 | 8 | vram | 146.336 | 501.3376 | 252.4736 | 281088 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 63.23 | 0.5089 | 198.4663 | 198.4663 | 0.2681 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 4096 | 1024 | 16 | pcie_async | 146.304 | 521.856 | 261.5296 | 281088 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 63.78 | 0.5325 | 198.4663 | 198.4663 | 0.2681 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 4096 | 1024 | 16 | vram | 151.68 | 515.9488 | 264.8064 | 281088 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 7 | 5 | 1695 | 7601 | 63.51 | 0.5256 | 198.4663 | 198.4663 | 0.2681 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 4096 | 1024 | 24 | pcie_async | 148.48 | 516.064 | 275.0592 | 281088 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 63.73 | 0.5315 | 198.4663 | 198.4663 | 0.2681 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 4096 | 1024 | 24 | vram | 148.256 | 519.328 | 267.68 | 281088 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 63.66 | 0.5346 | 198.4663 | 198.4663 | 0.2681 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 4096 | 1024 | 32 | pcie_async | 157.696 | 516.096 | 258.0288 | 281088 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 64.09 | 0.5284 | 198.4663 | 198.4663 | 0.2681 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 4096 | 1024 | 32 | vram | 146.432 | 516.7552 | 262.3552 | 281088 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 63.74 | 0.5212 | 198.4663 | 198.4663 | 0.2681 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 8192 | 512 | 8 | pcie_async | 155.68 | 1767.6224 | 643.52 | 223744 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 8001 | 64.57 | 1.8092 | 238.4116 | 238.4116 | 0.2134 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 8192 | 512 | 8 | vram | 151.552 | 1802.4128 | 675.4944 | 223744 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 64.1 | 1.8422 | 238.4116 | 238.4116 | 0.2134 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 8192 | 512 | 16 | pcie_async | 145.408 | 1831.7952 | 661.5872 | 223744 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 8001 | 64.18 | 1.8587 | 238.4116 | 238.4116 | 0.2134 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 8192 | 512 | 16 | vram | 149.504 | 1810.9312 | 690.3296 | 223744 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 63.62 | 1.8452 | 238.4116 | 238.4116 | 0.2134 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 8192 | 512 | 24 | pcie_async | 149.728 | 1801.0304 | 667.7376 | 223744 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 5 | 5 | 1695 | 8001 | 63.92 | 1.8258 | 238.4116 | 238.4116 | 0.2134 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 8192 | 512 | 24 | vram | 151.552 | 1819.8144 | 671.3664 | 223744 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 2 | 5 | 1695 | 7601 | 63.88 | 1.8371 | 238.4116 | 238.4116 | 0.2134 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 8192 | 512 | 32 | pcie_async | 154.624 | 1872.5184 | 742.5728 | 223744 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 63.81 | 1.9139 | 238.4116 | 238.4116 | 0.2134 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 8192 | 512 | 32 | vram | 248.992 | 1820.0448 | 667.8144 | 223744 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 64.07 | 1.8371 | 238.4116 | 238.4116 | 0.2134 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 8192 | 1024 | 8 | pcie_async | 152.576 | 998.6048 | 405.856 | 305664 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 64.25 | 1.1254 | 238.4897 | 238.4897 | 0.2915 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 8192 | 1024 | 8 | vram | 161.856 | 959.0912 | 414.272 | 305664 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 7 | 5 | 1695 | 7601 | 63.74 | 0.9779 | 238.4897 | 238.4897 | 0.2915 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 8192 | 1024 | 16 | pcie_async | 147.456 | 986.1376 | 394.1376 | 305664 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 5 | 5 | 1695 | 7601 | 63.4 | 1.1008 | 238.4897 | 238.4897 | 0.2915 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 8192 | 1024 | 16 | vram | 150.464 | 964.4288 | 393.5616 | 305664 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 8001 | 64.26 | 0.9851 | 238.4897 | 238.4897 | 0.2915 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 8192 | 1024 | 24 | pcie_async | 152.576 | 905.2736 | 380.4352 | 305664 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 2 | 5 | 1695 | 7601 | 63.79 | 0.9166 | 238.4897 | 238.4897 | 0.2915 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 8192 | 1024 | 24 | vram | 147.456 | 943.5456 | 387.4688 | 305664 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 63.65 | 0.9492 | 238.4897 | 238.4897 | 0.2915 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 8192 | 1024 | 32 | pcie_async | 153.568 | 951.2 | 387.5712 | 305664 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 7 | 5 | 1695 | 7601 | 63.75 | 0.9605 | 238.4897 | 238.4897 | 0.2915 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 8192 | 1024 | 32 | vram | 161.792 | 1075.072 | 434.7968 | 305664 | 5120 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 64.01 | 1.3857 | 238.4897 | 238.4897 | 0.2915 | n/a | n/a | n/a | unavailable | n/a |

### PCIe profile summary

Source raw rows: `raw/pcie_events.csv` = 10. Summary artifact: `derived/pcie_summary.csv`.

| model_id | block_size | kv_block_bytes | transfer_only_us | overlap_total_us | dummy_compute_us | exposed_transfer_us | effective_gbps | overlap_status | telemetry_tier | telemetry_provider | telemetry_status | nvml_available | gpu_util | gpu_mem_used_mb | sm_clock_mhz | mem_clock_mhz | power_w | pt_step_ms | pt_mem_alloc_mb | pt_mem_reserved_mb | pt_workspace_mb | acu_pct | gbu_pct | smu_pct | microscopic_telemetry_status | microscopic_error |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| facebook/opt-2.7b | 512 | 5242880 | 4847.6672 | 44027.6937 | 43414.5272 | 613.1666 | 1.0815 | measured | baseline_nvml_pt | nvidia-smi | partial | true | 9 | 5 | 1695 | 7601 | 63.88 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-2.7b | 1024 | 10485760 | 22270.4453 | 37710.3821 | 31851.1095 | 5859.2726 | 0.4708 | measured | baseline_nvml_pt | nvidia-smi | partial | true | 9 | 5 | 1695 | 7601 | 63.84 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | unavailable | n/a |

## SLA Tables

### Successful configurations

| model_id | chunk_tokens | sequence_length | ttft_ms | tpot_ms_vram | tpot_ms_pcie_async | decode_runway_tokens | status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| facebook/opt-2.7b | 512 | 1024 | 561.4141 | 46.1867 | 84.349 | 29599 | success |
| facebook/opt-2.7b | 512 | 2048 | 561.4141 | 72.8171 | 132.08 | 29598 | success |
| facebook/opt-2.7b | 512 | 4096 | 561.4141 | 71.0738 | 226.4396 | 29598 | success |
| facebook/opt-2.7b | 512 | 8192 | 561.4141 | 127.418 | 427.312 | 29598 | success |
| facebook/opt-2.7b | 1024 | 1024 | 525.9018 | 41.3346 | 229.4766 | 29086 | success |
| facebook/opt-2.7b | 1024 | 2048 | 525.9018 | 47.888 | 420.022 | 29086 | success |
| facebook/opt-2.7b | 1024 | 4096 | 525.9018 | 53.0465 | 805.0365 | 29086 | success |
| facebook/opt-2.7b | 1024 | 8192 | 525.9018 | 79.3799 | 1572.2995 | 29086 | success |

### Failed configurations

No rows available.

## Per-Model Scaling Analysis

| model_id | successful_configs | failed_configs | chunk_tokens_tested | sequence_lengths_tested | largest_successful_chunk_tokens | ttft_ms_min | ttft_ms_max | tpot_ms_vram_min | tpot_ms_vram_max | tpot_ms_pcie_async_min | tpot_ms_pcie_async_max | max_decode_runway_tokens |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| facebook/opt-2.7b | 8 | 0 | 512, 1024 | 1024, 2048, 4096, 8192 | 1024 | 525.9018 | 561.4141 | 41.3346 | 127.418 | 84.349 | 1572.2995 | 29599 |

## Plots

### Revised 01 Ran Trace Interleaving

![Revised 01 Ran Trace Interleaving](../plots/revised_01_ran_trace_interleaving.png)

[Interactive companion](../plots/revised_01_ran_trace_interleaving_interactive.html)

### Revised 02 Prefill Safety Boundary

![Revised 02 Prefill Safety Boundary](../plots/revised_02_prefill_safety_boundary.png)

### Revised 03 Prefill Vram Composition

![Revised 03 Prefill Vram Composition](../plots/revised_03_prefill_vram_composition.png)

### Revised 04 Ttft Vs Runway

![Revised 04 Ttft Vs Runway](../plots/revised_04_ttft_vs_runway.png)

### Revised 05 Decode Tpot Degradation

![Revised 05 Decode Tpot Degradation](../plots/revised_05_decode_tpot_degradation.png)

### Revised 06 Operation Level Microarchitecture Summary

![Revised 06 Operation Level Microarchitecture Summary](../plots/revised_06_operation_level_microarchitecture_summary.png)

### Revised 07 Hardware Utilization Profiling

![Revised 07 Hardware Utilization Profiling](../plots/revised_07_hardware_utilization_profiling.png)

### Revised 08 Decode Memory Consumption

![Revised 08 Decode Memory Consumption](../plots/revised_08_decode_memory_consumption.png)

### 09 Spatial VRAM Composition (Prefill) · Pie View

![09 Spatial VRAM Composition (Prefill) · Pie View](../plots/revised_09_prefill_vram_composition_pie.png)
