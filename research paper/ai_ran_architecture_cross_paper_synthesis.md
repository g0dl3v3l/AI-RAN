# AI-RAN Inference Architecture Cross-Paper Synthesis

## Scope

This note consolidates the architectural analysis across the following paper families:

- **Weaver** — AI-and-RAN compute sharing for foundation model training on AI-RAN infrastructure.
- **CORA** — latency-critical inference serving through end-to-end coordination across uplink, compute, and downlink.
- **Beyond Connectivity** — an open architecture for converging AI and RAN workloads on shared infrastructure.
- **AI-RAN pathway / concept papers** — cloud-native, microservice-based, hierarchical AI-RAN architecture concepts.
- **Open & AI RAN workshop papers** — especially *Distributed AI Platform for the 6G RAN*, *Towards AI-Native RAN: Architecture and Key Technologies*, traffic-prediction rApp/xApp work, and drift-handling in O-RAN.

The goal is to answer five architecture directives for a **generic, cloud-native, multi-tenant AI inference framework over RAN infrastructure**.

## Evidence policy

- **Direct evidence**: explicitly grounded in the cited paper or source.
- **Architectural synthesis**: reasoned system design that combines multiple sources and should not be mistaken for a finalized standard.

---

## 1. Executive Synthesis

The papers are solving different layers of the same system:

- **Weaver** solves **AI-and-RAN coexistence at the fastest timescale**: how to expose stable spare GPU capacity to a non-RAN workload while preserving strict RAN deadlines.
- **CORA** solves **latency-critical inference coordination across uplink / compute / downlink** using offline profiling plus runtime adaptation.
- **Beyond Connectivity** defines the **missing orchestration layer** that current O-RAN does not yet provide for generic AI workloads: an **AI-RAN Orchestrator**, **AI-SMO**, and **AI-RAN sites** extending **O-Cloud**.
- **AI-RAN pathway / Open & AI RAN papers** explain how this should be made **cloud-native**, **microservice-based**, and **hierarchical**, with control split across **SMO / Non-RT RIC / Near-RT RIC / DU-local logic**.

### Main design outcome

A viable generic AI-RAN inference system is **not** a single scheduler. It is a **hierarchical control stack** with:

1. **SMO / Non-RT RIC / O-Cloud** for lifecycle, placement, policy, model management, and SLA classes.
2. **Near-RT RIC / xApps** for live routing and policy enforcement.
3. **DU-local or dApp-like logic** for per-slot enforcement and coexistence with RAN deadlines.

This architecture can support **generic onboarding of heterogeneous AI services**, but **hard latency guarantees** still require **profiling, admission control, and conservative isolation**. Current O-RAN specifications and hardware isolation mechanisms do **not** yet form a complete generic low-latency AI multi-tenancy framework on their own.

---

## 2. Evidence Boundary

### Strong direct conclusions

- **Weaver does not map directly to today’s SMO**; its fast control loop is embedded in the **MAC scheduler**.
- **Beyond Connectivity** explicitly argues that the current O-RAN SMO/RIC architecture does **not** support generic AI workloads on shared RAN infrastructure and proposes architectural extensions.
- **AI-RAN pathway** explicitly shows a **hierarchical control picture** with **Non-RT RIC**, **Near-RT RIC**, and **dApps**.
- **CORA** explicitly relies on **offline profiling** plus **runtime adaptation** for latency-critical inference.
- Current practice still leans heavily on **physical isolation** such as **MIG**, **MPS**, and CPU pinning.

### Synthesis-level conclusions

- A **hierarchical RIC for distributed inference routing** is a sound architectural synthesis, but it is **not yet a finalized standard O-RAN design**.
- A Paradrop-like AI-RAN platform is feasible at the **orchestration substrate** level, but not as a **fully unprofiled hard-SLA scheduler** for arbitrary unseen workloads.

---

## 3. Directive 1 — Weaver’s Algorithm and O-RAN SMO Integration

## Short answer

**No, Weaver’s orchestration algorithm does not map directly to the O-RAN SMO framework.**

