"""Frozen v1 NSS predictor over admitted trade tapes (Run 1).

Constants come only from ``FrozenPredictorConfig``; there are no tuning
knobs by design - a changed constant is a new preregistered run (spec
section 16). Eligibility enforces availability-time causality: a trade
enters a window only if both its event time and its availability time
precede the decision (spec section 5). Unknown-side trades are excluded
from both signed and total volume (conservative denominator); their
count is reported.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_NS = 1_000_000_000


@dataclass(frozen=True)
class FrozenPredictorConfig:
    window_seconds: int = 300
    minimum_trades: int = 10
    band_upper: float = 0.15
    band_lower: float = -0.15
    p_up_clip_low: float = 0.1
    p_up_clip_high: float = 0.9
    stale_input_seconds: int = 60


def eligible_trades(tape: list[dict[str, Any]], *, decision_time_ns: int) -> list[dict[str, Any]]:
    return [
        row
        for row in tape
        if int(row["event_time_ns"]) <= decision_time_ns
        and int(row["available_time_ns"]) <= decision_time_ns
    ]


def reference_price(eligible: list[dict[str, Any]], *, decision_time_ns: int) -> dict[str, Any] | None:
    candidates = [t for t in eligible if int(t["event_time_ns"]) <= decision_time_ns]
    if not candidates:
        return None
    last = max(candidates, key=lambda t: int(t["event_time_ns"]))
    return {
        "price": last["price"],
        "event_time_ns": int(last["event_time_ns"]),
        "trade_id": last.get("trade_id"),
    }


def evaluate_prediction(
    eligible: list[dict[str, Any]],
    *,
    decision_time_ns: int,
    config: FrozenPredictorConfig,
) -> dict[str, Any]:
    if len(eligible) < config.minimum_trades:
        return {"outcome": "ABSTAINED_MODEL", "reason": "INSUFFICIENT_TRADES"}
    window_start_ns = decision_time_ns - config.window_seconds * _NS
    window = [t for t in eligible if window_start_ns < int(t["event_time_ns"]) <= decision_time_ns]
    if not window:
        return {"outcome": "ABSTAINED_MODEL", "reason": "STALE_INPUT"}

    buyer_volume = sum(float(t["quantity"]) for t in window if t["aggressor_side"] == "BUY")
    seller_volume = sum(float(t["quantity"]) for t in window if t["aggressor_side"] == "SELL")
    total_volume = buyer_volume + seller_volume
    if total_volume <= 0:
        return {"outcome": "ABSTAINED_MODEL", "reason": "INSUFFICIENT_TRADES"}

    raw_nss = (buyer_volume - seller_volume) / total_volume
    p_up = min(max(0.5 + 0.5 * raw_nss, config.p_up_clip_low), config.p_up_clip_high)
    if raw_nss >= config.band_upper:
        direction = "UP"
    elif raw_nss <= config.band_lower:
        direction = "DOWN"
    else:
        return {"outcome": "ABSTAINED_MODEL", "reason": "FLAT_BAND"}

    return {
        "outcome": "PREDICTED",
        "direction": direction,
        "raw_nss": raw_nss,
        "p_up": p_up,
        "p_selected": p_up if direction == "UP" else 1.0 - p_up,
        "window_start_ns": window_start_ns,
        "window_end_ns": decision_time_ns,
        "buyer_count": sum(1 for t in window if t["aggressor_side"] == "BUY"),
        "seller_count": sum(1 for t in window if t["aggressor_side"] == "SELL"),
        "unknown_count": sum(1 for t in window if t["aggressor_side"] == "UNKNOWN"),
        "buyer_volume": buyer_volume,
        "seller_volume": seller_volume,
        "total_volume": total_volume,
    }
