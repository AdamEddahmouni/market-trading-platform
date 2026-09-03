"""Physical (P) return distribution forecast contracts — SHARED P2."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

VolatilityModel = Literal["ewma", "garch", "har_rv"]


@dataclass(frozen=True, slots=True)
class HorizonForecast:
    """Single-horizon physical distribution summary."""

    horizon_days: int
    mean_return: float
    variance: float
    quantiles: dict[str, float]
    upside_tail_probability: float
    downside_tail_probability: float
    skew: float


@dataclass(frozen=True, slots=True)
class PhysicalDistributionForecast:
    """Multi-horizon physical return distribution forecast (platform-owned P)."""

    symbol: str
    as_of_time: str
    model: VolatilityModel
    model_version: str
    realized_vol_close_to_close: float | None
    vol_forecast_annualized: float | None
    horizons: tuple[HorizonForecast, ...] = field(default_factory=tuple)
    methodology_tags: tuple[str, ...] = field(default_factory=tuple)
    jump_count: int = 0
    event_window_active: bool = False
    confidence: str = "LOW"
    provenance_ref: str = ""


def horizon_forecast_to_dict(horizon: HorizonForecast) -> dict[str, Any]:
    return {
        "horizon_days": horizon.horizon_days,
        "mean_return": horizon.mean_return,
        "variance": horizon.variance,
        "quantiles": dict(horizon.quantiles),
        "upside_tail_probability": horizon.upside_tail_probability,
        "downside_tail_probability": horizon.downside_tail_probability,
        "skew": horizon.skew,
    }


def physical_distribution_to_dict(forecast: PhysicalDistributionForecast) -> dict[str, Any]:
    return {
        "symbol": forecast.symbol,
        "as_of_time": forecast.as_of_time,
        "model": forecast.model,
        "model_version": forecast.model_version,
        "realized_vol_close_to_close": forecast.realized_vol_close_to_close,
        "vol_forecast_annualized": forecast.vol_forecast_annualized,
        "horizons": [horizon_forecast_to_dict(h) for h in forecast.horizons],
        "methodology_tags": list(forecast.methodology_tags),
        "jump_count": forecast.jump_count,
        "event_window_active": forecast.event_window_active,
        "confidence": forecast.confidence,
        "provenance_ref": forecast.provenance_ref,
    }


__all__ = [
    "HorizonForecast",
    "PhysicalDistributionForecast",
    "VolatilityModel",
    "horizon_forecast_to_dict",
    "physical_distribution_to_dict",
]
