"""Matplotlib figures for the notebook. Needs the ``notebook`` extra (matplotlib)."""

from __future__ import annotations

import math

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from matplotlib.patches import Circle

from .estimate import SINGLE_SAMPLE_DEVIATION, Z95
from .simulation import Points

INSIDE_COLOR = "#2F80ED"
OUTSIDE_COLOR = "#F2994A"


def plot_points(points: Points, ax: Axes | None = None, size: float = 2) -> Axes:
    """The square [−1, 1]² with the unit circle and the points, coloured by where they landed."""
    ax = ax or plt.subplots(figsize=(6, 6))[1]
    ax.scatter(points.x[points.inside], points.y[points.inside], s=size, c=INSIDE_COLOR, linewidths=0, label="inside")
    ax.scatter(
        points.x[~points.inside], points.y[~points.inside], s=size, c=OUTSIDE_COLOR, linewidths=0, label="outside"
    )
    ax.add_patch(Circle((0, 0), 1, fill=False, color="0.3", linewidth=1.2))
    ax.set(xlim=(-1, 1), ylim=(-1, 1), aspect="equal", xticks=[-1, 0, 1], yticks=[-1, 0, 1])
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), ncols=2, markerscale=4, frameon=False)
    return ax


def plot_convergence(counts: np.ndarray, estimates: np.ndarray, ax: Axes | None = None) -> Axes:
    """The estimate against the number of points, inside the 95% band ± 1.96 · σ₁ / √N."""
    ax = ax or plt.subplots(figsize=(8, 4))[1]
    band = Z95 * SINGLE_SAMPLE_DEVIATION / np.sqrt(counts)
    ax.fill_between(counts, math.pi - band, math.pi + band, color="0.85", label="95% of runs")
    ax.axhline(math.pi, color="0.3", linestyle="--", linewidth=1, label="π")
    ax.plot(counts, estimates, color=INSIDE_COLOR, linewidth=1.6, label="this run")
    ax.set_xscale("log")
    ax.set(xlabel="points", ylabel="estimate", ylim=(math.pi - 0.3, math.pi + 0.3))
    ax.legend(loc="upper right")
    return ax
