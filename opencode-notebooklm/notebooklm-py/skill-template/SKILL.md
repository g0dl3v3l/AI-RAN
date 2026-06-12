---
name: notebooklm-py-research-unofficial
description: Use notebooklm-py (unofficial) as a NotebookLM access layer for OpenCode research workflows with explicit evidence tracking and breakage-risk caveats.
version: 0.1.0
author: opencode-local
license: MIT
tags: [notebooklm, notebooklm-py, unofficial, research, evidence-synthesis]
dependencies: [python3, notebooklm-py]
---

# notebooklm-py-research-unofficial

## Overview

This skill is for teams that explicitly choose `teng-lin/notebooklm-py` despite
its unofficial/reverse-engineered nature.

Use this skill when you need to:
- run fast local NotebookLM workflows through `notebooklm` CLI,
- orchestrate notebook/source setup from OpenCode prompts,
- keep output quality controls (evidence maps, caveats, uncertainty labels).

## Required setup

1. Install upstream package:

```bash
pip install notebooklm-py
# optional browser login helpers
pip install "notebooklm-py[browser]"
playwright install chromium
```

2. Ensure CLI is callable:

```bash
python opencode-notebooklm/notebooklm-py/opencode_notebooklm_py_adapter.py doctor
```

3. Authenticate:

```bash
python opencode-notebooklm/notebooklm-py/opencode_notebooklm_py_adapter.py login
python opencode-notebooklm/notebooklm-py/opencode_notebooklm_py_adapter.py doctor --auth-test
```

## Workflow (research-first)

### Phase 1 — Scope and acceptance criteria
- Convert user request into objective + output schema.
- Define evidence requirements before generating synthesis.

### Phase 2 — Notebook targeting
- Create or select notebook:

```bash
python opencode-notebooklm/notebooklm-py/opencode_notebooklm_py_adapter.py create --title "Topic Notebook"
python opencode-notebooklm/notebooklm-py/opencode_notebooklm_py_adapter.py use --notebook-id "NOTEBOOK_ID"
```

### Phase 3 — Source ingestion
- Add sources (web/file/text) with adapter commands.
- For advanced ingestion (e.g., research search), use raw passthrough:

```bash
python opencode-notebooklm/notebooklm-py/opencode_notebooklm_py_adapter.py raw -- source add-research "query" --max-results 5
```

### Phase 4 — Evidence extraction in OpenCode
- Build a table: `claim | source_ref | quote_or_data | confidence | caveats`.
- Separate direct evidence from inference.

### Phase 5 — Deliverables
- concise synthesis,
- contradiction/gap list,
- next-source plan,
- citation/evidence map.

## Must do

- Mark this path as **unofficial** in outputs and handoffs.
- Keep strict claim-to-source mapping.
- Re-check upstream command/API behavior before upgrades.

## Must not do

- Do not present notebooklm-py behavior as Google-supported API guarantees.
- Do not drop uncertainty/caveats when evidence conflicts.
- Do not use this path for compliance-critical production workflows without fallback.

## Self-check before finalizing

- Auth works (`doctor --auth-test`).
- Notebook/source operations succeeded.
- Every key claim has traceable evidence.
- Output includes explicit unofficial-path caveat.
