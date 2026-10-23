"""Glue between the page's JavaScript and the montecarlo_pi package, running in Pyodide."""

import numpy as np

from montecarlo_pi import Simulation, decimal_window, samples_for_decimals

_simulation: Simulation | None = None


def start(seed=None) -> str:
    """Begins a new run; returns its seed as text (it can be larger than JavaScript's safe integers)."""
    global _simulation
    _simulation = Simulation(None if seed is None else int(seed))
    return str(_simulation.seed)


def step(count: int, capture: int, decimals=None):
    """
    Draws up to ``count`` points (or until ``decimals`` match) and returns the new state:
    (inside, total, π̂, standard error, matching decimals, matched, x/y as float32 bytes, inside flags as bytes).
    """
    if decimals is None:
        points = _simulation.run(int(count), int(capture))
        matched = False
    else:
        matched, points = _simulation.run_until_decimals(int(decimals), int(count), int(capture))

    xy = np.empty(2 * len(points.x), dtype=np.float32)
    xy[0::2] = points.x
    xy[1::2] = points.y

    e = _simulation.estimate
    return (
        e.inside,
        e.total,
        e.pi,
        e.standard_error,
        e.matching_decimals,
        matched,
        xy.tobytes(),
        points.inside.astype(np.uint8).tobytes(),
    )


def window_text(decimals: int) -> str:
    lower, upper = decimal_window(int(decimals))
    return f"[{lower:.{decimals}f}, {upper:.{decimals}f})"


def points_needed(decimals: int) -> float:
    return samples_for_decimals(int(decimals))
