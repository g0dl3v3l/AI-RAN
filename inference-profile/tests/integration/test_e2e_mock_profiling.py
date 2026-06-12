"""End-to-end test with mock profiling data (CPU-only testing)."""

import csv
import json
import tempfile
from pathlib import Path

import pytest

from inference_profile import (
    mock_profiler,
    plots,
    profile_reducer,
    report,
    simulator,
    trace_contract,
)
from inference_profile.paths import bundle_paths_from_run_root

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = PROJECT_ROOT / "tests" / "fixtures"


def _write_mock_e2e_ldpc_trace(trace_path: Path) -> None:
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    with trace_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["time_ms", "sm_utilization"],
        )
        writer.writeheader()
        writer.writerows(
            [
                {"time_ms": 0.0, "sm_utilization": 100.0},
                {"time_ms": 5.0, "sm_utilization": 0.0},
                {"time_ms": 1005.0, "sm_utilization": 100.0},
            ]
        )


def test_e2e_pipeline_with_mock_profiling():
    """Verify full pipeline stages execute with mock profiling data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_root = Path(tmpdir) / "e2e-run"
        run_root.mkdir(parents=True, exist_ok=True)
        bundle_paths = bundle_paths_from_run_root(run_root)
        bundle_paths.run_manifest_path.write_text(
            json.dumps({"run_id": run_root.name}) + "\n",
            encoding="utf-8",
        )
        bundle_paths.environment_path.write_text(
            json.dumps(
                {
                    "stage": "mock-e2e",
                    "models": ["facebook/opt-125m"],
                    "cuda_available": False,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        bundle_paths.logs_dir.mkdir(parents=True, exist_ok=True)
        (bundle_paths.logs_dir / "profile-stage.log").write_text(
            "mock profile stage complete\n",
            encoding="utf-8",
        )
        ldpc_trace_path = Path(tmpdir) / "ldpc_trace_mock_e2e.csv"
        _write_mock_e2e_ldpc_trace(ldpc_trace_path)

        trace_result = trace_contract.validate_trace_contract(
            ldpc_trace=ldpc_trace_path,
            ran_ctrl_trace=FIXTURE_ROOT / "ran_ctrl_trace_valid.csv",
            output_root=run_root,
        )
        assert trace_result.success is True

        raw_root = run_root / "raw"
        raw_root.mkdir(parents=True, exist_ok=True)
        (raw_root / "model_constants.json").write_text(
            json.dumps(
                {
                    "model_id": "facebook/opt-125m",
                    "num_hidden_layers": 12,
                    "hidden_size": 768,
                    "total_weight_bytes_fp16": 250_478_592,
                    "vram_ceiling_bytes": 14_400_000_000,
                }
            ),
            encoding="utf-8",
        )

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

        reduction_result = profile_reducer.reduce_profile_events(run_root=run_root)

        assert reduction_result.prefill_summary_path.exists()
        assert reduction_result.decode_summary_path.exists()
        assert reduction_result.pcie_summary_path.exists()
        assert reduction_result.prefill_row_count > 0
        assert reduction_result.decode_row_count > 0
        assert reduction_result.pcie_row_count > 0

        sim_result = simulator.run_deterministic_simulation(run_root=run_root)

        assert sim_result.results_path.exists()
        assert sim_result.timeline_path.exists()
        assert sim_result.row_count >= 0
        with sim_result.results_path.open("r", encoding="utf-8", newline="") as handle:
            result_rows = list(csv.DictReader(handle))
        assert any(row["status"] == "success" for row in result_rows)

        with (run_root / "derived" / "model_constants.csv").open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "model_id",
                    "num_hidden_layers",
                    "hidden_size",
                    "vram_ceiling_bytes",
                    "total_weight_bytes_fp16",
                    "kv_bytes_per_token_all_layers",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "model_id": "facebook/opt-125m",
                    "num_hidden_layers": 12,
                    "hidden_size": 768,
                    "vram_ceiling_bytes": 14_400_000_000,
                    "total_weight_bytes_fp16": 250_478_592,
                    "kv_bytes_per_token_all_layers": 36_864,
                }
            )

        plot_paths = plots.generate_profiling_plots(run_root=run_root)

        assert len(plot_paths) == 6, "Should generate 6 plots"
        for plot_name, plot_path in plot_paths.items():
            assert plot_path.exists(), f"Plot {plot_name} should exist at {plot_path}"

        report_path = report.generate_run_report(run_root=run_root)

        assert report_path.exists()
        report_content = report_path.read_text()
        assert "RAN Inference Profiling Report" in report_content

        assert (run_root / "derived" / "prefill_summary.csv").exists()
        assert (run_root / "derived" / "decode_summary.csv").exists()
        assert (run_root / "derived" / "pcie_summary.csv").exists()
        assert (run_root / "derived" / simulator.SIMULATION_INPUTS_FILENAME).exists()
        assert (run_root / "derived" / "ran_inference_profiling_results.csv").exists()
        assert (run_root / "plots").exists()
        assert (run_root / "ran_inference_profiling_report.md").exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
