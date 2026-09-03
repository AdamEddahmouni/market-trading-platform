"""Risk-neutral (Q) distribution forecast contracts — Options O3."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class RiskNeutralHorizonForecast:
    """Single-horizon risk-neutral distribution summary."""

    horizon_days: int
    mean_return: float
    variance: float
    upside_tail_probability: float
    downside_tail_probability: float
    skew: float


@dataclass(frozen=True, slots=True)
class RiskNeutralDistributionForecast:
    """Risk-neutral implied distribution from options surface (lane-owned Q)."""

    symbol: str
    as_of_time: str
    model_version: str
    underlying_price: float | None
    vol_implied_annualized: float | None
    horizons: tuple[RiskNeutralHorizonForecast, ...] = field(default_factory=tuple)
    methodology_tags: tuple[str, ...] = field(default_factory=tuple)
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    confidence: str = "LOW"
    provenance_ref: str = ""


def risk_neutral_horizon_to_dict(horizon: RiskNeutralHorizonForecast) -> dict[str, Any]:
    return {
        "horizon_days": horizon.horizon_days,
        "mean_return": horizon.mean_return,
        "variance": horizon.variance,
        "upside_tail_probability": horizon.upside_tail_probability,
        "downside_tail_probability": horizon.downside_tail_probability,
        "skew": horizon.skew,
    }


def risk_neutral_distribution_to_dict(forecast: RiskNeutralDistributionForecast) -> dict[str, Any]:
    return {
        "symbol": forecast.symbol,
        "as_of_time": forecast.as_of_time,
        "model_version": forecast.model_version,
        "underlying_price": forecast.underlying_price,
        "vol_implied_annualized": forecast.vol_implied_annualized,
        "horizons": [risk_neutral_horizon_to_dict(h) for h in forecast.horizons],
        "methodology_tags": list(forecast.methodology_tags),
        "quality_flags": list(forecast.quality_flags),
        "confidence": forecast.confidence,
        "provenance_ref": forecast.provenance_ref,
    }


__all__ = [
    "RiskNeutralDistributionForecast",
    "RiskNeutralHorizonForecast",
    "risk_neutral_distribution_to_dict",
    "risk_neutral_horizon_to_dict",
]
