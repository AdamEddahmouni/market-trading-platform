"""Options lane — IV engine (O2)."""

from __future__ import annotations

import math
from typing import Literal

CallPut = Literal["call", "put"]
IV_SOLVER_VERSION = "bsm_newton_v1"


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def bsm_price(
    spot: float,
    strike: float,
    time_years: float,
    rate: float,
    volatility: float,
    call_put: CallPut,
) -> float:
    if spot <= 0 or strike <= 0 or time_years <= 0 or volatility <= 0:
        return 0.0
    sqrt_t = math.sqrt(time_years)
    d1 = (math.log(spot / strike) + (rate + 0.5 * volatility ** 2) * time_years) / (
        volatility * sqrt_t
    )
    d2 = d1 - volatility * sqrt_t
    if call_put == "call":
        return spot * _norm_cdf(d1) - strike * math.exp(-rate * time_years) * _norm_cdf(d2)
    return strike * math.exp(-rate * time_years) * _norm_cdf(-d2) - spot * _norm_cdf(-d1)


def implied_volatility(
    market_price: float,
    spot: float,
    strike: float,
    time_years: float,
    rate: float,
    call_put: CallPut,
    *,
    max_iter: int = 50,
    tolerance: float = 1e-6,
) -> float | None:
    """Newton-Raphson IV solver — fail-closed on invalid inputs."""
    if market_price <= 0 or spot <= 0 or strike <= 0 or time_years <= 0:
        return None
    intrinsic = max(spot - strike, 0.0) if call_put == "call" else max(strike - spot, 0.0)
    if market_price < intrinsic:
        return None
    sigma = 0.3
    for _ in range(max_iter):
        price = bsm_price(spot, strike, time_years, rate, sigma, call_put)
        diff = price - market_price
        if abs(diff) < tolerance:
            return round(sigma, 8)
        sqrt_t = math.sqrt(time_years)
        d1 = (math.log(spot / strike) + (rate + 0.5 * sigma ** 2) * time_years) / (
            sigma * sqrt_t
        )
        vega = spot * _norm_pdf(d1) * sqrt_t
        if vega <= 1e-12:
            return None
        sigma -= diff / vega
        if sigma <= 0:
            sigma = 0.01
    return None


def dual_track_iv(
    *,
    market_price: float,
    spot: float,
    strike: float,
    time_years: float,
    rate: float,
    call_put: CallPut,
    provider_iv: float | None = None,
) -> dict[str, object]:
    """Dual-track provider_iv + internal_iv with solver version tag."""
    internal = implied_volatility(market_price, spot, strike, time_years, rate, call_put)
    return {
        "internal_iv": internal,
        "provider_iv": provider_iv,
        "solver_version": IV_SOLVER_VERSION,
        "iv_invalid": internal is None,
    }


__all__ = [
    "IV_SOLVER_VERSION",
    "bsm_price",
    "dual_track_iv",
    "implied_volatility",
]
