from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path


def _load_run_smoke_request_script():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "run_smoke_request.py"
    spec = importlib.util.spec_from_file_location("run_smoke_request_script", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_base_url_enables_external_server_runtime() -> None:
    module = _load_run_smoke_request_script()
    args = argparse.Namespace(
        base_url="http://127.0.0.1:8000/v1",
        allow_docker_start=False,
        docker_image="vllm/vllm-openai:latest",
        model="example/model",
        docker_port=8000,
        container_name="",
    )

    config = module._build_runtime_config(args)

    assert config["external_server"] == {
        "enabled": True,
        "base_url": "http://127.0.0.1:8000/v1",
    }
    assert config["docker_server"]["enabled"] is False


def test_empty_base_url_keeps_external_server_disabled() -> None:
    module = _load_run_smoke_request_script()
    args = argparse.Namespace(
        base_url="",
        allow_docker_start=False,
        docker_image="vllm/vllm-openai:latest",
        model="example/model",
        docker_port=8000,
        container_name="",
    )

    config = module._build_runtime_config(args)

    assert config["external_server"] == {"enabled": False, "base_url": ""}
