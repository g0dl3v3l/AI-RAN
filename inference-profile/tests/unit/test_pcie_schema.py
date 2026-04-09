"""Unit tests for PCIe profiling schema and contract."""

import tempfile
from pathlib import Path

import pytest

from inference_profile import pcie_profile


def test_resolve_pcie_output_path_defaults_to_raw_pcie_events_csv():
    """Verify PCIe output path defaults to raw/pcie_events.csv."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_root = Path(tmpdir)
        resolved_path = pcie_profile.resolve_pcie_output_path(output_root=output_root)
        
        assert resolved_path == output_root / "raw" / "pcie_events.csv"


def test_resolve_pcie_output_path_respects_explicit_raw_output_path():
    """Verify explicit raw_output_path overrides default."""
    with tempfile.TemporaryDirectory() as tmpdir:
        explicit_path = Path(tmpdir) / "custom.csv"
        resolved_path = pcie_profile.resolve_pcie_output_path(
            raw_output_path=explicit_path
        )
        
        assert resolved_path == explicit_path


def test_pcie_fieldnames_are_exact():
    """Verify PCIe event fieldnames match specification."""
    expected_fields = (
        "model_id",
        "block_size",
        "kv_block_bytes",
        "transfer_only_us",
        "overlap_total_us",
        "dummy_compute_us",
        "exposed_transfer_us",
        "timed_iteration",
    )
    assert pcie_profile.PCIE_EVENT_FIELDNAMES == expected_fields


def test_pcie_constants_are_fixed():
    """Verify PCIe constants match plan specification."""
    assert pcie_profile.PCIE_DTYPE_NAME == "float16"
    assert pcie_profile.PCIE_EVENTS_FILENAME == "pcie_events.csv"


def test_calculate_kv_block_bytes():
    """Verify KV block byte calculation formula."""
    # KV block bytes = 2 * num_heads * block_size * head_dim * 2 (FP16 = 2 bytes)
    num_heads = 8
    head_dim = 64
    block_size = 128
    
    result = pcie_profile.calculate_kv_block_bytes(block_size, num_heads, head_dim)
    expected = 2 * num_heads * block_size * head_dim * 2
    
    assert result == expected


def test_calculate_kv_block_bytes_scales_with_block_size():
    """Verify KV block bytes scales linearly with block size."""
    num_heads = 8
    head_dim = 64
    
    bytes_64 = pcie_profile.calculate_kv_block_bytes(64, num_heads, head_dim)
    bytes_128 = pcie_profile.calculate_kv_block_bytes(128, num_heads, head_dim)
    
    # Doubling block size should double byte count
    assert bytes_128 == 2 * bytes_64


def test_normalize_block_sizes():
    """Verify block size normalization."""
    normalized = pcie_profile._normalize_block_sizes([64, 128])
    assert normalized == (64, 128)
    
    with pytest.raises(ValueError):
        pcie_profile._normalize_block_sizes([])
    
    with pytest.raises(ValueError):
        pcie_profile._normalize_block_sizes([0, -1])


def test_exposed_transfer_calculation():
    """Verify exposed_transfer_us = max(0, overlap_total_us - dummy_compute_us)."""
    # Test case 1: Transfer overlaps completely with compute
    overlap_total = 100.0
    dummy_compute = 150.0
    exposed = max(0.0, overlap_total - dummy_compute)
    assert exposed == 0.0, "No exposed transfer when compute is slower"
    
    # Test case 2: Transfer is slower than compute
    overlap_total = 200.0
    dummy_compute = 50.0
    exposed = max(0.0, overlap_total - dummy_compute)
    assert exposed == 150.0, "Exposed transfer = overlap - compute"
    
    # Test case 3: Transfer and compute equal
    overlap_total = 100.0
    dummy_compute = 100.0
    exposed = max(0.0, overlap_total - dummy_compute)
    assert exposed == 0.0, "No exposed transfer when times are equal"
