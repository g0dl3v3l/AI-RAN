# RAN Inference Profiling Report

Run root: `/mnt/data/dheeraj/dicertation/inference-profile/runs/revised-full-20260414-opt67b-combined`

## Environment

| field | value |
| --- | --- |
| cache_root | n/a |
| captured_at | 2026-04-14T11:52:43Z |
| chunk_sizes | [64, 128, 256] |
| cuda_available | true |
| cuda_device_count | 8 |
| cwd | /mnt/data/dheeraj/dicertation/inference-profile |
| decode_modes | ["vram", "pcie_async"] |
| experiment_type | ran-dgxspark-v1 |
| gpu_id | 6 |
| l_out | 1024 |
| models | ["facebook/opt-6.7b"] |
| platform | Linux-6.8.0-106-generic-x86_64-with-glibc2.35 |
| python_executable | /home/dheeraj/miniconda3/envs/mls/bin/python |
| python_version | 3.11.14 |
| run_root | /mnt/data/dheeraj/dicertation/inference-profile/runs/revised-full-20260414-g6-opt67b-c64-256 |
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
| facebook/opt-6.7b | 100 | 32 | 4096 | 32 | 16384 | 15 | 402759680 | 13316947968 | 15170115993 |

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

Source raw rows: `raw/prefill_events.csv` = 700. Summary artifact: `derived/prefill_summary.csv`.

| model_id | chunk_tokens | sm_ai_partition | max_input_tokens | prefill_max_gemm_us | prefill_workspace_bytes | prefill_parked_activation_bytes | telemetry_tier | telemetry_provider | telemetry_status | nvml_available | gpu_util | gpu_mem_used_mb | sm_clock_mhz | mem_clock_mhz | power_w | pt_step_ms | pt_mem_alloc_mb | pt_mem_reserved_mb | pt_workspace_mb | acu_pct | gbu_pct | smu_pct | microscopic_telemetry_status | microscopic_error |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| facebook/opt-6.7b | 64 | 8 | 1024 | 307.2 | 2097152 | 2097152 | baseline_nvml_pt | nvidia-smi | ok | true | 7 | 5 | 1695 | 7601 | 67.08 | 0.3072 | 399.1953 | 399.1953 | 2 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 64 | 16 | 1024 | 270.336 | 2097152 | 2097152 | baseline_nvml_pt | nvidia-smi | ok | true | 6 | 5 | 1695 | 7601 | 68.14 | 0.2703 | 399.1953 | 399.1953 | 2 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 64 | 24 | 1024 | 270.24 | 2097152 | 2097152 | baseline_nvml_pt | nvidia-smi | ok | true | 5 | 5 | 1695 | 7601 | 68.4 | 0.2702 | 399.1953 | 399.1953 | 2 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 64 | 32 | 1024 | 271.36 | 2097152 | 2097152 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 68.59 | 0.2714 | 399.1953 | 399.1953 | 2 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 128 | 8 | 1024 | 296.96 | 4194304 | 4194304 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 8001 | 69.77 | 0.297 | 405.1953 | 405.1953 | 4 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 128 | 16 | 1024 | 297.984 | 4194304 | 4194304 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 8001 | 70.02 | 0.298 | 405.1953 | 405.1953 | 4 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 128 | 24 | 1024 | 296.96 | 4194304 | 4194304 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 69.85 | 0.297 | 405.1953 | 405.1953 | 4 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 128 | 32 | 1024 | 304.128 | 4194304 | 4194304 | baseline_nvml_pt | nvidia-smi | ok | true | 4 | 5 | 1695 | 8001 | 70.45 | 0.3041 | 405.1953 | 405.1953 | 4 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 256 | 8 | 1024 | 547.84 | 8388608 | 8388608 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 8001 | 71.7 | 0.5478 | 417.1953 | 417.1953 | 8 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 256 | 16 | 1024 | 546.912 | 8388608 | 8388608 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 71.46 | 0.5469 | 417.1953 | 417.1953 | 8 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 256 | 24 | 1024 | 545.792 | 8388608 | 8388608 | baseline_nvml_pt | nvidia-smi | ok | true | 23 | 5 | 1695 | 7601 | 71.62 | 0.5458 | 417.1953 | 417.1953 | 8 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 256 | 32 | 1024 | 546.784 | 8388608 | 8388608 | baseline_nvml_pt | nvidia-smi | ok | true | 1 | 5 | 1695 | 7601 | 71.59 | 0.5468 | 417.1953 | 417.1953 | 8 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 512 | 8 | 1024 | 822.272 | 16777216 | 16777216 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 68.54 | 0.8223 | 441.1953 | 441.1953 | 16 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 512 | 16 | 1024 | 829.44 | 16777216 | 16777216 | baseline_nvml_pt | nvidia-smi | ok | true | 1 | 5 | 1695 | 7601 | 68.51 | 0.8294 | 441.1953 | 441.1953 | 16 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 512 | 24 | 1024 | 828.288 | 16777216 | 16777216 | baseline_nvml_pt | nvidia-smi | ok | true | 6 | 5 | 1695 | 7601 | 69.06 | 0.8283 | 441.1953 | 441.1953 | 16 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 512 | 32 | 1024 | 826.112 | 16777216 | 16777216 | baseline_nvml_pt | nvidia-smi | ok | true | 6 | 5 | 1695 | 7601 | 69.22 | 0.8261 | 441.1953 | 441.1953 | 16 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 8 | 1024 | 1795.072 | 33554432 | 33554432 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 8001 | 74.99 | 1.7951 | 489.1953 | 489.1953 | 32 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 16 | 1024 | 1635.3281 | 33554432 | 33554432 | baseline_nvml_pt | nvidia-smi | ok | true | 39 | 5 | 1695 | 7601 | 74.23 | 1.6353 | 489.1953 | 489.1953 | 32 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 24 | 1024 | 1654.6561 | 33554432 | 33554432 | baseline_nvml_pt | nvidia-smi | ok | true | 48 | 5 | 1695 | 7601 | 74.58 | 1.6547 | 489.1953 | 489.1953 | 32 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 32 | 1024 | 1638.4 | 33554432 | 33554432 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 8001 | 74.62 | 1.6384 | 489.1953 | 489.1953 | 32 | n/a | n/a | n/a | unavailable | n/a |

