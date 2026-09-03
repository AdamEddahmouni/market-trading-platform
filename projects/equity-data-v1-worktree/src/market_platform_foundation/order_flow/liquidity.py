"""Liquidity dynamics from L2 depth snapshots — Order Flow OF6 (fixture scope).

Displayed-depth withdrawal/replenishment, spread response, and fragility composites.
Without MBO cancel events, withdrawal is inferred from net depth drops between snapshots.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .ofi import _best_bid_ask, _sorted_bids, _sorted_asks, snapshot_book_state_valid, snapshot_pair_book_state_valid

LIQUIDITY_METHOD_DEPTH_DELTA = "liquidity_depth_delta_v1"
LIQUIDITY_VERSION = "1"

FRAGILITY_ELEVATED_THRESHOLD = 0.25
WITHDRAWAL_RATIO_SIGNAL_THRESHOLD = 0.15


@dataclass(frozen=True, slots=True)
class LiquidityDynamicsResult:
    net_depth_delta: float
    bid_depth_delta: float
    ask_depth_delta: float
    depth_withdrawal: float
    depth_replenishment: float
    spread_delta: float
    relative_spread_delta: float
    fragility_score: float
    resiliency_score: float | None
    total_depth: float
    liquidity_method: str
    liquidity_version: str
    book_state_valid: bool
    level_count: int | None = None


def _level_size_sum(levels: list[dict[str, Any]], level_count: int) -> float:
    total = 0.0
    for rank in range(min(level_count, len(levels))):
        try:
            total += float(levels[rank]["size"])
        except (KeyError, TypeError, ValueError):
            continue
    return total


def snapshot_total_depth(snapshot: dict[str, Any], *, level_count: int = 10) -> float | None:
    """Sum displayed bid + ask size across top `level_count` ranks."""
    if not snapshot_book_state_valid(snapshot):
        return None
    bids = _sorted_bids(snapshot["bids"])
    asks = _sorted_asks(snapshot["asks"])
    return _level_size_sum(bids, level_count) + _level_size_sum(asks, level_count)


def snapshot_side_depths(snapshot: dict[str, Any], *, level_count: int = 10) -> tuple[float, float] | None:
    if not snapshot_book_state_valid(snapshot):
        return None
    bids = _sorted_bids(snapshot["bids"])
    asks = _sorted_asks(snapshot["asks"])
    return _level_size_sum(bids, level_count), _level_size_sum(asks, level_count)


def _spread_metrics(snapshot: dict[str, Any]) -> tuple[float, float] | None:
    bbo = _best_bid_ask(snapshot)
    if bbo is None:
        return None
    bid_price, _, ask_price, _ = bbo
    spread = ask_price - bid_price
    mid = (bid_price + ask_price) / 2.0
    relative_spread = spread / mid if mid > 0 else 0.0
    return spread, relative_spread


def _fragility_score(
    *,
    prev_total_depth: float,
    curr_total_depth: float,
    depth_withdrawal: float,
    relative_spread_delta: float,
) -> float:
    if prev_total_depth <= 0:
        withdrawal_ratio = 1.0 if depth_withdrawal > 0 else 0.0
        depth_ratio = 0.0
    else:
        withdrawal_ratio = depth_withdrawal / prev_total_depth
        depth_ratio = curr_total_depth / prev_total_depth
    depth_shrink = max(0.0, 1.0 - min(depth_ratio, 1.0))
    spread_component = min(1.0, max(0.0, relative_spread_delta) * 50.0)
    score = 0.5 * withdrawal_ratio + 0.3 * depth_shrink + 0.2 * spread_component
    return round(min(max(score, 0.0), 1.0), 6)


def compute_trajectory_resiliency(
    snapshots: list[dict[str, Any]],
    *,
    level_count: int = 10,
) -> float | None:
    """Recovery ratio from local depth trough to subsequent peak (fixture trajectory)."""
    depths: list[float] = []
    for snapshot in snapshots:
        total = snapshot_total_depth(snapshot, level_count=level_count)
        if total is None:
            return None
        depths.append(total)
    if len(depths) < 3:
        return None
    shock_index = min(range(len(depths)), key=lambda i: depths[i])
    shock_depth = depths[shock_index]
    peak_before = max(depths[: shock_index + 1])
    if shock_depth >= peak_before:
        return 1.0
    peak_after = max(depths[shock_index:])
    recovery = (peak_after - shock_depth) / (peak_before - shock_depth)
    return round(min(max(recovery, 0.0), 1.0), 6)


def compute_liquidity_dynamics(
    prev_snapshot: dict[str, Any],
    curr_snapshot: dict[str, Any],
    *,
    level_count: int = 10,
    trajectory_resiliency: float | None = None,
) -> LiquidityDynamicsResult:
    """Pair-wise displayed-depth liquidity dynamics between two book snapshots."""
    if not snapshot_pair_book_state_valid(prev_snapshot, curr_snapshot):
        return LiquidityDynamicsResult(
            net_depth_delta=0.0,
            bid_depth_delta=0.0,
            ask_depth_delta=0.0,
            depth_withdrawal=0.0,
            depth_replenishment=0.0,
            spread_delta=0.0,
            relative_spread_delta=0.0,
            fragility_score=0.0,
            resiliency_score=None,
            total_depth=0.0,
            liquidity_method=LIQUIDITY_METHOD_DEPTH_DELTA,
            liquidity_version=LIQUIDITY_VERSION,
            book_state_valid=False,
            level_count=level_count,
        )

    prev_sides = snapshot_side_depths(prev_snapshot, level_count=level_count)
    curr_sides = snapshot_side_depths(curr_snapshot, level_count=level_count)
    prev_spread = _spread_metrics(prev_snapshot)
    curr_spread = _spread_metrics(curr_snapshot)
    if prev_sides is None or curr_sides is None or prev_spread is None or curr_spread is None:
        return LiquidityDynamicsResult(
            net_depth_delta=0.0,
            bid_depth_delta=0.0,
            ask_depth_delta=0.0,
            depth_withdrawal=0.0,
            depth_replenishment=0.0,
            spread_delta=0.0,
            relative_spread_delta=0.0,
            fragility_score=0.0,
            resiliency_score=None,
            total_depth=0.0,
            liquidity_method=LIQUIDITY_METHOD_DEPTH_DELTA,
            liquidity_version=LIQUIDITY_VERSION,
            book_state_valid=False,
            level_count=level_count,
        )

    prev_bid, prev_ask = prev_sides
    curr_bid, curr_ask = curr_sides
    prev_total = prev_bid + prev_ask
    curr_total = curr_bid + curr_ask
    net_delta = curr_total - prev_total
    withdrawal = max(0.0, -net_delta)
    replenishment = max(0.0, net_delta)
    spread_delta = curr_spread[0] - prev_spread[0]
    relative_spread_delta = curr_spread[1] - prev_spread[1]
    fragility = _fragility_score(
        prev_total_depth=prev_total,
        curr_total_depth=curr_total,
        depth_withdrawal=withdrawal,
        relative_spread_delta=relative_spread_delta,
    )
    resiliency = trajectory_resiliency

    return LiquidityDynamicsResult(
        net_depth_delta=round(net_delta, 4),
        bid_depth_delta=round(curr_bid - prev_bid, 4),
        ask_depth_delta=round(curr_ask - prev_ask, 4),
        depth_withdrawal=round(withdrawal, 4),
        depth_replenishment=round(replenishment, 4),
        spread_delta=round(spread_delta, 8),
        relative_spread_delta=round(relative_spread_delta, 8),
        fragility_score=fragility,
        resiliency_score=resiliency,
        total_depth=round(curr_total, 4),
        liquidity_method=LIQUIDITY_METHOD_DEPTH_DELTA,
        liquidity_version=LIQUIDITY_VERSION,
        book_state_valid=True,
        level_count=level_count,
    )


def liquidity_dynamics_to_dict(result: LiquidityDynamicsResult) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "net_depth_delta": result.net_depth_delta,
        "bid_depth_delta": result.bid_depth_delta,
        "ask_depth_delta": result.ask_depth_delta,
        "depth_withdrawal": result.depth_withdrawal,
        "depth_replenishment": result.depth_replenishment,
        "spread_delta": result.spread_delta,
        "relative_spread_delta": result.relative_spread_delta,
        "fragility_score": result.fragility_score,
        "total_depth": result.total_depth,
        "liquidity_method": result.liquidity_method,
        "liquidity_version": result.liquidity_version,
        "book_state_valid": result.book_state_valid,
    }
    if result.resiliency_score is not None:
        payload["resiliency_score"] = result.resiliency_score
    if result.level_count is not None:
        payload["level_count"] = result.level_count
    return payload


def withdrawal_ratio(result: LiquidityDynamicsResult, prev_total_depth: float) -> float:
    if prev_total_depth <= 0:
        return 1.0 if result.depth_withdrawal > 0 else 0.0
    return result.depth_withdrawal / prev_total_depth


def fragility_elevated(result: LiquidityDynamicsResult, *, prev_total_depth: float) -> bool:
    ratio = withdrawal_ratio(result, prev_total_depth)
    return result.fragility_score >= FRAGILITY_ELEVATED_THRESHOLD or ratio >= WITHDRAWAL_RATIO_SIGNAL_THRESHOLD


__all__ = [
    "FRAGILITY_ELEVATED_THRESHOLD",
    "LIQUIDITY_METHOD_DEPTH_DELTA",
    "LIQUIDITY_VERSION",
    "WITHDRAWAL_RATIO_SIGNAL_THRESHOLD",
    "LiquidityDynamicsResult",
    "compute_liquidity_dynamics",
    "compute_trajectory_resiliency",
    "fragility_elevated",
    "liquidity_dynamics_to_dict",
    "snapshot_total_depth",
    "withdrawal_ratio",
]
