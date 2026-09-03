"""Shared BUILD 06 signal test fixtures."""

from __future__ import annotations

from market_platform_foundation.intelligence.contracts import (
    ContractReference,
    IntelligenceScope,
    QualityState,
    QualitySummary,
    SnapshotV1,
)
from market_platform_foundation.intelligence.snapshots.resolver import SnapshotResolvedState
from tests.intelligence.test_persistence_fixtures import DECISION_NS, INSTRUMENT, QUALITY, SCOPE, sample_event

T = DECISION_NS
WINDOW = 300 * 1_000_000_000
ONE_SEC = 1_000_000_000


def quote_event(
    event_id: str,
    *,
    event_time_ns: int,
    bid: float = 100.0,
    ask: float = 100.10,
    bid_size: float = 500,
    ask_size: float = 400,
    available_time_ns: int | None = None,
) -> object:
    return sample_event(
        event_id,
        event_type="QUOTE",
        event_time_ns=event_time_ns,
        available_time_ns=available_time_ns or event_time_ns,
        payload={
            "bid": bid,
            "ask": ask,
            "bid_size": bid_size,
            "ask_size": ask_size,
        },
    )


def trade_event(
    event_id: str,
    *,
    event_time_ns: int,
    price: float,
    quantity: float,
    aggressor_side: str | None = None,
    available_time_ns: int | None = None,
) -> object:
    payload: dict = {"price": price, "quantity": quantity}
    if aggressor_side is not None:
        payload["aggressor_side"] = aggressor_side
    return sample_event(
        event_id,
        event_type="TRADE",
        event_time_ns=event_time_ns,
        available_time_ns=available_time_ns or event_time_ns,
        payload=payload,
    )


def book_event(
    event_id: str,
    *,
    event_time_ns: int,
    bids: list[dict],
    asks: list[dict],
    available_time_ns: int | None = None,
) -> object:
    return sample_event(
        event_id,
        event_type="BOOK",
        event_time_ns=event_time_ns,
        available_time_ns=available_time_ns or event_time_ns,
        payload={"bids": bids, "asks": asks},
    )


def resolved_snapshot(
    snapshot_id: str,
    *,
    decision_time_ns: int = T,
    events: tuple = (),
    quality: QualitySummary = QUALITY,
) -> SnapshotResolvedState:
    snapshot = SnapshotV1(
        snapshot_id=snapshot_id,
        schema_version="1",
        decision_time_ns=decision_time_ns,
        scope=SCOPE,
        quality=quality,
        source_event_refs=tuple(
            ContractReference(kind="event", id=event.event_id) for event in events
        ),
    )
    return SnapshotResolvedState(snapshot=snapshot, events=events, signals=())


__all__ = [
    "INSTRUMENT",
    "ONE_SEC",
    "SCOPE",
    "T",
    "WINDOW",
    "book_event",
    "quote_event",
    "resolved_snapshot",
    "trade_event",
]
