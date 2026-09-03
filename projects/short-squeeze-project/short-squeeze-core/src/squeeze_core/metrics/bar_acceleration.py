"""Bar acceleration metric: rate-of-change of bar-level returns.

Measures whether the most recent completed bar's percentage change is accelerating
or decelerating relative to the preceding bars.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def bar_acceleration(
    bar_returns: list[float],
    *,
    window: int = 5,
) -> float | None:
    """Compute acceleration as the excess return of the most recent bar.

    Returns the difference between the most recent bar's return and the
    trimmed mean of the preceding bar returns, in percentage points.

    Returns ``None`` when fewer than 2 bars are available.
    """
    if len(bar_returns) < 2:
        return None

    recent = bar_returns[-1]
    prior = bar_returns[-min(len(bar_returns), window + 1):-1]

    if not prior:
        return None

    # Trimmed mean: drop highest and lowest if >= 4 prior bars
    sorted_prior = sorted(prior)
    if len(sorted_prior) >= 4:
        sorted_prior = sorted_prior[1:-1]

    avg = sum(sorted_prior) / len(sorted_prior)
    return round(recent - avg, 6)


@dataclass(frozen=True, slots=True)
class BarAccelerationResult:
    value: float | None
    bar_count: int
    window: int
    unit: str = "PERCENTAGE_POINTS"


def compute_bar_acceleration(
    bars: list[dict[str, Any]],
    *,
    window: int = 5,
) -> BarAccelerationResult:
    bar_returns: list[float] = []
    for bar in bars:
        open_price = bar.get("open")
        close_price = bar.get("close")
        if open_price is None or close_price is None or float(open_price) == 0:
            continue
        pct = (float(close_price) - float(open_price)) / float(open_price) * 100.0
        bar_returns.append(pct)

    return BarAccelerationResult(
        value=bar_acceleration(bar_returns, window=window),
        bar_count=len(bar_returns),
        window=window,
    )


__all__ = [
    "BarAccelerationResult",
    "bar_acceleration",
    "compute_bar_acceleration",
]
