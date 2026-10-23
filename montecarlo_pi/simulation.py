"""Throwing random points at the square [−1, 1]², vectorised with NumPy."""

from __future__ import annotations

import secrets
from typing import NamedTuple

import numpy as np

from .estimate import Estimate, decimal_window

BLOCK = 1 << 20
"""Points generated at once; keeps memory flat for any number of points."""


class Points(NamedTuple):
    """Points in [−1, 1]² and whether each fell inside the unit circle."""

    x: np.ndarray
    y: np.ndarray
    inside: np.ndarray

    @staticmethod
    def empty() -> Points:
        return Points(np.empty(0), np.empty(0), np.empty(0, dtype=bool))


class Simulation:
    """
    A run of the experiment with its own random stream.

    Point number *i* always uses draws 2i and 2i + 1 of the seed's PCG64 stream, so a seed gives the
    same result however the points are split into calls, including after :meth:`run_until_decimals`.
    """

    def __init__(self, seed: int | None = None) -> None:
        self.seed = secrets.randbits(63) if seed is None else int(seed)
        self._bit_generator = np.random.PCG64(self.seed)
        self._rng = np.random.Generator(self._bit_generator)
        self.estimate = Estimate()

    def run(self, n: int, capture: int = 0) -> Points:
        """Draws ``n`` more points and returns the first ``capture`` of them, for drawing."""
        if n < 0:
            raise ValueError("n must not be negative")

        captured: list[Points] = []
        wanted = capture
        remaining = n
        while remaining > 0:
            size = min(BLOCK, remaining)
            points = self._draw(size)
            self.estimate = self.estimate.add(np.count_nonzero(points.inside), size)
            if wanted > 0:
                captured.append(Points(*(a[:wanted] for a in points)))
                wanted -= len(captured[-1].x)
            remaining -= size

        return _concat(captured)

    def run_until_decimals(self, decimals: int, budget: int, capture: int = 0) -> tuple[bool, Points]:
        """
        Draws points until the estimate's first ``decimals`` decimals equal π's, or ``budget`` points.

        Stops at exactly the first point after which the estimate is in the window, as if the points
        were drawn one by one. Returns whether it matched, and the first ``capture`` points drawn.
        """
        lower, upper = decimal_window(decimals)
        if self._in_window(self.estimate.inside, self.estimate.total, lower, upper):
            return True, Points.empty()

        captured: list[Points] = []
        drawn = 0
        while drawn < budget:
            size = min(BLOCK, budget - drawn)
            state = self._bit_generator.state
            points = self._draw(size)

            inside_so_far = self.estimate.inside + np.cumsum(points.inside)
            total_so_far = self.estimate.total + np.arange(1, size + 1)
            hits = self._in_window(inside_so_far, total_so_far, lower, upper)
            matched = bool(hits.any())
            used = int(np.argmax(hits)) + 1 if matched else size

            if matched:
                # Give back the draws after the matching point, so the stream continues right after it.
                self._bit_generator.state = state
                self._bit_generator.advance(2 * used)

            if capture > 0:
                captured.append(Points(*(a[: min(capture, used)] for a in points)))
                capture -= len(captured[-1].x)

            self.estimate = self.estimate.add(np.count_nonzero(points.inside[:used]), used)
            drawn += used
            if matched:
                return True, _concat(captured)

        return False, _concat(captured)

    def _draw(self, size: int) -> Points:
        xy = self._rng.random((size, 2)) * 2 - 1
        x, y = xy[:, 0], xy[:, 1]
        return Points(x, y, x * x + y * y <= 1)

    @staticmethod
    def _in_window(inside, total, lower: float, upper: float):
        # lower ≤ 4 · inside / total < upper, without dividing.
        return (total > 0) & (4.0 * inside >= lower * total) & (4.0 * inside < upper * total)


def estimate_pi(n: int, seed: int | None = None) -> Estimate:
    """Estimates π from ``n`` random points."""
    simulation = Simulation(seed)
    simulation.run(n)
    return simulation.estimate


def convergence(n: int, seed: int | None = None, checkpoints: int = 200) -> tuple[np.ndarray, np.ndarray]:
    """
    The estimate after a growing number of points, at ``checkpoints`` log-spaced counts up to ``n``.

    Returns the counts and the estimates at those counts.
    """
    counts = np.unique(np.geomspace(1, n, checkpoints).astype(np.int64))
    simulation = Simulation(seed)
    estimates = np.empty(len(counts))
    for i, count in enumerate(counts):
        simulation.run(int(count) - simulation.estimate.total)
        estimates[i] = simulation.estimate.pi
    return counts, estimates


def _concat(parts: list[Points]) -> Points:
    if not parts:
        return Points.empty()
    return Points(*(np.concatenate(column) for column in zip(*parts, strict=True)))
