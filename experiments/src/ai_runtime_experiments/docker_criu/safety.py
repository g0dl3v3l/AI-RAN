from __future__ import annotations

import re
import uuid
from collections.abc import Mapping

EXPERIMENT_CONTAINER_NAME_PREFIX = "ai-edge-v0-criu-"
EXPERIMENT_LABEL_KEY = "ai-edge-experiment"
EXPERIMENT_LABEL_VALUE = "v0"
EXPERIMENT_COMPONENT_LABEL_KEY = "ai-edge-component"
EXPERIMENT_COMPONENT_LABEL_VALUE = "docker-criu"
EXPERIMENT_RUN_ID_LABEL_KEY = "ai-edge-run-id"

_DOCKER_NAME_SAFE_RE = re.compile(r"[^a-z0-9_.-]+")



def _slug(value: str, *, default: str) -> str:
    slug = _DOCKER_NAME_SAFE_RE.sub("-", value.lower().strip()).strip("-.")
    return slug or default



def build_experiment_container_name(run_id: str, *, token: str | None = None) -> str:
    run_fragment = _slug(run_id, default="run")[:24]
    token_fragment = _slug(token or uuid.uuid4().hex[:8], default="token")[:12]
    return f"{EXPERIMENT_CONTAINER_NAME_PREFIX}{run_fragment}-{token_fragment}".rstrip("-")



def build_experiment_labels(run_id: str) -> dict[str, str]:
    return {
        EXPERIMENT_LABEL_KEY: EXPERIMENT_LABEL_VALUE,
        EXPERIMENT_COMPONENT_LABEL_KEY: EXPERIMENT_COMPONENT_LABEL_VALUE,
        EXPERIMENT_RUN_ID_LABEL_KEY: run_id,
    }



def build_docker_label_args(run_id: str) -> list[str]:
    args: list[str] = []
    for key, value in build_experiment_labels(run_id).items():
        args.extend(["--label", f"{key}={value}"])
    return args



def is_experiment_owned_container(*, container_name: str, labels: Mapping[str, str]) -> bool:
    if not container_name.startswith(EXPERIMENT_CONTAINER_NAME_PREFIX):
        return False
    if labels.get(EXPERIMENT_LABEL_KEY) != EXPERIMENT_LABEL_VALUE:
        return False
    if labels.get(EXPERIMENT_COMPONENT_LABEL_KEY) != EXPERIMENT_COMPONENT_LABEL_VALUE:
        return False
    run_id = labels.get(EXPERIMENT_RUN_ID_LABEL_KEY)
    return isinstance(run_id, str) and bool(run_id.strip())



def ensure_experiment_owned_container(*, container_name: str, labels: Mapping[str, str]) -> None:
    if not is_experiment_owned_container(container_name=container_name, labels=labels):
        raise ValueError(
            f"refusing destructive Docker action because container is not experiment-owned: {container_name}"
        )
