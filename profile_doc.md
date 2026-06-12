# vRAN Edge Inference Profiling Methodology and Provisional Layering Decision

This document records the current independent profiling strategy for RAN edge inference, the rationale for choosing a profiling level, and a provisional per-category answer for where profiling should be centered. It uses the local review only for the `Workload in doc` row names and for the formal definition of the ComputeLease score axes. It does **not** assume that the model, runtime, or serving choices in the review are already correct.

**Current position:** profiling should be performed as a **layered procedure**, not at only one layer. Model-level profiling captures intrinsic workload shape and hard constraints. Runtime-level profiling captures executable boundaries, allocator behavior, and engine-specific memory mechanisms. Serving and resource-system profiling is the only layer that can close the final ComputeLease scorecard.

## 🎯 Purpose and scope

The main design question is simple: **at what level should an inference system be profiled for RAN edge deployment, model level, runtime level, serving/resource-system level, or all of them?**

The answer matters because the governing score axes in the review are defined against a **ComputeLease** contract, not against a raw model alone. The review asks whether a system can survive bounded lease durations, hard VRAM caps, early reclaim, and zero-SM gaps. Those are container and system behaviors, not only model behaviors.

This document therefore does four things:

1. Re-states the score axes in a system-design form.
2. Defines what each profiling layer can and cannot prove.
3. Adds **Implementation Feasibility** as a separate formal dimension.
4. Gives a provisional per-category answer for the dominant profiling layer, while keeping the final unified versus hybrid stack question deferred.

## 🧭 Deferred questions and non-goals

This document does **not** decide whether the final inference platform should be:

- one unified stack for all categories,
- a hybrid platform with shared control and category-specific execution paths, or
- fully separate stacks per category.

That decision should be made **after** the layered profiling results are available.

This document also does not finalize the score of any concrete system. It defines the method that will later justify those scores.

## 📏 Score axes carried over from the review

The review in `progress/unified_vran_edge_inference_sota_review_2022_2026.md` defines four score axes under a ComputeLease contract with fields such as `duration_us`, `preemption_notice_us`, `reclaim_mode`, `sm_budget_sms`, and `vram_budget_bytes`.

| Axis | Review question | Dominant proof layer | Why one layer alone is insufficient |
| --- | --- | --- | --- |
| **Preemption Resilience** | Can execution be safely interrupted, and what is the safest preemption boundary? | **Serving/resource-system** | The model may suggest a natural boundary, and the runtime may expose one, but only the full system can prove that pause, reclaim, and resume actually work under `preemption_notice_us` and `reclaim_mode`. |
| **Micro-Segmentation** | Can work be chopped into units that fit sub-millisecond or microsecond-scale leases? | **Runtime/engine** | The model suggests candidate units, but the runtime determines whether those units are really executable with low enough overhead and variance. The system layer must still validate scheduling under actual leases. |
| **State Parking** | During 0 percent SM availability, what state must be parked, where, and at what cost? | **Serving/resource-system** | The model only identifies what state exists. The runtime exposes what state can be surfaced or evicted. Only the serving layer can prove park, restore, and resume under bandwidth and reclaim constraints. |
| **Tight VRAM Compliance** | Can the system stay under a hard `vram_budget_bytes` cap without collapse? | **Runtime plus serving/resource-system** | The model provides lower bounds and scaling shape, but allocator behavior, fragmentation, paging, admission control, and multi-tenant interactions appear at runtime and system layers. |

### Score admissibility rule

The score admissibility rule for this methodology is:

- **Model-level evidence may never by itself close a final ComputeLease score.**
- **Runtime-level evidence may justify provisional claims**, especially for micro-segmentation and partial VRAM behavior.
- **Final High/Medium/Low axis scores require serving/resource-system evidence**, ideally under lease traces or lease-equivalent experiments.

## 🪜 Hierarchical execution-unit ladder

Every profile packet should report a **hierarchical execution-unit ladder**, not a single “natural micro-segmentation unit.” The purpose of the ladder is to separate what is merely visible to profiling from what is actually schedulable and from what is defensibly stoppable under a lease.

