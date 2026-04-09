# IPP Citation and SOTA Inference Upgrade

## TL;DR
> **Summary**: Upgrade `IPP/main.tex` from draft-quality citation placeholders to an evidence-backed proposal by seeding `IPP/main.bib` with verified local-corpus references, paraphrasing metric-heavy claims around those citations, and expanding `The Anatomy of Latency-Critical Inference Workloads` with phase-aware modern LLM serving literature.
> **Deliverables**:
> - verified BibTeX entries in `IPP/main.bib`
> - replaced citation placeholders and `\todo` citation debt in approved sections of `IPP/main.tex`
> - expanded inference-anatomy subsection with prefill/decode, KV-cache, batching, and modern serving-system references
> - successful LaTeX/BibTeX compilation with zero undefined citations
> **Effort**: Medium
> **Parallel**: YES - 2 waves
> **Critical Path**: Task 1 → Task 2 → Task 3/4/6 → Task 5 → Task 7 → Task 8

## Context
### Original Request
Upgrade the proposal in `IPP/` by integrating metrics from the local literature in `research paper/`, replacing citation placeholders with proper `\cite{...}` commands, and expanding `The Anatomy of Latency-Critical Inference Workloads` with 2024–2026 SOTA LLM inference systems and frameworks. Preserve structure, headings, and the AI-and-RAN hypothesis. Produce the plan first and do not modify `.tex` files before approval.

### Interview Summary
- `IPP/main.tex` is the only proposal source file.
- `IPP/main.bib` is the active bibliography (`\bibliography{main}`) and currently contains only template entries.
- `IPP/main.tex` currently has 34 `\todo` markers and no live `\cite{}` calls.
- Highest-priority citation debt is concentrated around `main.tex:106-157` and `main.tex:181-245`.
- The target subsection already exists at `main.tex:206-221` and must be expanded in place rather than restructured.
- `research paper/` contains the local corpus: `weaver.pdf`, `CORA.pdf`, `SLA.pdf`, `CHRONOS.pdf`, `beyond.pdf`, `AIRAN.pdf`, `open&airan.pdf`, `paradrop.pdf`, and synthesis markdown.

### Metis Review (gaps addressed)
- Freeze scope to citation completion, academically stronger paraphrasing, and the target subsection expansion; do not rewrite the proposal or fill empty stubs like Feasibility/Beneficiaries.
- Treat exact unsupported numbers as removable: every retained metric must map to a verified source, otherwise soften the prose.
- Prefer peer-reviewed papers and official DOI/USENIX/ACM pages; use project docs or GitHub only for implementation-context sources such as TensorRT-LLM, and label them as contextual when used.
- Preserve the AI-and-RAN hypothesis while tightening unsupported certainty, especially around MIG feasibility and inference/RAN coexistence claims.
- Validate with `latexmk`; do not assume the current `unsrt` style will magically render DOI hyperlinks beyond what plain BibTeX supports.

## Work Objectives
### Core Objective
Turn `IPP/main.tex` into a citation-backed, academically coherent proposal without changing its structure or core hypothesis.

### Deliverables
- A populated `IPP/main.bib` with verified entries for the local corpus and selected modern LLM serving systems.
- Rewritten proposal sentences where placeholders currently sit, using paraphrased evidence rather than filename placeholders.
- An expanded `The Anatomy of Latency-Critical Inference Workloads` subsection that clearly explains prefill vs decoding and references modern serving engines.
- A clean compile artifact proving the document remains valid LaTeX.

### Definition of Done (verifiable conditions with commands)
- `grep -n '\\todo\|Insert citation\|Cite ' IPP/main.tex` returns no citation-debt markers in the approved edited ranges.
- `grep -n '\\cite{' IPP/main.tex` returns citations in the previously uncited sections.
- `latexmk -pdf -interaction=nonstopmode -halt-on-error "IPP/main.tex"` exits with code 0.
- `grep -n 'Citation .* undefined\|There were undefined citations\|Undefined control sequence\|Emergency stop' IPP/main.log` returns no matches.
- `grep -n '@.*{.*weaver\|@.*{.*cora\|@.*{.*chronos\|@.*{.*vllm\|@.*{.*sarathi\|@.*{.*distserve' IPP/main.bib` returns the seeded bibliography entries.

