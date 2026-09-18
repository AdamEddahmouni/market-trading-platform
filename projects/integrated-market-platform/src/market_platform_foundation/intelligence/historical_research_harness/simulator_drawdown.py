"""Mark-to-market net-PnL equity curve and max drawdown for simulator research.

Authority: HISTORICAL_DEVELOPMENT only. Does not alter frozen v3 evidence manifests.

Curve basis: cumulative **net** mark-to-market PnL (0 before first fill), sampled
after each fill at the bar close on or before ``fill_time``, plus a terminal
sample using the same end-of-run mark as ``aggregate_fill_economics``.

This is **not** drawdown on total cash equity (initial_cash dominates); it
matches research ``net_pnl`` units (native currency).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ...numeric import decimal_to_minor_units

DRAWDOWN_METRICS_VERSION = "simulator-research/net-mtm-drawdown/1.0.0"
MAX_DRAWDOWN_SOURCE_EQUITY_CURVE = "EQUITY_CURVE_NET_MTM"


def mark_price_minor_at_or_before(
    events: Sequence[Mapping[str, Any]],
    *,
    at_time_ns: int,
    instrument_id: str | None,
    price_scale: int,
) -> int | None:
    bars = [
        event
        for event in events
        if event.get("event_type") == "BAR_OHLCV_1M"
        and int(event["available_time"]) <= at_time_ns
        and (instrument_id is None or str(event.get("instrument_id")) == instrument_id)
    ]
    if not bars:
        return None
    last = max(bars, key=lambda row: int(row["available_time"]))
    payload = last.get("bar_payload")
    if not isinstance(payload, dict):
        return None
    close = str(payload.get("close", ""))
    try:
        return decimal_to_minor_units(close, scale=price_scale)
    except ValueError:
        return None


def gross_unrealized_minor(
    *,
    position_shares: int,
    basis_minor: int,
    mark_minor: int | None,
) -> int:
    if position_shares == 0 or mark_minor is None:
        return 0
    if position_shares > 0:
        return position_shares * mark_minor - basis_minor
    return abs(basis_minor) - abs(position_shares) * mark_minor


def max_peak_to_trough_drawdown(curve: Sequence[float]) -> float:
    if not curve:
        return 0.0
    peak = curve[0]
    max_dd = 0.0
    for value in curve:
        if value > peak:
            peak = value
        decline = peak - value
        if decline > max_dd:
            max_dd = decline
    return max_dd


def net_mtm_pnl_native(
    *,
    gross_market_realized_minor: int,
    gross_unrealized_minor: int,
    scale: int,
    slippage_total_native: float,
    policy_fees_total_native: float,
) -> float:
    gross_realized_native = gross_market_realized_minor / float(scale)
    gross_unrealized_native = gross_unrealized_minor / float(scale)
    gross_pnl = gross_realized_native + gross_unrealized_native
    transaction_costs = slippage_total_native + policy_fees_total_native
    return gross_pnl - transaction_costs


__all__ = [
    "DRAWDOWN_METRICS_VERSION",
    "MAX_DRAWDOWN_SOURCE_EQUITY_CURVE",
    "gross_unrealized_minor",
    "mark_price_minor_at_or_before",
    "max_peak_to_trough_drawdown",
    "net_mtm_pnl_native",
]
