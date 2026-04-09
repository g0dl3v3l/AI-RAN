## Initialized

### 2026-04-07 — task 1 citation ledger

- `IPP/main.tex` has a 26-heading structural baseline; later edits must preserve that heading inventory exactly.
- The approved citation-edit scope is frozen to `IPP/main.tex:106-157`, `IPP/main.tex:181-250`, and `IPP/main.bib`; `IPP/main.tex:162-168` (`Feasibility`, `Beneficiaries`) is explicitly out of scope.
- `IPP/main.tex:339-342` confirms the active bibliography wiring is `\bibliography{main}` with `unsrt` style.
- `IPP/main.bib` currently contains only template/example entries, so every domain citation key still needs to be seeded.
- Frozen local-corpus BibTeX keys for downstream tasks: `beyond`, `airan`, `openairan`, `cora`, `chronos`, `paradrop`, `weaver`, `slaairan`.
- Local support for the Weaver spare-capacity narrative is stronger than it first appears: the repo’s Weaver experiment note supports bursty/spatial spare compute and provides precise SMU/ACU/GBU figures for later paraphrasing.

### 2026-04-07 — task 2 bibliography seeding

- `beyond` was verified from the local PDF front matter and the official arXiv page for `arXiv:2507.06911`, which confirms the five-author list and the arXiv DOI `10.48550/arXiv.2507.06911`.
- `airan` was verified from the local journal PDF front matter and DOI metadata as *Journal of Information and Intelligence*, volume 4, issue 1, pages 5--22, year 2026.
- `cora` was verified from the local PDF front matter and DOI metadata as *Proceedings of the ACM on Networking*, volume 3, issue `CoNEXT4`, with DOI `10.1145/3768987`.
- The frozen key `chronos` maps to the local paper titled *Towards Scalable and Cost-Effective RAN Emulation Leveraging the Public Cloud*, verified from the local PDF front matter and DOI metadata for HotMobile 2025.
- `paradrop` local front matter exposed the title and three-author list clearly, while the official DOI metadata (`10.1109/SEC.2016.39`) confirmed the IEEE/ACM SEC 2016 venue, pages `1--13`, and canonical URL.
- The local `open&airan.pdf` corpus item is the full workshop proceedings volume, not a single paper, and its front matter verifies the ACM publisher, Hong Kong venue, 2025 date, and ISBN `979-8-4007-1977-6`.
- `slaairan` was verified from the local front matter and the official arXiv page for `arXiv:2602.23722`, which confirms the eight-author list and workshop acceptance note for IEEE INFOCOM Workshops 2026.
- The requested `latexmk -pdf -interaction=nonstopmode -halt-on-error "main.tex"` run completed after BibTeX generated an empty bibliography, because `IPP/main.tex` still has no `\cite{...}` commands yet; this means the updated `main.bib` did not break the document build path.
- `weaver` is stored as `@misc` rather than `@unpublished` so the local-manuscript placeholder can remain conservative without needing an unverifiable `author` field.

### 2026-04-07 — task 3 prose repair

- The strongest locally grounded quantitative evidence for `IPP/main.tex:106-157` comes from `weaver`: about 40% spare compute with four peak-load DUs, about 85% spare SM capacity during peak daytime periods, and a training-throughput jump from about 54 TFLOPs to about 142 TFLOPs when bursty spare compute is stabilized.
- Local support for inference difficulty is stronger when phrased as phase- or pipeline-dependent with `cora`, `weaver`, and `slaairan`, rather than as a universal claim that inference is always both compute- and memory-bound.
- `chronos` is a strong timeliness citation for scalable, public-cloud RAN experimentation, but it should not be stretched into a direct citation for RAN and inference coexistence claims.

### 2026-04-07 — task 4 background citation repair

- The cleanest local citation chain for the AI-RAN background block is `openairan` plus `beyond` plus `airan`: `openairan` anchors O-RAN disaggregation and workshop-era cloud-native framing, `beyond` anchors O-Cloud and orchestration extension, and `airan` anchors the broader AI-RAN paradigm and edge-cloud coordination.
- The local `airan` paper directly supports the preserved three-pillar taxonomy in proposal language, especially the distinction between AI-for-RAN optimization, AI-on-RAN service hosting, and shared AI-and-RAN infrastructure.
- `chronos` is strongest when used for slot-budget pressure, release synchrony, and timing-jitter sensitivity. The local summaries still support those claims more cleanly than the original exact CPU/NIC sizing tuple.

### 2026-04-07 — task 5 inference-anatomy serving systems

- `cora` and `slaairan` remain the right local anchors for end-to-end feasibility and strict-SLA placement, but they need modern serving-system papers layered in when the prose moves from pipeline budgeting to prefill/decode execution anatomy.
- The archival serving literature aligns cleanly on the phase split needed in this subsection: prefill is prompt-parallel and typically compute-dense, while decoding is token-serial and usually constrained by memory movement or KV-cache handling rather than raw ALU saturation.
- `pagedattention` is the strongest citation in this task for KV-cache memory management because its abstract explicitly calls out large, dynamically changing KV caches, fragmentation/duplication waste, and batch-size limits.
- `sarathiserve` is the strongest citation here for prefill/decode interference and chunked-prefill scheduling because its abstract explicitly contrasts compute-dense prefills with low-utilization decodes and explains why naive interleaving hurts both throughput and latency.
- `distserve` is best used as a qualified example that some systems disaggregate prefill and decoding under tight TTFT/per-token latency constraints; it should not be generalized into a claim that all modern serving systems disaggregate.

### 2026-04-07 — task 6 related-work claim tightening

- The cleanest local evidence chain for the rewritten related-work block is `chronos` for slot-budget urgency, `weaver` for spare-compute profiling and training compatibility, `paradrop` for edge multi-tenancy, and `cora` for end-to-end latency budgeting.
- CORA has enough local quantitative support to cite its pre-admission budgeting path directly, including RB demand from I/O and channel quality, SM demand from a speedup model, about `0.18 ms` planner overhead, and roughly `112 B` of request metadata.
- The strongest Weaver wording remains contrastive rather than confirmatory: it supports spare-compute harvesting for compatible secondary work and explicitly warns that LLM decoding is a weaker sharing match than training because both decode and LDPC stress bandwidth.

### 2026-04-07 — task 7 final citation cleanup

- The last in-scope citation debt sat in the live `Cloud-Native O-RAN Architecture` paragraph around lines `176--180`; replacing those inline placeholders with the established local keys `openairan`, `beyond`, `airan`, and `chronos` cleared the remaining semantic-block debt without widening scope.
- A forced `latexmk -g -pdf -interaction=nonstopmode -halt-on-error "main.tex"` reran BibTeX and pdfLaTeX cleanly, and `IPP/main.log` no longer reports undefined citations or fatal LaTeX errors.
- `grep` over `IPP/main.tex` now finds only the preamble `todonotes` package line, so the already-edited semantic blocks no longer contain `\todo`, `Insert citation`, or `Cite ` markers.

### 2026-04-07 — task 8 final academic-flow pass

- The final polish pass worked best as sentence-level smoothing only. The citation scaffold and subsection order were already stable, so coherence improved without widening scope or changing the proposal's hypothesis.
- The `Significance` subsection reads more credibly when framed as a conditional research contribution rather than as an already-proven outcome.
- Small transition edits in the Motivation and Background blocks were enough to make the proposal read like one academic argument instead of adjacent repaired fragments.