| Ladder level | Definition | What it is for | What it is not |
| --- | --- | --- | --- |
| **Smallest algorithmic primitive** | The smallest workload-intrinsic operation that explains compute, bandwidth, and state shape, such as GEMM/GEMV-backed attention or MLP sub-ops, convolution, upsampling, or ray-marching primitives. | Primitive-level workload characterization and lower-bound feasibility reasoning. | It is **not** automatically a safe-stop boundary. |
| **Runtime-exposed schedulable unit** | The smallest unit a concrete runtime or serving stack can actually budget, batch, or meter, such as a decode iteration, prefill chunk, tile sub-inference, or ray batch. | Micro-segmentation analysis and provisional runtime claims. | It is **not** automatically reclaim-safe or restart-safe. |
| **Smallest empirically justified safe-stop boundary** | The smallest boundary with direct evidence or measured proof that work can stop, reclaim, and later resume or retry with bounded cost under the current stack. | Preemption resilience, state parking, and final ComputeLease score closure. | It must not be assumed just because a lower-level primitive exists. |

Two rules follow from this ladder:

1. A safe-stop boundary may occur at **any** ladder level, including the algorithmic primitive level, but only when the runtime and system evidence actually support it.
2. If a lower-level primitive is visible in profiling but the current stack cannot safely stop there, the packet must report that **gap explicitly** rather than collapsing the ladder into one field.

### Unit-selection decision rule

For every category packet, every candidate unit that matters to the design must be classified in one of three ways:

| Candidate unit outcome | Meaning | Required justification |
| --- | --- | --- |
| **Selected as profiling primitive** | The unit is useful for workload characterization and lower-bound reasoning. | Explain what source proves or motivates its existence. |
| **Selected as current safe scheduling sub-unit** | The unit is the current best boundary for cooperative leasing, reclaim, and bounded lost work. | Explain why it satisfies the safe-stop rule under the current stack. |
| **Not selected as current safe scheduling sub-unit** | The unit exists or is visible, but is not the current lease-safe boundary. | State exactly why it fails selection: not runtime-exposed, no committed restart state, no bounded reclaim proof, unacceptable quality risk, or only inferential support. |

A candidate unit may be **selected for profiling** and **not selected for safe scheduling** at the same time. That distinction must be written explicitly rather than left implicit.

### Safe-stop selection rule

A candidate unit should be selected as the **current safe scheduling sub-unit** only if all of the following are true under the current stack:

1. **Runtime exposure**: the runtime or serving layer can actually budget, meter, or surface that unit as a boundary.
2. **Recoverable state**: enough state can be preserved, reconstructed, or retried from that boundary without undefined partial progress.
3. **Bounded reclaim cost**: there is direct evidence or a clearly labeled AH that stop, reclaim, and resume or retry can occur with bounded lost work under the lease.

If any one of these is missing, the unit may still be profiled, but it must be marked **not selected as the current safe scheduling sub-unit**.

### Provenance rule

Every packet must state the provenance of each important selection or rejection:

- **Direct in local review** if the local review explicitly says it.
- **Direct in external source** if a cited paper or official doc explicitly says it.
- **Packet synthesis** if the packet combines multiple sources into a new conclusion.
- **AH** if the claim is a forward-looking implementation hypothesis rather than current evidence.

No packet should present a packet-synthesis conclusion as if it were a verbatim statement from the unified review.

## 🧪 Layered profiling workflow

