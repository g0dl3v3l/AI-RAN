# Unified vRAN Edge Inference SOTA Review (2022–2026)

## Title, Scope Freeze, and Assumptions

- Title: Unified vRAN Edge Inference State of the Art Review, 2022–2026
 - Scope freeze: This document provides a complete review covering the inclusive SOTA window from 2022 through 2026. The review focuses on scheduler-facing workload classes, primary systems evaluated in the local corpus, and architecture synthesis across AI-RAN related literature. The analysis in this file is complete for the 2022–2026 window, and the in-repo CORA baseline (see CORA Baseline Taxonomy) serves as the anchored provenance for workload identities and parameters.
- Assumptions: All subsequent content should assume operator-managed AI-RAN sites, hierarchical control (SMO / Non-RT RIC / Near-RT RIC / DU-local), and access to GPU partitioning mechanisms such as MIG and MPS where applicable.

## 2022–2026 SOTA Window Rule

The review limits included primary evidence to work published or preprinted within 2022 through 2026 inclusive. Earlier foundational work may be cited as background but does not constitute a primary SOTA item for this window.

## Summary Matrix

Summary Matrix: primary SOTA system per CORA workload (one row per workload × primary system). Core Innovation is a short phrase. Links are stable DOI/arXiv/publisher URLs and match the report references.

| CORA Workload (Mx) | Primary SOTA System | Paper Type | Core Innovation | Venue/Year | Link |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Image Segmentation (M1) | USHER | Serving Runtime | Interference-aware co-location, OG-Merger | OSDI 2024 | https://www.usenix.org/system/files/osdi24-shubha.pdf |
| Image Segmentation (M1) | Orion | Resource Manager | Operator-level kernel scheduling | EuroSys 2024 | https://doi.org/10.1145/3627703.3629578 |
| Image Segmentation (M1) | PPipe | Serving Runtime | Pool-based pipeline parallelism | ATC 2025 | https://www.usenix.org/system/files/atc25-kong.pdf |
| Image Segmentation (M1) | RAVAS | Resource Manager | GPU%-based compute-share allocation | SEC 2023 | https://doi.org/10.1145/3583740.3628443 |
| Image Segmentation (M1) | OctopInf | Serving Runtime | Spatiotemporal portion scheduling (CORAL) | PerCom 2025 (preprint) | https://doi.org/10.48550/arXiv.2502.01277 |
| Pose Estimation (M2) | USHER | Serving Runtime | Interference-aware co-location, OG-Merger | OSDI 2024 | https://www.usenix.org/system/files/osdi24-shubha.pdf |
| Pose Estimation (M2) | Orion | Resource Manager | Operator-level kernel scheduling | EuroSys 2024 | https://doi.org/10.1145/3627703.3629578 |
| Pose Estimation (M2) | PPipe | Serving Runtime | Pool-based pipeline parallelism | ATC 2025 | https://www.usenix.org/system/files/atc25-kong.pdf |
| Pose Estimation (M2) | RAVAS | Resource Manager | GPU%-based compute-share allocation | SEC 2023 | https://doi.org/10.1145/3583740.3628443 |
| Pose Estimation (M2) | OctopInf | Serving Runtime | Spatiotemporal portion scheduling (CORAL) | PerCom 2025 (preprint) | https://doi.org/10.48550/arXiv.2502.01277 |
| Language Processing (M3) | vLLM/PagedAttention | Serving Runtime / Model Accelerator | KV block paging & swap/recompute | SOSP 2023 | https://doi.org/10.1145/3600006.3613165 |
| Language Processing (M3) | Orca | Serving Runtime | Iteration-level scheduling & selective batching | OSDI 2022 | https://www.usenix.org/system/files/osdi22-yu.pdf |
| Language Processing (M3) | DistServe | Serving Runtime | Prefill/decode disaggregation, pull-based KV transfer | OSDI 2024 | https://www.usenix.org/system/files/osdi24-zhong-yinmin.pdf |
| Language Processing (M3) | SpotServe | Serving Runtime | Preemption-aware commit + context migration | ASPLOS 2024 | https://doi.org/10.1145/3620665.3640411 |
| Language Processing (M3) | CacheGen | Model Accelerator | Compressed KV chunking & streaming | SIGCOMM 2024 | https://doi.org/10.1145/3651890.3672274 |
| Translation (M4) | vLLM/PagedAttention | Serving Runtime / Model Accelerator | KV block paging & swap/recompute | SOSP 2023 | https://doi.org/10.1145/3600006.3613165 |
| Translation (M4) | Orca | Serving Runtime | Iteration-level scheduling & selective batching | OSDI 2022 | https://www.usenix.org/system/files/osdi22-yu.pdf |
| Translation (M4) | DistServe | Serving Runtime | Prefill/decode disaggregation, pull-based KV transfer | OSDI 2024 | https://www.usenix.org/system/files/osdi24-zhong-yinmin.pdf |
| Translation (M4) | SpotServe | Serving Runtime | Preemption-aware commit + context migration | ASPLOS 2024 | https://doi.org/10.1145/3620665.3640411 |
| Translation (M4) | CacheGen | Model Accelerator | Compressed KV chunking & streaming | SIGCOMM 2024 | https://doi.org/10.1145/3651890.3672274 |
| Super Resolution (M5) | USHER | Serving Runtime | Activation-aware resource estimation | OSDI 2024 | https://www.usenix.org/system/files/osdi24-shubha.pdf |
| Super Resolution (M5) | Orion | Resource Manager | Operator-level kernel scheduling | EuroSys 2024 | https://doi.org/10.1145/3627703.3629578 |
| Super Resolution (M5) | Aqua | Resource Manager | Network-accelerated memory offloading (Aqua Tensors) | arXiv 2024 | https://doi.org/10.48550/arXiv.2407.21255 |
| Super Resolution (M5) | Proteus | Serving Runtime | Accuracy-scaling variant selection | ASPLOS 2024 | https://doi.org/10.1145/3617232.3624849 |
| Volume Rendering (M6) | Instant-NGP | Model Accelerator | Multiresolution hash encoding + fused kernels | SIGGRAPH 2022 | https://doi.org/10.1145/3528223.3530127 |
| Volume Rendering (M6) | NerfAcc | Model Accelerator | Efficient sampling & packed tensors | ICCV 2023 | https://arxiv.org/abs/2305.04966 |
| Volume Rendering (M6) | TensoRF | Model Accelerator | Compact tensor factorization for radiance fields | ECCV 2022 | https://doi.org/10.48550/arXiv.2203.09517 |
| Volume Rendering (M6) | DirectVoxGO | Model Accelerator | Voxel-grid optimization for fast convergence | CVPR 2022 | https://doi.org/10.1109/CVPR52688.2022.00538 |

## Inclusion rubric

This review uses an explicit inclusion rubric so later per-system write-ups cleanly separate **what a paper directly claims** from **what we infer or adapt** for a vRAN-edge setting.

### Paper types (classification used in every system subsection)

- **Serving Runtime**: An end-to-end inference serving engine/runtime. The paper’s primary contribution is a *system* that accepts inference requests and executes them under realistic constraints (multi-tenant load, tail latency, batching, memory/cache, state/session handling, and hardware allocation). A serving runtime usually spans several of the (a)–(g) axes.
- **Resource Manager**: A system primarily focused on **GPU sharing, placement, isolation, and interference management** across tenants/queues/slices. It may rely on an existing serving runtime (or leave request lifecycle unspecified) but must define concrete resource-control mechanisms (e.g., partitioning, fairness, co-location control, admission/eviction policy).
- **Model Accelerator**: A workload- or model-family-specific acceleration technique/toolbox (e.g., operator fusion, compression, specialized cache structures, rendering accelerators). Model accelerators serve as *mechanism evidence* in this review. As a general rule, accelerator-only papers are not treated as “primary systems” unless they also present an end-to-end serving/runtime or a resource-manager design that addresses request lifecycle, scheduling, and state/VRAM management. When an accelerator is included as mechanism evidence, authors must explicitly label any runtime or serving gaps and provide adaptation hypotheses used by the report.

Exception (M6 carve-out): For the M6 Volume Rendering workload this review makes a narrow, documented exception. Several accelerator-first papers (Instant-NGP, NerfAcc, TensoRF, DirectVoxGO) are considered primaries for the M6 row because they provide decisive, model-family-specific mechanism evidence that directly determines core compute and memory behavior for the workload. Inclusion of these accelerator primaries is permitted only when the report (a) records the exact runtime/serving semantics those papers omit, (b) explicitly flags the runtime gaps, and (c) imports or cites bridge mechanism evidence (e.g., vLLM/SpotServe/CacheGen patterns) to justify adaptation hypotheses for ComputeLease operation.

### “Primary system” criteria (what counts as SOTA evidence in this report)

A paper/system is treated as a **primary** SOTA system for this 2022–2026 review only if it satisfies all of:

1. **Year window**: Published or released as a stable preprint in **2022–2026 inclusive**.
2. **Architecture-rich**: Substantively covers at least **3 of the 4** system axes below for the target workload:
   - **Runtime architecture/topology** (control plane vs data plane, pipeline structure, execution model)
   - **Memory & cache management** (what is stored, where, and how it is bounded/evicted)
   - **Request scheduling & batching** (queueing, ordering, batching, deadline/priority handling)
   - **Session/state management** (what state persists across steps/requests and how it is resumed)
   
   For **stateless one-shot** workloads, *session/state* may be explicitly marked **“N/A by design”** and still count as architecture-rich if the other axes are covered.
3. **Stable citation link**: Provides a stable link suitable for long-lived auditing (**DOI or arXiv** preferred; a stable publisher/venue PDF is acceptable).

4. **M6 carve-out (controlled accelerator primaries)**: For the special-case M6 workload only, accelerator-only papers may be accepted as primaries when they present decisive mechanism evidence for the workload. Such inclusions must be accompanied by (a) an explicit statement of any missing serving/runtime semantics, (b) an adaptation hypothesis mapping to ComputeLease fields, and (c) citation of bridge evidence used to fill runtime gaps. This carve-out does not apply to other workloads.

### Evidence policy (how claims are written)

- **Direct evidence**: A statement that is explicitly supported by the paper’s text, figures, evaluation, or design description. These are written as factual summaries.
- **Inferred / adapted**: A statement that maps a mechanism to the vRAN-edge setting but is **not** directly claimed/evaluated by the paper. These must be labeled using the adaptation-hypothesis tag below.

### Adaptation hypothesis label (mandatory for non-direct mappings)

Use the label:

> **Adaptation hypothesis (AH-\<short-id\>)**: \<claim\>

Rules:
- Use **Adaptation hypothesis** whenever we propose a behavior needed under the ComputeLease setting (bursty leases, strict VRAM cap) that is **not** a direct claim of the paper.
- Each AH must name (i) what the paper provides, (ii) what the vRAN-edge container would need to add/change, and (iii) which **ComputeLease** fields the hypothesis depends on.

## ComputeLease scorecard

Each system subsection includes a short **vRAN edge viability** assessment under an assumed **ComputeLease** contract (defined in the next section). The scorecard is intentionally small and repeatable; it is used to compare “how close” a serving/runtime design is to operating inside bursty spare-GPU windows.

### Score axes (definitions + High/Med/Low scoring)

#### 1) Preemption Resilience

*Question*: Can execution be safely interrupted without corrupting state, and what is the **safest preemption boundary**?

- **High**: Cooperative preemption is supported at fine granularity (e.g., token-step, small operator-group, ray-batch), with bounded lost work and explicit recovery semantics.
- **Medium**: Preemption is possible but requires coarser boundaries (e.g., micro-batch drain, chunk boundary, request-stage boundary) and/or non-trivial quiesce time; some lost work is expected.
- **Low**: Preemption is unsafe or effectively requires full-request completion; interruption risks crash/corruption or forces large rollback/recompute.

**Typical ComputeLease fields used**: `preemption_notice_us`, `reclaim_mode`, `duration_us`.

#### 2) Micro-Segmentation

*Question*: Can work be chopped into units that fit **sub-millisecond** (and potentially **microsecond-scale**) leases? What is the **minimum unit**?

- **High**: The runtime exposes an explicit micro-segmentation unit with low overhead and predictable runtime (operator-group, tile/patch, token-step, ray-batch), enabling scheduling into sub-ms windows.
- **Medium**: Segmentation exists but the minimum unit is multi-millisecond and/or has high overhead/variance; may not reliably fit microsecond-scale windows.
- **Low**: Work is monolithic (long kernels/critical sections) or segmentation is undefined; requires long contiguous GPU time.

**Typical ComputeLease fields used**: `duration_us`, `sm_budget_sms`, `start_time_us`.

#### 3) State Parking

*Question*: During **0% SM availability** gaps (no active lease), what state must be parked, where, and at what cost?

- **High**: Required state is bounded and can be parked/restored cheaply (e.g., small metadata, compact caches, incremental checkpoints). Parking location is explicit (host RAM / local NVMe / remote store) and supports fast resume.
- **Medium**: State can be parked but is large and/or costly to move; partial parking/compression is required and resume latency is non-trivial.
- **Low**: State is unbounded or tightly coupled to GPU memory; parking is infeasible or implies severe recompute/availability loss.

**Typical ComputeLease fields used**: `preemption_notice_us`, `reclaim_mode`, `duration_us`, `bandwidth_budget_hint` (optional).

#### 4) Tight VRAM Compliance (stress evaluation centers on the canonical cap vram_budget_bytes; 60% stress is achieved by configuring vram_budget_bytes = 0.6 * physical_vram_bytes)

*Question*: Can the system operate under a strict VRAM ceiling (the canonical contract field is `vram_budget_bytes` — see note above) without OOM/thrashing/fragmentation collapse? Many scorecards in this report evaluate a stress case that sets `vram_budget_bytes` to 60% of the physical VRAM; the canonical check is always whether live usage stays below `vram_budget_bytes`.

- **High**: VRAM use is explicitly bounded (admission control + predictable allocations), supports eviction/paging/offload, and remains stable under a hard cap with headroom for fragmentation.
- **Medium**: Some VRAM controls exist (e.g., cache caps/eviction), but stability depends on careful tuning; performance degradation and occasional pressure events are plausible under a hard cap.
- **Low**: Relies on near-full VRAM or unbounded caches; likely to OOM or degrade catastrophically under a strict cap.

**Typical ComputeLease fields used**: `vram_budget_bytes`, `gpu_slice` (optional), `gpu_id` (optional).

### Evidence level

- **Direct**: The paper explicitly states or evaluates the relevant behavior.
- **Inferred**: The behavior is plausible from the architecture description but not explicitly claimed/evaluated. Must be accompanied by an **Adaptation hypothesis (AH-…)**.

### Per-system scorecard template (to be copied into each system subsection)

| Axis | Score (High/Med/Low) | Evidence (Direct/Inferred) | Notes (boundary/unit/state/VRAM mechanism) | ComputeLease fields referenced |
| :--- | :--- | :--- | :--- | :--- |
| Preemption Resilience |  |  |  |  |
| Micro-Segmentation |  |  |  |  |
| State Parking |  |  |  |  |
| Tight VRAM Compliance (stress bounded by vram_budget_bytes; 60% stress via vram_budget_bytes = 0.6 * physical_vram_bytes) |  |  |  |  |

## Scheduler / lease contract assumptions

This report assumes the existence of an **external resource allocator/scheduler** that offers bursty access to GPU compute at the vRAN edge. The scheduler itself is **out of scope** here; we only define the *contract* that the inference container assumes it receives.

### Canonical `ComputeLease` contract (assumed interface)

The inference container assumes it is granted a time-bounded lease describing *how much* GPU compute and *how much* VRAM it may use during that window:

```yaml
ComputeLease:
  # Required fields (assumed contract)
  lease_id: string                 # unique identifier for this lease instance
  start_time_us: int               # lease start time (microseconds, scheduler timebase)
  duration_us: int                 # lease duration in microseconds
  sm_budget_sms: int               # effective number of SMs available during the lease
  vram_budget_bytes: int           # hard VRAM budget available to the container
  preemption_notice_us: int        # minimum warning before an early reclaim / end-of-lease reclaim
  reclaim_mode: hard|soft          # hard: must stop by end; soft: best-effort/graceful reclaim
  priority_tier: int               # admission + degradation policy tier (higher = more important)

  # Optional fields (if scheduler/hardware exposes them)
  gpu_id: string?                  # physical GPU identifier (PCIe/BDF, UUID, or node-local id)
  gpu_slice: string?               # MIG UUID or logical slice identifier
  bandwidth_budget_hint: string?   # optional hint (qualitative or quantitative) for state movement
```

Note on VRAM semantics
- `vram_budget_bytes` is a hard VRAM budget: it is the upper bound the container must respect during the lease. When the report refers to a “60% VRAM stress” evaluation, that is an evaluation/configuration choice implemented by setting

  `vram_budget_bytes = 0.6 * physical_vram_bytes`

  for stress-testing purposes. Do not apply an additional multiplicative “0.6×” to `vram_budget_bytes` when reasoning about compliance; all compliance checks compare live usage against `vram_budget_bytes` as the single canonical cap.

### How the inference container uses the lease

Given a `ComputeLease`, the container uses the contract to make **local runtime decisions** (not network/air-interface scheduling decisions):

1. **Admission control**: Accept/reject (or defer) requests so predicted compute and VRAM footprint fit within `sm_budget_sms`/`duration_us` and `vram_budget_bytes`, with policy guided by `priority_tier`.
2. **Micro-segmentation unit selection**: Choose the smallest executable unit that fits the lease envelope (e.g., tile/patch, operator-group, token-step, ray-batch) and aligns with `preemption_notice_us`/`reclaim_mode`.
3. **State parking decision**: Decide what state must be persisted when there is no active lease (0% SM availability), where to park it (host RAM / local NVMe / remote store), and what to evict from VRAM to respect `vram_budget_bytes`.
4. **Pause/park between leases**: When compute is unavailable (no active lease), quiesce GPU work, checkpoint/park required state, and free VRAM as needed; on a new lease, restore state and resume at a safe boundary.

## CORA Baseline Taxonomy

This section presents the CORA baseline taxonomy as an in-repo extracted interpretation. It uses only the local profiling matrix (`research paper/edge_ran_inference_research_matrix.md`) for workload identities and parameters, and the CORA bibliographic metadata in `IPP/main.bib` (DOI: 10.1145/3768987) as provenance. The CORA PDF may be paywalled; treat the entries below as the repo-grounded interpretation of CORA and the profiling matrix.

Below, each CORA workload (M1–M6) is stated using the exact workload name from the matrix, followed by a concise baseline block with: model archetype, delivery mechanism, phase decomposition (as listed in the matrix), dominant pipeline-stage pressure, and a short preemptibility note.

M1 Image Segmentation (DeepLabV3)

- Model archetype: CNN (DeepLabV3)
- Delivery mechanism: One-shot
- Phase decomposition: Feature extraction; Upsampling
- Dominant pipeline-stage pressure: UL > Compute > DL
- Preemptibility: Poor (high context-switch cost mid-layer; scheduling expects coarse per-inference or coarse layer-group boundaries)

M2 Pose Estimation (Transformer/CNN Hybrid)

- Model archetype: Transformer / CNN hybrid
- Delivery mechanism: One-shot
- Phase decomposition: Visual feature extraction; attention propagation
- Dominant pipeline-stage pressure: UL > Compute >> DL
- Preemptibility: Poor (similar per-inference/coarse boundaries required)

M3 Language Processing (Auto-regressive Transformer)

- Model archetype: Auto-regressive Transformer
- Delivery mechanism: Streaming
- Phase decomposition: Prefill (prompt) ; Decode (generation)
- Dominant pipeline-stage pressure: Compute ≈ DL > UL
- Preemptibility: Excellent (can pause between tokens; token-step is the natural fine-grained boundary)

M4 Translation (Seq2Seq Transformer)

- Model archetype: Seq2Seq Transformer
- Delivery mechanism: Streaming
- Phase decomposition: Encoder (source) ; Decoder (target)
- Dominant pipeline-stage pressure: Compute ≈ DL > UL
- Preemptibility: Excellent (token-step / decode boundaries allow interruption)

M5 Super Resolution (ESRGAN)

- Model archetype: CNN / GAN (ESRGAN)
- Delivery mechanism: One-shot
- Phase decomposition: Feature extraction; Pixel-shuffle (upsampling)
- Dominant pipeline-stage pressure: Compute > DL (UL can bind under UL-scarce TDD)
- Preemptibility: Poor (activation-heavy, high mid-layer preemption cost; coarse tiling/patching is the plausible segmentation)

M6 Volume Rendering (NeRF)

- Model archetype: MLP (NeRF family)
- Delivery mechanism: One-shot
- Phase decomposition: Ray sampling ; Volume integration
- Dominant pipeline-stage pressure: Compute > DL >> UL
- Preemptibility: Good (can pause between ray-batches; ray-batch is the natural micro-segmentation unit)

Summary table (CORA workload → preemptibility → natural micro-segmentation unit → key state)

| CORA workload (Mx) | Preemptibility | Natural micro-segmentation unit | Key state |
| :--- | :--- | :--- | :--- |
| M1 Image Segmentation (DeepLabV3) | Poor | Per-inference / coarse layer group | per-inference activations / feature maps |
| M2 Pose Estimation (Transformer/CNN Hybrid) | Poor | Per-inference / coarse layer group | per-inference activations / intermediate feature tensors |
| M3 Language Processing (Auto-regressive Transformer) | Excellent | Per-token step | KV cache (decode state) |
| M4 Translation (Seq2Seq Transformer) | Excellent | Per-token step | Encoder/Decoder KV cache and decoder stream state |
| M5 Super Resolution (ESRGAN) | Poor | Per-inference / coarse tile (tiling) | large activation maps / intermediate feature maps |
| M6 Volume Rendering (NeRF) | Good | Per-ray-batch | voxel/hash tables or partial integration buffers |

