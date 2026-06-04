import json
from pathlib import Path

from ai_runtime_experiments.artifacts import append_jsonl, write_json
from ai_runtime_experiments.schemas import ProbeStatus, make_probe_result


def test_append_jsonl_writes_two_records(tmp_path: Path):
    jsonl_path = tmp_path / "events.jsonl"

    record_1 = make_probe_result(
        run_id="run_001",
        component="smoke_request",
        status=ProbeStatus.OK,
        details={"seq": 1},
        timestamp_utc="2026-01-01T00:00:00Z",
        monotonic_ns=1,
    )
    record_2 = make_probe_result(
        run_id="run_001",
        component="smoke_request",
        status=ProbeStatus.OK,
        details={"seq": 2},
        timestamp_utc="2026-01-01T00:00:01Z",
        monotonic_ns=2,
    )

    append_jsonl(jsonl_path, record_1)
    append_jsonl(jsonl_path, record_2)

    lines = jsonl_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == record_1
    assert json.loads(lines[1]) == record_2


def test_write_json_writes_parseable_file(tmp_path: Path):
    json_path = tmp_path / "artifact.json"
    record = make_probe_result(
        run_id="run_001",
        component="docker",
        status=ProbeStatus.SKIPPED,
        details={"reason": "dry-run"},
        timestamp_utc="2026-01-01T00:00:00Z",
        monotonic_ns=999,
    )

    write_json(json_path, record)

    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert parsed == record
