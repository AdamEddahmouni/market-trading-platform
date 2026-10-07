"""Provider-neutral, current-market US-equity screener projection.

Finviz supplies a broad published snapshot. Moomoo L1 is read only for a
bounded viewport; the two sources retain separate field provenance.
"""

from __future__ import annotations

import math
import threading
import time
from collections import OrderedDict
from datetime import UTC, datetime
from typing import Any, Callable

from ..finviz.screener import FinvizScreenerClient, FinvizScreenerRow
from ..finviz.config import DEFAULT_SCREENER_COLUMNS
from ..finviz.symbols import finviz_to_canonical
from ..market_data.live_runtime import get_live_runtime, provider_symbol_for
from ..market_data.subscription_manager import SubscriptionPriority
from ..market_sessions import us_equity_screener_session
from .screener_admission import UNAVAILABLE_REFERENCE, ClassificationReference, admission_summary, admit_equity
from .screener_filters import apply_filters, field_value
from .screener_query import DEFAULT_PAGE_LIMIT, exact_matches_first, order_rows, page_payload, parse_query
from .screener_snapshot import SOURCE as QUOTE_SNAPSHOT_SOURCE
from .screener_snapshot import EtfSnapshotSource, MarketSnapshot

SCHEMA_VERSION = "screener/1.0.0"
UNIVERSE = "US_EQUITIES"
# S13: the export is every US listing, including funds. Admission (ETFs out,
# REITs / closed-end funds / BDCs in) is an IMP rule in screener_admission,
# not Finviz's opaque "Stocks only (ex-Funds)" filter; the same export is the
# classification reference that keeps REITs and CEFs out of US_ETFS.
FILTER = "geo_usa"
# Verified export IDs: ticker, company, sector, industry, country, cap, float,
# short float, short ratio, RSI, RVOL, price, change, and volume.
SCREENER_COLUMNS = ",".join(dict.fromkeys(("1,2,3,4,5,6,25,30,31,59,64,65,66,67," + DEFAULT_SCREENER_COLUMNS).split(",")))
MAX_WINDOW = 32
# Finviz carries no bid/ask; these filter and sort through one OpenD snapshot of the universe.
QUOTE_SNAPSHOT_FIELDS = ("bid", "ask", "spread_pct")
QUOTE_EVENT_STALE_MS = 60_000  # no provider quote update for a minute is stale, however often it is polled
RESULT_CACHE_ENTRIES = 16  # ordered result references per query identity, never row copies
SNAPSHOT_TTL_SECONDS = 120
CLIENT_TTL_SECONDS = 45
FIELD_NAMES = (
    "price", "change_pct", "volume", "rel_volume", "float_shares",
    "market_cap", "short_float_pct", "rsi_14", "avg_volume",
    "shares_outstanding", "short_ratio", "eps_ttm", "pe", "fwd_pe", "perf_week",
)


def _iso_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def pending_quote_reason(runtime: Any, instrument_id: str) -> str:
    """Why an accepted quote subscription has no quote yet: the feed's real state, not a blanket wait."""

    from .screener_specialist import _PERMISSION_WORDS, _QUOTA_WORDS, DISCONNECTED_STATES

    lifecycle = getattr(runtime, "lifecycle", None)
    connection = str(getattr(getattr(lifecycle, "connection_state", None), "value",
                             getattr(lifecycle, "connection_state", ""))).upper()
    if getattr(runtime, "feed", None) is None or connection in DISCONNECTED_STATES - {"CONNECTING"}:
        return "OPEND_UNAVAILABLE"
    errors = getattr(runtime.feed, "subscription_errors", {}) or {}
    refusal = next((value for (code, name), value in errors.items()
                    if name == "QUOTE" and code.split(".")[-1].upper() == instrument_id.upper()), None)
    if refusal is not None:
        message = str(refusal.get("message") or "").lower()
        if any(word in message for word in _PERMISSION_WORDS):
            return "ENTITLEMENT_MISSING"
        if any(word in message for word in _QUOTA_WORDS):
            return "PROVIDER_QUOTA_EXHAUSTED"
        return "PROVIDER_SUBSCRIBE_REFUSED"
    return "AWAITING_QUOTE"