### Must Have
- Replace raw placeholders like `Cite: weaver.pdf` with stable BibTeX keys.
- Ground all retained metrics in verified local or official sources.
- Expand the inference section with explicit prefill/decode behavior, KV-cache implications, and modern scheduling techniques such as PagedAttention, continuous batching, and prefill/decode separation.
- Keep the current section and subsection headings unchanged.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- No new sections, no reordered headings, no changed AI-and-RAN hypothesis.
- No vendor blogs, Medium posts, or marketing copy as primary academic evidence.
- No unsupported exact latency or overhead numbers left in place.
- No citations to local note filenames in final prose.
- No edits to `Feasibility`, `Beneficiaries`, or the bibliography style unless the user explicitly expands scope.

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed.
- Test decision: tests-after using LaTeX compilation plus content checks
- QA policy: Every task includes executable grep/read/compile scenarios
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. <3 per wave (except final) = under-splitting.
> Extract shared dependencies as Wave-1 tasks for max parallelism.

Wave 1: foundation and verified-source seeding
- Task 1 — baseline citation ledger and scope freeze
- Task 2 — seed verified local-corpus BibTeX entries
- Task 3 — repair Motivation / Hypothesis / Novelty citation debt
- Task 4 — repair Background citation debt for O-RAN / AI-RAN / CHRONOS

Wave 2: target subsection expansion, related-work tightening, and validation
- Task 5 — vet SOTA serving sources and expand inference anatomy subsection
- Task 6 — tighten related-work claims on GPU sharing, orchestration, and RAN-aware scheduling
- Task 7 — compile and eliminate BibTeX/LaTeX failures plus surviving citation debt
- Task 8 — final academic-flow and scope-preservation pass

### Dependency Matrix (full, all tasks)
| Task | Depends On | Enables |
| :--- | :--- | :--- |
| 1 | none | 2, 3, 4, 5, 6 |
| 2 | 1 | 3, 4, 5, 6, 7 |
| 3 | 1, 2 | 7, 8 |
| 4 | 1, 2 | 7, 8 |
| 5 | 1, 2 | 7, 8 |
| 6 | 1, 2 | 7, 8 |
| 7 | 2, 3, 4, 5, 6 | 8 |
| 8 | 7 | Final Verification Wave |

