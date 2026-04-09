---
tags: [concept, ai-ran, gpu, sharing]
aliases: [Spare Compute Envelope, SM Envelope]
---

# Spare-compute envelope

A [[spare-compute envelope]] is a stable, RAN-safe exposure of GPU capacity that remains after satisfying latency-critical [[RAN]] processing.

## Paper anchor
- [[papers/weaver|Weaver]]

## Why it matters
Raw spare compute can be too bursty to be useful. A stable envelope allows co-located workloads to make forward progress without violating RAN deadlines.

## Implication for [[LLM]] systems
- good fit: training, adaptation, embeddings, some prefill work
- poor default fit: same-GPU interactive [[LLM decode]]

## Linked notes
- [[concepts/phase-aware-llm-serving|Phase-aware LLM serving]]
- [[synthesis/feasibility-matrix|Feasibility matrix]]
