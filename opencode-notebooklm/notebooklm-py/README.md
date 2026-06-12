# OpenCode + notebooklm-py (Unofficial Path)

This folder is a **parallel integration path** for users who explicitly choose
[`teng-lin/notebooklm-py`](https://github.com/teng-lin/notebooklm-py).

> Warning: `notebooklm-py` is unofficial and relies on undocumented/internal APIs.
> Expect breaking changes, auth flow changes, and maintenance overhead.

## What this adds

- `opencode_notebooklm_py_adapter.py` — OpenCode-friendly wrapper around the
  upstream `notebooklm` CLI.
- `skill-template/SKILL.md` — skill template for research workflows using this path.
- `examples/research_workflow.md` — a practical loop with evidence discipline.

## Install

```bash
pip install notebooklm-py
# optional browser-assisted login extras
pip install "notebooklm-py[browser]"
playwright install chromium
```

Optional environment override:

```bash
# if your CLI binary name/path differs
export NOTEBOOKLM_PY_BIN="notebooklm"
```

## Initial auth and health check

```bash
python opencode-notebooklm/notebooklm-py/opencode_notebooklm_py_adapter.py doctor
python opencode-notebooklm/notebooklm-py/opencode_notebooklm_py_adapter.py login
python opencode-notebooklm/notebooklm-py/opencode_notebooklm_py_adapter.py doctor --auth-test
```

## Core commands via adapter

```bash
python opencode-notebooklm/notebooklm-py/opencode_notebooklm_py_adapter.py create --title "RAN Reliability Literature 2026"
python opencode-notebooklm/notebooklm-py/opencode_notebooklm_py_adapter.py use --notebook-id "NOTEBOOK_ID"
python opencode-notebooklm/notebooklm-py/opencode_notebooklm_py_adapter.py source-add --kind web --value "https://example.com/paper"
python opencode-notebooklm/notebooklm-py/opencode_notebooklm_py_adapter.py ask --question "What are the key findings and open gaps?"
python opencode-notebooklm/notebooklm-py/opencode_notebooklm_py_adapter.py metadata
python opencode-notebooklm/notebooklm-py/opencode_notebooklm_py_adapter.py share-status
```

## Advanced passthrough

For any command not yet wrapped, use raw passthrough:

```bash
python opencode-notebooklm/notebooklm-py/opencode_notebooklm_py_adapter.py raw -- source add-research "latest papers on retrieval calibration" --max-results 5
```

## OpenCode wiring

1. Keep the enterprise kit (`../README.md`) as the production default.
2. Use this path only for user-selected unofficial workflows.
3. Build a local OpenCode skill from `./skill-template/SKILL.md`.
4. In skill runs, keep strict evidence mapping in OpenCode outputs:
   - claim,
   - source reference,
   - quote/data,
   - uncertainty/caveats.

## Upstream references (not local guarantees)

- Repo: https://github.com/teng-lin/notebooklm-py
- PyPI: https://pypi.org/project/notebooklm-py/

Re-validate command semantics against upstream README/changelog whenever upgrading.
