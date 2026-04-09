# Task 1 Citation-Debt Ledger and Scope Freeze

Date: 2026-04-07

## Skill evaluation declaration

No built-in skill overlaps this local citation-ledger task. `playwright`, `dev-browser`, and `frontend-ui-ux` are browser/UI-only; `git-master` is git-only; `review-work` is for post-implementation review; `ai-slop-remover` is for single-file cleanup, not evidence mapping.

## Scope freeze

- Approved prose-edit windows for later tasks: `IPP/main.tex:106-157` and `IPP/main.tex:181-250`
- Approved bibliography-edit target for later tasks: `IPP/main.bib`
- Explicitly out of scope: `IPP/main.tex:162-168` (`Feasibility`, `Beneficiaries`)
- Structural constraint: headings remain unchanged
- Task-1 guardrail: no files in `IPP/` were edited while producing this ledger

## Baseline structure inventory from `IPP/main.tex`

Heading baseline captured by `grep '^\\(section|subsection|subsubsection)\{' IPP/main.tex`:

1. `100` `\section{Motivation}`
2. `103` `\subsection{Problem Statement}`
3. `115` `\subsection{Research Hypothesis and Objectives}`
4. `118` `\subsubsection{Research Hypothesis}`
5. `126` `\subsubsection{Objectives}`
6. `144` `\subsection{Timeliness, Novelty, and Significance}`
7. `147` `\subsubsection{Timeliness}`
8. `150` `\subsubsection{Novelty and Relation to Prior Work}`
9. `159` `\subsubsection{Significance}`
10. `162` `\subsection{Feasibility}`
11. `166` `\subsection{Beneficiaries}`
12. `173` `\section{Background and Related Work}`
13. `178` `\subsection{Background}`
14. `181` `\subsubsection{Cloud-Native O-RAN Architecture}`
15. `191` `\subsubsection{The AI-RAN Paradigm}`
16. `206` `\subsubsection{The Anatomy of Latency-Critical Inference Workloads}`
17. `224` `\subsubsection{Strict RAN Service Level Agreements (SLAs) vs. IT Workloads}`
18. `228` `\subsubsection{The Hardware Dichotomy: Training vs. Inference}`
19. `232` `\subsection{Related Work}`
20. `235` `\subsubsection{Hardware-Level GPU Sharing Mechanisms}`
21. `238` `\subsubsection{Edge Multi-Tenancy and Orchestration}`
22. `241` `\subsubsection{End-to-End Latency Coordination}`
23. `244` `\subsubsection{RAN-Aware Co-scheduling}`
24. `248` `\subsection{Summary of Research Gap}`
25. `255` `\section{Methodology}`
26. `272` `\section{Project Plan and Timeline}`

## Bibliography wiring baseline

- Active BibTeX file is confirmed by `IPP/main.tex:339-342`:
  - `\bibliographystyle{unsrt}`
  - `\bibliography{main}`
- `IPP/main.bib` currently contains only template/example entries (`template`, `zamiri2024strategies`); none of the domain citations below are present yet.

## Frozen lowercase BibTeX key registry for later tasks

| Key | Planned source |
| :-- | :-- |
| `beyond` | Polese et al., “Beyond Connectivity: An Open Architecture for AI-RAN Convergence in 6G” |
| `airan` | “AI-RAN: The pathway to future wireless networks” |
| `openairan` | local `open&airan.pdf` proceedings / O-RAN architecture source |
| `cora` | Jin et al., “End-to-End Coordination of RAN and Edge Server for Latency-Critical Inference Serving over Cellular Networks” |
| `chronos` | Pawar et al., “Towards Scalable and Cost-Effective RAN Emulation Leveraging the Public Cloud” |
| `paradrop` | Liu et al., “Paradrop: Enabling Lightweight Multi-tenancy at the Network’s Extreme Edge” |
| `weaver` | “Weaver: Foundation Model Training over AI-RAN Compute Infrastructure” |
| `slaairan` | Yet et al., “SLA-Aware Distributed LLM Inference Across Device-RAN-Cloud” |

### Key-freeze rule for unresolved placeholders

Do **not** freeze new keys for `Polese JSAC 2024`, `AI-RAN Alliance Whitepaper 2024`, `YinYangRAN`, `CAORA`, `AORA`, or `AdaInf` during later local-corpus-only work unless those sources are separately verified from local material. Current default disposition is to rewrite those sentences against the frozen local keys above or soften/remove unsupported exact claims.

