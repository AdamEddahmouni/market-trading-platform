"""Reproducible BSM Greeks (O2)."""

from __future__ import annotations

import math
from typing import Literal

from .iv import _norm_cdf, _norm_pdf

CallPut = Literal["call", "put"]
GREEKS_VERSION = "bsm_greeks_v1"


def bsm_greeks(
    spot: float,
    strike: float,
    time_years: float,
    rate: float,
    volatility: float,
    call_put: CallPut,
) -> dict[str, float | None]:
    if spot <= 0 or strike <= 0 or time_years <= 0 or volatility <= 0:
        return {
            "delta": None,
            "gamma": None,
            "vega": None,
            "theta": None,
            "version": GREEKS_VERSION,
        }
    sqrt_t = math.sqrt(time_years)
    d1 = (math.log(spot / strike) + (rate + 0.5 * volatility ** 2) * time_years) / (
        volatility * sqrt_t
    )
    d2 = d1 - volatility * sqrt_t
    gamma = _norm_pdf(d1) / (spot * volatility * sqrt_t)
    vega = spot * _norm_pdf(d1) * sqrt_t / 100.0
    if call_put == "call":
        delta = _norm_cdf(d1)
        theta = (
            -spot * _norm_pdf(d1) * volatility / (2 * sqrt_t)
            - rate * strike * math.exp(-rate * time_years) * _norm_cdf(d2)
        ) / 365.0
    else:
        delta = _norm_cdf(d1) - 1.0
        theta = (
            -spot * _norm_pdf(d1) * volatility / (2 * sqrt_t)
            + rate * strike * math.exp(-rate * time_years) * _norm_cdf(-d2)
        ) / 365.0
    return {
        "delta": round(delta, 8),
        "gamma": round(gamma, 8),
        "vega": round(vega, 8),
        "theta": round(theta, 8),
        "version": GREEKS_VERSION,
    }


__all__ = ["GREEKS_VERSION", "bsm_greeks"]
