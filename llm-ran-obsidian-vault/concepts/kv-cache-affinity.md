---
tags: [concept, llm, cache, mobility, session]
aliases: [KV Cache Affinity]
---

# KV-cache affinity

[[KV-cache affinity]] is the principle that a live generative session should stay close to the compute node holding its attention cache unless there is a compelling reason to migrate it.

## Why it matters in [[RAN]] environments
- UEs move between cells and sites.
- Handover can break locality between the user and the serving [[LLM]] worker.
- Migration cost can erase the latency budget for the next decode steps.

## Not directly solved by the paper set
This note is a synthesis gap that emerges when [[papers/cora|CORA]]-style scheduling is combined with mobility and long-lived [[LLM]] sessions.

## Design implication
- prioritize continuity for ongoing decode sessions
- distinguish fresh-session admission from in-flight-session protection
- test migration policies in a [[concepts/ran-digital-twin|digital twin]] before production rollout

## Linked notes
- [[concepts/phase-aware-llm-serving|Phase-aware LLM serving]]
- [[architecture/control-loops|Control loops]]
