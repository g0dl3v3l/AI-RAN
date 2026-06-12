from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd

from inference_profile import plots


def test_render_utilization_heatmap_panel_aggregates_duplicates_with_mean() -> None:
    frame = pd.DataFrame(
        [
            {
                "model_id": "facebook/opt-125m",
                "chunk_tokens": 64,
                "sm_ai_partition": 8,
                "metric_value": 40.0,
            },
            {
                "model_id": "facebook/opt-125m",
                "chunk_tokens": 64,
                "sm_ai_partition": 8,
                "metric_value": 80.0,
            },
            {
                "model_id": "facebook/opt-125m",
                "chunk_tokens": 64,
                "sm_ai_partition": 16,
                "metric_value": 20.0,
            },
        ]
    )

    fig, axis = plt.subplots()
    try:
        image = plots._render_utilization_heatmap_panel(
            axis=axis,
            frame=frame,
            x_column="chunk_tokens",
            metric_label="GBU (%)",
            title="test",
            xlabel="Chunk",
            vmin=0.0,
            vmax=100.0,
            fallback_image=None,
        )
        matrix = image.get_array()
        assert float(matrix[0, 0]) == 60.0
        assert float(matrix[1, 0]) == 20.0
    finally:
        plt.close(fig)


def test_build_prefill_utilization_heatmap_frame_uses_mean() -> None:
    prefill_events_df = pd.DataFrame(
        [
            {
                "model_id": "facebook/opt-125m",
                "chunk_tokens": 64,
                "sm_ai_partition": 8,
                "gbu_pct": 40.0,
            },
            {
                "model_id": "facebook/opt-125m",
                "chunk_tokens": 64,
                "sm_ai_partition": 8,
                "gbu_pct": 80.0,
            },
            {
                "model_id": "facebook/opt-125m",
                "chunk_tokens": 64,
                "sm_ai_partition": 16,
                "gbu_pct": 20.0,
            },
        ]
    )

    frame = plots._build_prefill_utilization_heatmap_frame(
        prefill_events_df=prefill_events_df,
        metric_column="gbu_pct",
    )

    sm8 = frame[frame["sm_ai_partition"] == 8]
    sm16 = frame[frame["sm_ai_partition"] == 16]
    assert len(sm8) == 1
    assert len(sm16) == 1
    assert float(sm8.iloc[0]["metric_value"]) == 60.0
    assert float(sm16.iloc[0]["metric_value"]) == 20.0
