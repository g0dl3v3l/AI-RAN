# Multi-Tenant Edge/RAN Inference Scheduling

## Paper-by-Paper Evidence Matrix and Enhanced Workload Profiling Matrix

Prepared from the local paper corpus in `research paper/`.

## 1. Scope

This note consolidates the current research synthesis for a multi-tenant inference scheduler targeting latency-critical workloads in edge and RAN environments. It combines:

1. a **paper-by-paper evidence matrix** with explicit separation between **direct evidence** and **extrapolated inference**;
2. a **scheduler-facing parameter taxonomy** derived from the corpus; and
3. an **enhanced profiling matrix** for workloads M1–M6.

### Evidence policy

- **Direct evidence** means the property is explicitly grounded in the cited paper’s measurements, system design, equations, figures, or stated findings.
- **Extrapolated inference** means the property is not claimed verbatim by the paper, but is a careful scheduler-facing generalization derived from the paper’s methodology or bottlenecks.
- Where the corpus is weaker, the text explicitly softens the claim rather than treating it as a first-class intrinsic workload fact.

## 2. Corpus overview

| Paper | Role in synthesis | Main scheduler contribution | Citation |
| :--- | :--- | :--- | :--- |
| CORA | Primary scheduling paper | End-to-end RAN↔edge coordination, stage-aware budgeting, admission control, RB/SM demand modeling | [1] |
| SLA-Aware Distributed LLM Inference Across Device-RAN-Cloud | Primary SLA feasibility / placement paper | Strict-SLA feasibility across device/RAN-edge/cloud, TTFT as stall proxy, hard-MIG co-location evidence | [8] |
| Weaver | Primary scheduling paper | Multi-dimensional GPU pressure, slice elasticity, sharing overheads, slot-level shaping | [7] |
| LIDAR | Workload augmentation paper | Compression leverage, communication-dominated sensing, edge-offload energy effects | [4] |
| EdgeEye | Workload/microarchitecture augmentation paper | Inference-engine dependence, CPU/GPU staging and post-processing overhead | [3] |
| Paradrop | Orchestration/isolation paper | Containerized multitenancy, quotas, deploy/start overheads, network shaping, storage constraints | [6] |
| Lightweight Multitenancy at the Network’s Extreme Edge | Orchestration/isolation paper | Resource-limited extreme edge, managed policies, ownership and permission complexity | [5] |
| CHRONOS | Infrastructure/validation paper | Sub-ms timing sensitivity, slot barriers, fidelity requirements for scheduler evaluation | [2] |

## 3. Paper-by-paper evidence matrix

