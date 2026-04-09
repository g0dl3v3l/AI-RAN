---
tags: [architecture, llm-ran, edge-ai]
aliases: [Reference Architecture, LLM Inference over RAN]
---

# Reference architecture

## Recommended stack

### Tier 0: Device
- user prompt capture
- optional local fallback model

### Tier 1: Far-edge gateway
- [[concepts/extreme-edge-service-chutes|service chutes]]
- prompt compression, privacy redaction, retrieval cache, enterprise policy

### Tier 2: RAN control
- radio measurements and queue state
- [[concepts/latency-budgeting|latency planner]]
- [[papers/weaver|Weaver]]-style RAN-safe compute export

### Tier 3: MEC inference plane
- latency-critical serving workers
- session manager and [[concepts/kv-cache-affinity|KV-cache anchor]]
- split [[prefill]] / [[decode]] pools when possible
- use only when site-local accelerator and memory envelopes are explicitly provisioned

### Tier 4: AI-RAN spare-compute plane
- opportunistic training, adaptation, embeddings, batch prefill
- only for workloads compatible with the [[concepts/spare-compute-envelope|spare-compute envelope]]

### Tier 5: Regional / central AI cluster
- large models
- overflow inference
- global cache and model lifecycle management
- default full-model serving tier when MEC resources are uncertain

### Tier 6: Validation / digital twin
- [[concepts/ran-digital-twin|CHRONOS-style digital twin]]

## Data path
`device -> gateway -> uplink -> planner -> prefill -> decode -> token stream -> downlink`

### Safe default path
`device -> gateway -> uplink -> planner -> regional edge inference -> token stream -> downlink`

## Control path
`telemetry -> budget planner -> radio scheduler -> compute dispatcher -> session manager -> placement/orchestration`

## Design rule
Use [[papers/weaver|Weaver]] to share RAN-adjacent compute **only where workload compatibility is favorable**. Do not assume that all [[LLM]] phases belong on the same shared GPU pool.

## Linked notes
- [[concepts/serving-slos|Serving SLOs]]
- [[architecture/control-loops|Control loops]]
- [[concepts/latency-budgeting|Latency budgeting]]
- [[concepts/phase-aware-llm-serving|Phase-aware LLM serving]]
