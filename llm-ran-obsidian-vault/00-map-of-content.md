---
tags: [llm-ran, ran, edge-ai, moc]
aliases: [LLM-RAN MOC, LLM over RAN MOC]
---

# Map of Content: [[architecture/reference-architecture|LLM Inference over RAN]]

This vault organizes the four source papers into a design space for [[architecture/reference-architecture|LLM inference over RAN and associated compute infrastructure]].

## Core synthesis
- [[01-comprehensive-analysis|Comprehensive analysis]]
- [[synthesis/cross-paper-synergies|Cross-paper synergies]]
- [[synthesis/feasibility-matrix|Feasibility matrix]]
- [[synthesis/open-problems|Open problems]]

## Architecture
- [[architecture/reference-architecture|Reference architecture]]
- [[architecture/control-loops|Control loops]]

## Concepts
- [[concepts/serving-slos|Serving SLOs]]
- [[concepts/ran-digital-twin|RAN digital twin]]
- [[concepts/latency-budgeting|Latency budgeting]]
- [[concepts/spare-compute-envelope|Spare-compute envelope]]
- [[concepts/extreme-edge-service-chutes|Extreme-edge service chutes]]
- [[concepts/phase-aware-llm-serving|Phase-aware LLM serving]]
- [[concepts/kv-cache-affinity|KV-cache affinity]]

## Source papers
- [[papers/chronos|CHRONOS]]
- [[papers/cora|CORA]]
- [[papers/paradrop|Paradrop]]
- [[papers/weaver|Weaver]]

## Major architectural components discovered
1. [[concepts/extreme-edge-service-chutes|Extreme-edge ingress and pre/post-processing]]
2. [[concepts/latency-budgeting|End-to-end RAN-edge latency budgeting]]
3. [[concepts/phase-aware-llm-serving|Phase-aware LLM execution]]
4. [[concepts/kv-cache-affinity|Session and KV-cache anchoring]]
5. [[concepts/spare-compute-envelope|RAN-safe GPU spare-compute sharing]]
6. [[concepts/ran-digital-twin|Digital twin and emulation workflow]]

## Recommended reading order
1. [[01-comprehensive-analysis|Comprehensive analysis]]
2. [[architecture/reference-architecture|Reference architecture]]
3. [[synthesis/feasibility-matrix|Feasibility matrix]]
4. [[papers/cora|CORA]] and [[papers/weaver|Weaver]]
5. [[papers/chronos|CHRONOS]] and [[papers/paradrop|Paradrop]]