| Paper | Scheduler-facing topic | Direct evidence | Extrapolated inference | Citation |
| :--- | :--- | :--- | :--- | :--- |
| CORA | Dominant pipeline-stage pressure | CORA explicitly models and allocates separate **uplink**, **compute**, and **downlink** latency budgets, with RB demand derived from I/O size and channel quality and SM demand derived from a speedup model. The paper shows that the binding stage varies by workload and load condition. | A multi-tenant scheduler should represent each workload by its **dominant resource-domain pressure** rather than by a single end-to-end latency estimate. | [1] |
| CORA | Channel-quality sensitivity | Channel quality is a first-order input to RB demand estimation and is updated at runtime every 100 ms. Admission viability and latency-budget feasibility depend on it. | Workloads with larger transmitted inputs/outputs should expose **channel-quality sensitivity** as an admission and placement feature, especially under variable TDD or wireless congestion. | [1] |
| CORA | Pre-admission cost observability | CORA shows that request costing can be done with lightweight metadata and planner overhead (about 0.18 ms, 112 B/request metadata), before dispatch to the execution engine. | A scheduler should distinguish workloads whose cost can be estimated **before dispatch** from those whose runtime remains partially hidden until generation unfolds. | [1] |
| CORA | Goodput vs tail-latency tradeoff | CORA’s evaluation uses goodput, deadline satisfaction, and latency distributions rather than average latency alone. | Admission control should be designed around **deadline-constrained goodput** and **tail-risk**, not mean service time. | [1] |
| SLA-Aware Distributed LLM Inference Across Device-RAN-Cloud | SLA tiers and tier-feasibility envelope | The paper defines Premium (0.5 s), Medium (1.0 s), and Basic (≥1.0 s) service tiers, and directly measures device / RAN-edge / cloud feasibility. On-device execution remains multi-second and misses strict SLAs, edge Premium feasibility is mainly achieved by quantized variants, and cloud Premium feasibility is poor on the evaluated WAN path while Medium remains feasible. | A scheduler should represent **tier-feasibility envelopes** explicitly: the same workload variant may be infeasible on-device, edge-feasible under hard isolation, and WAN-limited in the cloud. | [8] |
| SLA-Aware Distributed LLM Inference Across Device-RAN-Cloud | TTFT as stall/queue proxy | The paper explicitly uses logged TTFT as a practical proxy for prefill/queue stalls and shows that strict deadline misses are tail-dominated and strongly associated with elevated TTFT under tight budgets. | For streaming/generative workloads, **TTFT can serve as a near-real-time stall signal** for admission, rerouting, or de-prioritization decisions even when full runtime is not yet known. | [8] |
| SLA-Aware Distributed LLM Inference Across Device-RAN-Cloud | Hard isolation contract under co-location | Fixed MIG partitioning, reserved slices, and Kubernetes priority enforcement preserve DU timing-health proxies and avoid throughput collapse under saturated downlink with up to N=20 concurrent inference clients in the tested setup. | Under tight RAN-coupled SLAs, **acceptable sharing mode** should be encoded as an operational contract (e.g., hard isolation versus opportunistic sharing), not left implicit. | [8] |
| SLA-Aware Distributed LLM Inference Across Device-RAN-Cloud | WAN-path dependence of remote tiers | The paper reports that cloud Premium misses are dominated by transport floor and tail excursions on the measured WAN path, whereas all variants meet 1.0 s deadlines. | Remote-tier feasibility should be profiled with a separate **transport-floor/tail dependence** dimension rather than attributed entirely to server-side compute. | [8] |
| SLA-Aware Distributed LLM Inference Across Device-RAN-Cloud | Quantization sensitivity for strict SLA | AWQ and certain 3B quantized variants are Premium-feasible at the edge, while FP16 and some 7B formats remain tail-limited. | Model variant and quantization format should be treated as **first-class scheduling knobs** for streaming transformer workloads rather than as offline-only model choices. | [8] |
| Weaver | Multi-dimensional GPU pressure | Weaver separates GPU usage into **SM Utilization (SMU)**, **Arithmetic Compute Utilization (ACU)**, and **Global Bandwidth Utilization (GBU)**. It shows that RAN LDPC is bandwidth-bound while FM training is compute-bound. | GPU-facing workload profiling should not collapse all accelerator demand into one number. It should track at least **arithmetic pressure**, **global-memory-bandwidth pressure**, and **SM occupancy width/slice demand** separately. | [7] |
| Weaver | GPU slice elasticity | Weaver demonstrates SM-envelope shaping, SM quantization, and sharing-mechanism overhead tradeoffs across MPS, MIG, Green Contexts, and related mechanisms. | Inference workloads should expose **GPU slice elasticity**: how gracefully they adapt to smaller SM allocations or changing slice sizes without violating latency targets. | [7] |
| Weaver | Scheduling granularity and jitter tolerance | Weaver’s controller operates at slot granularity and uses slot-bounded compute units and PRB↔SM lookup control. | The useful scheduling granularity of a workload should be explicit: token-step, ray-batch, coarse layer group, or full inference. This also implies a workload-specific **tolerance to scheduler jitter**. | [7] |
| Weaver | What should *not* be overgeneralized | Weaver’s exact-once ownership, rerouting, debt accounting, and model-layout rebalancing are part of an FM training system with distributed mutable state. | These mechanisms should **not** be imported wholesale into inference semantics. For inference, the transferable part is mainly the **resource-shape abstraction** and **sharing overhead awareness**, not training-state migration or exact-once training logic. | [7] |
| LIDAR | Compression leverage | LIDAR shows that raw point clouds are substantially larger than image inputs, that compressive offloading materially reduces latency, and that Octree Resolution / Point Resolution are explicit knobs. | Communication-heavy inference modalities should expose **compression leverage** as a first-class scheduler parameter when network transfer, not model FLOPs alone, drives latency. | [4] |
| LIDAR | Edge-offload energy benefit | The paper reports that offloading is always beneficial from a device energy-efficiency perspective, even when real-time latency is still missed. | For device-attached sensing workloads, schedulers should consider **device-energy benefit from edge offload** separately from latency benefit. A policy may offload even if latency is only modestly improved. | [4] |
| LIDAR | Future partitioning cost model | The paper explicitly identifies dynamic model partitioning and layer-wise profiling as future work for large-scale point-cloud segmentation. | Layer-wise partition cost and intermediate-representation size should be treated as future scheduler inputs for large, communication-heavy models, but not claimed as already validated by this paper. | [4] |
| EdgeEye | CPU-side staging and post-processing | EdgeEye states that buffer management and post-processing are the hardest parts of element implementation on the CPU side, and uses CUDA mapped memory to simplify CPU↔GPU movement. | Workloads should expose **CPU-side pre/post-processing and host↔GPU staging sensitivity** as separate from nominal model complexity. This matters for scheduling and placement. | [3] |
| EdgeEye | Inference-engine dependence | EdgeEye shows materially different throughput when using optimized vendor inference engines (TensorRT, FP16) versus framework-level execution. | Performance profiles should be tied to the **serving stack** and not only to the model family; a scheduler may need different profiles for the same model under different runtimes. | [3] |
| Paradrop | Quotas and edge-node scarcity | Paradrop explicitly manages CPU, memory, network, and disk quotas, and emphasizes that edge nodes are resource-limited compared with cloud servers. | Multi-tenant inference placement at the extreme edge must carry **non-GPU constraints**—CPU, memory, bandwidth, and storage—as admission-time resources, not as afterthoughts. | [6] |
| Paradrop | Deployment and lifecycle overhead | Paradrop reports deploy/start/stop/delete overheads and discusses network shaping and storage quotas. | Cold-path orchestration cost should be represented explicitly for workloads that depend on rapid service instantiation or movement across nodes. | [6] |
| Lightweight Multitenancy | Ownership and policy complexity | The article emphasizes managed policy design, permission management, and the difference between user/ISP-owned edge resources and centrally owned cloud resources. | **Preferred isolation mechanism** should be treated as a policy/configuration question rather than an intrinsic workload property. The workload matrix should instead encode what sharing modes are acceptable under its latency budget. | [5] |
| CHRONOS | Sub-ms timing sensitivity | CHRONOS shows that VM interruption and network latencies can consume large fractions of a slot budget, and that faithful emulation requires real scheduler code and slot-level barriers. | Scheduler evaluation for RAN-adjacent workloads must preserve **timing fidelity**, **release synchrony**, and **jitter sensitivity**. A workload can look admissible in coarse simulation but fail in slot-realistic environments. | [2] |
| CHRONOS | Release synchrony | Chronos uses the slot as the natural synchronization barrier for emulation components. | **Release pattern / arrival synchrony** should be a first-class profiling dimension. Periodic slot-aligned arrivals, bursty interactive sessions, and smooth streams create very different queueing behavior. | [2] |