## Evidence anchors used to build this ledger

- `research paper/ai_ran_architecture_cross_paper_synthesis.md:24-39`
- `research paper/ai_ran_architecture_cross_paper_synthesis.md:47-56`
- `research paper/ai_ran_architecture_cross_paper_synthesis.md:600-610`
- `research paper/edge_ran_inference_research_matrix.md:38-60`
- `research paper/edge_ran_inference_research_matrix.md:169-183`
- `weaver_fm_training_vs_ldpc_experiments.md:59-64`
- `weaver_fm_training_vs_ldpc_experiments.md:100-142`
- `weaver_fm_training_vs_ldpc_experiments.md:162-172`

## Ledger — approved window `IPP/main.tex:106-157`

| ID | Lines | Current claim / placeholder cluster | Primary source | Fallback source | Planned anchor key | Later-task note |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| A1 | 106 | AI-RAN paradigm, shared cloud-native GPU base stations, asset utilization, revenue narrative (`Insert citation for AI-RAN Alliance/Beyond Connectivity`) | Beyond Connectivity (`beyond`) | AI-RAN pathway (`airan`) | `beyond` | Replace the raw AI-RAN Alliance placeholder with locally supported academic AI-RAN architecture framing. |
| A2 | 106 | Edge inference offload benefits for constrained endpoints and low-latency applications (`Insert citation for CORA / Edge AI inference`) | CORA (`cora`) | SLA-aware distributed inference (`slaairan`) | `cora` | Keep the claim general unless later source verification supports the exact endpoint examples (robots, smart glasses, XR). |
| A3 | 108 | Overprovisioned RAN hardware leaves spare capacity; spare cycles are bursty and spatially complementary (`Insert Weaver citation`) | Weaver (`weaver`) | Beyond Connectivity (`beyond`) | `weaver` | Weaver is the only local direct source for bursty/spatial spare-compute behavior. |
| A4 | 108 | Exact metric cluster: “40\% and 85\% spare capacity” | Weaver (`weaver`) | Beyond Connectivity (`beyond`) | `weaver` | Keep only if later prose aligns with the local Weaver notes (about 40% spare under 4-DU worst case; about 85% spare even during peak daytime); otherwise soften to “substantial spare capacity.” |
| A5 | 110 | MIG/MPS are insufficient for safe millisecond-level coexistence on their own | Weaver (`weaver`) | SLA-aware distributed inference (`slaairan`) | `weaver` | Local corpus supports the tradeoff qualitatively; exact named-system comparisons should not be introduced unless separately verified. |
| A6 | 112 | Need a hierarchical, RAN-first orchestration/scheduling architecture | Beyond Connectivity (`beyond`) | Weaver (`weaver`) | `beyond` | Later prose can cite both, but the orchestration anchor should be `beyond`. |
| A7 | 119 | Weaver shows training can coexist with RAN because FM training is compute-heavy while LDPC/RAN is bandwidth-heavy (`Cite Weaver`) | Weaver (`weaver`) | CHRONOS (`chronos`) | `weaver` | Supported by the local Weaver experiment note; preserve the training-vs-inference distinction. |
| A8 | 121 | Inference is harder than training; phase-aware compute/memory pressure must be stated carefully (yellow revisit + Paradrop placeholder) | SLA-aware distributed inference (`slaairan`) | CORA (`cora`) | `slaairan` | Rewrite away from “inference is always both compute- and memory-bound” toward prefill/decode-specific wording. |
| A9 | 121 | Paradrop as cloud-native multi-tenancy substrate at the extreme edge (`Cite Paradrop`) | Paradrop (`paradrop`) | Beyond Connectivity (`beyond`) | `paradrop` | Safe to keep as orchestration precedent, but not as proof of sub-ms RAN-safe preemption. |
| A10 | 137 | CORA-inspired end-to-end latency coordination across uplink / compute / downlink (`Cite CORA`) | CORA (`cora`) | SLA-aware distributed inference (`slaairan`) | `cora` | Strong direct local support from the matrix note. |
| A11 | 148 | Timeliness / 6G inflection / transition to cloud-native GPU-accelerated vRAN (`Cite Polese JSAC 2024`, `Cite AI-RAN Alliance Whitepaper 2024`, `Cite Polese 2025: Beyond Connectivity`) | Beyond Connectivity (`beyond`) | AI-RAN pathway (`airan`) | `beyond` | Collapse the unresolved external placeholders into locally supported AI-RAN architecture sources unless later evidence adds the missing papers. |
| A12 | 148 | Rising edge-AI demand for constrained mobile devices | CORA (`cora`) | SLA-aware distributed inference (`slaairan`) | `cora` | Use local inference-serving evidence instead of unsupported industry whitepaper language. |
| A13 | 153 | Exact named-system claim cluster: YinYangRAN / CAORA / AORA plus exact `~0.3 seconds` and `~7 seconds` numbers | Weaver (`weaver`) | SLA-aware distributed inference (`slaairan`) | `weaver` | Current local notes do **not** verify those named systems or numbers. Default plan is to soften this into a general “MPS/MIG tradeoff and reconfiguration overhead” statement unless later verification is added. |
| A14 | 155 | “Strict latency limits for multiple inference models are inherently complex” (`Cite AdaInf SIGCOMM 2023`) | SLA-aware distributed inference (`slaairan`) | CORA (`cora`) | `slaairan` | Replace the unresolved AdaInf placeholder with locally supported strict-SLA feasibility / tail-risk language. |
| A15 | 155 | Weaver as micro-level sharing evidence, but only for training (`Cite Weaver`) | Weaver (`weaver`) | SLA-aware distributed inference (`slaairan`) | `weaver` | Keep the caution that Weaver is contrastive evidence, not direct decode-safety proof. |
| A16 | 155 | Paradrop as macro-level multi-tenancy precedent (`Cite Paradrop SEC 2016`) | Paradrop (`paradrop`) | Beyond Connectivity (`beyond`) | `paradrop` | Good source for containerized extreme-edge isolation. |
| A17 | 155 | CORA as macro-level end-to-end inference coordination (`Cite CORA CoNEXT 2025`) | CORA (`cora`) | SLA-aware distributed inference (`slaairan`) | `cora` | Anchor the uplink/compute/downlink budgeting claim here. |
| A18 | 157 | Inference is latency-critical and memory-/bandwidth-sensitive; direct evidence should be phase-aware | SLA-aware distributed inference (`slaairan`) | CORA (`cora`) | `slaairan` | Do not keep the universalized sentence as written; rewrite around prefill/decode asymmetry. |
| A19 | 157 | Bridge micro-level profiling (Weaver) with macro-level orchestration (CORA + Paradrop) | Weaver (`weaver`) | CORA (`cora`) | `weaver` | Later prose can cite multiple keys, but `weaver` is the micro-scheduler anchor for the novelty claim. |