def quote_view(runtime: Any, quote: Any) -> dict[str, Any]:
    """Current L1 quote with its own state/age; stale quotes are never labelled LIVE."""

    now_ns = time.time_ns()
    received_age_ms = max(0, (now_ns - int(quote.received_ns)) // 1_000_000)
    # A provider event time (snapshot update_time) dates the quote itself; receipt only proves the feed
    # is polling. Without one, receipt age is the only clock available.
    event_ns = int(getattr(quote, "event_time_ns", 0) or 0)
    has_event_time = bool(event_ns) and event_ns != int(quote.received_ns)
    age_ms = max(0, (now_ns - event_ns) // 1_000_000) if has_event_time else received_age_ms
    quality = str(quote.quality or "UNKNOWN").upper()
    admission = str(quote.admission or "UNKNOWN").upper()
    connection = str(getattr(getattr(runtime, "lifecycle", None), "connection_state", "AVAILABLE")).upper()
    reason: str | None = quality
    if "DISCONNECTED" in connection or "RECONNECTING" in connection:
        state, reason = "STALE", connection.rsplit(".", 1)[-1]
    elif received_age_ms > 5_000:
        state, reason = "STALE", "FEED_SILENT"
    elif has_event_time and age_ms > QUOTE_EVENT_STALE_MS:
        state, reason = "STALE", "NO_QUOTE_UPDATE_WITHIN_TTL"
    elif "DELAY" in quality:
        state = "DELAYED"
    elif admission in ("BLOCKED", "DEGRADED") or quality not in ("PASS", "GOOD"):
        state = "UNAVAILABLE"
    else:
        state = "LIVE"
    bid, ask = _number(quote.bid_price), _number(quote.ask_price)
    spread = (ask - bid) / ((ask + bid) / 2) * 100 if bid is not None and ask is not None and ask >= bid and ask + bid > 0 else None
    values = {"price": _number(quote.last_price), "volume": _number(quote.volume), "bid": bid, "ask": ask, "spread_pct": spread}
    book_received_ns = int(getattr(quote, "book_received_ns", 0) or quote.received_ns)
    # The cache retains only receipt time for a book carried through a later
    # last-price push. Never manufacture its provider clock from that push.
    def field(name: str, value: float | None) -> dict[str, Any]:
        is_book = name in ("bid", "ask", "spread_pct")
        received_ns = book_received_ns if is_book else int(quote.received_ns)
        observed_ns = event_ns if has_event_time and (not is_book or received_ns == int(quote.received_ns)) else None
        return {"value": value, "source": str(quote.provider or "MOOMOO"),
                "state": state if value is not None else "UNAVAILABLE",
                "as_of_ns": observed_ns or received_ns,
                "event_time_ns": observed_ns,
                "provider_as_of": datetime.fromtimestamp(observed_ns / 1e9, UTC).isoformat().replace("+00:00", "Z") if observed_ns else None,
                "received_ns": received_ns}
    return {
        "state": state, "age_ms": age_ms, "reason": None if state == "LIVE" else reason,
        "quality": quality, "admission": admission,
        "fields": {name: field(name, value) for name, value in values.items()},
    }


def _snapshot_row(row: FinvizScreenerRow, as_of: str, classification: dict[str, Any] | None = None) -> dict[str, Any]:
    identity = finviz_to_canonical(row.ticker)
    fields = {
        name: {
            "value": getattr(row, name),
            "source": "FINVIZ_ELITE",
            "state": "SNAPSHOT" if getattr(row, name) is not None else "UNAVAILABLE",
            "as_of": as_of,
        }
        for name in FIELD_NAMES
    }
    return {
        "instrument": {
            "instrument_id": identity.instrument_id,
            "venue_id": identity.venue_id,
            "asset_class": "EQUITY",
            "instrument_kind": "TRADABLE_SECURITY",
        },
        "symbol": row.ticker,
        "company": row.company,
        "sector": row.sector or None,
        "industry": row.industry or None,
        "country": row.country or None,
        "earnings_date": row.earnings_date or None,
        "recommendation": row.recommendation or None,
        # S13 provenance: why this listing is in US Equities (backend/debug metadata).
        "classification": classification or admit_equity(row, as_of=as_of).classification,
        "fields": fields,
    }


def _quote_transport() -> Any | None:
    from ..market_data.current_bars import current_bars_service

    return current_bars_service().transport()


def _with_quote_snapshot(row: dict[str, Any], snapshot: MarketSnapshot) -> dict[str, Any]:
    """A page row carrying the bid/ask/spread it was filtered and ordered by."""

    identity = row["instrument"]["instrument_id"]
    as_of = snapshot.row_as_of.get(identity)
    fields = dict(row["fields"])
    for name in QUOTE_SNAPSHOT_FIELDS:
        value = snapshot.value(identity, name)
        fields[name] = {"value": value, "source": QUOTE_SNAPSHOT_SOURCE,
                        "state": "SNAPSHOT" if value is not None else "UNAVAILABLE",
                        "as_of": as_of if value is not None else None}
    return {**row, "fields": fields}


def with_current_quote(row: dict[str, Any], quote: dict[str, Any]) -> dict[str, Any]:
    """Join trusted, already-owned L1 fields without mutating reference/order caches.

    A retained stale/delayed/timeless observation remains visibly its own source;
    decision eligibility is independently evaluated at the consumer cutoff.
    Missing quote fields do not erase legitimate reference fields.
    """
    live = {name: value for name, value in quote.get("fields", {}).items()
            if name in ("price", "volume", "bid", "ask", "spread_pct")
            and value.get("value") is not None}
    return {**row, "fields": {**row["fields"], **live}} if live else row


class ScreenerService:
    """Own one snapshot cache and independent, expiring viewport subscriptions."""

    def __init__(
        self,
        *,
        source_factory: Callable[[], Any] = FinvizScreenerClient,
        runtime_getter: Callable[..., Any | None] = get_live_runtime,
        monotonic: Callable[[], float] = time.monotonic,
        now: Callable[[], str] = _iso_now,
        quote_transport_getter: Callable[[], Any | None] = _quote_transport,
    ) -> None:
        self._quotes = EtfSnapshotSource(transport_getter=quote_transport_getter, clock=monotonic,
                                         prefix="eq", require_complete=False)
        self._source_factory = source_factory
        self._runtime_getter = runtime_getter
        self._monotonic = monotonic
        self._now = now
        self._lock = threading.RLock()
        self._rows: list[dict[str, Any]] = []
        self._as_of: str | None = None
        self._last_fetch = 0.0
        self._error: str | None = None
        self._reference: ClassificationReference = UNAVAILABLE_REFERENCE
        self._admission: dict[str, Any] | None = None
        self._previous: tuple[str | None, list[dict[str, Any]]] = (None, [])
        self._ordered: OrderedDict[tuple[str | None, str | None, str], list[dict[str, Any]]] = OrderedDict()
        self._clients: dict[str, tuple[set[str], float, Any]] = {}
        self._expiry_timer: threading.Timer | None = None

    def _schedule_expiry(self) -> None:
        if self._expiry_timer is not None or not self._clients:
            return
        timer = threading.Timer(CLIENT_TTL_SECONDS, self._expire_clients)
        timer.daemon = True
        self._expiry_timer = timer
        timer.start()

    def _expire_clients(self) -> None:
        with self._lock:
            self._expiry_timer = None
            now = self._monotonic()
            for expired, (_, seen, _) in list(self._clients.items()):
                if now - seen >= CLIENT_TTL_SECONDS:
                    self._release(expired)
            self._schedule_expiry()

    def _refresh(self, *, force: bool = False) -> None:
        if not force and self._last_fetch and self._monotonic() - self._last_fetch < SNAPSHOT_TTL_SECONDS:
            return
        self._last_fetch = self._monotonic()
        try:
            export = self._source_factory().fetch_export(filter_expr=FILTER, columns=SCREENER_COLUMNS)
            if not export.get("success"):
                self._error = str(export.get("error") or "SOURCE_UNAVAILABLE")
                return
            as_of = str(export.get("received_at") or self._now())
            if self._as_of is not None and self._as_of != as_of:
                self._previous = (self._as_of, self._rows)
            decisions = [(row, admit_equity(row, as_of=as_of)) for row in export["rows"]]
            self._rows = [_snapshot_row(row, as_of, decision.classification)
                          for row, decision in decisions if decision.admitted]
            self._reference = ClassificationReference.build(export["rows"], as_of=as_of)
            self._admission = admission_summary(UNIVERSE, (decision for _row, decision in decisions),
                                                reference_as_of=as_of)
            self._as_of = as_of
            self._ordered.clear()
            self._error = None
        except Exception as exc:
            self._error = type(exc).__name__

    def read(
        self, *, universe: str = UNIVERSE, search: str = "",
        sort: str = "volume", descending: bool = True,
        offset: int = 0, limit: int = DEFAULT_PAGE_LIMIT, force_refresh: bool = False,
        filters: list[dict[str, Any]] | None = None, result_set: str | None = None,
        selected: str | None = None,
    ) -> dict[str, Any]:
        if universe != UNIVERSE:
            raise ValueError("UNSUPPORTED_UNIVERSE")
        query = parse_query(universe=universe, search=search, sort=sort, descending=descending,
                            offset=offset, limit=limit, filters=filters, result_set=result_set, selected=selected)
        uses_quotes = query.sort in QUOTE_SNAPSHOT_FIELDS or any(
            rule["field"] in QUOTE_SNAPSHOT_FIELDS for rule in query.filters)
        snapshot: MarketSnapshot | None = None
        snapshot_error: str | None = None
        with self._lock:
            if query.result_set is not None:
                # A later page reads the exact snapshot its first page was ordered from.
                token, _, snapshot_id = query.result_set.partition("|")
                pinned = next(((as_of, rows) for as_of, rows in ((self._as_of, self._rows), self._previous)
                               if as_of is not None and as_of == token), None)
                snapshot = self._quotes.retained(snapshot_id) if snapshot_id else None
                if pinned is None or bool(snapshot_id) != uses_quotes or (snapshot_id and snapshot is None):
                    raise ValueError("RESULT_SET_CHANGED")
                as_of, source_rows = pinned
            else:
                self._refresh(force=force_refresh)
                as_of, source_rows = self._as_of, self._rows
            admission, error = self._admission, self._error
        if uses_quotes and query.result_set is None and source_rows:
            # Outside the lock: the snapshot is a dozen provider calls and must not stall quote windows.
            snapshot, snapshot_error = self._quotes.current(
                [{"provider_symbol": provider_symbol_for(row["instrument"]["instrument_id"]),
                  "instrument": row["instrument"]} for row in source_rows],
                catalog_as_of=str(as_of), force=force_refresh)
        envelope = {
            "schema_version": SCHEMA_VERSION,
            "universe": UNIVERSE,
            "generated_at": self._now(),
            "market_session": us_equity_screener_session(),
            "universe_as_of": as_of,
            "screener_as_of": as_of,
            "evaluation": "SNAPSHOT",
            "snapshot": snapshot.summary() if snapshot else None,
            "unfiltered_count": len(source_rows),
            "admission": admission,
            "provider_health": [{
                "provider": "FINVIZ_ELITE",
                "state": "DEGRADED" if error and source_rows else "UNAVAILABLE" if error else "HEALTHY",
                "reason": error,
            }, *([{"provider": QUOTE_SNAPSHOT_SOURCE, "role": "MARKET_SNAPSHOT",
                   "state": "UNAVAILABLE" if snapshot is None else "HEALTHY", "reason": snapshot_error}]
                 if uses_quotes else [])],
        }
        if uses_quotes and snapshot is None:
            # No universe-wide bid/ask: say so rather than filter on the few rows that are live.
            return {**envelope, "result_set_id": None,
                    "source_error": (error if not source_rows else None) or snapshot_error or "MARKET_SNAPSHOT_UNAVAILABLE",
                    **page_payload(query, [])}

        def observe(row: dict[str, Any], name: str) -> Any:
            if snapshot is not None and name in QUOTE_SNAPSHOT_FIELDS:
                return snapshot.value(row["instrument"]["instrument_id"], name)
            return field_value(row, name)

        key = (as_of, snapshot.id if snapshot else None, query.identity)
        with self._lock:
            ordered = self._ordered.get(key)
        if ordered is None:
            needle = query.search.casefold()
            matched = [row for row in apply_filters(source_rows, list(query.filters), observe)
                       if not needle or needle in row["symbol"].casefold() or needle in row["company"].casefold()]
            ordered = exact_matches_first(order_rows(matched, query.sort, query.descending, observe), needle)
            with self._lock:
                self._ordered[key] = ordered
                while len(self._ordered) > RESULT_CACHE_ENTRIES:
                    self._ordered.popitem(last=False)
        page = page_payload(query, ordered)
        if snapshot is not None:
            page["rows"] = [_with_quote_snapshot(row, snapshot) for row in page["rows"]]
        # Ordering/filtering stays on the universe snapshot; only returned cells go live.
        page["rows"] = [with_current_quote(row, self.quote_for(row["instrument"]["instrument_id"]))
                        for row in page["rows"]]
        return {**envelope, "result_set_id": f"{as_of}|{snapshot.id}" if snapshot else as_of,
                "source_error": error if not source_rows else None, **page}

    def classification_reference(self) -> ClassificationReference:
        """The current export's classification of every US listing (the ETF admission reference)."""

        with self._lock:
            self._refresh()
            reference = self._reference
            # A failed refresh keeps the last good classification (as it keeps the rows), with the error attached.
            if not reference.available:
                return ClassificationReference(None, {}, self._error or "SOURCE_UNAVAILABLE")
            return ClassificationReference(reference.as_of, reference.entries, self._error, reference.fingerprint)

    def admission_audit(self) -> dict[str, Any] | None:
        with self._lock:
            self._refresh()
            return self._admission

    def row_for(self, instrument_id: str) -> tuple[dict[str, Any] | None, str | None]:
        """One current snapshot row by canonical ID (no filters/search), plus source error."""

        with self._lock:
            self._refresh()
            row = next((item for item in self._rows if item["instrument"]["instrument_id"] == instrument_id), None)
            error = self._error if not self._rows else None
        return (with_current_quote(row, self.quote_for(instrument_id)) if row else None), error

    def quote_for(self, instrument_id: str) -> dict[str, Any]:
        runtime = self._runtime_getter(create=False)
        quote = runtime.state.quote_for(instrument_id) if runtime is not None else None
        if quote is None:
            return {"state": "UNAVAILABLE", "fields": {},
                    "reason": "RUNTIME_UNAVAILABLE" if runtime is None else pending_quote_reason(runtime, instrument_id)}
        return quote_view(runtime, quote)

    @staticmethod
    def _consumer(client_id: str) -> str:
        return f"main-screener:{client_id}"

    def _release(self, client_id: str) -> None:
        old = self._clients.pop(client_id, None)
        if old is None:
            return
        symbols, _, runtime = old
        if runtime is not None:
            for symbol in sorted(symbols):
                runtime.unsubscribe(
                    instrument_id=symbol, capabilities=["BASIC_QUOTE"],
                    consumer_id=self._consumer(client_id),
                )

    def release(self, client_id: str) -> dict[str, Any]:
        with self._lock:
            self._release(client_id)
        return {"released": True}

    def window(self, client_id: str, symbols: list[str], *, known: dict[str, str] | None = None,
               market_session: str | None = None) -> dict[str, Any]:
        if not client_id or len(client_id) > 80 or not all(c.isalnum() or c in "-_" for c in client_id):
            raise ValueError("INVALID_CLIENT_ID")
        if len(symbols) > MAX_WINDOW:
            raise ValueError("WINDOW_LIMIT_EXCEEDED")
        with self._lock:
            now = self._monotonic()
            for expired, (_, seen, _) in list(self._clients.items()):
                if now - seen > CLIENT_TTL_SECONDS:
                    self._release(expired)
            admitted = (known if known is not None else
                        {row["instrument"]["instrument_id"]: row["instrument"]["instrument_id"] for row in self._rows})
            targets = {admitted[item] for item in symbols if item in admitted}
            if len(set(symbols)) != len(symbols) or len(targets) != len(symbols) or not set(symbols) <= set(admitted):
                raise ValueError("UNKNOWN_OR_DUPLICATE_INSTRUMENT")
            runtime = self._runtime_getter(create=False)
            previous, _, previous_runtime = self._clients.get(client_id, (set(), now, runtime))
            if previous_runtime is not runtime:
                self._release(client_id)
                previous = set()
            active = set(previous)
            for symbol in sorted(active - targets):
                if runtime is not None:
                    runtime.unsubscribe(instrument_id=symbol, capabilities=["BASIC_QUOTE"], consumer_id=self._consumer(client_id))
                active.remove(symbol)
            rejected: dict[str, str] = {}
            for requested in symbols:
                symbol = admitted[requested]
                if symbol in active or runtime is None:
                    continue
                result = runtime.subscribe(
                    instrument_id=symbol, capabilities=["BASIC_QUOTE"],
                    consumer_id=self._consumer(client_id),
                    priority=int(SubscriptionPriority.BACKGROUND_RESEARCH),
                )
                if any(item.get("accepted") for item in result):
                    active.add(symbol)
                else:
                    rejected[symbol] = str(next((item.get("reason") for item in result if item.get("reason")), "NOT_ADMITTED"))
            self._clients[client_id] = (active, now, runtime)
            self._schedule_expiry()
            quotes: dict[str, dict[str, Any]] = {}
            for requested in symbols:
                symbol = admitted[requested]
                quote = runtime.state.quote_for(symbol) if runtime is not None and symbol in active else None
                if quote is None:
                    reason = (rejected.get(symbol) or (pending_quote_reason(runtime, symbol) if symbol in active
                                                       else "RUNTIME_UNAVAILABLE"))
                    quotes[requested] = {"state": "UNAVAILABLE", "reason": reason, "fields": {}}
                    continue
                quotes[requested] = quote_view(runtime, quote)
            return {"schema_version": SCHEMA_VERSION, "generated_at": self._now(),
                    "market_session": market_session or us_equity_screener_session(), "active": len(active),
                    "cap": MAX_WINDOW, "quotes": quotes}


_SERVICE = ScreenerService()


def screener_service() -> ScreenerService:
    return _SERVICE


def read_screener(**kwargs: Any) -> dict[str, Any]:
    from .screener_multi import multi_screener_service

    return multi_screener_service().read(**kwargs)


def update_screener_window(client_id: str, symbols: list[str], *, universe: str = UNIVERSE) -> dict[str, Any]:
    from .screener_multi import multi_screener_service

    return multi_screener_service().window(client_id, symbols, universe=universe)


def release_screener_window(client_id: str) -> dict[str, Any]:
    return _SERVICE.release(client_id)
