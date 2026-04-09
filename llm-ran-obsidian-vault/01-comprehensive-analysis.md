---
tags: [llm-ran, ran, edge-ai, synthesis]
aliases: [Comprehensive LLM-RAN Analysis]
---

# Comprehensive Analysis: Architecting [[architecture/reference-architecture|LLM Inference over RAN]]

## Map of Content
- [[00-map-of-content|Map of Content]]
- [[architecture/reference-architecture|Reference architecture]]
- [[architecture/control-loops|Control loops]]
- [[synthesis/cross-paper-synergies|Cross-paper synergies]]
- [[synthesis/feasibility-matrix|Feasibility matrix]]
- [[synthesis/open-problems|Open problems]]

## Problem framing

The target system is not just “an LLM at the edge.” It is a coordinated, multi-tier inference system in which the [[RAN]] path, the [[edge server]], the [[AI-RAN]] compute substrate, and the far-edge/gateway layer all materially affect latency, admission, and cost. The four papers contribute complementary system primitives:

- [[papers/chronos|CHRONOS]] contributes the [[concepts/ran-digital-twin|digital-twin and emulation]] substrate.
- [[papers/cora|CORA]] contributes [[concepts/latency-budgeting|end-to-end latency budgeting]] and cross-domain scheduling.
- [[papers/weaver|Weaver]] contributes [[concepts/spare-compute-envelope|RAN-safe spare GPU control]] and hierarchical resource adaptation.
- [[papers/paradrop|Paradrop]] contributes [[concepts/extreme-edge-service-chutes|lightweight multi-tenant edge placement]] and orchestration.

The papers do **not** directly solve full [[LLM]] inference over cellular RAN. The architecture must therefore adapt their methods, especially around [[concepts/phase-aware-llm-serving|prefill vs. decode separation]], [[concepts/kv-cache-affinity|KV-cache mobility]], and the fact that interactive autoregressive inference is not the same as one-shot [[DNN]] serving.

## Service objectives for this architecture

The runtime should be optimized around [[concepts/serving-slos|serving SLOs]] that matter for interactive [[LLM]] systems rather than a single generic deadline:

- [[TTFT]] or first-token responsiveness
- per-token latency during active generation
- session completion class, i.e. whether the request is short, streaming, or long-lived

This framing makes [[papers/cora|CORA]] more useful, because its budget planner can be adapted into a rolling budget system rather than a fixed one-shot request deadline.

## What each paper contributes as a reusable primitive

### [[papers/chronos|CHRONOS]]
- Reusable primitive: public-cloud [[RAN]] emulation with [[time virtualization]], slot barriers, and scalable multi-VM coordination.
- Direct value: build a testbed for scheduler design, mobility/handover stress, and cross-tier placement experiments before any production deployment.
- Adaptation: extend the emulated application plane to include [[LLM]] request streams, model-serving queues, session migration, and downlink token streaming.

### [[papers/cora|CORA]]
- Reusable primitive: a planner that jointly reasons about [[uplink]], [[compute]], and [[downlink]] stages and enforces them with radio and compute schedulers.
- Direct value: this is the strongest runtime foundation for latency-critical inference.
- Adaptation: replace “single compute stage” with [[concepts/phase-aware-llm-serving|prefill, decode, and streaming]]; add output-length uncertainty and session state awareness.

### [[papers/weaver|Weaver]]
- Reusable primitive: RAN-first control that turns bursty GPU demand into a stable [[concepts/spare-compute-envelope|SM envelope]], plus hierarchical resource adaptation across sites.
- Direct value: allows safe harvesting of spare [[GPU]] resources from [[AI-RAN]] infrastructure.
- Adaptation: use this primarily for compute-complementary work such as [[prefill]], embeddings, retrieval preprocessing, background fine-tuning, or training—not naive co-location of full interactive decode.

### [[papers/paradrop|Paradrop]]
- Reusable primitive: multi-tenant service containers at the extreme edge with backend orchestration and explicit resource policy.
- Direct value: a practical model for deploying lightweight ingress, privacy, caching, and preprocessing near the user.
- Adaptation: treat it as a far-edge/gateway tier, not as the main cellular inference engine.

## Requirements and constraints extracted from the papers

### Hardware and platform constraints
- [[RAN]] slot deadlines remain hard constraints even when sharing compute.
- [[GPU-accelerated RAN]] is assumed by [[papers/weaver|Weaver]]; without that substrate, spare-compute harvesting changes shape.
- [[papers/paradrop|Paradrop]] assumes modest gateway resources, so only light services belong there.
- [[papers/chronos|CHRONOS]] depends on emulation hooks such as [[FAPI]], custom hypervisor behavior, and slot coordination.

### Software constraints
- [[papers/cora|CORA]] and [[papers/weaver|Weaver]] both assume deep scheduler visibility inside the base-station or [[DU]] software path.
- Offline model profiling is necessary for planning, especially for [[input size]], [[output size]], and compute scaling.
- Existing open-source stacks like [[OpenAirInterface]] are a practical substrate, but they also shape what can be modified.