```mermaid
flowchart LR
    accTitle: Layered Profiling Workflow
    accDescr: The workflow starts with workload and model profiling, then moves to runtime profiling, then to serving and resource-system profiling. Final ComputeLease scores are only closed after the serving or resource-system layer is evaluated.

    model_layer["1. Model and workload profile"]
    gate_1{"Workload class is lease-plausible?"}
    runtime_layer["2. Runtime and engine profile"]
    gate_2{"Runtime exposes usable unit and bounded memory behavior?"}
    system_layer["3. Serving and resource-system profile"]
    scorecard["4. Final ComputeLease scorecard"]
    stop_1["Stop, reformulate model or category split"]
    stop_2["Change runtime, export path, or model variant"]

    model_layer --> gate_1
    gate_1 -->|Yes| runtime_layer
    gate_1 -->|No| stop_1
    runtime_layer --> gate_2
    gate_2 -->|Yes| system_layer
    gate_2 -->|No| stop_2
    system_layer --> scorecard

    classDef core fill:#dbeafe,stroke:#2563eb,stroke-width:2px,color:#1e3a5f
    classDef gate fill:#fef9c3,stroke:#ca8a04,stroke-width:2px,color:#713f12
    classDef end fill:#dcfce7,stroke:#16a34a,stroke-width:2px,color:#14532d
    classDef stop fill:#fee2e2,stroke:#dc2626,stroke-width:2px,color:#7f1d1d

    class model_layer,runtime_layer,system_layer core
    class gate_1,gate_2 gate
    class scorecard end
    class stop_1,stop_2 stop
```

## 🔬 What each profiling layer can prove

| Layer | Core purpose | What it can prove | What it cannot prove |
| --- | --- | --- | --- |
| **Model / workload layer** | Describe intrinsic workload shape | Smallest algorithmic primitives, candidate lifted units, phase structure, state inventory, scaling laws, hard infeasibility flags | Lease-compliant preemption, actual parking cost, allocator stability, multi-tenant cap compliance |
| **Runtime / engine layer** | Characterize executable behavior of a concrete engine | Runtime-exposed schedulable units, latency variance, allocator behavior, paging/offload features, exportability, quantization support | End-to-end reclaim behavior, admission control quality, multi-tenant interactions under lease traces |
| **Serving / resource-system layer** | Evaluate a lease-aware deployment path | Smallest empirically justified safe-stop boundary, admission control, reclaim, park/resume, concurrency interactions, cap enforcement, final scorecard outcome | Intrinsic model properties independent of the chosen engine or system |

### Layer-specific profiling outputs

#### 1. Model and workload profile

This layer should collect only workload-intrinsic descriptors:

- the **smallest algorithmic primitives** that actually generate the workload shape,
- candidate lifted units above those primitives, such as operator-groups, token-steps, chunks, tiles, patches, or ray-batches,
- phase decomposition,
- persistent state categories by level,
- peak and scaling trends for activations, KV, scene state, or latent state,
- hard infeasibility flags, such as if useful segmentation requires unacceptable task reformulation.

#### 2. Runtime and engine profile

This layer should profile a concrete engine implementation:

- the **runtime-exposed schedulable unit** or units,
- the actual minimum executable unit that the runtime can meter or budget,
- unit latency distribution and variance,
- exposed pause points, flush behavior, and any gap between profiled units and actually stoppable units,
- allocator behavior, paging support, offload mechanisms, fragmentation behavior,
- export friction, quantization support, operator coverage,
- server-edge and embedded-edge portability.

#### 3. Serving and resource-system profile

This layer should evaluate a lease-aware deployment path:

- the **smallest empirically justified safe-stop boundary** under the current stack,
- admission control,
- reclaim handling,
- pause, park, and resume behavior,
- cap enforcement under `vram_budget_bytes`,
- headroom under stress,
- multi-tenant interference,
- lease trace execution and deadline behavior.

## ⚙️ Implementation Feasibility as a separate formal dimension

Implementation Feasibility should not be folded into the four score axes. It answers a different question: **even if a layer could in principle support a strong score, how practical is it to build and validate on the target platform?**

### Feasibility scoring

| Feasibility score | Meaning |
| --- | --- |
| **High** | Mature open tooling exists, the export and deployment path is straightforward, and validation can be done without major custom systems work. |
| **Medium** | The path is plausible, but requires custom glue, non-trivial integration work, or careful tuning across layers. |
| **Low** | The path likely needs major custom runtime or control-plane work, or depends on behavior not directly supported by existing tooling. |

### Platform split

Feasibility must be evaluated for **both** platform classes because server-edge and embedded-edge are not interchangeable:

| Platform class | Typical implication |
| --- | --- |
| **NVIDIA edge server** | More likely to support richer serving/resource-system experiments, multi-tenant control, and larger parked state. |
| **Jetson / embedded edge** | Stronger pressure on memory, storage bandwidth, and system complexity. Some system-level strategies that are practical on servers may become infeasible or disproportionately costly. |

## 🧱 Evidence policy

This document follows the evidence discipline already used in the local review:

- **Direct evidence** means the source explicitly states or measures the behavior.
- **Inferred evidence** means the behavior is plausible from the architecture or benchmark data but not directly proven.
- Any non-direct claim that matters for the methodology should be labeled as an **Adaptation Hypothesis**, or AH.

### Working evidence rules for this document

1. Use direct evidence whenever a source explicitly measures a required behavior.
2. Allow labeled inference when direct evidence is missing but the mechanism is still strong enough to motivate experiments.
3. Do not let an inferred claim close a final ComputeLease score without later system-level validation.

## 🗺️ Provisional per-category profiling-level decision

The table below is the current provisional answer. It states where profiling should be centered for each category, which supporting layers remain mandatory, and what the current feasibility looks like for server-edge and embedded-edge deployment.

| Category | Workload in doc | Independent baseline models, primary first | Dominant profiling layer | Mandatory supporting layers | Why this is the right starting point | Feasibility, edge server | Feasibility, Jetson / embedded |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Transformer / autoregressive models** | **M3 Language Processing** | Llama 3.2 3B, Qwen3 4B, then Qwen2.5 3B or 7B, Gemma 3 4B, Mistral 7B | **Serving/resource-system** | Model and runtime | Below token-step, M3 still contains algorithmic primitives such as GEMM/GEMV-backed attention and MLP sub-ops. But for current edge-facing stacks, the most defensible safe-stop boundary remains the decode token-step, with prefill chunks as a runtime-specific intermediate unit when explicitly supported. | High | Medium |
| **Translation** | **M4 Translation** | NLLB-200 distilled 600M, MarianMT or OPUS-MT, then M2M100, mBART-50, MADLAD-400 | **Runtime, then serving/resource-system** | Model | Encoder-decoder state structure matters enough that runtime choice is decisive early. Final score closure still requires system-level proof. | High | Medium |
| **Computer vision models** | **M1 Image Segmentation** | SegFormer-B0 or B1, DeepLabV3+, then YOLO11-seg, U-Net, Mask2Former | **Runtime** | Model and serving/resource-system | The model layer identifies activation shape and plausible tile or patch boundaries, but runtime determines whether fine-enough executable units really exist. Final score still closes at the system layer. | High | Medium |
| **Computer vision models** | **M2 Pose Estimation** | RTMPose-s or m, YOLO11-pose, then ViTPose, HRNet, OpenPose | **Runtime** | Model and serving/resource-system | Similar to M1, but the hybrid operator mix makes runtime behavior even more important. The model layer cannot by itself prove lease behavior. | High | Medium |
| **Computer vision models** | **M5 Super Resolution** | Real-ESRGAN, SwinIR, then HAT, RLFN, RCAN or EDSR | **Model, as a hard gate, then runtime** | Serving/resource-system | Below tile level, M5 still contains real operator primitives such as convolution, upsampling, attention, and residual blocks. But for current TensorRT-style edge stacks, those lower primitives are mainly profiling structure; the most defensible safe-stop boundary remains a validated external tile boundary, otherwise the full inference request. | Medium | Low |
| **Volume rendering** | **M6 Volume Rendering** | Instant-NGP, Nerfacto, then TensoRF, mip-NeRF 360, Zip-NeRF | **Model plus runtime bridge** | Serving/resource-system | This row is defined by workload-native CUDA and scene-state behavior. The M6 carve-out in the review already acknowledges that accelerator evidence matters earlier here. Final score closure still requires a serving-layer wrapper, but only after proving that the runtime path is viable. | Medium | Low |
| **Diffusion models** | **Uncovered in current doc** | SDXL 1.0, Stable Diffusion 3.5 Medium, then SD1.5, SDXL Turbo or LCM, FLUX.1-schnell | **Runtime, then serving/resource-system** | Model | Denoising step structure is suggestive at model level, but latency, memory pressure, and cap behavior are runtime-driven. Final scoring still requires lease-aware serving proof. | Medium | Low |
| **Voice-related models** | **Uncovered in current doc** | Whisper large-v3, NVIDIA Parakeet 0.6B, then Distil-Whisper, FastConformer, wav2vec2 or XLS-R | **Split the category first** | Runtime and serving/resource-system after split | This row is too broad as a single category. Streaming ASR, offline ASR, speech translation, and TTS have different natural units and state behavior. No single profiling layer should be chosen until the row is split. | Medium | Medium to Low |

