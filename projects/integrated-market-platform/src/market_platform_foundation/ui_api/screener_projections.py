"""Provider-neutral, current-market US-equity screener projection.

Finviz supplies a broad published snapshot. Moomoo L1 is read only for a
bounded viewport; the two sources retain separate field provenance.
"""

from __future__ import annotations

import math
import threading
import time
from datetime import UTC, datetime
from typing import Any, Callable

from ..finviz.screener import FinvizScreenerClient, FinvizScreenerRow
from ..finviz.symbols import finviz_to_canonical
from ..market_data.live_runtime import get_live_runtime
from ..market_data.subscription_manager import SubscriptionPriority
from ..market_sessions import us_equity_session_label

SCHEMA_VERSION = "screener/1.0.0"
UNIVERSE = "US_EQUITIES"
FILTER = "geo_usa,ind_stocksonly"
# Verified export IDs: ticker, company, sector, industry, country, cap, float,
# short float, short ratio, RSI, RVOL, price, change, and volume.
SCREENER_COLUMNS = "1,2,3,4,5,6,25,30,31,59,64,65,66,67"
MAX_WINDOW = 32
SNAPSHOT_TTL_SECONDS = 120
CLIENT_TTL_SECONDS = 45
FIELD_NAMES = (
    "price", "change_pct", "volume", "rel_volume", "float_shares",
    "market_cap", "short_float_pct", "rsi_14",
)


def _iso_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _snapshot_row(row: FinvizScreenerRow, as_of: str) -> dict[str, Any]:
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
        },
        "symbol": row.ticker,
        "company": row.company,
        "sector": row.sector or None,
        "industry": row.industry or None,
        "fields": fields,
    }


