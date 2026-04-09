---
tags: [synthesis, feasibility, llm-ran]
aliases: [Feasibility Matrix]
---

# Feasibility matrix

| Architecture option | Papers used most directly | Feasibility | Main upside | Main risk |
|---|---|---:|---|---|
| Dedicated MEC inference with RAN-aware scheduling | [[papers/cora]], [[papers/chronos]], [[papers/paradrop]] | High | strongest latency control | less infrastructure reuse |
| Hybrid sharing: dedicated decode, opportunistic prefill/aux work | [[papers/cora]], [[papers/weaver]], [[papers/chronos]] | Medium-High | captures spare compute without destabilizing decode | orchestration complexity |
| Full shared same-GPU RAN + LLM inference | [[papers/weaver]], [[papers/cora]] | Low | maximal reuse in theory | [[LLM decode]] and RAN PHY both stress memory bandwidth |
| Gateway-assisted hierarchical service | [[papers/paradrop]], [[papers/cora]], [[papers/chronos]] | Medium-High | privacy, locality, ingress reduction | weak far-edge hardware |
| Opportunistic FM training / adaptation on AI-RAN | [[papers/weaver]], [[papers/chronos]] | High | best fit for spare compute | not a full inference solution by itself |

## Recommended path
The best near-term design is the **hybrid** path:
- keep interactive [[decode]] on dedicated inference hardware
- use [[papers/cora|CORA]]-style planning end to end
- use [[papers/weaver|Weaver]] only for compatible workloads
- use [[papers/paradrop|Paradrop]] at the far edge

## Linked notes
- [[concepts/spare-compute-envelope|Spare-compute envelope]]
- [[concepts/phase-aware-llm-serving|Phase-aware LLM serving]]
- [[architecture/reference-architecture|Reference architecture]]
