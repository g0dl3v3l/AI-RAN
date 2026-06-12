"""Unit tests for worker-side MPS partition environment mapping."""

import os

import pytest

from inference_profile import experiments, worker_profile_point


def _reset_mps_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CUDA_MPS_ENABLE_PER_CTX_DEVICE_MULTIPROCESSOR_PARTITIONING", raising=False)
    monkeypatch.delenv("CUDA_MPS_ACTIVE_THREAD_PERCENTAGE", raising=False)


def test_configure_mps_partition_legacy_percent_passthrough(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _reset_mps_env(monkeypatch)

    worker_profile_point._configure_mps_partition({"sm_ai_partition": 40})

    assert "CUDA_MPS_ENABLE_PER_CTX_DEVICE_MULTIPROCESSOR_PARTITIONING" in os.environ
    assert os.environ["CUDA_MPS_ACTIVE_THREAD_PERCENTAGE"] == "40"


def test_configure_mps_partition_revised_sm_count_maps_to_percentage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _reset_mps_env(monkeypatch)

    worker_profile_point._configure_mps_partition(
        {
            "sm_ai_partition": 8,
            "experiment_type": experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE,
        }
    )

    assert os.environ["CUDA_MPS_ACTIVE_THREAD_PERCENTAGE"] == "25"


def test_configure_mps_partition_revised_percent_value_passthrough(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _reset_mps_env(monkeypatch)

    worker_profile_point._configure_mps_partition(
        {
            "sm_ai_partition": 80,
            "experiment_type": experiments.RAN_DGXSPARK_V1_EXPERIMENT_TYPE,
        }
    )

    assert os.environ["CUDA_MPS_ACTIVE_THREAD_PERCENTAGE"] == "80"


def test_configure_mps_partition_rejects_invalid_range() -> None:
    with pytest.raises(ValueError, match="sm_ai_partition must be between 1 and 100"):
        worker_profile_point._configure_mps_partition({"sm_ai_partition": 0})