Provenance note: the taxonomy above is an in-repo extracted interpretation based on `research paper/edge_ran_inference_research_matrix.md` (workload rows and profiling columns) and the CORA entry in `IPP/main.bib` (DOI: 10.1145/3768987). The CORA paper may be paywalled; where the matrix uses a phrasing (e.g., "KV Cache") that is not verbatim in the CORA PDF, the wording here follows the matrix's scheduler-facing vocabulary and is explicitly labeled as the repo-grounded interpretation.


## Workloads

## M1 Image Segmentation (DeepLabV3)

Primary systems considered: USHER, Orion, PPipe, RAVAS, OctopInf

#### USHER

Paper Type: `Serving Runtime`

(a) High-Level Architecture & System Design

USHER is an end-to-end inference serving system aimed at improving GPU utilization and goodput under latency SLOs by **spatially multiplexing multiple DL models** on a GPU while explicitly modeling **inter-model interference**. It is built around three components: (1) a fast resource estimator based on GPU kernel analysis (GK-Estimator), (2) a heuristic scheduler (IR-Scheduler) that chooses batch size, replication degree, and placement to maximize compute+memory utilization under SLO constraints, and (3) an operator-graph merger (OG-Merger) that merges compatible operator graphs to reduce cache interference.

For M1 (DeepLabV3-like segmentation), USHER is best viewed as *serving-runtime evidence* for interference-aware consolidation of one-shot CNN inference (segmentation requests behave like other one-shot CNN requests, but are typically more activation-heavy).

(b) Infrastructure & Hardware Assumptions

USHER assumes NVIDIA GPUs and uses GPU sharing primitives such as **MPS** (and discusses MIG as a contrasting option). It extracts an operator-level graph (using an ONNX representation for framework independence) and maps operators to GPU kernels using profiling tools; the system relies on offline/one-time profiling for some calibration but aims to avoid prohibitive per-model offline profiling by using kernel analysis to estimate requirements.

Operationally, USHER assumes a conventional inference-serving environment: models are available as graphs, requests arrive over time (variable rates), and the runtime can choose replication and batching under per-model latency SLOs.

(c) Core Optimizations & Algorithmic Design

- **GK-Estimator**: estimates a model’s compute/memory resource requirements by identifying which GPU kernels can execute concurrently for each operator (via kernel analysis) and aggregating resource needs across concurrent-kernel sets.
- **IR-Scheduler**: avoids expensive global optimization by using a lightweight heuristic that forms moderate-sized model groups and then chooses batch size, replication degree, and placement to (i) meet SLOs and (ii) increase joint compute+memory utilization by co-locating compute-heavy and memory-heavy models.
- **OG-Merger**: reduces cache interference by merging operator graphs of sufficiently similar models/operators (e.g., operators with similar structure and weights), creating merged “super-operators” where feasible.

(d) Memory & Cache Management

USHER explicitly treats GPU memory and cache behavior as first-class: it distinguishes memory-space utilization from compute utilization and attributes goodput loss to interference (including cache interference). OG-Merger targets cache reuse by merging graphs when weight submatrices are similar, which (per USHER’s framing) increases cache-content reuse beyond weight-sharing approaches that only reduce memory footprint.

For one-shot segmentation, the key memory pressure is typically intermediate feature tensors/activations (per-inference, not persistent across requests). USHER’s allocator decisions are primarily about *co-located models* and their combined resource footprints rather than intra-request activation paging.

(e) Request Scheduling & Batching

USHER’s scheduling objective is to satisfy latency SLOs while maximizing goodput and cost-efficiency by combining three knobs: **batch size**, **replication degree**, and **placement**. Batching is treated as a coarse knob that increases compute utilization but can increase latency; USHER emphasizes that batching alone cannot simultaneously saturate compute and memory, motivating its joint optimization.

For M1 requests, the practical mapping is “frame-level serving”: segmentation requests can be queued and batched (within SLO), and co-location decisions should consider both compute saturation and memory/activation footprint.

(f) Session & State Management

**N/A by design for one-shot CV inference**: individual segmentation requests are stateless across requests in USHER’s serving model. Persisted state is primarily the loaded model weights/graphs and any profiling/estimation metadata used by the scheduler and merger.

(g) Hardware Parallelization & Resource Allocation

USHER’s resource allocation is primarily **spatial multiplexing** on a single GPU using MPS-like partitioning of compute “space,” combined with placement across a GPU cluster (replication/placement decisions). It also considers workload division across multiple GPUs for large models (discussed in the context of replication/partitioning), but its core contribution for this workload family is interference-aware multiplexing and placement.

vRAN Edge Viability (ComputeLease) + ComputeLease Scorecard:

Under a ComputeLease contract, USHER’s *direct* contribution is high-quality **resource requirement estimation** and **interference-aware co-location**. What it does **not** directly provide is lease-aligned preemption and sub-ms micro-segmentation for a single one-shot request.

**Adaptation hypothesis (AH-USHER-LEASE-OPGROUP)**: Use USHER’s operator/kernels requirement estimates to choose a safe **operator-group** boundary for partial execution that fits `duration_us`/`sm_budget_sms`, and checkpoint only minimal per-request metadata at boundaries. This requires adding (i) operator-group execution control (beyond USHER’s batching/placement) and (ii) a cooperative pause protocol keyed to `preemption_notice_us`/`reclaim_mode`.

ComputeLease Scorecard:

| Axis | Score (High/Med/Low) | Evidence (Direct/Inferred) | Notes (boundary/unit/state/VRAM mechanism) | ComputeLease fields referenced |
| :--- | :--- | :--- | :--- | :--- |
| Preemption Resilience | Medium | Inferred | Safe boundary is per-batch/per-request; no explicit lease-driven preemption in USHER. | `preemption_notice_us`, `reclaim_mode`, `duration_us` |
| Micro-Segmentation | Low | Inferred | USHER optimizes batching/placement, not sub-ms operator chunking; operator-group chunking is AH-USHER-LEASE-OPGROUP. | `duration_us`, `sm_budget_sms` |
| State Parking | Medium | Inferred | One-shot requests are stateless; dominant “state” is model weights + scheduler metadata. Parking weights under hard reclaim implies reload cost (not directly addressed). | `reclaim_mode`, `vram_budget_bytes`, `bandwidth_budget_hint` |
| Tight VRAM Compliance (≤60% stress) | Medium | Direct+Inferred | Direct: explicit modeling of memory utilization and interference; inferred: behavior under hard VRAM cap requires admission control keyed to `vram_budget_bytes`. | `vram_budget_bytes` |

[R1]

#### Orion

Paper Type: `Resource Manager`

(a) High-Level Architecture & System Design

Orion is a fine-grained, interference-aware GPU sharing system that **transparently intercepts GPU kernel launches from multiple clients** sharing a GPU and schedules work at **operator granularity**. Its core thesis is that DNN executions are composed of short operators (10s–1000s of µs) with heterogeneous compute vs memory behavior; by co-scheduling complementary operators, Orion increases overall GPU utilization while preserving tail latency for a high-priority job.

For M1 segmentation serving, Orion contributes a concrete mechanism to turn “one-shot CNN inference” into a stream of schedulable operator units suitable for multi-tenant co-location.

(b) Infrastructure & Hardware Assumptions

Orion targets NVIDIA CUDA GPUs and integrates with PyTorch, positioning itself as a transparent interposition layer that observes kernel launches and enforces a scheduling policy across clients. Orion’s evaluation emphasizes mixed-priority collocation (latency-sensitive inference with best-effort inference, and inference with training), assuming multiple concurrent GPU clients and a need for tail-latency protection.

(c) Core Optimizations & Algorithmic Design

Orion’s core optimization is **operator-level scheduling** that uses operator characteristics (size and whether compute- vs memory-bound) and job priority to choose what to run concurrently. This avoids head-of-line blocking from request-level time slicing and aims to exploit “gaps” where one job underutilizes either compute units or memory bandwidth.

(d) Memory & Cache Management

Orion is primarily a compute/bandwidth scheduler rather than a cache manager: it reasons about operator resource requirements to reduce interference and improve utilization but does not introduce a new paging/eviction subsystem. For one-shot segmentation, this means Orion can mitigate *interference-induced latency* via better co-scheduling, but tight VRAM caps must be handled via external admission control or explicit memory budgeting.

(e) Request Scheduling & Batching

Orion effectively replaces coarse request-level time slicing with **fine-grained operator scheduling**, allowing a high-priority inference request stream to interleave with best-effort inference/training operators in the short idle windows that naturally occur within DNN execution. Orion does not require batching for the high-priority job; best-effort work is opportunistic.

(f) Session & State Management

**N/A by design for one-shot CV inference**: per-request segmentation state (activations) is ephemeral and local to the framework runtime. Orion’s persistent “state” is scheduler-side: per-client queues, operator profiles/classification, and policy parameters.

(g) Hardware Parallelization & Resource Allocation

Orion focuses on **single-GPU sharing** across clients via fine-grained kernel scheduling; it does not require multi-GPU parallelism for a single request. It implicitly assumes the GPU is shared (e.g., via standard CUDA multi-process execution) and Orion acts as the mediator at kernel-launch time.

vRAN Edge Viability (ComputeLease) + ComputeLease Scorecard:

Orion aligns well with ComputeLease’s micro-window idea because its native scheduling unit (operator/kernel) is already in the **10s–1000s of µs** range. However, Orion cannot preempt *within* a running kernel; safe interruption is at kernel boundaries.

**Adaptation hypothesis (AH-ORION-LEASE-GUARDRAIL)**: Add a lease guardrail that (i) forbids launching kernels whose predicted runtime would exceed remaining `duration_us` (given `sm_budget_sms`) and (ii) forces quiesce when `preemption_notice_us` is reached. This uses Orion’s operator-level visibility but requires additional prediction/guard logic.

ComputeLease Scorecard:

| Axis | Score (High/Med/Low) | Evidence (Direct/Inferred) | Notes (boundary/unit/state/VRAM mechanism) | ComputeLease fields referenced |
| :--- | :--- | :--- | :--- | :--- |
| Preemption Resilience | Medium | Direct+Inferred | Direct: operator-level scheduling; inferred: cooperative quiesce at kernel boundaries before lease end (AH-ORION-LEASE-GUARDRAIL). | `preemption_notice_us`, `duration_us`, `reclaim_mode` |
| Micro-Segmentation | High | Direct | Minimum unit is operator/kernel (10s–1000s of µs in Orion’s framing). | `duration_us`, `sm_budget_sms`, `start_time_us` |
| State Parking | High | Direct | One-shot inference is stateless across requests; scheduler-side state is small metadata. | `reclaim_mode`, `bandwidth_budget_hint` |
| Tight VRAM Compliance (≤60% stress) | Medium | Inferred | Orion does not introduce a VRAM budgeter; requires admission control keyed to `vram_budget_bytes`. | `vram_budget_bytes` |

[R2]

#### PPipe

Paper Type: `Serving Runtime`

(a) High-Level Architecture & System Design

PPipe is a DNN serving system for heterogeneous GPU clusters that uses **pool-based pipeline parallelism**: a model is partitioned into stages, and each stage is executed by a *pool* of GPUs of the same type; requests traverse pools stage-by-stage. PPipe separates a **control plane** (MILP-based planning of partition points, GPU allocation, and batch sizes) from a **data plane** that handles real-world dynamics (bursty arrivals, inter-stage queueing, network contention) via resource-reservation-based adaptive batching.

For M1 segmentation serving, the direct mapping is again frame-level serving: segmentation inference can be pipelined across heterogeneous GPU pools for throughput, but it is not inherently designed for microsecond-scale lease fragmentation.

(b) Infrastructure & Hardware Assumptions

PPipe assumes a heterogeneous GPU cluster with measurable interconnect bandwidth between servers/GPUs. It relies on offline profiling (per-layer/per-block latency under different batch sizes and GPU types, e.g., from TensorRT profiling outputs) and assumes that model weights can be preloaded asynchronously. The paper explicitly notes that many CNNs in EVA pipelines are typically not memory constrained on datacenter GPUs, and its baseline MILP formulation does not model GPU memory.

(c) Core Optimizations & Algorithmic Design

- **MILP planning**: jointly selects partition points, GPU pool sizes, and batch sizes to maximize throughput (or alternative objectives such as cost), subject to an end-to-end latency SLO.
- **Pre-partitioning**: groups hundreds of layers into a smaller number of blocks to reduce MILP search space and runtime.
- **Batch-size unification with vGPUs**: introduces a notion of virtual GPUs (via MPS) so the planner can keep a unified batch size across partitions while matching throughput across heterogeneous pools.
- **Data-plane adaptive batching + reservation**: addresses asynchronous/bursty arrival and network contention by selecting the next pipeline path and batch size that meets SLO under current availability.

(d) Memory & Cache Management

PPipe is explicit about **feature-map transfer costs** between partitions (network contention is a key challenge) and uses weight preloading to reduce migration downtime. However, the baseline formulation does not treat GPU memory as a binding constraint for vision models; for strict VRAM ceilings (ComputeLease), PPipe’s memory controls are not the main focus.

(e) Request Scheduling & Batching

PPipe’s data plane batches incoming requests and routes each batch through a planned pooled pipeline, adapting batch sizes to handle (i) batch formation delay and (ii) inter-partition queueing delay. This is effective for throughput-oriented serving under ms-to-100ms SLOs, but the minimum unit is still “batch through a stage/block,” not a microsecond-scale operator slice.

(f) Session & State Management

**N/A by design for one-shot CV inference**: the stable state is (i) the deployed partition plan, (ii) cached/profiling metadata, and (iii) the loaded weights for each partition on each GPU pool. Per-request state is limited to in-flight feature maps between partitions.

(g) Hardware Parallelization & Resource Allocation

PPipe’s core mechanism is **pipeline parallelism across GPU pools** plus **virtual GPUs via MPS** for finer resource partitioning within a physical GPU. Resource allocation is computed by the control plane (MILP) and enacted by the data plane through reservation and dispatch.

vRAN Edge Viability (ComputeLease) + ComputeLease Scorecard:

ComputeLease primarily changes PPipe’s feasibility: bursty micro-leases conflict with PPipe’s assumption of relatively stable GPU availability during a batch’s traversal through pipeline stages.

**Adaptation hypothesis (AH-PPIPE-LEASE-BLOCKS)**: Use PPipe’s pre-partitioned blocks as the micro-segmentation unit and schedule *block-execution slices* only when `duration_us`/`sm_budget_sms` suffice; otherwise defer execution and park in-flight feature maps to host memory under `reclaim_mode=hard`. This requires adding explicit activation/feature-map parking semantics.

ComputeLease Scorecard:

| Axis | Score (High/Med/Low) | Evidence (Direct/Inferred) | Notes (boundary/unit/state/VRAM mechanism) | ComputeLease fields referenced |
| :--- | :--- | :--- | :--- | :--- |
| Preemption Resilience | Low | Inferred | Safe boundary is between batches or after draining a stage; mid-batch interruption implies replay/partial loss. | `preemption_notice_us`, `reclaim_mode`, `duration_us` |
| Micro-Segmentation | Medium | Direct+Inferred | Direct: blocks/stages exist; inferred: sub-ms slicing of blocks is AH-PPIPE-LEASE-BLOCKS. | `duration_us`, `sm_budget_sms` |
| State Parking | Medium | Inferred | In-flight feature maps + partition-local weights; parking/resume across 0% SM gaps not a direct design point. | `reclaim_mode`, `bandwidth_budget_hint`, `vram_budget_bytes` |
| Tight VRAM Compliance (≤60% stress) | Low | Direct | Paper states CNN serving typically not memory constrained and MILP does not account for GPU memory (baseline). | `vram_budget_bytes` |

[R3]

#### RAVAS

Paper Type: `Resource Manager`

(a) High-Level Architecture & System Design

RAVAS is an edge video analytics system that tackles variable workload and co-location interference by combining (i) **model selection** (choose a lightweight model meeting an accuracy target) with (ii) **interference-aware resource allocation** via controlled spatial sharing of GPU compute capacity (GPU% / SM allocation). Its architecture includes streamers (per-feed ingestion/inference), a manager (model selection + resource allocation), a profiler (throughput vs GPU% curves), and monitoring/telemetry.

For M1 segmentation, RAVAS is best treated as resource-manager evidence: it shows how to pick among multiple candidate models/configs and allocate GPU compute shares under deadlines, but it is not a segmentation-specific runtime.

(b) Infrastructure & Hardware Assumptions

RAVAS assumes an edge server GPU shared among multiple concurrent inference workloads (video feeds) where interference is a primary issue. It uses **spatial multiplexing** (GPU% / SM allocation) to co-run models and relies on profiling to understand throughput under different GPU% allocations.

(c) Core Optimizations & Algorithmic Design

- **RL-based model selection** (off-policy Q-learning): selects the lightest model that meets an accuracy constraint relative to a base (most accurate) model.
- **Interference-aware allocation**: assigns GPU% to individual models to prevent oversubscription and reduce inference interference, informed by profiler measurements.
- **Group assignment**: assigns models to camera groups with similar temporal characteristics to reduce interference.

(d) Memory & Cache Management

RAVAS’s primary resource-control lever is compute (GPU%/SM share), not cache/memory. Its reported interference model is focused on throughput/latency under co-execution; VRAM-bound behavior and explicit cache controls are not central.

(e) Request Scheduling & Batching

RAVAS schedules at the granularity of frames/feeds: each frame is processed by an assigned model instance subject to a latency target (e.g., “process each frame within 100 ms” in its problem statement). The system’s “scheduling” is dominated by selecting which model to run and how much GPU% it receives, rather than micro-batch formation within a single model.

(f) Session & State Management

**N/A by design for one-shot CV inference**: per-frame inference is stateless across frames in the model-execution sense (beyond any streaming pipeline bookkeeping). Persistent state is the RL policy/Q-table (or learned parameters), profiling history, and telemetry.

(g) Hardware Parallelization & Resource Allocation

RAVAS’s hardware allocation is explicit: allocate a **percentage of GPU compute (GPU% / SM count)** to each model/application to enable controlled spatial sharing and reduce oversubscription/interference.

vRAN Edge Viability (ComputeLease) + ComputeLease Scorecard:

ComputeLease maps naturally to RAVAS’s GPU%-based allocation: `sm_budget_sms` can be treated as the coarse resource envelope for concurrent model instances. What is missing is fine-grained within-request segmentation; RAVAS operates at frame boundaries.

**Adaptation hypothesis (AH-RAVAS-LEASE-SM-MAP)**: Replace “GPU%” with lease-provided `sm_budget_sms` and gate decisions on `duration_us` (admit only as many concurrent requests/instances as can complete within the lease), while using `vram_budget_bytes` as a hard cap for which models/configs are admissible.

ComputeLease Scorecard:

| Axis | Score (High/Med/Low) | Evidence (Direct/Inferred) | Notes (boundary/unit/state/VRAM mechanism) | ComputeLease fields referenced |
| :--- | :--- | :--- | :--- | :--- |
| Preemption Resilience | Medium | Direct | Safe boundary is per-frame/per-request; stop between frames without corrupting state. | `preemption_notice_us`, `reclaim_mode` |
| Micro-Segmentation | Medium | Direct | Unit is a frame/request (100ms-level deadlines in paper); not operator-level. | `duration_us` |
| State Parking | High | Direct | Minimal persistent runtime state beyond policy/profiles; one-shot inference state is ephemeral. | `reclaim_mode`, `bandwidth_budget_hint` |
| Tight VRAM Compliance (≤60% stress) | Medium | Inferred | Memory controls not central; strict `vram_budget_bytes` admission requires added policy (AH-RAVAS-LEASE-SM-MAP). | `vram_budget_bytes` |

[R4]

#### OctopInf

Paper Type: `Serving Runtime`

(a) High-Level Architecture & System Design

OctopInf targets edge video analytics (EVA) pipelines and introduces a containerized serving platform with two key runtime mechanisms: **CWD** (Cross-device Workload Distributor) to choose placements/batch sizes/instance counts under workload/network/device profiles, and **CORAL** (Co-location Inference Spatiotemporal Scheduler) to co-schedule model instances on GPUs using a stream-based spatiotemporal abstraction. A knowledge base stores telemetry and profiles used for periodic scheduling and runtime adaptation.

For M1 segmentation, OctopInf’s value is as an EVA-style serving runtime that already includes (i) explicit multi-model/container orchestration and (ii) a scheduler that reasons about time+space resource constraints.

(b) Infrastructure & Hardware Assumptions

OctopInf assumes a heterogeneous edge environment (edge devices + an edge server), containerized deployment, and inference engines such as TensorRT/OpenVINO/ONNX execution backends. It explicitly models network variability and uses device/model/network profiles to guide workload distribution.

(c) Core Optimizations & Algorithmic Design

- **CWD (workload distribution)**: explores configurations (batch size, placement, number of instances) guided by insights about burstiness, network bottlenecks, and limiting split points.
- **CORAL (spatiotemporal scheduling)**: introduces an “inference stream” abstraction; schedules each model execution as a **portion** with a time length and a compute-capability width, placing portions into available free portions while satisfying compute+memory sufficiency and duty-cycle (SLO) constraints.
- **Horizontal autoscaling**: complements periodic scheduling with quicker responses to workload surges/dips.

(d) Memory & Cache Management

CORAL’s placement test explicitly checks memory sufficiency (conceptually: weights + intermediate tensors must fit within available GPU memory) when assigning an execution portion to a GPU stream. OctopInf does not propose a new cache structure for a single model, but it does incorporate memory feasibility into its multi-model scheduling decision.

(e) Request Scheduling & Batching

OctopInf treats inference as pipeline serving under SLOs and uses batch-size selection (via CWD) plus spatiotemporal co-location scheduling (via CORAL) to reduce interference and keep end-to-end latency within SLO. The scheduling granularity is model-instance “portions” (batch execution slices) arranged according to pipeline DAG order.

(f) Session & State Management

**N/A by design for one-shot CV inference**: per-request state is transient. Persistent system state is the knowledge base of profiles/telemetry, configured pipeline deployments, and container-instance metadata.

(g) Hardware Parallelization & Resource Allocation

OctopInf’s resource allocation is multi-dimensional: it selects (i) how many container instances to run per model, (ii) where to run them (edge vs server), and (iii) how to co-locate them on GPUs via CORAL’s stream/portion abstraction, subject to compute and memory constraints.

