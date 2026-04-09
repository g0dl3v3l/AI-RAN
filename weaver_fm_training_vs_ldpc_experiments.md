# Weaver: experiments used to profile FM training workloads against LDPC

## Scope

This note extracts the **characterization/profiling experiments** in *Weaver: Foundation Model Training over AI-RAN Compute Infrastructure* that were used to understand **FM training as a co-located workload** and to compare it with the **GPU-accelerated LDPC workload** used by the RAN.

I focus on the paper's **workload-profiling evidence** (mainly Sections 4 and 5) rather than the later end-to-end Weaver-vs-baseline system evaluation.

## Short answer

The paper's **direct FM-training-vs-LDPC profiling** is centered on:

1. **Micro-scale LDPC profiling across RAN operating points** (Fig. 1, §4.1)
2. **Direct FM-training vs LDPC GPU resource comparison** using ACU and GBU (Fig. 2, §4.1)
3. **A condensed workload comparison table** summarizing compute-vs-bandwidth demand (Table 2, §4.1)

The paper also includes **supporting experiments** that are not direct FM-vs-LDPC comparisons but explain why FM training is feasible on the same infrastructure:

4. **Multi-DU worst-case LDPC aggregation study** (§4.1)
5. **Macro-scale traffic/SMU replay across sites** (Figs. 3–4, §4.2)
6. **FM training under bursty vs stable RAN-derived SM envelopes** (Fig. 5, §5.1)

---

## Experiment inventory

| # | Experiment | Where | Setup / sweep | What was measured | Main takeaway |
|---|---|---|---|---|---|
| 1 | Micro-scale LDPC profiling under RAN contexts | Fig. 1, §4.1 | OAI + SionnaRK on NVIDIA DGX Spark; MCS sweep 0–28; PRB sweep 0–273; LDPC fixed at 10 iterations | LDPC latency, SM utilization (SMU), arithmetic compute utilization (ACU), global bandwidth utilization (GBU) | LDPC leaves substantial slack: low ACU, moderate/high GBU, and low SM occupancy |
| 2 | Direct FM training vs LDPC GPU behavior comparison | Fig. 2, §4.1 | FM training GEMMs across model sizes 1.3B–70B vs LDPC decoding across transport-block sizes | ACU vs GBU placement of the two workloads | FM training is compute-bound; LDPC is memory-bandwidth-bound; they are structurally complementary |
| 3 | Workload-characteristics summary table | Table 2, §4.1 | Side-by-side summary of RAN LDPC, FM training, and LLM decoding | Dominant operation, compute demand, bandwidth demand, coexistence compatibility | FM training is compatible with RAN sharing; LLM decoding is not |
| 4 | Multi-DU worst-case LDPC headroom study | §4.1 text | 1, 2, 4, and 8 DUs; each at peak traffic (MCS 28, 273 PRBs) every slot | Aggregate SM utilization | Even with multiple DUs, meaningful spare compute remains for FM training |
| 5 | Macro-scale site/time spare-compute study | Figs. 3–4, §4.2 | Replay per-slot uplink traffic traces from 6 production cell sites | Hourly traffic and average SMU over time and across sites | Spare compute is temporally bursty per site but spatially complementary across sites |
| 6 | FM training sensitivity to RAN-derived SM envelopes | Fig. 5, §5.1 | Compare a bursty SM envelope derived from RAN traffic against a stabilized SM envelope | FM training computational throughput (TFLOPs) | Stable spare compute is much more usable for FM training than bursty spare compute |

---

## Detailed breakdown of each experiment

### 1) Micro-scale LDPC profiling under RAN contexts

**Where:** Fig. 1, §4.1  
**Purpose:** Establish what the LDPC workload actually consumes on the GPU before placing FM training beside it.

**Setup**
- Platform: **SionnaRK + OpenAirInterface (OAI)** with **GPU-accelerated LDPC decoding** on an **NVIDIA DGX Spark** with **48 SMs**.
- Tool: **OAI `ulsim`**.
- Sweep dimensions:
  - **MCS index:** 0–28
  - **PRB count:** 0–273
- Decoder setting: **LDPC fixed at 10 iterations** to capture **worst-case execution time**.

**Metrics measured**
- **LDPC decoding latency**
- **SM utilization (SMU)**
- **Arithmetic compute utilization (ACU)**
- **Global bandwidth utilization (GBU)**

**What the experiment showed**
- Worst-case LDPC decoding finished in about **700 µs**, still below the slot deadline budget.
- Worst-case **SMU** was only about **35%**.
- Worst-case **ACU** reached only about **12%**.
- **GBU** rose much higher, up to about **60%** depending on transport-block conditions.

**Why it matters for FM training**
- This experiment shows that LDPC is **not strongly compute-bound** on the GPU.
- Instead, it is relatively **memory-bandwidth-heavy**, leaving arithmetic/compute headroom that FM training can exploit.

---

### 2) Direct FM training vs LDPC comparison on GPU resource usage

**Where:** Fig. 2, §4.1  
**Purpose:** This is the paper's **main direct workload comparison** between FM training and LDPC.

**Setup**
- FM-training side: profile **GPU operations for FM training**, specifically **GEMM-heavy training kernels**, across **model sizes from 1.3B to 70B**.
- LDPC side: profile **LDPC decoding** across different transport-block sizes.
- Comparison space: **ACU vs GBU**.

**Metrics measured**
- **Arithmetic compute utilization (ACU)**
- **Global bandwidth utilization (GBU)**

**What the experiment showed**
- **FM training** points cluster in the **compute-bound** region (**ACU > GBU**).
- **LDPC decoding** points cluster in the **memory-bandwidth-bound** region (**GBU > ACU**).

