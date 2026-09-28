"""Public spot Crypto market data for the Main Screener."""

from __future__ import annotations

import math
import json
import os
import threading
import time
import urllib.parse
import urllib.request
from collections import OrderedDict
from datetime import UTC, datetime
from typing import Any

from ..features.auto_support_resistance import METHOD, MIN_STRENGTH, build_structure, classify
from ..market_data.current_bars import Bar
from ..xa01.compatibility import register_crypto_pair
from ..xa01.enums import InstrumentKind, XaAssetClass
from ..xa01.errors import Xa01Error
from ..xa01.identity import crypto_pair_identity_key, derive_canonical_id
from .screener_filters import apply_filters, field_value
from .screener_query import ScreenerQuery, order_rows, page_payload

VENUE = "KRAKEN"
SOURCE = "KRAKEN_SPOT_PUBLIC"
TICKER_FIELDS = ("price", "change_pct", "base_volume", "quote_volume", "bid", "ask", "spread_pct",
                 "high_24h", "low_24h", "trade_count")
CATALOG_TTL_S = 900
SNAPSHOT_TTL_S = 20
FAILURE_TTL_S = 30
RETAINED_RESULTS = 3
_INTERVAL_SECONDS = {"1m": 60, "5m": 300, "15m": 900}
STRENGTH_SEMANTICS = ("Zone strength 0-100 scores structural evidence (touches, recency, rejection, volume); "
                      "it is not a probability that the zone holds.")


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class KrakenSpotClient:
    """Anonymous official Kraken Spot REST market-data adapter; never account APIs."""

    BASE = "https://api.kraken.com/0/public/"

    def _get(self, endpoint: str, **params: Any) -> dict[str, Any]:
        url = self.BASE + endpoint + "?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(url, headers={"User-Agent": "IMP-Screener/1.0", "Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status != 200:
                raise ValueError("KRAKEN_HTTP_UNAVAILABLE")
            raw = response.read(10_000_001)
        if len(raw) > 10_000_000:
            raise ValueError("KRAKEN_RESPONSE_TOO_LARGE")
        payload = json.loads(raw)
        if not isinstance(payload, dict) or payload.get("error") or not isinstance(payload.get("result"), dict):
            raise ValueError("KRAKEN_PROTOCOL_ERROR")
        return payload

    def asset_pairs(self) -> dict[str, Any]:
        return self._get("AssetPairs", assetVersion=1)

    def ticker(self, pair: list[str] | None = None) -> dict[str, Any]:
        return self._get("Ticker", **({"pair": ",".join(pair), "assetVersion": 1} if pair else {"assetVersion": 1}))

    def ohlc(self, pair: str, interval: int) -> dict[str, Any]:
        return self._get("OHLC", pair=pair, interval=interval, assetVersion=1)


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (ValueError, TypeError):
        return None
    return number if math.isfinite(number) else None


def _at(value: Any, index: int) -> float | None:
    return _number(value[index]) if isinstance(value, list) and len(value) > index else None


def _increment(decimals: Any) -> str | None:
    """Kraken publishes precision as a decimal count; the step is 10^-decimals."""

    if isinstance(decimals, bool) or not isinstance(decimals, int) or not 0 <= decimals <= 18:
        return None
    return "1" if decimals == 0 else f"0.{'0' * (decimals - 1)}1"


def _identity(base: str, quote: str) -> str:
    try:
        return register_crypto_pair(base_asset=base, quote_asset=quote, venue_id=VENUE,
                                    product_type="SPOT", provider_id="KRAKEN", provider_symbol=f"{base}/{quote}")
    except Xa01Error:
        # A catalog refresh can update descriptive metadata without changing the pair identity.
        return derive_canonical_id(instrument_kind=InstrumentKind.CRYPTO_PAIR, asset_class=XaAssetClass.CRYPTO,
                                   identity_key=crypto_pair_identity_key(base_asset=base, quote_asset=quote,
                                                                         venue_id=VENUE))


