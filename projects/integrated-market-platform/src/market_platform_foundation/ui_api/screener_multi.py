"""Current OpenD contract/ETF catalogs for the Main Screener.

Catalog discovery is metadata only. Market fields remain unavailable until an
independent, bounded quote path supplies them. No replay or fixture source is
admitted here.
"""

from __future__ import annotations

import math
import re
import threading
import time
from collections import OrderedDict
from datetime import UTC, date, datetime
from typing import Any, Callable
from zoneinfo import ZoneInfo

from ..futures.spec_registry import resolve_futures_spec
from ..market_data.current_bars import current_bars_service
from ..market_sessions import us_equity_session_label
from ..xa01.compatibility import register_etf_fund, register_future_contract, register_future_contract_reference
from .screener_filters import apply_filters, field_value
from .screener_futures_context import resolve_contract
from .screener_projections import MAX_WINDOW, RESULT_CACHE_ENTRIES, SCHEMA_VERSION, screener_service
from .screener_query import DEFAULT_PAGE_LIMIT, ScreenerQuery, order_rows, page_payload, parse_query, snapshot_fields
from .screener_snapshot import SOURCE as SNAPSHOT_SOURCE
from .screener_snapshot import EtfSnapshotSource, MarketSnapshot
from .screener_universes import FUTURES, US_EQUITIES, US_ETFS, universe_spec

ET = ZoneInfo("America/New_York")
CATALOG_TTL_SECONDS = 900
CATALOG_RETAINED = 2
QUOTE_REFUSAL_TTL_SECONDS = 300
MARKET_STATE_TTL_SECONDS = 30
_MAIN_CODE = re.compile(r"^US\.([A-Za-z0-9]+)main$", re.IGNORECASE)
_DATED_CODE = re.compile(r"^US\.([A-Za-z0-9]+)(\d{2})(0[1-9]|1[0-2])$")
_FUTURES_NUMBERS = ("price", "change_pct", "volume", "open_interest", "bid", "ask", "spread_pct", "dte", "lead", "tick_size", "multiplier")
_ETF_NUMBERS = ("price", "change_pct", "volume", "avg_volume", "rel_volume", "rsi_14", "bid", "ask", "spread_pct")
SNAPSHOT_FIELDS = snapshot_fields(US_ETFS)


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _field(value: float | None, as_of: str, *, source: str = "MOOMOO_OPEND", state: str = "CURRENT_METADATA") -> dict[str, Any]:
    return {"value": value, "source": source, "state": state if value is not None else "UNAVAILABLE",
            "as_of": as_of if value is not None else None}


def _finite(raw: Any) -> float | None:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _exchange(raw: Any) -> str | None:
    """Provider exchange code, or None when the provider has no venue (e.g. ``N/A``)."""

    value = str(raw or "").strip().upper()
    return None if value in {"", "N/A", "NONE", "UNKNOWN"} else value


def _transport() -> Any | None:
    return current_bars_service().transport()


def _catalog_row_base(*, canonical_id: str, symbol: str, name: str, asset_class: str,
                      venue: str, as_of: str, numbers: tuple[str, ...]) -> dict[str, Any]:
    return {
        "instrument": {"instrument_id": canonical_id, "venue_id": venue,
                       "asset_class": asset_class, "instrument_kind": "FUTURE_CONTRACT" if asset_class == "FUTURE" else "TRADABLE_SECURITY"},
        "symbol": symbol, "company": name, "sector": None, "industry": None,
        "exchange": _exchange(venue), "country": "USA", "earnings_date": None, "recommendation": None,
        "fields": {field: _field(None, as_of) for field in numbers},
    }


