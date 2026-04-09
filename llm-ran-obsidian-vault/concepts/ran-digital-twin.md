---
tags: [concept, ran, digital-twin, emulation]
aliases: [RAN Digital Twin]
---

# RAN digital twin

A [[RAN digital twin]] is a high-fidelity emulated environment that reproduces base-station behavior, protocol timing, and multi-site coordination closely enough to test scheduling, orchestration, and serving policies without touching the live network.

## Why it matters here
- [[LLM]] over [[RAN]] introduces cross-layer effects that are hard to reason about analytically.
- Scheduler and placement changes should be tested against mobility, handover, and contention at scale.

## Paper anchor
- [[papers/chronos|CHRONOS]]

## Role in the architecture
- offline validation
- stress testing of [[concepts/latency-budgeting|latency budgets]]
- testing [[concepts/kv-cache-affinity|KV-cache migration]] strategies
- replay of multi-site serving experiments

## Linked notes
- [[architecture/reference-architecture|Reference architecture]]
- [[architecture/control-loops|Control loops]]