## 🧩 Independent baseline and engine snapshot

This section captures the current independent baseline and engine profile so the work is recorded in one place.

| Category | Workload in doc | Primary baselines | Primary runtimes | Fallback runtimes | Preferred serving/resource systems |
| --- | --- | --- | --- | --- | --- |
| Transformer / autoregressive | M3 Language Processing | Llama 3.2 3B, Qwen3 4B | TensorRT-LLM or TensorRT Edge-LLM, llama.cpp | CTranslate2, ONNX Runtime GenAI | vLLM, SGLang, Dynamo or llm-d |
| Translation | M4 Translation | NLLB-200 distilled 600M, MarianMT | CTranslate2, ONNX Runtime plus TensorRT EP | TensorRT, TVM | Triton, Riva when a packaged translation stack is needed |
| Computer vision, segmentation | M1 Image Segmentation | SegFormer-B0 or B1, DeepLabV3+ | TensorRT | ONNX Runtime plus TensorRT or CUDA EP, TVM | DeepStream, Triton, Hummingbird or USHER for strict shared-GPU packing studies |
| Computer vision, pose | M2 Pose Estimation | RTMPose-s or m, YOLO11-pose | TensorRT | ONNX Runtime plus TensorRT or CUDA EP, TVM | DeepStream, Triton, OctopInf for systems-style edge analytics studies |
| Computer vision, super resolution | M5 Super Resolution | Real-ESRGAN, SwinIR | TensorRT | ONNX Runtime plus TensorRT EP, TVM | Triton, USHER for packed shared inference, Proteus for accuracy-aware variant selection |
| Volume rendering | M6 Volume Rendering | Instant-NGP, Nerfacto | Instant-NGP or tiny-cuda-nn, NerfAcc | TensorRT for exported subgraphs, TVM | Custom deployment around Instant-NGP or NerfAcc |
| Diffusion | Uncovered | SDXL 1.0, Stable Diffusion 3.5 Medium | TensorRT | ONNX Runtime plus TensorRT EP, TVM | Triton |
| Voice-related | Uncovered | Whisper large-v3, NVIDIA Parakeet 0.6B | CTranslate2 or faster-whisper, TensorRT | ONNX Runtime | Riva, Triton |

## ✅ Recommended strategy

The strategy for answering the profiling-level question should be:

1. **Profile every category at all three layers**, but do not treat all layers equally.
2. In every packet, report the **full execution-unit ladder**: smallest algorithmic primitive, runtime-exposed schedulable unit, and smallest empirically justified safe-stop boundary.
3. Use the **dominant profiling layer** in the matrix above to decide where the decisive evidence should be concentrated.
4. Keep **Implementation Feasibility** separate from the four score axes.
5. Require a **platform split**, edge server and Jetson or embedded, whenever feasibility or memory behavior could diverge materially.
6. Close final scores only after a serving/resource-system experiment or lease-equivalent experiment has been run.

### Operationally, the workflow should be:

1. **Workload screen**
   - identify the smallest algorithmic primitives,
   - identify candidate lifted units above those primitives,
   - inventory persistent state by level,
   - identify hard infeasibility cases.
2. **Runtime characterization**
   - identify the runtime-exposed schedulable unit,
   - measure unit latency, variance, and allocator behavior,
   - record offload, paging, quantization, and profiling-visible versus stoppable-unit gaps.
