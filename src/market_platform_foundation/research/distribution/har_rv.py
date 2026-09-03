"""HAR-RV volatility forecasting baseline."""

from __future__ import annotations

import math
from typing import Sequence

from .realized_vol import close_to_close_returns, realized_volatility_close_to_close


def _window_rv(closes: Sequence[float]) -> float:
    rv = realized_volatility_close_to_close(closes)
    return rv if rv is not None else 0.0


def har_rv_forecast(
    closes: Sequence[float],
    *,
    daily_window: int = 5,
    weekly_window: int = 22,
    monthly_window: int = 66,
) -> float | None:
    """Simple HAR-RV using equal-weighted component averages (research baseline)."""
    if len(closes) < monthly_window + 1:
        return None
    daily = _window_rv(closes[-daily_window - 1:])
    weekly = _window_rv(closes[-weekly_window - 1:])
    monthly = _window_rv(closes[-monthly_window - 1:])
    forecast = 0.3 * daily + 0.4 * weekly + 0.3 * monthly
    if forecast <= 0:
        return None
    return round(forecast, 6)


__all__ = ["har_rv_forecast"]
