from __future__ import annotations

import pytest

from inference_profile import pcie_profile


@pytest.mark.parametrize(
    ("overlap_total_us", "dummy_compute_us", "expected_exposed_transfer_us"),
    (
        (100.0, 150.0, 0.0),
        (200.0, 50.0, 150.0),
        (100.0, 100.0, 0.0),
        (50.5, 20.25, 30.25),
    ),
)
def test_calculate_exposed_transfer_us_matches_task8_formula(
    overlap_total_us: float,
    dummy_compute_us: float,
    expected_exposed_transfer_us: float,
) -> None:
    assert pcie_profile.calculate_exposed_transfer_us(
        overlap_total_us,
        dummy_compute_us,
    ) == pytest.approx(expected_exposed_transfer_us)


def test_calculate_exposed_transfer_us_never_goes_negative() -> None:
    assert pcie_profile.calculate_exposed_transfer_us(12.0, 30.0) == 0.0
