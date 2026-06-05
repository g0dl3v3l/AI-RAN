from __future__ import annotations

import argparse

from experiments.scripts.run_smoke_request import _build_runtime_config


def test_base_url_enables_external_server_runtime() -> None:
    args = argparse.Namespace(
        base_url="http://127.0.0.1:8000/v1",
        allow_docker_start=False,
        docker_image="vllm/vllm-openai:latest",
        model="example/model",
        docker_port=8000,
        container_name="",
    )

    config = _build_runtime_config(args)

    assert config["external_server"] == {
        "enabled": True,
        "base_url": "http://127.0.0.1:8000/v1",
    }
    assert config["docker_server"]["enabled"] is False


def test_empty_base_url_keeps_external_server_disabled() -> None:
    args = argparse.Namespace(
        base_url="",
        allow_docker_start=False,
        docker_image="vllm/vllm-openai:latest",
        model="example/model",
        docker_port=8000,
        container_name="",
    )

    config = _build_runtime_config(args)

    assert config["external_server"] == {"enabled": False, "base_url": ""}