It naturally splits into two layers:

1. **Fast coexistence control** — DU-local / MAC-scheduler / dApp-like logic.
2. **Slow cross-site coordination** — O-Cloud / SMO-adjacent orchestration.

## Direct evidence from Weaver

Weaver explicitly:

- embeds a **RAN-centric spare-compute controller inside the MAC scheduler**,
- uses **compute-aware MAC scheduling**,
- maintains a stable **SM envelope**,
- separates adaptation into **inter-site** and **intra-site slot-level** control,
- places a **centralized training state coordinator at the mobile core**.

That is not how present SMO works. SMO is a lifecycle/orchestration plane, not a per-slot scheduler.

## Architectural mapping to O-RAN

| Weaver component | Best-fit O-RAN placement | Rationale |
| :--- | :--- | :--- |
| RAN-centric spare-compute controller | **DU-local / MAC scheduler / dApp-like runtime** | Operates at per-slot timescale and directly shapes PRB/SM demand |
| Intra-site slot-level scheduling | **Below Near-RT RIC** | Too fast for SMO and likely too fast for conventional Near-RT loops |
| Centralized training state coordinator | **AI-SMO / O-Cloud / Non-RT-adjacent orchestration** | Slower, cross-site coordination role |
| Inter-site workload redistribution / model rebalancing | **SMO / O-Cloud orchestration domain** | Cross-site optimization with slower adaptation |

## Interface interpretation

### O1
Useful for:
- telemetry,
- monitoring,
- coexistence-policy configuration,
- alarm/reporting.

Not appropriate for:
- per-slot training control.

### O2 / AI-O2
Useful for:
- deploying training/inference services,
- GPU partition configuration,
- model and image rollout,
- site-level resource allocation,
- O-Cloud lifecycle automation.

This is the right fit for **Weaver’s slow path**, not the fast path.

### A1
Useful for:
- coarse policy transfer from **Non-RT RIC** to **Near-RT RIC**,
- coexistence policy,
- SLA class guidance,
- admission posture.

### E2
Useful for:
- near-real-time radio control,
- live telemetry,
- xApp policy enforcement,
- exposure of radio state to inference-routing logic.

Not sufficient by itself for:
- Weaver’s embedded per-slot GPU/RAN scheduler logic.

## Directive 1 conclusion

**Weaver should be integrated with O-RAN as a split control system, not as a direct SMO algorithm.** Its **slow orchestration** can be aligned with **SMO / Non-RT RIC / O-Cloud**, while its **fast spare-compute shaping** must remain **DU-local**, effectively below standard RIC timescales.

---

## 4. Directive 2 — Pre-Profiling vs Generic Multi-Tenancy

## 4.1 How allocation works in Beyond without CORA-style rigid profiling

Beyond does **not** replace profiling with a universal runtime scheduler.

Instead, it introduces an **orchestration substrate**:

- **AI-RAN Orchestrator**,
- **AI-SMO**,
- **AI-RAN sites**,
- **AI-O2**,
- real-time and batch workflows,
- operator policy interfaces,
- workload automation,
- MEC-like real-time entry paths.

So Beyond changes the problem from:

> “How do I exactly schedule a known workload end-to-end under a hard latency budget?”

to:

> “How do I build an architecture that can onboard, place, validate, isolate, and manage heterogeneous AI workloads on shared RAN infrastructure?”

## 4.2 Why CORA and Weaver need pre-profiling

Both papers are targeting **strong guarantees**:

- **CORA**: deadline-sensitive inference.
- **Weaver**: RAN-safe training coexistence under per-slot timing constraints.

They therefore require:

- per-model demand estimation,
- speedup models,
- runtime channel/load adaptation,
- admission control,
- bounded scheduling behavior.

This is a different goal from Beyond’s generic orchestration architecture.

## 4.3 Can a Paradrop-like multi-tenant framework exist on the RAN?

### Yes — at the orchestration layer

It is practical for:

- cloud-native onboarding,
- containerized deployment,
- tenant isolation,
- model registry,
- policy-driven placement,
- edge/cloud distribution,
- lifecycle automation,
- best-effort or coarse-SLA AI services.

### Not yet — for arbitrary unpredictable low-latency coexistence with guarantees

The papers do **not** show that current O-RAN plus current hardware can safely host **arbitrary unseen tenant AI workloads** with strong latency guarantees next to RAN hot paths.

That still requires:

- curated workload classes,
- predeployment or prewarming,
- profiling or hardware-aware characterization,
- admission control,
- conservative isolation or fast local control.

## 4.4 Do current O-RAN specs and hardware isolation allow truly generic multi-tenancy?

### O-RAN specifications

Current O-RAN materials support:

- cloudification,
- common APIs,
- lifecycle management,
- O-Cloud orchestration,
- AI/ML workflow descriptions,
- O1/O2-based management.

They do **not** provide:

- a mature standardized generic multi-tenant AI inference scheduler,
- a standard fast path for arbitrary AI workload coexistence at DU timescales,
- a standardized GPU arbitration plane for AI + RAN coexistence.

### Hardware isolation reality

#### MIG
- hard partitioning,
- useful for safe isolation,
- coarse,
- expensive to reconfigure,
- poor fit for highly dynamic coexistence.

#### MPS
- finer-grained sharing,
- usable in managed inference settings like CORA,
- best-effort,
- no hard memory isolation,
- costly to reconfigure for highly dynamic per-slot coexistence.

#### Green Contexts
- lower switching overhead,
- helpful,
- still not a complete answer for full hard isolation across all resource dimensions.

#### CPU pinning / quotas
- good for coarse orchestration,
- insufficient for accelerator-level deadline-sensitive coexistence.

## Directive 2 conclusion

**Beyond makes generic AI workload onboarding possible at the architecture level, but not fully generic hard-SLA multi-tenancy at the scheduler level.** Today’s O-RAN stack plus MIG/MPS/pinning support **managed coexistence**, not unconstrained unpredictable low-latency AI multi-tenancy with strong guarantees.

---

## 5. Directive 3 — Microservices, Cloud-Native Design, and AI-RAN

## 5.1 What the papers imply

The AI-RAN literature strongly supports a design that is:

- **cloud-native**,
- **containerized**,
- **microservice-based**,
- **O-Cloud managed**,
- **policy/orchestration driven**.

The strongest support comes from:

- **Beyond Connectivity**,
- **AI-RAN: The pathway to future wireless networks**,
- **Towards AI-Native RAN**,
- **Distributed AI Platform for the 6G RAN**.

## 5.2 Recommended architecture for the inference system

### A. Orchestration plane — SMO / AI-SMO / O-Cloud

Responsibilities:

- model registry,
- deployment automation,
- tenant onboarding,
- authentication and validation,
- policy management,
- resource reservation,
- placement across AI-RAN sites,
- telemetry collection over O1/O2,
- SLA-class assignment.

### B. Near-real-time control plane — Non-RT RIC + Near-RT RIC

#### Non-RT RIC
- model lifecycle,
- retraining triggers,
- cache placement policy,
- admission class configuration,
- inter-site placement policy.

#### Near-RT RIC
- live route selection among candidate sites/services,
- slice-aware prioritization,
- dynamic offload enable/disable,
- policy enforcement via xApps.

### C. Site runtime plane — AI-RAN site / AI-O-Cloud runtime

- long-lived inference services,
- model preloading,
- GPU partition and quota enforcement,
- data-plane attachment to DU/CU/UPF-adjacent paths,
- monitoring, rollback, and scaling.

### D. Hot-path execution plane — DU-local / dApp-like / pinned runtime

- strictest loops,
- no cold starts,
- minimal remote orchestration in the decision path,
- shared-memory or minimal-hop data paths,
- long-lived resident services.

## 5.3 Overhead of microservices at DU edge

### Strongly supported conclusion

Beyond reports deployment costs that are already enough to rule out cold deployment for strict hot-path latency:

