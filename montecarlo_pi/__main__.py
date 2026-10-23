"""Command line: ``python -m montecarlo_pi 1e7 --seed 42`` or ``python -m montecarlo_pi --decimals 3``."""

from __future__ import annotations

import argparse
import sys
import time

from .estimate import PI_DIGITS, samples_for_decimals
from .simulation import Simulation


def parse_count(text: str) -> int:
    """Accepts 1000000, 1_000_000, 1e6, 2.5M or 1B."""
    text = text.strip().replace("_", "").replace(",", "")
    scale = {"K": 1e3, "M": 1e6, "B": 1e9}.get(text[-1:].upper(), 1)
    value = float(text[:-1] if scale != 1 else text) * scale
    if value < 1 or value != int(value):
        raise argparse.ArgumentTypeError(f"not a whole number of points: {text}")
    return int(value)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="montecarlo_pi", description="Estimate π with random points.")
    parser.add_argument(
        "points", nargs="?", type=parse_count, default=10_000_000, help="number of points (default 1e7)"
    )
    parser.add_argument("--decimals", type=int, help="instead: draw until this many decimals match")
    parser.add_argument("--seed", type=int, help="repeat a run exactly")
    args = parser.parse_args(argv)

    # The output contains π; a Windows console defaults to a code page without it.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    simulation = Simulation(args.seed)
    start = time.perf_counter()
    if args.decimals is not None:
        matched, _ = simulation.run_until_decimals(args.decimals, budget=10_000_000_000)
        verdict = "matched" if matched else "no match within 10 billion points"
    else:
        simulation.run(args.points)
        verdict = "done"
    seconds = time.perf_counter() - start

    e = simulation.estimate
    low, high = e.interval95
    print(f"estimate   {e.pi:.10f}   ({e.matching_decimals} correct decimals, {verdict})")
    print(f"π          {PI_DIGITS}")
    print(f"error      {e.error:+.2e}   95% interval [{low:.6f}, {high:.6f}]")
    print(
        f"points     {e.total:,} ({e.inside:,} inside) in {seconds:.2f} s ({e.total / max(seconds, 1e-9):,.0f} points/s)"
    )
    if args.decimals is not None:
        print(
            f"for 95% certainty of {args.decimals} decimals you would need about {samples_for_decimals(args.decimals):.1e} points"
        )
    print(f"seed       {simulation.seed}")


if __name__ == "__main__":
    main()