def project_futures_catalog(raw: list[dict[str, Any]], *, today: date, as_of: str) -> list[dict[str, Any]]:
    """One verified dated lead contract per provider main alias; expired rows fail closed."""

    dated = {str(row.get("code")): row for row in raw if _DATED_CODE.fullmatch(str(row.get("code") or ""))}
    results: dict[str, dict[str, Any]] = {}
    for main in raw:
        match = _MAIN_CODE.fullmatch(str(main.get("code") or ""))
        if not match or main.get("stock_type") != "FUTURE" or main.get("delisting"):
            continue
        root = match.group(1).upper()
        contract = resolve_contract(root, main, dated, today)
        if contract["state"] != "CURRENT":
            continue
        code = contract["provider_code"]
        detail = dated.get(code)
        if not detail or detail.get("stock_type") != "FUTURE" or detail.get("delisting"):
            continue
        expiry = date.fromisoformat(contract["last_trade_date"])
        if expiry < today:
            continue
        spec = resolve_futures_spec(root, today)
        if spec is None:
            canonical = register_future_contract_reference(
                contract_id=contract["contract_id"], family_root=root,
                contract_month=contract["contract_month"], expiration=expiry.isoformat(),
            )
        else:
            canonical = register_future_contract(
                contract_id=contract["contract_id"], family_root=root,
                contract_month=contract["contract_month"], expiration=expiry.isoformat(),
                contract_multiplier=str(spec.multiplier),
            )
        row = _catalog_row_base(canonical_id=canonical, symbol=contract["contract_id"],
                                name=str(detail.get("name") or main.get("name") or contract["contract_id"]),
                                asset_class="FUTURE", venue=str(detail.get("exchange_type") or "FUTURES"),
                                as_of=as_of, numbers=_FUTURES_NUMBERS)
        row.update({"root": root, "contract_month": contract["contract_month"],
                    "expiry": expiry.isoformat(), "lead": True, "provider_symbol": code,
                    "market_data_id": contract["contract_id"]})
        row["fields"].update({"dte": _field(float((expiry - today).days), as_of),
                              "lead": _field(1.0, as_of),
                              "tick_size": _field(float(spec.tick_size) if spec else None, as_of,
                                                   source="IMP_FUTURES_SPEC" if spec else "MOOMOO_OPEND"),
                              "multiplier": _field(float(spec.multiplier) if spec else None, as_of,
                                                   source="IMP_FUTURES_SPEC" if spec else "MOOMOO_OPEND")})
        results[canonical] = row
    return sorted(results.values(), key=lambda item: (item["root"], item["symbol"]))


def project_etf_catalog(raw: list[dict[str, Any]], *, as_of: str) -> list[dict[str, Any]]:
    """Only provider-classified ETFs; never infer fund status from a name/ticker."""

    results: dict[str, dict[str, Any]] = {}
    for source in raw:
        code = str(source.get("code") or "")
        if source.get("stock_type") != "ETF" or source.get("delisting") or not code.startswith("US."):
            continue
        symbol = code[3:].upper()
        if not symbol or not all(char.isalnum() or char in ".-" for char in symbol):
            continue
        canonical = register_etf_fund(symbol=symbol)
        row = _catalog_row_base(canonical_id=canonical, symbol=symbol,
                                name=str(source.get("name") or symbol), asset_class="ETF_FUND",
                                venue=str(source.get("exchange_type") or "US_ETF"),
                                as_of=as_of, numbers=_ETF_NUMBERS)
        row.update({"provider_symbol": code, "market_data_id": symbol})
        results[canonical] = row
    return sorted(results.values(), key=lambda item: item["symbol"])


