## Initialized

### 2026-04-07 — task 1 citation ledger

- Freeze all later IPP edits to `IPP/main.tex:106-157` and `IPP/main.tex:181-250`, plus `IPP/main.bib`; do not widen scope during citation repair.
- Preserve the current section/subsection/subsubsection structure exactly; headings captured in Task 1 are the immutable baseline.
- Treat `IPP/main.tex:162-168` (`Feasibility`, `Beneficiaries`) as hard out-of-scope stubs.
- Use locally supported academic sources as the default rewrite strategy: `beyond`, `airan`, `openairan`, `cora`, `chronos`, `paradrop`, `weaver`, and `slaairan`.
- Do not freeze or seed new BibTeX keys for unresolved external placeholders (`Polese JSAC 2024`, `AI-RAN Alliance Whitepaper 2024`, `YinYangRAN`, `CAORA`, `AORA`, `AdaInf`) during local-corpus-only work; rewrite those claims against the frozen local keys or soften/remove them.
- Use `openairan` as the stable umbrella key for the local `open&airan.pdf` source unless Task 2 later verifies a more precise in-proceedings citation from the local material without changing the key policy.

### 2026-04-07 — task 2 bibliography seeding

- Keep `openairan` as a proceedings-level umbrella entry under the frozen key, because the local corpus file is the whole Open and AI RAN 2025 volume and not one single canonical architecture paper.
- Use conservative BibTeX types that match the verified source state: journal articles for `airan` and `cora`, in-proceedings entries for `chronos`, `paradrop`, and `slaairan`, a proceedings entry for `openairan`, and a `@misc` local-manuscript entry for `weaver`.
- Record `slaairan` against its accepted workshop venue while using the official arXiv DOI and URL, since the local paper and arXiv page confirm acceptance but do not expose a final IEEE proceedings DOI yet.
- Leave `weaver` intentionally sparse instead of guessing an author list or venue, and store it as `@misc` because that type tolerates missing author metadata better than `@unpublished`.

### 2026-04-07 — task 3 prose repair

- Recast MIG as a hard-isolation option and comparison baseline, not the presumed final sharing mechanism, so the micro-scheduler objective and the novelty discussion do not contradict each other.
- Replace unresolved prior-work placeholders in `IPP/main.tex:145-151` with a local-corpus synthesis centered on `beyond`, `airan`, `openairan`, `chronos`, `cora`, `paradrop`, `weaver`, and `slaairan`.
- Preserve the original research hypothesis meaning while rewriting the sentence structure to remove citation TODOs and make the inference challenge explicitly phase-aware.

### 2026-04-07 — task 4 background citation repair

- Rewrite `IPP/main.tex:182` around `chronos` timing-fidelity evidence instead of retaining the unsupported exact CHRONOS hardware-sizing tuple.
- Use `openairan,beyond,airan` together in the cloud-native O-RAN to AI-RAN bridge sentence so the paragraph reads as one architecture chain instead of isolated one-off citations.
- Anchor the AI-and-RAN economic and coexistence framing with `airan`, `weaver`, and `beyond`, while keeping the proposal focused on compatibility with primary RAN deadlines rather than on unsupported utilization rhetoric.
- Use `cora` and `slaairan` to soften the opening of `The Anatomy of Latency-Critical Inference Workloads`, so the subsection starts from stage-aware latency budgeting and strict-SLA feasibility before later tasks add more detailed serving anatomy.

### 2026-04-07 — task 5 inference-anatomy serving systems

- Keep `cora` and `slaairan` as the first and last anchors in the rewritten block so the subsection still reads as an AI-RAN feasibility argument rather than a detached serving-systems survey.
- Add exactly three new serving-system keys---`pagedattention`, `sarathiserve`, and `distserve`---because they cover the required memory-management, chunked-prefill scheduling, and prefill/decode disaggregation claims without widening the subsection into a broader product catalog.
- Phrase DistServe as a qualified example (`some systems explicitly disaggregate`) to avoid overclaiming that disaggregation is the default design across modern LLM serving stacks.
- Do not add `tensorrtllm` in this task, because the revised prose does not need implementation-only claims such as inflight batching or KV-cache reuse from vendor-maintained project pages.

### 2026-04-07 — task 6 related-work claim tightening

- Treat the live edit target as the semantic block from `Strict RAN Service Level Agreements (SLAs) vs. IT Workloads` through `Summary of Research Gap`, because the current file has shifted by about ten lines relative to the frozen Task 1 ledger even though the subsection order is unchanged.
- Remove the unsupported exact MIG and MPS reconfiguration timings entirely instead of softening them with speculative numbers.
- Reframe the final gap paragraph around the missing inference-specific micro-scheduler for shared RAN GPUs, not around a stronger claim that Weaver already demonstrates decode-safe coexistence.

### 2026-04-07 — task 7 final citation cleanup

- Keep the final background-paragraph repair on the previously approved local key chain: `openairan,beyond,airan` for O-RAN disaggregation/cloud-native/SMO claims and `chronos` for slot-budget execution pressure.
- Do not remove the `todonotes` package import in this task, because the scope is citation/build cleanup inside approved semantic blocks rather than document-wide package cleanup.

### 2026-04-07 — task 8 final academic-flow pass

- Keep the final pass strictly at the prose-polish level inside the live Motivation and Background/Related-Work semantic blocks, with no heading, label, or hypothesis changes.
- Treat a stable 26-heading inventory, an empty citation-placeholder grep, and a successful `latexmk` rebuild as the completion gate for this scope-preservation pass.
