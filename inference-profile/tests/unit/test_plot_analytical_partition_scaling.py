from __future__ import annotations

import pandas as pd
import pytest

from inference_profile import experiments
from inference_profile.plots import _build_prefill_safety_boundary_frame


def test_prefill_safety_boundary_uses_analytical_scaling_for_revised_runs() -> None:
    results_df = pd.DataFrame(
        [
            {
                "model_id": "facebook/opt-1.3b",
                "chunk_tokens": 256,
                "status": "success",
                "experiment_type": experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE,
                "prefill_max_gemm_us": 100.0,
                "prefill_max_gemm_us_sm8": 1.0,
                "prefill_max_gemm_us_sm16": 1.0,
                "prefill_max_gemm_us_sm24": 1.0,
                "prefill_max_gemm_us_sm32": 1.0,
            }
        ]
    )

    frame = _build_prefill_safety_boundary_frame(results_df)
    frame = frame.sort_values("sm_ai_partition").reset_index(drop=True)

    assert frame["sm_ai_partition"].tolist() == [8, 16, 24, 32]
    assert frame["prefill_max_gemm_us"].tolist() == [
        pytest.approx(600.0),
        pytest.approx(300.0),
        pytest.approx(200.0),
        pytest.approx(150.0),
    ]