### Decode profile summary

Source raw rows: `raw/decode_events.csv` = 6400. Summary artifact: `derived/decode_summary.csv`.

| model_id | sequence_length | block_size | sm_ai_partition | decode_mode | decode_max_gemv_us | attention_fetch_compute_us | reduction_overhead_us | decode_workspace_bytes | decode_parked_activation_bytes | telemetry_tier | telemetry_provider | telemetry_status | nvml_available | gpu_util | gpu_mem_used_mb | sm_clock_mhz | mem_clock_mhz | power_w | pt_step_ms | pt_mem_alloc_mb | pt_mem_reserved_mb | pt_workspace_mb | acu_pct | gbu_pct | smu_pct | microscopic_telemetry_status | microscopic_error |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| facebook/opt-6.7b | 1024 | 64 | 8 | pcie_async | 267.264 | 1719.8848 | 659.4944 | 155648 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 70.22 | 1.7428 | 408.4077 | 408.4077 | 0.1484 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 64 | 8 | vram | 276.48 | 1734.2144 | 663.552 | 155648 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 12 | 5 | 1695 | 7601 | 70.14 | 1.7449 | 408.4077 | 408.4077 | 0.1484 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 64 | 16 | pcie_async | 263.168 | 1721.4656 | 5456.7745 | 155648 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 70.35 | 12.6761 | 408.4077 | 408.4077 | 0.1484 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 64 | 16 | vram | 277.504 | 1713.4336 | 647.3216 | 155648 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 70.32 | 1.7746 | 408.4077 | 408.4077 | 0.1484 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 64 | 24 | pcie_async | 276.48 | 1733.9968 | 678.5088 | 155648 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 4 | 5 | 1695 | 7601 | 70.24 | 1.793 | 408.4077 | 408.4077 | 0.1484 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 64 | 24 | vram | 18284.544 | 1781.7408 | 705.024 | 155648 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 3 | 5 | 1695 | 7601 | 70.33 | 18.2845 | 408.4077 | 408.4077 | 0.1484 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 64 | 32 | pcie_async | 267.264 | 1721.7152 | 651.5008 | 155648 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 70.97 | 1.7377 | 408.4077 | 408.4077 | 0.1484 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 64 | 32 | vram | 296.832 | 1810.0864 | 658.2592 | 155648 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 1 | 5 | 1695 | 7601 | 70.71 | 2.1043 | 408.4077 | 408.4077 | 0.1484 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 128 | 8 | pcie_async | 266.24 | 925.8816 | 401.2288 | 97792 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 71.31 | 0.939 | 408.3374 | 408.3374 | 0.0933 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 128 | 8 | vram | 270.336 | 924.0064 | 402.6368 | 97792 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 17 | 5 | 1695 | 8001 | 71.14 | 0.9431 | 408.3374 | 408.3374 | 0.0933 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 128 | 16 | pcie_async | 278.528 | 977.6832 | 476.1152 | 97792 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 71.02 | 0.9902 | 408.3374 | 408.3374 | 0.0933 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 128 | 16 | vram | 267.264 | 939.2704 | 414.7136 | 97792 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 15 | 5 | 1695 | 7601 | 71.18 | 0.9557 | 408.3374 | 408.3374 | 0.0933 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 128 | 24 | pcie_async | 268.288 | 2803.4048 | 4060.1792 | 97792 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 7 | 5 | 1695 | 8001 | 71.49 | 12.5532 | 408.3374 | 408.3374 | 0.0933 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 128 | 24 | vram | 270.336 | 934.944 | 403.872 | 97792 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 71.3 | 0.943 | 408.3374 | 408.3374 | 0.0933 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 128 | 32 | pcie_async | 266.208 | 916.224 | 401.1584 | 97792 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 8001 | 71.97 | 0.9247 | 408.3374 | 408.3374 | 0.0933 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 128 | 32 | vram | 270.24 | 926.2976 | 404.2944 | 97792 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 8001 | 71.6 | 0.9351 | 408.3374 | 408.3374 | 0.0933 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 256 | 8 | pcie_async | 273.568 | 547.4496 | 318.6432 | 93696 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 5 | 5 | 1695 | 7601 | 71.91 | 0.6206 | 408.3315 | 408.3315 | 0.0894 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 256 | 8 | vram | 447.424 | 516.3776 | 266.8864 | 93696 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 71.54 | 0.5225 | 408.3315 | 408.3315 | 0.0894 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 256 | 16 | pcie_async | 269.312 | 520.1856 | 263.9936 | 93696 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 17 | 5 | 1695 | 7601 | 71.57 | 0.5325 | 408.3315 | 408.3315 | 0.0894 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 256 | 16 | vram | 266.24 | 542.7712 | 312.704 | 93696 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 12 | 5 | 1695 | 7601 | 71.78 | 0.6175 | 408.3315 | 408.3315 | 0.0894 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 256 | 24 | pcie_async | 283.648 | 514.2144 | 261.5744 | 93696 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 12 | 5 | 1695 | 8001 | 72.1 | 0.5273 | 408.3315 | 408.3315 | 0.0894 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 256 | 24 | vram | 272.384 | 578.0928 | 306.3168 | 93696 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 71.88 | 0.7296 | 408.3315 | 408.3315 | 0.0894 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 256 | 32 | pcie_async | 268.288 | 535.1104 | 276.0704 | 93696 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 1 | 5 | 1695 | 7601 | 71.58 | 0.5417 | 408.3315 | 408.3315 | 0.0894 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 256 | 32 | vram | 277.504 | 523.0464 | 270.6816 | 93696 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 7 | 5 | 1695 | 7601 | 71.65 | 0.5315 | 408.3315 | 408.3315 | 0.0894 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 512 | 8 | pcie_async | 277.344 | 312.6784 | 214.0288 | 140800 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 17 | 5 | 1695 | 7601 | 66.26 | 0.3284 | 408.3765 | 408.3765 | 0.1343 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 512 | 8 | vram | 272.384 | 310.2656 | 210.3296 | 140800 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 66.68 | 0.3183 | 408.3765 | 408.3765 | 0.1343 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 512 | 16 | pcie_async | 267.264 | 306.7776 | 201.9904 | 140800 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 2 | 5 | 1695 | 7601 | 66.72 | 0.3223 | 408.3765 | 408.3765 | 0.1343 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 512 | 16 | vram | 650.24 | 400.1728 | 289.344 | 140800 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 66.86 | 0.7055 | 408.3765 | 408.3765 | 0.1343 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 512 | 24 | pcie_async | 271.36 | 303.3984 | 205.2608 | 140800 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 66.97 | 0.3145 | 408.3765 | 408.3765 | 0.1343 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 512 | 24 | vram | 293.696 | 361.6896 | 262.0608 | 140800 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 66.58 | 0.4741 | 408.3765 | 408.3765 | 0.1343 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 512 | 32 | pcie_async | 342.816 | 313.312 | 202.5664 | 140800 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 67.07 | 0.3613 | 408.3765 | 408.3765 | 0.1343 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 512 | 32 | vram | 538.624 | 374.0544 | 252.9472 | 140800 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 67.05 | 0.5386 | 408.3765 | 408.3765 | 0.1343 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 1024 | 8 | pcie_async | 265.216 | 179.7376 | 176.5504 | 197120 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 1 | 5 | 1695 | 7601 | 66.79 | 0.2652 | 408.4302 | 408.4302 | 0.188 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 1024 | 8 | vram | 276.48 | 195.84 | 189.0688 | 197120 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 8001 | 66.86 | 0.2765 | 408.4302 | 408.4302 | 0.188 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 1024 | 16 | pcie_async | 268.288 | 194.8352 | 182.2848 | 197120 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 67.28 | 0.2683 | 408.4302 | 408.4302 | 0.188 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 1024 | 16 | vram | 266.24 | 179.1424 | 176.4672 | 197120 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 66.98 | 0.2662 | 408.4302 | 408.4302 | 0.188 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 1024 | 24 | pcie_async | 267.424 | 185.76 | 173.632 | 197120 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 67.47 | 0.2674 | 408.4302 | 408.4302 | 0.188 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 1024 | 24 | vram | 266.24 | 179.36 | 176.2944 | 197120 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 8001 | 67.75 | 0.2662 | 408.4302 | 408.4302 | 0.188 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 1024 | 32 | pcie_async | 270.176 | 176.3584 | 167.328 | 197120 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 67.21 | 0.2702 | 408.4302 | 408.4302 | 0.188 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 1024 | 32 | vram | 266.976 | 176.2624 | 172.8704 | 197120 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 67.42 | 0.267 | 408.4302 | 408.4302 | 0.188 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 64 | 8 | pcie_async | 268.288 | 3666.7392 | 1220.7808 | 303104 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 71.98 | 4.7841 | 424.5483 | 424.5483 | 0.2891 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 64 | 8 | vram | 269.152 | 3669.3824 | 1200.352 | 303104 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 71.76 | 4.8579 | 424.5483 | 424.5483 | 0.2891 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 64 | 16 | pcie_async | 267.264 | 3617.8176 | 1273.3376 | 303104 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 1 | 5 | 1695 | 7601 | 71.82 | 4.78 | 424.5483 | 424.5483 | 0.2891 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 64 | 16 | vram | 266.24 | 3618.6625 | 1170.0544 | 303104 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 8 | 5 | 1695 | 7601 | 71.86 | 4.8159 | 424.5483 | 424.5483 | 0.2891 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 64 | 24 | pcie_async | 275.456 | 3581.5296 | 1194.5984 | 303104 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 71.85 | 4.7718 | 424.5483 | 424.5483 | 0.2891 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 64 | 24 | vram | 267.264 | 3585.7024 | 1169.5808 | 303104 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 20 | 5 | 1695 | 7601 | 72.11 | 4.7104 | 424.5483 | 424.5483 | 0.2891 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 64 | 32 | pcie_async | 284.672 | 3970.2976 | 1413.952 | 303104 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 27 | 5 | 1695 | 7601 | 72.05 | 5.0936 | 424.5483 | 424.5483 | 0.2891 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 64 | 32 | vram | 266.24 | 3710.5088 | 1268.7296 | 303104 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 71.95 | 5.1302 | 424.5483 | 424.5483 | 0.2891 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 128 | 8 | pcie_async | 268.064 | 1756.1728 | 656.6016 | 171520 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 72.27 | 1.8094 | 424.4077 | 424.4077 | 0.1636 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 128 | 8 | vram | 267.168 | 1731.1552 | 672.2048 | 171520 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 71.96 | 1.7513 | 424.4077 | 424.4077 | 0.1636 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 128 | 16 | pcie_async | 266.112 | 1753.8688 | 664.9216 | 171520 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 1 | 5 | 1695 | 7601 | 72.69 | 1.7898 | 424.4077 | 424.4077 | 0.1636 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 128 | 16 | vram | 274.304 | 2012.352 | 807.5264 | 171520 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 72.27 | 2.3921 | 424.4077 | 424.4077 | 0.1636 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 128 | 24 | pcie_async | 265.216 | 1666.6688 | 635.4944 | 171520 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 72.83 | 1.6937 | 424.4077 | 424.4077 | 0.1636 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 128 | 24 | vram | 266.08 | 1756.5696 | 672.352 | 171520 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 9 | 5 | 1695 | 7601 | 72.69 | 1.7705 | 424.4077 | 424.4077 | 0.1636 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 128 | 32 | pcie_async | 276.48 | 1764.9664 | 694.848 | 171520 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 73.04 | 1.9067 | 424.4077 | 424.4077 | 0.1636 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 128 | 32 | vram | 273.408 | 1740.352 | 669.7152 | 171520 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 72.99 | 1.8094 | 424.4077 | 424.4077 | 0.1636 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 256 | 8 | pcie_async | 280.576 | 969.3184 | 405.2992 | 130560 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 72.97 | 1.0127 | 424.3667 | 424.3667 | 0.1245 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 256 | 8 | vram | 271.36 | 956.864 | 395.0656 | 130560 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 72.76 | 0.9658 | 424.3667 | 424.3667 | 0.1245 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 256 | 16 | pcie_async | 264.192 | 925.4656 | 382.4704 | 130560 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 73.25 | 0.9452 | 424.3667 | 424.3667 | 0.1245 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 256 | 16 | vram | 264.192 | 957.8944 | 395.9232 | 130560 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 8 | 5 | 1695 | 8001 | 73.48 | 0.9668 | 424.3667 | 424.3667 | 0.1245 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 256 | 24 | pcie_async | 272.384 | 964.384 | 411.8848 | 130560 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 73.05 | 0.9737 | 424.3667 | 424.3667 | 0.1245 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 256 | 24 | vram | 264.192 | 992.0768 | 396.1856 | 130560 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 3 | 5 | 1695 | 7601 | 73.19 | 1.1469 | 424.3667 | 424.3667 | 0.1245 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 256 | 32 | pcie_async | 268.256 | 951.9168 | 389.9008 | 130560 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 1 | 5 | 1695 | 8001 | 73.74 | 0.972 | 424.3667 | 424.3667 | 0.1245 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 256 | 32 | vram | 275.456 | 1040.0256 | 446.9248 | 130560 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 1 | 5 | 1695 | 7601 | 73.22 | 1.0724 | 424.3667 | 424.3667 | 0.1245 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 512 | 8 | pcie_async | 274.656 | 514.7904 | 259.296 | 159232 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 67.65 | 0.5281 | 424.394 | 424.394 | 0.1519 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 512 | 8 | vram | 266.048 | 522.2016 | 264.3072 | 159232 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 67.07 | 0.5294 | 424.394 | 424.394 | 0.1519 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 512 | 16 | pcie_async | 263.168 | 515.3024 | 260.5376 | 159232 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 67.77 | 0.5254 | 424.394 | 424.394 | 0.1519 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 512 | 16 | vram | 264.192 | 535.0016 | 289.1648 | 159232 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 3 | 5 | 1695 | 7601 | 67.31 | 0.5829 | 424.394 | 424.394 | 0.1519 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 512 | 24 | pcie_async | 269.312 | 533.6896 | 284.0448 | 159232 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 67.97 | 0.5417 | 424.394 | 424.394 | 0.1519 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 512 | 24 | vram | 271.616 | 535.1424 | 287.9936 | 159232 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 68.25 | 0.5468 | 424.394 | 424.394 | 0.1519 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 512 | 32 | pcie_async | 273.408 | 519.936 | 260.2432 | 159232 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 8 | 5 | 1695 | 7601 | 67.71 | 0.5425 | 424.394 | 424.394 | 0.1519 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 512 | 32 | vram | 268.288 | 526.7264 | 277.6576 | 159232 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 8 | 5 | 1695 | 7601 | 67.8 | 0.5397 | 424.394 | 424.394 | 0.1519 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 1024 | 8 | pcie_async | 262.944 | 296.7232 | 192.9152 | 271872 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 8 | 5 | 1695 | 8001 | 68.27 | 0.306 | 424.5015 | 424.5015 | 0.2593 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 1024 | 8 | vram | 270.336 | 300.6208 | 196.128 | 271872 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 67.89 | 0.3123 | 424.5015 | 424.5015 | 0.2593 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 1024 | 16 | pcie_async | 267.264 | 310.3104 | 204.192 | 271872 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 3 | 5 | 1695 | 7601 | 67.74 | 0.3338 | 424.5015 | 424.5015 | 0.2593 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 1024 | 16 | vram | 307.2 | 313.3184 | 212.7552 | 271872 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 67.68 | 0.3224 | 424.5015 | 424.5015 | 0.2593 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 1024 | 24 | pcie_async | 275.264 | 303.0656 | 201.9712 | 271872 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 67.64 | 0.3164 | 424.5015 | 424.5015 | 0.2593 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 1024 | 24 | vram | 268.288 | 297.1264 | 201.92 | 271872 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 68.09 | 0.3031 | 424.5015 | 424.5015 | 0.2593 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 1024 | 32 | pcie_async | 264.128 | 292.6528 | 188.4928 | 271872 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 67.97 | 0.3052 | 424.5015 | 424.5015 | 0.2593 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 2048 | 1024 | 32 | vram | 266.24 | 295.3536 | 196.7872 | 271872 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 67.78 | 0.3052 | 424.5015 | 424.5015 | 0.2593 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 64 | 8 | pcie_async | 265.024 | 6541.6832 | 2186.24 | 598016 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 73.67 | 6.6673 | 456.8296 | 456.8296 | 0.5703 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 64 | 8 | vram | 264.192 | 6561.7984 | 2174.816 | 598016 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 73.61 | 6.7062 | 456.8296 | 456.8296 | 0.5703 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 64 | 16 | pcie_async | 264.192 | 6382.9888 | 2187.2448 | 598016 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 73.54 | 6.4369 | 456.8296 | 456.8296 | 0.5703 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 64 | 16 | vram | 274.432 | 6409.8304 | 2167.328 | 598016 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 73.44 | 6.5413 | 456.8296 | 456.8296 | 0.5703 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 64 | 24 | pcie_async | 269.248 | 6618.7008 | 2176.8192 | 598016 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 73.6 | 6.8792 | 456.8296 | 456.8296 | 0.5703 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 64 | 24 | vram | 268.288 | 6557.1457 | 2202.3424 | 598016 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 73.57 | 6.7585 | 456.8296 | 456.8296 | 0.5703 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 64 | 32 | pcie_async | 267.072 | 6462.4704 | 2262.9952 | 598016 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 1 | 5 | 1695 | 7601 | 73.31 | 6.571 | 456.8296 | 456.8296 | 0.5703 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 64 | 32 | vram | 273.408 | 6630.2592 | 2258.3104 | 598016 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 73.67 | 6.743 | 456.8296 | 456.8296 | 0.5703 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 128 | 8 | pcie_async | 266.08 | 3690.8928 | 1171.8592 | 318976 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 10 | 5 | 1695 | 7601 | 73.08 | 4.8353 | 456.5483 | 456.5483 | 0.3042 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 128 | 8 | vram | 268.288 | 3695.4176 | 1229.8112 | 318976 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 73.3 | 4.8568 | 456.5483 | 456.5483 | 0.3042 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 128 | 16 | pcie_async | 274.432 | 3697.1136 | 1209.2608 | 318976 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 73.17 | 4.8673 | 456.5483 | 456.5483 | 0.3042 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 128 | 16 | vram | 270.08 | 3707.4688 | 1175.5456 | 318976 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 8 | 5 | 1695 | 7601 | 73.06 | 4.8189 | 456.5483 | 456.5483 | 0.3042 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 128 | 24 | pcie_async | 264.32 | 3582.3488 | 1159.5776 | 318976 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 14 | 5 | 1695 | 7601 | 73.54 | 4.5281 | 456.5483 | 456.5483 | 0.3042 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 128 | 24 | vram | 282.624 | 3701.7536 | 1227.6288 | 318976 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 6 | 5 | 1695 | 7601 | 73.29 | 4.7606 | 456.5483 | 456.5483 | 0.3042 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 128 | 32 | pcie_async | 266.176 | 3636.5504 | 1168.6144 | 318976 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 73.21 | 4.8238 | 456.5483 | 456.5483 | 0.3042 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 128 | 32 | vram | 272.256 | 3850.8032 | 1382.1184 | 318976 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 73.57 | 5.0063 | 456.5483 | 456.5483 | 0.3042 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 256 | 8 | pcie_async | 264.96 | 1815.3344 | 645.5424 | 204288 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 13 | 5 | 1695 | 8001 | 73.63 | 1.9436 | 456.437 | 456.437 | 0.1948 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 256 | 8 | vram | 267.04 | 1839.0272 | 683.4112 | 204288 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 8 | 5 | 1695 | 7601 | 73.15 | 1.8668 | 456.437 | 456.437 | 0.1948 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 256 | 16 | pcie_async | 273.408 | 1905.0112 | 746.6432 | 204288 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 73.28 | 2.0675 | 456.437 | 456.437 | 0.1948 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 256 | 16 | vram | 269.312 | 1832.9408 | 661.6704 | 204288 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 73.26 | 1.8432 | 456.437 | 456.437 | 0.1948 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 256 | 24 | pcie_async | 265.216 | 1773.2736 | 629.7792 | 204288 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 73.44 | 1.7994 | 456.437 | 456.437 | 0.1948 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 256 | 24 | vram | 264.192 | 1762.0864 | 628.9792 | 204288 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 8001 | 73.44 | 1.7992 | 456.437 | 456.437 | 0.1948 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 256 | 32 | pcie_async | 269.312 | 1930.0096 | 748.8256 | 204288 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 73.7 | 1.9671 | 456.437 | 456.437 | 0.1948 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 256 | 32 | vram | 265.216 | 1707.5968 | 619.2576 | 204288 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 8001 | 73.78 | 1.7233 | 456.437 | 456.437 | 0.1948 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 512 | 8 | pcie_async | 264.192 | 955.3792 | 402.5088 | 196096 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 1 | 5 | 1695 | 7601 | 67.79 | 0.9748 | 456.4292 | 456.4292 | 0.187 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 512 | 8 | vram | 266.24 | 967.0784 | 401.9968 | 196096 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 67.69 | 0.978 | 456.4292 | 456.4292 | 0.187 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 512 | 16 | pcie_async | 268.128 | 967.5392 | 402.0352 | 196096 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 8001 | 68.11 | 0.978 | 456.4292 | 456.4292 | 0.187 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 512 | 16 | vram | 271.36 | 912.704 | 373.7152 | 196096 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 68.07 | 0.9235 | 456.4292 | 456.4292 | 0.187 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 512 | 24 | pcie_async | 264.192 | 925.952 | 397.8624 | 196096 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 67.65 | 0.9321 | 456.4292 | 456.4292 | 0.187 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 512 | 24 | vram | 264.192 | 941.216 | 381.8304 | 196096 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 67.64 | 0.9585 | 456.4292 | 456.4292 | 0.187 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 512 | 32 | pcie_async | 264.192 | 980.9536 | 431.4496 | 196096 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 67.91 | 0.989 | 456.4292 | 456.4292 | 0.187 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 512 | 32 | vram | 263.168 | 952.4032 | 394.8096 | 196096 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 8 | 5 | 1695 | 7601 | 67.6 | 0.9963 | 456.4292 | 456.4292 | 0.187 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 1024 | 8 | pcie_async | 264.192 | 489.0816 | 246.528 | 290304 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 12 | 5 | 1695 | 7601 | 67.62 | 0.5079 | 456.519 | 456.519 | 0.2769 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 1024 | 8 | vram | 264.192 | 508.9216 | 262.8736 | 290304 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 67.75 | 0.5325 | 456.519 | 456.519 | 0.2769 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 1024 | 16 | pcie_async | 264.192 | 502.3872 | 256.608 | 290304 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 67.97 | 0.512 | 456.519 | 456.519 | 0.2769 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 1024 | 16 | vram | 296.768 | 522.8544 | 267.6608 | 290304 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 15 | 5 | 1695 | 7601 | 67.88 | 0.5284 | 456.519 | 456.519 | 0.2769 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 1024 | 24 | pcie_async | 269.312 | 511.9808 | 273.6128 | 290304 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 1 | 5 | 1695 | 7601 | 68.1 | 0.5263 | 456.519 | 456.519 | 0.2769 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 1024 | 24 | vram | 273.408 | 526.2976 | 269.2864 | 290304 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 7 | 5 | 1695 | 7601 | 68.1 | 0.5395 | 456.519 | 456.519 | 0.2769 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 1024 | 32 | pcie_async | 265.12 | 513.0752 | 257.8432 | 290304 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 68.32 | 0.5202 | 456.519 | 456.519 | 0.2769 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 4096 | 1024 | 32 | vram | 300.032 | 521.2288 | 268.1216 | 290304 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 68.11 | 0.5315 | 456.519 | 456.519 | 0.2769 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 64 | 8 | pcie_async | 264.192 | 13178.4702 | 4454.8353 | 1187840 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 11 | 5 | 1695 | 7601 | 73.96 | 13.2915 | 521.3921 | 521.3921 | 1.1328 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 64 | 8 | vram | 264.192 | 12995.4687 | 4203.5328 | 1187840 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 4 | 5 | 1695 | 7601 | 74.07 | 13.3123 | 521.3921 | 521.3921 | 1.1328 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 64 | 16 | pcie_async | 264.96 | 12811.5072 | 4219.1039 | 1187840 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 20 | 5 | 1695 | 7601 | 74.01 | 12.972 | 521.3921 | 521.3921 | 1.1328 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 64 | 16 | vram | 262.048 | 12481.5554 | 4141.5103 | 1187840 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 34 | 5 | 1695 | 8001 | 74.53 | 12.7086 | 521.3921 | 521.3921 | 1.1328 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 64 | 24 | pcie_async | 270.336 | 23490.3173 | 5447.2768 | 1187840 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 3 | 5 | 1695 | 7601 | 73.97 | 42.5933 | 521.3921 | 521.3921 | 1.1328 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 64 | 24 | vram | 267.264 | 12614.2593 | 4297.0881 | 1187840 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 8001 | 74.17 | 12.9731 | 521.3921 | 521.3921 | 1.1328 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 64 | 32 | pcie_async | 268.288 | 12886.6304 | 4247.3151 | 1187840 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 9 | 5 | 1695 | 7601 | 74.05 | 13.3929 | 521.3921 | 521.3921 | 1.1328 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 64 | 32 | vram | 272.48 | 12644.1408 | 4160.2688 | 1187840 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 2 | 5 | 1695 | 7601 | 73.89 | 12.7723 | 521.3921 | 521.3921 | 1.1328 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 128 | 8 | pcie_async | 267.264 | 6453.76 | 2148.128 | 613888 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 21 | 5 | 1695 | 7601 | 73.83 | 6.5995 | 520.8296 | 520.8296 | 0.5854 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 128 | 8 | vram | 264.192 | 6581.1392 | 2197.1264 | 613888 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 73.94 | 6.6956 | 520.8296 | 520.8296 | 0.5854 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 128 | 16 | pcie_async | 269.312 | 6645.8304 | 2196.0639 | 613888 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 73.62 | 6.9491 | 520.8296 | 520.8296 | 0.5854 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 128 | 16 | vram | 278.464 | 6763.776 | 2375.3024 | 613888 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 21 | 5 | 1695 | 7601 | 73.83 | 6.8578 | 520.8296 | 520.8296 | 0.5854 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 128 | 24 | pcie_async | 269.312 | 6276.0576 | 2111.904 | 613888 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 73.95 | 6.4195 | 520.8296 | 520.8296 | 0.5854 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 128 | 24 | vram | 274.432 | 6761.4145 | 2185.8432 | 613888 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 73.76 | 6.91 | 520.8296 | 520.8296 | 0.5854 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 128 | 32 | pcie_async | 264.192 | 6419.8591 | 2127.488 | 613888 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 2 | 5 | 1695 | 7601 | 73.88 | 6.572 | 520.8296 | 520.8296 | 0.5854 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 128 | 32 | vram | 266.24 | 6599.0528 | 2284.512 | 613888 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 73.85 | 6.8239 | 520.8296 | 520.8296 | 0.5854 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 256 | 8 | pcie_async | 356.352 | 3848.9664 | 1242.9632 | 351744 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 73.61 | 5.0586 | 520.5776 | 520.5776 | 0.3354 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 256 | 8 | vram | 273.408 | 3772.1792 | 1155.4944 | 351744 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 73.57 | 4.7596 | 520.5776 | 520.5776 | 0.3354 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 256 | 16 | pcie_async | 272.384 | 3745.6129 | 1159.2064 | 351744 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 2 | 5 | 1695 | 7601 | 73.53 | 4.8476 | 520.5776 | 520.5776 | 0.3354 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 256 | 16 | vram | 265.12 | 3723.6928 | 1176.6912 | 351744 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 7 | 5 | 1695 | 8001 | 73.79 | 4.6572 | 520.5776 | 520.5776 | 0.3354 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 256 | 24 | pcie_async | 264.192 | 3804.5311 | 1227.1744 | 351744 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 26 | 5 | 1695 | 7601 | 73.73 | 4.7575 | 520.5776 | 520.5776 | 0.3354 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 256 | 24 | vram | 265.504 | 3830.5472 | 1199.072 | 351744 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 2 | 5 | 1695 | 7601 | 73.31 | 5.1425 | 520.5776 | 520.5776 | 0.3354 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 256 | 32 | pcie_async | 269.312 | 3894.4448 | 1204.7104 | 351744 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 2 | 5 | 1695 | 7601 | 73.45 | 5.3821 | 520.5776 | 520.5776 | 0.3354 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 256 | 32 | vram | 266.08 | 3773.4272 | 1158.3104 | 351744 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 73.6 | 4.9386 | 520.5776 | 520.5776 | 0.3354 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 512 | 8 | pcie_async | 263.904 | 1841.3696 | 698.6112 | 269824 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 19 | 5 | 1695 | 7601 | 68.67 | 1.8514 | 520.4995 | 520.4995 | 0.2573 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 512 | 8 | vram | 265.216 | 1802.7648 | 650.4704 | 269824 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 13 | 5 | 1695 | 7601 | 68.25 | 1.8153 | 520.4995 | 520.4995 | 0.2573 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 512 | 16 | pcie_async | 266.368 | 1749.4144 | 638.784 | 269824 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 8001 | 69.12 | 1.8115 | 520.4995 | 520.4995 | 0.2573 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 512 | 16 | vram | 267.264 | 1765.6256 | 643.2896 | 269824 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 3 | 5 | 1695 | 7601 | 68.9 | 1.7859 | 520.4995 | 520.4995 | 0.2573 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 512 | 24 | pcie_async | 262.976 | 1786.1312 | 638.1056 | 269824 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 1 | 5 | 1695 | 7601 | 69.31 | 1.7981 | 520.4995 | 520.4995 | 0.2573 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 512 | 24 | vram | 264.192 | 1786.0224 | 669.088 | 269824 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 68.76 | 1.8043 | 520.4995 | 520.4995 | 0.2573 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 512 | 32 | pcie_async | 266.24 | 1875.1104 | 705.5744 | 269824 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 69.02 | 1.8952 | 520.4995 | 520.4995 | 0.2573 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 512 | 32 | vram | 264.192 | 1754.5216 | 660.896 | 269824 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 68.94 | 1.7674 | 520.4995 | 520.4995 | 0.2573 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 1024 | 8 | pcie_async | 267.2 | 937.3824 | 390.1376 | 327168 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 69.24 | 0.9667 | 520.5542 | 520.5542 | 0.312 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 1024 | 8 | vram | 267.2 | 970.3168 | 413.6768 | 327168 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 17 | 5 | 1695 | 7601 | 69.04 | 0.98 | 520.5542 | 520.5542 | 0.312 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 1024 | 16 | pcie_async | 311.296 | 980 | 419.4624 | 327168 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 21 | 5 | 1695 | 7601 | 68.85 | 1.0424 | 520.5542 | 520.5542 | 0.312 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 1024 | 16 | vram | 265.216 | 950.1312 | 405.6576 | 327168 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 8 | 5 | 1695 | 8001 | 69.26 | 0.9659 | 520.5542 | 520.5542 | 0.312 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 1024 | 24 | pcie_async | 276.48 | 964.384 | 399.7888 | 327168 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 68.65 | 0.9697 | 520.5542 | 520.5542 | 0.312 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 1024 | 24 | vram | 268.288 | 1001.0496 | 445.824 | 327168 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 68.74 | 1.158 | 520.5542 | 520.5542 | 0.312 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 1024 | 32 | pcie_async | 268.288 | 958.6048 | 392.3968 | 327168 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 68.94 | 0.9708 | 520.5542 | 520.5542 | 0.312 | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 8192 | 1024 | 32 | vram | 265.216 | 956.1216 | 393.632 | 327168 | 8192 | baseline_nvml_pt | nvidia-smi | ok | true | 0 | 5 | 1695 | 7601 | 68.81 | 0.9626 | 520.5542 | 520.5542 | 0.312 | n/a | n/a | n/a | unavailable | n/a |