## 4. Promoted scheduler-facing parameter additions

The following parameters are strong enough to be promoted into the master profiling matrix.

| Parameter | Why it is first-class | Main grounding |
| :--- | :--- | :--- |
| Dominant pipeline-stage pressure (UL / Compute / DL) | Determines which domain is actually binding the request under multi-resource contention | CORA [1] |
| Channel-quality sensitivity | Affects RB demand, admission viability, and effective stage budget | CORA [1] |
| Release pattern / arrival synchrony | Governs queue buildup, batching opportunity, and collision structure | CORA [1], CHRONOS [2] |
| Pre-admission cost observability | Distinguishes workloads that can be costed accurately before dispatch from those that unfold online | CORA [1] |
| TTFT / stall-proxy observability | Gives a practical near-real-time signal of prefill stalls and queue buildup for streaming/generative workloads under tight budgets | SLA-aware distributed inference [8] |
| Quantization sensitivity for strict-SLA feasibility | Variant choice can shift the same workload from Premium-infeasible to Premium-feasible on identical edge hardware | SLA-aware distributed inference [8] |
| Remote-tier transport-floor dependence | Distinguishes remote execution that is compute-limited from remote execution that is WAN-limited | SLA-aware distributed inference [8] |
| Arithmetic compute pressure | Separates FLOP-heavy tenants from others even on the same GPU | Weaver [7] |
| Global memory-bandwidth pressure | Captures bandwidth-bound interference that scalar “GPU utilization” misses | Weaver [7] |
| SM occupancy width / slice demand | Encodes how much spatial GPU width a request naturally wants | CORA [1], Weaver [7] |
| GPU slice elasticity | Encodes how gracefully the workload tolerates smaller or changing slices | Weaver [7] |
| CPU-side pre/post-processing & host↔GPU staging sensitivity | Captures runtime overhead outside the core model kernels | EdgeEye [3] |
| Compression leverage (network-facing) | Important when input transfer dominates or can be traded against compute | LIDAR [4] |
| Expected device-energy benefit from edge offload | Relevant for device-attached sensing and battery-sensitive pipelines | LIDAR [4] |
| Interference-induced tail-latency sensitivity | Reflects vulnerability to co-tenant contention and runtime variability | CORA [1], CHRONOS [2] |
| Minimum useful scheduling granularity | Indicates whether the scheduler can act at token, batch, tile, or full-inference level | Weaver [7] plus workload-specific extrapolation |
| Tolerance to scheduler jitter / control-plane delay | Important in sub-ms and streaming environments | CHRONOS [2], Weaver [7] |
| Deadline miss-cost / SLO hardness | Better framing than generic “priority”; tells the scheduler how expensive a miss is | CORA [1] plus careful extrapolation |
| Persistent local artifact / storage footprint | Affects placement, cold-cache behavior, and storage-constrained edge nodes | Paradrop [6], LLM/stateful workload extrapolation |