vRAN Edge Viability (ComputeLease) + ComputeLease Scorecard:

ComputeLease is close in spirit to OctopInf’s spatiotemporal scheduler: CORAL already reasons over “time portions” and resource sufficiency. The main gap is that CORAL’s portion durations are tied to batch inference profiles (often ms-scale), while ComputeLease may be sub-ms.

**Adaptation hypothesis (AH-OCTOPINF-LEASE-PORTIONS)**: Refine CORAL’s portion abstraction to target sub-ms leases by (i) lowering the minimum executable unit from “batch execution” to “operator-group” (or “tile”) and (ii) constraining portion placement by remaining lease time (`duration_us`) and compute envelope (`sm_budget_sms`). This requires integrating operator/tile profiling into the knowledge base.

ComputeLease Scorecard:

| Axis | Score (High/Med/Low) | Evidence (Direct/Inferred) | Notes (boundary/unit/state/VRAM mechanism) | ComputeLease fields referenced |
| :--- | :--- | :--- | :--- | :--- |
| Preemption Resilience | Medium | Inferred | Natural boundary is between scheduled portions; hard reclaim mid-portion would require replay. | `preemption_notice_us`, `reclaim_mode`, `duration_us` |
| Micro-Segmentation | Medium | Direct+Inferred | Direct: portion abstraction exists; inferred: sub-ms portions require new profiling/unit (AH-OCTOPINF-LEASE-PORTIONS). | `duration_us`, `sm_budget_sms`, `start_time_us` |
| State Parking | Medium | Inferred | In-flight pipeline data + container state; explicit 0% SM parking/restart not a primary goal. | `reclaim_mode`, `bandwidth_budget_hint` |
| Tight VRAM Compliance (≤60% stress) | High | Direct | CORAL checks memory sufficiency when placing portions (weights + intermediates) against GPU capacity. | `vram_budget_bytes` |

[R5]

##### What transfers to vRAN edge inference container (M1)

- Operator-level (kernel-boundary) scheduling as a first-class micro-segmentation strategy (Orion).
- Interference-aware co-location with explicit modeling of compute vs memory utilization (USHER) plus optional graph-level cache-interference mitigation.
- Planning + runtime split: offline/periodic planning with a fast online data plane to handle bursty arrivals (PPipe, OctopInf).
- Compute-share control surfaces that map naturally onto `sm_budget_sms` (RAVAS GPU% allocation; PPipe/OctopInf virtualized GPU notions).

---

## M2 Pose Estimation (Transformer/CNN Hybrid)

Primary systems considered: USHER, Orion, PPipe, RAVAS, OctopInf

#### USHER

Paper Type: `Serving Runtime`

(a) High-Level Architecture & System Design

USHER is an end-to-end inference serving system for **interference-aware GPU sharing** across multiple DL models while meeting latency SLOs. It combines (1) a kernel-analysis based estimator (GK-Estimator), (2) a heuristic scheduler (IR-Scheduler) that selects batch size, replication degree, and placement, and (3) an operator-graph merger (OG-Merger) to reduce cache interference by merging sufficiently similar operator graphs.

For M2 pose estimation (hybrid CNN/Transformer), the workload is still “one-shot CV inference” at the request level; USHER applies as serving-runtime evidence for consolidating multi-model, latency-constrained inference under interference.

(b) Infrastructure & Hardware Assumptions

USHER assumes NVIDIA GPUs and leverages GPU sharing mechanisms such as MPS (and discusses MIG as a more rigid alternative). It relies on operator graphs (via ONNX for framework-independent representation) and kernel-level profiling/analysis to map operators to kernels and estimate resource needs.

(c) Core Optimizations & Algorithmic Design

- **GK-Estimator** estimates compute/memory requirements by aggregating requirements across sets of concurrently executing kernels.
- **IR-Scheduler** uses a heuristic grouping+placement strategy to co-locate compute-heavy and memory-heavy models and choose batch size/replication/placement under SLO constraints.
- **OG-Merger** merges operator graphs to reduce cache interference when models/operators are sufficiently similar.

(d) Memory & Cache Management

USHER explicitly targets joint compute+memory utilization and attributes goodput losses to interference, including cache interference. OG-Merger is its main cache-related mechanism (merging graphs to increase cache-content reuse), while the scheduler controls placement decisions based on estimated memory footprint.

For pose estimation, intermediate activations are per-request (not persistent); USHER’s direct control point is at the level of co-located models and their combined footprints.

(e) Request Scheduling & Batching

USHER schedules by selecting **batch size**, **replication degree**, and **placement** to satisfy latency SLOs and maximize goodput/cost-efficiency under interference. The mapping for pose estimation is again frame-level serving: batching can be used when SLO allows, while placement decisions should account for combined compute+memory behavior.

(f) Session & State Management

**N/A by design for one-shot CV inference**: pose estimation requests are stateless across requests. Persistent state is the model weights/graphs and scheduler/merger metadata (e.g., profiles/estimates).

(g) Hardware Parallelization & Resource Allocation

USHER’s primary hardware mechanism is **spatial multiplexing** on a GPU (e.g., via MPS) combined with cluster-level placement/replication decisions to meet SLOs while improving utilization.

vRAN Edge Viability (ComputeLease) + ComputeLease Scorecard:

USHER provides strong *resource estimation + interference-aware placement* building blocks, but does not directly implement lease-aligned preemption or sub-ms execution chunking for a single pose-estimation request.

**Adaptation hypothesis (AH-USHER-LEASE-OPGROUP-M2)**: Use USHER’s operator/kernels requirement estimates to select an **operator-group** boundary that fits `duration_us`/`sm_budget_sms`, and add a cooperative quiesce protocol keyed to `preemption_notice_us`/`reclaim_mode`.

ComputeLease Scorecard:

| Axis | Score (High/Med/Low) | Evidence (Direct/Inferred) | Notes (boundary/unit/state/VRAM mechanism) | ComputeLease fields referenced |
| :--- | :--- | :--- | :--- | :--- |
| Preemption Resilience | Medium | Inferred | Safe boundary is per-request/per-batch; no explicit lease-driven quiesce in USHER. | `preemption_notice_us`, `reclaim_mode`, `duration_us` |
| Micro-Segmentation | Low | Inferred | USHER optimizes batching/placement, not sub-ms operator chunking; operator-group chunking is AH-USHER-LEASE-OPGROUP-M2. | `duration_us`, `sm_budget_sms` |
| State Parking | Medium | Inferred | Requests stateless; main parked state is weights/metadata if hard reclaim forces VRAM eviction. | `reclaim_mode`, `vram_budget_bytes`, `bandwidth_budget_hint` |
| Tight VRAM Compliance (≤60% stress) | Medium | Direct+Inferred | Direct: explicit modeling of memory utilization/interference; inferred: hard VRAM cap requires lease-aware admission keyed to `vram_budget_bytes`. | `vram_budget_bytes` |

[R1]

#### Orion

Paper Type: `Resource Manager`

(a) High-Level Architecture & System Design

Orion is a fine-grained GPU sharing system that **intercepts GPU kernel launches** from multiple clients and schedules at the granularity of individual operators/kernels to minimize interference while improving utilization. It targets operator durations in the **10s–1000s of µs** regime and uses operator characteristics (compute- vs memory-bound, size) and job priority to decide concurrency.

For M2 pose estimation, Orion’s operator-level scheduling is directly relevant: hybrid CNN/Transformer models exhibit operator heterogeneity (e.g., attention and convolution operators) and can benefit from interference-aware co-scheduling.

(b) Infrastructure & Hardware Assumptions

Orion assumes NVIDIA CUDA GPUs and integrates with PyTorch as a transparent interposition layer mediating kernel launches from multiple clients. It assumes concurrent clients with mixed priorities and aims to protect tail latency for high-priority inference while using best-effort work to fill utilization gaps.

(c) Core Optimizations & Algorithmic Design

The key optimization is **operator-level interference-aware scheduling**: avoid request-level head-of-line blocking and exploit complementary resource usage (compute vs memory bandwidth) by selecting which operator from which client to run concurrently.

(d) Memory & Cache Management

Orion is primarily a compute/bandwidth scheduler; it does not introduce a dedicated VRAM paging/eviction subsystem. Under ComputeLease-like VRAM caps, pose-estimation serving still needs explicit admission/memory budgeting outside Orion.

(e) Request Scheduling & Batching

Orion effectively schedules *within* inference execution by interleaving operators from different clients based on priority and operator characteristics. It reduces reliance on batching for the high-priority job; best-effort work is opportunistic.

(f) Session & State Management

**N/A by design for one-shot CV inference**: per-request activations are ephemeral; persistent state is scheduler metadata (queues, operator classification/profiles).

(g) Hardware Parallelization & Resource Allocation

Orion focuses on fine-grained **single-GPU sharing** across clients at kernel-launch granularity.

vRAN Edge Viability (ComputeLease) + ComputeLease Scorecard:

Orion’s operator-level unit is already close to the ComputeLease micro-window abstraction. The key limitation is that kernels cannot be preempted mid-flight; safe interruption is at kernel boundaries.

**Adaptation hypothesis (AH-ORION-LEASE-GUARDRAIL-M2)**: Add lease-aware guards that prevent launching kernels predicted to exceed remaining `duration_us` (given `sm_budget_sms`) and force quiesce on `preemption_notice_us`.

ComputeLease Scorecard:

| Axis | Score (High/Med/Low) | Evidence (Direct/Inferred) | Notes (boundary/unit/state/VRAM mechanism) | ComputeLease fields referenced |
| :--- | :--- | :--- | :--- | :--- |
| Preemption Resilience | Medium | Direct+Inferred | Direct: operator-level scheduling; inferred: lease-driven quiesce at kernel boundaries (AH-ORION-LEASE-GUARDRAIL-M2). | `preemption_notice_us`, `duration_us`, `reclaim_mode` |
| Micro-Segmentation | High | Direct | Minimum unit is operator/kernel (10s–1000s of µs). | `duration_us`, `sm_budget_sms`, `start_time_us` |
| State Parking | High | Direct | One-shot requests stateless; scheduler-side state is compact. | `reclaim_mode`, `bandwidth_budget_hint` |
| Tight VRAM Compliance (≤60% stress) | Medium | Inferred | Requires explicit admission control keyed to `vram_budget_bytes`. | `vram_budget_bytes` |

[R2]

#### PPipe

Paper Type: `Serving Runtime`

(a) High-Level Architecture & System Design

PPipe is a DNN serving system for heterogeneous GPU clusters using **pool-based pipeline parallelism** with a control plane (MILP-based planning of partitions/GPU allocation/batch sizes) and a data plane (resource reservation + adaptive batching) to handle bursty arrivals and network contention.

For M2 pose estimation, PPipe maps at the level of frame/request serving throughput; it is not designed around microsecond-scale lease fragmentation.

(b) Infrastructure & Hardware Assumptions

PPipe assumes a heterogeneous GPU cluster and relies on offline profiling (per-layer/per-block latency and feature-map transfer costs, e.g., using TensorRT-derived profiles). The baseline planner does not account for GPU memory for CNN-heavy EVA workloads and assumes weights can be preloaded asynchronously.

(c) Core Optimizations & Algorithmic Design

MILP planning + pre-partitioning (block grouping) + batch-size unification using MPS-backed virtual GPUs, plus a runtime data plane for adaptive batching/reservation.

(d) Memory & Cache Management

PPipe treats feature-map transfer and network contention as key performance constraints, but explicitly de-emphasizes VRAM as a primary limiter for its vision workloads; strict VRAM-capped edge leases therefore require additional admission/memory controls.

(e) Request Scheduling & Batching

PPipe batches requests and routes them through pipeline stages/pools, dynamically adjusting to avoid SLO violations under bursty arrivals and inter-stage queuing. Minimum unit remains “batch through a stage/block.”

(f) Session & State Management

**N/A by design for one-shot CV inference**: stable state is the partition plan + profiling metadata + partition-local weights; per-request state is in-flight feature maps.

(g) Hardware Parallelization & Resource Allocation

Pipeline parallelism across GPU pools plus MPS-based virtual GPUs to shape effective GPU “sizes” for unified batching.

vRAN Edge Viability (ComputeLease) + ComputeLease Scorecard:

ComputeLease’s bursty micro-windows challenge PPipe because a batch’s traversal through pipeline stages assumes continuity. The primary direct transfer is the control-plane/data-plane split and block-based profiling.

**Adaptation hypothesis (AH-PPIPE-LEASE-BLOCKS-M2)**: Treat PPipe’s pre-partitioned blocks as segmentation units and dispatch only when remaining `duration_us`/`sm_budget_sms` are sufficient, parking in-flight feature maps when `reclaim_mode=hard`.

ComputeLease Scorecard:

| Axis | Score (High/Med/Low) | Evidence (Direct/Inferred) | Notes (boundary/unit/state/VRAM mechanism) | ComputeLease fields referenced |
| :--- | :--- | :--- | :--- | :--- |
| Preemption Resilience | Low | Inferred | Safe boundary is between batches or after draining a stage. | `preemption_notice_us`, `reclaim_mode`, `duration_us` |
| Micro-Segmentation | Medium | Direct+Inferred | Direct: blocks/stages exist; inferred: sub-ms slicing is AH-PPIPE-LEASE-BLOCKS-M2. | `duration_us`, `sm_budget_sms` |
| State Parking | Medium | Inferred | In-flight feature maps + partition weights; explicit 0% SM parking not core. | `reclaim_mode`, `bandwidth_budget_hint`, `vram_budget_bytes` |
| Tight VRAM Compliance (≤60% stress) | Low | Direct | Baseline planning does not model GPU memory for vision workloads. | `vram_budget_bytes` |

[R3]

#### RAVAS

Paper Type: `Resource Manager`

(a) High-Level Architecture & System Design

RAVAS is an edge analytics system that combines **RL-based model selection** with **interference-aware GPU compute-share allocation (GPU% / SM allocation)**. It is modular (streamers, manager, profiler, monitoring) and aims to meet per-frame latency deadlines while maintaining an accuracy target.

For M2 pose estimation, RAVAS transfers as a resource-manager pattern for selecting among multiple candidate pose models/configs and allocating compute shares under interference.

(b) Infrastructure & Hardware Assumptions

RAVAS assumes an edge GPU shared among concurrent inference workloads where co-location interference impacts latency/throughput. It uses spatial multiplexing (GPU%) plus profiling for throughput under different compute shares.

(c) Core Optimizations & Algorithmic Design

Off-policy Q-learning model selection + dependent (interference-aware) compute-share allocation, informed by profiler data.

(d) Memory & Cache Management

RAVAS’s main lever is compute-share control; explicit VRAM/caching strategies are not central.

(e) Request Scheduling & Batching

Scheduling operates at per-frame/per-request granularity: choose which model runs for which feed and allocate GPU% so deadlines are met under interference.

(f) Session & State Management

**N/A by design for one-shot CV inference**: persistent state is policy/profiles/telemetry; per-request inference state is transient.

(g) Hardware Parallelization & Resource Allocation

Explicit spatial sharing via GPU% (SM allocation) to each model/application.

vRAN Edge Viability (ComputeLease) + ComputeLease Scorecard:

ComputeLease maps naturally to RAVAS’s compute-share framing: `sm_budget_sms` can replace GPU% as the scheduling envelope. Fine-grained micro-segmentation remains at the frame boundary.

**Adaptation hypothesis (AH-RAVAS-LEASE-SM-MAP-M2)**: Gate model selection and concurrent instance counts on `duration_us` and enforce a hard `vram_budget_bytes` admissibility rule for pose models.

ComputeLease Scorecard:

| Axis | Score (High/Med/Low) | Evidence (Direct/Inferred) | Notes (boundary/unit/state/VRAM mechanism) | ComputeLease fields referenced |
| :--- | :--- | :--- | :--- | :--- |
| Preemption Resilience | Medium | Direct | Stop between frames/requests; mid-request interruption not required. | `preemption_notice_us`, `reclaim_mode` |
| Micro-Segmentation | Medium | Direct | Unit is frame/request (deadline-scale). | `duration_us` |
| State Parking | High | Direct | Minimal persistent runtime state (policy/profiles). | `reclaim_mode`, `bandwidth_budget_hint` |
| Tight VRAM Compliance (≤60% stress) | Medium | Inferred | Requires explicit `vram_budget_bytes`-aware admission (AH-RAVAS-LEASE-SM-MAP-M2). | `vram_budget_bytes` |

[R4]

#### OctopInf

Paper Type: `Serving Runtime`

(a) High-Level Architecture & System Design

OctopInf is a containerized serving runtime for EVA pipelines with a periodic planner (**CWD**) and a spatiotemporal GPU co-location scheduler (**CORAL**) built on an “inference stream / portion” abstraction. It uses a knowledge base of telemetry/profiles and adds a horizontal autoscaler for runtime workload shifts.

For M2 pose estimation, OctopInf transfers primarily as a “pipeline scheduling + co-location” pattern even if the pipeline collapses to a single model stage.

(b) Infrastructure & Hardware Assumptions

Assumes edge devices + an edge server, containerized deployment, and inference engines (e.g., TensorRT/OpenVINO/ONNX), with explicit modeling of network variability and device/model profiles.

(c) Core Optimizations & Algorithmic Design

CWD explores batch size/placement/instance-count configurations under burstiness/network constraints; CORAL schedules model instances into free spatiotemporal portions while checking compute and memory sufficiency and preserving duty-cycle (SLO) constraints.

(d) Memory & Cache Management

CORAL includes an explicit memory sufficiency check when placing portions (weights + intermediate memory must fit). OctopInf is not a per-model paging system, but it is memory-aware at the multi-model scheduler level.

(e) Request Scheduling & Batching

Uses batch-size selection (CWD) and spatiotemporal co-location scheduling (CORAL) to mitigate interference and meet end-to-end SLOs; granularity is batch-execution “portions” arranged by pipeline DAG order.

(f) Session & State Management

**N/A by design for one-shot CV inference**: per-request state is transient; persistent state is profiles/telemetry + deployment metadata.

(g) Hardware Parallelization & Resource Allocation

Allocates resources via instance scaling + placement (edge vs server) + GPU stream/portion packing with compute+memory feasibility checks.

vRAN Edge Viability (ComputeLease) + ComputeLease Scorecard:

OctopInf is conceptually close to ComputeLease because CORAL schedules over time/space portions with memory constraints. The gap is that portion sizes are tied to batch inference profiles (often ms-scale), whereas ComputeLease may be sub-ms.

**Adaptation hypothesis (AH-OCTOPINF-LEASE-PORTIONS-M2)**: Extend CORAL’s portion abstraction with sub-ms units (operator-group or tile) and constrain placement by remaining `duration_us` and `sm_budget_sms`, requiring additional fine-grained profiling in the knowledge base.

ComputeLease Scorecard:

| Axis | Score (High/Med/Low) | Evidence (Direct/Inferred) | Notes (boundary/unit/state/VRAM mechanism) | ComputeLease fields referenced |
| :--- | :--- | :--- | :--- | :--- |
| Preemption Resilience | Medium | Inferred | Boundary between portions; hard reclaim mid-portion requires replay. | `preemption_notice_us`, `reclaim_mode`, `duration_us` |
| Micro-Segmentation | Medium | Direct+Inferred | Direct: portion abstraction exists; inferred: sub-ms portions require new unit (AH-OCTOPINF-LEASE-PORTIONS-M2). | `duration_us`, `sm_budget_sms`, `start_time_us` |
| State Parking | Medium | Inferred | In-flight pipeline data + container state; explicit 0% SM parking not core. | `reclaim_mode`, `bandwidth_budget_hint` |
| Tight VRAM Compliance (≤60% stress) | High | Direct | Memory sufficiency is checked during portion placement. | `vram_budget_bytes` |

[R5]

##### What transfers to vRAN edge inference container (M2)

- Operator-level scheduling for hybrid CNN/Transformer inference as a micro-segmentation primitive (Orion).
- Interference-aware consolidation driven by compute-vs-memory utilization modeling (USHER).
- Control-plane planning plus online data-plane adaptation for bursty arrivals (PPipe, OctopInf).
- A compute-share control surface that maps directly to `sm_budget_sms` (RAVAS GPU% → SM budget mapping).

---

## M3 Language Processing (Auto-regressive Transformer)

Primary systems considered: vLLM/PagedAttention, Orca, DistServe, SpotServe, CacheGen

#### vLLM/PagedAttention

Paper Type: `Serving Runtime | Resource Manager | Model Accelerator`

(a) High-Level Architecture & System Design

vLLM is a high-throughput LLM serving runtime built around **PagedAttention**, which virtualizes the attention key/value (KV) cache as **logical KV blocks** mapped onto **physical KV blocks** (GPU memory). The runtime includes (i) a centralized scheduler, (ii) a KV block manager (GPU block allocator + CPU block allocator), and (iii) an attention implementation that consumes per-sequence “block tables” to locate non-contiguous KV pages.

The key architectural outcome is that requests/sequences can be admitted and progressed without requiring contiguous KV allocation; this enables high utilization under variable prompt lengths and generation lengths.

(b) Infrastructure & Hardware Assumptions

vLLM targets NVIDIA-style GPUs with high-bandwidth device memory and assumes the serving stack can manage GPU memory explicitly. For preemption recovery, vLLM explicitly relies on **CPU RAM as swap space** (CPU block allocator) and on the ability to **recompute KV** by re-running a prompt phase (i.e., recomputation is feasible because generated tokens can be concatenated with the original prompt). It also supports distributed execution via tensor model parallelism.

(c) Core Optimizations & Algorithmic Design

The core contribution is **PagedAttention**: KV cache pages can be stored non-contiguously and accessed via an indirection layer. vLLM further exploits LLM-specific semantics to reduce KV movement through:

- **Physical block sharing** across decoding branches (e.g., beam search) with copy-on-write (CoW) at the block level.
- **Shared-prefix caching** by reserving physical blocks for common prefixes and mapping logical blocks onto those cached blocks (last block marked CoW).

These mechanisms increase batching opportunities and reduce fragmentation-induced headroom loss.

(d) Memory & Cache Management

