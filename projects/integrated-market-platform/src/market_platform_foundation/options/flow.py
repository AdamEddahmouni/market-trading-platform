"""Options O5 signed flow engine — fail-closed on uncertain direction."""

from __future__ import annotations

from typing import Any

from ..contracts.options_quality import OptionQualityFlag
from .edge import infer_underlying_price_from_activities
from .greeks import bsm_greeks

FLOW_VERSION = "options_signed_flow_v3"
UNDERLYING_PRICE_ASSUMPTION_MISSING = "UNDERLYING_PRICE_ASSUMPTION_MISSING"
BSM_VOL_OR_RATE_ASSUMPTION_MISSING = "BSM_VOL_OR_RATE_ASSUMPTION_MISSING"

_VOL_FIELD_NAMES = ("provider_iv", "implied_vol")
_RATE_FIELD_NAMES = ("rate",)


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


def _positive_float(value: Any) -> float | None:
    if isinstance(value, (int, float)) and float(value) > 0:
        return float(value)
    return None


def _resolve_spot(activities: list[dict[str, Any]], spot: float | None) -> float | None:
    explicit = _positive_float(spot)
    if explicit is not None:
        return explicit
    inferred = infer_underlying_price_from_activities(activities)
    if inferred is not None and inferred > 0:
        return inferred
    return None


def _first_positive_field(activities: list[dict[str, Any]], field_names: tuple[str, ...]) -> float | None:
    for row in activities:
        if not isinstance(row, dict):
            continue
        nested = row.get("canonical_contract")
        sources = [row]
        if isinstance(nested, dict):
            sources.append(nested)
        for source in sources:
            for name in field_names:
                resolved = _positive_float(source.get(name))
                if resolved is not None:
                    return resolved
    return None


def _resolve_rate(activities: list[dict[str, Any]], rate: float | None) -> float | None:
    explicit = _positive_float(rate)
    if explicit is not None:
        return explicit
    return _first_positive_field(activities, _RATE_FIELD_NAMES)


def _resolve_vol(activities: list[dict[str, Any]], vol: float | None) -> float | None:
    explicit = _positive_float(vol)
    if explicit is not None:
        return explicit
    return _first_positive_field(activities, _VOL_FIELD_NAMES)


def aggregate_signed_flow(
    activities: list[dict[str, Any]],
    *,
    spot: float | None = None,
    rate: float | None = None,
    vol: float | None = None,
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
    resolved_spot = _resolve_spot(activities, spot)
    resolved_rate = _resolve_rate(activities, rate)
    resolved_vol = _resolve_vol(activities, vol)
    greeks_flow_available = (
        resolved_spot is not None and resolved_rate is not None and resolved_vol is not None
    )

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
        if not greeks_flow_available or resolved_spot is None or resolved_rate is None or resolved_vol is None:
            continue
        strike = float(row.get("strike", resolved_spot))
        option_type = str(row.get("option_type", "call")).lower()
        dte = int(row.get("dte", row.get("days_to_expiration", 30)) or 30)
        time_years = max(dte / 365.0, 1 / 365.0)
        greeks = bsm_greeks(
            resolved_spot,
            strike,
            time_years,
            resolved_rate,
            resolved_vol,
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

    payload: dict[str, Any] = {
        "buy_initiated_volume": buy_volume,
        "sell_initiated_volume": sell_volume,
        "confirmed_trade_count": confirmed_count,
        "uncertain_trade_count": uncertain_count,
        "quality_flags": sorted(quality_flags),
        "greeks_flow_available": greeks_flow_available,
    }
    if greeks_flow_available:
        payload["net_delta_flow"] = round(net_delta_flow, 4)
        payload["net_gamma_flow"] = round(net_gamma_flow, 6)
        payload["net_vega_flow"] = round(net_vega_flow, 4)
    else:
        payload["net_delta_flow"] = None
        payload["net_gamma_flow"] = None
        payload["net_vega_flow"] = None
        if resolved_spot is None:
            payload["reason"] = UNDERLYING_PRICE_ASSUMPTION_MISSING
        else:
            payload["reason"] = BSM_VOL_OR_RATE_ASSUMPTION_MISSING
    return payload


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
    spot: float | None = None,
    rate: float | None = None,
    vol: float | None = None,
) -> dict[str, Any]:
    """Build signed-flow snapshot for workspace — fail-closed when no confirmed direction."""
    if not activities:
        return {
            "available": False,
            "reason": "NO_ACTIVITIES",
            "flow_version": FLOW_VERSION,
        }
    aggregate = aggregate_signed_flow(activities, spot=spot, rate=rate, vol=vol)
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
    snapshot: dict[str, Any] = {
        "available": True,
        "flow_version": FLOW_VERSION,
        "signed_flow_available": signed_available and dominant_direction is not None,
        "greeks_flow_available": bool(aggregate.get("greeks_flow_available")),
        "dominant_direction": dominant_direction,
        "as_of_time": as_of_time,
        "aggregate": aggregate,
        "abnormal_flow": abnormal_rows,
        "not_trade_signal": True,
    }
    if aggregate.get("reason"):
        snapshot["reason"] = aggregate["reason"]
    return snapshot


__all__ = [
    "BSM_VOL_OR_RATE_ASSUMPTION_MISSING",
    "FLOW_VERSION",
    "UNDERLYING_PRICE_ASSUMPTION_MISSING",
    "abnormal_flow_vs_baseline",
    "aggregate_signed_flow",
    "build_flow_snapshot",
    "classify_signed_flow",
]
