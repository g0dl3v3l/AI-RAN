from __future__ import annotations

import pytest

from inference_profile import opt_assets


@pytest.mark.parametrize(
    ("num_hidden_layers", "expected_index"),
    [(12, 5), (24, 11), (32, 15)],
)
def test_select_middle_layer_index_uses_lower_middle_rule(
    num_hidden_layers: int,
    expected_index: int,
) -> None:
    assert opt_assets.select_middle_layer_index(num_hidden_layers) == expected_index


def test_derive_opt_config_keeps_opt_projection_and_head_metadata() -> None:
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

    assert config.model_id == "facebook/opt-350m"
    assert config.hidden_size == 1024
    assert config.word_embed_proj_dim == 512
    assert config.head_dim == 64
    assert config.final_layer_norm_enabled is False
    assert config.kv_bytes_per_token_all_layers == 98_304


def test_derive_opt_config_defaults_word_embed_proj_dim_to_hidden_size() -> None:
    config = opt_assets.derive_opt_config(
        "facebook/opt-125m",
        {
            "hidden_size": 768,
            "num_hidden_layers": 12,
            "num_attention_heads": 12,
            "ffn_dim": 3072,
            "max_position_embeddings": 2048,
            "vocab_size": 50272,
            "do_layer_norm_before": True,
        },
    )

    assert config.word_embed_proj_dim == 768
    assert config.final_layer_norm_enabled is True


def test_resolve_indexed_layer_shards_prefers_model_decoder_prefix() -> None:
    prefix, shard_filenames = opt_assets.resolve_indexed_layer_shards(
        {
            "weight_map": {
                "model.decoder.layers.11.fc1.weight": "layer-a.bin",
                "model.decoder.layers.11.fc1.bias": "layer-a.bin",
                "decoder.layers.11.fc2.weight": "layer-b.bin",
            }
        },
        11,
    )

    assert prefix == "model.decoder.layers.11."
    assert shard_filenames == ("layer-a.bin",)


def test_resolve_indexed_layer_shards_falls_back_to_decoder_prefix_and_deduplicates() -> (
    None
):
    prefix, shard_filenames = opt_assets.resolve_indexed_layer_shards(
        {
            "weight_map": {
                "decoder.layers.15.fc1.weight": "layer-a.bin",
                "decoder.layers.15.fc2.weight": "layer-b.bin",
                "decoder.layers.15.fc2.bias": "layer-b.bin",
            }
        },
        15,
    )

    assert prefix == "decoder.layers.15."
    assert shard_filenames == ("layer-a.bin", "layer-b.bin")
