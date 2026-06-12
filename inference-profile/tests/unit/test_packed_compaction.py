import pandas as pd
from inference_profile import plots


def test_compact_packed_variant_rows_merges_contiguous():
    rows = [
        {
            "task_id": 0,
            "phase": "prefill",
            "mode": "vram",
            "trace_interval_index": 1,
            "start_time_ms": 0.0,
            "end_time_ms": 1.0,
            "duration_ms": 1.0,
        },
        {
            "task_id": 0,
            "phase": "prefill",
            "mode": "vram",
            "trace_interval_index": 1,
            "start_time_ms": 1.0,
            "end_time_ms": 2.0,
            "duration_ms": 1.0,
        },
        # different trace index -> should not merge
        {
            "task_id": 0,
            "phase": "prefill",
            "mode": "vram",
            "trace_interval_index": 2,
            "start_time_ms": 2.0,
            "end_time_ms": 3.0,
            "duration_ms": 1.0,
        },
        # different task -> should be separate
        {
            "task_id": 1,
            "phase": "prefill",
            "mode": "vram",
            "trace_interval_index": 1,
            "start_time_ms": 0.5,
            "end_time_ms": 1.5,
            "duration_ms": 1.0,
        },
    ]
    df = pd.DataFrame(rows)
    compacted = plots._build_packed_task_trace_data(df, left=0.0, right=10.0)
    # compacted returns trace entries grouped by label; find prefill label
    found = [t for t in compacted if t[0] == "Prefill"]
    assert found, "Prefill label should be present"
    label, x_vals, y_vals, hover = found[0]
    # After compaction task 0 should have a merged span from 0.0 to 2.0
    assert any(x is not None and abs(x - 0.0) < 1e-6 for x in x_vals)
    assert any(x is not None and abs(x - 2.0) < 1e-6 for x in x_vals)
