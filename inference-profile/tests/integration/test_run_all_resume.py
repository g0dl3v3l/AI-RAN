from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from inference_profile import cli, experiments, manifests, paths, run_orchestrator


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _seed_legacy_failed_profile_manifest(run_root: Path) -> None:
    run_root.mkdir(parents=True, exist_ok=True)
    _write_json(
        run_root / paths.RUN_MANIFEST_FILENAME,
        {
            "run_id": run_root.name,
            "status": "failed",
            "stage_status": {
                "bootstrap-env": "success",
                "validate-traces": "success",
                "profile": "failed",
                "simulate": "pending",
                "report": "pending",
                "verify-bundle": "pending",
            },
        },
    )


def _patch_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    stage_calls: list[str],
    *,
    validate_success: bool = True,
    verify_status: str = "success",
) -> None:
    import inference_profile.bootstrap as bootstrap_module
    import inference_profile.plots as plots_module
    import inference_profile.profile_orchestrator as profile_module
    import inference_profile.report as report_module
    import inference_profile.simulator as simulator_module
    import inference_profile.trace_contract as trace_module
    import inference_profile.verify_bundle as verify_module

    def fake_bootstrap_environment(
        *,
        output_root,
        cache_root=None,
        gpu_id=0,
        experiment_type=None,
        manifest_metadata=None,
    ):
        del cache_root, gpu_id, experiment_type, manifest_metadata
        stage_calls.append("bootstrap-env")
        bundle_paths = paths.bundle_paths_from_run_root(Path(output_root))
        for directory in bundle_paths.directories:
            directory.mkdir(parents=True, exist_ok=True)
        if not bundle_paths.run_manifest_path.exists():
            manifests.initialize_run_manifest(bundle_paths)
        bundle_paths.environment_path.write_text(
            '{"stage":"bootstrap-env"}\n',
            encoding="utf-8",
        )
        manifests.update_stage_status(
            bundle_paths.run_manifest_path,
            stage="bootstrap-env",
            status="success",
            details={"stub": True},
        )
        return SimpleNamespace(output_root=Path(output_root))

    def fake_validate_trace_contract(ldpc_trace, ran_ctrl_trace, output_root):
        del ldpc_trace, ran_ctrl_trace
        stage_calls.append("validate-traces")
        output_root = Path(output_root)
        raw_dir = output_root / "raw"
        derived_dir = output_root / "derived"
        raw_dir.mkdir(parents=True, exist_ok=True)
        derived_dir.mkdir(parents=True, exist_ok=True)
        trace_inspection_path = raw_dir / "trace_inspection.json"
        trace_inspection_path.write_text("{}\n", encoding="utf-8")
        normalized_trace_path = derived_dir / "normalized_ldpc_trace.csv"
        validation_errors_path = raw_dir / "validation_errors.csv"
        if validate_success:
            normalized_trace_path.write_text(
                "time_ms,sm_utilization\n0,0\n", encoding="utf-8"
            )
            return SimpleNamespace(
                success=True,
                trace_inspection_path=trace_inspection_path,
                normalized_trace_path=normalized_trace_path,
                validation_errors_path=None,
                user_error_message=lambda: "",
            )
        validation_errors_path.write_text(
            "trace_name,error_code,message\nldpc_trace.csv,invalid,validation failed\n",
            encoding="utf-8",
        )
        return SimpleNamespace(
            success=False,
            trace_inspection_path=trace_inspection_path,
            normalized_trace_path=None,
            validation_errors_path=validation_errors_path,
            user_error_message=lambda: "validation failed",
        )

    def fake_orchestrate_profile_run(
        *,
        run_root,
        models,
        chunk_sizes,
        sequence_lengths,
        gpu_id=0,
        sm_ai_partition=100,
        cache_root=None,
        experiment_type=None,
    ):
        del (
            models,
            chunk_sizes,
            sequence_lengths,
            gpu_id,
            sm_ai_partition,
            cache_root,
            experiment_type,
        )
        stage_calls.append("profile")
        manifest_path = Path(run_root) / paths.RUN_MANIFEST_FILENAME
        run_root = Path(run_root)
        environment_path = run_root / paths.ENVIRONMENT_FILENAME
        if not environment_path.exists():
            environment_path.write_text('{"stage":"profile"}\n', encoding="utf-8")
        (run_root / "logs" / "profile-stage.log").write_text(
            "profile stage complete\n",
            encoding="utf-8",
        )
        for relative_path in (
            "raw/prefill_events.csv",
            "raw/prefill_events_status.csv",
            "raw/decode_events.csv",
            "raw/decode_events_status.csv",
            "raw/pcie_events.csv",
            "raw/pcie_events_status.csv",
            "derived/model_constants.csv",
            "derived/prefill_summary.csv",
            "derived/decode_summary.csv",
            "derived/pcie_summary.csv",
        ):
            artifact_path = run_root / relative_path
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text("header\nvalue\n", encoding="utf-8")
        manifests.update_stage_status(
            manifest_path,
            stage="profile",
            status="success",
            details={"stub": True},
        )
        return SimpleNamespace(
            success=True,
            row_counts={"prefill": 1, "decode": 1, "pcie": 1},
            run_root=Path(run_root),
        )

    def fake_run_deterministic_simulation(
        *, run_root, ldpc_trace_path=None, experiment_type=None
    ):
        del ldpc_trace_path, experiment_type
        stage_calls.append("simulate")
        derived_dir = Path(run_root) / "derived"
        derived_dir.mkdir(parents=True, exist_ok=True)
        (derived_dir / "simulation_inputs.csv").write_text(
            "header\nvalue\n",
            encoding="utf-8",
        )
        results_path = derived_dir / "ran_inference_profiling_results.csv"
        timeline_path = derived_dir / "schedule_timeline.csv"
        results_path.write_text("status\nsuccess\n", encoding="utf-8")
        timeline_path.write_text("phase\nprefill\n", encoding="utf-8")
        return SimpleNamespace(
            results_path=results_path,
            timeline_path=timeline_path,
            row_count=1,
        )

    def fake_generate_profiling_plots(*, run_root):
        stage_calls.append("report")
        derived_dir = Path(run_root) / "derived"
        derived_dir.mkdir(parents=True, exist_ok=True)
        plots_dir = Path(run_root) / "plots"
        plots_dir.mkdir(parents=True, exist_ok=True)
        for filename in (
            "01_ran_trace_interleaving.png",
            "02_prefill_safety_boundary.png",
            "03_prefill_vram_composition.png",
            "04_ttft_vs_runway.png",
            "05_decode_tpot_degradation.png",
            "06_operation_level_microarchitecture_summary.png",
        ):
            (plots_dir / filename).write_bytes(b"png")
        (plots_dir / "01_ran_trace_interleaving_interactive.html").write_text(
            "<html><body>interactive</body></html>",
            encoding="utf-8",
        )
        (derived_dir / "packed_exemplar_timeline.csv").write_text(
            "schedule_variant,task_id,model_id,chunk_tokens,sequence_length,phase,mode,family,chunk_index,token_index,layer_index,atom_index,trace_interval_index,start_time_ms,end_time_ms,duration_ms\n"
            "vram,0,facebook/opt-125m,64,1024,prefill,prefill,prefill_gemm,0,,0,0,0,0.0,1.0,1.0\n",
            encoding="utf-8",
        )

    def fake_generate_run_report(*, run_root):
        report_path = Path(run_root) / paths.REPORT_FILENAME
        report_path.write_text("report\n", encoding="utf-8")
        report_module.write_run_checksum_manifest(run_root=run_root)
        return report_path

    def fake_verify_bundle(run_root):
        stage_calls.append("verify-bundle")
        status = verify_status
        return {
            "status": status,
            "complete": status == "success",
            "checksums_valid": status == "success",
            "missing_artifacts": []
            if status == "success"
            else ["raw/prefill_events.csv"],
            "zero_byte_artifacts": [],
            "checksum_missing_artifacts": [],
            "checksum_mismatches": [],
        }

    monkeypatch.setattr(
        bootstrap_module, "bootstrap_environment", fake_bootstrap_environment
    )
    monkeypatch.setattr(
        trace_module, "validate_trace_contract", fake_validate_trace_contract
    )
    monkeypatch.setattr(
        profile_module, "orchestrate_profile_run", fake_orchestrate_profile_run
    )
    monkeypatch.setattr(
        simulator_module,
        "run_deterministic_simulation",
        fake_run_deterministic_simulation,
    )
    monkeypatch.setattr(
        plots_module, "generate_profiling_plots", fake_generate_profiling_plots
    )
    monkeypatch.setattr(report_module, "generate_run_report", fake_generate_run_report)
    monkeypatch.setattr(verify_module, "verify_bundle", fake_verify_bundle)