The new SLA paper [8] makes three additional dimensions much more concrete for **M3/M4-like streaming transformer workloads**: **TTFT as a practical stall proxy**, **quantization sensitivity under strict budgets**, and **WAN-path dependence of cloud feasibility**. These are promoted here as scheduler-facing parameters, but only TTFT is reflected directly inside the M1–M6 table below because the paper’s direct measurements are concentrated on LLM/VLM-style workloads rather than the full workload set.

## 5. Weak or softened extrapolations

The following ideas are useful, but should **not** be treated as hard intrinsic workload facts from the current paper set:

1. **Training-state migration cost** from Weaver should not be copied directly into inference. For inference, the safer abstraction is **request/session-state transfer cost** or **artifact/cache locality sensitivity**. [7]
2. **Exact-once ownership/accounting** in Weaver is a training-runtime correctness mechanism, not a generic inference property. [7]
3. **Co-location affinity** between compute-bound and memory-bound tenants is best treated as **heuristic scheduling guidance**, not as paper-grounded workload truth. [7]
4. **Preferred isolation mechanism** is not intrinsic to a workload. The scheduler should instead encode which isolation modes are acceptable under latency budget, hardware availability, and orchestration constraints. The new SLA paper strengthens the case for **hard MIG isolation** as an operational contract for safe RAN+AI co-location in the tested setup, but this is still not a universal per-workload mechanism preference. [5][6][7][8]
5. **Compression leverage** should be applied selectively to communication-heavy, compressible modalities; LIDAR supports this strongly, but the result should not be universalized across all models. [4]
6. The SLA paper’s device / edge / cloud feasibility results are strongest for **LLM/VLM-style streaming models** on the tested hardware and WAN path; they should not be universalized to all M1–M6 workloads without broader measurement coverage. [8]

## 6. Enhanced profiling matrix for M1–M6

The table below preserves the baseline matrix and appends the newly promoted scheduler-facing rows.