def _quote_from_futures_snapshot(source: dict[str, Any], now_s: float) -> dict[str, Any]:
    """A snapshot becomes live only with explicit realtime mode and a fresh clock."""

    raw_time = str(source.get("update_time") or "")[:19]
    try:
        event = datetime.strptime(raw_time, "%Y-%m-%d %H:%M:%S").replace(tzinfo=ET)
        as_of = event.astimezone(UTC).isoformat().replace("+00:00", "Z")
        age_ms = max(0, int((now_s - event.timestamp()) * 1000))
    except ValueError:
        as_of, age_ms = None, None
    mode = str(source.get("data_mode") or source.get("market_data_mode") or "").upper()
    state = ("UNAVAILABLE" if age_ms is None else
             "STALE" if age_ms > 15_000 else
             "DELAYED" if "DELAY" in mode else
             "LIVE" if mode in {"LIVE", "REALTIME", "REAL_TIME"} else "UNAVAILABLE")
    price = _finite(source.get("last_price"))
    previous = _finite(source.get("prev_close_price"))
    bid, ask = _finite(source.get("bid_price")), _finite(source.get("ask_price"))
    spread = (ask - bid) / ((ask + bid) / 2) * 100 if bid is not None and ask is not None and ask >= bid and ask + bid > 0 else None
    values = {"price": price, "change_pct": (price - previous) / previous * 100 if price is not None and previous and previous > 0 else None,
              "volume": _finite(source.get("volume")), "open_interest": _finite(source.get("open_interest")),
              "bid": bid, "ask": ask, "spread_pct": spread}
    return {"state": state, "reason": None if state == "LIVE" else "DELAYED_PROVIDER" if state == "DELAYED" else
            "STALE_QUOTE" if state == "STALE" else "UNVERIFIED_QUOTE_MODE",
            **({"age_ms": age_ms} if age_ms is not None else {}),
            "fields": {field: {"value": value if state in {"LIVE", "DELAYED"} else None, "source": "MOOMOO_OPEND",
                                "state": state if value is not None and state in {"LIVE", "DELAYED"} else "UNAVAILABLE",
                                "as_of": as_of} for field, value in values.items()}}


def _futures_session(raw: Any) -> str:
    """Only classify states whose provider meaning is unambiguous."""

    state = str(raw or "").upper()
    if state in {"FUTURE_OPEN", "FUTURE_TRADING"}:
        return "TRADING"
    if state in {"FUTURE_CLOSE", "FUTURE_CLOSED"}:
        return "CLOSED"
    if "REST" in state or "MAINTENANCE" in state:
        return "MAINTENANCE"
    return "UNAVAILABLE"


def _observer(snapshot: MarketSnapshot | None) -> Callable[[dict[str, Any], str], Any]:
    """Field values for filtering/sorting: catalog values, or one complete snapshot."""

    if snapshot is None:
        return field_value

    def observe(row: dict[str, Any], name: str) -> Any:
        if name in SNAPSHOT_FIELDS:
            return snapshot.value(row["instrument"]["instrument_id"], name)
        return field_value(row, name)
    return observe


def _with_snapshot(row: dict[str, Any], snapshot: MarketSnapshot) -> dict[str, Any]:
    """A page row carrying the snapshot values it was filtered and ordered by."""

    identity = row["instrument"]["instrument_id"]
    as_of = snapshot.row_as_of.get(identity)
    fields = dict(row["fields"])
    for name in SNAPSHOT_FIELDS:
        value = snapshot.value(identity, name)
        fields[name] = {"value": value, "source": SNAPSHOT_SOURCE,
                        "state": "SNAPSHOT" if value is not None else "UNAVAILABLE",
                        "as_of": as_of if value is not None else None}
    return {**row, "fields": fields, "snapshot_id": snapshot.id}