## Ledger — approved window `IPP/main.tex:181-250`

| ID | Lines | Current claim / placeholder cluster | Primary source | Fallback source | Planned anchor key | Later-task note |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| B1 | 182 | O-RAN disaggregation, open interfaces, Split 7.2, O-RU/O-DU division (`Cite: open&airan.pdf`) | Open & AI RAN source (`openairan`) | Beyond Connectivity (`beyond`) | `openairan` | Use the local O-RAN architecture source as the structural anchor. |
| B2 | 184 | vRAN cloudification, containerized microservices, O-Cloud, SMO orchestration (`Cite: beyond.pdf`) | Beyond Connectivity (`beyond`) | Open & AI RAN source (`openairan`) | `beyond` | Strong support in the AI-RAN architecture synthesis note. |
| B3 | 184 | AI/ML-driven network automation inside the architecture (`Cite: AIRAN.pdf`) | AI-RAN pathway (`airan`) | Open & AI RAN source (`openairan`) | `airan` | Good fit for AI-native control and orchestration language. |
| B4 | 186 | Slot duration / control-plane and data-plane timing requirements (`Cite: CHRONOS.pdf`) | CHRONOS (`chronos`) | Open & AI RAN source (`openairan`) | `chronos` | Direct local support for sub-ms timing sensitivity. |
| B5 | 188 | Exact hardware sizing cluster: `100MHz`, `4x4 MIMO`, `~1Gbps`, `8 high-performance CPU cores`, `10Gbps NIC`, `>60% PHY` (`Cite: CHRONOS.pdf`) | CHRONOS (`chronos`) | Beyond Connectivity (`beyond`) | `chronos` | Current mandatory synthesis notes do not restate all of these exact numbers. Verify against the local CHRONOS paper before retaining exact figures; otherwise soften. |
| B6 | 192 | Network as distributed compute substrate; AI-RAN paradigm (`Cite: beyond.pdf`, `Cite: AIRAN.pdf`) | Beyond Connectivity (`beyond`) | AI-RAN pathway (`airan`) | `beyond` | `beyond` is the architecture anchor; `airan` is the paradigm fallback. |
| B7 | 196 | AI-for-RAN pillar and representative optimization examples (`Cite: AIRAN.pdf, open&airan.pdf`) | AI-RAN pathway (`airan`) | Open & AI RAN source (`openairan`) | `airan` | Keep the three-pillar taxonomy unchanged. |
| B8 | 197 | AI-on-RAN distributed learning / multi-agent inference role (`Cite: AIRAN.pdf`) | AI-RAN pathway (`airan`) | Open & AI RAN source (`openairan`) | `airan` | Safe pillar citation. |
| B9 | 198 | AI-and-RAN as opportunistic compute sharing (`Cite: weaver.pdf`) | Weaver (`weaver`) | Beyond Connectivity (`beyond`) | `weaver` | `weaver` is the clearest local anchor for shared-infrastructure coexistence. |
| B10 | 201 | AI-and-RAN remains underexplored; operators overprovision for peak load and see downtime (`Cite: weaver.pdf`, `Cite: open&airan.pdf`) | Weaver (`weaver`) | Open & AI RAN source (`openairan`) | `weaver` | Keep the underexplored/economic framing, but avoid unsupported CAPEX/OPEX flourish if not directly sourced. |
| B11 | 203 | Monetizing spare DU compute as an edge grid without disrupting primary network functions (`Cite: beyond.pdf`, `Cite: AIRAN.pdf`) | Beyond Connectivity (`beyond`) | AI-RAN pathway (`airan`) | `beyond` | Orchestration/economic upside belongs on `beyond`; service-protection language can cite `airan` too if needed. |
| B12 | 207 | Interactive mobile AI workloads, strict latency budgets, and offload need (`Cite: CORA.pdf`, `Cite: SLA.pdf`) | CORA (`cora`) | SLA-aware distributed inference (`slaairan`) | `cora` | The exact `200 ms` / `400 ms` figures are not present in the mandatory local synthesis notes; verify against the local paper before retaining, else soften to “strict interactive latency budgets.” |
| B13 | 209 | Inference executes in distinct phases with different hardware profiles (`Cite: SLA.pdf`) | SLA-aware distributed inference (`slaairan`) | CORA (`cora`) | `slaairan` | This is the local anchor for later phase-aware rewriting. |
| B14 | 211 | Prefill: parallel prompt processing, compute-dense, TTFT, KV-cache creation (`Cite: SLA.pdf`) | SLA-aware distributed inference (`slaairan`) | CORA (`cora`) | `slaairan` | Keep only claims that the local source can support; modern serving citations will be added in later tasks. |
| B15 | 213 | Decode: token-serial, memory/KV pressure, token-throughput sensitivity (`Cite: SLA.pdf`) | SLA-aware distributed inference (`slaairan`) | Weaver (`weaver`) | `slaairan` | Avoid overspecifying microarchitectural internals unless confirmed during later source seeding. |
| B16 | 215 | Decode can look low-ALU yet still be unsafe due to cache / memory-bus contention with RAN (`Cite: CHRONOS.pdf, SLA.pdf`) | SLA-aware distributed inference (`slaairan`) | CHRONOS (`chronos`) | `slaairan` | Good bridge between phase-aware inference and RAN deadline risk. |
| B17 | 217 | Quantized variants are often required for strict edge SLAs; sub-0.5-second feasibility is model-dependent (`Cite: SLA.pdf`) | SLA-aware distributed inference (`slaairan`) | CORA (`cora`) | `slaairan` | Local matrix directly supports `0.5 s` and `1.0 s` tier language. |
| B18 | 219 | End-to-end latency = uplink + compute + downlink; bottleneck shifts by workload and channel quality (`Cite: CORA.pdf`, `Cite: edge_ran_inference_research_matrix.md`) | CORA (`cora`) | SLA-aware distributed inference (`slaairan`) | `cora` | Replace markdown-filename pseudo-citation with the underlying CORA source. |
| B19 | 221 | Bursty interactive arrivals, sequence-length variance, queueing, tail-latency sensitivity (`Cite: edge_ran_inference_research_matrix.md`) | SLA-aware distributed inference (`slaairan`) | CHRONOS (`chronos`) | `slaairan` | Replace note-filename citation with supported paper-backed latency / release-pattern wording. |
| B20 | 225 | Strict RAN SLA paragraph: slot deadlines, MAC scheduling, packet processing, crash risk (`Cite: CHRONOS.pdf`) | CHRONOS (`chronos`) | Weaver (`weaver`) | `chronos` | Strong local support. |
| B21 | 229 | Training is compute-intensive and elastic (`Cite: weaver.pdf`) | Weaver (`weaver`) | CHRONOS (`chronos`) | `weaver` | Direct local support from Weaver profiling. |
| B22 | 229 | Inference is interactive, strict-SLA, and sensitive to bandwidth/cache contention (`Cite: CORA.pdf`, `Cite: SLA.pdf`) | SLA-aware distributed inference (`slaairan`) | CORA (`cora`) | `slaairan` | Split training and inference evidence instead of forcing a single mixed claim. |
| B23 | 236 | MIG/MPS tradeoff paragraph with exact `~7 seconds` and `~0.3 seconds` numbers (`Cite: weaver.pdf`) | Weaver (`weaver`) | SLA-aware distributed inference (`slaairan`) | `weaver` | Keep only the qualitative rigidity/overhead argument unless the exact numbers are later verified from the named papers. |
| B24 | 239 | Paradrop validates edge multi-tenancy; Beyond extends orchestration toward AI-RAN (`Cite: edge_ran_inference_research_matrix.md`, `Cite: beyond.pdf`) | Paradrop (`paradrop`) | Beyond Connectivity (`beyond`) | `paradrop` | Replace the markdown-filename pseudo-citation with the underlying Paradrop paper. |
| B25 | 242 | CORA models RB/SM demand and dynamically rebalances uplink / compute / downlink budgets (`Cite: CORA.pdf`, `Cite: edge_ran_inference_research_matrix.md`) | CORA (`cora`) | SLA-aware distributed inference (`slaairan`) | `cora` | Strong direct local support. |
| B26 | 245 | Weaver as state-of-the-art RAN-safe sharing, Green Contexts, spare compute, but training-only scope (`Cite: weaver.pdf`) | Weaver (`weaver`) | CHRONOS (`chronos`) | `weaver` | Keep the training-only caution explicit. |
| B27 | 250 | Research-gap synthesis: no micro-scheduler for latency-critical inference on shared RAN GPUs; adapt Weaver with orchestration support | Weaver (`weaver`) | CORA (`cora`) | `weaver` | This is the bridge claim for later Tasks 5–6. |