**SLA-paper note.** The new SLA paper [8] directly strengthens the interpretation of **M3/M4-like streaming transformer workloads**: strict-SLA feasibility depends strongly on quantized variant choice, TTFT tail excursions, hard isolation at the RAN edge, and WAN-path effects for cloud execution. These effects are not yet generalized into separate M1–M6 rows for all workload families because the paper does not measure the non-transformer workloads directly.

| Parameter | Image Segmentation (M1) | Pose Estimation (M2) | Language Processing (M3) | Translation (M4) | Super Resolution (M5) | Volume Rendering (M6) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Model Architecture** | CNN (DeepLabV3) | Transformer/CNN Hybrid | Auto-regressive Transformer | Seq2Seq Transformer | CNN/GAN (ESRGAN) | MLP (NeRF) |
| **Sub-Workloads** | 1. Feature Ext.<br>2. Upsampling | 1. Visual Feature Ext.<br>2. Attention Prop. | 1. Prefill (Prompt)<br>2. Decode (Gen) | 1. Encoder (Source)<br>2. Decoder (Target) | 1. Feature Ext.<br>2. Pixel-shuffle | 1. Ray Sampling<br>2. Vol. Integration |
| **Compute vs. Memory Bound** | Compute-bound | Compute-bound | **Prefill:** Compute<br>**Decode:** Memory | **Encoder:** Compute<br>**Decoder:** Memory | Highly Compute & Memory-bound | Extremely Compute-bound |
| **Delivery Mechanism** | One-shot | One-shot | Streaming | Streaming | One-shot | One-shot |
| **Input Size** | Fixed $(3\times196\times196)$ | Fixed $(2\times3\times112\times112)$ | Variable (Paper limit: 8 words) | Variable (Paper limit: 8 words) | Fixed $(3\times112\times112)$ | Fixed ray batch |
| **Output Size** | Fixed $(1\times196\times196)$ | Fixed $(16\times3)$ | Variable (Paper max: 16 words) | Variable (Paper max: 16 words) | Fixed $(3\times224\times224)$ | Fixed $(3\times196\times196)$ |
| **Static VRAM Footprint** | Low to Medium | Medium | High (LLM Weights) | High (Seq2Seq Weights) | Medium | Low (Small MLP weights) |
| **Dynamic VRAM Scaling** | Scales with $H \times W \times Batch$ | Scales with $H \times W \times Batch$ | Scales with $Batch \times Seq\_Len$ (KV Cache) | Scales with $Batch \times Seq\_Len$ (KV Cache) | Extreme (Massive activation maps) | Low (Scales purely with ray batch size) |
| **Cold-Start Latency** | Fast | Moderate | Slow (Heavy I/O weight loading) | Slow (Heavy I/O weight loading) | Moderate | Very Fast |
| **Max Optimal Batch Size** | High (Highly parallelizable) | High | Bound by KV Cache limits | Bound by KV Cache limits | Very Low (Memory bottlenecks quickly) | Arbitrary (Rays can be infinitely grouped) |
| **Continuous Batching** | N/A | N/A | Highly Compatible (Token-level injection) | Highly Compatible (Token-level injection) | N/A | N/A |
| **Preemptibility** | Poor (High context-switch cost mid-layer) | Poor | Excellent (Can pause between tokens) | Excellent (Can pause between tokens) | Poor | Good (Can pause between ray batches) |
| **Execution Determinism** | Very High | Very High | Low (Output length dictates runtime) | Low (Output length dictates runtime) | Very High | High |
| **Precision** | FP16 | FP16 | FP16 | FP16 | FP16 | FP16 |
| **Generative AI Metrics** | N/A | N/A | TTFT & TBT apply; TTFT also serves as a practical stall/queue proxy under strict budgets | TTFT & TBT apply; TTFT also serves as a practical stall/queue proxy under strict budgets | N/A | N/A |
| **Dominant Pipeline-Stage Pressure (UL / Compute / DL)** | UL > Compute > DL | UL > Compute >> DL | Compute ≈ DL > UL | Compute ≈ DL > UL | Compute > DL; UL can bind under UL-scarce TDD | Compute > DL >> UL |
| **Channel-Quality Sensitivity** | High | High | Medium | Medium | High | Medium |
| **Release Pattern / Arrival Synchrony** | Periodic frame-driven; bursty under multi-camera load | Periodic paired-frame | Interactive bursty sessions | Interactive bursty sessions | Periodic frame-driven; burst-intolerant | Frame/query bursts; internal ray batches regular |
| **Pre-admission Cost Observability** | Very High | Very High | Medium (prompt known, decode length unknown) | Medium (source known, target length variable) | High | High |
| **Arithmetic Compute Pressure** | High | High | High in prefill; Medium in decode | High in encoder/prefill; Medium in decode | Very High | Very High |
| **Global Memory-Bandwidth Pressure** | Low-Medium | Medium | High in decode | High in decode | Very High | Low-Medium |
| **SM Occupancy Width / Slice Demand** | Medium-wide | Medium-wide | Narrow in decode; medium in prefill | Narrow-medium | Wide, but memory-limited | Wide; controlled by ray batch |
| **GPU Slice Elasticity** | Medium | Medium | High | High | Low | Very High |
| **CPU-side Pre/Post-Processing & Host↔GPU Staging Sensitivity** | Medium | Medium | Medium-High | Medium | Medium-High | Low-Medium |
| **Compression Leverage (Network-facing)** | Medium | Medium | Low | Low | High | High |
| **Expected Device-Energy Benefit from Edge Offload** | High | High | Medium | Medium | Very High | High |
| **Interference-Induced Tail-Latency Sensitivity** | Medium | Medium | Very High | High | Very High | Medium |
| **Minimum Useful Scheduling Granularity** | Per-inference / coarse layer group | Per-inference / coarse layer group | Per-token step | Per-token step | Per-inference / coarse tile | Per-ray-batch |
| **Tolerance to Scheduler Jitter / Control-Plane Delay** | Medium | Medium | Low | Low | Low-Medium | Medium |
| **Deadline Miss-Cost / SLO Hardness** | High; frame miss usually wastes full request | High | Mixed; soft per token, hard on TTFT | Mixed; soft per token, hard on end-to-end latency | High | Medium; progressive degradation possible |
| **Persistent Local Artifact / Storage Footprint** | Low | Low-Medium | High | High | Medium | Medium |

