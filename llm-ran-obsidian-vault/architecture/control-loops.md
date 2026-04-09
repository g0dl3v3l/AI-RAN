---
tags: [architecture, control, scheduling]
aliases: [Control Loops]
---

# Control loops

An [[LLM]]-over-[[RAN]] system needs at least four nested control loops.

## 1. Slot loop
- timescale: sub-ms to ms
- concern: RAN deadline compliance and [[concepts/spare-compute-envelope|SM envelope]] stability
- paper anchor: [[papers/weaver|Weaver]]

## 2. Request loop
- timescale: ms to hundreds of ms
- concern: [[concepts/latency-budgeting|uplink/prefill/decode/downlink budgeting]], admission, dispatch order
- paper anchor: [[papers/cora|CORA]]

## 3. Session / site loop
- timescale: hundreds of ms to seconds
- concern: handover, [[concepts/kv-cache-affinity|KV-cache affinity]], overflow routing, cross-site placement
- paper anchor: partially [[papers/weaver|Weaver]], but largely an adaptation for [[LLM]] serving

## 4. Lifecycle loop
- timescale: minutes to days
- concern: profiling, model placement, policy tuning, digital-twin experiments
- paper anchor: [[papers/chronos|CHRONOS]] and [[papers/paradrop|Paradrop]]

## Design implication
The system should not collapse these loops into one controller. The papers together imply a hierarchical design where each loop sees the right abstraction, not raw lower-level volatility.

## Linked notes
- [[architecture/reference-architecture|Reference architecture]]
- [[synthesis/cross-paper-synergies|Cross-paper synergies]]