### PCIe profile summary

Source raw rows: `raw/pcie_events.csv` = 25. Summary artifact: `derived/pcie_summary.csv`.

| model_id | block_size | kv_block_bytes | transfer_only_us | overlap_total_us | dummy_compute_us | exposed_transfer_us | effective_gbps | overlap_status | telemetry_tier | telemetry_provider | telemetry_status | nvml_available | gpu_util | gpu_mem_used_mb | sm_clock_mhz | mem_clock_mhz | power_w | pt_step_ms | pt_mem_alloc_mb | pt_mem_reserved_mb | pt_workspace_mb | acu_pct | gbu_pct | smu_pct | microscopic_telemetry_status | microscopic_error |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| facebook/opt-6.7b | 64 | 1048576 | 287.6032 | 29557.5553 | 29260.1402 | 297.4151 | 3.6459 | measured | baseline_nvml_pt | nvidia-smi | partial | true | 0 | 5 | 1695 | 7601 | 60.16 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 128 | 2097152 | 397.4976 | 32227.4887 | 31973.1915 | 254.2972 | 5.2759 | measured | baseline_nvml_pt | nvidia-smi | partial | true | 2 | 5 | 1695 | 7601 | 59.49 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 256 | 4194304 | 3028.2816 | 43143.936 | 42332.3656 | 811.5704 | 1.385 | measured | baseline_nvml_pt | nvidia-smi | partial | true | 0 | 5 | 1695 | 7601 | 71.4 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 512 | 8388608 | 16010.7773 | 44331.2131 | 43820.6785 | 510.5346 | 0.5239 | measured | baseline_nvml_pt | nvidia-smi | partial | true | 0 | 5 | 1695 | 7601 | 68.42 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | unavailable | n/a |
| facebook/opt-6.7b | 1024 | 16777216 | 1194.4704 | 35975.5387 | 35383.1157 | 592.423 | 14.0457 | measured | baseline_nvml_pt | nvidia-smi | partial | true | 0 | 5 | 1695 | 7601 | 68.53 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | unavailable | n/a |