- RAN/ResNet-like workloads: roughly **1–4 s** deployment time,
- LLM deployment: roughly **5.8–34.4 s** average.

Together with CORA’s explicit use of **preloaded models**, this supports the conclusion that:

> **On-demand container deployment is too slow for strict sub-second inference service instantiation at the DU edge.**

### Safe conclusion

The evidence supports a qualitative rule:

> Use microservices and containers for **packaging, lifecycle, deployment, and policy orchestration**, but **do not rely on cold deployment or excessive cross-service hops on the latency-critical path**.

So the correct architecture is:

- **cold path**: cloud-native, microservice-heavy,
- **hot path**: pre-warmed, pinned, long-lived, minimal-hop.

---

## 6. Directive 4 — Hierarchical RIC for Inference

## Short answer

A **hierarchical RIC for inference** is best presented as a **cross-paper architectural synthesis**, not as an already standardized final design.

The hierarchy itself is strongly supported.

## 6.1 Direct evidence for hierarchy

### From AI-RAN pathway
- **Non-RT RIC** handles long-horizon policy, training/retraining, and delay-tolerant functions.
- **Near-RT RIC** handles inference-driven control.
- **dApps** handle ultra-low-latency local control when data export is infeasible.

### From Beyond
- **AI-RAN Orchestrator / AI-SMO**,
- **AI-RAN sites**,
- **AI-accelerated Near-RT RIC**,
- real-time and batch workflows,
- **AI-O2**,
- MEC-like entry path.

### From Open & AI RAN papers
- NAS traffic prediction: **rApps** for architecture optimization, **xApps** for real-time inference.
- Drift handling: **Non-RT RIC** for model lifecycle, **Near-RT RIC** for xApps.

## 6.2 Recommended split for distributed inference management

| Layer | Timescale | Main role for inference | O-RAN entities / interfaces |
| :--- | :--- | :--- | :--- |
| **SMO / AI-SMO / O-Cloud** | seconds to minutes and above | onboarding, model registry, placement, lifecycle, SLA classes, policy, capacity reservation, cross-site orchestration | O1, O2 / AI-O2 |
| **Non-RT RIC / rApps** | >1 s | model selection policy, retraining triggers, cache policy, coarse admission, traffic-class strategy | A1, O1/O2 telemetry intake |
| **Near-RT RIC / xApps** | ~10 ms to 1 s | live inference routing, site/cell/service steering, slice-aware resource control, dynamic policy enforcement | E2, A1 |
| **DU-local / dApp / MAC / site runtime** | sub-10 ms to per-slot | batching gates, accelerator partition adherence, preemption, PRB/SM shaping, direct local inference | local scheduler logic |

## 6.3 What each layer should decide

### Non-RT RIC / SMO
- which models are allowed,
- which tenant/SLA class gets what reservation,
- which AI-RAN site should host each service class,
- which services must remain warm,
- operator coexistence policy.

### Near-RT RIC
- which already-available service instance should handle a request,
- whether to stay local or move to neighboring edge/cloud,
- live slice/cell/service prioritization.

### DU-local / dApp
- whether the task can execute safely this slot,
- whether to delay, batch, or drop,
- how much accelerator capacity is exposed right now.

## Directive 4 conclusion

The correct phrasing is:

> **A hierarchical inference RIC is a sound architectural synthesis from the current AI-RAN/O-RAN literature.**

It should not be presented as a finalized standardized inference scheduler, but the split across **Non-RT**, **Near-RT**, and **DU-local** responsibilities is strongly supported.

---

## 7. Directive 5 — Resolving Weaver’s Concerns for Inference

Weaver is a **training** paper, so its concerns do not transfer unchanged to inference.

## 7.1 Compute contention

### In Weaver
- training is compute-bound,
- RAN LDPC is memory-bandwidth bound,
- coexistence is possible if spare compute is shaped safely.

### In inference
Compute contention still matters, but the objective changes:

- training maximizes long-run throughput,
- inference minimizes deadline misses and tail latency.

