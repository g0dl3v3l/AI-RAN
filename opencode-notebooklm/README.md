# OpenCode ↔ NotebookLM Enterprise Integration Kit

This folder gives you a production-minded starting point to let OpenCode workflows **access and manage NotebookLM Enterprise notebooks/sources** and run repeatable research loops.

## What is official vs fallback

- **Official and recommended**: NotebookLM Enterprise APIs under Gemini Enterprise / Discovery Engine (`v1alpha` paths).
- **Not recommended for production**: unofficial wrappers/reverse-engineered endpoints (higher breakage/compliance risk).
- **If you explicitly choose the unofficial path**: see `./notebooklm-py/` for a contained OpenCode setup using `teng-lin/notebooklm-py`.

## Confirmed official docs (pinned)

- Notebooks API: https://docs.cloud.google.com/gemini/enterprise/notebooklm-enterprise/docs/api-notebooks
- Sources API: https://docs.cloud.google.com/gemini/enterprise/notebooklm-enterprise/docs/api-notebooks-sources
- Setup: https://docs.cloud.google.com/gemini/enterprise/notebooklm-enterprise/docs/set-up-notebooklm
- Access in Gemini Enterprise: https://docs.cloud.google.com/gemini/enterprise/docs/access-notebooklm
- Audio overview API: https://docs.cloud.google.com/gemini/enterprise/notebooklm-enterprise/docs/api-audio-overview

## Confirmed API surface

### Notebook lifecycle
- `notebooks.create`
- `notebooks.get`
- `notebooks.listRecentlyViewed`
- `notebooks.batchDelete`
- `notebooks.share`

### Source lifecycle
- `notebooks.sources.batchCreate`
- `notebooks.sources.uploadFile`
- `notebooks.sources.get`
- `notebooks.sources.batchDelete`

Note: `notebooks.sources.uploadFile` uses the `/upload/v1alpha/.../sources:uploadFile` endpoint and requires `X-Goog-Upload-Protocol: raw` plus `X-Goog-Upload-File-Name` headers.
### Endpoint pattern

```text
https://ENDPOINT_LOCATION-discoveryengine.googleapis.com/v1alpha/projects/PROJECT_NUMBER/locations/LOCATION/...
```

Common location values in docs/examples: `us`, `eu`, `global`.

## Prerequisites

1. Google Cloud project with NotebookLM Enterprise configured.
2. Discovery Engine API enabled.
3. IAM roles assigned (NotebookLM Enterprise admin/user as required).
4. NotebookLM Enterprise license is active for the calling user account.
5. Auth initialized:

```bash
gcloud auth login
# If Drive-backed source ingestion is needed:
gcloud auth login --enable-gdrive-access
```

## Environment variables

```bash
export NOTEBOOKLM_PROJECT_NUMBER="123456789012"
export NOTEBOOKLM_LOCATION="us"
# Optional; defaults to NOTEBOOKLM_LOCATION
export NOTEBOOKLM_ENDPOINT_LOCATION="us"
# Optional if you want explicit token injection
# export NOTEBOOKLM_BEARER_TOKEN="ya29...."
```

## Quickstart commands

From this folder:

```bash
python notebooklm_enterprise_client.py list-recent --page-size 10
python notebooklm_enterprise_client.py create --title "RAN Reliability Literature 2026"
python notebooklm_enterprise_client.py get --notebook-id "NOTEBOOK_ID"
python notebooklm_enterprise_client.py source-upload --notebook-id "NOTEBOOK_ID" --file ./paper.pdf --mime-type application/pdf
```

For non-file source ingestion with `batchCreate`, create a request payload and run:

```json
{
  "userContents": [
    {
      "webContent": {
        "url": "https://example.com",
        "sourceName": "Example web source"
      }
    }
  ]
}
```

Save that as `./sources_payload.json`, then run:

```bash
python notebooklm_enterprise_client.py source-batch-create --notebook-id "NOTEBOOK_ID" --payload-json ./sources_payload.json
```

## How to wire this into OpenCode

1. Use this client as your **NotebookLM access layer**.
2. Build/extend a local OpenCode skill from `skill-template/SKILL.md`.
3. In the skill workflow:
   - map research goal → target notebook,
   - ingest/update sources,
   - trigger synthesis steps in OpenCode,
   - export structured notes/citation tables to your repo.

## Research workflow recommendation

See `examples/research_workflow.md` for a reproducible loop that keeps NotebookLM as the synthesis workspace while OpenCode orchestrates data collection, evidence extraction, and reporting.

## Optional unofficial setup (user-selected)

If you intentionally want to use `teng-lin/notebooklm-py` in OpenCode, use the parallel starter in:

```text
opencode-notebooklm/notebooklm-py/
```

That path includes:
- `opencode_notebooklm_py_adapter.py` (CLI wrapper for OpenCode automation),
- `README.md` setup instructions,
- `skill-template/SKILL.md` for research workflow orchestration,
- `examples/research_workflow.md` prompt/runbook.

Use this route only when you accept unofficial API instability and possible authentication flow changes.

## Important behavioral constraints

- Imported sources can behave as snapshots/copies (not always live-linked updates).
- Sharing and role behavior is enterprise-policy and IAM constrained (including recipient licensing and role prerequisites such as Cloud NotebookLM User).
- Use role enums from the official API (`PROJECT_ROLE_READER`, `PROJECT_ROLE_WRITER`, `PROJECT_ROLE_OWNER`) when calling `notebooks.share`.
- Quotas/limits are enterprise-plan dependent.
- API is currently documented under `v1alpha`; pin assumptions and revalidate before production hardening.
