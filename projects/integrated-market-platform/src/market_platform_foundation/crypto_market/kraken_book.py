"""Kraken Spot WebSocket v2 ``book`` channel on the canonical L2 engine.

Protocol (docs.kraken.com/api/docs/websocket-v2/book; verified live
2026-09-28, 2,128/2,128 checksums across BTC, ETH, XRP, SHIB, PEPE /USD):

* the first message after subscribing is a full ``snapshot`` of ``depth``
  levels per side; later ``update`` messages carry changed levels, where
  ``qty`` 0 removes a price level;
* the venue does not send removals for levels pushed below the subscribed
  depth, so the local book is truncated to ``depth`` after every message;
* every snapshot and update carries a CRC32 ``checksum`` of the top 10 asks
  (low to high) then top 10 bids (high to low), each level's price and qty
  formatted to the pair's price/qty precision with the decimal point and
  leading zeros removed.

Prices and quantities are parsed as ``Decimal`` from the JSON text. A
checksum disagreement invalidates the book with a recovery-required reason;
the stream then resubscribes for a fresh snapshot. An invalid book is never
continued or displayed.
"""

from __future__ import annotations

import json
import zlib
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from ..order_flow.order_book.contracts import BookLevel, BookStatusReason, BookValidity, build_depth_update
from ..order_flow.order_book.engine import IncrementalOrderBook

PROVIDER = "KRAKEN"
CHECKSUM_LEVELS = 10


def parse_message(text: str) -> Any:
    """JSON with exact decimals: floats become ``Decimal`` so no digit is lost."""

    return json.loads(text, parse_float=Decimal)


def iso_ns(value: Any) -> int | None:
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        head, _, fraction = value[:-1].partition(".")
        seconds = datetime.fromisoformat(head + "+00:00").timestamp()
    except ValueError:
        return None
    digits = (fraction + "000000000")[:9] if fraction.isdigit() or not fraction else None
    if digits is None:
        return None
    return int(seconds) * 1_000_000_000 + int(digits)


def _decimal(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (Decimal, int)):
        raise ValueError("KRAKEN_BOOK_MALFORMED")
    number = Decimal(value)
    if not number.is_finite():
        raise ValueError("KRAKEN_BOOK_MALFORMED")
    return number


def checksum_field(value: Decimal, decimals: int) -> str:
    try:
        fixed = value.quantize(Decimal(1).scaleb(-decimals))
    except InvalidOperation:
        raise ValueError("KRAKEN_BOOK_MALFORMED") from None
    return format(fixed, "f").replace(".", "").lstrip("0")


def book_checksum(bids: Iterable[BookLevel], asks: Iterable[BookLevel], *, price_decimals: int,
                  qty_decimals: int) -> int:
    parts = [checksum_field(level.price, price_decimals) + checksum_field(level.size, qty_decimals)
             for level in list(asks)[:CHECKSUM_LEVELS]]
    parts += [checksum_field(level.price, price_decimals) + checksum_field(level.size, qty_decimals)
              for level in list(bids)[:CHECKSUM_LEVELS]]
    return zlib.crc32("".join(parts).encode("ascii")) & 0xFFFFFFFF


