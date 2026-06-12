from __future__ import annotations

import pandas as pd
import pytest

from inference_profile.plots import _plot_hardware_utilization_profiling
from inference_profile.simulator import _validate_revised_microscopic_telemetry


def test_hardware_utilization_plot_raises_when_microscopic_telemetry_missing(
    tmp_path,
) -> None:
    results_df = pd.DataFrame(
        [
            {
                "model_id": "facebook/opt-1.3b",
                "chunk_tokens": 256,
                "sequence_length": 1024,
                "prefill_gpu_util": 2.0,
                "decode_vram_gpu_util": 2.0,
                "decode_pcie_async_gpu_util": 2.0,
                "prefill_acu_pct": None,
                "prefill_gbu_pct": None,
                "prefill_smu_pct": None,
                "decode_vram_acu_pct": None,
                "decode_pcie_async_acu_pct": None,
                "decode_vram_gbu_pct": None,
                "decode_pcie_async_gbu_pct": None,
                "decode_vram_smu_pct": None,
                "decode_pcie_async_smu_pct": None,
            }
        ]
    )

    with pytest.raises(ValueError, match="Microscopic telemetry missing"):
        _plot_hardware_utilization_profiling(
            results_df=results_df,
            prefill_events_df=pd.DataFrame(),
            decode_events_df=pd.DataFrame(),
            model_constants_df=pd.DataFrame(),
            success_rows=pd.DataFrame(),
            trace_df=pd.DataFrame(),
            timeline_df=pd.DataFrame(),
            packed_timeline_df=pd.DataFrame(),
            exemplar_row=pd.Series(dtype="object"),
            plot5_chunk_selection={},
            plot_path=tmp_path / "hardware-utilization.png",
        )


def test_validate_revised_microscopic_telemetry_raises_when_null_present() -> None:
    simulation_inputs = pd.DataFrame(
        [
            {
                "model_id": "facebook/opt-1.3b",
                "chunk_tokens": 256,
                "sequence_length": 1024,
                "prefill_acu_pct": 79.0,
                "prefill_gbu_pct": None,
                "prefill_smu_pct": 67.5,
                "decode_vram_acu_pct": 56.5,
                "decode_vram_gbu_pct": 87.0,
                "decode_vram_smu_pct": 59.0,
                "decode_pcie_async_acu_pct": 56.5,
                "decode_pcie_async_gbu_pct": 87.0,
                "decode_pcie_async_smu_pct": 59.0,
            }
        ]
    )

    with pytest.raises(ValueError, match="Microscopic telemetry missing"):
        _validate_revised_microscopic_telemetry(simulation_inputs)
