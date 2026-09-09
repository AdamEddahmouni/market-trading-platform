"""IBKR L1 observational accumulation (G6).

IB delivers price and size in separate callbacks (``tickPrice`` /
``tickSize``) and often with different field ids. This module maintains
subscription-local accumulation so that the canonical L1 quote facts are
truthful: a field that has never been observed stays ``None`` — an unknown
size is never coerced to 0 and a missing side is never fabricated. Delayed
tick fields mark the accumulation delayed; delayed facts are never presented
as real-time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .constants import (
    TICK_ASK,
    TICK_ASK_SIZE,
    TICK_BID,
    TICK_BID_SIZE,
    TICK_LAST,
    TICK_LAST_SIZE,
)
from .contracts import EntitlementState, L1QuoteFacts


@dataclass(slots=True)
class L1Accumulator:
    """Per-subscription L1 fact accumulation (mutable; adapter-lock owned)."""

    instrument_id: str
    subscription_id: str
    generation: int
    bid_price: float | None = None
    ask_price: float | None = None
    bid_size: float | None = None
    ask_size: float | None = None
    last_price: float | None = None
    last_size: float | None = None
    delayed: bool = False
    entitlement: EntitlementState = EntitlementState.UNKNOWN
    source_time_ns: int | None = None
    received_time_ns: int | None = None
    tick_count: int = 0
    last_unknown_field: int | None = None

    def on_tick_price(
        self,
        *,
        field: int,
        price: float | None,
        source_time_ns: int | None = None,
        received_time_ns: int | None = None,
    ) -> L1QuoteFacts:
        """Apply one ``tickPrice`` fact and return the refreshed facts."""
        self.tick_count += 1
        if price is not None:
            self._store_price(field, price)
        self._touch_times(source_time_ns, received_time_ns)
        return self.facts()

    def on_tick_size(
        self,
        *,
        field: int,
        size: float | None,
        source_time_ns: int | None = None,
        received_time_ns: int | None = None,
    ) -> L1QuoteFacts:
        """Apply one ``tickSize`` fact and return the refreshed facts."""
        self.tick_count += 1
        if size is not None:
            self._store_size(field, size)
        self._touch_times(source_time_ns, received_time_ns)
        return self.facts()

    def _store_price(self, field: int, price: float) -> None:
        if field == TICK_BID:
            self.bid_price = price
        elif field == TICK_ASK:
            self.ask_price = price
        elif field == TICK_LAST:
            self.last_price = price
        else:
            from .mapping import classify_tick_field, is_delayed_tick_field

            classified = classify_tick_field(field)
            if classified.delayed:
                self.delayed = True
            if classified.slot == "bid_price":
                self.bid_price = price
            elif classified.slot == "ask_price":
                self.ask_price = price
            elif classified.slot == "last_price":
                self.last_price = price
            else:
                self.last_unknown_field = field

    def _store_size(self, field: int, size: float) -> None:
        if field == TICK_BID_SIZE:
            self.bid_size = size
        elif field == TICK_ASK_SIZE:
            self.ask_size = size
        elif field == TICK_LAST_SIZE:
            self.last_size = size
        else:
            from .mapping import classify_tick_field

            classified = classify_tick_field(field)
            if classified.delayed:
                self.delayed = True
            if classified.slot == "bid_size":
                self.bid_size = size
            elif classified.slot == "ask_size":
                self.ask_size = size
            elif classified.slot == "last_size":
                self.last_size = size
            else:
                self.last_unknown_field = field

    def _touch_times(
        self,
        source_time_ns: int | None,
        received_time_ns: int | None,
    ) -> None:
        if source_time_ns is not None:
            self.source_time_ns = source_time_ns
        if received_time_ns is not None:
            self.received_time_ns = received_time_ns

    def mark_delayed(self) -> None:
        """Explicitly mark the subscription data delayed (entitlement path)."""
        self.delayed = True
        if self.entitlement is EntitlementState.UNKNOWN:
            self.entitlement = EntitlementState.DELAYED

    def mark_entitled(self) -> None:
        """Only an explicit provider/entitlement fact may set ENTITLED."""
        if not self.delayed:
            self.entitlement = EntitlementState.ENTITLED

    def facts(self) -> L1QuoteFacts:
        """Immutable truthful snapshot of the accumulated facts."""
        return L1QuoteFacts(
            instrument_id=self.instrument_id,
            subscription_id=self.subscription_id,
            generation=self.generation,
            bid_price=self.bid_price,
            ask_price=self.ask_price,
            bid_size=self.bid_size,
            ask_size=self.ask_size,
            last_price=self.last_price,
            last_size=self.last_size,
            delayed=self.delayed,
            entitlement=self.entitlement,
            source_time_ns=self.source_time_ns,
            received_time_ns=self.received_time_ns,
        )

    def as_dict(self) -> dict[str, Any]:
        return self.facts().as_dict()


__all__ = ["L1Accumulator"]