def project_catalog(payload: dict[str, Any], *, as_of: str) -> list[dict[str, Any]]:
    if payload.get("error") or not isinstance(payload.get("result"), dict):
        raise ValueError("CRYPTO_CATALOG_UNAVAILABLE")
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for product_id, product in payload["result"].items():
        if not isinstance(product_id, str) or not isinstance(product, dict):
            raise ValueError("CRYPTO_CATALOG_MALFORMED")
        # This is the documented Kraken Spot AssetPairs endpoint. Currency classes
        # and online status are explicit provider metadata, never name heuristics.
        if product.get("aclass_base") != "currency" or product.get("aclass_quote") != "currency":
            continue
        if product.get("status") != "online":
            continue
        base, quote = product.get("base"), product.get("quote")
        if not isinstance(base, str) or not isinstance(quote, str) or not base or not quote or base == quote:
            raise ValueError("CRYPTO_CATALOG_MALFORMED")
        base, quote = base.upper(), quote.upper()
        pair = f"{base}/{quote}"
        if pair != product_id.upper() or pair in seen:
            raise ValueError("CRYPTO_CATALOG_IDENTITY_MISMATCH")
        seen.add(pair)
        rows.append({
            "instrument": {"instrument_id": _identity(base, quote), "venue_id": VENUE,
                           "asset_class": "CRYPTO", "instrument_kind": "CRYPTO_PAIR",
                           "tradability": "DISCOVERY_ONLY"},
            "symbol": pair, "company": pair, "sector": None, "industry": None,
            "base_asset": base, "quote_asset": quote, "venue": VENUE, "product_type": "SPOT",
            "status": "ONLINE", "provider_symbol": product_id, "provider_wsname": product.get("wsname"),
            "min_order_size": product.get("ordermin"), "min_order_notional": product.get("costmin"),
            "price_increment": product.get("tick_size"), "base_decimals": product.get("lot_decimals"),
            "base_increment": _increment(product.get("lot_decimals")),
            "quote_increment": _increment(product.get("cost_decimals")),
            "price_decimals": product.get("pair_decimals"),
            "catalog_as_of": as_of,
            "fields": {field: {"value": None, "source": SOURCE, "state": "UNAVAILABLE", "as_of": None}
                       for field in TICKER_FIELDS},
        })
    return rows


def project_ticker(payload: dict[str, Any]) -> dict[str, float | None]:
    price, open_utc = _at(payload.get("c"), 0), _number(payload.get("o"))
    bid, ask = _at(payload.get("b"), 0), _at(payload.get("a"), 0)
    volume, vwap = _at(payload.get("v"), 1), _at(payload.get("p"), 1)
    if price is not None and price <= 0:
        price = None
    if bid is not None and bid <= 0:
        bid = None
    if ask is not None and ask <= 0:
        ask = None
    if volume is not None and volume < 0:
        volume = None
    spread = (ask - bid) / ((ask + bid) / 2) * 100 if bid and ask and ask >= bid else None
    return {"price": price, "change_pct": (price / open_utc - 1) * 100 if price and open_utc and open_utc > 0 else None,
            "base_volume": volume, "quote_volume": volume * vwap if volume is not None and vwap is not None else None,
            "bid": bid, "ask": ask, "spread_pct": spread,
            "high_24h": _at(payload.get("h"), 1), "low_24h": _at(payload.get("l"), 1),
            "trade_count": _at(payload.get("t"), 1)}


