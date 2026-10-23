"""The estimate of π after a number of points, and facts about its precision."""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal

PI_DIGITS = "3.141592653589793"
"""π to 15 decimals, the precision of a float."""

MAX_DECIMALS = 15

Z95 = 1.959963984540054
"""z for a two-sided 95% interval."""

SINGLE_SAMPLE_DEVIATION = math.sqrt(math.pi * (4 - math.pi))
"""Standard deviation of a single point's contribution, √(π(4 − π)) ≈ 1.642."""


@dataclass(frozen=True)
class Estimate:
    """π ≈ 4 · inside / total, from ``total`` points of which ``inside`` fell in the unit circle."""

    inside: int = 0
    total: int = 0

    @property
    def pi(self) -> float:
        return 4 * self.inside / self.total if self.total else math.nan

    @property
    def error(self) -> float:
        return self.pi - math.pi

    @property
    def standard_error(self) -> float:
        """σ(π̂) = 4 · √(p(1 − p) / N), each point being a Bernoulli trial with p = inside / total."""
        if not self.total:
            return math.nan
        p = self.inside / self.total
        return 4 * math.sqrt(p * (1 - p) / self.total)

    @property
    def interval95(self) -> tuple[float, float]:
        half = Z95 * self.standard_error
        return self.pi - half, self.pi + half

    @property
    def matching_decimals(self) -> int:
        return matching_decimals(self.pi)

    def add(self, inside: int, total: int) -> Estimate:
        return Estimate(self.inside + int(inside), self.total + int(total))


def matching_decimals(estimate: float) -> int:
    """How many leading decimals of ``estimate`` equal those of π, by truncation (3.1418 → 3)."""
    if not math.isfinite(estimate) or math.floor(estimate) != 3:
        return 0

    text = f"{estimate:.{MAX_DECIMALS}f}"
    count = 0
    for ours, theirs in zip(text[2:], PI_DIGITS[2:], strict=True):
        if ours != theirs:
            break
        count += 1
    return count


def decimal_window(decimals: int) -> tuple[float, float]:
    """Estimates whose first ``decimals`` decimals are π's: [3.14, 3.15) for two decimals."""
    if not 0 <= decimals <= MAX_DECIMALS:
        raise ValueError(f"decimals must be between 0 and {MAX_DECIMALS}")

    lower = Decimal(PI_DIGITS[: 2 + decimals].rstrip("."))
    step = Decimal(1).scaleb(-decimals)
    return float(lower), float(lower + step)


def samples_for_half_width(half_width: float) -> float:
    """Points needed for a 95% interval no wider than ± ``half_width``: N = (z · σ₁ / half_width)²."""
    if half_width <= 0:
        raise ValueError("half_width must be positive")
    return (Z95 * SINGLE_SAMPLE_DEVIATION / half_width) ** 2


def samples_for_decimals(decimals: int) -> float:
    """Points needed to be 95% sure of the first ``decimals`` decimals (error below half a unit)."""
    return samples_for_half_width(0.5 * 10.0**-decimals)