vLLM’s memory manager uses an **all-or-nothing eviction policy** at the granularity of a sequence: because a sequence’s blocks are accessed together, either all blocks for a sequence are evicted or none are. Multi-sequence requests (e.g., beam candidates) are gang-scheduled as a **sequence group** and are preempted/rescheduled together due to block sharing.

For recovery after eviction, vLLM considers two explicit mechanisms:

- **Swapping**: evicted KV blocks are copied to **CPU memory (CPU RAM swap)**, bounded such that CPU swap usage does not exceed the total GPU KV blocks allocated for the KV cache.
- **Recomputation**: KV cache is regenerated when a preempted sequence is rescheduled; recomputation can be cheaper than original decode because the already-generated tokens are concatenated into a new prompt, enabling prompt-phase parallelism.

vLLM also chooses a practical **block size** (default 16 tokens) to trade off internal fragmentation and paging overhead.

(e) Request Scheduling & Batching

vLLM adopts **FCFS** for fairness and preempts latest-arrived requests first when capacity is exceeded. Under memory pressure (insufficient free KV blocks), vLLM preempts sequence groups and triggers eviction; in the swap-based design described, vLLM may pause acceptance of new requests while completing preempted sequences (a conservative policy that prioritizes correctness and bounded swap).

Batching is enabled by the increased KV efficiency (more concurrent sequences fit) and by hiding diverse decoding policies behind the logical→physical mapping.

(f) Session & State Management

The dominant long-lived session state in auto-regressive serving is the **per-sequence KV cache**. vLLM makes this explicit and provides a concrete park/resume story: when a sequence group is preempted, its KV blocks can be **parked to CPU RAM** (swap) and later **brought back**; alternatively, the KV can be discarded and **recomputed** from text.

This is a direct blueprint for “state parking” under ComputeLease: the KV cache is the “session state” to park, and recovery is either (i) bandwidth-bound swap-in or (ii) compute-bound recomputation.

(g) Hardware Parallelization & Resource Allocation

vLLM supports tensor model parallelism and relies on the KV block manager to allocate device memory across concurrent sequences. The “resource allocation” surface is: (i) how much KV memory to reserve (a function of `vram_budget_bytes`), (ii) how many concurrent sequences/sequence groups to admit (admission control), and (iii) scheduler policies for prioritization and preemption.

vRAN Edge Viability (ComputeLease) + ComputeLease Scorecard:


vLLM is one of the closest “mechanism fits” to ComputeLease because it already treats KV cache as a pageable object with explicit **preemption + recovery** semantics. For vRAN edge, the key is to make the unit of cooperative pause align with (i) a **decode-step boundary** and (ii) an **eviction-safe sequence-group boundary**, using `preemption_notice_us` to trigger eviction/swap and `duration_us`/`sm_budget_sms` to cap per-lease decode work. Tight VRAM compliance is achieved by enforcing headroom in the KV block allocator: admission control caps total allocated KV blocks so that live KV remains ≤ `vram_budget_bytes`. For stress-testing, the report commonly sets

`vram_budget_bytes = 0.6 * physical_vram_bytes`

to represent the 60% stress target; the canonical comparison is always live usage versus `vram_budget_bytes`.

**Adaptation hypothesis (AH-VLLM-LEASE-HEADROOM):** vLLM provides block-level KV paging (swap/recompute) and FCFS+preemption. A vRAN-edge container would add a strict “KV headroom guard” that rejects or parks low-priority sequences when live KV exceeds `vram_budget_bytes` (configured as desired for stress) and uses `preemption_notice_us` to initiate swap-out before reclaim.

ComputeLease Scorecard:

| Axis | Score (High/Med/Low) | Evidence (Direct/Inferred) | Notes (boundary/unit/state/VRAM mechanism) | ComputeLease fields referenced |
| :--- | :--- | :--- | :--- | :--- |
| Preemption Resilience | High | Direct+Inferred | Direct: request preemption + eviction with recovery via swap-to-CPU-RAM or recomputation; inferred: bind preemption trigger to `preemption_notice_us`. Safe boundary: decode-step / sequence-group eviction point. | `preemption_notice_us`, `duration_us` |
| Micro-Segmentation | Medium | Inferred | vLLM schedules at request/sequence-group level; micro-segmentation for ComputeLease requires mapping decode work to small time windows (e.g., cap tokens/steps per lease). | `duration_us`, `sm_budget_sms` |
| State Parking | High | Direct | Direct: KV cache can be swapped to CPU memory or recomputed; sequence groups can be evicted and later resumed. | `preemption_notice_us`, `bandwidth_budget_hint` |
| Tight VRAM Compliance (≤60% stress) | High | Inferred | Direct: block allocator/eviction exists; inferred: enforce ≤60% live-KV headroom via admission control and early swap-out. | `vram_budget_bytes` |

[R10]

#### Orca

Paper Type: `Serving Runtime | Resource Manager | Model Accelerator`

(a) High-Level Architecture & System Design

Orca is an LLM serving engine that introduces **iteration-level scheduling** (token-iteration granularity) and “selective batching” to improve utilization when requests have different prompt/generation lengths. It couples a scheduler with an execution engine, and keeps per-request progress in a request pool while interleaving work across requests at iteration boundaries.

(b) Infrastructure & Hardware Assumptions

The paper evaluates on multi-GPU NVIDIA systems (e.g., A100-class GPUs) and assumes standard GPU execution where kernels are not preemptible mid-kernel. Orca includes a control plane (e.g., gRPC) and uses GPU collectives (e.g., NCCL) for inter/intra-layer parallelism.

(c) Core Optimizations & Algorithmic Design

Orca’s key idea is to schedule at the granularity of a **single iteration** rather than completing an entire request end-to-end before switching. The scheduler aims to preserve an “iteration-level FCFS” property and uses selective batching to choose which requests run in each iteration.

Critically, Orca incorporates a guard against memory deadlock: when considering a request in the initiation phase, it reserves capacity proportional to `max_tokens`.

(d) Memory & Cache Management

Orca makes KV cache memory explicit through an **Attention K/V manager**. To avoid deadlock when KV buffers cannot be reclaimed until a request completes, Orca uses a pre-allocation model based on **K/V slots**:

- `n_slots` denotes the total number of K/V slots available for KV cache storage.
- A “slot” is defined by the memory required to store the attention key and value for a **single token**.
- The scheduler tracks `n_rsrv` (currently reserved slots) and, at request initiation, reserves `req.max_tokens` slots if possible.

This provides deterministic admission under a fixed KV memory reservation.

(e) Request Scheduling & Batching

The scheduler selects at most `max_bs` requests based on arrival time while respecting the K/V slot reservation constraint. Orca pipelines execution across workers by keeping multiple batches in flight (up to `n_workers`), improving utilization without forcing microbatching.

(f) Session & State Management

The key session-like state is again the per-request KV cache maintained by the Attention K/V manager. However, Orca does not specify a paging/eviction-to-CPU mechanism analogous to vLLM’s swap/recompute design; the design primarily assumes KV remains resident within the pre-allocated GPU KV region.

(g) Hardware Parallelization & Resource Allocation

Orca supports pipelining across workers and uses inter-layer and intra-layer partitions for large models. The operator-tunable knob `n_slots` effectively defines the KV memory region size and thus controls how many (and how large) requests can be simultaneously in flight.

vRAN Edge Viability (ComputeLease) + ComputeLease Scorecard:

Orca’s iteration-level scheduling maps naturally onto **micro-segmentation**: an iteration boundary is a clean unit to bound work to a lease duration (`duration_us`) and compute budget (`sm_budget_sms`). The gaps for ComputeLease are (i) no explicit **state parking** protocol under reclaim, and (ii) preemption is effectively “stop scheduling at next iteration,” which still requires a place to park KV under a hard VRAM cap. Under a strict ≤60% VRAM stress regime, Orca’s `n_slots` admission control can be used as a static VRAM partition for KV, but the system still needs headroom and reclaim handling tied to `preemption_notice_us`.

**Adaptation hypothesis (AH-ORCA-LEASE-PARK):** Orca provides token-iteration scheduling and slot-based KV admission. A vRAN-edge container would add a parking backend for KV (CPU RAM swap or recomputation-from-text) and wire `preemption_notice_us` to “stop-at-next-iteration + park,” while enforcing that the KV region stays ≤`vram_budget_bytes` (60% stress is achieved by configuring `vram_budget_bytes = 0.6 * physical_vram_bytes`) by configuring `n_slots` plus a headroom margin.

ComputeLease Scorecard:

| Axis | Score (High/Med/Low) | Evidence (Direct/Inferred) | Notes (boundary/unit/state/VRAM mechanism) | ComputeLease fields referenced |
| :--- | :--- | :--- | :--- | :--- |
| Preemption Resilience | Medium | Inferred | Safe boundary: iteration boundary; hard reclaim requires parking KV. Orca does not define swap/recompute; added via AH-ORCA-LEASE-PARK. | `preemption_notice_us`, `duration_us` |
| Micro-Segmentation | High | Direct+Inferred | Direct: iteration-level scheduling exists; inferred: bind “max iterations per lease” to `duration_us` and `sm_budget_sms`. | `duration_us`, `sm_budget_sms` |
| State Parking | Low | Direct | Direct: KV manager retains KV until completion; no park/resume protocol described. | `reclaim_mode`, `bandwidth_budget_hint` |
| Tight VRAM Compliance (≤60% stress) | Medium | Direct+Inferred | Direct: `n_slots`/reservation gives a bounded KV region; inferred: enforce ≤60% headroom by sizing `n_slots` and rejecting/parking overflow. | `vram_budget_bytes` |

[R15]

#### DistServe

Paper Type: `Serving Runtime | Resource Manager | Model Accelerator`

(a) High-Level Architecture & System Design

DistServe is a distributed serving system that **disaggregates prefill and decode** across different GPU instances. It includes a placement algorithm module, a RESTful API frontend, an orchestration layer, and a parallel execution engine. The objective is to meet latency SLOs (TTFT/TPOT) by allocating resources separately to the prefill-heavy and decode-heavy phases.

(b) Infrastructure & Hardware Assumptions

DistServe targets GPU clusters (evaluated on multi-node A100-class deployments with fast intra-node NVLink and slower cross-node links). It explicitly accounts for cross-node bandwidth constraints and uses placement policies (e.g., low node-affinity) when cross-node bandwidth is limited.

(c) Core Optimizations & Algorithmic Design

The primary optimization is phase disaggregation: prefill instances compute KV for long prompts, while decode instances focus on token-by-token generation. DistServe also addresses bursty workloads during KV transfer by switching from a “push” model to a “pull” model.

Specifically, to combat burstiness, DistServe uses a **pull method for KV cache transmission**: decoding instances fetch KV cache from prefill instances as needed, using the prefill instances’ GPU memory as a queueing buffer and reducing the risk of decode-side memory overload.

(d) Memory & Cache Management

DistServe’s memory management is tightly coupled to its KV-transfer protocol. By using a pull-based transfer, DistServe avoids overloading decoding instances with a deluge of KV caches; prefill instances can temporarily buffer KV in GPU memory. DistServe does not present an explicit KV paging/eviction design (e.g., swap-to-CPU), nor a fixed policy for strict VRAM headroom targets like ≤60%.

(e) Request Scheduling & Batching

The orchestration layer schedules requests across prefill/decode pools. Phase-specific batching policies follow from the disaggregation design: prefill throughput is amortized over prompt tokens while decode requires steady per-token service for many concurrent sequences. The pull-based KV transfer introduces an implicit backpressure mechanism.

(f) Session & State Management

Session state is effectively split: (i) prefill-side ephemeral state while computing KV, (ii) decode-side state while generating tokens, and (iii) the KV representation transmitted between phases. DistServe explicitly notes that it **does not implement advanced runtime policies like preemption and fault tolerance**, stating these are complementary; thus, lease-aware state parking is not provided.

(g) Hardware Parallelization & Resource Allocation

Resource allocation is performed by assigning GPUs to prefill and decode pools and by placing those pools with awareness of interconnect topology. Disaggregation creates a natural resource partition: compute/memory-heavy prompt processing on prefill GPUs and iterative decode on decode GPUs.

vRAN Edge Viability (ComputeLease) + ComputeLease Scorecard:

DistServe’s disaggregation provides a useful blueprint for vRAN-edge deployments where prefill and decode have different “lease shapes.” However, DistServe does not directly address ComputeLease-style preemption/state parking. For edge viability, the container would need to (i) treat the phase boundary (prefill→decode) as a primary preemption boundary and (ii) provide a parking layer for KV between phases, especially under ≤60% VRAM stress. The pull-based KV transmission mechanism is a direct mechanism that can be mapped to `vram_budget_bytes` (decode admission) and to `preemption_notice_us` (stop decode, park/flush outstanding transfers).

**Adaptation hypothesis (AH-DISTSERVE-LEASE-PARK):** DistServe provides phase disaggregation and pull-based KV transfer. A vRAN-edge container would add a persistent KV parking tier (CPU RAM or local SSD) and bind `preemption_notice_us` to “stop issuing decode steps + flush/persist outstanding KV chunks,” while constraining per-lease decode work by `duration_us` and `sm_budget_sms`.

ComputeLease Scorecard:

| Axis | Score (High/Med/Low) | Evidence (Direct/Inferred) | Notes (boundary/unit/state/VRAM mechanism) | ComputeLease fields referenced |
| :--- | :--- | :--- | :--- | :--- |
| Preemption Resilience | Low | Direct | Direct: paper states it does not implement preemption/fault tolerance; only safe boundary is coarse (phase boundary) unless extended via AH. | `preemption_notice_us`, `reclaim_mode` |
| Micro-Segmentation | Medium | Inferred | Natural segmentation at (prefill) chunk / (decode) iteration level; binding to microsecond leases requires additional per-lease token caps. | `duration_us`, `sm_budget_sms` |
| State Parking | Medium | Inferred | Pull-based KV reduces overload, but persistent parking is not described; can be added by persisting KV chunks. | `bandwidth_budget_hint`, `reclaim_mode` |
| Tight VRAM Compliance (≤60% stress) | Medium | Inferred | Decode-side overload is mitigated by pull; strict ≤60% requires admission + explicit headroom policy. | `vram_budget_bytes` |

[R16]

#### SpotServe

Paper Type: `Serving Runtime | Resource Manager | Model Accelerator`

(a) High-Level Architecture & System Design

SpotServe is a serving runtime designed explicitly for **preemptible (spot) GPU instances** under dynamic availability and fluctuating workloads. Architecturally, it combines an inference server with control-plane components for configuration updates and context migration, including a Parallelization Controller, Device Mapper, Migration Planner, and an “Interruption Arranger.” It also includes context managers/daemons to retain and migrate inference context.

(b) Infrastructure & Hardware Assumptions

SpotServe assumes cloud deployments spanning providers (e.g., AWS/Azure/GCP) and explicitly integrates with **cloud storage backends** (e.g., S3/Blob/GCS) for saving/loading state. It targets large models where reloading weights and rebuilding context is expensive, and it leverages on-demand resources where needed to coordinate migrations.

(c) Core Optimizations & Algorithmic Design

SpotServe’s core optimizations are centered on surviving preemption events: it dynamically **re-parallelizes** the inference configuration as instance availability changes, plans migrations, and uses the cloud provider’s preemption/grace-period signals to arrange interruption handling. A “memory efficient migration planner” enforces a maximum buffer-memory threshold during migration planning.

(d) Memory & Cache Management

SpotServe treats inference “context” (including KV/state required to continue decoding) as a first-class object to be retained and migrated. It introduces a meta-context layer and uses daemons to keep context alive and avoid reload of large context. When necessary, it can reload model weights locally (disk) or from remote storage.

This design provides explicit “state parking”: context can be saved to cloud storage and later loaded to resume after preemption.

(e) Request Scheduling & Batching

SpotServe adapts to fluctuating and bursty workloads by changing serving configurations and instance counts, detecting overload, and triggering reconfiguration/migration to preserve latency where possible. The scheduler-level contribution is workload-aware adaptation rather than a specific per-token batching algorithm.

(f) Session & State Management

SpotServe is explicitly a **stateful inference recovery** system: it commits progress (token-granular boundaries) so that after a preemption event it can resume generation without redoing all prior work. The context migration mechanism (meta-context manager + context daemons) is the core session/state manager.

(g) Hardware Parallelization & Resource Allocation

SpotServe allocates resources by choosing parallelization configurations and mapping them onto available devices, and by migrating context as those devices change. Its unit of allocation is the serving instance set and the parallelization strategy; it is designed to be elastic under instance churn.

vRAN Edge Viability (ComputeLease) + ComputeLease Scorecard:

SpotServe directly targets the two hardest ComputeLease requirements: **preemption resilience** and **state parking**. The vRAN-edge mapping is to treat each lease reclaim as a preemption event: on `preemption_notice_us`, SpotServe-like logic commits token progress, persists meta-context, and migrates/resumes on a later lease. Under ≤60% VRAM stress, SpotServe’s buffer-memory-threshold migration planning suggests a viable policy: reserve headroom for migration/commit buffers and keep live context below a threshold fraction of `vram_budget_bytes`.

**Adaptation hypothesis (AH-SPOTSERVE-LEASE-WINDOWS):** SpotServe provides preemption-aware commit/migrate. A vRAN-edge container would map `preemption_notice_us` to “commit+park now,” and set per-lease work to ensure the commit point occurs within `duration_us` given `sm_budget_sms` (e.g., bound decode steps per lease), while enforcing a context headroom threshold under `vram_budget_bytes` (≤60% stress target).

ComputeLease Scorecard:

| Axis | Score (High/Med/Low) | Evidence (Direct/Inferred) | Notes (boundary/unit/state/VRAM mechanism) | ComputeLease fields referenced |
| :--- | :--- | :--- | :--- | :--- |
| Preemption Resilience | High | Direct+Inferred | Direct: designed for preemptible instances with recovery; inferred: bind to ComputeLease `preemption_notice_us` and reclaim events. | `preemption_notice_us`, `reclaim_mode` |
| Micro-Segmentation | Medium | Inferred | Direct unit is token-level commit/migration planning; mapping to sub-ms leases requires bounding work per lease. | `duration_us`, `sm_budget_sms` |
| State Parking | High | Direct | Direct: save/load context via cloud storage and context daemons; enables park/resume across interruptions. | `bandwidth_budget_hint`, `reclaim_mode` |
| Tight VRAM Compliance (≤60% stress) | Medium | Inferred | Direct: migration planner enforces buffer-memory thresholds; inferred: enforce ≤60% live-context headroom under `vram_budget_bytes`. | `vram_budget_bytes` |

[R17]

#### CacheGen

Paper Type: `Serving Runtime | Resource Manager | Model Accelerator`

(a) High-Level Architecture & System Design

CacheGen is a system for **encoding and streaming KV cache** as compressed bitstreams so that long-context inference can avoid expensive prefill from text and can reduce bandwidth. It separates responsibilities across an inference server and a storage/metadata layer that maps chunk identifiers to encoded KV bitstreams.

(b) Infrastructure & Hardware Assumptions

CacheGen assumes the presence of a **storage server** reachable by the inference server and targets GPU-based encoding/decoding to keep overhead low. It is evaluated on long-context LLM workloads and assumes network bandwidth variability is a primary bottleneck.

(c) Core Optimizations & Algorithmic Design

The system exposes two core APIs:

- `store_kv(LLM) -> {chunk_id: encoded_KV}`: compute KV, split into chunks, encode each chunk, and store a dictionary mapping `chunk_id` to bitstreams for K and V.
- `get_kv(chunk_id) -> encoded_KV`: fetch encoded KV tensors for the chunk and transmit to inference.

CacheGen pipelines **transmission of chunk i** with **decoding of chunk i−1** and uses GPU kernels where each CUDA thread encodes/decodes one token’s KV symbols.

(d) Memory & Cache Management

CacheGen turns the KV cache into a **parkable artifact**: encoded KV bitstreams live outside GPU VRAM on a storage server and are fetched/decoded as needed. This reduces GPU memory pressure for long contexts and reduces network transfer sizes compared to naive KV transfer baselines.

(e) Request Scheduling & Batching

CacheGen’s scheduling lever is chunk-level streaming: context is delivered in chunks, enabling overlap and incremental availability. The system is compatible with concurrent requests by treating chunks as independently retrievable units.

(f) Session & State Management

Session state is represented by the set of chunk IDs and their corresponding encoded KV bitstreams. If a chunk is unavailable or a context is lost, CacheGen can fall back to sending the **text** chunk and recomputing KV, providing an explicit recovery path.

(g) Hardware Parallelization & Resource Allocation

The encoding/decoding path is GPU-accelerated and can be parallelized over tokens and chunks; allocation is shaped by the tradeoff between GPU decode compute and network/storage bandwidth.

vRAN Edge Viability (ComputeLease) + ComputeLease Scorecard:

CacheGen provides a strong ComputeLease primitive: **state parking for transformer sessions** via encoded KV chunks stored outside VRAM. Under `preemption_notice_us`, a vRAN-edge container can commit the current chunk boundary (or partial chunk) and later resume by fetching/decoding from storage. The micro-segmentation unit is naturally the **context chunk**, which can be sized so each lease processes a bounded number of chunks/steps under `duration_us` and `sm_budget_sms`. Tight VRAM compliance under ≤60% stress is supported by parking most context outside VRAM and only keeping working-set KV chunks resident, bounded by `vram_budget_bytes`.

**Adaptation hypothesis (AH-CACHEGEN-LEASE-CHUNKSIZE):** CacheGen provides chunked KV parking + GPU decode. A vRAN-edge container would choose chunk sizes to ensure “decode+next-chunk fetch” fits within `duration_us` given `sm_budget_sms`, and would initiate chunk-boundary commits when `preemption_notice_us` is raised.

ComputeLease Scorecard:

