"""Universe-wide ETF market snapshot for server-side filtering and sorting (S6).

A market filter such as ``Price > 100`` is truthful only when every candidate
row was evaluated by the same source. This module asks OpenD for a bounded
``get_market_snapshot`` of every catalog ETF (400 codes per call) and records,
per row, whether the provider returned it or refused it by name (an OTC
listing without quote entitlement). The snapshot is ``complete`` only when every
catalog row is accounted for; anything else (disconnect, protocol error, call
budget) makes it unusable and snapshot fields are refused rather than evaluated
on a partial set. Visible-row streaming quotes never feed this snapshot.
"""

from __future__ import annotations

import math
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Callable
from zoneinfo import ZoneInfo

from ..market_data.observational_state import _overnight_snapshot

ET = ZoneInfo("America/New_York")
SOURCE = "MOOMOO_OPEND_SNAPSHOT"
SNAPSHOT_TTL_SECONDS = 60          # a new result chain re-snapshots after this age
SNAPSHOT_MIN_REFRESH_SECONDS = 15  # explicit refresh cannot re-snapshot faster
SNAPSHOT_FAILURE_TTL_SECONDS = 30  # a failed build is not retried on every keystroke
SNAPSHOT_BATCH = 400               # vendor maximum codes per request
SNAPSHOT_MAX_CALLS = 50            # below the vendor's 60 snapshot requests / 30 s
SNAPSHOT_RETAINED = 3              # pinned page chains keep their snapshot
SNAPSHOT_STALE_AFTER = timedelta(days=7)  # a quote untouched this long is not current


def _finite(raw: Any) -> float | None:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _provider_time(raw: Any) -> datetime | None:
    text = str(raw or "")[:19]
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=ET).astimezone(UTC)
    except ValueError:
        return None


def snapshot_values(source: dict[str, Any], taken_at: datetime) -> tuple[dict[str, float | None], str | None]:
    """Canonical fields from one vendor snapshot row plus the row's provider clock."""

    updated = _provider_time(source.get("update_time"))
    if updated is None or taken_at - updated > SNAPSHOT_STALE_AFTER:
        return dict.fromkeys(("price", "change_pct", "volume", "bid", "ask", "spread_pct")), None
    price = _finite(source.get("last_price"))
    price = price if price is not None and price > 0 else None
    previous = _finite(source.get("prev_close_price"))
    bid, ask = _finite(source.get("bid_price")), _finite(source.get("ask_price"))
    if _overnight_snapshot(source):
        # Overnight the vendor book is the frozen after-hours close, not a current market.
        bid = ask = None
    bid = bid if bid is not None and bid > 0 else None
    ask = ask if ask is not None and ask > 0 else None
    spread = (ask - bid) / ((ask + bid) / 2) * 100 if bid is not None and ask is not None and ask >= bid else None
    volume = _finite(source.get("volume"))
    return ({"price": price,
             "change_pct": (price - previous) / previous * 100 if price is not None and previous and previous > 0 else None,
             "volume": volume if volume is not None and volume >= 0 else None,
             "bid": bid, "ask": ask, "spread_pct": spread},
            updated.isoformat().replace("+00:00", "Z"))


@dataclass(slots=True)
class MarketSnapshot:
    id: str
    as_of: str
    total: int
    values: dict[str, dict[str, float | None]]
    row_as_of: dict[str, str | None]
    refused: frozenset[str]
    calls: int
    duration_ms: float
    taken_monotonic: float
    catalog_as_of: str
    priced: int = field(init=False)

    def __post_init__(self) -> None:
        self.priced = sum(1 for item in self.values.values() if item.get("price") is not None)

    def value(self, instrument_id: str, name: str) -> float | None:
        return self.values.get(instrument_id, {}).get(name)

    def summary(self) -> dict[str, Any]:
        return {"id": self.id, "as_of": self.as_of, "source": SOURCE, "complete": True,
                "total": self.total, "returned": len(self.values), "priced": self.priced,
                "refused": len(self.refused), "refused_reason": "MOOMOO_QUOTE_NOT_ENTITLED" if self.refused else None,
                "calls": self.calls, "duration_ms": round(self.duration_ms, 1)}