## SLA Tables

### Successful configurations

| model_id | chunk_tokens | sequence_length | ttft_ms | tpot_ms_vram | tpot_ms_pcie_async | decode_runway_tokens | status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| facebook/opt-6.7b | 64 | 1024 | 3334.4718 | 135.9788 | 279.5341 | 3470 | success |
| facebook/opt-6.7b | 64 | 2048 | 3334.4718 | 210.4537 | 531.506 | 3470 | success |
| facebook/opt-6.7b | 64 | 4096 | 3334.4718 | 336.9286 | 939.5987 | 3469 | success |
| facebook/opt-6.7b | 64 | 8192 | 3334.4718 | 590.0573 | 1818.0096 | 3468 | success |
| facebook/opt-6.7b | 128 | 1024 | 1868.5624 | 94.465 | 158.3683 | 3406 | success |
| facebook/opt-6.7b | 128 | 2048 | 1868.5624 | 129.6165 | 261.9984 | 3406 | success |
| facebook/opt-6.7b | 128 | 4096 | 1868.5624 | 219.7266 | 465.2714 | 3406 | success |
| facebook/opt-6.7b | 128 | 8192 | 1868.5624 | 335.3922 | 845.0406 | 3405 | success |
| facebook/opt-6.7b | 256 | 1024 | 1679.7204 | 78.6801 | 181.3501 | 3278 | success |
| facebook/opt-6.7b | 256 | 2048 | 1679.7204 | 100.47 | 302.2053 | 3278 | success |
| facebook/opt-6.7b | 256 | 4096 | 1679.7204 | 125.3808 | 552.9547 | 3278 | success |
| facebook/opt-6.7b | 256 | 8192 | 1679.7204 | 208.903 | 1045.929 | 3277 | success |
| facebook/opt-6.7b | 512 | 1024 | 1268.908 | 123.4799 | 115.003 | 3022 | success |
| facebook/opt-6.7b | 512 | 2048 | 1268.908 | 77.2516 | 142.8085 | 3022 | success |
| facebook/opt-6.7b | 512 | 4096 | 1268.908 | 93.6391 | 226.6186 | 3022 | success |
| facebook/opt-6.7b | 512 | 8192 | 1268.908 | 128.0182 | 395.0937 | 3022 | success |
| facebook/opt-6.7b | 1024 | 1024 | 1258.2912 | 62.4316 | 81.8293 | 2510 | success |
| facebook/opt-6.7b | 1024 | 2048 | 1258.2912 | 66.8666 | 104.0243 | 2510 | success |
| facebook/opt-6.7b | 1024 | 4096 | 1258.2912 | 82.8654 | 151.4026 | 2510 | success |
| facebook/opt-6.7b | 1024 | 8192 | 1258.2912 | 94.1136 | 246.4036 | 2509 | success |

