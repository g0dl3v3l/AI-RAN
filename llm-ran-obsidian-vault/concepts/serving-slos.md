---
tags: [concept, slos, llm, latency]
aliases: [Serving SLOs]
---

# Serving SLOs

An [[LLM]]-over-[[RAN]] system should be optimized around a small set of user-visible serving objectives rather than a single undifferentiated request deadline.

## Core objectives
- [[TTFT]]: time to first token
- per-token latency during active generation
- session completion class: short, medium, or long-lived generation

## Why this matters
- [[papers/cora|CORA]] becomes more useful when its planner is adapted to rolling budgets tied to these objectives.
- [[concepts/phase-aware-llm-serving|Phase-aware LLM serving]] depends on separating prompt upload, [[prefill]], [[decode]], and token streaming.
- [[concepts/kv-cache-affinity|KV-cache affinity]] matters more for long-lived sessions than for short requests.

## Linked notes
- [[concepts/latency-budgeting|Latency budgeting]]
- [[architecture/reference-architecture|Reference architecture]]