| Axis | Score (High/Med/Low) | Evidence (Direct/Inferred) | Notes (boundary/unit/state/VRAM mechanism) | ComputeLease fields referenced |
| :--- | :--- | :--- | :--- | :--- |
| Preemption Resilience | High | Inferred | Chunk boundaries provide natural resume points; fallback to text+recompute enables recovery if KV missing. | `preemption_notice_us`, `duration_us` |
| Micro-Segmentation | High | Direct+Inferred | Direct: chunked get/store APIs; inferred: choose chunk size so per-lease chunk processing fits `duration_us`/`sm_budget_sms`. | `duration_us`, `sm_budget_sms` |
| State Parking | High | Direct | Direct: KV stored as encoded bitstreams on a storage server and fetched on demand. | `bandwidth_budget_hint`, `reclaim_mode` |
| Tight VRAM Compliance (≤60% stress) | High | Inferred | Encoded KV is off-VRAM; only a small working set needs VRAM. Enforce headroom by bounding in-VRAM decoded chunks. | `vram_budget_bytes` |

[R18]

##### Additional mechanisms (non-primary)

###### FlexGen

FlexGen is an offloading framework for throughput-oriented generative inference when the model and/or KV cache do not fit in GPU memory. It explicitly aggregates memory across a three-level hierarchy (GPU, CPU, disk) and schedules I/O alongside compute; it treats **weights, activations, and KV cache** as tensors to be placed and moved according to a cost model. While it is not a serving runtime for low-latency interactive use, it provides concrete “state parking” and offload mechanics that can be reused to meet hard `vram_budget_bytes` constraints under reclaim.

[R11]

###### DeepSpeed ZeRO-Inference

DeepSpeed-Inference includes ZeRO-Inference, a heterogeneous GPU+CPU+NVMe inference design that partitions/offloads model parameters to make massive-model inference feasible with limited GPU resources. As mechanism evidence for ComputeLease, ZeRO-Inference provides a systematic approach to keeping GPU-resident state bounded and to shifting state into CPU/NVMe tiers when GPU VRAM is the limiting lease dimension.

[R12]

---

## M4 Translation (Seq2Seq Transformer)

Primary systems considered: vLLM/PagedAttention, Orca, DistServe, SpotServe, CacheGen

#### vLLM/PagedAttention

Paper Type: `Serving Runtime | Resource Manager | Model Accelerator`

(a) High-Level Architecture & System Design

For translation workloads (encoder-decoder Transformers), the dominant “streaming” state still resides on the **decoder side**: decoding remains auto-regressive and produces a growing decoder KV cache. vLLM’s architecture (scheduler + KV block manager + PagedAttention) therefore transfers **primarily to the decoder component**: decoder KV is managed as logical KV blocks mapped to physical blocks, and PagedAttention consumes block tables for non-contiguous KV pages.

What does *not* transfer 1:1: encoder outputs are typically computed once per request and can be cached as a fixed tensor; this is not the same as the unbounded, growing KV working set on the decoder.

(b) Infrastructure & Hardware Assumptions

Same assumptions as in M3: explicit GPU memory management with a CPU-side allocator for swap (CPU RAM), and the ability to recompute decoder KV by re-running prompt-like computation. For seq2seq, recomputation can be applied to the decoder KV; encoder outputs can be recomputed or cached depending on policy.

(c) Core Optimizations & Algorithmic Design

PagedAttention provides block-level KV indirection and supports CoW/sharing patterns. For translation, the most relevant mechanism is still KV cache paging and eviction on the decoder. Shared-prefix caching is less central (translation prompts are less “system prompt”-heavy than instruction chat), but any common prefix structure in prompts can still be cached as in M3.

(d) Memory & Cache Management

Decoder KV cache can be managed with the same all-or-nothing eviction at the sequence/sequence-group level, with recovery via (i) CPU-RAM swapping or (ii) recomputation. Encoder-side memory is finite and fixed (per request) and can be treated as part of admission control.

(e) Request Scheduling & Batching

FCFS scheduling and latest-first preemption policies can apply to translation requests, but the decisive preemption boundary remains a decoder-step (iteration) boundary where KV eviction/parking is safe.

(f) Session & State Management

Session state is the (i) decoder KV cache and (ii) optionally cached encoder outputs. vLLM provides a concrete park/resume story for the decoder KV (swap or recompute). For a vRAN container, encoder outputs can be included in the parked state if recomputation is too costly under `duration_us`/`sm_budget_sms`.

(g) Hardware Parallelization & Resource Allocation

Resource allocation for ComputeLease is expressed as: cap decoder KV memory (and any encoder-output cache) under `vram_budget_bytes`, and bound per-lease decode work under `duration_us` and `sm_budget_sms`, with eviction/parking triggered under `preemption_notice_us`.

vRAN Edge Viability (ComputeLease) + ComputeLease Scorecard:

vLLM remains highly relevant for translation because the decoder-side KV cache is still the dominant growing state. The key caveat is that translation introduces an extra fixed “encoder output” state; a lease-aware container must decide whether to (a) keep encoder outputs in VRAM, (b) park them (CPU RAM), or (c) recompute them, depending on `duration_us`/`sm_budget_sms` and bandwidth constraints. Under ≤60% VRAM stress, the same headroom policy used in M3 can be applied by bounding total live KV+encoder-cache to ≤`vram_budget_bytes` (60% stress is achieved by configuring `vram_budget_bytes = 0.6 * physical_vram_bytes`).

**Adaptation hypothesis (AH-VLLM-LEASE-ENCDEC):** vLLM provides decoder KV paging (swap/recompute) and scheduling. A vRAN-edge container would extend the parked state to include encoder outputs when recomputing the encoder would violate `duration_us`/`sm_budget_sms`, and would trigger park on `preemption_notice_us`.

ComputeLease Scorecard:

| Axis | Score (High/Med/Low) | Evidence (Direct/Inferred) | Notes (boundary/unit/state/VRAM mechanism) | ComputeLease fields referenced |
| :--- | :--- | :--- | :--- | :--- |
| Preemption Resilience | High | Direct+Inferred | Decoder KV can be swapped to CPU RAM or recomputed; bind to `preemption_notice_us` for cooperative park-at-boundary. | `preemption_notice_us`, `duration_us` |
| Micro-Segmentation | Medium | Inferred | Requires capping decode work per lease; seq2seq adds encoder stage but micro-segmentation is still decoder-step bounded. | `duration_us`, `sm_budget_sms` |
| State Parking | High | Direct+Inferred | Direct: KV swap/recompute; inferred: optionally park encoder outputs as part of session state under reclaim. | `bandwidth_budget_hint`, `reclaim_mode` |
| Tight VRAM Compliance (≤60% stress) | High | Inferred | Enforce headroom across decoder KV + encoder-cache using admission control/eviction. | `vram_budget_bytes` |

[R10]

#### Orca

Paper Type: `Serving Runtime | Resource Manager | Model Accelerator`

(a) High-Level Architecture & System Design

For translation, Orca’s iteration-level scheduling transfers primarily to the **decoder phase** (auto-regressive decoding). Encoder computation is a one-shot stage; the scheduler can treat the encoder as part of request initiation and then manage decoder iterations similarly to M3.

(b) Infrastructure & Hardware Assumptions

Same as M3: GPU-based execution with a scheduler and an explicit Attention K/V manager; evaluated on multi-GPU NVIDIA systems.

(c) Core Optimizations & Algorithmic Design

Iteration-level scheduling provides a clean micro-segmentation unit for decoder steps. Orca’s selective batching and reservation mechanism remain relevant, but for seq2seq the reservation budget should include both (i) decoder KV slots and (ii) any encoder-output buffers retained for cross-attention.

(d) Memory & Cache Management

Orca’s K/V slot model maps to decoder KV cache. The scheduler uses `n_slots` to bound KV cache memory and reserves `req.max_tokens` at initiation to avoid deadlock. It does not specify a swap-to-CPU parking protocol; thus, under hard reclaims a vRAN container must add parking.

(e) Request Scheduling & Batching

Requests are selected by arrival time subject to reservation constraints. For translation, batching opportunities may be lower (encoder lengths differ), but the key benefit remains stable progress by interleaving decoder iterations.

(f) Session & State Management

State consists of decoder KV and (optionally) cached encoder outputs. Orca does not specify explicit park/resume; state is assumed resident within the pre-allocated KV region.

(g) Hardware Parallelization & Resource Allocation

Resource allocation is expressed through `n_slots` (KV region sizing) and pipeline/parallel configurations for large models.

vRAN Edge Viability (ComputeLease) + ComputeLease Scorecard:

Orca’s iteration boundary is a strong candidate for ComputeLease micro-segmentation in translation, but only if the container can safely park decoder KV and any required encoder-side tensors under reclaim. Without parking, preemption resilience is limited to “stop scheduling new iterations,” which fails under hard `vram_budget_bytes` pressure. Under ≤60% VRAM stress, `n_slots` provides a bounded KV region; headroom requires reserving capacity for park/commit buffers under `preemption_notice_us`.

**Adaptation hypothesis (AH-ORCA-LEASE-ENCDEC):** Orca provides iteration-level scheduling and slot-based KV admission. A vRAN-edge container would add a decoder-KV parking backend and include encoder outputs in the parked state when needed, triggered by `preemption_notice_us`, while bounding per-lease iterations under `duration_us`/`sm_budget_sms`.

ComputeLease Scorecard:

| Axis | Score (High/Med/Low) | Evidence (Direct/Inferred) | Notes (boundary/unit/state/VRAM mechanism) | ComputeLease fields referenced |
| :--- | :--- | :--- | :--- | :--- |
| Preemption Resilience | Medium | Inferred | Safe boundary: decoder iteration boundary; needs explicit parking under hard reclaim. | `preemption_notice_us`, `duration_us` |
| Micro-Segmentation | High | Direct+Inferred | Direct: iteration-level scheduling; inferred: cap iterations per lease using `duration_us`/`sm_budget_sms`. | `duration_us`, `sm_budget_sms` |
| State Parking | Low | Direct | No explicit swap/park protocol described; must be added for ComputeLease. | `reclaim_mode`, `bandwidth_budget_hint` |
| Tight VRAM Compliance (≤60% stress) | Medium | Direct+Inferred | Direct: bounded KV via `n_slots`; inferred: reserve headroom for parked encoder/decoder state under stress. | `vram_budget_bytes` |

[R15]

#### DistServe

Paper Type: `Serving Runtime | Resource Manager | Model Accelerator`

(a) High-Level Architecture & System Design

DistServe’s disaggregation (prefill vs decode) can be reinterpreted for translation as a separation between (i) **encoder + decoder-prefill** (context building) and (ii) decoder token generation. The key transferable idea is to allocate cluster resources differently for “context build” vs “steady decode,” which is still meaningful for seq2seq.

(b) Infrastructure & Hardware Assumptions

Same as M3: GPU clusters with heterogeneous interconnect bandwidth; placement must account for topology.

(c) Core Optimizations & Algorithmic Design

Pull-based KV transmission to combat burstiness remains relevant for translation if encoder outputs/decoder KV are transferred across instances. Using prefill-side GPU memory as a queueing buffer reduces decode-side overload.

(d) Memory & Cache Management

DistServe provides a burstiness-mitigation memory mechanism (prefill-side queueing) but does not define a strict eviction/parking policy. For seq2seq, the state to transfer/park includes both decoder KV and encoder-side tensors required for cross-attention.

(e) Request Scheduling & Batching

Orchestration schedules across phase pools; translation introduces additional heterogeneity in encoder lengths, but the phase separation still improves control.

(f) Session & State Management

DistServe does not implement preemption/fault-tolerance policies; thus, lease-aware session parking must be added for ComputeLease.

(g) Hardware Parallelization & Resource Allocation

Disaggregation is an explicit resource partition across GPUs/instances.

vRAN Edge Viability (ComputeLease) + ComputeLease Scorecard:

DistServe is useful for vRAN edge as an architectural pattern (separate context-build vs decode), but it does not by itself satisfy preemption/state-parking requirements. For translation, the parked state must include encoder-side tensors plus decoder KV. Under ≤60% VRAM stress, pull-based transfer helps prevent decode overload but does not enforce hard headroom; the container must bind admission to `vram_budget_bytes` and bind “drain/park” to `preemption_notice_us`.

**Adaptation hypothesis (AH-DISTSERVE-LEASE-ENCDEC):** DistServe provides disaggregation + pull-based KV transfer. A vRAN-edge container would persist encoder outputs + decoder KV between phases, park them under `preemption_notice_us`, and cap per-lease work with `duration_us`/`sm_budget_sms`.

ComputeLease Scorecard:

| Axis | Score (High/Med/Low) | Evidence (Direct/Inferred) | Notes (boundary/unit/state/VRAM mechanism) | ComputeLease fields referenced |
| :--- | :--- | :--- | :--- | :--- |
| Preemption Resilience | Low | Direct | Direct: preemption not implemented in paper; only coarse phase boundaries are safe without added mechanisms. | `preemption_notice_us`, `reclaim_mode` |
| Micro-Segmentation | Medium | Inferred | Phase boundary and chunked transfers exist; sub-ms lease mapping requires per-lease decode caps. | `duration_us`, `sm_budget_sms` |
| State Parking | Medium | Inferred | Pull transfer reduces overload; persistent parking of encoder+decoder state must be added. | `bandwidth_budget_hint`, `reclaim_mode` |
| Tight VRAM Compliance (≤60% stress) | Medium | Inferred | Requires explicit admission/headroom policy; pull mitigates burst overload but not strict cap. | `vram_budget_bytes` |

[R16]
 
 
#### SpotServe

Paper Type: `Serving Runtime | Resource Manager | Model Accelerator`

(a) High-Level Architecture & System Design

SpotServe’s design transfers directly to seq2seq in the sense that translation decoding is still an iterative process with a growing decoder state. The architecture (controllers + migration planner + context managers/daemons + interruption arranger) is agnostic to whether the model is decoder-only or encoder-decoder; the key is that there is expensive state to preserve across interruptions.

(b) Infrastructure & Hardware Assumptions

Cloud deployments with explicit integration to remote storage backends.

(c) Core Optimizations & Algorithmic Design

Dynamic reparallelization and migration planning under preemption/grace signals.

(d) Memory & Cache Management

Context is treated as migratable and parkable; for seq2seq, this includes (i) decoder KV and (ii) any cached encoder outputs.

(e) Request Scheduling & Batching

Workload-aware reconfiguration under fluctuating/bursty demand.

(f) Session & State Management

Stateful recovery with token-granular commit points extends naturally to translation decoding.

(g) Hardware Parallelization & Resource Allocation

Elastic allocation via configuration updates and migrations.

vRAN Edge Viability (ComputeLease) + ComputeLease Scorecard:

SpotServe is directly aligned with ComputeLease because it already treats “preemption notice” as a first-class control-plane event. For translation, a vRAN-edge container can map `preemption_notice_us` to “commit+park encoder+decoder state now,” and size per-lease decoding so that commits happen within `duration_us` given `sm_budget_sms`. Under ≤60% VRAM stress, reserve headroom for migration buffers and keep live context bounded under `vram_budget_bytes`.

**Adaptation hypothesis (AH-SPOTSERVE-LEASE-ENCDEC):** SpotServe provides commit/migrate and remote state persistence. A vRAN-edge container would include encoder outputs in the parked context and enforce a VRAM headroom threshold (≤60%) for live context under `vram_budget_bytes`.

ComputeLease Scorecard:

| Axis | Score (High/Med/Low) | Evidence (Direct/Inferred) | Notes (boundary/unit/state/VRAM mechanism) | ComputeLease fields referenced |
| :--- | :--- | :--- | :--- | :--- |
| Preemption Resilience | High | Direct+Inferred | Designed for preemptible instances with recovery; bind to lease `preemption_notice_us`. | `preemption_notice_us`, `reclaim_mode` |
| Micro-Segmentation | Medium | Inferred | Token-level commit exists; map to lease windows by bounding work per lease. | `duration_us`, `sm_budget_sms` |
| State Parking | High | Direct | Save/load context via storage; extend to include encoder outputs. | `bandwidth_budget_hint`, `reclaim_mode` |
| Tight VRAM Compliance (≤60% stress) | Medium | Inferred | Use buffer-memory threshold planning + headroom admission to keep live context under cap. | `vram_budget_bytes` |

[R17]

#### CacheGen

Paper Type: `Serving Runtime | Resource Manager | Model Accelerator`

(a) High-Level Architecture & System Design

CacheGen’s KV encoding/streaming concept transfers to seq2seq primarily for the decoder-side KV cache. Translation also has encoder outputs; CacheGen can be applied to park/stream those encoder-side tensors as well, but the paper’s direct evidence is KV (K/V tensors) as the primary streamed state.

(b) Infrastructure & Hardware Assumptions

Storage server + GPU decode/encode path; network bandwidth variability is assumed.

(c) Core Optimizations & Algorithmic Design

Chunked KV store/get APIs and GPU-based arithmetic-coding encode/decode with chunk pipelining.

(d) Memory & Cache Management

KV is parked off-VRAM as encoded bitstreams; only a working set is decoded into VRAM.

(e) Request Scheduling & Batching

Chunk-level streaming is the natural scheduling unit.

(f) Session & State Management

Session state is a set of chunk IDs that can be fetched/decoded; fallback exists via text+recompute.

(g) Hardware Parallelization & Resource Allocation

GPU decode/encode parallelizes across tokens/chunks.
 
vRAN Edge Viability (ComputeLease) + ComputeLease Scorecard:

CacheGen provides a direct state-parking mechanism for translation decoder KV via chunked encoded KV stored outside VRAM. A vRAN-edge container can treat chunk boundaries as cooperative pause points under `preemption_notice_us` and can choose chunk sizes so that “decode+fetch” fits within `duration_us` given `sm_budget_sms`. Under ≤60% VRAM stress, the working set of decoded chunks is explicitly bounded by `vram_budget_bytes`.

**Adaptation hypothesis (AH-CACHEGEN-LEASE-ENCDEC):** CacheGen directly supports decoder KV parking; a vRAN-edge container would additionally decide whether to park encoder outputs alongside KV (or recompute) based on `duration_us`/`sm_budget_sms`.

ComputeLease Scorecard:

| Axis | Score (High/Med/Low) | Evidence (Direct/Inferred) | Notes (boundary/unit/state/VRAM mechanism) | ComputeLease fields referenced |
| :--- | :--- | :--- | :--- | :--- |
| Preemption Resilience | High | Inferred | Chunk boundaries enable resume; fallback via text+recompute if state missing. | `preemption_notice_us`, `duration_us` |
| Micro-Segmentation | High | Direct+Inferred | Direct: chunk APIs; inferred: select chunk size for lease window. | `duration_us`, `sm_budget_sms` |
| State Parking | High | Direct | Direct: encoded KV stored on storage server and fetched on demand. | `bandwidth_budget_hint`, `reclaim_mode` |
| Tight VRAM Compliance (≤60% stress) | High | Inferred | Working set is bounded by decoded chunks; enforce headroom under cap. | `vram_budget_bytes` |

[R18]

##### Additional mechanisms (non-primary)

###### FlexGen

FlexGen provides an explicit GPU↔CPU↔disk offload pipeline for generative inference and treats KV cache as an offloadable tensor. For translation, the same mechanism can be used to park decoder KV (and optionally encoder outputs) when `vram_budget_bytes` is tight or when a reclaim requires eviction.

[R11]

###### DeepSpeed ZeRO-Inference

DeepSpeed ZeRO-Inference provides systematic CPU/NVMe offload for inference-time memory scaling. For translation, this is mechanism evidence for parking model state and other tensors outside VRAM when leases enforce strict `vram_budget_bytes` limits.

[R12]

---

## M5 Super Resolution (ESRGAN)

Primary systems considered: USHER, Orion, Aqua, Proteus

Super-resolution (ESRGAN-like) inference is a **one-shot, highly deterministic** workload, but it is hostile to fine-grained preemption in the vRAN-edge setting: it is **activation-heavy** (massive intermediate feature maps), has **very low batch headroom** (batch size quickly bottlenecks on activation VRAM), and exhibits **poor mid-layer preemptibility** (high context-switch / restart cost once deep into the forward pass). In CORA’s matrix terms, the minimum useful scheduling granularity is closer to **per-inference / coarse tile** than to per-operator preemption.

The four systems below are not written as SR-specialized runtimes; this section therefore separates **direct mechanisms** from SR/ComputeLease mappings, labeling non-direct mappings as **Adaptation hypothesis (AH-...)**.

#### USHER

Paper Type: `Serving Runtime`

(a) High-Level Architecture & System Design

USHER is an interference-aware scheduling system for multi-model ML inference that targets **resource (compute+memory) underutilization** caused by coarse batching and inter-model interference. It takes as input (i) per-model request rates and (ii) available GPU types, and outputs a placement/sizing plan that chooses **batch size**, **replication degree**, and **GPU placement** to maximize goodput or cost-efficiency while meeting latency SLOs.

Architecturally, USHER has three major components: (1) a GPU-kernel-based estimator for model resource needs (**GK-Estimator**), (2) a lightweight heuristic scheduler (**IR-Scheduler**) that decides batch/replication/placement while being interference-aware, and (3) an operator-graph merging stage (**OG-Merger**) to reduce cache interference when multiple models co-reside on one GPU.

SR-specific mapping: USHER’s primary abstractions are **per-model** and **per-batch**; it does not claim SR tiling/patching. Any SR “tile-level” mapping is therefore treated as an adaptation hypothesis (see vRAN section).

(b) Infrastructure & Hardware Assumptions

USHER targets GPU inference deployments with multiple concurrently hosted models and potentially **heterogeneous GPU clusters**. It assumes standard DNN framework execution that ultimately launches GPU kernels; the paper describes (and evaluates) setups built on NVIDIA GPUs (e.g., V100-class) and leverages conventional inference baselines that use batching and/or spatial multiplexing.

The design assumes the ability to (i) run multiple models concurrently on a GPU (e.g., using mechanisms like MPS in related work), and (ii) replicate models across GPUs to divide workload when needed.

SR-specific mapping: For vRAN edge, the practical constraint is often a **single GPU slice** (MIG/MPS-like) with a hard VRAM cap. USHER’s cluster-scale placement logic must therefore be treated as a mechanism that can be down-scoped to “one node / one slice” rather than assumed to run unchanged.

(c) Core Optimizations & Algorithmic Design

