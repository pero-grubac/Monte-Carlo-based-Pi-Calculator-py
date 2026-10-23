import math

import numpy as np
import pytest

from montecarlo_pi import Simulation, convergence, estimate_pi
from montecarlo_pi.simulation import BLOCK


def test_estimate_is_close_to_pi():
    estimate = estimate_pi(2_000_000, seed=42)

    # Within 5 standard errors: fails by chance for less than one seed in a million.
    assert abs(estimate.error) < 5 * estimate.standard_error
    assert estimate.total == 2_000_000


def test_same_seed_gives_same_result():
    assert estimate_pi(100_000, seed=7) == estimate_pi(100_000, seed=7)


def test_different_seeds_give_different_results():
    assert estimate_pi(100_000, seed=1) != estimate_pi(100_000, seed=2)


def test_random_seed_is_recorded():
    simulation = Simulation()
    simulation.run(1000)

    assert estimate_pi(1000, seed=simulation.seed) == simulation.estimate


@pytest.mark.parametrize(
    "batches",
    [
        [3_000_000],
        [1, 999, 500_000, 2_497_000, 2_000],
        [BLOCK, BLOCK, 3_000_000 - 2 * BLOCK],
        [BLOCK - 1, 2, 3_000_000 - BLOCK - 1],
    ],
)
def test_result_does_not_depend_on_how_work_is_split(batches):
    simulation = Simulation(99)
    for batch in batches:
        simulation.run(batch)

    assert simulation.estimate == estimate_pi(3_000_000, seed=99)


def test_capture_returns_first_points():
    simulation = Simulation(5)

    points = simulation.run(50, capture=100)

    assert len(points.x) == 50
    assert points.inside.sum() == simulation.estimate.inside
    assert np.all(np.abs(points.x) <= 1)
    assert np.array_equal(points.inside, points.x**2 + points.y**2 <= 1)


def test_capture_across_blocks():
    points = Simulation(5).run(BLOCK + 10, capture=BLOCK + 5)

    assert len(points.x) == BLOCK + 5


def test_run_until_decimals_stops_inside_window():
    simulation = Simulation(3)

    matched, _ = simulation.run_until_decimals(2, budget=10_000_000)

    assert matched
    assert 3.14 <= simulation.estimate.pi < 3.15
    assert simulation.estimate.matching_decimals >= 2


def test_run_until_decimals_stops_at_first_matching_point():
    simulation = Simulation(3)
    simulation.run_until_decimals(2, budget=10_000_000)
    total = simulation.estimate.total

    # Replaying point by point, no shorter prefix may already be in the window.
    points = Simulation(3).run(total, capture=total)
    running = 4 * np.cumsum(points.inside) / np.arange(1, total + 1)
    first = int(np.argmax((running >= 3.14) & (running < 3.15))) + 1

    assert first == total


def test_run_until_decimals_continues_the_same_stream():
    simulation = Simulation(8)
    simulation.run_until_decimals(12, budget=1_500_000)
    simulation.run(600_000)

    assert simulation.estimate == estimate_pi(2_100_000, seed=8)


def test_run_until_decimals_after_a_match_continues_exactly():
    simulation = Simulation(3)
    simulation.run_until_decimals(2, budget=10_000_000)
    matched_at = simulation.estimate.total
    simulation.run(1000)

    assert simulation.estimate == estimate_pi(matched_at + 1000, seed=3)


def test_run_until_decimals_respects_budget():
    simulation = Simulation(1)

    matched, points = simulation.run_until_decimals(9, budget=1000, capture=10)

    assert not matched
    assert simulation.estimate.total == 1000
    assert len(points.x) == 10


def test_run_rejects_negative_count():
    with pytest.raises(ValueError):
        Simulation(1).run(-1)


def test_convergence_is_log_spaced_and_ends_at_n():
    counts, estimates = convergence(100_000, seed=1, checkpoints=50)

    assert counts[0] == 1
    assert counts[-1] == 100_000
    assert np.all(np.diff(counts) > 0)
    assert estimates[-1] == estimate_pi(100_000, seed=1).pi
    assert abs(estimates[-1] - math.pi) < 0.05
