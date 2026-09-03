"""Multi-horizon physical return distribution forecasts from vol baselines."""

from __future__ import annotations

import math
from typing import Literal, Sequence

from ...contracts.physical_distribution import (
    HorizonForecast,
    PhysicalDistributionForecast,
    VolatilityModel,
)
from .ewma import ewma_volatility_forecast
from .events import count_recent_jumps, event_window_active
from .garch import garch11_forecast
from .har_rv import har_rv_forecast
from .realized_vol import close_to_close_returns, realized_volatility_close_to_close

MODEL_VERSION = "physical_p_gaussian_v1"
DEFAULT_HORIZONS = (1, 5, 10)
QUANTILE_KEYS = ("Q01", "Q05", "Q50", "Q95", "Q99")
QUANTILE_Z = {
    "Q01": -2.326,
    "Q05": -1.645,
    "Q50": 0.0,
    "Q95": 1.645,
    "Q99": 2.326,
}


def _vol_forecast_for_model(
    closes: Sequence[float],
    model: VolatilityModel,
) -> float | None:
    if model == "ewma":
        return ewma_volatility_forecast(closes)
    if model == "garch":
        return garch11_forecast(closes)
    return har_rv_forecast(closes)


def _horizon_forecast(
    vol_annualized: float,
    horizon_days: int,
) -> HorizonForecast:
    """Gaussian baseline: scale vol by sqrt(horizon/252), zero mean."""
    daily_var = (vol_annualized / math.sqrt(252)) ** 2
    horizon_var = daily_var * horizon_days
    horizon_vol = math.sqrt(horizon_var)
    quantiles = {
        key: round(QUANTILE_Z[key] * horizon_vol, 8)
        for key in QUANTILE_KEYS
    }
    upside_tail = _normal_tail_probability(horizon_vol, threshold=0.05)
    downside_tail = _normal_tail_probability(horizon_vol, threshold=-0.05, below=True)
    return HorizonForecast(
        horizon_days=horizon_days,
        mean_return=0.0,
        variance=round(horizon_var, 10),
        quantiles=quantiles,
        upside_tail_probability=upside_tail,
        downside_tail_probability=downside_tail,
        skew=0.0,
    )


def _normal_tail_probability(
    vol: float,
    *,
    threshold: float,
    below: bool = False,
) -> float:
    if vol <= 0:
        return 0.0
    z = threshold / vol
    cdf = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
    if below:
        return round(cdf, 6)
    return round(1.0 - cdf, 6)


def physical_distribution_forecast(
    closes: Sequence[float],
    *,
    symbol: str,
    as_of_time: str,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    model: VolatilityModel = "ewma",
    catalyst_event_times: Sequence[str] | None = None,
    provenance_ref: str = "",
) -> PhysicalDistributionForecast | None:
    """Compose vol baseline into multi-horizon physical P forecast (Gaussian v1)."""
    if len(closes) < 5:
        return None
    vol = _vol_forecast_for_model(closes, model)
    if vol is None or vol <= 0:
        return None
    rv = realized_volatility_close_to_close(closes)
    returns = close_to_close_returns(closes)
    jumps = count_recent_jumps(returns)
    event_active = event_window_active(as_of_time, catalyst_event_times or ())
    confidence = "MODERATE" if len(closes) >= 30 else "LOW"
    if len(closes) >= 60:
        confidence = "HIGH"
    horizon_rows = tuple(_horizon_forecast(vol, h) for h in sorted(set(horizons)))
    return PhysicalDistributionForecast(
        symbol=symbol.upper(),
        as_of_time=as_of_time,
        model=model,
        model_version=MODEL_VERSION,
        realized_vol_close_to_close=rv,
        vol_forecast_annualized=vol,
        horizons=horizon_rows,
        methodology_tags=(
            "gaussian_baseline",
            f"vol_model:{model}",
            "estimator:close_to_close_only",
        ),
        jump_count=jumps,
        event_window_active=event_active,
        confidence=confidence,
        provenance_ref=provenance_ref,
    )


__all__ = [
    "DEFAULT_HORIZONS",
    "MODEL_VERSION",
    "physical_distribution_forecast",
]
