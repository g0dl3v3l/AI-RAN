from __future__ import annotations

import csv
from pathlib import Path

import pytest
import torch

from inference_profile import pcie_profile

_OPT_125M_CONFIG = {
    "hidden_size": 768,
    "num_hidden_layers": 12,
    "num_attention_heads": 12,
    "ffn_dim": 3072,
    "max_position_embeddings": 2048,
    "vocab_size": 50272,
    "word_embed_proj_dim": 768,
    "do_layer_norm_before": True,
}


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.mark.gpu_smoke
def test_pcie_profile_smoke_writes_positive_timings_and_nonnegative_exposed_transfer(
    tmp_path: Path,
) -> None:
    if not torch.cuda.is_available():
        pytest.skip("CUDA is unavailable in this environment")

    output_root = tmp_path / "pcie-smoke"
    result = pcie_profile.profile_pcie_sweep(
        model_id="facebook/opt-125m",
        output_root=output_root,
        block_sizes=(64,),
        warmup_iterations=1,
        timed_iterations=2,
        gpu_id=0,
        config_payload=_OPT_125M_CONFIG,
    )

    rows = _read_rows(result.raw_output_path)
    expected_kv_block_bytes = pcie_profile.calculate_kv_block_bytes(64, 12, 64)

    assert rows
    assert result.row_count == len(rows)
    assert all(row["model_id"] == "facebook/opt-125m" for row in rows)
    assert all(int(row["block_size"]) == 64 for row in rows)
    assert all(int(row["kv_block_bytes"]) == expected_kv_block_bytes for row in rows)
    assert all(float(row["transfer_only_us"]) > 0 for row in rows)
    assert all(float(row["overlap_total_us"]) > 0 for row in rows)
    assert all(float(row["dummy_compute_us"]) > 0 for row in rows)
    assert all(float(row["exposed_transfer_us"]) >= 0 for row in rows)
    assert all(
        float(row["exposed_transfer_us"])
        == pytest.approx(
            pcie_profile.calculate_exposed_transfer_us(
                float(row["overlap_total_us"]),
                float(row["dummy_compute_us"]),
            )
        )
        for row in rows
    )
