"""Bounded pagination for IBKR historical TRADE windows (Lane C / EVIDENCE-HARDENING-02)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

from ...canonical import canonical_bytes, sha256_bytes
from .historical_trades import (
    ObservationalHistoricalTrade,
    normalize_ibkr_historical_trades_payload,
)

DEFAULT_TICKS_PER_PAGE = 1000
DEFAULT_MAX_PAGES = 10
DEFAULT_MIN_INTER_PAGE_INTERVAL_NS = 15_000_000_000  # align with IB historical pacing floor


def trade_order_key(trade: ObservationalHistoricalTrade) -> tuple[int, str, float, float]:
    return (trade.event_time_ns, trade.trade_id, trade.price, trade.size)


def trade_dedup_key(trade: ObservationalHistoricalTrade) -> tuple[int, str, float, float]:
    return (trade.event_time_ns, trade.trade_id, trade.price, trade.size)


def sort_trades_deterministic(
    trades: Sequence[ObservationalHistoricalTrade],
) -> list[ObservationalHistoricalTrade]:
    return sorted(trades, key=trade_order_key)


@dataclass(frozen=True, slots=True)
class HistoricalTradesPageRecord:
    page_index: int
    request_start_time_ns: int
    request_end_time_ns: int
    ticks_requested: int
    trade_count: int
    raw_payload_sha256: str
    continuation_cursor_ns: int | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "page_index": self.page_index,
            "request_start_time_ns": self.request_start_time_ns,
            "request_end_time_ns": self.request_end_time_ns,
            "ticks_requested": self.ticks_requested,
            "trade_count": self.trade_count,
            "raw_payload_sha256": self.raw_payload_sha256,
            "continuation_cursor_ns": self.continuation_cursor_ns,
        }


@dataclass(frozen=True, slots=True)
class HistoricalTradesRetrievalProvenance:
    requested_start_time_ns: int
    requested_end_time_ns: int
    returned_start_time_ns: int | None
    returned_end_time_ns: int | None
    complete: bool
    page_count: int
    total_trade_count: int
    aggregate_content_sha256: str
    pages: tuple[HistoricalTradesPageRecord, ...] = ()
    incomplete_reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "requested_interval_ns": {
                "start": self.requested_start_time_ns,
                "end": self.requested_end_time_ns,
            },
            "returned_interval_ns": {
                "start": self.returned_start_time_ns,
                "end": self.returned_end_time_ns,
            },
            "complete": self.complete,
            "page_count": self.page_count,
            "total_trade_count": self.total_trade_count,
            "aggregate_content_sha256": self.aggregate_content_sha256,
            "pages": [page.as_dict() for page in self.pages],
            "incomplete_reason": self.incomplete_reason,
        }


PageFetchFn = Callable[[int, int, int], Mapping[str, Any]]


def _hash_payload(payload: Mapping[str, Any]) -> str:
    return sha256_bytes(canonical_bytes(dict(payload)))


def _aggregate_content_hash(trades: Sequence[ObservationalHistoricalTrade]) -> str:
    body = [trade.to_dict() for trade in sort_trades_deterministic(trades)]
    return sha256_bytes(canonical_bytes(body))


def paginate_historical_trades(
    fetch_page: PageFetchFn,
    *,
    instrument_id: str,
    window_start_time_ns: int,
    window_end_time_ns: int,
    received_time_ns: int | None = None,
    ticks_per_page: int = DEFAULT_TICKS_PER_PAGE,
    max_pages: int = DEFAULT_MAX_PAGES,
    min_inter_page_interval_ns: int = DEFAULT_MIN_INTER_PAGE_INTERVAL_NS,
    sleep_fn: Callable[[float], None] = time.sleep,
    monotonic_ns_fn: Callable[[], int] = time.monotonic_ns,
) -> tuple[list[ObservationalHistoricalTrade], HistoricalTradesRetrievalProvenance]:
    """Fetch and merge historical TRADE pages with bounded requests and dedup."""
    if window_start_time_ns > window_end_time_ns:
        raise ValueError("INVALID_HISTORICAL_TRADE_WINDOW")
    if ticks_per_page < 1 or max_pages < 1:
        raise ValueError("INVALID_PAGINATION_BOUNDS")

    cursor_ns = int(window_start_time_ns)
    end_ns = int(window_end_time_ns)
    seen: set[tuple[int, str, float, float]] = set()
    merged: list[ObservationalHistoricalTrade] = []
    page_records: list[HistoricalTradesPageRecord] = []
    complete = True
    incomplete_reason: str | None = None
    last_fetch_end_ns = monotonic_ns_fn()

    for page_index in range(max_pages):
        if cursor_ns > end_ns:
            break
        if page_index > 0 and min_inter_page_interval_ns > 0:
            elapsed = monotonic_ns_fn() - last_fetch_end_ns
            remaining = min_inter_page_interval_ns - elapsed
            if remaining > 0:
                sleep_fn(remaining / 1_000_000_000)

        payload = fetch_page(cursor_ns, end_ns, ticks_per_page)
        last_fetch_end_ns = monotonic_ns_fn()
        raw_hash = _hash_payload(payload)
        page_trades = normalize_ibkr_historical_trades_payload(
            payload,
            instrument_id=instrument_id,
            received_time_ns=received_time_ns,
        )
        page_trades = sort_trades_deterministic(page_trades)
        added = 0
        page_max_time: int | None = None
        for trade in page_trades:
            if trade.event_time_ns < cursor_ns or trade.event_time_ns > end_ns:
                continue
            key = trade_dedup_key(trade)
            if key in seen:
                continue
            seen.add(key)
            merged.append(trade)
            added += 1
            page_max_time = (
                trade.event_time_ns
                if page_max_time is None
                else max(page_max_time, trade.event_time_ns)
            )

        next_cursor: int | None = None
        if page_max_time is not None:
            next_cursor = page_max_time + 1

        page_records.append(
            HistoricalTradesPageRecord(
                page_index=page_index,
                request_start_time_ns=cursor_ns,
                request_end_time_ns=end_ns,
                ticks_requested=ticks_per_page,
                trade_count=added,
                raw_payload_sha256=raw_hash,
                continuation_cursor_ns=next_cursor,
            )
        )

        if not page_trades:
            break

        if added == 0 and len(page_trades) >= ticks_per_page:
            complete = False
            incomplete_reason = "STALLED_PAGINATION_CURSOR"
            break

        if len(page_trades) < ticks_per_page:
            break

        if next_cursor is None or next_cursor <= cursor_ns:
            break

        if next_cursor > end_ns:
            break

        if page_index + 1 >= max_pages:
            complete = False
            incomplete_reason = "MAX_PAGES_REACHED"
            break

        cursor_ns = next_cursor

    merged = sort_trades_deterministic(merged)
    returned_start = merged[0].event_time_ns if merged else None
    returned_end = merged[-1].event_time_ns if merged else None
    provenance = HistoricalTradesRetrievalProvenance(
        requested_start_time_ns=window_start_time_ns,
        requested_end_time_ns=window_end_time_ns,
        returned_start_time_ns=returned_start,
        returned_end_time_ns=returned_end,
        complete=complete,
        page_count=len(page_records),
        total_trade_count=len(merged),
        aggregate_content_sha256=_aggregate_content_hash(merged),
        pages=tuple(page_records),
        incomplete_reason=incomplete_reason,
    )
    return merged, provenance


__all__ = [
    "DEFAULT_MAX_PAGES",
    "DEFAULT_MIN_INTER_PAGE_INTERVAL_NS",
    "DEFAULT_TICKS_PER_PAGE",
    "HistoricalTradesPageRecord",
    "HistoricalTradesRetrievalProvenance",
    "paginate_historical_trades",
    "sort_trades_deterministic",
    "trade_dedup_key",
    "trade_order_key",
]
