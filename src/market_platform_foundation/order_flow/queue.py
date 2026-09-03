"""MBO queue reconstruction and position estimates — Order Flow OF10."""

from __future__ import annotations

from typing import Any

from .contracts import (
    MboOrder,
    MboOrderSide,
    MicrostructureCapabilityTier,
    PriceLevelQueue,
    QueuePositionEstimate,
    QueueSnapshot,
)

QUEUE_METHOD = "fifo_displayed_mbo_v1"
QUEUE_VERSION = "1"


def parse_mbo_orders(orders: list[dict[str, Any]]) -> list[MboOrder]:
    """Parse raw fixture/provider MBO order dicts into canonical contracts."""
    parsed: list[MboOrder] = []
    for row in orders:
        if not isinstance(row, dict):
            continue
        side_raw = str(row.get("side", "")).lower()
        if side_raw not in {MboOrderSide.BID.value, MboOrderSide.ASK.value}:
            continue
        parsed.append(
            MboOrder(
                order_id=str(row.get("order_id", "")),
                price=float(row.get("price", 0.0)),
                size=float(row.get("size", 0.0)),
                side=MboOrderSide(side_raw),
                sequence=int(row.get("sequence", 0)),
                timestamp=str(row.get("timestamp", "")),
            )
        )
    return sorted(parsed, key=lambda order: (order.sequence, order.order_id))


def reconstruct_queue_at_price(orders: list[MboOrder], *, price: float, side: MboOrderSide) -> PriceLevelQueue:
    """Aggregate MBO orders at one price level in FIFO sequence order."""
    level_orders = [
        order
        for order in orders
        if order.side == side and abs(order.price - price) < 1e-9
    ]
    level_orders = sorted(level_orders, key=lambda order: (order.sequence, order.order_id))
    total_size = sum(order.size for order in level_orders)
    return PriceLevelQueue(
        price=price,
        side=side,
        orders=tuple(level_orders),
        total_size=total_size,
    )


def build_queue_snapshot(
    orders: list[MboOrder] | list[dict[str, Any]],
    *,
    event_time: str,
) -> QueueSnapshot | None:
    """Build queue snapshot from MBO orders at one event time."""
    parsed = orders if orders and isinstance(orders[0], MboOrder) else parse_mbo_orders(orders)  # type: ignore[arg-type]
    if not parsed:
        return None

    quality_flags: list[str] = []
    if any(order.sequence <= 0 for order in parsed):
        quality_flags.append("SEQUENCE_INCOMPLETE")

    bid_prices = sorted({order.price for order in parsed if order.side == MboOrderSide.BID}, reverse=True)
    ask_prices = sorted({order.price for order in parsed if order.side == MboOrderSide.ASK})
    bid_queues = tuple(
        reconstruct_queue_at_price(parsed, price=price, side=MboOrderSide.BID) for price in bid_prices
    )
    ask_queues = tuple(
        reconstruct_queue_at_price(parsed, price=price, side=MboOrderSide.ASK) for price in ask_prices
    )
    return QueueSnapshot(
        event_time=event_time,
        bid_queues=bid_queues,
        ask_queues=ask_queues,
        queue_method=QUEUE_METHOD,
        queue_version=QUEUE_VERSION,
        capability_tier=MicrostructureCapabilityTier.MBO,
        quality_flags=tuple(quality_flags),
    )


def estimate_queue_position(
    snapshot: QueueSnapshot,
    *,
    price: float,
    side: MboOrderSide | str,
    hypothetical_size: float,
) -> QueuePositionEstimate:
    """Estimate queue position for a hypothetical passive order at a price level."""
    side_enum = MboOrderSide(str(side).lower())
    queues = snapshot.bid_queues if side_enum == MboOrderSide.BID else snapshot.ask_queues
    level_queue = next((queue for queue in queues if abs(queue.price - price) < 1e-9), None)
    if level_queue is None:
        return QueuePositionEstimate(
            price=price,
            side=side_enum,
            hypothetical_size=hypothetical_size,
            size_ahead=0.0,
            size_at_level=0.0,
            queue_method=QUEUE_METHOD,
            queue_version=QUEUE_VERSION,
            quality_flags=("PRICE_LEVEL_NOT_FOUND",),
        )
    size_ahead = max(level_queue.total_size - hypothetical_size, 0.0)
    return QueuePositionEstimate(
        price=price,
        side=side_enum,
        hypothetical_size=hypothetical_size,
        size_ahead=size_ahead,
        size_at_level=level_queue.total_size,
        queue_method=QUEUE_METHOD,
        queue_version=QUEUE_VERSION,
        quality_flags=snapshot.quality_flags,
    )


def compute_queue_imbalance_mbo(snapshot: QueueSnapshot) -> float:
    """MBO-refined queue pressure at touch: (bid_touch - ask_touch) / (bid_touch + ask_touch)."""
    bid_touch = snapshot.bid_queues[0].total_size if snapshot.bid_queues else 0.0
    ask_touch = snapshot.ask_queues[0].total_size if snapshot.ask_queues else 0.0
    denom = bid_touch + ask_touch
    if denom <= 0:
        return 0.0
    return (bid_touch - ask_touch) / denom


__all__ = [
    "QUEUE_METHOD",
    "QUEUE_VERSION",
    "build_queue_snapshot",
    "compute_queue_imbalance_mbo",
    "estimate_queue_position",
    "parse_mbo_orders",
    "reconstruct_queue_at_price",
]