def _patch_pipeline_with_real_verify(
    monkeypatch: pytest.MonkeyPatch,
    stage_calls: list[str],
) -> None:
    import inference_profile.bootstrap as bootstrap_module
    import inference_profile.plots as plots_module
    import inference_profile.profile_orchestrator as profile_module
    import inference_profile.report as report_module
    import inference_profile.simulator as simulator_module
    import inference_profile.trace_contract as trace_module
    import inference_profile.verify_bundle as verify_module

    def _write_text(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def fake_bootstrap_environment(
        *,
        output_root,
        cache_root=None,
        gpu_id=0,
        experiment_type=None,
        manifest_metadata=None,
    ):
        del cache_root, gpu_id, experiment_type, manifest_metadata
        stage_calls.append("bootstrap-env")
        bundle_paths = paths.bundle_paths_from_run_root(Path(output_root))
        for directory in bundle_paths.directories:
            directory.mkdir(parents=True, exist_ok=True)
        manifests.initialize_run_manifest(bundle_paths)
        _write_text(bundle_paths.environment_path, '{"stage":"bootstrap-env"}\n')
        manifests.update_stage_status(
            bundle_paths.run_manifest_path,
            stage="bootstrap-env",
            status="success",
            details={"stub": True},
        )
        return SimpleNamespace(output_root=Path(output_root))

    def fake_validate_trace_contract(ldpc_trace, ran_ctrl_trace, output_root):
        del ldpc_trace, ran_ctrl_trace
        stage_calls.append("validate-traces")
        output_root = Path(output_root)
        trace_inspection_path = output_root / "raw" / "trace_inspection.json"
        normalized_trace_path = output_root / "derived" / "normalized_ldpc_trace.csv"
        _write_text(
            trace_inspection_path,
            '{"primary_trace":{"usable":true},"secondary_trace":{"usable":true}}\n',
        )
        _write_text(normalized_trace_path, "time_ms,sm_utilization\n0,0\n")
        return SimpleNamespace(
            success=True,
            trace_inspection_path=trace_inspection_path,
            normalized_trace_path=normalized_trace_path,
            validation_errors_path=None,
            user_error_message=lambda: "",
        )

    def fake_orchestrate_profile_run(
        *,
        run_root,
        models,
        chunk_sizes,
        sequence_lengths,
        gpu_id=0,
        sm_ai_partition=100,
        cache_root=None,
        experiment_type=None,
    ):
        del (
            models,
            chunk_sizes,
            sequence_lengths,
            gpu_id,
            sm_ai_partition,
            cache_root,
            experiment_type,
        )
        stage_calls.append("profile")
        run_root = Path(run_root)
        bundle_paths = paths.bundle_paths_from_run_root(run_root)
        _write_text(
            bundle_paths.logs_dir / "profile-stage.log", "profile stage complete\n"
        )
        for relative_path in (
            "raw/prefill_events.csv",
            "raw/prefill_events_status.csv",
            "raw/decode_events.csv",
            "raw/decode_events_status.csv",
            "raw/pcie_events.csv",
            "raw/pcie_events_status.csv",
            "derived/model_constants.csv",
            "derived/prefill_summary.csv",
            "derived/decode_summary.csv",
            "derived/pcie_summary.csv",
        ):
            _write_text(run_root / relative_path, "header\nvalue\n")
        manifests.update_stage_status(
            bundle_paths.run_manifest_path,
            stage="profile",
            status="success",
            details={"stub": True},
        )
        return SimpleNamespace(
            success=True,
            row_counts={"prefill": 1, "decode": 1, "pcie": 1},
            run_root=run_root,
        )

    def fake_run_deterministic_simulation(
        *, run_root, ldpc_trace_path=None, experiment_type=None
    ):
        del ldpc_trace_path, experiment_type
        stage_calls.append("simulate")
        run_root = Path(run_root)
        results_path = run_root / "derived" / "ran_inference_profiling_results.csv"
        timeline_path = run_root / "derived" / "schedule_timeline.csv"
        _write_text(run_root / "derived" / "simulation_inputs.csv", "header\nvalue\n")
        _write_text(results_path, "header\nvalue\n")
        _write_text(timeline_path, "header\nvalue\n")
        return SimpleNamespace(
            results_path=results_path,
            timeline_path=timeline_path,
            row_count=1,
        )

    def fake_generate_profiling_plots(*, run_root):
        stage_calls.append("report")
        derived_dir = Path(run_root) / "derived"
        derived_dir.mkdir(parents=True, exist_ok=True)
        plots_dir = Path(run_root) / "plots"
        plots_dir.mkdir(parents=True, exist_ok=True)
        for filename in (
            "01_ran_trace_interleaving.png",
            "02_prefill_safety_boundary.png",
            "03_prefill_vram_composition.png",
            "04_ttft_vs_runway.png",
            "05_decode_tpot_degradation.png",
            "06_operation_level_microarchitecture_summary.png",
        ):
            (plots_dir / filename).write_bytes(b"png")
        (plots_dir / "01_ran_trace_interleaving_interactive.html").write_text(
            "<html><body>interactive</body></html>",
            encoding="utf-8",
        )
        (derived_dir / "packed_exemplar_timeline.csv").write_text(
            "schedule_variant,task_id,model_id,chunk_tokens,sequence_length,phase,mode,family,chunk_index,token_index,layer_index,atom_index,trace_interval_index,start_time_ms,end_time_ms,duration_ms\n"
            "vram,0,facebook/opt-125m,64,1024,prefill,prefill,prefill_gemm,0,,0,0,0,0.0,1.0,1.0\n",
            encoding="utf-8",
        )

    def fake_generate_run_report(*, run_root):
        bundle_paths = paths.bundle_paths_from_run_root(Path(run_root))
        _write_text(bundle_paths.report_path, "report\n")
        report_module.write_run_checksum_manifest(run_root=run_root)
        return bundle_paths.report_path

    real_verify_bundle = verify_module.verify_bundle

    def wrapped_verify_bundle(run_root):
        stage_calls.append("verify-bundle")
        return real_verify_bundle(Path(run_root))

    monkeypatch.setattr(
        bootstrap_module, "bootstrap_environment", fake_bootstrap_environment
    )
    monkeypatch.setattr(
        trace_module, "validate_trace_contract", fake_validate_trace_contract
    )
    monkeypatch.setattr(
        profile_module, "orchestrate_profile_run", fake_orchestrate_profile_run
    )
    monkeypatch.setattr(
        simulator_module,
        "run_deterministic_simulation",
        fake_run_deterministic_simulation,
    )
    monkeypatch.setattr(
        plots_module, "generate_profiling_plots", fake_generate_profiling_plots
    )
    monkeypatch.setattr(report_module, "generate_run_report", fake_generate_run_report)
    monkeypatch.setattr(verify_module, "verify_bundle", wrapped_verify_bundle)


def test_stage_order_is_fixed() -> None:
    assert run_orchestrator.STAGE_ORDER == [
        "bootstrap-env",
        "validate-traces",
        "profile",
        "simulate",
        "report",
        "verify-bundle",
    ]


def test_load_or_create_manifest_migrates_legacy_schema_to_canonical_contract(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "legacy-run"
    _seed_legacy_failed_profile_manifest(run_root)

    manifest = cast(dict[str, Any], run_orchestrator.load_or_create_manifest(run_root))

    assert "status" not in manifest
    assert "stage_status" not in manifest
    assert manifest["final_status"] == "profile_failed"
    assert manifest["stages"]["bootstrap-env"]["latest_status"] == "success"
    assert manifest["stages"]["validate-traces"]["latest_status"] == "success"
    assert manifest["stages"]["profile"]["latest_status"] == "profile_failed"


def test_get_resume_start_index_rejects_prior_stage_without_success() -> None:
    manifest = {
        "stages": {
            "bootstrap-env": {"latest_status": "success"},
        }
    }

    with pytest.raises(ValueError, match="prior stage 'validate-traces'"):
        run_orchestrator.get_resume_start_index("profile", manifest)


def test_run_orchestrator_executes_fixed_stage_order_and_marks_final_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_root = tmp_path / "ordered-run"
    stage_calls: list[str] = []
    _patch_pipeline(monkeypatch, stage_calls)

    manifest = cast(
        dict[str, Any],
        run_orchestrator.run_orchestrator(
            run_root=run_root,
            ldpc_trace=tmp_path / "ldpc.csv",
            ran_ctrl_trace=tmp_path / "ran.csv",
            models=["facebook/opt-125m"],
            chunk_sizes=[32],
            sequence_lengths=[128],
        ),
    )

    written = _read_json(run_root / paths.RUN_MANIFEST_FILENAME)

    assert stage_calls == run_orchestrator.STAGE_ORDER
    assert manifest["final_status"] == "success"
    assert written["final_status"] == "success"
    assert "status" not in written
    assert "stage_status" not in written
    assert [
        written["stages"][stage]["latest_status"]
        for stage in run_orchestrator.STAGE_ORDER
    ] == [
        "success",
        "success",
        "success",
        "success",
        "success",
        "success",
    ]


def test_run_orchestrator_resume_from_profile_skips_prior_successes_and_reruns_requested_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_root = tmp_path / "resume-run"
    _seed_legacy_failed_profile_manifest(run_root)
    stage_calls: list[str] = []
    _patch_pipeline(monkeypatch, stage_calls)

    manifest = cast(
        dict[str, Any],
        run_orchestrator.run_orchestrator(
            run_root=run_root,
            ldpc_trace=tmp_path / "ldpc.csv",
            ran_ctrl_trace=tmp_path / "ran.csv",
            models=["facebook/opt-125m"],
            chunk_sizes=[32],
            sequence_lengths=[128],
            resume_from="profile",
        ),
    )

    written = _read_json(run_root / paths.RUN_MANIFEST_FILENAME)

    assert stage_calls == ["profile", "simulate", "report", "verify-bundle"]
    assert manifest["final_status"] == "success"
    assert len(written["stages"]["bootstrap-env"]["history"]) == 1
    assert len(written["stages"]["validate-traces"]["history"]) == 1
    assert [entry["status"] for entry in written["stages"]["profile"]["history"]] == [
        "profile_failed",
        "success",
    ]
    assert [entry["status"] for entry in written["final_status_history"]] == [
        "profile_failed",
        "success",
    ]


def test_run_orchestrator_stops_on_first_failure_and_records_canonical_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_root = tmp_path / "failed-run"
    stage_calls: list[str] = []
    _patch_pipeline(monkeypatch, stage_calls, validate_success=False)

    with pytest.raises(RuntimeError, match="validation failed"):
        run_orchestrator.run_orchestrator(
            run_root=run_root,
            ldpc_trace=tmp_path / "ldpc.csv",
            ran_ctrl_trace=tmp_path / "ran.csv",
            models=["facebook/opt-125m"],
            chunk_sizes=[32],
            sequence_lengths=[128],
        )

    written = _read_json(run_root / paths.RUN_MANIFEST_FILENAME)

    assert stage_calls == ["bootstrap-env", "validate-traces"]
    assert written["final_status"] == "validation_failed"
    assert written["stages"]["validate-traces"]["latest_status"] == "validation_failed"
    assert "profile" not in written["stages"]


def test_cli_run_all_fails_when_final_manifest_status_is_not_success(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    import inference_profile.run_orchestrator as orchestrator_module

    monkeypatch.setattr(
        orchestrator_module,
        "run_orchestrator",
        lambda **_: {"final_status": "fetch_failed"},
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main(
            [
                "run-all",
                "--run-root",
                str(tmp_path / "run"),
                "--ldpc-trace",
                str(tmp_path / "ldpc.csv"),
                "--ran-ctrl-trace",
                str(tmp_path / "ran.csv"),
                "--models",
                "facebook/opt-125m",
                "--chunk-sizes",
                "32",
                "--sequence-lengths",
                "128",
            ]
        )

    stderr = capsys.readouterr().err

    assert exc_info.value.code == 2
    assert "final status" in stderr
    assert "fetch_failed" in stderr


def test_cli_run_all_dry_run_creates_revised_manifest_without_executing_stages(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_root = tmp_path / "runs" / "revised-ran-dgxspark-smoke"

    exit_code = cli.main(
        [
            "run-all",
            "--run-root",
            str(run_root),
            "--ldpc-trace",
            str(tmp_path / "ldpc.csv"),
            "--ran-ctrl-trace",
            str(tmp_path / "ran.csv"),
            "--models",
            "facebook/opt-125m",
            "--chunk-sizes",
            "64",
            "--sequence-lengths",
            "1024",
            "--experiment-type",
            experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE,
            "--dry-run",
        ]
    )

    stdout = capsys.readouterr().out
    manifest = _read_json(run_root / "run_manifest.json")

    assert exit_code == 0
    assert "Planned stages:" in stdout
    assert "- bootstrap-env" in stdout
    assert "- verify-bundle" in stdout
    assert manifest["schema_version"] == experiments.RAN_DGXSPARK_V1_SCHEMA_VERSION
    assert manifest["experiment_type"] == experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE
    assert manifest["telemetry_tier"] == experiments.RAN_DGXSPARK_V1_TELEMETRY_TIER
    assert manifest["scheduler"] == experiments.RAN_DGXSPARK_V1_SCHEDULER
    assert manifest["final_status"] is None


def test_cli_run_all_dry_run_allows_default_revised_run_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = cli.main(
        [
            "run-all",
            "--ldpc-trace",
            str(tmp_path / "ldpc.csv"),
            "--ran-ctrl-trace",
            str(tmp_path / "ran.csv"),
            "--models",
            "facebook/opt-125m",
            "--chunk-sizes",
            "64",
            "--sequence-lengths",
            "1024",
            "--experiment-type",
            experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE,
            "--dry-run",
        ]
    )

    stdout = capsys.readouterr().out
    assert exit_code == 0
    assert "revised-ran-dgxspark-" in stdout


def test_cli_run_all_dry_run_allows_missing_execution_args_for_revised_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = cli.main(
        [
            "run-all",
            "--experiment-type",
            experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE,
            "--dry-run",
        ]
    )

    stdout = capsys.readouterr().out
    assert exit_code == 0
    assert "Planned stages:" in stdout
    assert "Run manifest:" in stdout


def test_run_orchestrator_final_bundle_remains_checksum_stable_after_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import inference_profile.verify_bundle as verify_module

    run_root = tmp_path / "final-bundle-run"
    stage_calls: list[str] = []
    _patch_pipeline_with_real_verify(monkeypatch, stage_calls)

    manifest = cast(
        dict[str, Any],
        run_orchestrator.run_orchestrator(
            run_root=run_root,
            ldpc_trace=tmp_path / "ldpc.csv",
            ran_ctrl_trace=tmp_path / "ran.csv",
            models=["facebook/opt-125m"],
            chunk_sizes=[64],
            sequence_lengths=[1024],
        ),
    )

    verification = verify_module.verify_bundle(run_root)

    assert stage_calls == [*run_orchestrator.STAGE_ORDER, "verify-bundle"]
    assert manifest["final_status"] == "success"
    assert (
        "plots/01_ran_trace_interleaving_interactive.html"
        in manifest["stages"]["report"]["details"]["plot_files"]
    )
    assert verification["status"] == "success"
    assert verification["checksum_mismatches"] == []


def test_run_orchestrator_can_resume_from_verify_bundle_after_failed_verification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import inference_profile.verify_bundle as verify_module

    run_root = tmp_path / "resume-verify-bundle-run"
    initial_stage_calls: list[str] = []
    _patch_pipeline_with_real_verify(monkeypatch, initial_stage_calls)

    run_orchestrator.run_orchestrator(
        run_root=run_root,
        ldpc_trace=tmp_path / "ldpc.csv",
        ran_ctrl_trace=tmp_path / "ran.csv",
        models=["facebook/opt-125m"],
        chunk_sizes=[64],
        sequence_lengths=[1024],
    )

    manifests.set_final_status(
        run_root / paths.RUN_MANIFEST_FILENAME,
        "fetch_failed",
        details={"reason": "simulated previous verify failure"},
    )

    resumed_stage_calls: list[str] = []
    real_verify_bundle = verify_module.verify_bundle

    def wrapped_verify_bundle(run_root_path: Path) -> dict[str, Any]:
        resumed_stage_calls.append("verify-bundle")
        return cast(dict[str, Any], real_verify_bundle(run_root_path))

    monkeypatch.setattr(verify_module, "verify_bundle", wrapped_verify_bundle)

    resumed_manifest = cast(
        dict[str, Any],
        run_orchestrator.run_orchestrator(
            run_root=run_root,
            ldpc_trace=tmp_path / "ldpc.csv",
            ran_ctrl_trace=tmp_path / "ran.csv",
            models=["facebook/opt-125m"],
            chunk_sizes=[64],
            sequence_lengths=[1024],
            resume_from="verify-bundle",
        ),
    )

    verification = real_verify_bundle(run_root)

    assert resumed_stage_calls == ["verify-bundle"]
    assert resumed_manifest["final_status"] == "success"
    assert verification["status"] == "success"
    assert verification["checksum_mismatches"] == []
