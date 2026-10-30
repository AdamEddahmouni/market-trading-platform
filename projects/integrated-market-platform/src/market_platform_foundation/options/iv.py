"""Options lane — IV engine (O2)."""

from __future__ import annotations

import math
from typing import Literal

CallPut = Literal["call", "put"]
# v2 (2026-10-29, AUD-036/038): European discounted-strike admission bounds and a bracketed Newton solver.
# v1 compared against undiscounted spot intrinsic and ran unguarded Newton from 0.3.
# v3 preserves the requested price tolerance when eight-decimal IV rounding would exceed it.
IV_SOLVER_VERSION = "bsm_bracketed_newton_v3"
# Above this volatility a price is treated as indistinguishable from the upper no-arbitrage bound.
_MAX_VOLATILITY = 1000.0


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
    """European BSM implied volatility — fail-closed on invalid inputs.

    A price is admitted only strictly inside the European no-arbitrage bounds, which use the discounted strike:
    call ``max(S - K e^{-rT}, 0) < C < S``, put ``max(K e^{-rT} - S, 0) < P < K e^{-rT}`` (any sign of ``r``).
    The BSM price rises monotonically in volatility between those bounds, so the root is bracketed and found by
    Newton steps that fall back to bisection whenever a step leaves the bracket. ``None`` means out of domain or
    no volatility reprices within ``tolerance`` (price units) in ``max_iter`` iterations.
    """
    values = (market_price, spot, strike, time_years, rate)
    if not all(math.isfinite(value) for value in values):
        return None
    if market_price <= 0 or spot <= 0 or strike <= 0 or time_years <= 0:
        return None
    discounted_strike = strike * math.exp(-rate * time_years)
    if call_put == "call":
        lower, upper = max(spot - discounted_strike, 0.0), spot
    else:
        lower, upper = max(discounted_strike - spot, 0.0), discounted_strike
    if not lower < market_price < upper:
        return None

    def price_at(sigma: float) -> float:
        return bsm_price(spot, strike, time_years, rate, sigma, call_put)

    # Bracket [lo, hi]: price(lo) < market_price <= price(hi). price(0+) is the lower bound.
    lo, hi = 0.0, 1.0
    while price_at(hi) < market_price:
        lo, hi = hi, hi * 2.0
        if hi > _MAX_VOLATILITY:
            return None
    sqrt_t = math.sqrt(time_years)
    sigma = 0.3 if lo < 0.3 < hi else 0.5 * (lo + hi)
    for _ in range(max_iter):
        diff = price_at(sigma) - market_price
        if abs(diff) < tolerance:
            rounded = round(sigma, 8)
            # Rounding can move a converged price back outside the requested tolerance.
            return rounded if abs(price_at(rounded) - market_price) < tolerance else sigma
        if diff < 0:
            lo = sigma
        else:
            hi = sigma
        d1 = (math.log(spot / strike) + (rate + 0.5 * sigma ** 2) * time_years) / (
            sigma * sqrt_t
        )
        vega = spot * _norm_pdf(d1) * sqrt_t
        step = sigma - diff / vega if vega > 1e-12 else lo - 1.0
        sigma = step if lo < step < hi else 0.5 * (lo + hi)
        if hi - lo <= 1e-14 * max(1.0, hi):
            break
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