### Failed configurations

No rows available.

## Per-Model Scaling Analysis

| model_id | successful_configs | failed_configs | chunk_tokens_tested | sequence_lengths_tested | largest_successful_chunk_tokens | ttft_ms_min | ttft_ms_max | tpot_ms_vram_min | tpot_ms_vram_max | tpot_ms_pcie_async_min | tpot_ms_pcie_async_max | max_decode_runway_tokens |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| facebook/opt-6.7b | 20 | 0 | 64, 128, 256, 512, 1024 | 1024, 2048, 4096, 8192 | 1024 | 1258.2912 | 3334.4718 | 62.4316 | 590.0573 | 81.8293 | 1818.0096 | 3470 |

## Plots

### Revised 01 Ran Trace Interleaving

![Revised 01 Ran Trace Interleaving](plots/revised_01_ran_trace_interleaving.png)

[Interactive companion](plots/revised_01_ran_trace_interleaving_interactive.html)

### Revised 02 Prefill Safety Boundary

![Revised 02 Prefill Safety Boundary](plots/revised_02_prefill_safety_boundary.png)

### Revised 03 Prefill Vram Composition

![Revised 03 Prefill Vram Composition](plots/revised_03_prefill_vram_composition.png)

### Revised 04 Ttft Vs Runway

![Revised 04 Ttft Vs Runway](plots/revised_04_ttft_vs_runway.png)

### Revised 05 Decode Tpot Degradation

![Revised 05 Decode Tpot Degradation](plots/revised_05_decode_tpot_degradation.png)

### Revised 06 Operation Level Microarchitecture Summary

![Revised 06 Operation Level Microarchitecture Summary](plots/revised_06_operation_level_microarchitecture_summary.png)

### Revised 07 Hardware Utilization Profiling

![Revised 07 Hardware Utilization Profiling](plots/revised_07_hardware_utilization_profiling.png)

### Revised 08 Decode Memory Consumption

![Revised 08 Decode Memory Consumption](plots/revised_08_decode_memory_consumption.png)

### 09 Spatial VRAM Composition (Prefill) · Pie View

![09 Spatial VRAM Composition (Prefill) · Pie View](plots/revised_09_prefill_vram_composition_pie.png)
