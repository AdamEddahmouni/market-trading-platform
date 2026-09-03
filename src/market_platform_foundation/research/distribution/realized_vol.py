"""Realized volatility estimators — documented, not mixed across estimators."""

from __future__ import annotations

import math
from typing import Sequence


def close_to_close_returns(closes: Sequence[float]) -> list[float]:
    if len(closes) < 2:
        return []
    returns: list[float] = []
    for prev, curr in zip(closes, closes[1:]):
        if prev <= 0 or curr <= 0:
            continue
        returns.append(math.log(curr / prev))
    return returns


def realized_volatility_close_to_close(closes: Sequence[float]) -> float | None:
    """Annualized close-to-close realized volatility from log returns."""
    returns = close_to_close_returns(closes)
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((value - mean) ** 2 for value in returns) / (len(returns) - 1)
    if variance <= 0:
        return 0.0
    return round(math.sqrt(variance) * math.sqrt(252), 6)


def realized_volatility_parkinson(highs: Sequence[float], lows: Sequence[float]) -> float | None:
    """Parkinson high-low volatility estimator."""
    if not highs or not lows or len(highs) != len(lows):
        return None
    terms: list[float] = []
    for high, low in zip(highs, lows):
        if high <= 0 or low <= 0 or low >= high:
            continue
        terms.append((math.log(high / low) ** 2) / (4 * math.log(2)))
    if not terms:
        return None
    variance = sum(terms) / len(terms)
    return round(math.sqrt(variance) * math.sqrt(252), 6)


__all__ = [
    "close_to_close_returns",
    "realized_volatility_close_to_close",
    "realized_volatility_parkinson",
]