## 7. Interpretation notes for scheduler design

### 7.1 What the matrix now captures better

- It separates **where latency is spent** (UL, compute, DL) from **what kind of GPU pressure is induced** (compute vs bandwidth vs SM width).
- It distinguishes **service-time predictability** from **control sensitivity**. A workload can be deterministic at the kernel level yet still vulnerable to channel swings or scheduler jitter.
- It adds **offload economics** rather than treating edge offload as a binary choice: compression leverage, device-energy benefit, and artifact footprint all matter.
- It now also distinguishes **compute-limited infeasibility** from **transport-limited infeasibility**: a remote cloud tier can be powerful yet still miss Premium deadlines because WAN floor and tail consume too much of the latency budget. [8]

### 7.2 How this changes scheduling decisions

- **Admission control** should be both **stage-aware** and **channel-aware**, not just GPU-aware. [1]
- **Queue architecture** should separate coarse deterministic jobs (M1, M2, M5), token-elastic streaming jobs (M3, M4), and batch-elastic compute jobs (M6).
- For **M3/M4-like streaming models**, **TTFT** is a practical near-real-time stall signal and should be monitored as an operational proxy for queueing/prefill trouble under tight budgets. [8]
- Premium edge tiers for streaming transformers should pair **quantized variants** with **reserved hard-isolation slices** when co-located with RAN functions; the cloud can still be Medium-feasible while remaining Premium-unreliable on WAN-constrained paths. [8]
- **Placement and co-location** should avoid stacking memory-bandwidth-heavy tenants together when possible; this is heuristic guidance derived from the Weaver resource-shape view, not hard evidence of universal pairing rules. [7]
- **Kubernetes requests/limits** should include GPU slice class, CPU, memory, network, and ephemeral storage, especially on ParaDrop-like extreme-edge nodes. [5][6]

