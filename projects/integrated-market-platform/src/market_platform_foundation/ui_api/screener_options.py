"""Selected-underlying current options context for the Main Screener (S7).

One selected Screener instrument → its current option chain from the Finviz
Elite export (``FinvizOptionChainProvider``), normalized into
``screener-options/1.0.0``: the chain's own snapshot clock and state,
chain-wide and per-expiry analytics, and one expiry's contract rows.

This is selected-instrument context, not universe data. Nothing here feeds
Screener filters, sorting, or columns, and no chain is fetched unless the
Options panel or the Preview Options tab asks for one. A fixture or research
provider is refused; an unavailable chain is stated, never substituted.
"""

from __future__ import annotations

import statistics
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable

from ..contracts.options_quality import OptionQualityFlag
from ..finviz.config import OPTIONS_CACHE_TTL_S
from ..market_sessions import us_equity_session_label
from ..providers.adapters.finviz_option_chain import NormalizedChain, OptionRow
from ..providers.contracts import PROVIDER_UNAVAILABLE

SCHEMA_VERSION = "screener-options/1.0.0"
#: Distinct underlyings whose normalized chains are retained (least recently used goes first).
MAX_CACHED_UNDERLYINGS = 6
#: A chain is re-requested from the provider after the provider cache TTL.
REFRESH_AFTER_S = OPTIONS_CACHE_TTL_S
#: A snapshot older than two refresh periods is stale.
STALE_AFTER_S = 2 * OPTIONS_CACHE_TTL_S
#: After a failed refresh the last good chain is shown as STALE for at most this long.
LAST_GOOD_MAX_AGE_S = 30 * 60
TOP_CONTRACTS = 5
VIEWS = ("chain", "summary")
PROVIDER_LABELS = {"options.finviz.elite_export": "Finviz Elite"}
CAPABILITY = {"OPTIONS_CHAIN_CONTEXT": "SELECTED_UNDERLYING", "OPTIONS_ANALYTICS": "PARTIAL",
              "OPTIONS_UNIVERSE_QUERY": "NOT_SUPPORTED", "OPTIONS_EXECUTION_DATA": "NOT_AUTHORIZED"}
_FIXTURE_MARKERS = ("fixture", "replay", "demo")


def _iso(ns_or_s: float | None, *, seconds: bool = False) -> str | None:
    if not ns_or_s:
        return None
    value = ns_or_s if seconds else ns_or_s / 1_000_000_000
    return datetime.fromtimestamp(value, tz=UTC).isoformat().replace("+00:00", "Z")


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    """Safe ratio: undefined (None) when either side is unavailable or the denominator is zero."""

    if numerator is None or denominator is None or denominator == 0:
        return None
    return round(numerator / denominator, 4)


def _total(rows: list[OptionRow], attr: str) -> tuple[int | None, int]:
    values = [getattr(row, attr) for row in rows if getattr(row, attr) is not None]
    return (sum(values) if values else None), len(values)


def _brief(row: OptionRow, side_volume: int | None) -> dict[str, Any]:
    data = row.to_dict()
    return {key: data[key] for key in ("option_id", "provider_symbol", "type", "expiration", "strike", "volume",
                                       "open_interest", "volume_oi_ratio", "iv")} | {
        "share_of_side_volume_pct": round(row.volume / side_volume * 100, 2)
        if row.volume is not None and side_volume else None,
    }


def nearest_strike(rows: list[OptionRow], price: float | None) -> dict[str, Any] | None:
    """The listed strike closest to the underlying price — not a claim of exact ATM."""

    if price is None or price <= 0 or not rows:
        return None
    strikes = sorted({row.strike for row in rows})
    strike = min(strikes, key=lambda value: (abs(value - price), value))
    call = next((row for row in rows if row.strike == strike and row.option_type == "CALL"), None)
    put = next((row for row in rows if row.strike == strike and row.option_type == "PUT"), None)
    return {
        "expiration": rows[0].expiration if len({row.expiration for row in rows}) == 1 else None,
        "strike": strike, "basis_price": price, "distance": round(strike - price, 4),
        "distance_pct": round((strike - price) / price * 100, 2), "exact": strike == price,
        "call_iv": call.iv if call else None, "put_iv": put.iv if put else None,
        "call_mid": call.mid if call else None, "put_mid": put.mid if put else None,
    }


