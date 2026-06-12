from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from inference_profile import experiments, telemetry


def test_make_baseline_telemetry_row_uses_revised_tier_and_columns() -> None:
    row = telemetry.make_baseline_telemetry_row(
        ts="2026-04-13T23:00:00Z",
        gpu_id=0,
        point_id="prefill-facebook-opt-125m-chunk-64-sm-8",
        family="prefill",
        model_id="facebook/opt-125m",
        chunk_tokens=64,
        sm_ai_partition=8,
        public_status="success",
        pt_step_ms=1.25,
        pt_mem_alloc_mb=32.0,
        pt_mem_reserved_mb=64.0,
        pt_workspace_mb=16.0,
        nvml_available=False,
        sampling_error="nvml unavailable",
    )

    assert tuple(row.keys()) == telemetry.BASELINE_TELEMETRY_COLUMNS
    assert row["telemetry_tier"] == experiments.RAN_DGXSPARK_V1_TELEMETRY_TIER
    assert row["telemetry_provider"] == "nvidia-smi"
    assert row["family"] == "prefill"
    assert row["chunk_tokens"] == 64
    assert row["sm_ai_partition"] == 8
    assert row["gpu_id"] == 0
    assert row["pt_step_ms"] == 1.25
    assert row["pt_workspace_mb"] == 16.0
    assert row["nvml_available"] is False
    assert row["telemetry_status"] == "partial"
    assert row["acu_pct"] is None
    assert row["gbu_pct"] is None
    assert row["smu_pct"] is None
    assert row["microscopic_telemetry_status"] == "unavailable"
    assert row["sampling_error"] == "nvml unavailable"


def test_append_telemetry_row_writes_jsonl(tmp_path: Path) -> None:
    row = telemetry.make_baseline_telemetry_row(
        ts="2026-04-13T23:00:00Z",
        gpu_id=1,
        pt_step_ms=2.5,
        pt_mem_alloc_mb=12.0,
        pt_mem_reserved_mb=24.0,
        nvml_available=True,
    )

    path = telemetry.append_telemetry_row(tmp_path / "run-root", row)

    written = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
    ]
    assert path == tmp_path / "run-root" / "telemetry" / "telemetry.jsonl"
    assert written == [row]


def test_sample_nvml_baseline_returns_unavailable_payload_on_error(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        raise OSError("nvidia-smi missing")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = telemetry.sample_nvml_baseline(gpu_id=0)

    assert result["nvml_available"] is False
    assert result["gpu_util"] is None
    assert result["sampling_error"] == "nvidia-smi missing"


def test_sample_nvml_baseline_parses_csv_payload(monkeypatch) -> None:
    completed = subprocess.CompletedProcess(
        args=["nvidia-smi"],
        returncode=0,
        stdout="12, 345, 1500, 9000, 42.5\n",
        stderr="",
    )
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: completed)

    result = telemetry.sample_nvml_baseline(gpu_id=0)

    assert result == {
        "nvml_available": True,
        "gpu_util": 12.0,
        "gpu_mem_used_mb": 345.0,
        "sm_clock_mhz": 1500.0,
        "mem_clock_mhz": 9000.0,
        "power_w": 42.5,
        "sampling_error": None,
    }


def test_sample_point_telemetry_falls_back_cleanly_when_external_profiler_is_unavailable(
    monkeypatch,
) -> None:
    completed = subprocess.CompletedProcess(
        args=["nvidia-smi"],
        returncode=0,
        stdout="12, 345, 1500, 9000, 42.5\n",
        stderr="",
    )
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: completed)

    row = telemetry.sample_point_telemetry(
        ts="2026-04-13T23:00:00Z",
        gpu_id=0,
        point_id="decode-facebook-opt-125m-seq-1024-block-64-mode-pcie_async-sm-8",
        family="decode",
        model_id="facebook/opt-125m",
        sequence_length=1024,
        block_size=64,
        sm_ai_partition=8,
        decode_mode="pcie_async",
        public_status="success",
        pt_step_ms=2.5,
        pt_mem_alloc_mb=24.0,
        pt_mem_reserved_mb=32.0,
        pt_workspace_mb=8.0,
        preferred_tier=telemetry.EXTERNAL_PROFILER_TELEMETRY_TIER,
    )

    assert row["telemetry_tier"] == telemetry.EXTERNAL_PROFILER_TELEMETRY_TIER
    assert row["telemetry_status"] == "ok"
    assert row["decode_mode"] == "pcie_async"
    assert row["gpu_util"] == 12.0
    assert row["acu_pct"] == pytest.approx(56.5)
    assert row["gbu_pct"] == pytest.approx(71.34)
    assert row["smu_pct"] == pytest.approx(56.05)
    assert row["microscopic_telemetry_status"] == "estimated"
    assert row["microscopic_error"] == "external profiler unavailable"


def test_sample_point_telemetry_keeps_microscopic_counters_estimated_when_nvml_is_unavailable(
    monkeypatch,
) -> None:
    def fake_run(*args, **kwargs):
        raise OSError("nvidia-smi missing")

    monkeypatch.setattr(subprocess, "run", fake_run)

    row = telemetry.sample_point_telemetry(
        ts="2026-04-13T23:00:00Z",
        gpu_id=0,
        point_id="prefill-facebook-opt-125m-chunk-64-sm-8",
        family="prefill",
        model_id="facebook/opt-125m",
        chunk_tokens=64,
        sm_ai_partition=8,
        public_status="success",
        pt_step_ms=1.5,
        pt_mem_alloc_mb=16.0,
        pt_mem_reserved_mb=32.0,
        pt_workspace_mb=8.0,
    )

    assert row["gpu_util"] is None
    assert row["acu_pct"] == pytest.approx(67.94)
    assert row["gbu_pct"] == pytest.approx(71.875)
    assert row["smu_pct"] == pytest.approx(60.075)
    assert row["microscopic_telemetry_status"] == "estimated"
