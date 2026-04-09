---
tags: [synthesis, research, open-problems]
aliases: [Open Problems]
---

# Open problems

## 1. [[concepts/kv-cache-affinity|KV-cache affinity]] under handover
How should a long-lived session preserve decode continuity when the UE moves?

## 2. Token-length-aware [[concepts/latency-budgeting|latency budgeting]]
How should the planner handle uncertain output length and token streaming?

## 3. Decode compatibility with [[AI-RAN]] sharing
Can memory-bandwidth isolation make same-GPU [[LLM decode]] safe with RAN PHY?

## 4. Multi-tier placement policy
What is the optimal split between device, gateway, MEC, AI-RAN spare compute, and regional cloud for different model classes?

## 5. Digital-twin fidelity for serving systems
What extra instrumentation is needed in [[concepts/ran-digital-twin|digital twins]] to emulate session state, cache migration, and token streaming accurately?

## 6. Security and privacy at the far edge
How should gateway-local preprocessing interact with operator policy, tenant isolation, and enterprise trust boundaries?

## 7. Cross-site session continuity
How should [[papers/weaver|Weaver]]-style inter-site adaptation be repurposed for inference overflow without breaking session state consistency?
