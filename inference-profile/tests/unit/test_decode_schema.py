"""Unit tests for decode profiling schema and contract."""

import tempfile
from pathlib import Path

import pytest

from inference_profile import decode_profile


def test_resolve_decode_output_path_defaults_to_raw_decode_events_csv():
    """Verify decode output path defaults to raw/decode_events.csv."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_root = Path(tmpdir)
        resolved_path = decode_profile.resolve_decode_output_path(output_root=output_root)
        
        assert resolved_path == output_root / "raw" / "decode_events.csv"


def test_resolve_decode_output_path_respects_explicit_raw_output_path():
    """Verify explicit raw_output_path overrides default."""
    with tempfile.TemporaryDirectory() as tmpdir:
        explicit_path = Path(tmpdir) / "custom.csv"
        resolved_path = decode_profile.resolve_decode_output_path(
            raw_output_path=explicit_path
        )
        
        assert resolved_path == explicit_path


def test_decode_fieldnames_are_exact():
    """Verify decode event fieldnames match specification."""
    expected_fields = (
        "model_id",
        "sequence_length",
        "block_size",
        "op_type",
        "op_name",
        "timed_iteration",
        "duration_us",
        "baseline_vram_bytes",
        "peak_vram_bytes",
        "dynamic_workspace_bytes",
        "output_bytes",
    )
    assert decode_profile.DECODE_EVENT_FIELDNAMES == expected_fields


def test_decode_constants_are_fixed():
    """Verify decode constants match plan specification."""
    assert decode_profile.DECODE_BATCH_SIZE == 1
    assert decode_profile.DECODE_DTYPE_NAME == "float16"
    assert decode_profile.DECODE_OP_NAMES == (
        "q_proj", "k_proj", "v_proj", "out_proj", "fc1", "fc2"
    )
    assert decode_profile.DECODE_BLOCK_SIZES == (64, 128, 256, 512, 1024)


def test_calculate_num_blocks():
    """Verify block calculation logic."""
    assert decode_profile._calculate_num_blocks(1024, 64) == 16
    assert decode_profile._calculate_num_blocks(1024, 128) == 8
    assert decode_profile._calculate_num_blocks(2048, 512) == 4
    # Edge case: sequence length not divisible by block size
    assert decode_profile._calculate_num_blocks(1000, 64) == 16  # ceil(1000/64) = 16


def test_normalize_sequence_lengths():
    """Verify sequence length normalization."""
    normalized = decode_profile._normalize_sequence_lengths([1024, 2048])
    assert normalized == (1024, 2048)
    
    with pytest.raises(ValueError):
        decode_profile._normalize_sequence_lengths([])
    
    with pytest.raises(ValueError):
        decode_profile._normalize_sequence_lengths([0, -1])


def test_normalize_block_sizes():
    """Verify block size normalization."""
    normalized = decode_profile._normalize_block_sizes([64, 128])
    assert normalized == (64, 128)
    
    with pytest.raises(ValueError):
        decode_profile._normalize_block_sizes([])
    
    with pytest.raises(ValueError):
        decode_profile._normalize_block_sizes([0, -1])


def test_estimate_decode_parked_activation_bytes():
    """Verify decode parked activation matches [1,1,hidden_size] shape."""
    # For a mock config with hidden_size=768
    class MockConfig:
        hidden_size = 768
    
    config = MockConfig()
    parked_bytes = decode_profile.estimate_decode_parked_activation_bytes(config)
    
    # [1, 1, 768] in FP16 = 768 * 2 bytes
    expected = 1 * 1 * 768 * 2
    assert parked_bytes == expected
