"""Quality checks reuse canonical OF flags; no Moomoo-specific taxonomy."""

from __future__ import annotations

from typing import Any

from ..order_flow.l1 import compute_l1_state
from ..order_flow.quality import OrderFlowQualityFlag
from .normalization import levels_from_order_book


def assess_quote(payload: dict[str, Any]) -> tuple[str, ...]:
    flags: list[str] = []
    bid = float(payload.get("bid_price") or payload.get("best_bid") or 0)
    ask = float(payload.get("ask_price") or payload.get("best_ask") or 0)
    bid_size = float(payload.get("bid_vol") or payload.get("bid_size") or 0)
    ask_size = float(payload.get("ask_vol") or payload.get("ask_size") or 0)
    last = payload.get("last_price") or payload.get("last")
    if bid_size < 0 or ask_size < 0:
        flags.append("QUAL_INVALID_VOLUME")
    if bid > 0 and ask > 0:
        if ask < bid:
            flags.append(OrderFlowQualityFlag.CROSSED_BOOK.value)
        elif ask == bid:
            flags.append(OrderFlowQualityFlag.LOCKED_BOOK.value)
        l1 = compute_l1_state(best_bid=bid, best_ask=ask, bid_size=bid_size, ask_size=ask_size)
        if l1 is None:
            flags.append("INVALID_QUOTE")
        elif l1.relative_spread > 0.05:
            flags.append(OrderFlowQualityFlag.SPREAD_ABNORMAL.value)
    elif last in (None, 0, 0.0):
        flags.append("INVALID_QUOTE")
    return tuple(dict.fromkeys(flags))


def assess_ticker(payload: dict[str, Any], *, prior_sequence: int | None = None) -> tuple[str, ...]:
    flags: list[str] = []
    volume = float(payload.get("volume") or 0)
    price = float(payload.get("price") or 0)
    if volume < 0 or price < 0:
        flags.append("QUAL_INVALID_VOLUME")
    direction = str(payload.get("ticker_direction") or "").upper()
    if direction not in {"BUY", "SELL", "BID", "ASK"}:
        flags.append(OrderFlowQualityFlag.AGGRESSOR_UNKNOWN.value)
    sequence = payload.get("sequence")
    if prior_sequence is not None and sequence is not None:
        try:
            current = int(sequence)
            if current < prior_sequence:
                flags.append("TIMESTAMP_REVERSAL")
            elif current > prior_sequence:
                delta = current - prior_sequence
                if 1 < delta < 10_000:
                    flags.append(OrderFlowQualityFlag.SEQUENCE_GAP.value)
            elif current == prior_sequence:
                flags.append("DUPLICATE_TICK")
        except (TypeError, ValueError):
            pass
    return tuple(dict.fromkeys(flags))


def assess_book(payload: dict[str, Any]) -> tuple[str, ...]:
    flags: list[str] = []
    bids, asks = levels_from_order_book(payload)
    if not bids or not asks:
        flags.append(OrderFlowQualityFlag.DEPTH_PARTIAL.value)
        flags.append(OrderFlowQualityFlag.MICROSTRUCTURE_CAPABILITY_UNAVAILABLE.value)
        return tuple(dict.fromkeys(flags))
    if any(row["size"] < 0 for row in bids + asks):
        flags.append("QUAL_INVALID_VOLUME")
    best_bid = bids[0]["price"]
    best_ask = asks[0]["price"]
    if best_ask < best_bid:
        flags.append(OrderFlowQualityFlag.CROSSED_BOOK.value)
    elif best_ask == best_bid:
        flags.append(OrderFlowQualityFlag.LOCKED_BOOK.value)
    order_counts = [row.get("order_count") for row in bids + asks]
    if any(count in (None, 0) for count in order_counts[:2]):
        flags.append(OrderFlowQualityFlag.MBO_UNAVAILABLE.value)
    if payload.get("venue") in (None, "", "UNKNOWN"):
        flags.append(OrderFlowQualityFlag.VENUE_PARTIAL.value)
    return tuple(dict.fromkeys(flags))
