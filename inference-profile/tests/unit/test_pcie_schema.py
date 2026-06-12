from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path

import pytest
import torch

from inference_profile import pcie_profile
from inference_profile.worker_profile_point import RawCsvWriter


def test_resolve_pcie_output_path_defaults_to_raw_pcie_events_csv(
    tmp_path: Path,
) -> None:
    resolved_path = pcie_profile.resolve_pcie_output_path(output_root=tmp_path)

    assert resolved_path == tmp_path / "raw" / "pcie_events.csv"


def test_resolve_pcie_output_path_respects_explicit_raw_output_path(
    tmp_path: Path,
) -> None:
    explicit_path = tmp_path / "custom.csv"
    resolved_path = pcie_profile.resolve_pcie_output_path(raw_output_path=explicit_path)

    assert resolved_path == explicit_path


def test_pcie_fieldnames_are_exact() -> None:
    expected_fields = (
        "model_id",
        "block_size",
        "kv_block_bytes",
        "transfer_only_us",
        "overlap_total_us",
        "dummy_compute_us",
        "exposed_transfer_us",
        "timed_iteration",
    )
    assert pcie_profile.PCIE_EVENT_FIELDNAMES == expected_fields


def test_pcie_constants_are_fixed() -> None:
    assert pcie_profile.PCIE_DTYPE_NAME == "float16"
    assert pcie_profile.PCIE_EVENTS_FILENAME == "pcie_events.csv"


@pytest.mark.parametrize(
    ("block_size", "num_heads", "head_dim", "expected_bytes"),
    (
        (64, 12, 64, 2 * 64 * 12 * 64 * 2),
        (128, 8, 128, 2 * 128 * 8 * 128 * 2),
    ),
)
def test_calculate_kv_block_bytes(
    block_size: int,
    num_heads: int,
    head_dim: int,
    expected_bytes: int,
) -> None:
    assert (
        pcie_profile.calculate_kv_block_bytes(block_size, num_heads, head_dim)
        == expected_bytes
    )


def test_calculate_kv_block_bytes_scales_with_block_size() -> None:
    bytes_64 = pcie_profile.calculate_kv_block_bytes(64, 8, 64)
    bytes_128 = pcie_profile.calculate_kv_block_bytes(128, 8, 64)

    assert bytes_128 == 2 * bytes_64


def test_normalize_block_sizes() -> None:
    assert pcie_profile._normalize_block_sizes([64, 128]) == (64, 128)

    with pytest.raises(ValueError):
        pcie_profile._normalize_block_sizes([])

    with pytest.raises(ValueError):
        pcie_profile._normalize_block_sizes([0, -1])


def test_allocate_pinned_host_tensor_uses_cpu_pin_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    class FakeTensor:
        def uniform_(
            self, low: float, high: float, *, generator: object
        ) -> "FakeTensor":
            calls["uniform"] = (low, high, generator)
            return self

    class FakeGenerator:
        def __init__(self, *, device: str) -> None:
            calls["generator_device"] = device

        def manual_seed(self, seed: int) -> None:
            calls["seed"] = seed

    def fake_empty(
        num_elements: int,
        *,
        dtype: torch.dtype,
        device: str,
        pin_memory: bool,
    ) -> FakeTensor:
        calls["empty"] = {
            "num_elements": num_elements,
            "dtype": dtype,
            "device": device,
            "pin_memory": pin_memory,
        }
        return FakeTensor()

    monkeypatch.setattr(pcie_profile.torch, "empty", fake_empty)
    monkeypatch.setattr(pcie_profile.torch, "Generator", FakeGenerator)

    tensor = pcie_profile._allocate_pinned_host_tensor(16, dtype=torch.float16)

    assert isinstance(tensor, FakeTensor)
    assert calls["empty"] == {
        "num_elements": 16,
        "dtype": torch.float16,
        "device": "cpu",
        "pin_memory": True,
    }
    assert calls["generator_device"] == "cpu"
    assert calls["seed"] == 3_000


def test_time_pcie_transfer_only_uses_non_blocking_copy_and_normal_event_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    constructor_calls: list[dict[str, object]] = []

    class FakeTensor:
        def __init__(self) -> None:
            self.to_calls: list[dict[str, object]] = []

        def to(self, *, device: torch.device, non_blocking: bool) -> object:
            self.to_calls.append({"device": device, "non_blocking": non_blocking})
            return object()

    class FakeEvent:
        def __init__(self, *args: object, **kwargs: object) -> None:
            assert not args
            constructor_calls.append(dict(kwargs))

        def record(self) -> None:
            return None

        def elapsed_time(self, other: object) -> float:
            return 2.5

    host_tensor = FakeTensor()
    device = torch.device("cuda:0")

    monkeypatch.setattr(
        pcie_profile,
        "_allocate_pinned_host_tensor",
        lambda num_elements, *, dtype: host_tensor,
    )
    monkeypatch.setattr(pcie_profile.torch.cuda, "Stream", lambda device: object())
    monkeypatch.setattr(pcie_profile.torch.cuda, "Event", FakeEvent)
    monkeypatch.setattr(
        pcie_profile.torch.cuda,
        "stream",
        lambda stream: nullcontext(),
    )
    monkeypatch.setattr(pcie_profile.torch.cuda, "synchronize", lambda device: None)
    monkeypatch.setattr(
        pcie_profile.torch.cuda,
        "reset_peak_memory_stats",
        lambda device: None,
    )
    monkeypatch.setattr(pcie_profile.torch.cuda, "empty_cache", lambda: None)

    transfer_only_us = pcie_profile._time_pcie_transfer_only(
        block_size=64,
        num_attention_heads=12,
        head_dim=64,
        device=device,
        dtype=torch.float16,
    )

    assert transfer_only_us == pytest.approx(2_500.0)
    assert host_tensor.to_calls == [{"device": device, "non_blocking": True}]
    assert constructor_calls == [
        {"enable_timing": True},
        {"enable_timing": True},
    ]


