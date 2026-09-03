"""F9 relative-value spreads — calendar spread objects and baseline signals."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from ..contracts.futures import FuturesCurveSnapshot
from ..contracts.futures_quality import FuturesQualityFlag
from ..providers.contracts import ProviderResult

RV_VERSION = "futures_relative_value_v1"


def compute_calendar_spread(front_price: Decimal, back_price: Decimal) -> Decimal:
    return back_price - front_price


def spread_zscore(spread: float, history: list[float]) -> float | None:
    if not history:
        return None
    mean = sum(history) / len(history)
    variance = sum((value - mean) ** 2 for value in history) / len(history)
    if variance <= 0:
        return 0.0
    std = variance ** 0.5
    if std == 0:
        return 0.0
    return (spread - mean) / std


def spread_momentum_label(current: float, prior: float | None) -> str:
    if prior is None:
        return "UNKNOWN"
    delta = current - prior
    if delta > 0.25:
        return "WIDENING"
    if delta < -0.25:
        return "NARROWING"
    return "STABLE"


def relative_value_snapshot(
    curve: FuturesCurveSnapshot | None,
    *,
    spread_history: list[float] | None = None,
) -> dict[str, Any] | None:
    if curve is None or len(curve.prices) < 2:
        return None
    front_price = float(curve.prices[0])
    back_price = float(curve.prices[1])
    spread = back_price - front_price
    history = list(spread_history or [])
    z = spread_zscore(spread, history)
    prior = history[-1] if history else None
    hedge_ratio = 1.0
    return {
        "spread_type": "CALENDAR",
        "front_contract_id": curve.contract_ids[0],
        "back_contract_id": curve.contract_ids[1],
        "front_price": front_price,
        "back_price": back_price,
        "spread_value": spread,
        "hedge_ratio": hedge_ratio,
        "spread_zscore": z,
        "spread_momentum": spread_momentum_label(spread, prior),
        "curve_regime": "contango" if spread > 0 else "backwardation" if spread < 0 else "flat",
        "rv_version": RV_VERSION,
        "observation_time": curve.observation_time,
    }


def relative_value_payload(
    curve: FuturesCurveSnapshot | None,
    chain_result: ProviderResult | None,
    *,
    decision_time: int,
) -> dict[str, Any]:
    del decision_time
    flags: list[str] = []
    spread_history: list[float] = []
    if chain_result and chain_result.status == "available":
        for row in chain_result.events:
            if not isinstance(row, dict):
                continue
            history = row.get("spread_history")
            if isinstance(history, list):
                for item in history:
                    if isinstance(item, (int, float)):
                        spread_history.append(float(item))
    snapshot = relative_value_snapshot(curve, spread_history=spread_history or None)
    if snapshot is None:
        flags.append(FuturesQualityFlag.CURVE_SPARSE.value)
        return {
            "available": False,
            "futures_relative_value_available": False,
            "relative_value_snapshot": None,
            "quality_flags": flags,
        }
    return {
        "available": True,
        "futures_relative_value_available": True,
        "relative_value_snapshot": snapshot,
        "quality_flags": flags,
    }


__all__ = [
    "RV_VERSION",
    "compute_calendar_spread",
    "relative_value_payload",
    "relative_value_snapshot",
    "spread_momentum_label",
    "spread_zscore",
]
