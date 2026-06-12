# Example: OpenCode + notebooklm-py Research Workflow (Unofficial)

## Goal

Produce an evidence-grounded synthesis while using `notebooklm-py` as the
NotebookLM interaction layer.

## Step-by-step

1. **Health check + auth**

```bash
python opencode-notebooklm/notebooklm-py/opencode_notebooklm_py_adapter.py doctor
python opencode-notebooklm/notebooklm-py/opencode_notebooklm_py_adapter.py login
python opencode-notebooklm/notebooklm-py/opencode_notebooklm_py_adapter.py doctor --auth-test
```

2. **Create/select notebook**

```bash
python opencode-notebooklm/notebooklm-py/opencode_notebooklm_py_adapter.py create --title "Topic Notebook"
python opencode-notebooklm/notebooklm-py/opencode_notebooklm_py_adapter.py use --notebook-id "NOTEBOOK_ID"
```

3. **Add sources**

```bash
python opencode-notebooklm/notebooklm-py/opencode_notebooklm_py_adapter.py source-add --kind web --value "https://example.com/paper"
python opencode-notebooklm/notebooklm-py/opencode_notebooklm_py_adapter.py raw -- source add-research "latest papers on topic" --max-results 5
```

4. **Ask and capture evidence**

```bash
python opencode-notebooklm/notebooklm-py/opencode_notebooklm_py_adapter.py ask --question "Extract the top 10 claims with source evidence."
python opencode-notebooklm/notebooklm-py/opencode_notebooklm_py_adapter.py metadata
```

5. **Synthesize in OpenCode**

Build outputs with explicit traceability:

```text
claim | source_ref | quote_or_data | confidence | caveats
```

## Suggested prompt pattern

"Use notebooklm-py outputs as candidate evidence only. Produce 10 claims, map each claim to explicit source-backed quotes/data, list contradictions, and output a concise synthesis with uncertainty labels and caveats."

## Caveat

This flow depends on an unofficial client (`teng-lin/notebooklm-py`) and may
break when upstream internal APIs or auth behavior change.