## Unsupported / verify-before-retain metric inventory

| Lines | Metric or exact phrase | Status from local inventory | Planned disposition |
| :-- | :-- | :-- | :-- |
| 108, 245 | `40\%` to `85\%` spare compute | Locally supportable via the Weaver experiment note (`35.7/46.2/57.6/58.0%` SMU under 1/2/4/8 DUs and about `85%` spare daytime capacity), but must be phrased to match the source precisely | Keep only if later prose cites `weaver` and uses the exact supported interpretation; otherwise soften |
| 153, 236 | `~0.3 seconds` MPS reconfiguration and `~7 seconds` MIG reconfiguration | **Not** verified in the mandatory local synthesis notes | Remove or soften unless the named systems are later verified from local source material |
| 188 | `100MHz`, `4x4 MIMO`, `~1Gbps`, `8 cores`, `10Gbps`, `>60%` | Candidate `chronos` metrics, but the mandatory local synthesis notes only confirm timing sensitivity, not the whole exact hardware tuple | Verify against the local CHRONOS source before retaining exact values |
| 207 | `200 ms` for language and `400 ms` for video | Not present in the mandatory local synthesis notes used here | Verify against CORA before retaining; otherwise rewrite as strict interactive/sub-second latency |
| 217 | `sub-0.5-second` strict-SLA feasibility and `1.0 s` medium tier | Supported by `research paper/edge_ran_inference_research_matrix.md:42-46` via the SLA paper | Safe to keep if tied to `slaairan` and phrased as tier-dependent feasibility |

## Out-of-scope guard note

`IPP/main.tex:162-168` contains:

- `\subsection{Feasibility}`
- `\subsection{Beneficiaries}`

These stub sections are explicitly **out of scope** for all later work in this plan branch. No citation filling, prose drafting, or heading edits should occur there.

## Completion note

This ledger freezes the local-corpus-backed edit plan without modifying `IPP/main.tex` or `IPP/main.bib`.