class EtfSnapshotSource:
    """Builds, caches, and retains complete ETF snapshots; one build at a time."""

    def __init__(self, *, transport_getter: Callable[[], Any | None],
                 clock: Callable[[], float] = time.monotonic,
                 wall: Callable[[], datetime] = lambda: datetime.now(UTC),
                 prefix: str = "etf", require_complete: bool = True) -> None:
        self._transport_getter = transport_getter
        self._prefix = prefix
        # The ETF catalog is the vendor's own list, so a code it does not return is a failed
        # snapshot. An equity list from another source may name codes the vendor does not carry;
        # those rows simply have no value.
        self._require_complete = require_complete
        self._clock = clock
        self._wall = wall
        self._build_lock = threading.Lock()
        self._lock = threading.RLock()
        self._retained: OrderedDict[str, MarketSnapshot] = OrderedDict()
        self._known_refused: set[str] = set()
        self._failure: tuple[float, str] | None = None
        self._sequence = 0

    def retained(self, snapshot_id: str) -> MarketSnapshot | None:
        with self._lock:
            return self._retained.get(snapshot_id)

    def latest(self) -> MarketSnapshot | None:
        with self._lock:
            return next(reversed(self._retained.values()), None)

    def current(self, rows: list[dict[str, Any]], *, catalog_as_of: str,
                force: bool = False) -> tuple[MarketSnapshot | None, str | None]:
        """A complete snapshot no older than the TTL for this catalog, or the reason there is none."""

        with self._build_lock:
            latest = self.latest()
            age = self._clock() - latest.taken_monotonic if latest else math.inf
            fresh_enough = age < (SNAPSHOT_MIN_REFRESH_SECONDS if force else SNAPSHOT_TTL_SECONDS)
            if latest and latest.catalog_as_of == catalog_as_of and fresh_enough:
                return latest, None
            failure = self._failure
            if failure and not force and self._clock() - failure[0] < SNAPSHOT_FAILURE_TTL_SECONDS:
                return None, failure[1]
            snapshot, reason = self._build(rows, catalog_as_of=catalog_as_of)
            with self._lock:
                if snapshot is None:
                    self._failure = (self._clock(), reason or "MARKET_SNAPSHOT_UNAVAILABLE")
                    return None, self._failure[1]
                self._failure = None
                self._retained[snapshot.id] = snapshot
                while len(self._retained) > SNAPSHOT_RETAINED:
                    self._retained.popitem(last=False)
            return snapshot, None

    def _build(self, rows: list[dict[str, Any]], *, catalog_as_of: str) -> tuple[MarketSnapshot | None, str | None]:
        transport = self._transport_getter()
        fetch = getattr(transport, "fetch_market_snapshot", None) if transport is not None else None
        if not callable(fetch):
            return None, "MARKET_SNAPSHOT_UNAVAILABLE"
        if not rows:
            return None, "MARKET_SNAPSHOT_UNAVAILABLE"
        by_code = {row["provider_symbol"]: row["instrument"]["instrument_id"] for row in rows}
        with self._lock:
            refused = {code for code in self._known_refused if code in by_code}
        pending = [code for code in by_code if code not in refused]
        started, calls = self._clock(), 0
        vendor: dict[str, dict[str, Any]] = {}
        for index in range(0, len(pending), SNAPSHOT_BATCH):
            batch = pending[index:index + SNAPSHOT_BATCH]
            while batch:
                if calls >= SNAPSHOT_MAX_CALLS:
                    with self._lock:
                        # Keep what this attempt learned so the next one spends no calls on it.
                        self._known_refused |= refused
                    return None, "MARKET_SNAPSHOT_CALL_BUDGET"
                calls += 1
                try:
                    result = fetch(batch)
                except Exception:  # noqa: BLE001 — provider boundary fails closed
                    return None, "MARKET_SNAPSHOT_UNAVAILABLE"
                named = [code for code in result.get("refused_codes") or [] if code in batch]
                if result.get("reason_code"):
                    if not named:
                        return None, str(result["reason_code"])
                    refused.update(named)
                    batch = [code for code in batch if code not in named]
                    continue
                for item in result.get("rows") or []:
                    vendor[str(item.get("code"))] = item
                break
        # Complete means every catalog code was returned or refused by name.
        missing = [code for code in pending if code not in vendor and code not in refused]
        if missing and self._require_complete:
            return None, "MARKET_SNAPSHOT_INCOMPLETE"
        taken = self._wall()
        values: dict[str, dict[str, float | None]] = {}
        row_as_of: dict[str, str | None] = {}
        for code, item in vendor.items():
            canonical = by_code[code]
            values[canonical], row_as_of[canonical] = snapshot_values(item, taken)
        with self._lock:
            self._known_refused |= refused
            self._sequence += 1
            sequence = self._sequence
        as_of = taken.isoformat().replace("+00:00", "Z")
        return MarketSnapshot(id=f"{self._prefix}-{sequence}-{int(taken.timestamp())}", as_of=as_of, total=len(by_code),
                              values=values, row_as_of=row_as_of,
                              refused=frozenset(by_code[code] for code in refused),
                              calls=calls, duration_ms=(self._clock() - started) * 1000,
                              taken_monotonic=self._clock(), catalog_as_of=catalog_as_of), None
