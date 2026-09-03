"""Options O5 signed flow engine — fail-closed on uncertain direction."""

from __future__ import annotations

from typing import Any

from ..contracts.options_quality import OptionQualityFlag
from .greeks import bsm_greeks

FLOW_VERSION = "options_signed_flow_v1"
DEFAULT_SPOT = 100.0
DEFAULT_RATE = 0.05
DEFAULT_VOL = 0.35


def classify_signed_flow(activity: dict[str, Any]) -> dict[str, Any]:
    """Classify buy/sell initiation from explicit fixture fields only."""
    flow_side = str(activity.get("flow_side", "")).lower()
    open_close = str(activity.get("open_close", activity.get("open_close_label", "unknown"))).lower()
    quality_flags: list[str] = []
    direction: str | None = None
    if flow_side in {"buy", "buy_initiated", "buyer"}:
        direction = "buy_initiated"
    elif flow_side in {"sell", "sell_initiated", "seller"}:
        direction = "sell_initiated"
    else:
        quality_flags.append(OptionQualityFlag.FLOW_DIRECTION_UNCERTAIN.value)
    if open_close in {"", "unknown", "ambiguous"}:
        quality_flags.append(OptionQualityFlag.OPEN_CLOSE_UNKNOWN.value)
    return {
        "direction": direction,
        "open_close": open_close if open_close else "unknown",
        "quality_flags": quality_flags,
        "flow_confirmed": direction is not None,
    }


def abnormal_flow_vs_baseline(
    observed_volume: int,
    baseline_volume: float | None,
) -> dict[str, Any]:
    """Observed minus expected flow — fail-closed without baseline."""
    if baseline_volume is None or baseline_volume <= 0:
        return {"available": False, "reason": "BASELINE_MISSING"}
    abnormal = observed_volume - baseline_volume
    return {
        "available": True,
        "observed_volume": observed_volume,
        "expected_volume": round(baseline_volume, 4),
        "abnormal_volume": round(abnormal, 4),
    }


def aggregate_signed_flow(
    activities: list[dict[str, Any]],
    *,
    spot: float = DEFAULT_SPOT,
) -> dict[str, Any]:
    """Aggregate signed delta/gamma/vega flow equivalents — decomposed, no universal score."""
    buy_volume = 0
    sell_volume = 0
    net_delta_flow = 0.0
    net_gamma_flow = 0.0
    net_vega_flow = 0.0
    confirmed_count = 0
    uncertain_count = 0
    quality_flags: set[str] = set()

    for row in activities:
        if not isinstance(row, dict):
            continue
        classification = classify_signed_flow(row)
        if not classification["flow_confirmed"]:
            uncertain_count += 1
            quality_flags.update(classification["quality_flags"])
            continue
        confirmed_count += 1
        size = int(row.get("size", row.get("volume", 0)) or 0)
        if classification["direction"] == "buy_initiated":
            buy_volume += size
            sign = 1.0
        else:
            sell_volume += size
            sign = -1.0
        strike = float(row.get("strike", spot))
        option_type = str(row.get("option_type", "call")).lower()
        dte = int(row.get("dte", row.get("days_to_expiration", 30)) or 30)
        time_years = max(dte / 365.0, 1 / 365.0)
        greeks = bsm_greeks(
            spot,
            strike,
            time_years,
            DEFAULT_RATE,
            DEFAULT_VOL,
            "call" if option_type == "call" else "put",
        )
        delta = greeks.get("delta")
        gamma = greeks.get("gamma")
        vega = greeks.get("vega")
        multiplier = float(row.get("multiplier", 100))
        if isinstance(delta, (int, float)):
            net_delta_flow += sign * size * float(delta) * multiplier
        if isinstance(gamma, (int, float)):
            net_gamma_flow += sign * size * float(gamma) * multiplier
        if isinstance(vega, (int, float)):
            net_vega_flow += sign * size * float(vega) * multiplier

    return {
        "buy_initiated_volume": buy_volume,
        "sell_initiated_volume": sell_volume,
        "net_delta_flow": round(net_delta_flow, 4),
        "net_gamma_flow": round(net_gamma_flow, 6),
        "net_vega_flow": round(net_vega_flow, 4),
        "confirmed_trade_count": confirmed_count,
        "uncertain_trade_count": uncertain_count,
        "quality_flags": sorted(quality_flags),
    }


def _baseline_volume_by_type(activities: list[dict[str, Any]]) -> dict[str, float]:
    buckets: dict[str, list[int]] = {}
    for row in activities:
        if not isinstance(row, dict):
            continue
        option_type = str(row.get("option_type", "call")).lower()
        volume = int(row.get("volume", 0) or 0)
        buckets.setdefault(option_type, []).append(volume)
    return {
        key: sum(values) / len(values)
        for key, values in buckets.items()
        if values
    }


def build_flow_snapshot(
    activities: list[dict[str, Any]],
    *,
    as_of_time: str = "",
) -> dict[str, Any]:
    """Build signed-flow snapshot for workspace — fail-closed when no confirmed direction."""
    if not activities:
        return {
            "available": False,
            "reason": "NO_ACTIVITIES",
            "flow_version": FLOW_VERSION,
        }
    aggregate = aggregate_signed_flow(activities)
    baselines = _baseline_volume_by_type(activities)
    abnormal_rows: list[dict[str, Any]] = []
    for row in activities:
        if not isinstance(row, dict):
            continue
        option_type = str(row.get("option_type", "call")).lower()
        volume = int(row.get("volume", 0) or 0)
        abnormal_rows.append(
            abnormal_flow_vs_baseline(volume, baselines.get(option_type))
        )
    signed_available = aggregate["confirmed_trade_count"] > 0
    dominant_direction: str | None = None
    if signed_available:
        if aggregate["buy_initiated_volume"] > aggregate["sell_initiated_volume"]:
            dominant_direction = "buy_initiated"
        elif aggregate["sell_initiated_volume"] > aggregate["buy_initiated_volume"]:
            dominant_direction = "sell_initiated"
    return {
        "available": True,
        "flow_version": FLOW_VERSION,
        "signed_flow_available": signed_available and dominant_direction is not None,
        "dominant_direction": dominant_direction,
        "as_of_time": as_of_time,
        "aggregate": aggregate,
        "abnormal_flow": abnormal_rows,
        "not_trade_signal": True,
    }


__all__ = [
    "FLOW_VERSION",
    "abnormal_flow_vs_baseline",
    "aggregate_signed_flow",
    "build_flow_snapshot",
    "classify_signed_flow",
]