### Network constraints
- Cellular networks are shared and variable; [[uplink]] and [[downlink]] asymmetry matters.
- Multi-site orchestration inherits backhaul limitations and site heterogeneity.
- Public cloud can be used for emulation, but raw cloud timing is insufficiently deterministic for production-grade slot-sensitive operation.

### Fundamental limits
- The strongest limit surfaced by [[papers/weaver|Weaver]] is that [[LLM decode]] is typically memory-bandwidth heavy, much like RAN PHY hot paths, so direct same-GPU co-location is low-feasibility without very careful isolation or phase separation.
- [[papers/cora|CORA]] is best aligned with one-shot or bounded-output inference; autoregressive generation adds output-length uncertainty and long-lived state.
- [[papers/paradrop|Paradrop]] is a gateway pattern, not a direct substitute for MEC-grade inference hardware.

## Methodology taxonomy for an LLM-RAN system

### 1. [[concepts/ran-digital-twin|Digital twin and emulation]]
Use [[papers/chronos|CHRONOS]] to create repeatable experiments for mobility, handover, scheduler tuning, admission policies, and cross-site routing.

### 2. [[concepts/latency-budgeting|Latency-budgeted inference orchestration]]
Use the [[papers/cora|CORA]] idea of splitting latency across the full path, but expand the compute phase into [[concepts/phase-aware-llm-serving|prefill and decode]] rather than a single opaque execution block.

### 3. [[concepts/spare-compute-envelope|Spare-compute harvesting]]
Use [[papers/weaver|Weaver]] to expose stable compute envelopes from [[AI-RAN]] hardware, but only assign workloads whose resource profile is compatible with RAN safety.

### 4. [[concepts/extreme-edge-service-chutes|Extreme-edge placement]]
Use [[papers/paradrop|Paradrop]]-style chutes for prompt filtering, privacy-preserving preprocessing, retrieval-cache lookups, speech preprocessing, or enterprise policy logic.

### 5. Hierarchical control
The system naturally operates over [[architecture/control-loops|multiple timescales]]:
- slot-level: radio and SM enforcement
- request-level: latency planning and admission
- session/site-level: affinity, routing, and resharding
- lifecycle-level: profiling, placement, and digital-twin validation

## Recommended reference architecture

The most robust architecture is a **tiered, phase-aware design**:

1. **Device / on-UE tier**
   - capture prompt, audio, image, or sensor context
   - optionally run tiny local models for filtering or fallback

2. **Far-edge gateway tier** inspired by [[papers/paradrop|Paradrop]]
   - run [[concepts/extreme-edge-service-chutes|service chutes]] for local privacy filters, prompt compression, enterprise policy enforcement, retrieval cache, and request aggregation

3. **RAN control tier** inspired by [[papers/cora|CORA]] and [[papers/weaver|Weaver]]
   - collect channel state, infer request class, compute per-stage budgets, and coordinate radio + compute scheduling

4. **MEC inference tier**
   - host latency-critical [[prefill]] and/or [[decode]] workers **only when site accelerators are known and deterministic**
   - keep session-local [[concepts/kv-cache-affinity|KV caches]] anchored near active users

5. **AI-RAN spare-compute tier** inspired by [[papers/weaver|Weaver]]
   - host only compatible opportunistic workloads such as training, adaptation, embeddings, or compute-heavy prefill batches

6. **Regional / central AI cluster tier**
   - default home for full-model serving when far-edge or MEC accelerator envelopes are uncertain
   - host large models, overflow traffic, heavyweight reranking, global model management, and longer-running jobs

7. **Digital-twin validation tier** inspired by [[papers/chronos|CHRONOS]]
   - emulate full scenarios before changing live scheduling or placement policy

See [[architecture/reference-architecture|Reference architecture]].

In practice, the safest default serving path is:

`UE -> RAN -> far-edge ingress -> regional edge inference -> streamed downlink`

The MEC tier should be treated as an optimization tier, not an assumed baseline, unless its accelerator envelope is explicitly provisioned for serving.

## Why the architecture should be phase-aware

[[LLM]] inference is not one monolithic compute stage.

- [[Prefill]] is typically heavier, more batchable, and often more compute-dense.
- [[Decode]] is incremental, session-bound, and often more memory-bandwidth limited.
- [[Downlink streaming]] can overlap with decode and should be treated as a continuing transport budget, not a final one-shot response.

This means a direct lift of [[papers/cora|CORA]] should become:

`ingress -> uplink -> prefill -> decode loop -> token streaming downlink -> session teardown`

That decomposition lets the scheduler do three important things:
- place [[prefill]] and [[decode]] on different hardware pools
- protect interactive sessions with [[concepts/kv-cache-affinity|KV-cache affinity]]
- exploit [[papers/weaver|Weaver]]-style spare compute where it is actually compatible