def chain_analytics(rows: list[OptionRow], price: float | None = None) -> dict[str, Any]:
    """Deterministic analytics over supplied fields only; formulas in SCREENER_S7_OPTIONS.md."""

    calls = [row for row in rows if row.option_type == "CALL"]
    puts = [row for row in rows if row.option_type == "PUT"]
    call_volume, call_volume_n = _total(calls, "volume")
    put_volume, put_volume_n = _total(puts, "volume")
    call_oi, call_oi_n = _total(calls, "open_interest")
    put_oi, put_oi_n = _total(puts, "open_interest")
    expirations = sorted({row.expiration for row in rows})
    spreads = [row.spread_pct for row in rows if row.spread_pct is not None]
    by_volume = sorted((row for row in rows if row.volume), key=lambda row: (-row.volume, row.option_id))
    by_oi = sorted((row for row in rows if row.open_interest), key=lambda row: (-row.open_interest, row.option_id))
    side_volume = {"CALL": call_volume, "PUT": put_volume}
    nearest_rows = [row for row in rows if expirations and row.expiration == expirations[0]]
    return {
        "contracts": len(rows), "calls": len(calls), "puts": len(puts),
        "expirations": len(expirations), "nearest_expiration": expirations[0] if expirations else None,
        "call_volume": call_volume, "put_volume": put_volume,
        "total_volume": None if call_volume is None and put_volume is None else (call_volume or 0) + (put_volume or 0),
        "put_call_volume_ratio": _ratio(put_volume, call_volume),
        "call_put_volume_ratio": _ratio(call_volume, put_volume),
        "call_open_interest": call_oi, "put_open_interest": put_oi,
        "total_open_interest": None if call_oi is None and put_oi is None else (call_oi or 0) + (put_oi or 0),
        "put_call_oi_ratio": _ratio(put_oi, call_oi),
        "volume_reported": call_volume_n + put_volume_n, "open_interest_reported": call_oi_n + put_oi_n,
        "iv_reported": sum(1 for row in rows if row.iv is not None),
        "two_sided": len(spreads),
        "median_spread_pct": round(statistics.median(spreads), 2) if spreads else None,
        "most_active": [_brief(row, side_volume[row.option_type]) for row in by_volume[:TOP_CONTRACTS]],
        "largest_open_interest": [_brief(row, side_volume[row.option_type]) for row in by_oi[:TOP_CONTRACTS]],
        "nearest_strike": nearest_strike(nearest_rows, price),
    }


def expiration_rows(rows: list[OptionRow]) -> list[dict[str, Any]]:
    grouped: dict[str, list[OptionRow]] = {}
    for row in rows:
        grouped.setdefault(row.expiration, []).append(row)
    result = []
    for expiration in sorted(grouped):
        items = grouped[expiration]
        calls = [row for row in items if row.option_type == "CALL"]
        puts = [row for row in items if row.option_type == "PUT"]
        result.append({"expiration": expiration, "dte": items[0].dte, "contracts": len(items),
                       "strikes": len({row.strike for row in items}),
                       "call_volume": _total(calls, "volume")[0], "put_volume": _total(puts, "volume")[0]})
    return result


@dataclass
class _Entry:
    provider_id: str
    chain: NormalizedChain
    fetched_ns: int
    latency_ms: float | None
    provider_cache_hit: bool
    checked_at_s: float


def current_option_chain_provider() -> Any:
    """The Screener's current chain source: the Finviz Elite export adapter.

    Resolved here rather than from ``ProviderComposition.option_chain``: that
    slot is the research/replay chain (fixture-backed after
    ``bootstrap_default_providers``) and a default composition is stubs only.
    The adapter reports NOT_CONFIGURED itself when no Finviz credential exists.
    """

    from ..providers.adapters.finviz_option_chain import FinvizOptionChainProvider

    return FinvizOptionChainProvider()


_DEFAULT_PROVIDER: Any | None = None


def _default_provider() -> Any:
    global _DEFAULT_PROVIDER
    if _DEFAULT_PROVIDER is None:
        _DEFAULT_PROVIDER = current_option_chain_provider()
    return _DEFAULT_PROVIDER


def _default_row(instrument_id: str, universe: str, snapshot_id: str | None) -> tuple[dict[str, Any] | None, str | None]:
    from .screener_multi import multi_screener_service

    service = multi_screener_service()
    # An ETF catalog row has no price of its own; the latest retained OpenD snapshot
    # (its own source and clock) is the nearest-strike basis. None is built for this.
    snapshot_id = snapshot_id or service.latest_snapshot_id(universe)
    return service.row_for(instrument_id, universe=universe, snapshot_id=snapshot_id)


def _default_quote(instrument_id: str, universe: str) -> dict[str, Any]:
    from .screener_multi import multi_screener_service

    try:
        return multi_screener_service().quote_for(instrument_id, universe=universe)
    except Exception:  # noqa: BLE001 — a missing quote only removes the nearest-strike basis
        return {"state": "UNAVAILABLE", "fields": {}}