The key algorithmic idea is to optimize GPU utilization **holistically across compute and memory**, rather than treating batch size as a single knob. USHER explicitly models a model’s compute and memory requirements (Creq/Mreq) and groups models to increase the probability of beneficial multiplexing (e.g., pairing compute-heavy with memory-heavy models). It then selects discrete batch-size and replication choices and places replicas to satisfy latency SLOs while maximizing utilization.

USHER’s GK-Estimator derives resource requirements without running the model end-to-end on the GPU by analyzing low-level kernel behavior and using regressors for intermediate memory and kernel timing. The IR-Scheduler uses heuristics instead of solving a high-complexity global optimization, enabling adaptation when request rates change.

SR-specific mapping: ESRGAN-class SR is frequently both compute- and memory-stressed due to activations, and batch size is typically near 1. USHER’s “batch as utilization knob” is therefore constrained for SR; the transferable part is the **explicit modeling of intermediate (activation) memory** and the **interference-aware placement** logic.

(d) Memory & Cache Management

USHER’s resource model explicitly accounts for memory consumed by both **model parameters** and **intermediate data (activations)**, and its scheduler aims to avoid interference in “compute space” and “memory space” by ensuring allocated capacity matches estimated requirements.

To address cache-related interference that is not resolved by compute/memory-space isolation, USHER introduces an operator-graph merger that merges computation graphs to increase reuse of overlapping weights in GPU cache, aiming to reduce cache thrash under co-resident models.

SR-specific mapping: SR’s dominant dynamic VRAM term is intermediate feature maps, not KV cache. USHER’s explicit intermediate-memory modeling is directly relevant, but any claim that OG-Merger improves SR activation behavior would be speculative; OG-Merger is a cache-interference mechanism for co-resident models, not an SR activation offload mechanism.

(e) Request Scheduling & Batching

USHER’s IR-Scheduler chooses batch size and replication degree under latency SLOs and varying request rates, and then places model replicas on GPUs. The paper emphasizes that batching is discrete and cannot smoothly saturate both compute and memory, motivating the joint batch+replication+placement decision.

SR-specific mapping: SR’s “max optimal batch size” is typically very low because activations scale with spatial dimensions and batch. As a result, SR deployments cannot assume batching will be the primary utilization lever; instead, SR must lean on (i) safe multiplexing with other workloads and/or (ii) segmentation at a coarser unit (e.g., tile) — the latter is not a direct USHER mechanism.

(f) Session & State Management

USHER is oriented around per-request inference under latency SLOs and per-model request-rate dynamics. It does not introduce a long-lived per-user session state model; state is primarily the scheduler’s placement plan and the profiling/estimation artifacts used to compute it.

SR-specific mapping: SR is one-shot; session state is **N/A by workload design**. The remaining state relevant to vRAN edge is model weights (artifact locality) and any cached profiling/estimation data.

(g) Hardware Parallelization & Resource Allocation

USHER allocates resources by selecting replication degree (workload division across GPUs), choosing batch size per model, and placing replicas onto GPUs while accounting for compute and memory requirements. The design is intended to be compatible with standard GPU execution where multiple workloads can share a device (subject to interference constraints).

SR-specific mapping: For vRAN edge, the scheduler’s “allocation” primitive is often a **slice** (e.g., MIG instance) rather than a whole GPU. USHER’s placement can be interpreted as selecting which SR variants are admissible under a given slice’s `vram_budget_bytes` and effective `sm_budget_sms`.

vRAN Edge Viability (ComputeLease) + ComputeLease Scorecard:

USHER’s design point is **macro-scale** optimization (batch/replication/placement under SLOs) rather than microsecond-scale lease slicing. For SR, the key transferable value is that USHER explicitly models intermediate activation memory and uses that to make interference-aware placement decisions.

**Adaptation hypothesis (AH-USHER-TileLease):** USHER provides (i) a kernel-informed estimator for intermediate-memory needs and (ii) a heuristic scheduler for batch/replication/placement. To make SR viable under sub-ms ComputeLease windows, the vRAN inference container would (a) **tile/patch** SR inputs and treat each tile as an atomic “request” (batch≈1), and (b) use USHER’s estimator/scheduler to choose a tile size that fits `duration_us` and `vram_budget_bytes`, with early-stop on `preemption_notice_us` to avoid mid-tile interruption.

| Axis | Score (High/Med/Low) | Evidence (Direct/Inferred) | Notes (boundary/unit/state/VRAM mechanism) | ComputeLease fields referenced |
| :--- | :--- | :--- | :--- | :--- |
| Preemption Resilience | Low | Inferred | Safe boundary is effectively **end-of-inference**; USHER does not define cooperative preemption. SR mid-layer preemption remains costly due to activation state. | preemption_notice_us, reclaim_mode |
| Micro-Segmentation | Low | Inferred | Minimum unit is per-request/per-batch; SR tile-level segmentation would require AH-USHER-TileLease. | duration_us, sm_budget_sms |
| State Parking | Medium | Inferred | Scheduler/estimator state is small; model weights/variants must be available to reload. No explicit activation checkpointing. | reclaim_mode, bandwidth_budget_hint |
| Tight VRAM Compliance (≤60% stress) | High | Inferred | USHER explicitly estimates intermediate-memory requirements (Mreq) and uses them to avoid memory-space interference; can be used as admission control under `vram_budget_bytes`. | vram_budget_bytes |

[R1]

#### Orion

Paper Type: `Resource Manager`

(a) High-Level Architecture & System Design

Orion is a fine-grained, interference-aware GPU sharing system that **intercepts GPU kernel launches** from multiple clients sharing a GPU and schedules work at the granularity of individual operators/kernels. Its goal is to maximize utilization while minimizing interference at **10s–1000s of microseconds** timescales, preserving tail latency for high-priority inference while running best-effort co-tenants.

At a high level, Orion inserts a software scheduler between the ML framework and the GPU: intercepted kernel launches are placed into per-client software queues, and the Orion scheduler selects which kernel to submit next based on job priority, operator size, and whether an operator is compute- vs memory-bound.

SR-specific mapping: Orion’s direct unit of control is the kernel/operator. SR workloads can benefit from kernel-level interference control, but SR’s poor mid-layer preemptibility means that a vRAN container may still prefer **tile-level** boundaries for safe stopping (see vRAN section).

(b) Infrastructure & Hardware Assumptions

Orion assumes NVIDIA CUDA-like execution where kernels are non-preemptive after submission. It integrates transparently into a DNN framework (prototype implemented in PyTorch) by overriding CUDA runtime and library calls (CUDA runtime, cuDNN, cuBLAS) with wrapper functions.

Orion assumes the collocated jobs **fit in GPU memory** (memory capacity admission is orthogonal), and can run either (i) as threads in one process (fast in-process queues) or (ii) as separate processes using shared-memory queues, requiring GPU support for concurrent multi-process access (e.g., MPS).

(c) Core Optimizations & Algorithmic Design

Orion’s scheduling policy is interference-aware: it profiles kernels offline (compute-throughput vs memory-bandwidth intensity, expected duration, SM needs) and schedules kernels so that best-effort work uses GPU resources that the high-priority work is not saturating. It throttles best-effort kernels when lack of kernel preemption could otherwise cause head-of-line blocking.

The implementation uses CUDA stream priorities and CUDA events to monitor progress without heavy synchronization, enabling fast scheduling decisions.

(d) Memory & Cache Management

Orion primarily targets compute/memory-bandwidth interference at the kernel scheduling layer. It intercepts memory management operations to preserve semantics (and synchronizes clients for operations that imply device-wide synchronization), but it does not claim to introduce a new GPU memory virtualization layer.

The paper explicitly positions Orion as orthogonal to GPU memory swapping/offloading mechanisms (e.g., Unified Memory or specialized swapping systems), and suggests it can be combined with such mechanisms.

SR-specific mapping: SR activation-heavy behavior stresses VRAM; Orion alone does not ensure tight VRAM compliance under a hard cap.

(e) Request Scheduling & Batching

Orion schedules at the granularity of operators/kernels, enabling microsecond-scale time slicing in the sense of rapidly alternating between kernels from different clients. For inference jobs, a “request” is defined as a batch of inference inputs; Orion’s goal is to preserve high-priority request tail latency while improving aggregate throughput via fine-grained colocation.

SR-specific mapping: SR has limited batching headroom, so Orion’s benefit is less about large-batch throughput and more about **safe colocation** and **lease-sized kernel scheduling**.

(f) Session & State Management

Orion is stateless with respect to application-level sessions; its persistent state is primarily the offline profiling table indexed by kernel ID and the runtime queues tracking pending kernel launches.

SR-specific mapping: SR has no session state (N/A). The relevant “state” under ComputeLease is intermediate activation state inside an in-flight SR forward pass, which Orion does not checkpoint.

(g) Hardware Parallelization & Resource Allocation

Orion’s “allocation” is performed through scheduling decisions (which kernels run when) and through implicit control of SM occupancy by selecting kernels with known SM needs. It does not require MIG and can be used alongside MPS/streams; in multi-process mode it relies on a sharing mechanism like MPS for concurrent access.

vRAN Edge Viability (ComputeLease) + ComputeLease Scorecard:

Orion is the strongest match (among the four) to **microsecond-scale** compute leasing because it explicitly targets 10s–1000s of microseconds scheduling granularity. However, Orion cannot preempt an already-submitted kernel, and SR’s activation-heavy mid-layer state makes “stop anywhere” undesirable.

**Adaptation hypothesis (AH-ORION-CoarseTileBoundary):** Orion provides operator-level scheduling and interference awareness. To make SR interruption safe under hard reclaims, the vRAN container would (a) enforce **coarse tile/patch boundaries** as the only cooperative pause points (avoid mid-tile activation state), and (b) expose those tile boundaries as “requests” such that Orion’s high-priority scheduling keeps each tile’s tail within the lease window; this depends on `preemption_notice_us` (to drain) and `duration_us`/`sm_budget_sms` (to size tiles).

| Axis | Score (High/Med/Low) | Evidence (Direct/Inferred) | Notes (boundary/unit/state/VRAM mechanism) | ComputeLease fields referenced |
| :--- | :--- | :--- | :--- | :--- |
| Preemption Resilience | Medium | Inferred | Orion can switch at **kernel boundaries**; kernels are non-preemptive once submitted. For SR, safe boundary likely coarser (tile), per AH-ORION-CoarseTileBoundary. | preemption_notice_us, reclaim_mode |
| Micro-Segmentation | High | Direct | Schedules at **operator/kernel granularity** and explicitly targets 10s–1000s of microseconds interference control. | duration_us, sm_budget_sms |
| State Parking | Low | Inferred | No explicit mechanism to park in-flight activation state; combining with swapping/offload is suggested but not designed as a parking system. | reclaim_mode, bandwidth_budget_hint |
| Tight VRAM Compliance (≤60% stress) | Medium | Inferred | Assumes collocated jobs fit in GPU memory; VRAM cap enforcement requires external admission/swapping. | vram_budget_bytes |

[R2]

#### Aqua

Paper Type: `Resource Manager`

(a) High-Level Architecture & System Design

Aqua is a transparent, elastic GPU memory management framework designed to enable **responsive inference under memory contention** by reducing paging overheads. Aqua’s key architectural mechanism is to offload dynamic inference context to the memory of other GPUs in the same high-bandwidth interconnect domain (e.g., NVLink), rather than paging to host DRAM over PCIe.

The paper describes three main components: (1) Aqua-profiler to classify GPUs as memory *producers* (spare HBM) or *consumers* (memory-bound), (2) Aqua-placer to place models to maximize producer/consumer proximity within an interconnect domain, and (3) Aqua-lib, a memory management library that introduces elastic “Aqua Tensors” (offloaded tensor abstraction with reclaim by producers). Aqua also integrates fair, preemptive prompt scheduling (CFS-like) into serving engines to prevent request starvation.

SR-specific mapping: Aqua is not an SR system; its “context” is typically prompt KV cache and similar dynamic state. Applying its offload/elasticity ideas to SR activation state requires an explicit adaptation hypothesis.

(b) Infrastructure & Hardware Assumptions

Aqua targets **scale-up multi-GPU domains** where multiple GPUs share a high-bandwidth interconnect (NVLink/NVSwitch/ICI). It assumes an infrastructure layer can place models across GPUs/servers and that some GPUs may have spare HBM due to being compute-bound at peak throughput.

It also assumes integration with existing serving engines (e.g., vLLM-like) and that paging to host DRAM is available as a fallback when no producer HBM is available.

(c) Core Optimizations & Algorithmic Design

Aqua’s main optimization is **network-accelerated memory offloading**: it uses inter-GPU links to move paging traffic off PCIe, enabling preemptive/fair scheduling without prohibitive throughput loss. Aqua-profiler derives producer/consumer roles based on profiling free memory at peak throughput, and Aqua-placer performs placement to avoid relying on chance availability of nearby free HBM.

The paper notes practical constraints of interconnects (e.g., bandwidth only reaches peak above certain transfer sizes) and designs the offloaded-tensor abstraction accordingly.

(d) Memory & Cache Management

Memory management is Aqua’s center: Aqua-lib exposes an offloaded tensor abstraction (“Aqua Tensors”) that can live in producer GPU memory, with transparent access from the consumer and an elasticity mechanism for reclaim when producer load increases. Corner cases fall back to DRAM paging.

SR-specific mapping: SR’s activation maps are large and short-lived within a forward pass; Aqua’s direct evidence concerns paging persistent/dynamic context across scheduling slices. Treating SR intermediate activations as pageable/offloadable state is speculative without additional runtime support.

(e) Request Scheduling & Batching

Aqua motivates replacing batch-only inference with **time-sliced, fair scheduling** (CFS-like) to prevent prompt starvation and improve responsiveness. The approach relies on lower paging overheads enabled by Aqua’s offloads.

SR-specific mapping: SR has low batch headroom and deterministic service times; a fair scheduler would more naturally schedule **tiles** rather than tokens. That mapping is not a direct Aqua claim.

(f) Session & State Management

Aqua explicitly manages per-request dynamic inference state (e.g., prompt context) across time slices by moving state in/out of GPU HBM, enabling preemptive scheduling semantics for inference.

SR-specific mapping: SR has no multi-step “session” like decoding, but it does have large intermediate activation state during a forward pass. Making that state parkable is the key gap for SR.

(g) Hardware Parallelization & Resource Allocation

Aqua’s resource allocation is primarily memory-centric: it pairs memory consumers with producers within an interconnect domain and places models/shards accordingly. The placement formulation uses server/GPU constraints (e.g., one shard per GPU; tensor-parallel shards co-located within a server).

vRAN Edge Viability (ComputeLease) + ComputeLease Scorecard:

Aqua provides direct evidence that **paging overhead** is the primary obstacle to preemptive, fair scheduling under memory contention, and that offloading state over a fast GPU interconnect can enable responsive scheduling. For vRAN edge, the main mismatch is that SR’s critical state is activation-heavy mid-layer tensors, not KV cache.

**Adaptation hypothesis (AH-AQUA-SRActivationParking):** Aqua provides an elastic, transparent offloaded-tensor abstraction (Aqua Tensors) and placement to source fast offload capacity. To apply this to SR, the container would need to (a) expose SR **activation checkpoints at coarse tile boundaries** and (b) store those activation checkpoints in an Aqua-like offload pool (neighbor GPU HBM when available; otherwise host DRAM/NVMe), enabling pause/resume across leases; this depends on `vram_budget_bytes` (cap), `bandwidth_budget_hint` (movement), and `preemption_notice_us` (checkpoint time).

| Axis | Score (High/Med/Low) | Evidence (Direct/Inferred) | Notes (boundary/unit/state/VRAM mechanism) | ComputeLease fields referenced |
| :--- | :--- | :--- | :--- | :--- |
| Preemption Resilience | High | Direct | Aqua is explicitly designed to enable preemptive/fair scheduling by reducing paging overhead of inference state (time-slicing). SR-specific pause/resume of activations remains AH-AQUA-SRActivationParking. | preemption_notice_us, reclaim_mode |
| Micro-Segmentation | Medium | Inferred | Aqua’s direct segmentation is time-sliced prompt scheduling; SR would need tile-based units to fit `duration_us`. | duration_us, sm_budget_sms |
| State Parking | High | Direct | Explicitly manages offloaded inference context (Aqua Tensors) with elastic reclaim; can fall back to DRAM paging. | reclaim_mode, bandwidth_budget_hint |
| Tight VRAM Compliance (≤60% stress) | High | Direct | Addresses GPU memory contention via offloading/paging; provides a mechanism to operate under hard HBM pressure. | vram_budget_bytes |

[R13]

#### Proteus

Paper Type: `Serving Runtime`

(a) High-Level Architecture & System Design

Proteus is an inference-serving system that introduces **accuracy scaling** as a first-class control knob when hardware scaling is infeasible (e.g., fixed-size edge clusters). It serves queries using different model variants (accuracy/performance trade-offs) to meet throughput and latency SLO constraints.

The paper’s system architecture (Figure 2 in the paper) consists of a **Controller**, per-application **Load Balancers**, and **Workers**. Load balancers are on the data path (routing queries to workers/model variants), while the controller performs resource allocation off the critical path.

(b) Infrastructure & Hardware Assumptions

Proteus targets heterogeneous clusters with multiple device types. It assumes applications register their model variants, and the system profiles model-variant performance across device types and batch sizes. Profiling results are stored in an in-memory key-value store keyed by (model variant, device type, batch size) for fast lookup.

Load balancers can be distributed to avoid a single bottleneck, and workers host model variants and execute queries with adaptive batching.

(c) Core Optimizations & Algorithmic Design

Proteus jointly optimizes three coupled problems under accuracy scaling: (i) **model variant selection**, (ii) **model placement** on heterogeneous devices, and (iii) **query assignment** to devices/variants. The controller’s resource manager solves an MILP to maximize system accuracy while meeting target throughput and latency constraints, and can terminate/start model-variant instances based on the solution.

Proteus also proposes a proactive, non-work-conserving **adaptive batching** algorithm at workers to reduce SLO violations under bursty arrivals, without requiring changes to the ML framework.

SR-specific mapping: SR does not naturally provide a “variant ladder” in the paper; mapping accuracy scaling to SR requires explicitly defining SR variants (see vRAN section).

(d) Memory & Cache Management

Proteus does not introduce a new GPU paging/caching subsystem; instead, it manages memory indirectly through (i) which model variants are instantiated on which devices and (ii) what batch sizes are used. The architecture implies that model artifacts/variants are deployable on demand by the hardware executor.

SR-specific mapping: SR activation memory is the dominant dynamic term; Proteus primarily acts via variant choice and batching, not activation checkpointing.

(e) Request Scheduling & Batching

On the data path, each application’s load balancer routes queries according to a query assignment policy from the controller. Workers apply adaptive batching to improve throughput while meeting latency constraints. The controller reacts to macro-scale demand shifts (QPS) while adaptive batching reacts to micro-scale inter-arrival variability.

SR-specific mapping: SR’s batch headroom is low; Proteus-style batching primarily applies when SR queries can be aggregated (e.g., multiple independent tiles) — which is not claimed by the paper.

(f) Session & State Management

Proteus is request-oriented; it does not define multi-step sessions like token-by-token decoding. The relevant persistent state is the registration/profiling metadata and the active deployment state of model variants across workers.

(g) Hardware Parallelization & Resource Allocation

Proteus allocates hardware by placing model variants onto heterogeneous devices and assigning query fractions to each device. It can reconfigure deployments (start/stop instances of variants) when demand shifts, and it separates control (controller) from the serving critical path (load balancer/workers).

vRAN Edge Viability (ComputeLease) + ComputeLease Scorecard:

Proteus is directly motivated by fixed-size edge clusters and supports adapting accuracy to demand. For ComputeLease-driven vRAN operation, the most transferable idea is to treat **quality** as a runtime knob when compute/VRAM are scarce, but Proteus does not directly target microsecond-scale preemption.

**Adaptation hypothesis (AH-PROTEUS-SRVariantLadder):** Proteus provides a controller that selects among model variants and places them to meet throughput/SLO while maximizing accuracy. To apply to SR, the vRAN container would need to define an SR variant ladder (e.g., pruned/quantized ESRGAN variants, reduced-channel SR models, or lower upscaling factor) and select a variant per request (or per tile) based on `duration_us`/`sm_budget_sms` and `vram_budget_bytes`. This maps Proteus’s accuracy scaling onto SR under ComputeLease.

| Axis | Score (High/Med/Low) | Evidence (Direct/Inferred) | Notes (boundary/unit/state/VRAM mechanism) | ComputeLease fields referenced |
| :--- | :--- | :--- | :--- | :--- |
| Preemption Resilience | Low | Inferred | Proteus focuses on variant selection/placement and batching, not cooperative pause/resume; safe boundary is end-of-batch/end-of-request. | preemption_notice_us, reclaim_mode |
| Micro-Segmentation | Medium | Inferred | Adaptive batching changes batch size but does not define sub-ms micro-units; SR tile-level units require AH-PROTEUS-SRVariantLadder (and tiling mechanism). | duration_us, sm_budget_sms |
| State Parking | Medium | Inferred | Can start/stop variant instances; model artifacts can be redeployed. No explicit parking of in-flight activations. | reclaim_mode, bandwidth_budget_hint |
| Tight VRAM Compliance (≤60% stress) | Medium | Inferred | Indirectly controlled via variant choice and batch size; not a hard VRAM-capped runtime by itself. | vram_budget_bytes |

[R14]

---

## M6 Volume Rendering (NeRF)

Primary systems considered: Instant-NGP, NerfAcc, TensoRF, DirectVoxGO

#### Instant-NGP

Paper Type: `Model Accelerator`

(a) High-Level Architecture & System Design

Instant-NGP targets fast NeRF optimization/rendering by pairing a small MLP with a multiresolution hash-table encoding of 3D position; in the NeRF instantiation, it uses a density MLP followed by a color MLP (view-dependent color) and performs ray marching for rendering. It further accelerates ray marching by maintaining an occupancy grid to skip empty space and concentrate samples near surfaces. [R6]

(b) Infrastructure & Hardware Assumptions

