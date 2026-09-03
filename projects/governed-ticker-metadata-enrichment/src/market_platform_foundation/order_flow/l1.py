"""L1 quote state and book-pressure primitives."""

from __future__ import annotations

from typing import Any

from .contracts import BookPressureEvidence, L1QuoteState, MicrostructureCapabilityTier


def queue_imbalance(bid_size: float, ask_size: float) -> float:
    """QI = (BidSize - AskSize) / (BidSize + AskSize). Near-term book-pressure evidence."""
    total = bid_size + ask_size
    if total <= 0:
        return 0.0
    return round((bid_size - ask_size) / total, 6)


def depth_imbalance_ratio(bid_depth: float, ask_depth: float) -> float:
    """Raw bid/ask resting depth ratio — no directional interpretation."""
    if ask_depth <= 0:
        return 0.0
    return round(bid_depth / ask_depth, 6)


def compute_l1_state(
    *,
    best_bid: float,
    best_ask: float,
    bid_size: float,
    ask_size: float,
) -> L1QuoteState | None:
    """Derive canonical L1 microstructure features from top-of-book."""
    if best_bid <= 0 or best_ask <= 0 or best_ask < best_bid:
        return None
    spread = best_ask - best_bid
    mid = (best_bid + best_ask) / 2.0
    relative_spread = spread / mid if mid > 0 else 0.0
    total_size = bid_size + ask_size
    if total_size <= 0:
        microprice = mid
    else:
        microprice = (best_ask * bid_size + best_bid * ask_size) / total_size
    return L1QuoteState(
        best_bid=best_bid,
        best_ask=best_ask,
        bid_size=bid_size,
        ask_size=ask_size,
        spread=round(spread, 8),
        relative_spread=round(relative_spread, 8),
        mid=round(mid, 8),
        queue_imbalance=queue_imbalance(bid_size, ask_size),
        microprice=round(microprice, 8),
        microprice_minus_mid=round(microprice - mid, 8),
    )


def compute_book_pressure(
    bids: list[dict[str, Any]],
    asks: list[dict[str, Any]],
    *,
    level_count: int = 10,
) -> BookPressureEvidence | None:
    """Multi-level resting depth without domain directional labels."""
    if not bids or not asks:
        return None
    bid_depth = sum(float(row["size"]) for row in bids[:level_count])
    ask_depth = sum(float(row["size"]) for row in asks[:level_count])
    top_bid = max(bids, key=lambda row: float(row["price"]))
    top_ask = min(asks, key=lambda row: float(row["price"]))
    bbo = compute_l1_state(
        best_bid=float(top_bid["price"]),
        best_ask=float(top_ask["price"]),
        bid_size=float(top_bid["size"]),
        ask_size=float(top_ask["size"]),
    )
    qi = bbo.queue_imbalance if bbo else 0.0
    return BookPressureEvidence(
        depth_imbalance_ratio=depth_imbalance_ratio(bid_depth, ask_depth),
        queue_imbalance_l1=qi,
        bid_depth=bid_depth,
        ask_depth=ask_depth,
        level_count=min(level_count, len(bids), len(asks)),
    )


__all__ = [
    "compute_book_pressure",
    "compute_l1_state",
    "depth_imbalance_ratio",
    "queue_imbalance",
]