class ScreenerService:
    """Own one snapshot cache and independent, expiring viewport subscriptions."""

    def __init__(
        self,
        *,
        source_factory: Callable[[], Any] = FinvizScreenerClient,
        runtime_getter: Callable[..., Any | None] = get_live_runtime,
        monotonic: Callable[[], float] = time.monotonic,
        now: Callable[[], str] = _iso_now,
    ) -> None:
        self._source_factory = source_factory
        self._runtime_getter = runtime_getter
        self._monotonic = monotonic
        self._now = now
        self._lock = threading.RLock()
        self._rows: list[dict[str, Any]] = []
        self._as_of: str | None = None
        self._last_fetch = 0.0
        self._error: str | None = None
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
            self._rows = [_snapshot_row(row, as_of) for row in export["rows"]]
            self._as_of = as_of
            self._error = None
        except Exception as exc:
            self._error = type(exc).__name__

    def read(
        self, *, universe: str = UNIVERSE, search: str = "",
        sort: str = "volume", descending: bool = True,
        offset: int = 0, limit: int = 10_000, force_refresh: bool = False,
    ) -> dict[str, Any]:
        if universe != UNIVERSE:
            raise ValueError("UNSUPPORTED_UNIVERSE")
        if sort not in (*FIELD_NAMES, "symbol", "company"):
            raise ValueError("UNSUPPORTED_SORT")
        if offset < 0 or limit < 1 or limit > 10_000:
            raise ValueError("INVALID_RESULT_WINDOW")
        with self._lock:
            self._refresh(force=force_refresh)
            needle = search.strip().casefold()
            matched = [
                row for row in self._rows
                if not needle or needle in row["symbol"].casefold()
                or needle in row["company"].casefold()
            ]
            def key(row: dict[str, Any]) -> tuple[Any, ...]:
                value = (
                    row[sort].casefold() if sort in ("symbol", "company")
                    else row["fields"][sort]["value"]
                )
                # Stable ties; missing values always last regardless of direction.
                return (value is None, -value if descending and isinstance(value, (int, float))
                        else value, row["symbol"])
            if sort in ("symbol", "company") and descending:
                present = sorted((row for row in matched if row[sort]), key=lambda row: (row[sort].casefold(), row["symbol"]), reverse=True)
                matched = present + [row for row in matched if not row[sort]]
            else:
                matched.sort(key=key)
            return {
                "schema_version": SCHEMA_VERSION,
                "universe": UNIVERSE,
                "generated_at": self._now(),
                "market_session": us_equity_session_label(),
                "universe_as_of": self._as_of,
                "screener_as_of": self._as_of,
                "result_count": len(matched),
                "offset": offset,
                "provider_health": [{
                    "provider": "FINVIZ_ELITE",
                    "state": "DEGRADED" if self._error and self._rows else "UNAVAILABLE" if self._error else "HEALTHY",
                    "reason": self._error,
                }],
                "source_error": self._error if not self._rows else None,
                "rows": matched[offset:offset + limit],
            }

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

    def window(self, client_id: str, symbols: list[str]) -> dict[str, Any]:
        if not client_id or len(client_id) > 80 or not all(c.isalnum() or c in "-_" for c in client_id):
            raise ValueError("INVALID_CLIENT_ID")
        if len(symbols) > MAX_WINDOW:
            raise ValueError("WINDOW_LIMIT_EXCEEDED")
        with self._lock:
            now = self._monotonic()
            for expired, (_, seen, _) in list(self._clients.items()):
                if now - seen > CLIENT_TTL_SECONDS:
                    self._release(expired)
            known = {row["instrument"]["instrument_id"] for row in self._rows}
            targets = set(symbols)
            if len(targets) != len(symbols) or not targets <= known:
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
            for symbol in symbols:
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
            for symbol in symbols:
                quote = runtime.state.quote_for(symbol) if runtime is not None and symbol in active else None
                if quote is None:
                    quotes[symbol] = {"state": "UNAVAILABLE", "reason": rejected.get(symbol, "AWAITING_QUOTE" if symbol in active else "RUNTIME_UNAVAILABLE"), "fields": {}}
                    continue
                age_ms = max(0, (time.time_ns() - int(quote.received_ns)) // 1_000_000)
                quality = str(quote.quality or "UNKNOWN").upper()
                admission = str(quote.admission or "UNKNOWN").upper()
                connection = str(getattr(getattr(runtime, "lifecycle", None), "connection_state", "AVAILABLE")).upper()
                if age_ms > 5_000 or "DISCONNECTED" in connection or "RECONNECTING" in connection:
                    state = "STALE"
                elif "DELAY" in quality:
                    state = "DELAYED"
                elif admission in ("BLOCKED", "DEGRADED") or quality not in ("PASS", "GOOD"):
                    state = "UNAVAILABLE"
                else:
                    state = "LIVE"
                bid, ask = _number(quote.bid_price), _number(quote.ask_price)
                spread = (ask - bid) / ((ask + bid) / 2) * 100 if bid is not None and ask is not None and ask >= bid and ask + bid > 0 else None
                values = {"price": _number(quote.last_price), "volume": _number(quote.volume), "bid": bid, "ask": ask, "spread_pct": spread}
                quotes[symbol] = {
                    "state": state, "age_ms": age_ms, "reason": None if state == "LIVE" else quality,
                    "quality": quality, "admission": admission,
                    "fields": {
                        name: {"value": value, "source": str(quote.provider or "MOOMOO"),
                               "state": state if value is not None else "UNAVAILABLE",
                               "as_of_ns": int(quote.available_time_ns)}
                        for name, value in values.items()
                    },
                }
            return {"schema_version": SCHEMA_VERSION, "generated_at": self._now(),
                    "market_session": us_equity_session_label(), "active": len(active),
                    "cap": MAX_WINDOW, "quotes": quotes}


_SERVICE = ScreenerService()


def read_screener(**kwargs: Any) -> dict[str, Any]:
    return _SERVICE.read(**kwargs)


def update_screener_window(client_id: str, symbols: list[str]) -> dict[str, Any]:
    return _SERVICE.window(client_id, symbols)


def release_screener_window(client_id: str) -> dict[str, Any]:
    return _SERVICE.release(client_id)
