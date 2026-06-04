from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping


def write_json(path: str | Path, record: Mapping[str, Any]) -> None:
    """Write a single JSON artifact to disk (atomic-ish).

    Writes to a temp file in the same directory and then replaces the target.
    """

    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = out_path.with_name(out_path.name + ".tmp")
    payload = json.dumps(record, sort_keys=True, indent=2)
    tmp_path.write_text(payload + "\n", encoding="utf-8")

    os.replace(tmp_path, out_path)


def append_jsonl(path: str | Path, record: Mapping[str, Any]) -> None:
    """Append a JSON record as one line to a JSONL file."""

    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    line = json.dumps(record, sort_keys=True)
    with out_path.open("a", encoding="utf-8") as f:
        f.write(line)
        f.write("\n")
