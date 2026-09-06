"""HAR-RV volatility forecasting baseline."""

from __future__ import annotations

import math
from typing import Sequence

from .realized_vol import realized_volatility_close_to_close

HAR_DAILY_WEIGHT = 0.3
HAR_WEEKLY_WEIGHT = 0.4
HAR_MONTHLY_WEIGHT = 0.3
HAR_DAILY_WINDOW = 5
HAR_WEEKLY_WINDOW = 22
HAR_MONTHLY_WINDOW = 66


def _window_rv(closes: Sequence[float]) -> float:
    rv = realized_volatility_close_to_close(closes)
    return rv if rv is not None else 0.0


def har_rv_forecast(
    closes: Sequence[float],
    *,
    daily_window: int = HAR_DAILY_WINDOW,
    weekly_window: int = HAR_WEEKLY_WINDOW,
    monthly_window: int = HAR_MONTHLY_WINDOW,
) -> float | None:
    """Simple HAR-RV using equal-weighted component averages (research baseline)."""
    if len(closes) < monthly_window + 1:
        return None
    daily = _window_rv(closes[-daily_window - 1:])
    weekly = _window_rv(closes[-weekly_window - 1:])
    monthly = _window_rv(closes[-monthly_window - 1:])
    forecast = HAR_DAILY_WEIGHT * daily + HAR_WEEKLY_WEIGHT * weekly + HAR_MONTHLY_WEIGHT * monthly
    if forecast <= 0:
        return None
    return round(forecast, 6)


__all__ = [
    "HAR_DAILY_WEIGHT",
    "HAR_DAILY_WINDOW",
    "HAR_MONTHLY_WEIGHT",
    "HAR_MONTHLY_WINDOW",
    "HAR_WEEKLY_WEIGHT",
    "HAR_WEEKLY_WINDOW",
    "har_rv_forecast",
]
