from __future__ import annotations

import csv
from pathlib import Path

import pytest
import torch

from inference_profile import decode_profile

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
def test_decode_profile_smoke_writes_positive_durations_and_all_task7_op_types(
    tmp_path: Path,
) -> None:
    if not torch.cuda.is_available():
        pytest.skip("CUDA is unavailable in this environment")

    output_root = tmp_path / "decode-smoke"
    result = decode_profile.profile_decode_sweep(
        model_id="facebook/opt-125m",
        output_root=output_root,
        sequence_lengths=(1024,),
        block_sizes=(64,),
        warmup_iterations=1,
        timed_iterations=2,
        gpu_id=0,
        config_payload=_OPT_125M_CONFIG,
    )

    rows = _read_rows(result.raw_output_path)

    assert rows
    assert len(rows) == (len(decode_profile.DECODE_OP_NAMES) + 2) * 2
    assert result.row_count == len(rows)
    assert result.decode_parked_activation_bytes == 768 * 2
    assert {row["op_type"] for row in rows} == {
        decode_profile.DECODE_GEMV_OP_TYPE,
        decode_profile.DECODE_ATTENTION_FETCH_COMPUTE_OP_TYPE,
        decode_profile.DECODE_REDUCTION_OVERHEAD_OP_TYPE,
    }
    assert {
        row["op_name"]
        for row in rows
        if row["op_type"] == decode_profile.DECODE_GEMV_OP_TYPE
    } == set(decode_profile.DECODE_OP_NAMES)
    assert all(float(row["duration_us"]) > 0 for row in rows)
    assert all(int(row["dynamic_workspace_bytes"]) >= 0 for row in rows)
    assert all(int(row["output_bytes"]) >= 0 for row in rows)
    assert all(int(row["baseline_vram_bytes"]) >= 0 for row in rows)
    assert all(
        int(row["peak_vram_bytes"]) >= int(row["baseline_vram_bytes"]) for row in rows
    )
