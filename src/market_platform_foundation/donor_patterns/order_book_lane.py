"""Order-book depth helpers (PORT_ADAPT; no donor code copy)."""

from __future__ import annotations

from typing import Any

from ..order_flow.ofi import compute_bbo_ofi

Level = dict[str, float | int]


def best_bid_ask(snapshot: dict[str, Any]) -> dict[str, float] | None:
    bids = snapshot.get("bids", [])
    asks = snapshot.get("asks", [])
    if not isinstance(bids, list) or not isinstance(asks, list) or not bids or not asks:
        return None
    best_bid = max(bids, key=lambda row: float(row["price"]))
    best_ask = min(asks, key=lambda row: float(row["price"]))
    return {
        "ask_price": float(best_ask["price"]),
        "ask_size": float(best_ask["size"]),
        "bid_price": float(best_bid["price"]),
        "bid_size": float(best_bid["size"]),
    }


def depth_imbalance(
    bids: list[dict[str, Any]],
    asks: list[dict[str, Any]],
    *,
    level_count: int = 10,
) -> float:
    bid_sizes = sum(float(row["size"]) for row in bids[:level_count])
    ask_sizes = sum(float(row["size"]) for row in asks[:level_count])
    if ask_sizes <= 0:
        return 0.0
    return round(bid_sizes / ask_sizes, 4)


def snapshot_ofi(prev_snapshot: dict[str, Any], curr_snapshot: dict[str, Any]) -> float:
    """Backward-compatible BBO OFI delegate to order_flow.ofi."""
    return compute_bbo_ofi(prev_snapshot, curr_snapshot).value


def direction_from_imbalance(ratio: float, *, threshold: float = 1.2) -> str:
    if ratio <= 0:
        return "ambiguous"
    if ratio >= threshold:
        return "supports_long"
    if ratio <= (1.0 / threshold):
        return "supports_short"
    return "neutral"


def book_pressure_side(ratio: float, *, threshold: float = 1.2) -> str:
    """Raw resting-book pressure without domain interpretation policy.

    Order Flow owns this primitive; momentum vs contrarian lanes apply policy separately.
    """
    if ratio <= 0:
        return "neutral"
    if ratio >= threshold:
        return "bid_heavy"
    if ratio <= (1.0 / threshold):
        return "ask_heavy"
    return "neutral"


__all__ = [
    "best_bid_ask",
    "book_pressure_side",
    "depth_imbalance",
    "direction_from_imbalance",
    "snapshot_ofi",
]