class ScreenerOptionsService:
    """Bounded per-underlying chain cache with its own snapshot clock."""

    def __init__(self, *, provider_getter: Callable[[], Any] | None = None,
                 row_getter: Callable[[str, str, str | None], tuple[dict[str, Any] | None, str | None]] | None = None,
                 quote_getter: Callable[[str, str], dict[str, Any]] | None = None,
                 clock: Callable[[], float] | None = None,
                 session_label: Callable[[], str] | None = None,
                 max_entries: int = MAX_CACHED_UNDERLYINGS) -> None:
        self._provider_getter = provider_getter or _default_provider
        self._row_getter = row_getter or _default_row
        self._quote_getter = quote_getter or _default_quote
        self._clock = clock or time.time
        self._session_label = session_label or (lambda: us_equity_session_label())
        self._max_entries = max_entries
        self._entries: OrderedDict[tuple[str, str], _Entry] = OrderedDict()
        self._lock = threading.Lock()
        self._key_locks: dict[tuple[str, str], threading.Lock] = {}
        self.provider_requests = 0

    # -- cache ---------------------------------------------------------------

    def _key_lock(self, key: tuple[str, str]) -> threading.Lock:
        with self._lock:
            return self._key_locks.setdefault(key, threading.Lock())

    def _get(self, key: tuple[str, str]) -> _Entry | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is not None:
                self._entries.move_to_end(key)
            return entry

    def _put(self, key: tuple[str, str], entry: _Entry) -> None:
        with self._lock:
            self._entries[key] = entry
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                evicted, _ = self._entries.popitem(last=False)
                self._key_locks.pop(evicted, None)

    def cached_underlyings(self) -> list[str]:
        with self._lock:
            return [key[1] for key in self._entries]

    def _chain(self, provider: Any, symbol: str, underlying_id: str) -> tuple[_Entry | None, str | None, str | None]:
        """(entry, failure status, failure reason). A failure with a recent entry keeps the entry."""

        key = (str(provider.provider_id), symbol.upper())
        with self._key_lock(key):
            entry = self._get(key)
            now = self._clock()
            if entry is not None and now - entry.fetched_ns / 1e9 < REFRESH_AFTER_S:
                return entry, None, None
            self.provider_requests += 1
            result = provider.fetch_chain(symbol, underlying_id=underlying_id)
            chain = result.details.get("chain") if isinstance(result.details, dict) else None
            if result.status in ("available", "empty") and isinstance(chain, NormalizedChain):
                entry = _Entry(provider_id=key[0], chain=chain,
                               fetched_ns=int(result.details.get("fetched_time_ns") or now * 1e9),
                               latency_ms=result.details.get("latency_ms"),
                               provider_cache_hit=bool(result.details.get("cache_hit")), checked_at_s=now)
                self._put(key, entry)
                return entry, None, None
            status, reason = result.status, result.reason_code or "FINVIZ_OPTIONS_UNAVAILABLE"
            if entry is not None and now - entry.fetched_ns / 1e9 < LAST_GOOD_MAX_AGE_S:
                return entry, status, reason
            return None, status, reason

    # -- envelope ------------------------------------------------------------

    def _underlying(self, row: dict[str, Any], instrument_id: str, universe: str) -> dict[str, Any] | None:
        quote = self._quote_getter(instrument_id, universe)
        field = (quote.get("fields") or {}).get("price") or {}
        if quote.get("state") in ("LIVE", "DELAYED") and field.get("value"):
            return {"price": float(field["value"]), "source": str(field.get("source") or "MOOMOO"),
                    "state": str(quote["state"]), "as_of": _iso(field.get("as_of_ns"))}
        snapshot = (row.get("fields") or {}).get("price") or {}
        if snapshot.get("value"):
            return {"price": float(snapshot["value"]), "source": str(snapshot.get("source") or "SNAPSHOT"),
                    "state": "SNAPSHOT", "as_of": snapshot.get("as_of")}
        return None

    def _base(self, row: dict[str, Any], instrument_id: str, universe: str, view: str) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION, "generated_at": _iso(self._clock(), seconds=True),
            "instrument_id": instrument_id, "universe": universe, "symbol": str(row.get("symbol") or ""),
            "view": view, "market_session": self._session_label(), "capability": dict(CAPABILITY),
            "provider": None, "state": "UNAVAILABLE", "reason": None, "clock": None, "underlying": None,
            "completeness": None, "quality_flags": [], "fields_supplied": None, "expirations": [],
            "selected_expiration": None, "summary": None, "expiry_summary": None, "contracts": [],
        }

    def read(self, instrument_id: str, *, universe: str, expiration: str | None = None, view: str = "chain",
             snapshot_id: str | None = None) -> dict[str, Any] | None:
        if view not in VIEWS:
            raise ValueError("INVALID_OPTIONS_VIEW")
        row, _error = self._row_getter(instrument_id, universe, snapshot_id)
        if row is None:
            return None
        payload = self._base(row, instrument_id, universe, view)
        provider = self._provider_getter()
        provider_id = str(getattr(provider, "provider_id", ""))
        payload["provider"] = {"id": provider_id, "label": PROVIDER_LABELS.get(provider_id, provider_id),
                               "delivery": str(getattr(provider, "delivery", "SNAPSHOT"))}
        if any(marker in provider_id.lower() for marker in _FIXTURE_MARKERS):
            # The normal Screener path never shows fixture, replay, or demo chains.
            payload.update(state="UNAVAILABLE", reason="NON_CURRENT_PROVIDER_REFUSED")
            return payload
        symbol = str(row.get("market_data_id") or row.get("symbol") or "")
        entry, failure_status, failure_reason = self._chain(provider, symbol, instrument_id)
        if entry is None:
            payload.update(state="NOT_CONFIGURED" if failure_reason == PROVIDER_UNAVAILABLE
                           else "NOT_ENTITLED" if failure_status == "not_entitled" else "PROVIDER_UNAVAILABLE",
                           reason=failure_reason)
            return payload
        return self._populate(payload, entry, row, instrument_id, universe, expiration, view, failure_reason)

    def _populate(self, payload: dict[str, Any], entry: _Entry, row: dict[str, Any], instrument_id: str,
                  universe: str, expiration: str | None, view: str, failure_reason: str | None) -> dict[str, Any]:
        chain = entry.chain
        now = self._clock()
        age_s = max(0.0, now - entry.fetched_ns / 1e9)
        rows = list(chain.rows)
        dropped = sum(chain.dropped.values())
        payload["clock"] = {
            "fetched_at": _iso(entry.fetched_ns), "age_ms": int(age_s * 1000), "provider_as_of": None,
            "latest_contract_trade_at": chain.latest_contract_trade_at,
            "refresh_after_s": int(REFRESH_AFTER_S), "stale_after_s": int(STALE_AFTER_S),
            "provider_latency_ms": entry.latency_ms, "provider_cache_hit": entry.provider_cache_hit,
        }
        payload["completeness"] = {"provider_rows": chain.provider_rows, "usable": len(rows), "dropped": dropped,
                                   "dropped_reasons": dict(sorted(chain.dropped.items())),
                                   "expired_excluded": chain.expired_excluded,
                                   "unmapped_columns": list(chain.unmapped_columns)}
        payload["fields_supplied"] = chain.supplied_fields
        flags: list[str] = []
        if dropped:
            flags.append(OptionQualityFlag.OPTION_CHAIN_INCOMPLETE.value)
        if not rows:
            payload.update(state="NO_CHAIN", reason="NO_CURRENT_CONTRACTS" if not chain.expired_excluded
                           else "ONLY_EXPIRED_CONTRACTS", quality_flags=flags)
            return payload
        if failure_reason is not None or age_s >= STALE_AFTER_S:
            flags.append(OptionQualityFlag.OPTION_CHAIN_STALE.value)
            state, reason = "STALE", failure_reason or "SNAPSHOT_AGE_EXCEEDED"
        elif payload["market_session"] != "REGULAR":
            state, reason = "MARKET_CLOSED", "OPTIONS_MARKET_CLOSED"
        else:
            state, reason = "CURRENT_SNAPSHOT", None
        underlying = self._underlying(row, instrument_id, universe)
        price = underlying["price"] if underlying else None
        expirations = expiration_rows(rows)
        valid = {item["expiration"] for item in expirations}
        selected = expiration if expiration in valid else expirations[0]["expiration"]
        selected_rows = [item for item in rows if item.expiration == selected]
        payload.update(
            state=state, reason=reason, quality_flags=flags, underlying=underlying, expirations=expirations,
            selected_expiration=selected, summary=chain_analytics(rows, price),
            expiry_summary=chain_analytics(selected_rows, price) if view == "chain" else None,
            contracts=[item.to_dict() for item in selected_rows] if view == "chain" else [],
        )
        return payload


_SERVICE: ScreenerOptionsService | None = None
_SERVICE_LOCK = threading.Lock()


def options_service() -> ScreenerOptionsService:
    global _SERVICE
    with _SERVICE_LOCK:
        if _SERVICE is None:
            _SERVICE = ScreenerOptionsService()
        return _SERVICE


def read_options(instrument_id: str, **kwargs: Any) -> dict[str, Any] | None:
    return options_service().read(instrument_id, **kwargs)


__all__ = ["SCHEMA_VERSION", "ScreenerOptionsService", "chain_analytics", "current_option_chain_provider",
           "expiration_rows", "nearest_strike", "options_service", "read_options"]
