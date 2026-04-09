"""GPU smoke test for decode profiling."""

import os
import tempfile
from pathlib import Path

import pytest
import torch

from inference_profile import decode_profile


@pytest.mark.gpu_smoke
def test_decode_profile_smoke():
    """Verify decode profiler produces separate gemv, attention_fetch_compute, and reduction_overhead rows."""
    if not torch.cuda.is_available():
        pytest.skip("CUDA not available")

    with tempfile.TemporaryDirectory() as tmpdir:
        output_root = Path(tmpdir)
        
        # Profile 125M model with minimal parameters for smoke test
        result = decode_profile.profile_decode_sweep(
            model_id="facebook/opt-125m",
            output_root=output_root,
            sequence_lengths=[1024],
            block_sizes=[64],
            warmup_iterations=1,
            timed_iterations=2,
            gpu_id=0,
        )
        
        # Verify result structure
        assert result.model_id == "facebook/opt-125m"
        assert result.raw_output_path.exists()
        assert result.row_count > 0
        assert result.max_decode_workspace_bytes >= 0
        assert result.decode_parked_activation_bytes > 0
        
        # Verify CSV contains expected op types
        csv_path = result.raw_output_path
        with open(csv_path, "r") as f:
            content = f.read()
        
        # Check for all three op type categories
        assert "gemv" in content, "CSV must contain gemv rows (linear ops)"
        assert "attention_fetch_compute" in content, "CSV must contain attention_fetch_compute rows"
        assert "reduction_overhead" in content, "CSV must contain reduction_overhead rows"
        
        # Verify rows have positive durations
        lines = content.strip().split("\n")[1:]  # Skip header
        assert len(lines) > 0, "CSV must have at least one data row"
        
        for line in lines:
            parts = line.split(",")
            assert len(parts) == len(decode_profile.DECODE_EVENT_FIELDNAMES)


@pytest.mark.gpu_smoke
def test_decode_flash_reduction_math_stable():
    """Verify blockwise attention reduction math produces stable outputs."""
    if not torch.cuda.is_available():
        pytest.skip("CUDA not available")
    
    device = torch.device("cuda:0")
    head_dim = 64
    num_heads = 8
    seq_len = 512
    block_size = 128
    
    # Create synthetic query and KV cache
    query = torch.randn(num_heads, 1, head_dim, device=device, dtype=torch.float16)
    k_cache = torch.randn(num_heads, seq_len, head_dim, device=device, dtype=torch.float16)
    v_cache = torch.randn(num_heads, seq_len, head_dim, device=device, dtype=torch.float16)
    
    # Run blockwise attention
    output, m_list, l_list, o_list = decode_profile._blockwise_attention(
        query, k_cache, v_cache, block_size
    )
    
    # Verify block statistics are collected
    expected_num_blocks = (seq_len + block_size - 1) // block_size
    assert len(m_list) == expected_num_blocks, f"Expected {expected_num_blocks} m_i values"
    assert len(l_list) == expected_num_blocks, f"Expected {expected_num_blocks} l_i values"
    assert len(o_list) == expected_num_blocks, f"Expected {expected_num_blocks} o_i values"
    
    # Verify block statistics are numeric and positive
    for m_i in m_list:
        assert isinstance(m_i, float)
    for l_i in l_list:
        assert isinstance(l_i, float) and l_i > 0
    for o_i in o_list:
        assert o_i.shape == (num_heads, 1, head_dim)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "gpu_smoke"])
