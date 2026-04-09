---
tags: [concept, llm, inference, scheduling]
aliases: [Phase-Aware LLM Serving]
---

# Phase-aware LLM serving

[[LLM]] serving should be treated as a sequence of distinct phases rather than one opaque compute step.

## Main phases
- ingress / request normalization
- [[uplink]] transport
- [[prefill]]
- [[decode]] loop
- token streaming / [[downlink]]
- session teardown or cache retention

## Why this matters
- [[prefill]] and [[decode]] stress hardware differently.
- [[decode]] is more sensitive to session continuity and [[concepts/kv-cache-affinity|KV-cache affinity]].
- Some phases are much better fits for [[concepts/spare-compute-envelope|spare AI-RAN compute]] than others.

## Derived from
- [[papers/cora|CORA]] for stage budgeting
- [[papers/weaver|Weaver]] for workload compatibility and GPU-sharing caution

## Linked notes
- [[concepts/latency-budgeting|Latency budgeting]]
- [[architecture/reference-architecture|Reference architecture]]
