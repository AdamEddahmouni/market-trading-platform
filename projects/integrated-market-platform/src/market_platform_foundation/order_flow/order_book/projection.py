"""Snapshot compatibility projection for the canonical L2 book (G5, Checkpoint C).

The canonical incremental state is the single source of truth. Existing IMP
consumers (order-flow OFI/liquidity/impact/forecast, provider projections,
whale ledger, UI payloads) still read *snapshot-shaped* dictionaries with
``bids``/``asks`` rows of ``{price, size, ...}`` and a boolean
``book_state_valid``. This module projects the canonical engine state into
that legacy shape deterministically, and ingests legacy snapshot dictionaries
back through the canonical ``replace_from_snapshot`` ingestion mode.

Rules:

- The projection is deterministic: identical engine state → identical dict.
- ``book_state_valid`` is *derived truth* from the engine, never hard-coded.
- Additive compatibility fields expose the richer truth (``book_status``,
  ``sequence_status``, ``generation``, timestamps, ``freshness_status``) so
  downstream safety logic is not forced to guess from the boolean alone.
- Snapshot ingestion (``replace_from_snapshot``) explicitly RESETs old state
  and is never confused with an incremental UPDATE.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping

from .contracts import DepthOperation, DepthSide
from .engine import IncrementalOrderBook


def project_book_snapshot(
    book: IncrementalOrderBook,
    *,
    include_sequence: bool = True,
    include_rows: bool = True,
) -> dict[str, Any]:
    """Project canonical engine state into the legacy snapshot dict shape.

    Bid rows sort descending by price, ask rows ascending — matching the
    ordering the existing order-flow snapshot functions expect.
    """
    bids, asks = book.to_snapshot_rows()
    payload: dict[str, Any] = {
        "asks": asks if include_rows else [],
        "bids": bids if include_rows else [],
        "book_state_valid": book.book_state_valid,
        "book_status": book.validity.value,
        "book_status_reason": book.invalidation_reason.value,
        "generation": book.generation,
        "instrument_id": book.instrument_id,
        "level_count": max(len(bids), len(asks)) if include_rows else 0,
        "model_version": book.model_version,
        "sequence_state": book.sequence_state.value,
        "update_count": book.update_count,
        "reset_count": book.reset_count,
    }
    if include_sequence:
        payload["book_sequence"] = book.last_sequence
    if book.last_source_time_ns is not None:
        payload["last_source_time_ns"] = book.last_source_time_ns
    if book.last_received_time_ns is not None:
        payload["last_received_time_ns"] = book.last_received_time_ns
    if book.best_bid_price is not None:
        payload["best_bid"] = float(book.best_bid_price)
        payload["bid_size"] = float(book.best_bid_size) if book.best_bid_size is not None else None
    if book.best_ask_price is not None:
        payload["best_ask"] = float(book.best_ask_price)
        payload["ask_size"] = float(book.best_ask_size) if book.best_ask_size is not None else None
    return payload


def ingest_snapshot_dict(
    book: IncrementalOrderBook,
    snapshot: Mapping[str, Any],
    *,
    source: str | None = None,
    source_time_ns: int | None = None,
    received_time_ns: int | None = None,
    subscription_id: str | None = None,
) -> Any:
    """Ingest a legacy snapshot dictionary through the canonical engine.

    The canonical engine becomes authoritative: prior state is explicitly
    RESET, levels are loaded, validity is established from the imported state,
    and generation/sequence metadata is recorded. Returns the
    :class:`ApplyResult` from ``replace_from_snapshot``.
    """
    raw_bids = snapshot.get("bids", []) if isinstance(snapshot, dict) else []
    raw_asks = snapshot.get("asks", []) if isinstance(snapshot, dict) else []
    sequence = snapshot.get("book_sequence") if isinstance(snapshot, dict) else None
    if sequence is not None and (isinstance(sequence, bool) or not isinstance(sequence, int)):
        sequence = None
    return book.replace_from_snapshot(
        bids=_rows(raw_bids),
        asks=_rows(raw_asks),
        sequence=sequence,
        subscription_id=subscription_id,
        source_time_ns=source_time_ns,
        received_time_ns=received_time_ns,
        provider=source,
    )


def _rows(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, Mapping):
            rows.append({"price": item.get("price"), "size": item.get("size")})
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            rows.append({"price": item[0], "size": item[1]})
    return rows


def best_bid_ask(book: IncrementalOrderBook) -> tuple[Decimal | None, Decimal | None]:
    return book.best_bid_price, book.best_ask_price


def level_rows(book: IncrementalOrderBook) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return book.to_snapshot_rows()


__all__ = [
    "DepthOperation",
    "DepthSide",
    "best_bid_ask",
    "ingest_snapshot_dict",
    "level_rows",
    "project_book_snapshot",
]