## Cross-paper bottlenecks and how the papers fit together

### Bottleneck: variable radio delay
- Main tool: [[papers/cora|CORA]]
- Supporting tool: [[papers/paradrop|Paradrop]] by shrinking the payload before it enters the RAN

### Bottleneck: uncertainty about large-scale behavior
- Main tool: [[papers/chronos|CHRONOS]]
- Use it to test queueing, mobility, scheduler starvation, and handover-sensitive session anchoring

### Bottleneck: bursty shared GPU capacity
- Main tool: [[papers/weaver|Weaver]]
- Use stable envelopes for compatible work rather than exposing raw bursty slack to the serving stack

### Bottleneck: multi-tier orchestration and locality
- Main tool: [[papers/paradrop|Paradrop]]
- Adapt service-chute thinking to enterprise gateways, private MEC ingress, or far-edge on-prem nodes

## Architectural possibilities

### Option A: Dedicated MEC inference with RAN-aware scheduling
Use [[papers/cora|CORA]] for runtime scheduling, [[papers/chronos|CHRONOS]] for evaluation, and [[papers/paradrop|Paradrop]] for far-edge preprocessing.

- Best for: interactive conversational [[LLM]] serving
- Strength: strongest latency predictability
- Weakness: less aggressive infrastructure reuse

### Option B: Hybrid AI-RAN sharing with dedicated decode
Run [[decode]] on dedicated inference hardware but allow [[prefill]], embeddings, and background adaptation to consume [[papers/weaver|Weaver]]-exposed spare compute.

- Best for: mixed workloads and phased serving
- Strength: captures spare capacity without risking decode jitter
- Weakness: more orchestration complexity

### Option C: Full AI-RAN shared inference
Attempt to run the whole inference path on shared RAN GPUs.

- Best for: research exploration only
- Strength: maximal reuse of deployed compute
- Weakness: weakest feasibility because [[LLM decode]] and RAN PHY both pressure memory bandwidth

### Option D: Gateway-assisted hierarchical LLM service
Place small models or filters at the far edge, medium models at MEC, and large models in regional cloud.

- Best for: privacy-sensitive or enterprise scenarios
- Strength: matches heterogeneous hardware and traffic locality
- Weakness: requires more careful state and cache management

See [[synthesis/feasibility-matrix|Feasibility matrix]].

## What must be adapted specifically for LLM inference

1. **Output-length uncertainty**
   - [[papers/cora|CORA]] assumes more bounded outputs than open-ended generation.
   - LLM serving needs token-budget prediction or streaming replanning.

2. **[[concepts/kv-cache-affinity|KV-cache affinity]]**
   - none of the papers directly solve this
   - it becomes central under handover, mobility, and multi-edge routing

3. **Session-aware admission control**
   - new sessions and continuing sessions should not be treated the same
   - decode continuity should usually outrank fresh prefill admission

4. **Phase-specific placement**
   - [[prefill]] may tolerate opportunistic placement better than [[decode]]
   - background adaptation fits [[papers/weaver|Weaver]] better than interactive decode

5. **RAN event hooks into serving state**
   - handover, bearer changes, and cell load should influence routing and cache placement

## Practical recommendation

The highest-confidence architecture is:

- [[papers/chronos|CHRONOS]] as the design and validation lab
- [[papers/cora|CORA]] as the runtime scheduling core
- [[papers/paradrop|Paradrop]] as the extreme-edge ingress/privacy/cache layer
- [[papers/weaver|Weaver]] as the mechanism for opportunistic **non-decode** AI work on shared [[AI-RAN]] GPUs
- regional edge as the default full-model serving tier unless site-local accelerators are explicitly known

In other words: **use Weaver-like sharing for compatible work, not as a blanket justification to colocate all LLM inference with RAN PHY.**

## Research workflow suggested by the paper set

1. Build a [[concepts/ran-digital-twin|digital twin]] of the target network and serving topology.
2. Profile target model classes for prompt size, prefill cost, decode rate, and downlink streaming behavior.
3. Implement a [[papers/cora|CORA]]-style planner that reasons over `uplink -> prefill -> decode -> stream`.
4. Add [[papers/weaver|Weaver]]-style stable spare-compute exports only for compatible sub-workloads.
5. Add [[papers/paradrop|Paradrop]]-style far-edge services to reduce ingress size and preserve privacy.
6. Validate mobility, tail latency, and admission policies under large synthetic loads in [[papers/chronos|CHRONOS]].

## Open research questions

- How should [[KV cache]] be migrated under handover without breaking tail latency?
- Can [[prefill]] and [[decode]] be split across different tiers without excessive interconnect overhead?
- What prediction method is accurate enough for token-length-aware [[concepts/latency-budgeting|latency budgeting]]?
- Can memory-bandwidth isolation make same-GPU RAN + [[LLM decode]] coexistence practical?
- How should gateway-local privacy filters interact with operator scheduling and policy control?

See [[synthesis/open-problems|Open problems]].