def project_ohlc(payload: dict[str, Any], *, pair: str, timeframe: str, received_at: str) -> dict[str, Any]:
    interval = {"1m": 60, "5m": 300, "15m": 900}.get(timeframe)
    if interval is None:
        raise ValueError("INVALID_PREVIEW_BAR_SCOPE")
    values = payload.get("result", {}).get(pair)
    if payload.get("error") or not isinstance(values, list) or len(values) < 2:
        raise ValueError("CRYPTO_BARS_UNAVAILABLE")

    def bar(item: Any) -> dict[str, Any]:
        if not isinstance(item, list) or len(item) < 7:
            raise ValueError("CRYPTO_BARS_MALFORMED")
        start = int(item[0])
        prices = [_number(item[index]) for index in (1, 2, 3, 4)]
        volume = _number(item[6])
        if any(value is None or value <= 0 for value in prices) or volume is None or volume < 0:
            raise ValueError("CRYPTO_BARS_MALFORMED")
        return {"time": start, "start": datetime.fromtimestamp(start, UTC).isoformat().replace("+00:00", "Z"),
                "end": datetime.fromtimestamp(start + interval, UTC).isoformat().replace("+00:00", "Z"),
                "open": prices[0], "high": prices[1], "low": prices[2], "close": prices[3],
                "volume": volume, "session": "24_7"}

    bars = [bar(item) for item in values]
    if any(bars[index]["time"] >= bars[index + 1]["time"] for index in range(len(bars) - 1)):
        raise ValueError("CRYPTO_BARS_OUT_OF_ORDER")
    closed, forming = bars[:-1], bars[-1]
    return {"timeframe": timeframe, "session_scope": "24_7", "provider": SOURCE,
            "source_id": f"KRAKEN_OHLC:{pair}:{timeframe}", "state": "CURRENT", "reason": None,
            "provider_reason": None, "received_at": received_at,
            "latest_complete_bar_end": closed[-1]["end"], "bar_count": len(closed),
            "bars": closed, "forming": forming}