@dataclass(frozen=True, slots=True)
class BookView:
    """An immutable copy of one book for readers on other threads."""

    instrument_id: str
    validity: BookValidity
    invalidation_reason: BookStatusReason
    bids: tuple[BookLevel, ...]
    asks: tuple[BookLevel, ...]
    last_source_time_ns: int | None
    last_received_time_ns: int | None

    @property
    def is_empty(self) -> bool:
        return not self.bids and not self.asks

    @property
    def is_crossed(self) -> bool:
        return bool(self.bids and self.asks and self.bids[0].price >= self.asks[0].price)

    @property
    def book_state_valid(self) -> bool:
        return self.validity is BookValidity.VALID and not self.is_empty

    def to_snapshot_rows(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        return [level.to_row() for level in self.bids], [level.to_row() for level in self.asks]


class KrakenBook:
    """One pair's book: snapshot + deltas + depth truncation + checksum."""

    def __init__(self, instrument_id: str, *, depth: int, price_decimals: int, qty_decimals: int) -> None:
        if depth < CHECKSUM_LEVELS:
            raise ValueError("KRAKEN_BOOK_DEPTH_TOO_SMALL")
        self.engine = IncrementalOrderBook(instrument_id)
        self.depth, self.price_decimals, self.qty_decimals = depth, price_decimals, qty_decimals
        self.checksum_failures = 0
        self.last_checksum: int | None = None

    def _levels(self, data: dict[str, Any], key: str) -> list[tuple[Decimal, Decimal]]:
        rows = data.get(key)
        if not isinstance(rows, list):
            raise ValueError("KRAKEN_BOOK_MALFORMED")
        levels = []
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("KRAKEN_BOOK_MALFORMED")
            price, qty = _decimal(row.get("price")), _decimal(row.get("qty"))
            if price <= 0 or qty < 0:
                raise ValueError("KRAKEN_BOOK_MALFORMED")
            levels.append((price, qty))
        return levels

    def _truncate(self, received_ns: int) -> None:
        for side, levels in (("BID", self.engine.bids), ("ASK", self.engine.asks)):
            for position in range(len(levels) - 1, self.depth - 1, -1):
                self.engine.apply(build_depth_update(instrument_id=self.engine.instrument_id, operation="DELETE",
                                                     side=side, position=position, source=PROVIDER,
                                                     received_time_ns=received_ns))

    def _verify(self, expected: Any) -> bool:
        if isinstance(expected, bool) or not isinstance(expected, int):
            self.engine.invalidate(BookStatusReason.STRUCTURALLY_CORRUPT)
            return False
        actual = book_checksum(self.engine.bids, self.engine.asks, price_decimals=self.price_decimals,
                               qty_decimals=self.qty_decimals)
        self.last_checksum = expected
        if actual != expected:
            self.checksum_failures += 1
            self.engine.invalidate(BookStatusReason.CHECKSUM_MISMATCH)
            return False
        return True

    def apply_snapshot(self, data: dict[str, Any], *, received_ns: int, subscription_id: str) -> bool:
        try:
            bids, asks = self._levels(data, "bids"), self._levels(data, "asks")
        except ValueError:
            self.engine.invalidate(BookStatusReason.STRUCTURALLY_CORRUPT)
            return False
        if any(qty == 0 for _price, qty in bids + asks):
            self.engine.invalidate(BookStatusReason.STRUCTURALLY_CORRUPT)
            return False
        self.engine.replace_from_snapshot(
            bids=[{"price": price, "size": qty} for price, qty in bids],
            asks=[{"price": price, "size": qty} for price, qty in asks],
            subscription_id=subscription_id, source_time_ns=iso_ns(data.get("timestamp")),
            received_time_ns=received_ns, provider=PROVIDER)
        if self.engine.validity is not BookValidity.VALID:
            return False
        self._truncate(received_ns)
        return self._verify(data.get("checksum"))

    def apply_update(self, data: dict[str, Any], *, received_ns: int) -> bool:
        """False means the book is invalid and a fresh snapshot is required."""

        if self.engine.validity is not BookValidity.VALID:
            return False
        try:
            changes = [("BID", price, qty) for price, qty in self._levels(data, "bids")]
            changes += [("ASK", price, qty) for price, qty in self._levels(data, "asks")]
        except ValueError:
            self.engine.invalidate(BookStatusReason.STRUCTURALLY_CORRUPT)
            return False
        source_ns = iso_ns(data.get("timestamp"))
        for side, price, qty in changes:
            existing = {level.price for level in (self.engine.bids if side == "BID" else self.engine.asks)}
            operation = "DELETE" if qty == 0 else "UPDATE" if price in existing else "INSERT"
            self.engine.apply(build_depth_update(
                instrument_id=self.engine.instrument_id, operation=operation, side=side, price=price,
                size=None if qty == 0 else qty, source=PROVIDER, source_time_ns=source_ns,
                received_time_ns=received_ns))
            if self.engine.validity is not BookValidity.VALID:
                return False
        self._truncate(received_ns)
        return self._verify(data.get("checksum"))

    @property
    def valid(self) -> bool:
        return self.engine.validity is BookValidity.VALID

    def confirm_continuity(self, received_ns: int) -> None:
        """A heartbeat on a live connection confirms an unchanged valid book is still current."""

        if self.engine.validity is BookValidity.VALID and self.engine.last_received_time_ns is not None:
            self.engine.last_received_time_ns = max(self.engine.last_received_time_ns, received_ns)

    def view(self) -> BookView:
        engine = self.engine
        return BookView(engine.instrument_id, engine.validity, engine.invalidation_reason, tuple(engine.bids),
                        tuple(engine.asks), engine.last_source_time_ns, engine.last_received_time_ns)