The encoding and MLP evaluation are implemented in CUDA and integrated with tiny-cuda-nn fully-fused MLP kernels; the paper explicitly discusses GPU cache behavior and reports measurements on an NVIDIA RTX 3090 (6 MB L2 cache) as an example hardware point. [R6]

(c) Core Optimizations & Algorithmic Design

Core acceleration mechanisms are (i) multiresolution hash encoding (a hierarchy of hash tables of trainable feature vectors) that enables a much smaller MLP at comparable quality, (ii) fully-fused CUDA kernels to minimize wasted bandwidth/compute, and (iii) occupancy-grid–accelerated ray marching (with an optional cascaded occupancy grid for large scenes). [R6]

(d) Memory & Cache Management

Directly described memory mechanisms include half-precision storage for hash-table entries (with a full-precision master copy for mixed-precision updates) and a level-by-level evaluation schedule to keep a small working set resident in GPU caches; the NeRF instantiation also maintains an occupancy grid (and optionally a cascaded occupancy grid) as an auxiliary data structure for sampling/ray marching acceleration. Notably, the paper does **not** define a serving-runtime VRAM admission/eviction policy—only accelerator-internal layout/efficiency choices. [R6]

(e) Request Scheduling & Batching

Not addressed (gap for serving-runtime design).

(f) Session & State Management

Not addressed (gap for serving-runtime design). (Direct evidence: the accelerator’s persistent *model state* for NeRF includes multiresolution hash-table parameters, MLP weights, and an occupancy grid; however, no serving-session lifecycle, multi-request state isolation, or state parking/resume protocol is specified.) [R6]

(g) Hardware Parallelization & Resource Allocation

The design is explicitly GPU-parallel and cache-aware (hash-table queries can be evaluated in parallel; computation is structured to leverage GPU caches; kernels are CUDA-fused). The paper does not specify multi-tenant GPU slicing, lease-aware resource allocation, or cross-request isolation semantics. [R6]

vRAN Edge Viability (ComputeLease) + ComputeLease Scorecard:

Instant-NGP is **not** a serving engine; it is mechanism evidence for (i) ray-batch micro-segmentation (via ray marching + occupancy-grid skipping) and (ii) compact scene/state representation (hash tables + small MLP). Under a ComputeLease contract, a vRAN-edge container would still need to add lease-aware admission control, explicit preemption boundaries, and state parking.

| Axis | Score (High/Med/Low) | Evidence (Direct/Inferred) | Notes (boundary/unit/state/VRAM mechanism) | ComputeLease fields referenced |
| :--- | :--- | :--- | :--- | :--- |
| Preemption Resilience | Med | Inferred | Safe cooperative boundary plausibly at **ray-batch** drain points (ray marching loops); no explicit preemption semantics in paper. See AH-M6-INGP-SEGMENT. | `preemption_notice_us`, `reclaim_mode`, `duration_us` |
| Micro-Segmentation | Med | Inferred | Natural micro-unit is **ray-batch** (and/or sample-chunk along rays) with occupancy-grid skipping to reduce wasted work; microsecond-fit not evaluated. See AH-M6-INGP-SEGMENT. | `duration_us`, `sm_budget_sms`, `start_time_us` |
| State Parking | Med | Inferred | Persistent state = hash tables (half precision), small MLP weights, occupancy grid; parking location/format not specified. See AH-M6-INGP-PARK. | `reclaim_mode`, `preemption_notice_us`, `duration_us` |
| Tight VRAM Compliance (≤60% stress) | Med | Inferred | Hash table size and precision are explicit knobs; no VRAM hard-cap admission/eviction policy described. See AH-M6-INGP-PARK. | `vram_budget_bytes`, `gpu_slice` |

- **Adaptation hypothesis (AH-M6-INGP-SEGMENT)**: Treat **ray-batch** as the ComputeLease micro-segmentation + preemption boundary by constraining per-batch work to fit `duration_us` and draining in-flight batches on `preemption_notice_us` (Instant-NGP provides occupancy-grid accelerated ray marching; the vRAN-edge container must add lease-aware batch sizing and cooperative stop points).
- **Adaptation hypothesis (AH-M6-INGP-PARK)**: Park the **hash-table + MLP + occupancy-grid** state to host RAM / local NVMe when leases lapse (0% SM availability) and reload/rehydrate on the next lease; enforce `vram_budget_bytes` by selecting hash-table size/precision and freeing transient ray buffers at lease end (Instant-NGP provides compact state layout but not parking/eviction protocols).

[R6]

#### NerfAcc

Paper Type: `Model Accelerator`

(a) High-Level Architecture & System Design

NerfAcc is a PyTorch-oriented toolbox that aims to make NeRF acceleration via *efficient sampling* reusable across NeRF variants. It frames advanced sampling methods under a unified “transmittance estimator” view, provides plug-and-play APIs, and implements a rendering pipeline that supports spatial skipping (e.g., occupancy-grid sampling) and proposal-network sampling as modular components. [R7]

(b) Infrastructure & Hardware Assumptions

The toolbox is designed as a standalone library installable from PyPI and integrable into PyTorch codebases on Windows/Linux; it emphasizes performance via fusing operations into CUDA kernels while exposing Python APIs. The paper reports experiments conducted on a single NVIDIA RTX A5000 GPU for fair comparisons. [R7]

(c) Core Optimizations & Algorithmic Design

Core contributions are (i) a unifying formulation of sampling methods via transmittance estimation, and (ii) engineering a reusable implementation that incorporates two advanced sampling methods (occupancy-grid sampling from Instant-NGP and proposal-network sampling from mip-NeRF 360) while keeping the sampling step efficient and decoupled from particular radiance-field representations. [R7]

(d) Memory & Cache Management

NerfAcc introduces representations aimed at memory/efficiency of sampling: samples are represented as ray intervals, and variable-length per-ray samples are stored as “packed tensors” that keep only valid samples (avoiding dense (n_rays, n_samples, ...) tensors with large masked regions). It also describes filtering samples with gradients disabled to avoid carrying unnecessary samples through the autograd graph. Notably, these are accelerator-internal efficiency mechanisms, not a serving-runtime cache/eviction design. [R7]

(e) Request Scheduling & Batching

Not addressed (gap for serving-runtime design).

(f) Session & State Management

Not addressed (gap for serving-runtime design). (Direct evidence: NerfAcc defines estimator/model state such as occupancy grids and proposal networks used during sampling; it does not define multi-request session semantics, per-tenant isolation, or park/resume protocols across leases.) [R7]

(g) Hardware Parallelization & Resource Allocation

The paper emphasizes performance via fusing operations into CUDA kernels and structuring data as packed tensors for efficient GPU execution. It does not address multi-tenant GPU slicing, lease-aware allocation, or cross-request resource arbitration. [R7]

vRAN Edge Viability (ComputeLease) + ComputeLease Scorecard:

NerfAcc is **not** a multi-tenant serving runtime; it is mechanism evidence for efficient **ray sampling** and for representing variable-length ray samples compactly (packed tensors). For vRAN-edge viability, a serving container would need to add lease-aware request lifecycle, admission control, and explicit stop/park semantics.

| Axis | Score (High/Med/Low) | Evidence (Direct/Inferred) | Notes (boundary/unit/state/VRAM mechanism) | ComputeLease fields referenced |
| :--- | :--- | :--- | :--- | :--- |
| Preemption Resilience | Med | Inferred | Likely cooperative boundary at **ray-batch** or sampling-iteration boundaries; preemption not a design target in paper. See AH-M6-NERFACC-SEGMENT. | `preemption_notice_us`, `reclaim_mode`, `duration_us` |
| Micro-Segmentation | Med | Inferred | Natural unit is a **ray batch** (sampling + integration steps); packed-tensor structure may help keep per-batch work bounded, but microsecond-fit is not evaluated. See AH-M6-NERFACC-SEGMENT. | `duration_us`, `sm_budget_sms` |
| State Parking | Med | Inferred | State includes estimator structures (e.g., occupancy grid / proposal net) + model parameters; parking/resume is not specified. See AH-M6-NERFACC-PARK. | `reclaim_mode`, `preemption_notice_us` |
| Tight VRAM Compliance (≤60% stress) | Med | Inferred | Packed tensors reduce wasted sample storage; no explicit VRAM admission/eviction mechanism. See AH-M6-NERFACC-PARK. | `vram_budget_bytes` |

- **Adaptation hypothesis (AH-M6-NERFACC-SEGMENT)**: Use NerfAcc’s explicit sampling/rendering pipeline to define a **ray-batch** micro-segmentation boundary sized to fit `duration_us`, with cooperative stop points triggered by `preemption_notice_us` (NerfAcc provides efficient sampling primitives; the container must add lease-aware batch sizing and stop/resume policy).
- **Adaptation hypothesis (AH-M6-NERFACC-PARK)**: Park estimator state (e.g., occupancy grids / proposal-network weights) and per-scene model parameters outside VRAM between leases, and enforce `vram_budget_bytes` by bounding packed-sample buffers and freeing transient tensors at lease end (NerfAcc does not specify parking/eviction protocols).

[R7]

#### TensoRF

Paper Type: `Model Accelerator`

(a) High-Level Architecture & System Design

TensoRF represents a scene’s radiance field as an explicit 4D tensor corresponding to a 3D voxel grid with per-voxel multi-channel features, then factorizes this tensor into compact low-rank components (CP decomposition and a proposed vector-matrix (VM) decomposition). Density and view-dependent color are decoded from vector/matrix factors (with trilinear interpolation for continuity) to support volumetric rendering. [R8]

(b) Infrastructure & Hardware Assumptions

The implementation is described as standard PyTorch (explicitly “without customized CUDA kernels”), and the paper reports optimizing models on a single Tesla V100 GPU (16 GB) with ray batches (e.g., batch size 4096 pixel rays). [R8]

(c) Core Optimizations & Algorithmic Design

The central optimization is replacing per-voxel dense feature optimization with low-rank tensor factorization, reducing space complexity from O(n^3) to O(n) (CP) or O(n^2) (VM). It further uses coarse-to-fine reconstruction by upsampling vector/matrix factors and supports different decoders (MLP or spherical harmonics features). [R8]

(d) Memory & Cache Management

The paper provides direct evidence of compact model/state sizes (e.g., CP variants reported as <4 MB; VM variants retaining compact sizes such as <75 MB) and emphasizes lower memory footprint versus voxel-grid baselines; it does not, however, define serving-runtime cache admission/eviction behavior under a hard VRAM cap. [R8]

(e) Request Scheduling & Batching

Not addressed (gap for serving-runtime design).

(f) Session & State Management

Not addressed (gap for serving-runtime design). (Direct evidence: persistent model state is the set of tensor factors plus decoder parameters; the paper does not define multi-request session semantics, per-tenant isolation, or park/resume protocols across leases.) [R8]

(g) Hardware Parallelization & Resource Allocation

The work targets efficient single-GPU per-scene optimization/rendering in PyTorch and does not define multi-tenant resource allocation, GPU slicing, or lease-aware execution policies. [R8]

vRAN Edge Viability (ComputeLease) + ComputeLease Scorecard:

TensoRF is model-accelerator evidence for **bounded scene state** (compact tensor factors) and fast per-scene reconstruction; it does not define a serving runtime. Under ComputeLease, the primary benefit is that compact factorized state is easier to park/offload than dense voxel grids, but lease-aware admission/scheduling must be added by the container.

| Axis | Score (High/Med/Low) | Evidence (Direct/Inferred) | Notes (boundary/unit/state/VRAM mechanism) | ComputeLease fields referenced |
| :--- | :--- | :--- | :--- | :--- |
| Preemption Resilience | Med | Inferred | Likely cooperative boundary at **ray-batch** or optimization-step boundaries; no explicit preemption semantics. See AH-M6-TENSORF-SEGMENT. | `preemption_notice_us`, `duration_us` |
| Micro-Segmentation | Med | Inferred | Explicit ray batching exists (e.g., 4096 pixel rays in implementation); lease-fitting at microsecond scale not evaluated. See AH-M6-TENSORF-SEGMENT. | `duration_us`, `sm_budget_sms` |
| State Parking | High | Inferred | Model state is explicitly compact (reported MB-scale models), suggesting cheap park/restore; parking/resume protocol not specified. See AH-M6-TENSORF-PARK. | `reclaim_mode`, `preemption_notice_us`, `duration_us` |
| Tight VRAM Compliance (≤60% stress) | Med | Inferred | Compact factorized state reduces steady-state VRAM pressure versus dense voxel features; hard-cap compliance policies not defined. See AH-M6-TENSORF-PARK. | `vram_budget_bytes` |

- **Adaptation hypothesis (AH-M6-TENSORF-SEGMENT)**: Use **ray-batch** (and/or optimization-step) boundaries as cooperative stop points sized to fit `duration_us`, with draining on `preemption_notice_us` (TensoRF provides explicit batched-ray optimization; the container must add lease-aware batching + stop/resume).
- **Adaptation hypothesis (AH-M6-TENSORF-PARK)**: Park the tensor factors + decoder parameters to host RAM / local NVMe between leases and reload on demand; enforce `vram_budget_bytes` by keeping only the active scene factors resident in VRAM and freeing transient ray buffers (TensoRF provides compact state sizes but not a parking/eviction protocol).

[R8]

#### DirectVoxGO

Paper Type: `Model Accelerator`

(a) High-Level Architecture & System Design

DirectVoxGO accelerates per-scene radiance-field reconstruction by directly optimizing a **density voxel grid** for geometry and using a **feature voxel grid + shallow network** for view-dependent appearance; the method is designed to converge from scratch quickly (reported <15 minutes) and follows a pipeline of coarse geometry discovery followed by fine-detail/view-dependent reconstruction. [R9]

(b) Infrastructure & Hardware Assumptions

The paper reports per-scene training-time measurements on a single NVIDIA RTX 2080 Ti GPU and positions the method as single-GPU–friendly (<15 minutes per scene under their setup). [R9]

(c) Core Optimizations & Algorithmic Design

Two described techniques drive convergence/quality: (i) **post-activation interpolation** on voxel density to enable sharp surfaces at lower grid resolutions, and (ii) direct voxel density optimization with priors to avoid suboptimal geometry solutions; the approach explicitly avoids requiring a conversion step from a trained implicit model and avoids cross-scene pretraining. [R9]

(d) Memory & Cache Management

Direct evidence of memory-relevant state is the explicit density voxel grid plus feature voxel grid and shallow network. Not addressed (gap for serving-runtime design): no explicit VRAM admission control, eviction, or state paging design is provided (beyond choosing grid resolution/representation). [R9]

(e) Request Scheduling & Batching

Not addressed (gap for serving-runtime design).

(f) Session & State Management

Not addressed (gap for serving-runtime design). (Direct evidence: persistent model state is the voxel grids + shallow network parameters; the paper does not define multi-request session semantics, per-tenant isolation, or park/resume protocols across leases.) [R9]

(g) Hardware Parallelization & Resource Allocation

The work targets single-GPU efficiency (dense voxel-grid optimization + shallow network) and does not address multi-tenant resource allocation, GPU slicing, or lease-aware execution policies. [R9]

vRAN Edge Viability (ComputeLease) + ComputeLease Scorecard:

DirectVoxGO is model-accelerator evidence for replacing MLP-heavy NeRF evaluation with explicit voxel-grid state plus lightweight decoding. For ComputeLease viability, the main open issue is **state size vs. lease churn**: voxel grids may be cheap enough to keep resident on larger edge GPUs, but the paper does not provide lease-aware park/resume mechanisms.

| Axis | Score (High/Med/Low) | Evidence (Direct/Inferred) | Notes (boundary/unit/state/VRAM mechanism) | ComputeLease fields referenced |
| :--- | :--- | :--- | :--- | :--- |
| Preemption Resilience | Med | Inferred | Plausible cooperative boundary at ray-batch boundaries during rendering/optimization; not an explicit design target. See AH-M6-DVGO-SEGMENT. | `preemption_notice_us`, `duration_us` |
| Micro-Segmentation | Med | Inferred | Natural unit is **ray batch**; lease-fitting at microsecond scale not evaluated. See AH-M6-DVGO-SEGMENT. | `duration_us`, `sm_budget_sms` |
| State Parking | Med | Inferred | State = density + feature voxel grids + shallow network; parking/resume not specified and state size depends on grid resolution. See AH-M6-DVGO-PARK. | `reclaim_mode`, `preemption_notice_us` |
| Tight VRAM Compliance (≤60% stress) | Med | Inferred | Grid resolution is a knob; no explicit VRAM cap enforcement/eviction is described. See AH-M6-DVGO-PARK. | `vram_budget_bytes` |

- **Adaptation hypothesis (AH-M6-DVGO-SEGMENT)**: Use **ray-batch** boundaries as cooperative stop points and size per-batch work to `duration_us`, draining on `preemption_notice_us` (DirectVoxGO provides voxel-grid rendering/optimization structure; the container must add lease-aware batching + stop/resume).
- **Adaptation hypothesis (AH-M6-DVGO-PARK)**: Park voxel grids + shallow network parameters to host RAM / NVMe between leases and reload/rehydrate on demand; enforce `vram_budget_bytes` via grid-resolution selection and by freeing transient per-ray buffers at lease end (DirectVoxGO does not specify a parking/eviction protocol).

[R9]

##### Serving-runtime evidence gap

All four M6 primaries are **Model Accelerators** (Instant-NGP, NerfAcc, TensoRF, DirectVoxGO). As such, they provide strong evidence for *workload-specific mechanisms* (scene representation compactness, efficient sampling/ray marching, CUDA/PyTorch implementation choices) but provide little to no direct evidence for a **multi-tenant serving runtime** under ComputeLease.

Concretely, across (a)–(g) the dominant gaps for serving-runtime design are:

- **(e) Request scheduling & batching**: none of the primaries define queueing/admission, deadline/priority handling, or multi-tenant batching policies.
- **(f) Session/state management**: while each defines persistent *model state* (hash tables, voxel grids, tensor factors, estimators), none specifies lease-aware **state parking/resume**, per-tenant state isolation, or recovery semantics.
- **(g) Resource allocation**: none addresses vRAN-style bursty GPU slices (MIG/MPS), reclaim semantics, or interference control across tenants.

Therefore, any vRAN-edge NeRF container that adopts these accelerators must treat them as **mechanism components** and add an explicit serving-runtime layer for ComputeLease-driven admission control, micro-segmentation policy, and state parking.

##### Bridge mechanisms (non-primary)

The following **non-primary** serving/runtime systems are included only as *bridge mechanism evidence* for the missing serving-runtime axes above (especially VRAM hard-cap compliance and state parking). They are not NeRF systems, but they provide concrete patterns that can be adapted:

- **vLLM / PagedAttention**: demonstrates KV-cache paging/eviction for LLM serving to stabilize VRAM use under many concurrent sequences; the paging concept is a direct blueprint for “state parking” and “tight VRAM compliance” mechanisms that M6 primaries do not define. Adaptation hypothesis: a NeRF container could page scene/estimator state (occupancy grids, hash tables, voxel factors) across leases using similar indirection + eviction principles. [R10]
- **FlexGen**: provides an explicit offload pipeline for generative inference (GPU↔CPU↔disk) and a scheduling plan that trades compute for bandwidth to fit large models on a single GPU. This is bridge evidence for *how* to implement state parking/offload when VRAM is the limiting lease dimension. [R11]
- **DeepSpeed-Inference (ZeRO-Inference)**: provides inference-time partition/offload and memory-management mechanisms for transformer inference at scale; included here as bridge evidence for systematically bounding model/state residency under VRAM caps and reclaim events. [R12]

---

## Cross-cutting Mechanism Synthesis

Across M1–M6, the **ComputeLease** contract turns “GPU availability” into a short-lived envelope with explicit bounds on time (`start_time_us`, `duration_us`), effective compute width (`sm_budget_sms`), and VRAM (`vram_budget_bytes`), plus explicit reclaim semantics (`preemption_notice_us`, `reclaim_mode`) and policy (`priority_tier`). The primary systems in this review contribute complementary *mechanism* evidence for operating inside such envelopes:

- **Interference-aware consolidation + resource estimation** for one-shot CV/SR (USHER, RAVAS) and **fine-grained kernel-boundary scheduling** (Orion).
- **Portion/pipeline decomposition** for multi-stage one-shot workloads (OctopInf/CORAL, PPipe).
- **Phase/iteration aware serving** for streaming transformers (vLLM/PagedAttention, Orca, DistServe).
- **Preemption + state movement primitives** for streaming sessions (SpotServe, CacheGen), plus offload/paging patterns used as bridge mechanisms where primaries lack serving-runtime semantics.

M6 primaries (Instant-NGP, NerfAcc, TensoRF, DirectVoxGO) are **model accelerators**: they provide strong evidence for *what state exists* (hash tables, voxel grids, tensor factors) but not how to run multi-tenant under leases. Therefore, the synthesis below treats the M6 primaries as state-definition evidence and imports serving-runtime patterns (already discussed in M3/M4/M5/M6 bridge notes) for the missing runtime mechanisms.

### Lease-aware admission control

Admission control is the first cross-cutting mechanism: it decides what work can safely start (or continue) within a lease such that the container can still honor early reclaim/end-of-lease behavior.

- **Mechanism evidence in the review**:
  - USHER/RAVAS: pre-dispatch estimation and interference-aware consolidation for one-shot inference.
  - OctopInf/CORAL: stage-aware feasibility checks for portioned workloads (typically at coarse, ms-scale portions absent further refinement).
  - Proteus: variant/accuracy scaling as a first-class lever under strict latency constraints.
  - Orca/DistServe: phase/iteration budgeting and separation of prefill vs decode resource envelopes.

- **Adaptation hypothesis (AH-T9-LEASE-ADMISSION)**: Implement a **lease-aware admission gate** that consumes `duration_us`, `sm_budget_sms`, `vram_budget_bytes`, and `priority_tier` to accept/reject/defer work at the *micro-segmentation unit* granularity (not only per-request). What the papers provide: (i) resource estimation + consolidation heuristics (USHER/RAVAS), (ii) portion-/stage-feasibility framing (OctopInf/CORAL), and (iii) bounded-iteration serving for streaming sessions (Orca/DistServe). What the vRAN-edge container adds: a unified admission decision that also accounts for `preemption_notice_us` and `reclaim_mode` (must-stop vs best-effort) and optionally pins/filters by `gpu_id`/`gpu_slice` when hard isolation is required.