class CryptoScreener:
    def __init__(self, *, client: Any | None = None, env: Any = os.environ,
                 now: Any = _now, clock: Any = time.monotonic) -> None:
        self._client = client or KrakenSpotClient()
        self._env, self._now, self._clock = env, now, clock
        self._lock = threading.RLock()
        self._catalog_cache: tuple[float, str, list[dict[str, Any]], str | None] | None = None
        self._snapshot_cache: tuple[float, str, dict[str, dict[str, float | None]], str | None] | None = None
        self._results: OrderedDict[str, tuple[str, list[dict[str, Any]], dict[str, Any]]] = OrderedDict()
        self._bars: OrderedDict[tuple[str, str], tuple[float, dict[str, Any]]] = OrderedDict()
        self._sequence = 0

    def _catalog(self, force: bool = False) -> tuple[list[dict[str, Any]], str | None, str | None]:
        if self._env.get("IMP_CRYPTO_LIVE") != "1":
            return [], None, "CRYPTO_NOT_CONFIGURED"
        with self._lock:
            cache = self._catalog_cache
            if cache and not force and self._clock() - cache[0] < (FAILURE_TTL_S if cache[3] else CATALOG_TTL_S):
                return cache[2], cache[1], cache[3]
            try:
                as_of = self._now()
                rows = project_catalog(self._client.asset_pairs(), as_of=as_of)
                error = None
            except Exception:  # noqa: BLE001 — public provider boundary fails closed
                rows, as_of = (cache[2], cache[1]) if cache else ([], None)
                error = "CRYPTO_CATALOG_UNAVAILABLE"
            self._catalog_cache = (self._clock(), as_of or "", rows, error)
            return rows, as_of, error

    def _snapshot(self, rows: list[dict[str, Any]], force: bool = False) -> tuple[str | None, dict[str, dict[str, float | None]], str | None]:
        with self._lock:
            cache = self._snapshot_cache
            if cache and not force and self._clock() - cache[0] < (FAILURE_TTL_S if cache[3] else SNAPSHOT_TTL_S):
                return cache[1], cache[2], cache[3]
            if not rows:
                return None, {}, "MARKET_SNAPSHOT_UNAVAILABLE"
            try:
                payload = self._client.ticker()
                vendor = payload["result"]
                # Kraken documents the no-pair Ticker response as all tradable
                # pairs. Every admitted online catalog row must be present.
                if not isinstance(vendor, dict) or not {r["provider_symbol"] for r in rows} <= vendor.keys():
                    raise ValueError("MARKET_SNAPSHOT_INCOMPLETE")
                values = {row["instrument"]["instrument_id"]: project_ticker(vendor[row["provider_symbol"]])
                          for row in rows}
                as_of, error = self._now(), None
            except ValueError as exc:
                values, as_of, error = {}, None, str(exc)
            except Exception:  # noqa: BLE001 — provider timeout/connection failure
                values, as_of, error = {}, None, "MARKET_SNAPSHOT_UNAVAILABLE"
            self._snapshot_cache = (self._clock(), as_of or "", values, error)
            return as_of, values, error

    @staticmethod
    def _decorate(row: dict[str, Any], values: dict[str, float | None], as_of: str | None) -> dict[str, Any]:
        fields = {field: {"value": values.get(field), "source": SOURCE,
                          "state": "SNAPSHOT" if values.get(field) is not None else "UNAVAILABLE",
                          "as_of": as_of if values.get(field) is not None else None}
                  for field in TICKER_FIELDS}
        if fields["change_pct"]["value"] is not None:
            fields["change_pct"]["basis"] = "UTC_DAY_OPEN_TO_LAST"
        if fields["quote_volume"]["value"] is not None:
            fields["quote_volume"]["basis"] = "24H_BASE_VOLUME_X_24H_VWAP"
        return {**row, "fields": fields, "snapshot_id": as_of}

    def read(self, query: ScreenerQuery, *, force_refresh: bool = False) -> dict[str, Any]:
        with self._lock:
            if query.result_set:
                retained = self._results.get(query.result_set)
                if retained is None or retained[0] != query.identity:
                    raise ValueError("RESULT_SET_CHANGED")
                ordered = retained[1]
                return {**retained[2], "generated_at": self._now(), "result_set_id": query.result_set,
                        **page_payload(query, ordered)}
        rows, catalog_as_of, catalog_error = self._catalog(force_refresh)
        snapshot_as_of, values, snapshot_error = self._snapshot(rows, force_refresh) if rows else (None, {}, None)
        snapshot_ok = snapshot_as_of is not None and snapshot_error is None
        summary = ({"id": snapshot_as_of, "as_of": snapshot_as_of, "source": SOURCE, "complete": True,
                    "total": len(rows), "returned": len(values),
                    "priced": sum(item.get("price") is not None for item in values.values()),
                    "refused": 0, "refused_reason": None} if snapshot_ok else None)
        if query.uses_snapshot and not snapshot_ok:
            return {**self._envelope(rows, catalog_as_of, catalog_error, snapshot_error, summary),
                    "source_error": snapshot_error or catalog_error or "MARKET_SNAPSHOT_UNAVAILABLE",
                    "result_set_id": None, **page_payload(query, [])}
        decorated = [self._decorate(row, values.get(row["instrument"]["instrument_id"], {}), snapshot_as_of)
                     for row in rows]
        needle = query.search.casefold().replace("-", "/")
        matched = [row for row in apply_filters(decorated, list(query.filters), field_value)
                   if not needle or any(needle in str(row.get(field) or "").casefold()
                                        for field in ("symbol", "base_asset", "quote_asset", "venue", "provider_symbol"))]
        ordered = order_rows(matched, query.sort, query.descending, field_value)
        envelope = self._envelope(rows, catalog_as_of, catalog_error, snapshot_error, summary)
        with self._lock:
            self._sequence += 1
            result_set_id = f"crypto-{self._sequence}"
            self._results[result_set_id] = (query.identity, ordered, envelope)
            while len(self._results) > RETAINED_RESULTS:
                self._results.popitem(last=False)
        return {**envelope,
                "source_error": catalog_error if not rows else None, "result_set_id": result_set_id,
                **page_payload(query, ordered)}

    def _envelope(self, rows: list[dict[str, Any]], catalog_as_of: str | None, catalog_error: str | None,
                  snapshot_error: str | None, summary: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"schema_version": "screener/1.0.0", "universe": "CRYPTO", "generated_at": self._now(),
                "market_session": "24_7" if rows else "UNAVAILABLE", "universe_as_of": catalog_as_of,
                "screener_as_of": summary["as_of"] if summary else catalog_as_of,
                "evaluation": "SNAPSHOT" if summary else "CATALOG", "snapshot": summary,
                "unfiltered_count": len(rows),
                "provider_health": [
                    {"provider": SOURCE, "role": "CATALOG", "state": "NOT_CONFIGURED" if catalog_error == "CRYPTO_NOT_CONFIGURED" else
                     "STALE" if catalog_error and rows else "UNAVAILABLE" if catalog_error else "CURRENT", "reason": catalog_error},
                    {"provider": SOURCE, "role": "MARKET_SNAPSHOT", "state": "CURRENT" if summary else
                     "UNAVAILABLE", "reason": snapshot_error}],
                "source_error": catalog_error if not rows else None}

    def row_for(self, instrument_id: str) -> tuple[dict[str, Any] | None, str | None]:
        rows, _as_of, error = self._catalog()
        row = next((row for row in rows if row["instrument"]["instrument_id"] == instrument_id), None)
        if row is None:
            return None, error or "UNKNOWN_INSTRUMENT"
        cache = self._snapshot_cache
        return (self._decorate(row, cache[2].get(instrument_id, {}), cache[1]) if cache and not cache[3] else row), error

    def window(self, symbols: list[str]) -> dict[str, Any]:
        rows, _as_of, error = self._catalog()
        by_id = {row["instrument"]["instrument_id"]: row for row in rows}
        if not set(symbols) <= by_id.keys():
            raise ValueError("UNKNOWN_OR_DUPLICATE_INSTRUMENT")
        quotes: dict[str, Any] = {}
        if symbols:
            try:
                result = self._client.ticker([by_id[key]["provider_symbol"] for key in symbols])["result"]
            except Exception:  # noqa: BLE001
                result = {}
        else:
            result = {}
        as_of = self._now()
        for key in symbols:
            product = by_id[key]["provider_symbol"]
            values = project_ticker(result[product]) if product in result else {}
            quotes[key] = {"state": "SNAPSHOT" if values else "UNAVAILABLE", "session_state": "24_7",
                           "reason": None if values else error or "QUOTE_UNAVAILABLE",
                           "fields": self._decorate(by_id[key], values, as_of)["fields"]}
        return {"schema_version": "screener/1.0.0", "generated_at": as_of, "market_session": "24_7",
                "active": 0, "cap": 30, "quotes": quotes}

    def bars(self, instrument_id: str, timeframe: str) -> dict[str, Any]:
        row, error = self.row_for(instrument_id)
        if row is None:
            raise ValueError(error or "UNKNOWN_INSTRUMENT")
        interval = {"1m": 1, "5m": 5, "15m": 15}.get(timeframe)
        if interval is None:
            raise ValueError("INVALID_PREVIEW_BAR_SCOPE")
        key = (instrument_id, timeframe)
        with self._lock:
            cached = self._bars.get(key)
            if cached and self._clock() - cached[0] < 30:
                return cached[1]
        try:
            payload = self._client.ohlc(row["provider_symbol"], interval)
            result = project_ohlc(payload, pair=row["provider_symbol"], timeframe=timeframe, received_at=self._now())
        except Exception:  # noqa: BLE001 — no synthetic candles on provider failure
            result = {"timeframe": timeframe, "session_scope": "24_7", "provider": SOURCE,
                      "source_id": f"KRAKEN_OHLC:{row['provider_symbol']}:{timeframe}",
                      "state": "UNAVAILABLE", "reason": "CRYPTO_BARS_UNAVAILABLE", "provider_reason": None,
                      "received_at": None, "latest_complete_bar_end": None, "bar_count": 0, "bars": [], "forming": None}
        with self._lock:
            self._bars[key] = (self._clock(), result)
            while len(self._bars) > 16:
                self._bars.popitem(last=False)
        return result

    @staticmethod
    def levels(bars: dict[str, Any], quote: dict[str, Any]) -> dict[str, Any]:
        """Canonical auto support/resistance over the pair's own 24/7 venue bars."""

        base = {"method": METHOD, "timeframe": bars["timeframe"], "session_scope": "24_7",
                "bar_source": bars["source_id"], "provider": SOURCE, "bar_state": bars["state"],
                "min_strength": MIN_STRENGTH, "strength_semantics": STRENGTH_SEMANTICS,
                "input_bar_count": bars["bar_count"], "input_latest_bar_end": bars["latest_complete_bar_end"]}
        empty = {"calculated_at": None, "atr": None, "tolerance": None, "zones": [], "price": None,
                 "support": None, "resistance": None, "testing": None}
        if bars["state"] != "CURRENT":
            reason = bars["reason"] or "BAR_SOURCE_UNAVAILABLE"
            return {**base, **empty, "state": "UNAVAILABLE", "reason": reason, "reasons": [reason]}
        series = [Bar(start_ns=item["time"] * 1_000_000_000,
                      end_ns=(item["time"] + (_INTERVAL_SECONDS[bars["timeframe"]])) * 1_000_000_000,
                      open=item["open"], high=item["high"], low=item["low"], close=item["close"],
                      volume=item["volume"], session="24_7") for item in bars["bars"]]
        structure = build_structure(series)
        last = quote.get("fields", {}).get("price", {})
        if quote.get("state") == "SNAPSHOT" and last.get("value") is not None:
            price = {"value": last["value"], "source": "KRAKEN_TICKER_LAST", "state": "SNAPSHOT", "as_of": last.get("as_of")}
        elif series:
            price = {"value": series[-1].close, "source": "LAST_BAR_CLOSE", "state": "CURRENT",
                     "as_of": bars["latest_complete_bar_end"]}
        else:
            price = None
        result = classify(structure, price["value"] if price else None)
        return {**base, **result, "calculated_at": _now(), "atr": structure.atr,
                "volatility_basis": structure.volatility_basis, "tolerance": structure.tolerance,
                "zones": [zone.to_dict() for zone in structure.zones], "price": price}

    def chart(self, instrument_id: str, timeframe: str) -> dict[str, Any] | None:
        """S4 Charts panel payload: the same venue bars and levels the Quick Preview uses."""

        row, _error = self.row_for(instrument_id)
        if row is None:
            return None
        quote = self.window([instrument_id])["quotes"][instrument_id]
        bars = self.bars(instrument_id, timeframe)
        return {"schema_version": "screener-chart/1.0.0", "generated_at": self._now(), "market_session": "24_7",
                "instrument": {**row["instrument"], "symbol": row["symbol"], "company": row["company"]},
                "quote": quote, "bars": bars, "levels": self.levels(bars, quote)}


