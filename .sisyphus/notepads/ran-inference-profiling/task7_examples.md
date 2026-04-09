# Task 7: Real-World Examples — Blockwise Flash-Decoding Attention

## Executive Summary
Task 7 requires blockwise attention over KV-cache history with per-block score accumulation (m_i, l_i, o_i) and final reduction. **5 high-signal GitHub/arXiv sources** provide all necessary patterns; **FlashBlock (2026)** is the primary reference for block math, **vLLM** for engineering.

---

## 5 Production Examples (Ranked by Signal)

### 🥇 1. FlashBlock (Chen et al., 2026) — BLOCK MATH PRIMARY SOURCE
- **Paper**: https://arxiv.org/abs/2602.05305v2
- **Focus**: Per-block attention decomposition + log-space reduction
- **Key Equations** (3–5): Block-internal vs block-external accumulators (Z_i, U_i)
- **Copy**: m_i/l_i/o_i semantics, log-space composition `(U_out + U_in) / (Z_out + Z_in)`
- **Avoid**: Diffusion-specific multi-step logic
- **Why First**: Direct mathematical template for blockwise decode + single-token query (exactly Task 7)

### 🥈 2. vLLM PagedAttention (Kwon et al., 2023–2026) — ENGINEERING PATTERNS
- **Code**: https://github.com/vllm-project/vllm/blob/main/vllm/attention/ops/paged_attn.py
- **Focus**: Block table (logical→physical), partition-wise loop, v1 vs v2 heuristics
- **Copy**: Block table indexing, per-block fetch boundary, `_PARTITION_SIZE=512` pattern
- **Avoid**: Full scheduler/continuous batching logic
- **Why Second**: Production-proven block management; separates concerns cleanly

### 🥉 3. FlashAttention `flash_attn_with_kvcache` (Dao-AILab) — BASELINE API
- **API**: https://github.com/Dao-AILab/flash-attention
- **PR #678**: Paged KV cache support (merged main)
- **Focus**: Single-token decode with block_table parameter
- **Copy**: `cache_seqlens` per-sequence tracking, block_table shape contract
- **Avoid**: Not a source for accumulator math
- **Why Third**: Official reference for decode API surface

### 4️⃣ 4. vLLM RFC #39076 (2026-04-06) — TIMING SEPARATION
- **Issue**: https://github.com/vllm-project/vllm/issues/39076
- **Focus**: LSE (log-sum-exp) extraction as per-block reduction signal
- **Copy**: Attention_fetch_compute ↔ reduction_overhead boundary; LSE as intermediate
- **Avoid**: Full entropy-gated eviction heuristics
- **Why Fourth**: Validates Task 7's timing split design

### 5️⃣ 5. SwiftKV (2026 edge-accelerator) — COUNTER-EXAMPLE
- **Paper**: https://arxiv.org/abs/2601.10953v1
- **Focus**: Per-token streaming attention (no blockwise accumulation)
- **Copy**: Nothing; reference only
- **Avoid**: This streaming design (Task 7 uses blocks)
- **Why Fifth**: Confirms orthogonality of block-based approach

---

## Blockwise Decode Math (Ready to Code)

### Per-Block Accumulation Loop
```
For each block j of size B:
    K_j, V_j = fetch_kv_block(j)           # (B, d_head) each
    S_j = Q @ K_j^T / sqrt(d)              # (1, B) scores
    m_j = max(S_j)                         # Scalar: block max
    P_j = exp(S_j - m_j)                   # (1, B) softmax weights (numerically stable)
    l_j = sum(P_j)                         # Scalar: softmax denominator
    o_j = P_j @ V_j                        # (1, d_head) block output
    
    ← time this loop as attention_fetch_compute_us
```

### Final Reduction Pass
```
m_global = max(m_1, m_2, ..., m_num_blocks)  # Find global max

o_global = 0
l_global = 0
for i in range(num_blocks):
    α_i = exp(m_i - m_global)              # Stability correction
    l_global += l_i * α_i                  # Accumulate norms
    o_global += o_i * α_i                  # Accumulate outputs

output = o_global / l_global

← time this pass as reduction_overhead_us
```

---

## What to Copy vs Avoid

| Item | Source | Decision | Reason |
|------|--------|----------|--------|
| m_i/l_i/o_i per-block accumulators | FlashBlock Eq 3–5 | ✅ COPY | Direct match; stable softmax |
| Log-space final composition `(U_out+U_in)/(Z_out+Z_in)` | FlashBlock Eq 5 | ✅ COPY | Numerical stability required |
| Block table indexing + `cache_seqlens` | FlashAttn + vLLM | ✅ COPY | Production-proven contract |
| Partition-wise loop structure | vLLM v2 | ✅ COPY | Clear per-block boundary |
| LSE as reduction intermediate | vLLM RFC #39076 | ✅ COPY | Validates timing split |
| Full serving engine (scheduler) | vLLM core | ❌ AVOID | Out of scope; Task 7 is isolated |
| Diffusion multi-step logic | FlashBlock context | ❌ AVOID | Extract math only, not training |
| SwiftKV streaming approach | SwiftKV paper | ❌ AVOID | Orthogonal design |
| Monolithic kernel fusion | Various | ❌ AVOID | Task 7 requires separate timing |

---

## Implementation Checklist for Task 7

- [ ] Use FlashBlock's m_i/l_i/o_i math (Eqs 3–5)
- [ ] Block table from FlashAttn or vLLM (logical→physical mapping)
- [ ] Partition-wise loop with clear fetch boundary
- [ ] Separate timing bucket for reduction (not fused)
- [ ] LSE or equivalent as per-block norm (for final composition)
- [ ] Test on tiny synthetic trace (e.g., L=512, block_size=128, num_blocks=4)

---

## One-Line Takeaway
**Use FlashBlock's per-block m_i/l_i/o_i math + vLLM's block table pattern; keep fetch/compute and reduction as separate timing buckets.**

