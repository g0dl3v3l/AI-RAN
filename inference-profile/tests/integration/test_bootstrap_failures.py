from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from inference_profile import bootstrap


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_bootstrap_environment_reports_bootstrap_failed_when_cuda_torch_is_unavailable(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "bootstrap-no-cuda"

    with pytest.raises(bootstrap.BootstrapEnvironmentError) as exc_info:
        bootstrap.bootstrap_environment(output_root=output_root, gpu_id=0)

    result = exc_info.value.result
    payload = _read_json(output_root / "environment.json")
    manifest = _read_json(output_root / "run_manifest.json")

    assert result.success is False
    assert result.failure is not None
    assert result.failure.public_status == "bootstrap_failed"
    assert result.failure.failure_kind == "cuda_unavailable"
    assert result.failure.step == "cuda"
    assert payload["bootstrap_status"] == "bootstrap_failed"
    assert payload["public_status"] == "bootstrap_failed"
    assert payload["failure_kind"] == "cuda_unavailable"
    assert payload["failure_cause"] == "torch.cuda.is_available() returned False"
    assert payload["dependencies"]["torch"]["available"] is True
    assert payload["cuda"]["available"] is False
    assert payload["venv"]["system_site_packages_required"] is True
    assert manifest["final_status"] == "bootstrap_failed"
    assert manifest["stages"]["bootstrap-env"]["latest_status"] == "bootstrap_failed"


def test_bootstrap_environment_reports_typed_failure_for_unwritable_cache_root(
    monkeypatch,
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "bootstrap-bad-cache"
    cache_root = tmp_path / "readonly-cache"
    real_validate = bootstrap._validate_writable_directory

    def fake_validate(path: Path, *, label: str) -> dict[str, Any]:
        if label == "cache_root":
            raise bootstrap._BootstrapCheckFailed(
                bootstrap.BootstrapFailure(
                    failure_kind="path_not_writable",
                    failure_cause=(
                        f"{label} directory {path} is not writable: synthetic denial"
                    ),
                    step=label,
                )
            )
        return real_validate(path, label=label)

    monkeypatch.setattr(bootstrap, "_validate_writable_directory", fake_validate)

    with pytest.raises(bootstrap.BootstrapEnvironmentError) as exc_info:
        bootstrap.bootstrap_environment(
            output_root=output_root,
            cache_root=cache_root,
            gpu_id=0,
        )

    result = exc_info.value.result
    payload = _read_json(output_root / "environment.json")
    manifest = _read_json(output_root / "run_manifest.json")

    assert result.success is False
    assert result.failure is not None
    assert result.failure.failure_kind == "path_not_writable"
    assert result.failure.step == "cache_root"
    assert payload["bootstrap_status"] == "bootstrap_failed"
    assert payload["failure_kind"] == "path_not_writable"
    assert payload["failed_step"] == "cache_root"
    assert isinstance(payload["failure_cause"], str)
    assert "cache_root directory" in payload["failure_cause"]
    assert payload["paths"]["output_root"]["writable"] is True
    assert payload["manifest_update"]["status"] == "updated"
    assert not (output_root / ".venv").exists()
    assert manifest["final_status"] == "bootstrap_failed"
    assert manifest["stages"]["bootstrap-env"]["latest_status"] == "bootstrap_failed"
