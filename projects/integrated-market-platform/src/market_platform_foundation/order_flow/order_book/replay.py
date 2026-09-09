"""Deterministic event-log replay for the canonical L2 book (G5, Checkpoint F).

Replay never reads a wall clock: the book evolves only from the ordered
canonical events, so the same event log reproduces the same levels, the same
validity, and the same ``state_hash()`` on every run and after any restart.
Duplicate events are not double-applied; RESET boundaries and sequence-gap
invalidation replay identically.
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from typing import Any

from .contracts import ApplyResult, DepthUpdate
from .engine import IncrementalOrderBook


def replay(
    events: Iterable[DepthUpdate],
    *,
    instrument_id: str | None = None,
    initial: IncrementalOrderBook | None = None,
) -> IncrementalOrderBook:
    """Replay an ordered event log into a canonical book.

    ``initial`` may carry a pre-existing snapshot/generation; when omitted a
    fresh book is created from the first event's instrument.
    """
    ordered = list(events)
    for event in ordered:
        if not isinstance(event, DepthUpdate):
            raise TypeError(f"replay requires DepthUpdate events, got {type(event).__name__}")
    if initial is not None:
        book = initial
    else:
        resolved = instrument_id or (ordered[0].instrument_id if ordered else "")
        if not resolved:
            raise ValueError("replay requires events or an explicit instrument_id")
        book = IncrementalOrderBook(resolved)
    for event in ordered:
        book.apply(event)
    return book


def replay_with_results(
    events: Iterable[DepthUpdate],
    *,
    instrument_id: str | None = None,
) -> tuple[IncrementalOrderBook, list[ApplyResult]]:
    """Replay and return (final book, per-event ApplyResults)."""
    ordered = list(events)
    resolved = instrument_id or (ordered[0].instrument_id if ordered else "")
    if not resolved:
        raise ValueError("replay requires events or an explicit instrument_id")
    book = IncrementalOrderBook(resolved)
    results: list[ApplyResult] = []
    for event in ordered:
        results.append(book.apply(event))
    return book, results


def replay_state_hash(events: Iterable[DepthUpdate]) -> str:
    """Deterministic state hash after replay (same log → same hash)."""
    book = replay(events)
    return book.state_hash()


def measure_replay_throughput(
    events: list[DepthUpdate],
    *,
    repeats: int = 3,
) -> dict[str, Any]:
    """Measure replay throughput on representative depth.

    Returns wall-clock evidence only (``PERFORMANCE_MEASURED``, not a
    production-throughput claim).
    """
    event_count = len(events)
    start = time.perf_counter()
    book = None
    for _ in range(repeats):
        book = replay(events)
    elapsed = time.perf_counter() - start
    per_run = elapsed / max(1, repeats)
    return {
        "event_count": event_count,
        "repeats": repeats,
        "total_seconds": round(elapsed, 6),
        "seconds_per_run": round(per_run, 6),
        "events_per_second": round(event_count / per_run, 1) if per_run > 0 else 0.0,
        "final_book_state_valid": book.book_state_valid if book is not None else None,
        "final_level_counts": list(book.level_counts) if book is not None else None,
        "note": "PERFORMANCE_MEASURED — representative synthetic depth only",
    }


__all__ = ["measure_replay_throughput", "replay", "replay_state_hash", "replay_with_results"]
