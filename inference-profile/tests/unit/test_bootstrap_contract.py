from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from inference_profile import bootstrap


class _FakeCuda:
    def is_available(self) -> bool:
        return True

    def device_count(self) -> int:
        return 1

    def get_device_properties(self, gpu_id: int) -> SimpleNamespace:
        assert gpu_id == 0
        return SimpleNamespace(
            name="DGX Test GPU",
            total_memory=8_589_934_592,
            multi_processor_count=108,
            major=9,
            minor=0,
        )


_FAKE_TORCH = SimpleNamespace(
    __version__="2.11.0+cu130",
    version=SimpleNamespace(cuda="13.0"),
    cuda=_FakeCuda(),
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _fake_probe_dependency(module_name: str, *, required: bool):
    if module_name == "torch":
        return _FAKE_TORCH, {
            "required": True,
            "available": True,
            "version": _FAKE_TORCH.__version__,
            "error": None,
        }
    return None, {
        "required": required,
        "available": False,
        "version": None,
        "error": f"No module named '{module_name}'",
    }


def test_bootstrap_environment_creates_system_site_packages_venv_and_snapshot(
    monkeypatch,
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "bootstrap-ok"
    monkeypatch.setattr(bootstrap, "_probe_dependency", _fake_probe_dependency)
    monkeypatch.setattr(
        bootstrap,
        "_probe_cuda_driver_version",
        lambda _gpu_id: "550.54.14",
    )

    result = bootstrap.bootstrap_environment(output_root=output_root, gpu_id=0)
    payload = _read_json(output_root / "environment.json")
    manifest = _read_json(output_root / "run_manifest.json")

    assert result.success is True
    assert payload == result.payload
    assert payload["stage"] == "bootstrap-env"
    assert payload["bootstrap_status"] == "success"
    assert payload["public_status"] == "success"
    assert payload["failure_kind"] is None
    assert payload["failure_cause"] is None
    assert payload["installation"]["mode"] == "validate-only"
    assert payload["installation"]["system_packages_mutated"] is False
    assert payload["venv"]["create_command"] == (
        "python3 -m venv --system-site-packages .venv"
    )
    assert payload["venv"]["system_site_packages_required"] is True
    assert payload["venv"]["status"] == "created"
    assert payload["dependencies"]["torch"] == {
        "required": True,
        "available": True,
        "version": "2.11.0+cu130",
        "error": None,
    }
    assert payload["dependencies"]["transformers"]["available"] is False
    assert payload["dependencies"]["safetensors"]["available"] is False
    assert payload["paths"]["output_root"]["writable"] is True
    assert payload["paths"]["cache_root"]["writable"] is True
    assert payload["cuda"] == {
        "selected_gpu_id": 0,
        "available": True,
        "device_count": 1,
        "torch_cuda_build_version": "13.0",
        "driver_version": "550.54.14",
        "gpu_name": "DGX Test GPU",
        "total_memory_bytes": 8_589_934_592,
        "multi_processor_count": 108,
        "compute_capability": "9.0",
        "probe_error": None,
    }
    assert payload["manifest_update"]["status"] == "updated"
    assert manifest["final_status"] is None
    assert manifest["stages"]["bootstrap-env"]["latest_status"] == "success"

    pyvenv_cfg = output_root / ".venv" / "pyvenv.cfg"
    assert pyvenv_cfg.exists()
    assert (
        "include-system-site-packages = true"
        in pyvenv_cfg.read_text(encoding="utf-8").lower()
    )


def test_bootstrap_environment_validates_existing_venv_on_repeat_run(
    monkeypatch,
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "bootstrap-repeat"
    monkeypatch.setattr(bootstrap, "_probe_dependency", _fake_probe_dependency)
    monkeypatch.setattr(
        bootstrap,
        "_probe_cuda_driver_version",
        lambda _gpu_id: "550.54.14",
    )

    created = bootstrap.bootstrap_environment(output_root=output_root, gpu_id=0)
    validated = bootstrap.bootstrap_environment(output_root=output_root, gpu_id=0)
    manifest = _read_json(output_root / "run_manifest.json")

    assert created.payload["venv"]["status"] == "created"
    assert validated.success is True
    assert validated.payload["venv"]["status"] == "validated"
    assert validated.payload["manifest_update"]["status"] == "updated"
    assert len(manifest["stages"]["bootstrap-env"]["history"]) == 2
