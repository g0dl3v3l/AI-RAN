from __future__ import annotations

import os
from typing import Final

import pytest

AI_EDGE_RUN_INTEGRATION: Final = "AI_EDGE_RUN_INTEGRATION"
AI_EDGE_RUN_GPU: Final = "AI_EDGE_RUN_GPU"
AI_EDGE_VLLM_BASE_URL: Final = "AI_EDGE_VLLM_BASE_URL"


def _env_flag_enabled(name: str) -> bool:
    return os.environ.get(name) == "1"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    run_integration = _env_flag_enabled(AI_EDGE_RUN_INTEGRATION)
    run_gpu = _env_flag_enabled(AI_EDGE_RUN_GPU)
    integration_skip = pytest.mark.skip(
        reason=(
            "integration tests are opt-in; "
            f"set {AI_EDGE_RUN_INTEGRATION}=1 to run them"
        )
    )
    gpu_skip = pytest.mark.skip(
        reason=(
            "gpu tests are opt-in; "
            f"set {AI_EDGE_RUN_GPU}=1 to run them"
        )
    )

    for item in items:
        if "gpu" in item.keywords and not run_gpu:
            item.add_marker(gpu_skip)
            continue
        if "integration" in item.keywords and not run_integration:
            item.add_marker(integration_skip)


@pytest.fixture(scope="session")
def external_vllm_base_url() -> str:
    base_url = os.environ.get(AI_EDGE_VLLM_BASE_URL)
    if not base_url:
        pytest.skip(
            f"external vLLM smoke requires {AI_EDGE_VLLM_BASE_URL} to be set"
        )
    return base_url.rstrip("/")
