from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest

from inference_profile import cli, opt_assets, profile_orchestrator


def _write_csv(
    path: Path, fieldnames: list[str], rows: list[dict[str, object]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _build_inspection_result(
    model_id: str, output_root: Path
) -> opt_assets.InspectionResult:
    raw_dir = output_root / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    model_constants = {
        "num_hidden_layers": 12,
        "hidden_size": 768,
        "num_attention_heads": 12,
        "ffn_dim": 3072,
        "layer_index": 5,
        "layer_weight_bytes": 14_175_744,
        "total_weight_bytes_fp16": 250_478_592,
        "vram_ceiling_bytes": 0,
    }
    asset_manifest = {
        "model_id": model_id,
        "asset_source": "synthetic_fallback",
        "asset_source_reason": "test-partial-failure",
    }
    model_constants_path = raw_dir / opt_assets.MODEL_CONSTANTS_FILENAME
    asset_manifest_path = raw_dir / opt_assets.ASSET_MANIFEST_FILENAME
    model_constants_path.write_text(
        json.dumps(model_constants) + "\n", encoding="utf-8"
    )
    asset_manifest_path.write_text(json.dumps(asset_manifest) + "\n", encoding="utf-8")
    return opt_assets.InspectionResult(
        model_id=model_id,
        output_root=output_root,
        model_constants_path=model_constants_path,
        asset_manifest_path=asset_manifest_path,
        model_constants=model_constants,
        asset_manifest=asset_manifest,
        asset_source="synthetic_fallback",
        resolved_shard_filenames=(),
    )


def _point_logs(run_root: Path, point_id: str) -> tuple[Path, Path]:
    stdout_log_path = run_root / "logs" / f"{point_id}.stdout.log"
    stderr_log_path = run_root / "logs" / f"{point_id}.stderr.log"
    stdout_log_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_log_path.write_text(f"{point_id} stdout\n", encoding="utf-8")
    stderr_log_path.write_text(f"{point_id} stderr\n", encoding="utf-8")
    return stdout_log_path, stderr_log_path


def _point_result(
    *,
    run_root: Path,
    point_spec: dict[str, Any],
    rows: list[dict[str, object]],
    public_status: str,
    failure_kind: str | None = None,
    failure_cause: str | None = None,
) -> dict[str, object]:
    point_id = str(point_spec["point_id"])
    raw_output_path = Path(str(point_spec["raw_output_path"]))
    stdout_log_path, stderr_log_path = _point_logs(run_root, point_id)
    _write_csv(raw_output_path, list(point_spec["raw_fieldnames"]), rows)
    return {
        "success": public_status == "success",
        "public_status": public_status,
        "failure_kind": failure_kind,
        "failure_cause": failure_cause,
        "timed_out": False,
        "exit_code": 0 if public_status == "success" else 1,
        "raw_output_path": str(raw_output_path),
        "raw_output_exists": True,
        "raw_row_count": len(rows),
        "stdout_log_path": str(stdout_log_path),
        "stderr_log_path": str(stderr_log_path),
        "result_payload": {},
    }


@pytest.mark.remote_mock
def test_profile_cli_partial_failures_preserves_manifest_visibility_and_reduces_successes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    model_id = "facebook/opt-125m"
    output_root = tmp_path / "profile-out"
    call_sequence: list[str] = []

    def fake_inspect_model(
        *,
        model_id: str,
        cache_root: Path | None = None,
        output_root: Path,
    ) -> opt_assets.InspectionResult:
        del cache_root
        call_sequence.append(f"inspect:{model_id}")
        return _build_inspection_result(model_id, Path(output_root))

    def fake_run_profile_point(
        point_spec: dict[str, Any],
        *,
        run_root: Path,
        timeout_seconds: float,
    ) -> dict[str, object]:
        del timeout_seconds
        assert call_sequence[0] == f"inspect:{model_id}"
        point_id = str(point_spec["point_id"])
        call_sequence.append(f"point:{point_id}")
        run_root = Path(run_root)

        if point_id == "prefill-facebook-opt-125m-chunk-64":
            return _point_result(
                run_root=run_root,
                point_spec=point_spec,
                public_status="success",
                rows=[
                    {
                        "model_id": model_id,
                        "chunk_tokens": 64,
                        "op_name": "fc1",
                        "timed_iteration": 0,
                        "duration_us": 20.0,
                        "baseline_vram_bytes": 100,
                        "peak_vram_bytes": 160,
                        "dynamic_workspace_bytes": 60,
                        "output_bytes": 512,
                    }
                ],
            )
        if point_id == "prefill-facebook-opt-125m-chunk-128":
            return _point_result(
                run_root=run_root,
                point_spec=point_spec,
                public_status="profile_oom",
                failure_kind="cuda_oom",
                failure_cause="synthetic prefill oom",
                rows=[
                    {
                        "model_id": model_id,
                        "chunk_tokens": 128,
                        "op_name": "fc1",
                        "timed_iteration": 0,
                        "duration_us": 999.0,
                        "baseline_vram_bytes": 100,
                        "peak_vram_bytes": 1000,
                        "dynamic_workspace_bytes": 900,
                        "output_bytes": 4096,
                    }
                ],
            )
        if point_id == "decode-facebook-opt-125m-seq-1024-block-64":
            return _point_result(
                run_root=run_root,
                point_spec=point_spec,
                public_status="success",
                rows=[
                    {
                        "model_id": model_id,
                        "sequence_length": 1024,
                        "block_size": 64,
                        "op_type": "gemv",
                        "op_name": "q_proj",
                        "timed_iteration": 0,
                        "duration_us": 5.0,
                        "baseline_vram_bytes": 10,
                        "peak_vram_bytes": 18,
                        "dynamic_workspace_bytes": 8,
                        "output_bytes": 128,
                    },
                    {
                        "model_id": model_id,
                        "sequence_length": 1024,
                        "block_size": 64,
                        "op_type": "attention_fetch_compute",
                        "op_name": "",
                        "timed_iteration": 0,
                        "duration_us": 7.0,
                        "baseline_vram_bytes": 10,
                        "peak_vram_bytes": 42,
                        "dynamic_workspace_bytes": 32,
                        "output_bytes": 256,
                    },
                    {
                        "model_id": model_id,
                        "sequence_length": 1024,
                        "block_size": 64,
                        "op_type": "reduction_overhead",
                        "op_name": "",
                        "timed_iteration": 0,
                        "duration_us": 2.0,
                        "baseline_vram_bytes": 10,
                        "peak_vram_bytes": 22,
                        "dynamic_workspace_bytes": 12,
                        "output_bytes": 64,
                    },
                ],
            )
        if point_id == "decode-facebook-opt-125m-seq-1024-block-128":
            return _point_result(
                run_root=run_root,
                point_spec=point_spec,
                public_status="profile_failed",
                failure_kind="exception",
                failure_cause="synthetic decode failure",
                rows=[
                    {
                        "model_id": model_id,
                        "sequence_length": 1024,
                        "block_size": 128,
                        "op_type": "gemv",
                        "op_name": "q_proj",
                        "timed_iteration": 0,
                        "duration_us": 555.0,
                        "baseline_vram_bytes": 10,
                        "peak_vram_bytes": 510,
                        "dynamic_workspace_bytes": 500,
                        "output_bytes": 4096,
                    }
                ],
            )
        if point_id == "pcie-facebook-opt-125m-block-64":
            return _point_result(
                run_root=run_root,
                point_spec=point_spec,
                public_status="success",
                rows=[
                    {
                        "model_id": model_id,
                        "block_size": 64,
                        "kv_block_bytes": 2048,
                        "transfer_only_us": 10.0,
                        "overlap_total_us": 8.0,
                        "dummy_compute_us": 5.0,
                        "exposed_transfer_us": 3.0,
                        "timed_iteration": 0,
                    }
                ],
            )
        if point_id == "pcie-facebook-opt-125m-block-128":
            return _point_result(
                run_root=run_root,
                point_spec=point_spec,
                public_status="profile_failed",
                failure_kind="exception",
                failure_cause="synthetic pcie failure",
                rows=[
                    {
                        "model_id": model_id,
                        "block_size": 128,
                        "kv_block_bytes": 4096,
                        "transfer_only_us": 100.0,
                        "overlap_total_us": 90.0,
                        "dummy_compute_us": 5.0,
                        "exposed_transfer_us": 85.0,
                        "timed_iteration": 0,
                    }
                ],
            )
        raise AssertionError(f"Unexpected point_id: {point_id}")

    monkeypatch.setattr(opt_assets, "inspect_model", fake_inspect_model)
    monkeypatch.setattr(
        profile_orchestrator.worker_profile_point,
        "run_profile_point",
        fake_run_profile_point,
    )

    with pytest.raises(SystemExit) as excinfo:
        cli.main(
            [
                "profile",
                "--models",
                model_id,
                "--chunk-sizes",
                "64",
                "128",
                "--sequence-lengths",
                "1024",
                "--warmup",
                "1",
                "--iterations",
                "1",
                "--gpu-id",
                "0",
                "--output-root",
                str(output_root),
            ]
        )
    assert excinfo.value.code == 2
    assert "Profiling stage failed; see" in capsys.readouterr().err

    manifest = json.loads(
        (output_root / "run_manifest.json").read_text(encoding="utf-8")
    )
    profile_stage = manifest["stages"]["profile"]
    family_details = profile_stage["details"]["profiler_families"]

    assert profile_stage["latest_status"] == "profile_failed"
    assert family_details["prefill"] == {
        "requested_points": 2,
        "completed_points": 2,
        "successes": 1,
        "ooms": 1,
        "failures": 0,
        "raw_rows": 2,
    }
    assert family_details["decode"] == {
        "requested_points": 2,
        "completed_points": 2,
        "successes": 1,
        "ooms": 0,
        "failures": 1,
        "raw_rows": 4,
    }
    assert family_details["pcie"] == {
        "requested_points": 2,
        "completed_points": 2,
        "successes": 1,
        "ooms": 0,
        "failures": 1,
        "raw_rows": 2,
    }
    assert profile_stage["details"]["actual_summary_rows"] == {
        "model_constants": 1,
        "prefill": 1,
        "decode": 1,
        "pcie": 1,
    }
    assert profile_stage["details"]["expected_summary_rows"] == {
        "model_constants": 1,
        "prefill": 2,
        "decode": 2,
        "pcie": 2,
    }
    assert profile_stage["details"]["summary_rows_complete"] is False

    prefill_raw_rows = _read_csv_rows(output_root / "raw" / "prefill_events.csv")
    decode_raw_rows = _read_csv_rows(output_root / "raw" / "decode_events.csv")
    pcie_raw_rows = _read_csv_rows(output_root / "raw" / "pcie_events.csv")
    prefill_summary_rows = _read_csv_rows(
        output_root / "derived" / "prefill_summary.csv"
    )
    decode_summary_rows = _read_csv_rows(output_root / "derived" / "decode_summary.csv")
    pcie_summary_rows = _read_csv_rows(output_root / "derived" / "pcie_summary.csv")

    assert {row["public_status"] for row in prefill_raw_rows} == {
        "success",
        "profile_oom",
    }
    assert {row["public_status"] for row in decode_raw_rows} == {
        "success",
        "profile_failed",
    }
    assert {row["public_status"] for row in pcie_raw_rows} == {
        "success",
        "profile_failed",
    }

    assert prefill_summary_rows == [
        {
            "model_id": model_id,
            "chunk_tokens": "64",
            "prefill_max_gemm_us": "20.0",
            "prefill_workspace_bytes": "60",
            "prefill_parked_activation_bytes": "512",
        }
    ]
    assert decode_summary_rows == [
        {
            "model_id": model_id,
            "sequence_length": "1024",
            "block_size": "64",
            "decode_max_gemv_us": "5.0",
            "attention_fetch_compute_us": "7.0",
            "reduction_overhead_us": "2.0",
            "decode_workspace_bytes": "32",
            "decode_parked_activation_bytes": "64",
        }
    ]
    assert pcie_summary_rows == [
        {
            "model_id": model_id,
            "block_size": "64",
            "kv_block_bytes": "2048",
            "transfer_only_us": "10.0",
            "overlap_total_us": "8.0",
            "dummy_compute_us": "5.0",
            "exposed_transfer_us": "3.0",
            "effective_gbps": "0.2048",
        }
    ]
