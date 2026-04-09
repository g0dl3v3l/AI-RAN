---
tags: [concept, edge, gateway, orchestration]
aliases: [Extreme-Edge Service Chutes, Service Chutes]
---

# Extreme-edge service chutes

[[concepts/extreme-edge-service-chutes|Extreme-edge service chutes]] are lightweight, containerized services placed near the user or enterprise ingress point to run local logic before traffic reaches the main edge or cloud inference plane.

## Paper anchor
- [[papers/paradrop|Paradrop]]

## Best-fit functions
- prompt filtering and privacy redaction
- speech preprocessing
- retrieval-cache lookup
- policy enforcement
- fallback small-model inference

## Why this matters
Shrinking or sanitizing requests before they enter the [[RAN]] reduces pressure on [[uplink]] budgets and improves the odds that [[concepts/latency-budgeting|latency budgets]] can be met.

## Linked notes
- [[architecture/reference-architecture|Reference architecture]]
- [[synthesis/cross-paper-synergies|Cross-paper synergies]]
