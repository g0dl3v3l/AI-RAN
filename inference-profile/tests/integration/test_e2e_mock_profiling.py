"""End-to-end test with mock profiling data (CPU-only testing)."""

import tempfile
from pathlib import Path
import pytest
from inference_profile import mock_profiler, profile_reducer, simulator, plots, report


def test_e2e_pipeline_with_mock_profiling():
    """Verify full pipeline stages execute with mock profiling data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_root = Path(tmpdir) / "e2e-run"
        run_root.mkdir(parents=True, exist_ok=True)
        
        # Step 1: Generate mock profiling data
        raw_root = run_root / "raw"
        raw_root.mkdir(parents=True, exist_ok=True)
        
        prefill_rows = mock_profiler.generate_mock_prefill_events(
            model_id="facebook/opt-125m",
            output_path=raw_root / "prefill_events.csv",
            chunk_tokens=[64, 128],
        )
        decode_rows = mock_profiler.generate_mock_decode_events(
            model_id="facebook/opt-125m",
            output_path=raw_root / "decode_events.csv",
            sequence_lengths=[1024, 2048],
            chunk_sizes=[64, 128],
        )
        pcie_rows = mock_profiler.generate_mock_pcie_events(
            model_id="facebook/opt-125m",
            output_path=raw_root / "pcie_events.csv",
            chunk_sizes=[64, 128],
        )
        
        assert prefill_rows > 0, "Prefill events should be created"
        assert decode_rows > 0, "Decode events should be created"
        assert pcie_rows > 0, "PCIe events should be created"
        assert (raw_root / "prefill_events.csv").exists()
        assert (raw_root / "decode_events.csv").exists()
        assert (raw_root / "pcie_events.csv").exists()
        
        # Step 2: Run profile reduction
        reduction_result = profile_reducer.reduce_profile_events(run_root=run_root)
        
        assert reduction_result.prefill_summary_path.exists()
        assert reduction_result.decode_summary_path.exists()
        assert reduction_result.pcie_summary_path.exists()
        assert reduction_result.prefill_row_count > 0
        assert reduction_result.decode_row_count > 0
        assert reduction_result.pcie_row_count > 0
        
        # Step 3: Run simulation
        sim_result = simulator.run_deterministic_simulation(run_root=run_root)
        
        assert sim_result.results_path.exists()
        assert sim_result.timeline_path.exists()
        assert sim_result.row_count >= 0
        
        # Step 4: Generate plots
        plot_paths = plots.generate_profiling_plots(run_root=run_root)
        
        assert len(plot_paths) == 5, "Should generate 5 plots"
        for plot_name, plot_path in plot_paths.items():
            assert plot_path.exists(), f"Plot {plot_name} should exist at {plot_path}"
        
        # Step 5: Generate report
        report_path = report.generate_run_report(run_root=run_root)
        
        assert report_path.exists()
        report_content = report_path.read_text()
        assert "RAN Inference Profiling Report" in report_content
        
        # Verify all intermediate files exist
        assert (run_root / "derived" / "prefill_summary.csv").exists()
        assert (run_root / "derived" / "decode_summary.csv").exists()
        assert (run_root / "derived" / "pcie_summary.csv").exists()
        assert (run_root / "derived" / "ran_inference_profiling_results.csv").exists()
        assert (run_root / "plots").exists()
        assert (run_root / "ran_inference_profiling_report.md").exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
