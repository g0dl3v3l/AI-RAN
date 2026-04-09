from __future__ import annotations

import pytest

from inference_profile import opt_assets


_MODEL_CASES = (
    (
        "facebook/opt-125m",
        {
            "hidden_size": 768,
            "num_hidden_layers": 12,
            "num_attention_heads": 12,
            "ffn_dim": 3072,
            "max_position_embeddings": 2048,
            "vocab_size": 50272,
            "word_embed_proj_dim": 768,
            "do_layer_norm_before": True,
        },
        14_175_744,
        250_478_592,
    ),
    (
        "facebook/opt-350m",
        {
            "hidden_size": 1024,
            "num_hidden_layers": 24,
            "num_attention_heads": 16,
            "ffn_dim": 4096,
            "max_position_embeddings": 2048,
            "vocab_size": 50272,
            "word_embed_proj_dim": 512,
            "do_layer_norm_before": False,
        },
        25_192_448,
        662_392_832,
    ),
    (
        "facebook/opt-1.3b",
        {
            "hidden_size": 2048,
            "num_hidden_layers": 24,
            "num_attention_heads": 32,
            "ffn_dim": 8192,
            "max_position_embeddings": 2048,
            "vocab_size": 50272,
            "word_embed_proj_dim": 2048,
            "do_layer_norm_before": True,
        },
        100_716_544,
        2_631_516_160,
    ),
    (
        "facebook/opt-2.7b",
        {
            "hidden_size": 2560,
            "num_hidden_layers": 32,
            "num_attention_heads": 32,
            "ffn_dim": 10240,
            "max_position_embeddings": 2048,
            "vocab_size": 50272,
            "word_embed_proj_dim": 2560,
            "do_layer_norm_before": True,
            "_remove_final_layer_norm": False,
        },
        157_352_960,
        5_303_193_600,
    ),
    (
        "facebook/opt-6.7b",
        {
            "hidden_size": 4096,
            "num_hidden_layers": 32,
            "num_attention_heads": 32,
            "ffn_dim": 16384,
            "max_position_embeddings": 2048,
            "vocab_size": 50272,
            "word_embed_proj_dim": 4096,
            "do_layer_norm_before": True,
            "_remove_final_layer_norm": False,
        },
        402_759_680,
        13_316_947_968,
    ),
)


@pytest.mark.parametrize(
    (
        "model_id",
        "config_payload",
        "expected_layer_weight_bytes",
        "expected_total_weight_bytes",
    ),
    _MODEL_CASES,
)
def test_weight_byte_estimates_are_deterministic_for_fixed_opt_models(
    model_id: str,
    config_payload: dict[str, int | bool],
    expected_layer_weight_bytes: int,
    expected_total_weight_bytes: int,
) -> None:
    config = opt_assets.derive_opt_config(model_id, config_payload)

    assert (
        opt_assets.estimate_decoder_layer_weight_bytes_fp16(config)
        == expected_layer_weight_bytes
    )
    assert (
        opt_assets.estimate_total_weight_bytes_fp16(config)
        == expected_total_weight_bytes
    )


def test_vram_ceiling_uses_sixty_percent_of_total_gpu_memory() -> None:
    assert opt_assets.estimate_vram_ceiling_bytes(32_000_000_000) == 19_200_000_000


def test_vram_ceiling_without_detectable_gpu_memory_is_zero() -> None:
    assert opt_assets.estimate_vram_ceiling_bytes(None) == 0
    assert opt_assets.estimate_vram_ceiling_bytes(0) == 0
    assert opt_assets.estimate_vram_ceiling_bytes(-1) == 0


def test_synthetic_layer_metadata_matches_estimated_layer_weight_bytes() -> None:
    config = opt_assets.derive_opt_config(
        "facebook/opt-350m",
        {
            "hidden_size": 1024,
            "num_hidden_layers": 24,
            "num_attention_heads": 16,
            "ffn_dim": 4096,
            "max_position_embeddings": 2048,
            "vocab_size": 50272,
            "word_embed_proj_dim": 512,
            "do_layer_norm_before": False,
        },
    )

    metadata = opt_assets.build_synthetic_layer_metadata(
        config,
        layer_index=11,
        reason="monolithic_only",
    )

    assert metadata["dtype"] == "float16"
    assert metadata["seed"] == 53
    assert metadata["reason"] == "monolithic_only"
    assert metadata["parameters"][0] == {
        "name": "self_attn.q_proj.weight",
        "shape": [1024, 1024],
        "numel": 1_048_576,
        "bytes_fp16": 2_097_152,
        "seed": 53,
    }
    assert (
        sum(item["bytes_fp16"] for item in metadata["parameters"])
        == config.layer_weight_bytes
    )
