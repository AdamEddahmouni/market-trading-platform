"""Deterministic L2 research features from canonical book levels.

Does not label spoofing. Sequential diffs are liquidity add/remove/execute
candidates only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..order_flow.l1 import compute_l1_state, depth_imbalance_ratio, queue_imbalance


@dataclass(frozen=True, slots=True)
class BookFeatureSnapshot:
    spread: float | None
    midprice: float | None
    microprice: float | None
    bid_depth_1: float
    ask_depth_1: float
    bid_depth_5: float
    ask_depth_5: float
    bid_depth_10: float
    ask_depth_10: float
    book_imbalance_1: float
    book_imbalance_5: float
    book_imbalance_10: float
    depth_slope_bid: float | None
    depth_slope_ask: float | None
    depth_concentration_bid: float | None
    depth_concentration_ask: float | None
    distance_weighted_bid: float
    distance_weighted_ask: float
    large_resting_level: dict[str, Any] | None
    liquidity_wall_score: float
    capability_tier: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "ask_depth_1": self.ask_depth_1,
            "ask_depth_10": self.ask_depth_10,
            "ask_depth_5": self.ask_depth_5,
            "bid_depth_1": self.bid_depth_1,
            "bid_depth_10": self.bid_depth_10,
            "bid_depth_5": self.bid_depth_5,
            "book_imbalance_1": self.book_imbalance_1,
            "book_imbalance_10": self.book_imbalance_10,
            "book_imbalance_5": self.book_imbalance_5,
            "capability_tier": self.capability_tier,
            "depth_concentration_ask": self.depth_concentration_ask,
            "depth_concentration_bid": self.depth_concentration_bid,
            "depth_slope_ask": self.depth_slope_ask,
            "depth_slope_bid": self.depth_slope_bid,
            "distance_weighted_ask": self.distance_weighted_ask,
            "distance_weighted_bid": self.distance_weighted_bid,
            "large_resting_level": self.large_resting_level,
            "liquidity_wall_score": self.liquidity_wall_score,
            "microprice": self.microprice,
            "midprice": self.midprice,
            "spread": self.spread,
        }


def compute_book_features(
    bids: list[dict[str, Any]],
    asks: list[dict[str, Any]],
) -> BookFeatureSnapshot | None:
    if not bids or not asks:
        return None
    l1 = compute_l1_state(
        best_bid=float(bids[0]["price"]),
        best_ask=float(asks[0]["price"]),
        bid_size=float(bids[0]["size"]),
        ask_size=float(asks[0]["size"]),
    )
    bid_d1 = _depth(bids, 1)
    ask_d1 = _depth(asks, 1)
    bid_d5 = _depth(bids, 5)
    ask_d5 = _depth(asks, 5)
    bid_d10 = _depth(bids, 10)
    ask_d10 = _depth(asks, 10)
    wall = _largest_level(bids, asks)
    bid_total = bid_d10 or 1.0
    ask_total = ask_d10 or 1.0
    wall_size = float(wall["size"]) if wall else 0.0
    wall_score = wall_size / max(bid_total + ask_total, 1.0)
    return BookFeatureSnapshot(
        spread=None if l1 is None else l1.spread,
        midprice=None if l1 is None else l1.mid,
        microprice=None if l1 is None else l1.microprice,
        bid_depth_1=bid_d1,
        ask_depth_1=ask_d1,
        bid_depth_5=bid_d5,
        ask_depth_5=ask_d5,
        bid_depth_10=bid_d10,
        ask_depth_10=ask_d10,
        book_imbalance_1=queue_imbalance(bid_d1, ask_d1),
        book_imbalance_5=queue_imbalance(bid_d5, ask_d5),
        book_imbalance_10=queue_imbalance(bid_d10, ask_d10),
        depth_slope_bid=_slope(bids),
        depth_slope_ask=_slope(asks),
        depth_concentration_bid=_concentration(bids, bid_d10),
        depth_concentration_ask=_concentration(asks, ask_d10),
        distance_weighted_bid=_distance_weighted(bids, float(bids[0]["price"]), 1.0),
        distance_weighted_ask=_distance_weighted(asks, float(asks[0]["price"]), -1.0),
        large_resting_level=wall,
        liquidity_wall_score=round(wall_score, 6),
        capability_tier="L2_MBP",
    )


def diff_book_liquidity(
    prior: list[dict[str, Any]],
    current: list[dict[str, Any]],
    *,
    last_trade_size: float = 0.0,
) -> dict[str, float]:
    prior_map = {float(row["price"]): float(row["size"]) for row in prior}
    current_map = {float(row["price"]): float(row["size"]) for row in current}
    added = 0.0
    removed = 0.0
    for price, size in current_map.items():
        delta = size - prior_map.get(price, 0.0)
        if delta > 0:
            added += delta
        elif delta < 0:
            removed += -delta
    for price, size in prior_map.items():
        if price not in current_map:
            removed += size
    executed = min(last_trade_size, removed) if last_trade_size > 0 else 0.0
    return {
        "executed_liquidity": executed,
        "new_liquidity": added,
        "removed_liquidity": removed,
    }


def _depth(levels: list[dict[str, Any]], count: int) -> float:
    return sum(float(row["size"]) for row in levels[:count])


def _slope(levels: list[dict[str, Any]]) -> float | None:
    if len(levels) < 2:
        return None
    first = float(levels[0]["size"])
    last = float(levels[min(len(levels), 10) - 1]["size"])
    return round(last - first, 6)


def _concentration(levels: list[dict[str, Any]], total: float) -> float | None:
    if total <= 0 or not levels:
        return None
    return round(float(levels[0]["size"]) / total, 6)


def _distance_weighted(levels: list[dict[str, Any]], touch: float, sign: float) -> float:
    weighted = 0.0
    for row in levels[:10]:
        distance = abs(float(row["price"]) - touch)
        decay = 1.0 / (1.0 + distance)
        weighted += float(row["size"]) * decay
    return round(weighted * sign if sign < 0 else weighted, 6)


def _largest_level(
    bids: list[dict[str, Any]],
    asks: list[dict[str, Any]],
) -> dict[str, Any] | None:
    combined = [("bid", row) for row in bids[:10]] + [("ask", row) for row in asks[:10]]
    if not combined:
        return None
    side, row = max(combined, key=lambda item: float(item[1]["size"]))
    return {"price": float(row["price"]), "side": side, "size": float(row["size"])}


def imbalance_ratio(bid_depth: float, ask_depth: float) -> float:
    return depth_imbalance_ratio(bid_depth, ask_depth)
