---
tags: [synthesis, synergies, llm-ran]
aliases: [Cross-Paper Synergies]
---

# Cross-paper synergies

## [[papers/chronos|CHRONOS]] + [[papers/cora|CORA]]
Use the [[concepts/ran-digital-twin|digital twin]] to evaluate [[concepts/latency-budgeting|latency-budget planners]] under mobility, handover, and large-scale contention.

## [[papers/cora|CORA]] + [[papers/weaver|Weaver]]
Let [[papers/weaver|Weaver]] expose a stable compute abstraction and let [[papers/cora|CORA]] consume that abstraction for request-level latency planning.

## [[papers/paradrop|Paradrop]] + [[papers/cora|CORA]]
Push data reduction and privacy filtering to the far edge so the radio scheduler sees smaller, cleaner, more predictable requests.

## [[papers/paradrop|Paradrop]] + [[papers/weaver|Weaver]]
Reserve shared AI-RAN compute for heavy compatible tasks while keeping lightweight ingress logic at the gateway.

## [[papers/chronos|CHRONOS]] + [[papers/weaver|Weaver]]
Use emulation to test whether a proposed spare-compute policy remains RAN-safe before deploying it on live infrastructure.

## Highest-value combined reading
The strongest stack is:
- [[papers/chronos|CHRONOS]] for experimentation
- [[papers/cora|CORA]] for runtime inference coordination
- [[papers/weaver|Weaver]] for opportunistic compatible compute reuse
- [[papers/paradrop|Paradrop]] for far-edge ingress services