class MultiUniverseScreener:
    def __init__(self, *, transport_getter: Callable[[], Any | None] = _transport,
                 clock: Callable[[], float] = time.monotonic,
                 today: Callable[[], date] = lambda: datetime.now(ET).date(),
                 now: Callable[[], str] = _now, now_s: Callable[[], float] = time.time,
                 wall: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._transport_getter = transport_getter
        self._clock = clock
        self._today = today
        self._now = now
        self._now_s = now_s
        self._lock = threading.RLock()
        self._catalogs: dict[str, tuple[float, str, list[dict[str, Any]], str | None]] = {}
        # Current and previous projection per universe, so a pinned page chain
        # finishes on the rows it started from.
        self._projected: dict[str, OrderedDict[tuple[str, date], list[dict[str, Any]]]] = {}
        self._ordered: OrderedDict[tuple[Any, ...], list[dict[str, Any]]] = OrderedDict()
        self._snapshots = EtfSnapshotSource(transport_getter=transport_getter, clock=clock, wall=wall)
        self._quote_refusal: tuple[float, str] | None = None
        self._market_states: tuple[float, frozenset[str], dict[str, str]] | None = None

    def _catalog(self, universe: str, *, force: bool = False) -> tuple[list[dict[str, Any]], str | None, str | None]:
        with self._lock:
            cached = self._catalogs.get(universe)
            if cached and not force and self._clock() - cached[0] < CATALOG_TTL_SECONDS:
                raw, as_of, error = cached[2], cached[1], cached[3]
            else:
                transport = self._transport_getter()
                try:
                    result = ({"reason_code": "PROVIDER_UNAVAILABLE"} if transport is None else
                              transport.fetch_future_contracts([]) if universe == FUTURES else transport.fetch_etf_catalog())
                except Exception:  # noqa: BLE001 — provider boundary fails closed
                    result = {"reason_code": "PROVIDER_UNAVAILABLE"}
                error = str(result.get("reason_code")) if result.get("reason_code") else None
                if error:
                    if cached:
                        raw, as_of = cached[2], cached[1]
                    else:
                        raw, as_of = [], None
                else:
                    raw = list(result.get("rows") or [])
                    as_of = self._now()
                self._catalogs[universe] = (self._clock(), as_of or "", raw, error)
            today = self._today()
            retained = self._projected.setdefault(universe, OrderedDict())
            rows = retained.get((as_of or "", today))
            if rows is None:
                # Expiry and lead status are re-derived whenever the trading date changes.
                rows = (project_futures_catalog(raw, today=today, as_of=as_of or "") if universe == FUTURES
                        else project_etf_catalog(raw, as_of=as_of or ""))
                retained[(as_of or "", today)] = rows
                while len(retained) > CATALOG_RETAINED:
                    retained.popitem(last=False)
            return rows, as_of or None, error

    def _pinned_catalog(self, universe: str, as_of: str) -> list[dict[str, Any]] | None:
        with self._lock:
            return self._projected.get(universe, OrderedDict()).get((as_of, self._today()))

    def read(self, *, universe: str, search: str = "", sort: str | None = None, descending: bool = True,
             offset: int = 0, limit: int = DEFAULT_PAGE_LIMIT, force_refresh: bool = False,
             filters: list[dict[str, Any]] | None = None, result_set: str | None = None,
             selected: str | None = None) -> dict[str, Any]:
        universe_spec(universe)
        if universe == US_EQUITIES:
            return screener_service().read(universe=universe, search=search, sort=sort or "volume",
                                           descending=descending, offset=offset, limit=limit,
                                           force_refresh=force_refresh, filters=filters, result_set=result_set,
                                           selected=selected)
        query = parse_query(universe=universe, search=search, sort=sort, descending=descending, offset=offset,
                            limit=limit, filters=filters, result_set=result_set, selected=selected)
        return self._read_query(query, force_refresh=force_refresh)

    def _read_query(self, query: ScreenerQuery, *, force_refresh: bool) -> dict[str, Any]:
        universe, spec = query.universe, universe_spec(query.universe)
        snapshot: MarketSnapshot | None = None
        snapshot_error: str | None = None
        if query.result_set is not None:
            # A later page reads the exact catalog and snapshot its first page used.
            catalog_as_of, _, snapshot_id = query.result_set.partition("|")
            pinned = self._pinned_catalog(universe, catalog_as_of)
            snapshot = self._snapshots.retained(snapshot_id) if snapshot_id else None
            if pinned is None or bool(snapshot_id) != query.uses_snapshot or (snapshot_id and snapshot is None):
                raise ValueError("RESULT_SET_CHANGED")
            rows, as_of, error = pinned, catalog_as_of, None
        else:
            rows, as_of, error = self._catalog(universe, force=force_refresh)
            if query.uses_snapshot and rows:
                snapshot, snapshot_error = self._snapshots.current(rows, catalog_as_of=as_of or "",
                                                                   force=force_refresh)
        envelope = {"schema_version": SCHEMA_VERSION, "universe": universe, "generated_at": self._now(),
                    "market_session": "PROVIDER_SPECIFIC" if universe == FUTURES else us_equity_session_label(),
                    "universe_as_of": as_of, "screener_as_of": snapshot.as_of if snapshot else as_of,
                    "evaluation": "SNAPSHOT" if query.uses_snapshot else "CATALOG",
                    "snapshot": snapshot.summary() if snapshot else None,
                    "unfiltered_count": len(rows),
                    "provider_health": [
                        {"provider": spec.source, "role": "IDENTITY_SOURCE",
                         "state": "DEGRADED" if error and rows else "UNAVAILABLE" if error else "HEALTHY",
                         "reason": error},
                        {"provider": "MOOMOO_OPEND", "role": "QUOTE_SOURCE",
                         "state": "UNAVAILABLE" if universe == FUTURES else "WINDOW_ONLY",
                         "reason": "NOT_ENTITLED_OR_UNVERIFIED" if universe == FUTURES else None},
                        *([{"provider": SNAPSHOT_SOURCE, "role": "MARKET_SNAPSHOT",
                            "state": "UNAVAILABLE" if snapshot is None else "HEALTHY", "reason": snapshot_error}]
                          if query.uses_snapshot else []),
                    ]}
        if query.uses_snapshot and snapshot is None:
            # Never evaluate a market filter or sort on a partial or visible-row subset.
            return {**envelope, "result_set_id": None,
                    "source_error": error if not rows else snapshot_error or "MARKET_SNAPSHOT_UNAVAILABLE",
                    **page_payload(query, [])}
        key = (universe, as_of, self._today(), snapshot.id if snapshot else None, query.identity)
        with self._lock:
            ordered = self._ordered.get(key)
        if ordered is None:
            observe = _observer(snapshot)
            needle = query.search.casefold()
            keys = ("symbol", "company", "root") if universe == FUTURES else ("symbol", "company")
            matched = [row for row in apply_filters(rows, list(query.filters), observe)
                       if not needle or any(needle in str(row.get(key) or "").casefold() for key in keys)]
            ordered = order_rows(matched, query.sort, query.descending, observe)
            with self._lock:
                self._ordered[key] = ordered
                while len(self._ordered) > RESULT_CACHE_ENTRIES:
                    self._ordered.popitem(last=False)
        page = page_payload(query, ordered)
        if snapshot is not None:
            page["rows"] = [_with_snapshot(row, snapshot) for row in page["rows"]]
        return {**envelope, "result_set_id": f"{as_of}|{snapshot.id if snapshot else ''}" if rows else None,
                "source_error": error if not rows else None, **page}

    def row_for(self, instrument_id: str, *, universe: str,
                snapshot_id: str | None = None) -> tuple[dict[str, Any] | None, str | None]:
        """The catalog row; with a retained snapshot id, carrying that snapshot's values."""

        if universe == US_EQUITIES:
            return screener_service().row_for(instrument_id)
        rows, _as_of, error = self._catalog(universe)
        row = next((row for row in rows if row["instrument"]["instrument_id"] == instrument_id), None)
        snapshot = self._snapshots.retained(snapshot_id) if snapshot_id and universe == US_ETFS else None
        return (_with_snapshot(row, snapshot) if row is not None and snapshot is not None else row), error

    def quote_for(self, instrument_id: str, *, universe: str) -> dict[str, Any]:
        if universe == US_EQUITIES:
            return screener_service().quote_for(instrument_id)
        row, error = self.row_for(instrument_id, universe=universe)
        if row is None:
            return {"state": "UNAVAILABLE", "reason": error or "UNKNOWN_INSTRUMENT", "fields": {}}
        if universe == US_ETFS:
            return screener_service().quote_for(row["market_data_id"])
        return self.window("preview-futures", [instrument_id], universe=FUTURES)["quotes"][instrument_id]

    def window(self, client_id: str, symbols: list[str], *, universe: str) -> dict[str, Any]:
        universe_spec(universe)
        if universe == US_EQUITIES:
            return screener_service().window(client_id, symbols)
        if not client_id or len(client_id) > 80 or not all(char.isalnum() or char in "-_" for char in client_id):
            raise ValueError("INVALID_CLIENT_ID")
        if len(symbols) > MAX_WINDOW or len(set(symbols)) != len(symbols):
            raise ValueError("WINDOW_LIMIT_EXCEEDED")
        rows, _as_of, error = self._catalog(universe)
        by_id = {row["instrument"]["instrument_id"]: row for row in rows}
        if not set(symbols) <= set(by_id):
            raise ValueError("UNKNOWN_OR_DUPLICATE_INSTRUMENT")
        if universe == US_ETFS:
            return screener_service().window(client_id, symbols,
                                             known={key: by_id[key]["market_data_id"] for key in symbols},
                                             market_session=us_equity_session_label())
        screener_service().release(client_id)
        with self._lock:
            refusal = self._quote_refusal
            if refusal and self._clock() - refusal[0] < QUOTE_REFUSAL_TTL_SECONDS:
                reason, vendor = refusal[1], {}
            else:
                transport = self._transport_getter()
                try:
                    result = ({"reason_code": "PROVIDER_UNAVAILABLE"} if transport is None or not symbols else
                              transport.fetch_future_quotes([by_id[key]["provider_symbol"] for key in symbols]))
                except Exception:  # noqa: BLE001 — provider boundary fails closed
                    result = {"reason_code": "PROVIDER_UNAVAILABLE"}
                reason = str(result.get("reason_code")) if result.get("reason_code") else None
                vendor = {str(item.get("code")): item for item in result.get("rows") or []}
                if reason:
                    self._quote_refusal = (self._clock(), reason)
        quotes = {key: (_quote_from_futures_snapshot(vendor[by_id[key]["provider_symbol"]], self._now_s())
                        if by_id[key]["provider_symbol"] in vendor else
                        {"state": "UNAVAILABLE", "reason": reason or error or "AWAITING_QUOTE", "fields": {}})
                  for key in symbols}
        codes = frozenset(by_id[key]["provider_symbol"] for key in symbols)
        with self._lock:
            cached_states = self._market_states
            if cached_states and codes <= cached_states[1] and self._clock() - cached_states[0] < MARKET_STATE_TTL_SECONDS:
                states = cached_states[2]
            else:
                transport = self._transport_getter()
                try:
                    result = (transport.fetch_market_states(sorted(codes)) if transport is not None and codes and
                              callable(getattr(transport, "fetch_market_states", None)) else {"reason_code": "UNAVAILABLE"})
                except Exception:  # noqa: BLE001 — provider boundary fails closed
                    result = {"reason_code": "UNAVAILABLE"}
                states = ({str(item.get("code")): _futures_session(item.get("market_state"))
                           for item in result.get("rows") or []} if not result.get("reason_code") else {})
                self._market_states = (self._clock(), codes, states)
        for key, quote in quotes.items():
            quote["session_state"] = states.get(by_id[key]["provider_symbol"], "UNAVAILABLE")
        sessions = set(quote["session_state"] for quote in quotes.values())
        market_session = next(iter(sessions)) if len(sessions) == 1 else "MIXED" if sessions else "UNAVAILABLE"
        return {"schema_version": SCHEMA_VERSION, "generated_at": self._now(),
                "market_session": market_session, "active": 0, "cap": MAX_WINDOW, "quotes": quotes}

    def release(self, client_id: str) -> dict[str, Any]:
        return screener_service().release(client_id)


_SERVICE = MultiUniverseScreener()


def multi_screener_service() -> MultiUniverseScreener:
    return _SERVICE
