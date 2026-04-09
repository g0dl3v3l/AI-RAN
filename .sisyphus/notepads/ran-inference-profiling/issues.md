# Issues

## 2026-04-10 Task: T6 local verification environment
- The local machine exposes only a CUDA stub library (`cudaGetDeviceCount` error 34), so `tests/gpu/test_prefill_profile_smoke.py` skips here by design even though the targeted Task 6 pytest suite still passes.
- The package environment currently lacks `transformers` and `safetensors`, so Task 6 cannot rely on full OPT decoder-layer imports locally; the implemented profiler uses config-derived deterministic FP16 linears instead.
