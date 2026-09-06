"""GARCH(1,1) volatility baseline — stdlib implementation for research baselines."""

from __future__ import annotations

import math
from typing import Sequence

from .realized_vol import close_to_close_returns

DEFAULT_OMEGA = 1e-6
DEFAULT_ALPHA = 0.05
DEFAULT_BETA = 0.90


def garch11_forecast(
    closes: Sequence[float],
    *,
    omega: float = DEFAULT_OMEGA,
    alpha: float = DEFAULT_ALPHA,
    beta: float = DEFAULT_BETA,
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


__all__ = ["DEFAULT_ALPHA", "DEFAULT_BETA", "DEFAULT_OMEGA", "garch11_forecast"]
