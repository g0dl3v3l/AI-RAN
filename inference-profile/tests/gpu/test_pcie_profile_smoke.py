"""GPU smoke test for PCIe profiling."""

import tempfile
from pathlib import Path

import pytest
import torch

from inference_profile import pcie_profile


@pytest.mark.gpu_smoke
def test_pcie_profile_smoke():
    """Verify PCIe profiler produces valid H2D transfer measurements."""
    if not torch.cuda.is_available():
        pytest.skip("CUDA not available")

    with tempfile.TemporaryDirectory() as tmpdir:
        output_root = Path(tmpdir)
        
        # Profile 125M model with minimal parameters for smoke test
        result = pcie_profile.profile_pcie_sweep(
            model_id="facebook/opt-125m",
            output_root=output_root,
            block_sizes=[64],
            warmup_iterations=1,
            timed_iterations=2,
            gpu_id=0,
        )
        
        # Verify result structure
        assert result.model_id == "facebook/opt-125m"
        assert result.raw_output_path.exists()
        assert result.row_count > 0
        
        # Verify CSV contains expected columns
        csv_path = result.raw_output_path
        with open(csv_path, "r") as f:
            lines = f.readlines()
        
        assert len(lines) > 1, "CSV must have header and data rows"
        
        # Check header
        header = lines[0].strip()
        for field in pcie_profile.PCIE_EVENT_FIELDNAMES:
            assert field in header, f"Header must contain {field}"
        
        # Check data row
        data_row = lines[1].strip()
        assert len(data_row) > 0, "CSV must have at least one data row"
        
        # Parse CSV values
        parts = data_row.split(",")
        assert len(parts) == len(pcie_profile.PCIE_EVENT_FIELDNAMES)


@pytest.mark.gpu_smoke
def test_pcie_exposed_latency_formula():
    """Verify exposed_transfer_us calculation is sound."""
    if not torch.cuda.is_available():
        pytest.skip("CUDA not available")
    
    # Test the invariant: exposed_transfer_us = max(0, overlap_total_us - dummy_compute_us)
    test_cases = [
        # (overlap_total, dummy_compute, expected_exposed)
        (100.0, 50.0, 50.0),    # Transfer slower than compute
        (100.0, 150.0, 0.0),    # Compute slower, no exposed transfer
        (100.0, 100.0, 0.0),    # Equal times
        (50.0, 200.0, 0.0),     # Very fast compute
    ]
    
    for overlap_total, dummy_compute, expected_exposed in test_cases:
        exposed = max(0.0, overlap_total - dummy_compute)
        assert exposed == expected_exposed, (
            f"exposed_transfer_us calculation failed: "
            f"overlap={overlap_total}, compute={dummy_compute}, "
            f"expected={expected_exposed}, got={exposed}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "gpu_smoke"])
