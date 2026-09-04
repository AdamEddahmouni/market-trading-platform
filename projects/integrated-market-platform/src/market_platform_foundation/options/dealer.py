"""Options O6 dealer positioning — OI×gamma proxy with explicit uncertainty."""

from __future__ import annotations

from datetime import date
from typing import Any

from ..contracts.options_quality import OptionQualityFlag
from .greeks import bsm_greeks
from .iv import dual_track_iv
from .surface import infer_underlying_price

DEALER_VERSION = "options_dealer_proxy_v1"
DEALER_METHOD = "OI_GAMMA_PROXY_V1"
DEFAULT_RATE = 0.05
GAMMA_REGIME_THRESHOLD = 1e-6
HEDGING_PRESSURE_SPOT_SCALE = 0.01
GAMMA_AMPLIFICATION_THRESHOLD = 0.5
HEDGING_PRESSURE_THRESHOLD = 1.0

DEALER_ASSUMPTIONS = (
    "Dealers assumed short customer long option open interest (retail-flow convention).",
    "Gamma/delta/vega from internal BSM using mid-price IV — not participant-side positioning.",
    "Open interest treated as customer long; no net positioning by strike bucket.",
)

_BLOCKING_FLAGS = frozenset(
    {
        OptionQualityFlag.IV_INVALID.value,
        OptionQualityFlag.ADJUSTED_DELIVERABLE_UNKNOWN.value,
    }
)


