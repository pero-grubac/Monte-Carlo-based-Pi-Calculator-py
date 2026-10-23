import math
import subprocess
import sys

import pytest

from montecarlo_pi import Estimate, decimal_window, matching_decimals, samples_for_decimals


@pytest.mark.parametrize(
    ("estimate", "expected"),
    [
        (3.1418, 3),
        (3.14159, 5),
        (3.2, 0),
        (3.0, 0),
        (2.99, 0),
        (math.pi, 15),
        (math.nan, 0),
    ],
)
def test_matching_decimals(estimate, expected):
    assert matching_decimals(estimate) == expected


@pytest.mark.parametrize(
    ("decimals", "window"),
    [(0, (3.0, 4.0)), (2, (3.14, 3.15)), (4, (3.1415, 3.1416))],
)
def test_decimal_window(decimals, window):
    assert decimal_window(decimals) == pytest.approx(window)


def test_decimal_window_rejects_out_of_range():
    with pytest.raises(ValueError):
        decimal_window(16)


def test_samples_for_decimals_grows_hundredfold():
    # N = (1.96 · 1.642 / 0.005)² ≈ 414,000 for two decimals.
    assert samples_for_decimals(2) == pytest.approx(414_000, rel=1e-3)
    assert samples_for_decimals(4) / samples_for_decimals(3) == pytest.approx(100)


def test_estimate_statistics():
    estimate = Estimate(inside=7854, total=10_000)

    assert estimate.pi == pytest.approx(3.1416)
    assert estimate.standard_error == pytest.approx(4 * math.sqrt(0.7854 * 0.2146 / 10_000))
    assert estimate.interval95[0] == pytest.approx(estimate.pi - 1.96 * estimate.standard_error, rel=1e-4)
    assert estimate.matching_decimals == 3  # 3.1416 vs 3.14159…


def test_empty_estimate():
    estimate = Estimate()

    assert math.isnan(estimate.pi)
    assert math.isnan(estimate.standard_error)
    assert estimate.matching_decimals == 0


def test_command_line():
    result = subprocess.run(
        [sys.executable, "-m", "montecarlo_pi", "100K", "--seed", "1"],
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
    )

    assert "points     100,000" in result.stdout
    assert "seed       1" in result.stdout