### Agent Dispatch Summary (wave → task count → categories)
- Wave 1 → 4 tasks → `deep`, `writing`
- Wave 2 → 4 tasks → `writing`, `deep`, `quick`
- Final Verification → 4 tasks → `oracle`, `unspecified-high`, `deep`

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [x] 1. Build a citation-debt ledger and freeze scope

  **What to do**: Inventory all citation placeholders, unsupported exact metrics, and heading boundaries before editing. Build a working ledger that maps each target sentence or paragraph in `IPP/main.tex` to one primary source, one fallback source, and one planned BibTeX key. Freeze the approved edit scope to `main.tex:106-157` and `main.tex:181-250`, plus `IPP/main.bib`.
  **Must NOT do**: Do not edit prose yet. Do not touch `main.tex:162-168` (`Feasibility`, `Beneficiaries`). Do not change headings.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: this task decides all downstream evidence mapping and scope boundaries.
  - Skills: `[]` - no extra skills required.
  - Omitted: `[]` - none available.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 2, 3, 4, 5, 6 | Blocked By: none

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `IPP/main.tex:106-157` - dense citation debt in Motivation / Hypothesis / Novelty.
  - Pattern: `IPP/main.tex:181-250` - dense citation debt in Background / Related Work / Research Gap.
  - Pattern: `IPP/main.tex:206-221` - target subsection to expand in place.
  - Pattern: `IPP/main.tex:339-342` - confirms bibliography source file is `main.bib`.
  - API/Type: `IPP/main.bib:1-20` - currently almost empty; all domain entries must be added.
  - Pattern: `research paper/edge_ran_inference_research_matrix.md:38-60` - verified summary of CORA / SLA / Weaver / CHRONOS / Paradrop evidence.
  - Pattern: `research paper/edge_ran_inference_research_matrix.md:169-183` - bibliography metadata seed list for the local corpus.

  **Acceptance Criteria** (agent-executable only):
  - [ ] A ledger exists in working memory or evidence notes mapping every placeholder cluster in the approved ranges to at least one source and one BibTeX key.
  - [ ] Heading inventory from `IPP/main.tex` is captured before editing.
  - [ ] No files in `IPP/` are modified before the ledger is complete.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Baseline scope inventory
    Tool: Grep
    Steps: Search `IPP/main.tex` for `\\todo|Insert citation|Cite ` and separately for `^\\(section|subsection|subsubsection)\{`.
    Expected: Citation-debt hits are recorded; 26 headings are captured unchanged as the structural baseline.
    Evidence: .sisyphus/evidence/task-1-citation-ledger.md

  Scenario: Scope-guard failure check
    Tool: Read
    Steps: Read `IPP/main.tex:162-168` and confirm these stub sections are marked out of scope in the ledger.
    Expected: The ledger explicitly excludes `Feasibility` and `Beneficiaries` from editing.
    Evidence: .sisyphus/evidence/task-1-citation-ledger-scope.md
  ```

  **Commit**: NO | Message: `docs(ipp): freeze citation debt ledger` | Files: `IPP/main.tex`, `IPP/main.bib`

- [x] 2. Seed verified BibTeX entries for the local corpus

  **What to do**: Populate `IPP/main.bib` with stable keys for the local papers actually cited in the proposal: Weaver, CORA, CHRONOS, Paradrop, AIRAN, Beyond Connectivity, Open/O-RAN architecture sources, and SLA-aware distributed inference. Verify title, authors, year, venue, DOI, and URL against the PDF front matter or official paper page before insertion. Use memorable lowercase keys and freeze them before touching prose.
  **Must NOT do**: Do not add speculative fields. Do not cite local markdown notes as final bibliography entries. Do not add blog-only sources.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: BibTeX construction is structured documentation work with strict syntax requirements.
  - Skills: `[]` - no extra skills required.
  - Omitted: `[]` - none available.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 3, 4, 5, 6, 7 | Blocked By: 1

  **References** (executor has NO interview context - be exhaustive):
  - API/Type: `IPP/main.bib:1-20` - active bibliography file to populate.
  - Test: `research paper/edge_ran_inference_research_matrix.md:169-183` - pre-collected metadata for CORA, CHRONOS, Paradrop, SLA-aware distributed inference, and Weaver status.
  - Pattern: `research paper/CORA.pdf` - verify authors/venue/year if needed.
  - Pattern: `research paper/CHRONOS.pdf` - verify authors/venue/year if needed.
  - Pattern: `research paper/paradrop.pdf` - verify conference metadata.
  - Pattern: `research paper/AIRAN.pdf` - verify title and publication form.
  - Pattern: `research paper/beyond.pdf` - verify title and publication form.
  - Pattern: `research paper/open&airan.pdf` - verify title and publication form.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `IPP/main.bib` contains valid entries for all local sources used in Tasks 3, 4, and 6.
  - [ ] Every key planned in the ledger exists exactly once in `IPP/main.bib`.
  - [ ] BibTeX syntax is valid enough for `bibtex` to run without parse errors.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Key seeding success
    Tool: Grep
    Steps: Search `IPP/main.bib` for the frozen keys for weaver, cora, chronos, paradrop, airan, beyond, and sla-aware inference.
    Expected: Each key is present exactly once as an `@...{key,` entry.
    Evidence: .sisyphus/evidence/task-2-bib-keys.txt

  Scenario: BibTeX syntax failure check
    Tool: Bash
    Steps: Run `latexmk -pdf -interaction=nonstopmode -halt-on-error "IPP/main.tex"` after only the BibTeX seeding change.
    Expected: No BibTeX parse error; compile may still show undefined citations before Tasks 3-6, but bibliography syntax is accepted.
    Evidence: .sisyphus/evidence/task-2-bib-seed.log
  ```

  **Commit**: NO | Message: `docs(ipp): add verified bibliography seeds` | Files: `IPP/main.bib`

- [x] 3. Repair Motivation, Hypothesis, and Novelty citation debt

  **What to do**: Rewrite the prose in `main.tex:106-157` so that each factual claim is supported by a stable citation and, where evidence exists, a concrete metric. Specifically: replace the AI-RAN placeholder at `106`, the edge-offload justification at `106-107`, Weaver spare-compute claims at `108`, training-vs-inference framing at `119-121`, the CORA-inspired end-to-end objective at `137`, and the novelty paragraph at `153-157`. Reconcile the tension between “evaluate MIG” and “MIG is too rigid” by presenting MIG as a comparison baseline or hard-isolation option, not the presumed final answer.
  **Must NOT do**: Do not overclaim that inference is universally both compute- and memory-bound; state the phase split precisely. Do not retain filename placeholders or unsupported exact numbers.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: this is academic prose surgery with evidence integration.
  - Skills: `[]` - no extra skills required.
  - Omitted: `[]` - none available.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 7, 8 | Blocked By: 1, 2

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `IPP/main.tex:106-157` - exact edit window.
  - Pattern: `research paper/ai_ran_architecture_cross_paper_synthesis.md:24-39` - AI-RAN hierarchy and orchestration framing.
  - Pattern: `research paper/edge_ran_inference_research_matrix.md:38-47` - CORA, SLA-aware inference, Weaver summaries.
  - Pattern: `weaver_fm_training_vs_ldpc_experiments.md:59-64` - LDPC ~700 microseconds / 35% SMU / 12% ACU / up to 60% GBU findings.
  - Pattern: `weaver_fm_training_vs_ldpc_experiments.md:100-142` - direct contrast between FM training and LLM decoding resource profiles; multi-DU spare-compute numbers.
  - Pattern: `research paper/edge_ran_inference_research_matrix.md:42-46` - 0.5 s / 1.0 s SLA tiers and quantization caveats from the local SLA paper.
  - Test: `research paper/edge_ran_inference_research_matrix.md:169-183` - metadata anchors for CORA / Weaver / SLA-aware inference.

  **Acceptance Criteria** (agent-executable only):
  - [ ] No citation placeholder remains in `main.tex:106-157`.
  - [ ] The Weaver paragraph cites a real key and includes only metrics that are explicitly supported by the local corpus.
  - [ ] The hypothesis paragraph distinguishes training compatibility from inference difficulty without overstating universal inference behavior.
  - [ ] MIG is framed consistently as a comparison point or isolation mechanism, not as the settled design choice.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Placeholder removal in motivation cluster
    Tool: Read
    Steps: Read `IPP/main.tex` lines 106-157 after editing.
    Expected: The cluster contains `\cite{...}` calls, no `\todo` citation placeholders, and academically smoother transitions.
    Evidence: .sisyphus/evidence/task-3-motivation-snippet.txt

  Scenario: Unsupported-number failure check
    Tool: Grep
    Steps: Search `IPP/main.tex` for `40\\% and 85\\%|0.3 seconds|7 seconds|200 ms|400 ms` and inspect each hit for adjacent `\cite{}`.
    Expected: Every surviving exact number in this range has an adjacent citation or has been softened.
    Evidence: .sisyphus/evidence/task-3-metric-audit.txt
  ```

  **Commit**: NO | Message: `docs(ipp): replace motivation and hypothesis placeholders` | Files: `IPP/main.tex`

- [x] 4. Repair Background citation debt for O-RAN, AI-RAN, and timing constraints

  **What to do**: Replace the placeholders in `main.tex:181-205` with evidence-backed academic citations and lightly paraphrased prose. Strengthen the cloud-native O-RAN explanation with a single coherent citation chain, ground the slot-timing statements using CHRONOS, and preserve the AI-RAN three-pillar taxonomy while citing the local AI-RAN material rather than filenames.
  **Must NOT do**: Do not invent standards language that is not supported by the cited sources. Do not add new subsections.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: section-level literature synthesis and citation insertion.
  - Skills: `[]` - no extra skills required.
  - Omitted: `[]` - none available.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 7, 8 | Blocked By: 1, 2

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `IPP/main.tex:181-205` - exact edit window.
  - Pattern: `research paper/ai_ran_architecture_cross_paper_synthesis.md:24-39` - hierarchy and orchestration synthesis.
  - Pattern: `research paper/edge_ran_inference_research_matrix.md:59-60` - CHRONOS timing-fidelity summary.
  - Pattern: `research paper/edge_ran_inference_research_matrix.md:169-183` - metadata anchors.
  - Pattern: `research paper/open&airan.pdf` - O-RAN split / cloud-native architecture source.
  - Pattern: `research paper/AIRAN.pdf` - AI-RAN taxonomy source.
  - Pattern: `research paper/beyond.pdf` - AI-RAN orchestrator / O-Cloud convergence source.
  - Pattern: `research paper/CHRONOS.pdf` - sub-ms slot budget and timing sensitivity source.

  **Acceptance Criteria** (agent-executable only):
  - [ ] No placeholder remains in `main.tex:181-205`.
  - [ ] The O-RAN architecture statements cite verified O-RAN / AI-RAN sources.
  - [ ] The slot-timing and resource-demand claims cite CHRONOS or another validated local source.
  - [ ] The AI-RAN pillars are preserved structurally and cite real keys.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Background citation insertion
    Tool: Read
    Steps: Read `IPP/main.tex` lines 181-205 after editing.
    Expected: Every previously placeholder-backed paragraph now contains real `\cite{}` keys and no filename placeholders.
    Evidence: .sisyphus/evidence/task-4-background-snippet.txt

  Scenario: Structure-preservation failure check
    Tool: Grep
    Steps: Search `IPP/main.tex` for `^\\(section|subsection|subsubsection)\{` and compare with the baseline from Task 1.
    Expected: The heading list is unchanged.
    Evidence: .sisyphus/evidence/task-4-heading-audit.txt
  ```

  **Commit**: NO | Message: `docs(ipp): cite background and AI-RAN context` | Files: `IPP/main.tex`

- [x] 5. Expand the inference-anatomy subsection with SOTA serving systems

  **What to do**: Rewrite `main.tex:206-221` in place to combine the local SLA/CORA evidence with modern serving-system literature. The final text must explicitly explain that prefill is prompt-parallel and typically compute-dense, while decoding is token-serial and usually memory/KV-cache limited. Add citations to foundational and current serving systems: at minimum include PagedAttention/vLLM, one scheduling paper focused on prefill/decode interference or chunked prefill (Sarathi-Serve), and one prefill/decode disaggregation paper (DistServe). TensorRT-LLM may be cited only from official documentation or repository pages and only for implementation-context claims such as inflight batching or KV-cache reuse; it must not become the sole source for the conceptual argument.
  **Must NOT do**: Do not turn the subsection into a product survey. Do not cite blogs. Do not claim that “2026 systems all use disaggregation” unless that statement is explicitly qualified.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: cross-source synthesis across local corpus and modern serving papers.
  - Skills: `[]` - no extra skills required.
  - Omitted: `[]` - none available.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 7, 8 | Blocked By: 1, 2

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `IPP/main.tex:206-221` - exact subsection to rewrite in place.
  - Pattern: `research paper/edge_ran_inference_research_matrix.md:38-46` - CORA, SLA-aware inference, TTFT, quantization, and feasibility support.
  - Pattern: `llm-ran-obsidian-vault/concepts/phase-aware-llm-serving.md:8-21` - phase-aware serving structure.
  - Pattern: `llm-ran-obsidian-vault/concepts/serving-slos.md:8-18` - TTFT and token-latency framing.
  - Pattern: `llm-ran-obsidian-vault/01-comprehensive-analysis.md:139-155` - prefill/decode decomposition and KV-cache affinity rationale.
  - External: `https://dl.acm.org/doi/10.1145/3600006.3613165` - PagedAttention paper; foundational source for vLLM memory management.
  - External: `https://www.usenix.org/system/files/osdi24-agrawal.pdf` - Sarathi-Serve OSDI 2024; chunked prefill / throughput-latency tradeoff.
  - External: `https://www.usenix.org/system/files/osdi24-zhong-yinmin.pdf` - DistServe OSDI 2024; prefill/decode disaggregation.
  - External: `https://github.com/NVIDIA/TensorRT-LLM` - official TensorRT-LLM project page for implementation-context claims only.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `main.tex:206-221` contains explicit cited discussion of prefill vs decoding.
  - [ ] The subsection includes at least one cited KV-cache or memory-management statement.
  - [ ] The subsection includes at least one cited batching/scheduling statement.
  - [ ] The subsection ties phase-aware inference behavior back to AI-RAN contention risk rather than reading as a generic LLM tutorial.
  - [ ] New BibTeX entries for vLLM/PagedAttention, Sarathi-Serve, and DistServe are added before cite insertion.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Target subsection content check
    Tool: Read
    Steps: Read `IPP/main.tex` lines 206-221 after rewriting.
    Expected: The text names prefill and decoding, cites modern serving systems, and keeps the original subsection heading unchanged.
    Evidence: .sisyphus/evidence/task-5-inference-anatomy.txt

  Scenario: Source-quality failure check
    Tool: Grep
    Steps: Search `IPP/main.bib` for `developer\.nvidia\.com|docs\.vllm\.ai|medium\.com|dev\.to`.
    Expected: No low-quality blog/tutorial sources are present; if TensorRT-LLM is included, it comes from the official GitHub project or an official NVIDIA documentation page only.
    Evidence: .sisyphus/evidence/task-5-source-quality.txt
  ```

  **Commit**: NO | Message: `docs(ipp): expand inference anatomy with serving systems` | Files: `IPP/main.tex`, `IPP/main.bib`

- [x] 6. Tighten related-work claims on GPU sharing and orchestration

  **What to do**: Rewrite `main.tex:224-250` so the related-work section uses real citations and balanced claims. Ground the RAN-SLA urgency with CHRONOS, the training-vs-inference hardware split with Weaver + local SLA notes, the Paradrop orchestration paragraph with a real Paradrop citation, the CORA paragraph with its end-to-end budgeting data, and the Weaver paragraph with concrete spare-compute and sharing-overhead numbers. Keep the research-gap paragraph focused on the absence of an inference-specific micro-scheduler for shared RAN GPUs.
  **Must NOT do**: Do not oversell Weaver as direct evidence that LLM decoding is safe on shared RAN GPUs; Weaver is a cautionary and contrastive reference because its direct workload match is FM training, not decode.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: evidence-backed literature comparison and claim tightening.
  - Skills: `[]` - no extra skills required.
  - Omitted: `[]` - none available.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 7, 8 | Blocked By: 1, 2

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `IPP/main.tex:224-250` - exact edit window.
  - Pattern: `research paper/edge_ran_inference_research_matrix.md:38-60` - synthesized evidence for CORA / SLA / Weaver / CHRONOS / Paradrop.
  - Pattern: `weaver_fm_training_vs_ldpc_experiments.md:59-64` - ~700 microseconds LDPC latency and utilization metrics.
  - Pattern: `weaver_fm_training_vs_ldpc_experiments.md:100-142` - FM training vs LLM decode and multi-DU spare capacity.
  - Pattern: `weaver_fm_training_vs_ldpc_experiments.md:162-172` - temporal/spatial spare-compute findings.
  - Pattern: `research paper/ai_ran_architecture_cross_paper_synthesis.md:33-39` - hard guarantees still need profiling and conservative isolation.
  - Test: `research paper/edge_ran_inference_research_matrix.md:169-183` - metadata anchors.

  **Acceptance Criteria** (agent-executable only):
  - [ ] No placeholder remains in `main.tex:224-250`.
  - [ ] MPS and MIG overhead claims have adjacent citations or are softened.
  - [ ] The related-work section clearly distinguishes training evidence from inference evidence.
  - [ ] The research-gap paragraph still preserves the proposal’s core hypothesis.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Related-work evidence check
    Tool: Read
    Steps: Read `IPP/main.tex` lines 224-250 after editing.
    Expected: All prior `Cite:` placeholders are gone and the section reads as a comparative literature review.
    Evidence: .sisyphus/evidence/task-6-related-work.txt

  Scenario: Overclaim failure check
    Tool: Grep
    Steps: Search `IPP/main.tex` for phrases like `proved`, `guarantees`, or `safe` near Weaver/LLM decoding claims in this range.
    Expected: Wording is qualified where direct evidence is absent.
    Evidence: .sisyphus/evidence/task-6-overclaim-audit.txt
  ```

  **Commit**: NO | Message: `docs(ipp): tighten related work and research gap` | Files: `IPP/main.tex`

- [x] 7. Compile and remove remaining citation/build failures

  **What to do**: Run the full LaTeX/BibTeX pipeline, inspect the log, and fix all undefined citations, malformed BibTeX, or invalid LaTeX introduced by Tasks 2-6. Remove surviving citation-debt markers in the approved ranges. If the compiler reveals unsupported references or syntax problems, fix them immediately before proceeding.
  **Must NOT do**: Do not widen scope into rewriting unrelated sections. Do not leave a successful PDF with unresolved undefined citations.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: this is a deterministic validation-and-fix loop.
  - Skills: `[]` - no extra skills required.
  - Omitted: `[]` - none available.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: 8 | Blocked By: 2, 3, 4, 5, 6

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `IPP/main.tex:339-342` - active bibliography wiring.
  - Test: `IPP/main.bib` - seeded bibliography entries.
  - Test: `IPP/main.tex:106-157` - first edited range.
  - Test: `IPP/main.tex:181-250` - second edited range.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `latexmk -pdf -interaction=nonstopmode -halt-on-error "IPP/main.tex"` exits successfully.
  - [ ] `IPP/main.log` contains no undefined citations, no undefined control sequences, and no emergency stop.
  - [ ] `grep` finds no `\todo`, `Insert citation`, or `Cite ` markers in the approved edited ranges.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Full compile success
    Tool: Bash
    Steps: Run `latexmk -pdf -interaction=nonstopmode -halt-on-error "IPP/main.tex"` from the repo root.
    Expected: Exit code 0 and generated PDF/log files under `IPP/`.
    Evidence: .sisyphus/evidence/task-7-latexmk.log

  Scenario: Undefined-citation failure check
    Tool: Grep
    Steps: Search `IPP/main.log` for `Citation .* undefined|There were undefined citations|Undefined control sequence|Emergency stop`.
    Expected: Zero matches.
    Evidence: .sisyphus/evidence/task-7-log-audit.txt
  ```

  **Commit**: NO | Message: `docs(ipp): validate latex and fix bibliography issues` | Files: `IPP/main.tex`, `IPP/main.bib`

- [x] 8. Run a final academic-flow and scope-preservation pass

  **What to do**: Perform one final read-through of the edited ranges only. Tighten transitions, remove repetitive phrasing, ensure every numeric claim still has evidence, and confirm that the writing now sounds like a coherent academic proposal rather than a patched draft. Verify that headings, methodology scope, and the AI-and-RAN hypothesis are unchanged.
  **Must NOT do**: Do not introduce new citations or claims unless required to repair a documented issue from Task 7. Do not edit outside the approved ranges.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: final prose quality pass with strict scope control.
  - Skills: `[]` - no extra skills required.
  - Omitted: `[]` - none available.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: Final Verification Wave | Blocked By: 7

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `IPP/main.tex:106-157` - Motivation / Hypothesis / Novelty range.
  - Pattern: `IPP/main.tex:181-250` - Background / Related Work / Gap range.
  - Pattern: `IPP/main.tex:100-272` - surrounding structure that must remain intact.
  - Pattern: `IPP/main.tex:123-124` - hypothesis text to preserve semantically.
  - Test: `IPP/main.tex:206-221` - target subsection that must still read naturally inside its original section.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Edited sections read coherently and use academically appropriate transitions.
  - [ ] No structural heading changes occurred.
  - [ ] The proposal still argues the same AI-and-RAN hypothesis, only with stronger evidence and cleaner wording.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Scope-preservation audit
    Tool: Grep
    Steps: Re-run the heading inventory search from Task 1 and compare against the baseline.
    Expected: Exact same heading list as the baseline.
    Evidence: .sisyphus/evidence/task-8-heading-final.txt

  Scenario: Final prose spot-check
    Tool: Read
    Steps: Read `IPP/main.tex` lines 106-157 and 181-250.
    Expected: The prose is citation-backed, free of placeholder language, and structurally unchanged.
    Evidence: .sisyphus/evidence/task-8-prose-check.txt
  ```

  **Commit**: NO | Message: `docs(ipp): polish academic flow and preserve scope` | Files: `IPP/main.tex`

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.
- [ ] F1. Plan Compliance Audit — oracle
- [ ] F2. Code Quality Review — unspecified-high
- [ ] F3. Real Manual QA — unspecified-high
- [ ] F4. Scope Fidelity Check — deep

## Commit Strategy
- Workspace status: this directory is **not** currently a git repository.
- Default execution mode: use the four planned checkpoints as patch/diff milestones rather than actual commits.
- If the user later initializes git, use these commit messages in order:
  1. `docs: add verified bibliography seeds for local corpus and serving papers`
  2. `docs: replace IPP citation placeholders with verified keys`
  3. `docs: expand latency-critical inference anatomy with phase-aware serving sources`
  4. `docs: validate latex output and tighten unsupported claims`

## Success Criteria
- The proposal compiles cleanly.
- `IPP/main.bib` contains the sources needed for the edited sections.
- The edited ranges no longer contain citation placeholders.
- The inference-anatomy subsection explicitly and correctly describes prefill, decoding, KV-cache pressure, batching/disaggregation, and AI-RAN contention implications.
- The structure and AI-and-RAN hypothesis remain intact.
