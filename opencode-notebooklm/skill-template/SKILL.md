---
name: notebooklm-enterprise-research
description: Use NotebookLM Enterprise APIs to manage notebooks and sources as a controlled evidence container for OpenCode-led research. Synthesis/writing is performed in OpenCode (not via a NotebookLM chat API).
version: 0.1.0
author: opencode-local
license: MIT
tags: [notebooklm, research, enterprise-api, evidence-synthesis]
dependencies: [python3, gcloud]
---

# notebooklm-enterprise-research

## Overview

This skill operationalizes NotebookLM Enterprise as a **research notebook backend** while OpenCode handles orchestration, quality checks, and output generation.

Use this skill when you need to:
- access existing NotebookLM Enterprise notebooks,
- create/share notebooks for team research,
- ingest/update sources (PDF/web/text/Drive-backed content),
- convert notebook insights into structured outputs (tables, claims, evidence maps, draft sections).

## Required setup

1. NotebookLM Enterprise is enabled for the target Google Cloud project.
2. Discovery Engine API is enabled.
3. You have correct IAM permissions.
4. Local auth is initialized:

```bash
gcloud auth login
# for Google Drive source support
gcloud auth login --enable-gdrive-access
```

5. Environment variables are set:

```bash
export NOTEBOOKLM_PROJECT_NUMBER="123456789012"
export NOTEBOOKLM_LOCATION="us"
export NOTEBOOKLM_ENDPOINT_LOCATION="us"
```

## Workflow (research-first)

### Phase 1 — Clarify objective
- Convert user question into explicit research objective, constraints, and output format.
- Define acceptance criteria (e.g., number of sources, confidence threshold, citation completeness).

### Phase 2 — Notebook targeting
- List recently viewed notebooks (`listRecentlyViewed`) and match to objective.
- If none match, create a new notebook with a deterministic title.

### Phase 3 — Source lifecycle
- Ingest sources via `sources.uploadFile` for local files.
- Use `sources.batchCreate` for web/text/Drive-backed entries (`userContents` payload shape).
- Record source IDs and provenance metadata in the project output.
- If using sharing, ensure recipients are licensed and role/IAM constraints are satisfied before collaboration.
### Phase 4 — Synthesis loop in OpenCode
- Extract claims and supporting evidence into structured markdown.
- Separate:
  - direct evidence,
  - inferred conclusions,
  - open questions/gaps.
- Keep citation traceability per claim.

### Phase 5 — Deliverables
Produce one or more:
- evidence table (`claim | source | confidence | caveats`)
- concise literature synthesis
- contradiction/gap report
- draft manuscript section with citation placeholders

## Command helpers

Use the local client in this repo:

```bash
python opencode-notebooklm/notebooklm_enterprise_client.py list-recent --page-size 20
python opencode-notebooklm/notebooklm_enterprise_client.py create --title "Topic Notebook"
python opencode-notebooklm/notebooklm_enterprise_client.py source-upload --notebook-id "NOTEBOOK_ID" --file ./paper.pdf --mime-type application/pdf
```

## Must do

- Prefer official NotebookLM Enterprise API paths and documented methods.
- Keep an explicit evidence chain for every key claim.
- Track unresolved uncertainties as first-class outputs.
- Preserve reproducibility (stable notebook naming, stable output paths, deterministic formatting).

## Must not do

- Do not rely on unofficial/reverse-engineered NotebookLM endpoints in production.
- Do not present model-generated summaries as verified facts without source mapping.
- Do not drop caveats when source quality is weak or conflicting.

## Self-check before finalizing

- Notebook and source operations succeeded (IDs captured).
- Every major claim has at least one linked source.
- Conflicts and missing evidence are explicitly listed.
- Output matches requested format and scope.