### Mitigation path
- **CORA**: per-stage latency budgeting and dispatch ordering.
- **Beyond / AI-RAN**: AI-RAN sites, O-Cloud orchestration, policy-driven coexistence.

## 7.2 Memory limits

### In Weaver
Memory pressure includes:

- model state,
- optimizer state,
- layout coordination,
- dynamic reconfiguration overhead.

### In inference
Most training-specific burdens disappear, but memory remains important for:

- model residency,
- warm service count,
- feasible partition size,
- co-located service count.

### Evidence-supported interpretation
- Beyond’s deployment results imply non-trivial footprint and cold-path costs.
- CORA handles this operationally by **preloading models on the GPU**.

## 7.3 Network bottlenecks

### In Weaver
The dominant network concerns are inter-site coordination and dynamic cross-site capacity adaptation.

### In inference
The dominant network concerns become:

- uplink transport,
- downlink transport,
- edge vs cloud path selection,
- mobility-sensitive service continuity.

### Strongest grounding
This is where **CORA** is strongest:

- it models **uplink / compute / downlink** separately,
- updates channel information every **100 ms**,
- shows that different workloads bind at different stages.

## 7.4 What does not transfer from Weaver

These should not be imported as generic inference fundamentals:

- exact-once sample accounting,
- debt accounting for training contribution skew,
- model layout resharding,
- step-barrier logic,
- training throughput-maximization semantics.

## 7.5 What dominates in inference instead

Within the evidence base, the strongest supported inference-side concerns are:

- tail-latency sensitivity,
- model preloading / residency,
- cold deployment cost,
- transport-path dependence,
- admission under hard deadlines,
- local enforcement for safety-critical loops.

## Directive 5 conclusion

**Weaver’s training bottlenecks translate unevenly to inference.** Compute contention remains central, but training-state coordination mostly disappears. Inference shifts the problem toward **deadline-sensitive placement, model residency, transport-stage budgeting, and hot-path enforcement**.

---

## 8. Final Architectural Recommendation

## 8.1 Recommended system shape

### Layer 1 — AI-SMO / SMO / O-Cloud
Use for:

- tenant onboarding,
- model catalog,
- placement,
- policy,
- authentication,
- AI-O2 / O2 deployment,
- telemetry and lifecycle.

### Layer 2 — Non-RT RIC / rApps
Use for:

- model lifecycle policy,
- retraining triggers,
- architecture optimization,
- cache and residency policy,
- inter-site planning.

### Layer 3 — Near-RT RIC / xApps
Use for:

- live routing among already-available inference services,
- slice-aware steering,
- load-aware policy enforcement,
- dynamic offload decisions.

### Layer 4 — DU-local / dApps / scheduler plugins
Use for:

- per-slot coexistence,
- accelerator exposure control,
- batching/preemption gates,
- safe local inference when export is infeasible.

## 8.2 Two service classes are necessary

### Class A — curated latency-critical inference
- pre-profiled or at least hardware-characterized,
- pre-warmed,
- resident at AI-RAN site or DU-adjacent runtime,
- admitted conservatively,
- strong coexistence controls.

### Class B — generic cloud-native AI workloads
- containerized,
- policy-driven,
- batch or soft-real-time,
- placeable across AI-RAN sites / edge / cloud,
- weaker guarantees but higher flexibility.

This split is the cleanest way to reconcile:

- **Beyond’s generic platform ambition**, and
- **CORA/Weaver’s hard real-time conservatism**.

## 8.3 Final design conclusion

If the goal is a **generic, cloud-native, multi-tenant AI inference framework over RAN infrastructure**, then the strongest cross-paper conclusion is:

> Build **generic cloud-native orchestration** at the **SMO / O-Cloud / AI-RAN site** layers, but keep **strict latency-critical coexistence logic local to the DU / MAC / dApp runtime**.

Do **not** assume that current O-RAN specifications or current GPU isolation alone already provide a complete generic hard-SLA scheduler for arbitrary AI workloads.

---

## 9. Bottom-Line Answers to the Five Directives

