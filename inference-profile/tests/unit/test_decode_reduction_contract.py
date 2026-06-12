from __future__ import annotations

import math

import pytest
import torch

from inference_profile import decode_profile


def _make_cpu_fixture() -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    query = torch.tensor(
        [
            [[0.10, -0.20, 0.30, 0.40]],
            [[-0.15, 0.25, 0.05, -0.35]],
        ],
        dtype=torch.float64,
    )
    base = torch.arange(1, 1 + (2 * 5 * 4), dtype=torch.float64).reshape(2, 5, 4)
    k_cache = base / 25.0
    v_cache = base.flip(-1) / 17.0
    return query, k_cache, v_cache


def _direct_attention_oracle(
    query: torch.Tensor,
    k_cache: torch.Tensor,
    v_cache: torch.Tensor,
) -> torch.Tensor:
    scores = torch.matmul(query, k_cache.transpose(-2, -1)) * (
        1.0 / math.sqrt(int(query.shape[-1]))
    )
    weights = torch.softmax(scores, dim=-1)
    context = torch.matmul(weights, v_cache)
    return context.permute(1, 0, 2).reshape(1, 1, -1)


@pytest.mark.parametrize("block_size", [2, 3])
def test_blockwise_reduction_matches_direct_attention_oracle_on_cpu_fixture(
    block_size: int,
) -> None:
    query, k_cache, v_cache = _make_cpu_fixture()

    block_stats = decode_profile._collect_blockwise_attention_stats(
        query,
        k_cache,
        v_cache,
        block_size,
    )
    reduced_output = decode_profile._reduce_blockwise_attention_stats(block_stats)
    oracle_output = _direct_attention_oracle(query, k_cache, v_cache)

    assert len(block_stats) == decode_profile._calculate_num_blocks(
        k_cache.shape[1],
        block_size,
    )
    assert all(
        block.max_scores.shape == (query.shape[0], 1, 1) for block in block_stats
    )
    assert all(block.exp_sums.shape == (query.shape[0], 1, 1) for block in block_stats)
    assert all(block.weighted_values.shape == query.shape for block in block_stats)
    assert reduced_output.shape == (1, 1, query.shape[0] * query.shape[-1])
    assert torch.allclose(reduced_output, oracle_output, atol=1e-12, rtol=1e-12)


def test_block_stats_output_bytes_counts_all_saved_reduction_state() -> None:
    query, k_cache, v_cache = _make_cpu_fixture()
    block_stats = decode_profile._collect_blockwise_attention_stats(
        query,
        k_cache,
        v_cache,
        2,
    )

    expected_bytes = sum(
        (block.max_scores.numel() * block.max_scores.element_size())
        + (block.exp_sums.numel() * block.exp_sums.element_size())
        + (block.weighted_values.numel() * block.weighted_values.element_size())
        for block in block_stats
    )

    assert decode_profile._block_stats_output_bytes(block_stats) == expected_bytes


def test_full_attention_path_matches_direct_attention_oracle() -> None:
    query, k_cache, v_cache = _make_cpu_fixture()

    scores, probabilities, weighted_values = decode_profile._collect_full_attention_tensors(
        query,
        k_cache,
        v_cache,
    )
    reduced = decode_profile._reduce_full_attention(weighted_values)
    oracle_output = _direct_attention_oracle(query, k_cache, v_cache)

    assert scores.shape == (query.shape[0], 1, k_cache.shape[1])
    assert probabilities.shape == (query.shape[0], 1, k_cache.shape[1])
    assert weighted_values.shape == query.shape
    assert reduced.shape == oracle_output.shape
    assert torch.allclose(reduced, oracle_output, atol=1e-12, rtol=1e-12)

    expected_fetch_bytes = int(
        (scores.numel() * scores.element_size())
        + (probabilities.numel() * probabilities.element_size())
        + (weighted_values.numel() * weighted_values.element_size())
    )
    assert (
        decode_profile._full_attention_fetch_output_bytes(
            scores,
            probabilities,
            weighted_values,
        )
        == expected_fetch_bytes
    )
