from __future__ import annotations

import pytest

from inference_profile import opt_assets, prefill_profile

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
    ),
)


@pytest.mark.parametrize(("model_id", "config_payload"), _MODEL_CASES)
@pytest.mark.parametrize("chunk_tokens", [64, 1024])
def test_prefill_parked_activation_uses_fc1_output_for_standard_opt_models(
    model_id: str,
    config_payload: dict[str, int | bool],
    chunk_tokens: int,
) -> None:
    config = opt_assets.derive_opt_config(model_id, config_payload)

    output_bytes_by_op = prefill_profile.build_prefill_output_byte_map(
        config,
        chunk_tokens,
    )

    expected_hidden_bytes = chunk_tokens * config.hidden_size * 2
    expected_fc1_bytes = chunk_tokens * config.ffn_dim * 2

    assert tuple(output_bytes_by_op) == prefill_profile.PREFILL_OP_NAMES
    assert output_bytes_by_op["q_proj"] == expected_hidden_bytes
    assert output_bytes_by_op["k_proj"] == expected_hidden_bytes
    assert output_bytes_by_op["v_proj"] == expected_hidden_bytes
    assert output_bytes_by_op["out_proj"] == expected_hidden_bytes
    assert output_bytes_by_op["fc2"] == expected_hidden_bytes
    assert output_bytes_by_op["fc1"] == expected_fc1_bytes
    assert prefill_profile.largest_prefill_activation_op(config, chunk_tokens) == "fc1"
    assert (
        prefill_profile.estimate_prefill_parked_activation_bytes(config, chunk_tokens)
        == expected_fc1_bytes
    )
    assert output_bytes_by_op["fc1"] > max(
        output_bytes_by_op["q_proj"],
        output_bytes_by_op["out_proj"],
        output_bytes_by_op["fc2"],
    )


def test_prefill_parked_activation_scales_linearly_with_chunk_tokens() -> None:
    config = opt_assets.derive_opt_config(
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
    )

    assert prefill_profile.estimate_prefill_parked_activation_bytes(config, 1024) == (
        prefill_profile.estimate_prefill_parked_activation_bytes(config, 64) * 16
    )