def test_time_pcie_overlap_waits_for_both_side_streams_before_end_timing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call_log: list[tuple[str, object, object | None]] = []
    created_events: list[FakeEvent] = []

    class FakeTensor:
        def __init__(self, name: str) -> None:
            self.name = name

        def to(self, *, device: torch.device, non_blocking: bool) -> "FakeTensor":
            call_log.append(("copy_to", device, non_blocking))
            return FakeTensor(f"{self.name}_device")

        def t(self) -> "FakeTensor":
            call_log.append(("transpose", self.name, None))
            return self

    class FakeStream:
        def __init__(self, name: str) -> None:
            self.name = name

        def wait_event(self, event: "FakeEvent") -> None:
            call_log.append(("wait_event", self.name, event.label))

    class FakeEvent:
        def __init__(self, *args: object, **kwargs: object) -> None:
            assert not args
            assert kwargs == {"enable_timing": True}
            self.label = f"event_{len(created_events)}"
            created_events.append(self)

        def record(self) -> None:
            call_log.append(("record", self.label, None))

        def elapsed_time(self, other: object) -> float:
            if self is created_events[0] and other is created_events[1]:
                return 4.0
            if self is created_events[3] and other is created_events[4]:
                return 1.5
            raise AssertionError("unexpected elapsed_time pair")

    host_tensor = FakeTensor("host")
    device = torch.device("cuda:0")
    transfer_stream = FakeStream("transfer")
    compute_stream = FakeStream("compute")
    timing_stream = FakeStream("timing")
    stream_queue = [transfer_stream, compute_stream]
    randn_queue = [FakeTensor("compute_input"), FakeTensor("compute_weight")]

    monkeypatch.setattr(
        pcie_profile,
        "_allocate_pinned_host_tensor",
        lambda num_elements, *, dtype: host_tensor,
    )
    monkeypatch.setattr(
        pcie_profile.torch,
        "randn",
        lambda *args, **kwargs: randn_queue.pop(0),
    )
    monkeypatch.setattr(
        pcie_profile.torch,
        "matmul",
        lambda left, right: FakeTensor("compute_output"),
    )
    monkeypatch.setattr(
        pcie_profile.torch.cuda,
        "Stream",
        lambda device: stream_queue.pop(0),
    )
    monkeypatch.setattr(
        pcie_profile.torch.cuda,
        "current_stream",
        lambda device=None: timing_stream,
    )
    monkeypatch.setattr(pcie_profile.torch.cuda, "Event", FakeEvent)
    monkeypatch.setattr(
        pcie_profile.torch.cuda,
        "stream",
        lambda stream: nullcontext(),
    )
    monkeypatch.setattr(pcie_profile.torch.cuda, "synchronize", lambda device: None)
    monkeypatch.setattr(
        pcie_profile.torch.cuda,
        "reset_peak_memory_stats",
        lambda device: None,
    )
    monkeypatch.setattr(pcie_profile.torch.cuda, "empty_cache", lambda: None)

    overlap_total_us, dummy_compute_us = pcie_profile._time_pcie_overlap(
        block_size=64,
        num_attention_heads=12,
        head_dim=64,
        hidden_size=768,
        ffn_dim=3_072,
        device=device,
        dtype=torch.float16,
    )

    assert overlap_total_us == pytest.approx(4_000.0)
    assert dummy_compute_us == pytest.approx(1_500.0)


def test_profile_pcie_with_writer_marks_overlap_unavailable_when_overlap_timing_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    raw_output_path = tmp_path / "raw" / pcie_profile.PCIE_EVENTS_FILENAME
    writer = RawCsvWriter(
        raw_output_path, fieldnames=pcie_profile.PCIE_EVENT_FIELDNAMES
    )

    monkeypatch.setattr(
        pcie_profile,
        "_require_cuda_device",
        lambda _gpu_id: torch.device("cuda:0"),
    )
    monkeypatch.setattr(pcie_profile.torch.cuda, "set_device", lambda _device: None)
    monkeypatch.setattr(
        pcie_profile,
        "resolve_opt_config",
        lambda model_id, **_: type(
            "FakeConfig",
            (),
            {
                "model_id": model_id,
                "num_attention_heads": 12,
                "head_dim": 64,
                "hidden_size": 768,
                "ffn_dim": 3072,
            },
        )(),
    )
    monkeypatch.setattr(pcie_profile, "_run_pcie_transfer_warmup", lambda **_: None)
    monkeypatch.setattr(
        pcie_profile,
        "_time_pcie_transfer_only",
        lambda **_: 125.0,
    )
    monkeypatch.setattr(
        pcie_profile,
        "_time_pcie_overlap",
        lambda **_: (_ for _ in ()).throw(RuntimeError("overlap unsupported")),
    )

    try:
        result = pcie_profile.profile_pcie_with_writer(
            model_id="facebook/opt-125m",
            raw_writer=writer,
            block_sizes=(64,),
            warmup_iterations=0,
            timed_iterations=1,
        )
    finally:
        writer.close()

    rows = list(Path(raw_output_path).read_text(encoding="utf-8").splitlines())

    assert result.overlap_status == "unsupported"
    assert result.row_count == 1
    assert len(rows) == 2
    assert rows[1].split(",")[3:] == ["125.0", "", "", "", "0"]