### Micro-segmentation engine

ComputeLease forces a cross-cutting requirement: every workload must expose a *cooperative stop point* and a minimum executable unit that can be made to fit `duration_us` while remaining safe under `reclaim_mode`.

- **Mechanism evidence in the review**:
  - Orion: operator/kernel boundary scheduling (fine granularity) where the model is expressed as schedulable kernels.
  - Orca: iteration-level scheduling at token-step boundaries (natural for M3/M4).
  - CacheGen: chunk boundaries as a practical “pause/commit” unit for KV state movement.
  - M6 primaries: ray-batch structure and compact scene-state representations that can serve as natural *work units* but do not specify lease-fitting logic.

- **Adaptation hypothesis (AH-T9-MICROSEG-ENGINE)**: Provide a **micro-segmentation engine** that selects (and enforces) the smallest safe unit per workload class as a function of `duration_us`, `sm_budget_sms`, `preemption_notice_us`, and `reclaim_mode`. What the papers provide: (i) fine-grained boundaries (Orion, token-step in Orca), and (ii) chunk/batch units (CacheGen KV chunks; ray-batches in M6 accelerators). What the container adds: (a) a uniform representation of “unit runtime budget” tied to the current lease, and (b) explicit fallback rungs when the finest unit is unavailable (e.g., for one-shot CV, any segmentation finer than frame-level is **not** directly claimed by the CV serving papers and must be implemented as a cooperative tiling/patching policy sized to `duration_us`).

### State parking interface

State parking is the cross-cutting mechanism that makes lease gaps and early reclaim survivable: when compute is unavailable (or about to be reclaimed), the container must persist enough state to resume later, while freeing VRAM to respect `vram_budget_bytes`.

- **Mechanism evidence in the review**:
  - vLLM/PagedAttention: explicit paging/swap/recompute patterns for KV caches to bound VRAM growth.
  - SpotServe: preemption-aware “commit” semantics and context migration planning.
  - CacheGen: chunked KV compression + storage-backed streaming, offering an explicit unit for park/resume.
  - M6 primaries: define the persistent *scene state* (hash tables, voxel grids, tensor factors) that would need to be parked, but do not provide a protocol.

- **Adaptation hypothesis (AH-T9-STATE-PARK-API)**: Implement a workload-agnostic **State parking interface** that (i) freezes execution at a micro-segmentation boundary, (ii) emits a “park bundle” to host RAM / local NVMe / remote store selected using `bandwidth_budget_hint` (optional), and (iii) releases VRAM allocations to return under `vram_budget_bytes` before reclaim. What the papers provide: explicit KV and context movement building blocks (vLLM/SpotServe/CacheGen). What the container adds: a unified park/resume protocol usable by both streaming (M3/M4) and non-streaming workloads that still have persistent artifacts (e.g., M6 scene representations), with reclaim behavior driven by `preemption_notice_us`, `reclaim_mode`, and `lease_id` (for audit/trace of what was parked under which lease).

### Memory budgeter / fragmentation control

Under ComputeLease, VRAM is not “best effort”; it is a hard cap. Across workloads, VRAM pressure arises from distinct state types (activation-heavy one-shot CV/SR, KV caches for streaming, scene-state for NeRF). A cross-cutting subsystem is required to (a) allocate predictably within `vram_budget_bytes`, (b) keep headroom for fragmentation and transient buffers, and (c) coordinate eviction/offload with the state parking interface.

- **Mechanism evidence in the review**: vLLM’s paged KV blocks show how to avoid unbounded fragmentation growth in a dynamic cache; Aqua provides a concrete pattern for memory offload as a resource-control primitive; Proteus provides variant choice as a mechanism to shrink the working set when strict envelopes are violated.

- **Adaptation hypothesis (AH-T9-MEM-BUDGETER)**: Add a **memory budgeter/fragmentation control** module that converts `vram_budget_bytes` (and optional `gpu_slice`/`gpu_id`) into per-tenant/per-session allocation ceilings and triggers (i) cache paging/eviction, (ii) state parking/offload, or (iii) variant downgrade guided by `priority_tier`. What the papers provide: paging/offload/variant mechanisms; what the container adds: a unified accounting model spanning one-shot activations, KV caches, and “scene state,” plus reclaim-mode-aware headroom rules so that `reclaim_mode: hard` leases always retain sufficient slack to quiesce.

### Multi-tenant isolation ladder

Isolation is not a binary decision in this corpus; the mechanisms form a ladder from hard partitioning (MIG) through controlled sharing (MPS + interference-aware placement) down to best-effort opportunistic co-location.

- **Mechanism evidence in the review**: USHER explicitly discusses MPS-driven sharing and contrasts it with MIG-style partitioning; Orion’s contribution is fine-grained scheduling within a shared GPU context; the summary matrix includes systems whose feasibility depends on whether the site offers a stable slice (`gpu_slice`) or only opportunistic width (`sm_budget_sms`).

- **Adaptation hypothesis (AH-T9-ISOLATION-LADDER)**: Implement a **multi-tenant isolation ladder** keyed by `priority_tier` and optional `gpu_slice` availability: (L0) dedicated `gpu_slice`/`gpu_id` for the highest tiers, (L1) MPS sharing with interference-aware admission/placement (USHER-style), (L2) fine-grained kernel scheduling (Orion-style) inside a shared slice when supported, and (L3) best-effort co-location only for low priority tiers where reclaim/latency risk is acceptable. What the container adds: explicit, configurable mapping from `priority_tier` to isolation rung so “acceptable sharing mode” is treated as policy, not an implicit side effect.

### Cross-cutting telemetry and feedback

Finally, ComputeLease makes control sensitivity a first-class constraint: control decisions must be driven by observable signals that correlate with “lease trouble.” DistServe’s TTFT/TPOT framing (and the report’s matrix vocabulary around stage pressure and jitter sensitivity) motivates a minimal telemetry set: per-work-unit runtime vs `duration_us`, VRAM headroom vs `vram_budget_bytes`, and for streaming workloads, TTFT and per-iteration service time as stall proxies.

## Unified Architecture Synthesis

This section turns the mechanism palette above into a unified, repo-aligned architecture for vRAN-edge inference under **ComputeLease**. The external scheduler/allocator is still out of scope; the design here is the **container-level control and data plane** that consumes the canonical `ComputeLease` contract.

### Explicit alignment with repo tiering language

Repo tier names (from `llm-ran-obsidian-vault/architecture/reference-architecture.md`) are used as the primary vocabulary here. The RAN-native control layers referenced elsewhere in the report (“SMO / Non-RT / Near-RT / DU-local”) map onto these tiers as a *cross-reference*:

- **Tier 2 (RAN control)** corresponds to the Near-RT/DU-local control surface for budget planning + dispatch.
- **Tier 5/6 (Regional/central + validation)** correspond to SMO/Non-RT policy, model lifecycle, and validation loops.

If a reader prefers the RIC/SMO naming, use that mapping; the tier names below remain the canonical repo language.

| Repo Tier | Tier label | Role in this synthesis | ComputeLease touchpoint |
| :--- | :--- | :--- | :--- |
| Tier 0 | Device | Prompt capture; optional local fallback | No direct lease; may tag requests with desired `priority_tier` via policy |
| Tier 1 | Far-edge gateway | Policy enforcement (privacy redaction), prompt compression, retrieval cache | May reduce admission pressure by shrinking inputs; no direct lease |
| Tier 2 | RAN control | Latency planner + compute dispatcher; mediates when a site can safely export compute | Produces/forwards `ComputeLease` (including `start_time_us`, `duration_us`, `sm_budget_sms`, `vram_budget_bytes`, `preemption_notice_us`, `reclaim_mode`, `priority_tier`) |
| Tier 3 | MEC inference plane | Latency-critical serving workers; session manager and KV-cache anchor | Primary lease consumer for Lane B decode and stateful session continuity; may require fixed `gpu_slice` |
| Tier 4 | AI-RAN spare-compute plane | Opportunistic work compatible with the spare-compute envelope | Lease consumer for Lane A stateless/preemption-tolerant work and (when safe) prefill/auxiliary phases |
| Tier 5 | Regional / central AI cluster | Overflow inference; global cache + model lifecycle management | Source of non-lease compute when MEC/AI-RAN envelopes are uncertain |
| Tier 6 | Validation / digital twin | CHRONOS-style validation for timing/control sensitivity | Validates control policies and micro-segmentation choices rather than serving directly |

### Control-plane vs data-plane decomposition (container-focused)

The unified architecture is intentionally a containerized split: a CPU-heavy control plane that reacts to leases and telemetry, and a GPU-heavy data plane that runs the actual model execution.

**Control plane (per-site; runs in Tier 3 and/or Tier 4 alongside serving workers):**

1. **ComputeLease ingest + normalization**: validates required fields (`lease_id`, `start_time_us`, `duration_us`, `sm_budget_sms`, `vram_budget_bytes`, `preemption_notice_us`, `reclaim_mode`, `priority_tier`) and binds optional placement constraints (`gpu_id`, `gpu_slice`).
2. **Lease-aware admission control**: uses the current lease envelope to accept/reject/defer work (AH-T9-LEASE-ADMISSION).
3. **Micro-segmentation engine**: selects the micro-unit and cooperative stop points per workload/lane (AH-T9-MICROSEG-ENGINE).
4. **Memory budgeter/fragmentation control**: enforces `vram_budget_bytes` with reclaim-aware slack and triggers eviction/parking/degradation (AH-T9-MEM-BUDGETER).
5. **Isolation policy manager**: selects the multi-tenant isolation rung (MIG slice vs shared MPS, etc.) as an explicit policy keyed by `priority_tier` and `gpu_slice` availability (AH-T9-ISOLATION-LADDER).
6. **State parking orchestrator**: schedules park/resume actions at reclaim boundaries, choosing host RAM / local NVMe / remote store using `bandwidth_budget_hint` when provided (AH-T9-STATE-PARK-API).
7. **Telemetry + feedback**: exports TTFT/throughput proxies (streaming) and lease-fit/VRAM headroom signals to Tier 2 planners.

**Data plane (GPU workers; runs in Tier 3 and Tier 4):**

- **Lane A executor** (stateless / preemption-tolerant): runs one-shot workloads at frame-level boundaries (M1/M2/M5) and any additional work units whose restart cost is acceptable under reclaim.
- **Lane B executor** (stateful streaming): runs streaming transformer decode (M3/M4) and any stateful sessions requiring a session manager + state parking.
- **Session manager / KV-cache anchor**: maintains affinity for stateful sessions (Tier 3 default), coordinating with state parking to survive lease gaps.
- **State store backends**: host RAM / local NVMe / remote store endpoints used by the state parking interface; these are implementation choices, not new primary systems.

### 2-lane execution sketch

The lanes exist to avoid a “worst-case-for-everyone” runtime. They are a synthesis decision (no single paper proposes this exact split) but each lane is grounded in mechanisms already discussed.

- **Adaptation hypothesis (AH-T9-TWO-LANES)**: Use a **2-lane execution model**:
  - **Lane A (stateless / preemption-tolerant)**: prioritize work where the safe stop point is coarse but restartable (frame-level one-shot CV/SR; ray-batch units when the state is cheaply reconstructable). Leases can be shorter and more opportunistic; admission is conservative and may defer work when `reclaim_mode: hard` and `duration_us` is too short for the coarse boundary.
  - **Lane B (stateful streaming)**: prioritize work where the micro-unit is naturally fine-grained but state must persist (token-step decode with KV cache). Lane B is paired with the State parking interface so `preemption_notice_us` becomes an actionable “commit” window. This lane should preferentially bind to stable `gpu_slice` when available.
  What the papers provide: token-iteration micro-units (Orca), paged KV memory control (vLLM), phase separation (DistServe), and explicit preemption/commit semantics (SpotServe, CacheGen). What the container adds: an explicit lane split and queueing policy keyed by `priority_tier` and lease volatility.

### Rejected alternatives

1. **Single-lane unified executor for all workloads** (no explicit stateless/stateful split). Rejected because it conflates workloads whose “state” is primarily ephemeral activations (M1/M2/M5) with workloads whose state is a persistent session artifact (M3/M4 KV cache). The result is either (a) unnecessary state parking overhead for stateless jobs or (b) fragile session semantics for streaming.
2. **No state parking; rely on keeping all state resident in VRAM between leases.** Rejected because ComputeLease explicitly constrains `vram_budget_bytes` and models hard reclaim (`reclaim_mode: hard`). The review’s own M6 evidence gap also makes clear that relying on persistent VRAM residency is not justified by the primaries.
3. **Always bind both prefill and decode to the same opportunistic pool.** Rejected because the repo’s reference architecture distinguishes Tier 3 (latency-critical serving + session manager) from Tier 4 (spare-compute envelope). A unified opportunistic pool forces latency-critical decode to inherit reclaim volatility.

### Residual risks & assumptions

**Assumptions (explicit):**

- A scheduler exists that issues the canonical `ComputeLease` fields as defined earlier; the container does not invent or rename contract fields.
- Sites can enforce (or at least observe) VRAM envelopes sufficiently to implement `vram_budget_bytes`-aware admission and memory budgeting.
- A state store path exists (host RAM, local NVMe, and/or remote store) with enough stability for State parking, and `bandwidth_budget_hint` is either available or treated as unknown.

**Residual risks (even if implemented correctly):**

- **Lease-fit prediction risk**: one-shot workloads (M1/M2/M5) may still have coarse preemption boundaries, so very short `duration_us` windows can cause chronic deferral or wasted partial work.
- **State movement tail risk**: parking/resume latency is workload- and medium-dependent; without tight control, it can dominate end-to-end latency for Lane B.
- **Fragmentation/thrash risk**: even with budgeting, dynamic allocation patterns can induce fragmentation; the memory budgeter must be conservative enough to preserve reclaim slack.
- **Isolation-policy risk**: selecting a weaker rung for too-high `priority_tier` can reintroduce interference collapse; selecting too-strong isolation can waste scarce slices and reduce goodput.
- **Control sensitivity risk**: control-plane delays (telemetry lag, planning delay) can be a first-order fraction of the useful lease, especially when using micro-segmentation at very fine granularity.

## References

[R1] Sudipta Saha Shubha, Haiying Shen, Anand Iyer. “USHER: Holistic Interference Avoidance for Resource Optimized ML Inference.” 18th USENIX Symposium on Operating Systems Design and Implementation (OSDI 2024), 2024. https://www.usenix.org/system/files/osdi24-shubha.pdf

[R2] Foteini Strati, Xianzhe Ma, Ana Klimovic. “Orion: Interference-aware, Fine-grained GPU Sharing for ML Applications.” Nineteenth European Conference on Computer Systems (EuroSys ’24), 2024. https://doi.org/10.1145/3627703.3629578 (open PDF mirror: https://anakli.inf.ethz.ch/papers/orion_eurosys24.pdf)

[R3] Z. Jonny Kong, Qiang Xu, Y. Charlie Hu. “PPipe: Efficient Video Analytics Serving on Heterogeneous GPU Clusters via Pool-Based Pipeline Parallelism.” 2025 USENIX Annual Technical Conference (ATC 2025), 2025. https://www.usenix.org/system/files/atc25-kong.pdf

[R4] Ali Rahmanian, Björn Skubic, Ahmed Ali-Eldin, Selome Kostentinos Tesfatsion, Harald Gustafsson, Prashant Shenoy, Erik Elmroth. “RAVAS: Interference-Aware Model Selection and Resource Allocation for Live Edge Video Analytics.” IEEE/ACM Symposium on Edge Computing (SEC 2023), 2023. https://doi.org/10.1145/3583740.3628443 (open PDF: https://lass.cs.umass.edu/papers/pdf/sec2023-ravas.pdf)

[R5] Thanh-Tung Nguyen, Lucas Liebe, Nhat-Quang Tau, Yuheng Wu, Jinghan Cheng, Dongman Lee. “OCTOPINF: Workload-Aware Inference Serving for Edge Video Analytics.” IEEE International Conference on Pervasive Computing and Communications (PerCom 2025), preprint, 2025. https://doi.org/10.48550/arXiv.2502.01277 (arXiv: https://arxiv.org/abs/2502.01277)

[R6] Thomas Müller, Alex Evans, Christoph Schied, Alexander Keller. “Instant Neural Graphics Primitives with a Multiresolution Hash Encoding.” ACM Transactions on Graphics (SIGGRAPH 2022), 2022. https://doi.org/10.1145/3528223.3530127 (arXiv: https://arxiv.org/abs/2201.05989)

[R7] Ruilong Li, Hang Gao, Matthew Tancik, Angjoo Kanazawa. “NerfAcc: Efficient Sampling Accelerates NeRFs.” ICCV 2023. https://openaccess.thecvf.com/content/ICCV2023/papers/Li_NerfAcc_Efficient_Sampling_Accelerates_NeRFs_ICCV_2023_paper.pdf (arXiv: https://arxiv.org/abs/2305.04966)

[R8] Anpei Chen, Zexiang Xu, Andreas Geiger, Jingyi Yu, Hao Su. “TensoRF: Tensorial Radiance Fields.” ECCV 2022. https://doi.org/10.48550/arXiv.2203.09517 (arXiv: https://arxiv.org/abs/2203.09517)

[R9] Cheng Sun, Min Sun, Hwann-Tzong Chen. “Direct Voxel Grid Optimization: Super-fast Convergence for Radiance Fields Reconstruction.” CVPR 2022. https://doi.org/10.1109/CVPR52688.2022.00538 (open PDF: https://openaccess.thecvf.com/content/CVPR2022/papers/Sun_Direct_Voxel_Grid_Optimization_Super-Fast_Convergence_for_Radiance_Fields_Reconstruction_CVPR_2022_paper.pdf)

[R10] W. Kwon, Z. Li, S. Zhuang, Y. Sheng, L. Zheng, C. H. Yu, J. Gonzalez, H. Zhang, I. Stoica. “Efficient Memory Management for Large Language Model Serving with PagedAttention.” Symposium on Operating Systems Principles (SOSP 2023), 2023. https://doi.org/10.1145/3600006.3613165

[R11] Ying Sheng, Lianmin Zheng, Binhang Yuan, Zhuohan Li, Max Ryabinin, Daniel Y. Fu, Zhiqiang Xie, Beidi Chen, Clark Barrett, Joseph E. Gonzalez, Percy Liang, Christopher Ré, Ion Stoica, Ce Zhang. “FlexGen: High-Throughput Generative Inference of Large Language Models with a Single GPU.” arXiv, 2023. https://doi.org/10.48550/arXiv.2303.06865 (arXiv: https://arxiv.org/abs/2303.06865)

[R12] Reza Yazdani Aminabadi, Samyam Rajbhandari, Ammar Ahmad Awan, Chao Li, Dacheng Li, Erwin Zheng, Olatunji Ruwase, Shaden Smith, Mengzhou Zhang, Jeff Rasley, Yuxiong He. “DeepSpeed-Inference: Enabling Efficient Inference of Transformer Models at Unprecedented Scale.” SC22: International Conference for High Performance Computing, Networking, Storage and Analysis (SC ’22), 2022. https://doi.org/10.1109/SC41404.2022.00051

[R13] Abhishek Vijaya Kumar, Gianni Antichi, Rachee Singh. “AQUA: Network-Accelerated Memory Offloading for LLMs in Scale-Up GPU Domains.” arXiv preprint arXiv:2407.21255, 2024. https://doi.org/10.48550/arXiv.2407.21255

[R14] Ahmad Sadek, Hongyu Guan, Benjamin D. Friedman, Thomas Williams, Ramesh K. Sitaraman, Tony Woo. “Proteus: A High-Throughput Inference-Serving System with Accuracy Scaling.” Proceedings of the 29th ACM International Conference on Architectural Support for Programming Languages and Operating Systems, Volume 1 (ASPLOS 2024), 2024. https://doi.org/10.1145/3617232.3624849

[R15] Gyeong-In Yu, Joo Seong Jeong, Geon-Woo Kim, Soojeong Kim, Byung-Gon Chun. “Orca: A Distributed Serving System for Transformer-Based Generative Models.” 16th USENIX Symposium on Operating Systems Design and Implementation (OSDI 2022), 2022. https://www.usenix.org/conference/osdi22/presentation/yu (open PDF: https://www.usenix.org/system/files/osdi22-yu.pdf)

[R16] Yinmin Zhong, Shengyu Liu, Junda Chen, Jianbo Hu, Yibo Zhu, Xuanzhe Liu, Xin Jin, Hao Zhang. “DistServe: Disaggregating Prefill and Decoding for Goodput-optimized Large Language Model Serving.” 18th USENIX Symposium on Operating Systems Design and Implementation (OSDI 2024), 2024. https://www.usenix.org/conference/osdi24/presentation/zhong-yinmin (open PDF: https://www.usenix.org/system/files/osdi24-zhong-yinmin.pdf)

[R17] Xupeng Miao, Chunan Shi, Jiangfei Duan, Xiaoli Xi, Dahua Lin, Bin Cui, Zhihao Jia. “SpotServe: Serving Generative Large Language Models on Preemptible Instances.” Proceedings of the 29th ACM International Conference on Architectural Support for Programming Languages and Operating Systems, Volume 1 (ASPLOS 2024), 2024. https://doi.org/10.1145/3620665.3640411 (arXiv: https://arxiv.org/abs/2311.15566)

[R18] Yuhan Liu, Hanchen Li, Yihua Cheng, Siddhant Ray, Yuyang Huang, Qizheng Zhang, Kuntai Du, Jiayi Yao, Shan Lu, Ganesh Ananthanarayanan, Michael Maire, Henry Hoffmann, Ari Holtzman, Junchen Jiang. “CacheGen: KV Cache Compression and Streaming for Fast Large Language Model Serving.” ACM SIGCOMM 2024, 2024. https://doi.org/10.1145/3651890.3672274 (arXiv: https://arxiv.org/abs/2310.07240)
