---
tags: [paper, cora, ran, edge, scheduling, inference]
aliases: [CORA]
---

# CORA

Source: [CORA PDF](../CORA.pdf)

## Title
*End-to-End Coordination of RAN and Edge Server for Latency-Critical Inference Serving over Cellular Networks*

## Core contribution
[[papers/cora|CORA]] coordinates [[uplink]], [[compute]], and [[downlink]] with per-stage latency budgets, runtime load estimation, and deadline-aware radio/compute scheduling.

## Reusable primitives
- [[concepts/latency-budgeting|Latency budgeting]] across radio and compute
- per-model profiling for input/output size and compute scaling
- admission control under contention
- dispatch-order optimization at the edge server

## How it helps an [[LLM]]-over-[[RAN]] system
- It is the strongest runtime template for interactive inference.
- Its planner can be adapted from `uplink -> compute -> downlink` to [[concepts/phase-aware-llm-serving|`uplink -> prefill -> decode -> stream`]].
- Its radio scheduler logic is directly relevant for prioritizing latency-critical sessions.

## Needed adaptations
- output length is uncertain for autoregressive generation
- compute is not a single stage for [[LLM]] serving
- [[concepts/kv-cache-affinity|KV-cache affinity]] and handover are missing from the original design

## Key links
- [[concepts/latency-budgeting|Latency budgeting]]
- [[concepts/phase-aware-llm-serving|Phase-aware LLM serving]]
- [[architecture/reference-architecture|Reference architecture]]
