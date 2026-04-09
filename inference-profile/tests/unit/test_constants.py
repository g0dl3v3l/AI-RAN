from __future__ import annotations

from inference_profile import constants


def test_opt_model_ids_are_fixed() -> None:
    assert constants.OPT_MODEL_IDS == (
        "facebook/opt-125m",
        "facebook/opt-350m",
        "facebook/opt-1.3b",
        "facebook/opt-2.7b",
        "facebook/opt-6.7b",
    )


def test_chunk_sizes_and_sequence_lengths_are_fixed() -> None:
    assert constants.PREFILL_CHUNK_SIZES == (64, 128, 256, 512, 1024)
    assert constants.DECODE_SEQUENCE_LENGTHS == (1024, 2048, 4096, 8192)


def test_remote_paths_are_fixed() -> None:
    assert constants.REMOTE_HOST == "netsys@192.168.1.20"
    assert constants.REMOTE_PROJECT_ROOT == "/home/netsys/dheeraj/inference-profile"
    assert (
        constants.LOCAL_FETCH_ROOT
        == "/mnt/data/dheeraj/dicertation/inference-profile/runs"
    )
    assert constants.SSHPASS_FILE == "/mnt/data/dheeraj/dicertation/.ssh_pass"


def test_remote_trace_defaults_are_fixed() -> None:
    assert constants.REMOTE_LDPC_TRACE == (
        "/mnt/raid0sata2/netsys/weaver-ext/ran/traces/e2e_2026030418/"
        "e2e_20260304_182034_tractor_ran_ctrl/ldpc_trace.csv"
    )
    assert constants.REMOTE_RAN_CTRL_TRACE == (
        "/mnt/raid0sata2/netsys/weaver-ext/ran/traces/e2e_2026030418/"
        "e2e_20260304_182034_tractor_ran_ctrl/ran_ctrl_trace.csv"
    )
