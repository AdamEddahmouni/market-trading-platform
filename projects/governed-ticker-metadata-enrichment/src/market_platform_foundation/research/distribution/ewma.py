"""EWMA volatility forecasting baseline."""

from __future__ import annotations

import math
from typing import Sequence

from .realized_vol import close_to_close_returns


def ewma_variance(returns: Sequence[float], *, lambda_: float = 0.94) -> float | None:
    if not returns:
        return None
    variance = returns[0] ** 2
    for value in returns[1:]:
        variance = lambda_ * variance + (1 - lambda_) * (value ** 2)
    return variance


def ewma_volatility_forecast(closes: Sequence[float], *, lambda_: float = 0.94) -> float | None:
    returns = close_to_close_returns(closes)
    variance = ewma_variance(returns, lambda_=lambda_)
    if variance is None or variance <= 0:
        return None
    return round(math.sqrt(variance) * math.sqrt(252), 6)


__all__ = ["ewma_variance", "ewma_volatility_forecast"]
