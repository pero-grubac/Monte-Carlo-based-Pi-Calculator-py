"""Estimate π by throwing random points at a square and counting those that land in the circle."""

from .estimate import (
    PI_DIGITS,
    SINGLE_SAMPLE_DEVIATION,
    Z95,
    Estimate,
    decimal_window,
    matching_decimals,
    samples_for_decimals,
    samples_for_half_width,
)
from .simulation import Points, Simulation, convergence, estimate_pi

__all__ = [
    "PI_DIGITS",
    "SINGLE_SAMPLE_DEVIATION",
    "Z95",
    "Estimate",
    "Points",
    "Simulation",
    "convergence",
    "decimal_window",
    "estimate_pi",
    "matching_decimals",
    "samples_for_decimals",
    "samples_for_half_width",
]

__version__ = "2.0.0"