def _normalize_row(row: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    option_type = str(row.get("option_type", row.get("call_put", ""))).lower()
    if option_type not in {"call", "put"}:
        return None
    expiry = row.get("expiry", row.get("expiration"))
    strike_raw = row.get("strike")
    event_time = row.get("event_time")
    if not expiry or strike_raw is None or not event_time:
        return None
    try:
        strike = float(strike_raw)
    except (TypeError, ValueError):
        return None
    bid_raw = row.get("bid")
    ask_raw = row.get("ask")
    bid = float(bid_raw) if bid_raw is not None else 0.0
    ask = float(ask_raw) if ask_raw is not None else 0.0
    open_interest = int(row.get("open_interest", 0) or 0)
    multiplier_raw = row.get("multiplier")
    multiplier = 100.0
    if multiplier_raw is not None:
        try:
            multiplier = float(multiplier_raw)
        except (TypeError, ValueError):
            multiplier = 100.0
    deliverable = row.get("deliverable")
    if isinstance(deliverable, dict):
        shares = deliverable.get("shares_per_contract")
        if shares is not None:
            try:
                multiplier = float(shares)
            except (TypeError, ValueError):
                pass
    quality_flags = row.get("quality_flags") or []
    if isinstance(quality_flags, tuple):
        quality_flags = list(quality_flags)
    underlying_price = row.get("underlying_price")
    spot_hint = float(underlying_price) if isinstance(underlying_price, (int, float)) else None
    return {
        "option_type": option_type,
        "expiry": str(expiry),
        "strike": strike,
        "event_time": str(event_time),
        "bid": bid,
        "ask": ask,
        "open_interest": open_interest,
        "multiplier": multiplier,
        "quality_flags": [str(flag) for flag in quality_flags],
        "underlying_price": spot_hint,
        "provider_iv": row.get("provider_iv"),
    }


def _time_years(event_time: str, expiry: str) -> float | None:
    try:
        event_date = date.fromisoformat(event_time[:10])
        expiry_date = date.fromisoformat(expiry[:10])
    except ValueError:
        return None
    dte = max((expiry_date - event_date).days, 1)
    return dte / 365.0


def estimate_contract_dealer_greeks(
    contract_row: dict[str, Any],
    *,
    spot: float | None = None,
    rate: float = DEFAULT_RATE,
) -> dict[str, Any]:
    """Per-contract dealer greek proxy — fail-closed on missing OI or invalid IV."""
    normalized = _normalize_row(contract_row)
    if normalized is None:
        return {"available": False, "reason": "INVALID_CONTRACT_ROW"}
    if normalized["open_interest"] <= 0:
        return {"available": False, "reason": "OPEN_INTEREST_MISSING"}
    if any(flag in _BLOCKING_FLAGS for flag in normalized["quality_flags"]):
        return {"available": False, "reason": "BLOCKING_QUALITY_FLAG"}

    bid = normalized["bid"]
    ask = normalized["ask"]
    if bid <= 0 or ask <= 0:
        return {"available": False, "reason": "NO_TWO_SIDED_MARKET"}
    mid = (bid + ask) / 2.0
    strike = normalized["strike"]
    option_type = normalized["option_type"]
    call_put = "call" if option_type == "call" else "put"
    time_years = _time_years(normalized["event_time"], normalized["expiry"])
    if time_years is None:
        return {"available": False, "reason": "INVALID_DATES"}

    effective_spot = spot
    if effective_spot is None or effective_spot <= 0:
        if normalized["underlying_price"] is not None and normalized["underlying_price"] > 0:
            effective_spot = normalized["underlying_price"]
        else:
            effective_spot = infer_underlying_price(normalized, strike, call_put)

    provider_iv_raw = normalized.get("provider_iv")
    provider_iv = float(provider_iv_raw) if isinstance(provider_iv_raw, (int, float)) else None
    iv_track = dual_track_iv(
        market_price=mid,
        spot=effective_spot,
        strike=strike,
        time_years=time_years,
        rate=rate,
        call_put=call_put,
        provider_iv=provider_iv,
    )
    if iv_track.get("iv_invalid"):
        return {"available": False, "reason": "IV_INVALID"}

    volatility = iv_track.get("internal_iv") or iv_track.get("provider_iv")
    if not isinstance(volatility, (int, float)) or volatility <= 0:
        return {"available": False, "reason": "IV_INVALID"}

    greeks = bsm_greeks(effective_spot, strike, time_years, rate, float(volatility), call_put)
    delta = greeks.get("delta")
    gamma = greeks.get("gamma")
    vega = greeks.get("vega")
    if not all(isinstance(value, (int, float)) for value in (delta, gamma, vega)):
        return {"available": False, "reason": "GREEKS_UNAVAILABLE"}

    oi = normalized["open_interest"]
    multiplier = normalized["multiplier"]
    dealer_delta = -oi * float(delta) * multiplier
    dealer_gamma = -oi * float(gamma) * multiplier
    dealer_vega = -oi * float(vega) * multiplier

    return {
        "available": True,
        "strike": strike,
        "option_type": option_type,
        "open_interest": oi,
        "estimated_dealer_delta": round(dealer_delta, 4),
        "estimated_dealer_gamma": round(dealer_gamma, 6),
        "estimated_dealer_vega": round(dealer_vega, 4),
        "spot_used": round(effective_spot, 4),
        "method": DEALER_METHOD,
    }


def _gamma_flip_estimate(per_contract: list[dict[str, Any]]) -> float | None:
    if len(per_contract) < 2:
        return None
    by_strike: dict[float, float] = {}
    for row in per_contract:
        strike = row.get("strike")
        gamma = row.get("estimated_dealer_gamma")
        if isinstance(strike, (int, float)) and isinstance(gamma, (int, float)):
            by_strike[float(strike)] = by_strike.get(float(strike), 0.0) + float(gamma)
    if len(by_strike) < 2:
        return None
    strikes = sorted(by_strike)
    cumulative = 0.0
    previous_strike = strikes[0]
    previous_cumulative = by_strike[previous_strike]
    for strike in strikes[1:]:
        cumulative = previous_cumulative + by_strike[strike]
        if previous_cumulative == 0.0 or cumulative == 0.0:
            previous_strike = strike
            previous_cumulative = cumulative
            continue
        if (previous_cumulative < 0 < cumulative) or (previous_cumulative > 0 > cumulative):
            return round((previous_strike + strike) / 2.0, 4)
        previous_strike = strike
        previous_cumulative = cumulative
    return None


def _gamma_regime(net_gamma: float) -> str:
    if net_gamma < -GAMMA_REGIME_THRESHOLD:
        return "negative_gamma"
    if net_gamma > GAMMA_REGIME_THRESHOLD:
        return "positive_gamma"
    return "neutral"


def aggregate_dealer_exposure(
    contracts: list[dict[str, Any]],
    *,
    spot: float | None = None,
    as_of_time: str = "",
    rate: float = DEFAULT_RATE,
) -> dict[str, Any]:
    """Aggregate dealer exposure across contracts — fail-closed when no OI-backed rows."""
    per_contract: list[dict[str, Any]] = []
    quality_flags: set[str] = set()
    spot_used: float | None = None

    for row in contracts:
        if not isinstance(row, dict):
            continue
        estimate = estimate_contract_dealer_greeks(row, spot=spot, rate=rate)
        if not estimate.get("available"):
            continue
        per_contract.append(estimate)
        row_spot = estimate.get("spot_used")
        if isinstance(row_spot, (int, float)) and row_spot > 0:
            spot_used = float(row_spot)

    if not per_contract:
        return {
            "available": False,
            "reason": "NO_OI_BACKED_CONTRACTS",
            "quality_flags": [OptionQualityFlag.DEALER_POSITION_UNKNOWN.value],
            "method": DEALER_METHOD,
            "assumptions": list(DEALER_ASSUMPTIONS),
            "confidence": "LOW",
            "as_of_time": as_of_time,
            "dealer_version": DEALER_VERSION,
        }

    net_delta = sum(float(row["estimated_dealer_delta"]) for row in per_contract)
    net_gamma = sum(float(row["estimated_dealer_gamma"]) for row in per_contract)
    net_vega = sum(float(row["estimated_dealer_vega"]) for row in per_contract)
    effective_spot = spot if spot is not None and spot > 0 else spot_used or 1.0
    hedging_pressure = abs(net_gamma) * effective_spot * HEDGING_PRESSURE_SPOT_SCALE
    regime = _gamma_regime(net_gamma)

    return {
        "available": True,
        "as_of_time": as_of_time,
        "dealer_version": DEALER_VERSION,
        "method": DEALER_METHOD,
        "assumptions": list(DEALER_ASSUMPTIONS),
        "confidence": "LOW",
        "estimated_dealer_delta": round(net_delta, 4),
        "estimated_dealer_gamma": round(net_gamma, 6),
        "estimated_dealer_vega": round(net_vega, 4),
        "gamma_regime": regime,
        "hedging_pressure_estimate": round(hedging_pressure, 4),
        "gamma_flip_estimate": _gamma_flip_estimate(per_contract),
        "contract_count": len(contracts),
        "oi_backed_contract_count": len(per_contract),
        "spot_used": round(effective_spot, 4),
        "quality_flags": sorted(quality_flags),
        "not_trade_signal": True,
    }


def build_dealer_snapshot(
    source_rows: list[dict[str, Any]],
    *,
    as_of_time: str = "",
    spot: float | None = None,
) -> dict[str, Any]:
    """Build workspace dealer snapshot from activities or canonical chain contracts."""
    if not source_rows:
        return {
            "available": False,
            "reason": "NO_SOURCE_ROWS",
            "quality_flags": [OptionQualityFlag.DEALER_POSITION_UNKNOWN.value],
            "method": DEALER_METHOD,
            "assumptions": list(DEALER_ASSUMPTIONS),
            "confidence": "LOW",
            "dealer_version": DEALER_VERSION,
        }
    return aggregate_dealer_exposure(source_rows, spot=spot, as_of_time=as_of_time)


__all__ = [
    "DEALER_ASSUMPTIONS",
    "DEALER_METHOD",
    "DEALER_VERSION",
    "GAMMA_AMPLIFICATION_THRESHOLD",
    "HEDGING_PRESSURE_THRESHOLD",
    "aggregate_dealer_exposure",
    "build_dealer_snapshot",
    "estimate_contract_dealer_greeks",
]
