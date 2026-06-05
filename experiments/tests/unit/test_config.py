from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from ai_runtime_experiments.config import ResolvedConfig, load_config


MINIMAL_CONFIG = """
experiment_id: v0_env_probe
version: v0
runtime: vllm
model: meta-llama/Meta-Llama-3-8B-Instruct
arm: env_probe
workload:
  prompt: Respond with the exact text 'smoke ok'.
preemption_policy: {}
resource_delta: {}
telemetry: {}
output_dir: experiments/results/v0_env_probe
seed: 7
"""


def _write_config(path: Path, content: str = MINIMAL_CONFIG) -> Path:
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
    return path



def test_load_config_resolves_defaults_and_cli_overrides(tmp_path: Path):
    config_path = _write_config(tmp_path / "config.yaml")
    override_output_dir = tmp_path / "cli-run"

    resolved = load_config(
        config_path,
        output_dir_override=override_output_dir,
        dry_run=True,
    )

    assert isinstance(resolved, ResolvedConfig)
    assert resolved.config_path == config_path.resolve()
    assert resolved.output_dir == override_output_dir.resolve()
    assert resolved.run_id == "cli-run"
    assert resolved.dry_run is True
    assert resolved.runtime == "vllm"
    assert resolved.workload["prompt"] == "Respond with the exact text 'smoke ok'."
    assert resolved.runtime_options["vllm"]["docker_server"]["model"] == (
        "meta-llama/Meta-Llama-3-8B-Instruct"
    )
    assert resolved.probe_options["cuda"]["image"] == "nvidia/cuda:12.4.1-base-ubuntu22.04"

    dumped = resolved.to_dict()
    assert dumped["output_dir"] == str(override_output_dir.resolve())
    assert dumped["run_id"] == "cli-run"
    assert dumped["dry_run"] is True



def test_load_config_uses_safe_yaml_loader(tmp_path: Path):
    config_path = _write_config(
        tmp_path / "unsafe.yaml",
        "!!python/object/apply:os.system ['echo nope']\n",
    )

    with pytest.raises(ValueError, match="safe YAML"):
        load_config(config_path)



def test_load_config_rejects_unsupported_runtime(tmp_path: Path):
    config_path = _write_config(
        tmp_path / "unsupported.yaml",
        """
        experiment_id: v0_env_probe
        version: v0
        runtime: sglang
        model: null
        arm: env_probe
        workload: {}
        preemption_policy: {}
        resource_delta: {}
        telemetry: {}
        output_dir: experiments/results/v0_env_probe
        seed: 0
        """,
    )

    with pytest.raises(ValueError, match="unsupported runtime"):
        load_config(config_path)