3. **Serving/system experiment**
   - establish the smallest empirically justified safe-stop boundary,
   - run lease traces or lease-equivalent tests,
   - measure reclaim, resume, and VRAM-cap compliance,
   - assign final High, Medium, or Low scores plus evidence level.

## 📋 Decision procedure for the next phase

The next phase should instantiate one profile packet per category with the following template:

1. **Category and workload row**
2. **Selected baseline model or model family**
3. **Candidate runtime(s)**
4. **Candidate serving/resource-system(s)**
5. **Execution-unit ladder**: smallest algorithmic primitive, runtime-exposed schedulable unit, smallest justified safe-stop boundary
6. **Model-layer findings**
7. **Runtime-layer findings**
8. **Serving-layer findings**
9. **Final scorecard**
10. **Implementation Feasibility**, server-edge and embedded-edge separately
11. **Direct evidence vs AH list**

## 📚 Evidence base used in this document

### Local review anchors

- `progress/unified_vran_edge_inference_sota_review_2022_2026.md`, especially:
  - summary matrix and inclusion rubric,
  - ComputeLease scorecard section,
  - score axes definitions,
  - scheduler and lease contract assumptions,
  - CORA baseline taxonomy.
- `progress/weaver.pdf` together with `weaver_fm_training_vs_ldpc_experiments.md`, specifically for the reminder that primitive-level workload characterization can sit below serving-level scheduling boundaries.

### External evidence base used in the independent profile

- vLLM / PagedAttention, SOSP 2023: https://doi.org/10.1145/3600006.3613165
- Orca, OSDI 2022: https://www.usenix.org/system/files/osdi22-yu.pdf
- DistServe, OSDI 2024: https://www.usenix.org/system/files/osdi24-zhong-yinmin.pdf
- SpotServe, ASPLOS 2024: https://doi.org/10.1145/3620665.3640411
- CacheGen, SIGCOMM 2024: https://doi.org/10.1145/3651890.3672274
- TensorRT documentation: https://docs.nvidia.com/deeplearning/tensorrt/latest/inference-library/index.html
- TensorRT-LLM documentation: https://nvidia.github.io/TensorRT-LLM/
- TensorRT Edge-LLM supported models: https://nvidia.github.io/TensorRT-Edge-LLM/latest/user_guide/getting_started/supported-models.html
- ONNX Runtime execution providers: https://onnxruntime.ai/docs/execution-providers/
- CTranslate2 documentation: https://opennmt.net/CTranslate2/
- llama.cpp repository: https://github.com/ggml-org/llama.cpp
- SegFormer paper: https://arxiv.org/abs/2105.15203
- RTMPose paper: https://arxiv.org/abs/2303.07399
- Real-ESRGAN repository: https://github.com/xinntao/Real-ESRGAN
- SwinIR repository: https://github.com/JingyunLiang/SwinIR
- Instant-NGP paper and implementation: https://doi.org/10.1145/3528223.3530127 and https://github.com/NVlabs/instant-ngp
- NerfAcc paper: https://arxiv.org/abs/2305.04966
- DeepStream documentation: https://docs.nvidia.com/metropolis/deepstream/dev-guide/
- Triton Inference Server documentation: https://docs.nvidia.com/deeplearning/triton-inference-server/
- Riva documentation: https://docs.nvidia.com/deeplearning/riva/

## 🧾 Final methodological answer

The clean answer to the original design question is:

**Do not choose model-only, runtime-only, or system-only profiling. Use layered profiling with an explicit execution-unit ladder.**

- Use **model-level profiling** to identify the smallest algorithmic primitives and decide whether a workload family is even lease-plausible.
- Use **runtime-level profiling** to identify the runtime-exposed schedulable unit and the memory behavior of a concrete engine.
- Use **serving/resource-system profiling** to establish the smallest empirically justified safe-stop boundary and assign final ComputeLease scores.

In short:

**primitive ladder, runtime mechanism, system proof**.
