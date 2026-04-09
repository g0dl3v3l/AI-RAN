# Draft: Throughput Impact Plot

## Requirements (confirmed)
- [request]: "Guide me through creating a Throughput Impact Plot"
- [focus]: "Prefill throughput rescued by preventing constant SM preemption"
- [focus]: "Decode throughput rescued by throttling RAN GBU consumption"
- [plot]: "Grouped bar chart comparing Normalized Throughput (Tokens/s) of Prefill vs. Decode across Dedicated GPU, Bursty RAN, and Enveloped RAN"
- [process]: "Begin with Task 1 and ask me for confirmation before moving to the next steps."

## Technical Decisions
- [mode]: Research/data-audit first; no source-code implementation beyond planning artifacts unless required later

## Research Findings
- [oracle]: Real dedicated inference proxy data exists in `NVBenchSuite/analysis/data/exp_a_acu_gbu_data.csv` (phase-separated ACU/GBU), but no committed plot-ready direct inference-throughput dataset exists for Dedicated/Bursty/Enveloped scenarios.
- [oracle]: `MobiCom26-Eval` contains training/simulator throughput artifacts, not direct measured inference throughput suitable for the requested Prefill/Decode bar heights.
- [oracle]: `exp_c_heatmap_data.csv` should not be treated as measured throughput evidence.
- [missing-vars]: Need strict phase-throughput variables for Prefill and Decode under Dedicated GPU, Bursty RAN, and Enveloped RAN, with normalization to Dedicated.

## Open Questions
- [ ] Which exact existing files capture LDPC RAN execution profiles and training-throughput references?
- [ ] Final confirmation from repo audit: exact local file inventory for known data sources across `NVBenchSuite`, `MobiCom26-Eval`, and notes.

## Scope Boundaries
- INCLUDE: data audit, missing-variable checklist, experiment design guidance, plotting specification
- EXCLUDE: executing testbed collection in this turn