## 8. Reference notes on evidence strength

- Rows such as **dominant stage pressure**, **channel-quality sensitivity**, and **pre-admission observability** are strongly grounded by CORA because the six workloads M1–M6 are evaluated in that system. [1]
- Rows such as **TTFT as a stall proxy**, **strict-SLA tier feasibility**, **hard-isolation safety under co-location**, and **WAN-path dependence** are strongly grounded by the new SLA paper, but mainly for LLM/VLM-style streaming workloads. [8]
- Rows such as **arithmetic compute pressure**, **global memory-bandwidth pressure**, **SM width**, and **slice elasticity** are grounded as accelerator abstractions by Weaver, then transferred carefully into inference profiling. [7]
- Rows such as **compression leverage**, **device-energy benefit**, and **future layer-wise partitioning relevance** are strongest for sensing/3D workloads because that is what LIDAR directly studies. [4]
- Rows such as **CPU-side staging sensitivity** are grounded by EdgeEye’s implementation experience and should be read as serving-stack effects rather than pure model-architecture effects. [3]

## 9. References

[1] Sunghyun Jin, Serae Kim, Sangtae Ha, and Kyunghan Lee, “End-to-End Coordination of RAN and Edge Server for Latency-Critical Inference Serving over Cellular Networks,” *Proceedings of the ACM on Networking*, vol. 3, CoNEXT4, 2025. DOI: [10.1145/3768987](https://doi.org/10.1145/3768987).

[2] Ujjwal Pawar, Andrew E. Ferguson, Yuto Takano, Jon Larrea, Xenofon Foukas, Mahesh K. Marina, and Bozidar Radunovic, “Towards Scalable and Cost-Effective RAN Emulation Leveraging the Public Cloud,” *HotMobile ’25: Proceedings of the 26th International Workshop on Mobile Computing Systems and Applications*, 2025. DOI: [10.1145/3708468.3711895](https://doi.org/10.1145/3708468.3711895).

[3] Peng Liu, Bozhao Qi, and Suman Banerjee, “EdgeEye: An Edge Service Framework for Real-time Intelligent Video Analytics,” *EdgeSys ’18: Proceedings of the 1st International Workshop on Edge Systems, Analytics and Networking*, 2018. DOI: [10.1145/3213344.3213345](https://doi.org/10.1145/3213344.3213345).

[4] Fraser McLean, Leyang Xue, Chris Xiaoxuan Lu, and Mahesh Marina, “Towards edge-assisted real-time 3D segmentation of large scale LIDAR point clouds,” *EMDL ’22 / MobiSys ’22 Workshop*, 2022. DOI: [10.1145/3539491.3539591](https://doi.org/10.1145/3539491.3539591).

[5] Peng Liu, Lance Hartung, and Suman Banerjee, “Lightweight Multitenancy at the Network’s Extreme Edge,” *Computer*, 2017. DOI / official URL not verified in the current synthesis.

[6] Peng Liu, Dale Willis, and Suman Banerjee, “Paradrop: Enabling Lightweight Multi-tenancy at the Network’s Extreme Edge,” *IEEE/ACM Symposium on Edge Computing (SEC)*, 2016. DOI / official URL not verified in the current synthesis.

[7] “Weaver: Foundation Model Training over AI-RAN Compute Infrastructure,” local PDF in the current corpus; venue and DOI were not identified from the available metadata.

[8] Hariz Yet, Nguyen Thanh Tam, Mao V. Ngo, Lim Yi Shen, Lin Wei, Jihong Park, Binbin Chen, and Tony Q. S. Quek, “SLA-Aware Distributed LLM Inference Across Device-RAN-Cloud,” accepted to *IEEE INFOCOM Workshops 2026 (6G AI-RAN 2026)*, Tokyo, Japan; arXiv preprint arXiv:2602.23722, 2026. DOI: [10.48550/arXiv.2602.23722](https://doi.org/10.48550/arXiv.2602.23722). Public URL: [https://arxiv.org/abs/2602.23722](https://arxiv.org/abs/2602.23722).
