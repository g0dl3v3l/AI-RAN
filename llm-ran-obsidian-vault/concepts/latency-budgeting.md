---
tags: [concept, scheduling, latency, ran, edge]
aliases: [Latency Budgeting, End-to-End Latency Budgeting]
---

# Latency budgeting

[[Latency budgeting]] means splitting an end-to-end SLA across the actual stages that consume it, then giving each stage enough resource guidance to finish within its slice.

## Paper anchor
- [[papers/cora|CORA]]

## For [[LLM]] serving
The original `uplink -> compute -> downlink` split should become a richer chain:

`ingress -> uplink -> prefill -> decode loop -> token streaming downlink`

## Why it matters
- [[uplink]] and [[downlink]] are shared cellular resources.
- [[prefill]] and [[decode]] have different runtime profiles.
- streaming generation means the “response” is not a single final output.

## Dependencies
- [[concepts/phase-aware-llm-serving|Phase-aware LLM serving]]
- [[concepts/kv-cache-affinity|KV-cache affinity]]
- [[architecture/control-loops|Control loops]]
