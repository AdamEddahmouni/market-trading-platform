"""Futures depth lane patterns — PORT_ADAPT from Eric_futuresX concepts (stdlib only)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .order_book_lane import best_bid_ask, depth_imbalance, snapshot_ofi

ET = ZoneInfo("America/New_York")
RTH_OPEN = time(9, 30)
RTH_CLOSE = time(16, 0)


def get_third_friday(year: int, month: int) -> date:
    probe = date(year, month, 15)
    while probe.weekday() != 4:
        probe += timedelta(days=1)
    return probe


def quarterly_contract_month(today: date | None = None) -> str:
    """Return nearest ES/NQ quarterly contract month as YYYYMM."""
    today = today or date.today()
    year = today.year
    if today.month <= 3:
        expiry_month = 3
    elif today.month <= 6:
        expiry_month = 6
    elif today.month <= 9:
        expiry_month = 9
    else:
        expiry_month = 12
    expiry_year = year
    third_friday = get_third_friday(expiry_year, expiry_month)
    if today >= third_friday:
        if expiry_month == 3:
            expiry_month = 6
        elif expiry_month == 6:
            expiry_month = 9
        elif expiry_month == 9:
            expiry_month = 12
        else:
            expiry_month = 3
            expiry_year += 1
    return f"{expiry_year}{expiry_month:02d}"


def is_rth(ts: datetime) -> bool:
    """True when timestamp falls within 9:30–16:00 America/New_York."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=ET)
    else:
        ts = ts.astimezone(ET)
    current = ts.time()
    return RTH_OPEN <= current <= RTH_CLOSE


def depth_imbalance_signal(
    bids: list[dict[str, Any]],
    asks: list[dict[str, Any]],
    *,
    level_count: int = 5,
    threshold: float = 1.5,
) -> tuple[str, float]:
    """Return (signal, ratio) using FuturesX live_trader contrarian depth logic."""
    bid_sizes = sum(float(row["size"]) for row in bids[:level_count])
    ask_sizes = sum(float(row["size"]) for row in asks[:level_count])
    if ask_sizes <= 0:
        return "neutral", 0.0
    ratio = round(bid_sizes / ask_sizes, 4)
    if bid_sizes > ask_sizes * threshold:
        return "supports_short", ratio
    if ask_sizes > bid_sizes * threshold:
        return "supports_long", ratio
    return "neutral", ratio


def project_futures_depth(
    *,
    symbol: str,
    contract_month: str,
    exchange: str,
    session_state: str,
    snapshot: dict[str, Any],
    imbalance_ratio: float,
    imbalance_signal: str,
    ofi_value: float | None,
    rth: bool,
    ofi_method: str | None = None,
    ofi_version: str | None = None,
    book_state_valid: bool | None = None,
    ofi_degraded: bool | None = None,
    ofi_quality_flags: tuple[str, ...] | list[str] | None = None,
) -> dict[str, Any]:
    bbo = best_bid_ask(snapshot)
    row: dict[str, Any] = {
        "ask_size": bbo["ask_size"] if bbo else None,
        "best_ask": bbo["ask_price"] if bbo else None,
        "best_bid": bbo["bid_price"] if bbo else None,
        "bid_size": bbo["bid_size"] if bbo else None,
        "contract_month": contract_month,
        "epistemic_class": "DERIVED",
        "exchange": exchange,
        "imbalance_ratio": imbalance_ratio,
        "imbalance_signal": imbalance_signal,
        "lane": "futures_depth",
        "note": "Depth-derived positioning signal; not CFTC positioning or trade advice.",
        "ofi_value": ofi_value,
        "research_only": True,
        "rth": rth,
        "session_state": session_state,
        "snapshot_provenance": str(snapshot.get("source", "fixture_synthetic")),
        "symbol": symbol,
    }
    if ofi_method is not None:
        row["ofi_method"] = ofi_method
    if ofi_version is not None:
        row["ofi_version"] = ofi_version
    if book_state_valid is not None:
        row["book_state_valid"] = book_state_valid
    if ofi_degraded is not None:
        row["ofi_degraded"] = ofi_degraded
    if ofi_quality_flags is not None:
        row["ofi_quality_flags"] = list(ofi_quality_flags)
    return row


__all__ = [
    "depth_imbalance_signal",
    "get_third_friday",
    "is_rth",
    "project_futures_depth",
    "quarterly_contract_month",
    "snapshot_ofi",
]