**Why it matters**
- This is the core experimental evidence behind Weaver's claim that **FM training complements LDPC** on shared GPUs.
- The two workloads stress **different GPU bottlenecks**, which makes coexistence much more plausible than pairing LDPC with another bandwidth-heavy workload.

---

### 3) Condensed workload comparison table

**Where:** Table 2, §4.1  
**Purpose:** Summarize the direct profiling results into an explicit compatibility comparison.

**Reported values**
- **RAN (LDPC decoding):**
  - Dominant operation: **Vector**
  - Compute demand: **0.3–3%**
  - Bandwidth demand: **48–92%**
- **FM training:**
  - Dominant operation: **Matrix**
  - Compute demand: **30–57%**
  - Bandwidth demand: **moderate**
- **LLM decoding:**
  - Dominant operation: **Vector**
  - Compute demand: **<5%**
  - Bandwidth demand: **60–90%**

**Interpretation**
- The table makes the paper's conclusion very clear:
  - **FM training** is the workload the authors consider **compatible** with LDPC sharing.
  - **LLM decoding** is **not** a good match because it is also bandwidth-heavy, so it collides with LDPC's main bottleneck.

---

### 4) Multi-DU worst-case LDPC aggregation study

**Where:** §4.1, immediately after the Fig. 2 discussion  
**Purpose:** Test whether spare compute still exists when the GPU serves multiple DUs, not just a single DU.

**Setup**
- Number of DUs profiled: **1 / 2 / 4 / 8**
- Each DU driven at **peak traffic**:
  - **MCS 28**
  - **273 PRBs**
  - every slot

**Measured result**
- Aggregate **SMU** values were reported as:
  - **35.7%** for 1 DU
  - **46.2%** for 2 DUs
  - **57.6%** for 4 DUs
  - **58.0%** for 8 DUs

**Why it matters for FM training**
- Even under this pessimistic worst-case setup, about **40% spare compute** remains with **4 concurrent DUs**.
- The scaling flattens between 4 and 8 DUs because **memory bandwidth** and **host CPU feed rate** become the bottlenecks.
- This supports the argument that FM training can still exploit residual capacity even in multi-DU deployments.

---

### 5) Macro-scale temporal and spatial spare-compute study

**Where:** Figs. 3–4, §4.2  
**Purpose:** Profile where and when FM training could exploit the spare compute exposed by the LDPC/RAN workload.

**Setup**
- Replay **per-slot uplink transport-block traffic** from a **large-scale production traffic trace**.
- Tooling: modified **OAI PHY-TEST**.
- Data source: **6 production cell sites** from **3 operators in Madrid**, covering urban and suburban zones.

**What was measured**
- Hourly normalized uplink traffic
- Corresponding **average SMU** over time
- Cross-site spatial variation in utilization

**What the experiment showed**
- During off-peak hours, over **90% of SMs** can be idle.
- Even during peak daytime hours, spare SM capacity can remain around **85%**.
- Peaks are **staggered across sites**, so not all sites are busy at the same time.

**Why it matters for FM training**
- This is not a direct FM-vs-LDPC comparison, but it is part of the profiling story.
- It shows that the LDPC workload creates spare capacity that is:
  - **bursty within a site**, but
  - **complementary across sites**,
- which is exactly the kind of setting Weaver targets for distributed FM training.

---

### 6) FM training under bursty vs stable RAN-derived SM envelopes

**Where:** Fig. 5, §5.1  
**Purpose:** Profile how FM training reacts to the kind of spare-compute pattern generated by the LDPC/RAN workload.

**Setup**
- Compare two SM-envelope patterns:
  - **Bursty envelope** derived directly from RAN traffic
  - **Stable envelope** after smoothing/stabilization
- The average available SM count is nearly the same, but the temporal pattern is different.

**Measured result**
- FM training computational throughput:
  - about **54 TFLOPs** under the **bursty** envelope
  - about **142 TFLOPs** under the **stable** envelope

**Why it matters**
- This experiment shows that the question is not only **how much** spare compute exists, but also **how usable** it is.
- Even if LDPC leaves headroom, FM training benefits much more when that headroom is exposed as a **stable SM envelope** rather than a highly fluctuating one.

---

## What the paper is concluding from these experiments

Taken together, these experiments support four claims:

1. **LDPC does not saturate GPU arithmetic resources.**  
   It uses memory bandwidth much more heavily than raw compute.

2. **FM training stresses a different part of the GPU.**  
   FM training is GEMM-heavy and much more **compute-bound**.

3. **Therefore, FM training is a better co-located workload than LLM decoding.**  
   LLM decoding is also memory-bandwidth-heavy, so it conflicts with LDPC more directly.

4. **The remaining challenge is stability, not just availability.**  
   LDPC leaves meaningful spare compute, but that spare compute is bursty. Weaver's design is motivated by making that spare capacity stable enough for FM training to use efficiently.

## If you want the strictest answer

If your question is interpreted **strictly** as: *"Which experiments directly compare FM training with LDPC?"*, then the answer is:

1. **Fig. 2** — direct **ACU vs GBU** comparison of FM training and LDPC decoding  
2. **Table 2** — summarized workload comparison of LDPC, FM training, and LLM decoding

Everything else is supporting characterization that explains **why that direct comparison matters** and how Weaver turns the leftover LDPC capacity into something FM training can actually use.

## Excluded from this note

I did **not** treat the following as workload-profiling experiments for this question:

- The later **Weaver vs DTFM / Asteroid / Confidant** training-throughput evaluations in §8
- OTA/RFSIM user-performance validation of the RAN controller in §8.1
- Large-scale scaling studies in §8.3

Those are important for system evaluation, but they are **not the intrinsic FM-vs-LDPC workload characterization** you asked for.
