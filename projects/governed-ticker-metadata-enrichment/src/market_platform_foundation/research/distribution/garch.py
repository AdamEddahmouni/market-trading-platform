"""GARCH(1,1) volatility baseline — stdlib implementation for research baselines."""

from __future__ import annotations

import math
from typing import Sequence

from .realized_vol import close_to_close_returns


def garch11_forecast(
    closes: Sequence[float],
    *,
    omega: float = 1e-6,
    alpha: float = 0.05,
    beta: float = 0.90,
) -> float | None:
    returns = close_to_close_returns(closes)
    if len(returns) < 5:
        return None
    variance = returns[0] ** 2
    for value in returns[1:]:
        variance = omega + alpha * (value ** 2) + beta * variance
    if variance <= 0:
        return None
    return round(math.sqrt(variance) * math.sqrt(252), 6)


__all__ = ["garch11_forecast"]
