# Example: OpenCode + NotebookLM Enterprise Research Workflow

## Goal
Produce an evidence-grounded synthesis on a target topic while keeping NotebookLM as the managed notebook/source layer.

## Step-by-step

1. **Create/select notebook**
   - List recent notebooks.
   - Reuse if scope matches; otherwise create a new notebook.

2. **Ingest sources**
   - Upload PDFs and other local files.
   - Add web/text/Drive-backed sources via `batchCreate`.

3. **Extract evidence in OpenCode**
   - Build a claims table:

```text
claim | source_id | quote_or_data | confidence | caveats
```

4. **Synthesize outputs**
   - 1-page executive summary
   - contradiction/gap list
   - prioritized next-source list

5. **Finalize for downstream writing**
   - Export markdown artifacts into your repo.
   - Keep source IDs and notebook ID in metadata header.

## Suggested prompt pattern

"Use NotebookLM Enterprise notebook <NOTEBOOK_ID> sources as evidence ground truth. Extract top 10 claims, map each claim to explicit source evidence (quotes/data), list contradictions, then produce a concise synthesis with uncertainty labels."

## Optional additions

- Add `notebooks.share` for collaborator workflows.
- Add audio overview generation for rapid briefing (official API documented separately).