def _stream_pair(instrument_id: str) -> tuple[str, int, int] | None:
    """Kraken WS v2 symbol and checksum precision for a current catalog row."""

    row, _error = crypto_screener_service().row_for(instrument_id)
    if row is None:
        return None
    price_decimals, qty_decimals = row.get("price_decimals"), row.get("base_decimals")
    if not isinstance(price_decimals, int) or not isinstance(qty_decimals, int):
        return None
    return row["provider_symbol"], price_decimals, qty_decimals


def _stream_runtime() -> Any | None:
    if os.environ.get("IMP_CRYPTO_LIVE") != "1":
        return None
    from ..crypto_market.kraken_stream import kraken_stream_runtime

    return kraken_stream_runtime(_stream_pair)


_SPECIALIST: Any = None
_SPECIALIST_LOCK = threading.Lock()


def crypto_specialist_service() -> Any:
    """S4 Order Flow / CVD / Level 2 for Crypto: the same projections over the Kraken stream."""

    global _SPECIALIST
    from ..crypto_market.kraken_stream import BOOK, TRADES
    from .screener_specialist import ScreenerSpecialistService

    with _SPECIALIST_LOCK:
        if _SPECIALIST is None:
            _SPECIALIST = ScreenerSpecialistService(
                runtime_getter=_stream_runtime,
                known_instrument=lambda instrument_id: crypto_screener_service().row_for(instrument_id)[0] is not None,
                session_label=lambda: "24_7", trades_capability=TRADES, depth_capability=BOOK,
                panels=("order_flow", "cvd", "level2", "charts"),
                # Kraken acknowledges an unsubscribe immediately; there is no
                # OpenD-style minimum hold, so a released pair frees its slot at once.
                provider_hold_seconds=0)
    return _SPECIALIST


_SERVICE: CryptoScreener | None = None
_SERVICE_LOCK = threading.Lock()


def crypto_screener_service() -> CryptoScreener:
    global _SERVICE
    with _SERVICE_LOCK:
        if _SERVICE is None:
            _SERVICE = CryptoScreener()
    return _SERVICE