1. **Weaver ↔ SMO?**  
   **No direct mapping.** Fast control belongs in **DU/MAC/dApp-like logic**; only slow coordination maps near **SMO / Non-RT / O-Cloud**.

2. **Beyond vs CORA/Weaver profiling?**  
   **Beyond provides the orchestration substrate, not a replacement for profiling.** It enables heterogeneous AI onboarding; hard SLA still needs profiling, admission, and isolation.

3. **Microservices at DU edge?**  
   **Yes for lifecycle and orchestration. No for cold-path execution in strict sub-second loops.** Hot-path inference must be pre-warmed, pinned, and low-hop.

4. **Hierarchical RIC for inference?**  
   **Valid architectural synthesis.**  
   - **Non-RT / SMO**: lifecycle and coarse placement  
   - **Near-RT**: live routing and enforcement  
   - **DU-local**: per-slot coexistence and execution control

5. **Weaver concerns under inference?**  
   - **Compute contention remains**  
   - **Training-state mechanisms mostly disappear**  
   - **Memory shifts to residency / partition sizing**  
   - **Network shifts to uplink / downlink / edge-cloud transport**  
   - **CORA** is the main inference-side mitigation pattern

---

## 10. References

[1] **Weaver: Foundation Model Training over AI-RAN Compute Infrastructure.** Local PDF in current corpus; venue and DOI not identified from available metadata.

[2] Sunghyun Jin, Serae Kim, Sangtae Ha, and Kyunghan Lee, **“End-to-End Coordination of RAN and Edge Server for Latency-Critical Inference Serving over Cellular Networks,”** *Proceedings of the ACM on Networking*, vol. 3, CoNEXT4, 2025. DOI: [10.1145/3768987](https://doi.org/10.1145/3768987).

[3] Michele Polese, Niloofar Mohamadi, Salvatore D’Oro, Leonardo Bonati, and Tommaso Melodia, **“Beyond Connectivity: An Open Architecture for AI-RAN Convergence in 6G,”** arXiv:2507.06911, 2025. URL: [https://arxiv.org/abs/2507.06911](https://arxiv.org/abs/2507.06911).

[4] **AI-RAN: The pathway to future wireless networks.** Local PDF in current corpus; citation metadata not fully verified in this note.

[5] **Proceedings of the 2025 2nd ACM Workshop on Open and AI RAN.** Local PDF `open&airan.pdf`. Most relevant included works for this note are *Distributed AI Platform for the 6G RAN*, *Towards AI-Native RAN: Architecture and Key Technologies*, the AI-RAN traffic-prediction poster, and drift-handling work in AI/ML-integrated O-RAN.

[6] O-RAN Alliance WG6 public materials on cloudification and orchestration, including SMO–O-Cloud interaction through **O2**. Public reference: [https://public.o-ran.org/display/WG6](https://public.o-ran.org/display/WG6).

[7] O-RAN nGRG, **Cloud Friendly Future 6G RAN Architecture** (RR-2024-01). Public reference: [https://mediastorage.o-ran.org/ngrg-rr/nGRG-RR-2024-01-O-RAN%20Cloud%20Friendly%20Future%206G%20RAN-v1.2.1.pdf](https://mediastorage.o-ran.org/ngrg-rr/nGRG-RR-2024-01-O-RAN%20Cloud%20Friendly%20Future%206G%20RAN-v1.2.1.pdf).

[8] O-RAN nGRG, **Native AI Architecture Description** (RR-2023-02). Public reference: [https://mediastorage.o-ran.org/ngrg-rr/nGRG-RR-2023-02-Native%20AI%20Architecture%20Description-v1.2.pdf](https://mediastorage.o-ran.org/ngrg-rr/nGRG-RR-2023-02-Native%20AI%20Architecture%20Description-v1.2.pdf).

[9] O-RAN WG2, **AI/ML Workflow Description and Requirements**. Official specification download reference: [https://specifications.o-ran.org/download?id=158](https://specifications.o-ran.org/download?id=158).
