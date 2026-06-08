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
        runtime="vllm",
        docker_image="vllm/vllm-openai:latest",
        model="example/model",
        docker_port=8000,
        container_name="",
        host_model_dir="",
        model_file="",
        threads=4,
        ctx_size=2048,
        n_gpu_layers=0,
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
        runtime="vllm",
        docker_image="vllm/vllm-openai:latest",
        model="example/model",
        docker_port=8000,
        container_name="",
        host_model_dir="",
        model_file="",
        threads=4,
        ctx_size=2048,
        n_gpu_layers=0,
    )

    config = module._build_runtime_config(args)

    assert config["external_server"] == {"enabled": False, "base_url": ""}



def test_llama_cpp_docker_config_uses_model_file_and_host_dir() -> None:
    module = _load_run_smoke_request_script()
    args = argparse.Namespace(
        base_url="",
        allow_docker_start=True,
        runtime="llama_cpp",
        docker_image="",
        model="fallback.gguf",
        docker_port=8080,
        container_name="llama-test",
        host_model_dir="/home/netsys/llama-models",
        model_file="gemma-3-1b-it-f16.gguf",
        threads=6,
        ctx_size=1024,
        n_gpu_layers=0,
    )

    config = module._build_runtime_config(args)

    assert config["docker_server"]["enabled"] is True
    assert config["docker_server"]["image"] == "ghcr.io/ggml-org/llama.cpp:server"
    assert config["docker_server"]["model_file"] == "gemma-3-1b-it-f16.gguf"
    assert config["docker_server"]["host_model_dir"] == "/home/netsys/llama-models"
    assert config["docker_server"]["threads"] == 6
    assert config["docker_server"]["ctx_size"] == 1024
    assert config["docker_server"]["n_gpu_layers"] == 0
