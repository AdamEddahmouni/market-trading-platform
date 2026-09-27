"""Selected-instrument Quick Preview projection for the Main Screener (S3).

One bounded request per selected instrument/timeframe/scope returns identity,
current quote, key snapshot data, current bars, AUTO_SR_V1 levels, the
deterministic filter explanation, classed movement evidence, and contextual
futures. Quote, bars, and levels keep separate clocks. Nothing here reads
replay, capture, or fixture data.
"""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime, timedelta
from typing import Any, Callable
from zoneinfo import ZoneInfo

from ..features.auto_support_resistance import METHOD, MIN_STRENGTH, Structure, build_structure, classify
from ..market_data.current_bars import PROVIDER as BAR_PROVIDER
from ..market_data.current_bars import SOURCE_ID as BAR_SOURCE_ID
from ..market_data.current_bars import BarSeries, CurrentBarsService, current_bars_service
from ..market_sessions import us_equity_session_label
from .screener_filters import catalog_entry, rule_matches, validate_filters
from .screener_futures_context import FuturesContextService
from .screener_projections import ScreenerService, screener_service

SCHEMA_VERSION = "screener-preview/1.0.0"
ET = ZoneInfo("America/New_York")
STRENGTH_SEMANTICS = "Zone strength 0-100 scores structural evidence (touches, recency, rejection, volume); it is not a probability that the zone holds."
MAX_HEADLINES = 3
LEVEL_CACHE_SIZE = 64
KEY_FIELDS = ("price", "change_pct", "volume", "rel_volume", "avg_volume", "float_shares", "short_float_pct",
              "market_cap", "rsi_14", "bid", "ask", "spread_pct")
QUOTE_FIELDS = ("price", "volume", "bid", "ask", "spread_pct")
_LABELS = {"bid": ("Bid", "USD"), "ask": ("Ask", "USD"), "spread_pct": ("Spread %", "percent")}
_PHRASES = {"gt": "above", "gte": "at or above", "lt": "below", "lte": "at or below", "eq": "equal to",
            "ne": "not equal to", "between": "within", "in": "one of", "not_in": "not one of", "contains": "containing"}
_SYMBOLS = {"gt": ">", "gte": "≥", "lt": "<", "lte": "≤", "eq": "=", "ne": "≠", "between": "in",
            "in": "in", "not_in": "not in", "contains": "contains"}
SIGNED_FIELDS = frozenset(("change_pct", "perf_week"))


def _iso(ns: int) -> str:
    return datetime.fromtimestamp(ns / 1_000_000_000, tz=UTC).isoformat().replace("+00:00", "Z")


def _compact(value: float) -> str:
    for size, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(value) >= size:
            return f"{value / size:.2f}".rstrip("0").rstrip(".") + suffix
    return f"{value:,.0f}"


def format_value(field: str, value: Any, unit: str) -> str:
    if isinstance(value, str):
        return value
    if unit == "USD":
        return f"${_compact(value)}" if field == "market_cap" else f"${value:,.2f}"
    if unit == "percent":
        return f"{value:+.2f}%" if field in SIGNED_FIELDS else f"{value:.2f}%"
    if unit == "shares":
        return _compact(value)
    if unit == "ratio":
        return f"{value:.2f}×"
    if unit == "days":
        return f"{value:.2f} days"
    return f"{value:.2f}".rstrip("0").rstrip(".")


# ---------------------------------------------------------------- why it matched
def explain_matches(row: dict[str, Any], filters: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-rule facts using the exact S2 predicate; never provider tokens."""

    rules = validate_filters(filters)
    if not rules:
        return {"state": "NO_ACTIVE_FILTERS", "items": []}
    items = []
    for rule in rules:
        entry = catalog_entry(rule["field"])
        text_field = entry["type"] == "text"
        observed = row.get(rule["field"]) if text_field else row.get("fields", {}).get(rule["field"], {}).get("value")
        wanted = rule["value"]
        expected = (", ".join(wanted) if isinstance(wanted, list) and text_field
                    else "–".join(format_value(rule["field"], v, entry["unit"]) for v in wanted) if isinstance(wanted, list)
                    else format_value(rule["field"], wanted, entry["unit"]))
        passed = rule_matches(row, rule)
        if observed is None:
            text = f"{entry['label']} unavailable; {_SYMBOLS[rule['operator']]} {expected} cannot match"
        else:
            shown = format_value(rule["field"], observed, entry["unit"])
            text = (f"{entry['label']} {shown} is {_PHRASES[rule['operator']]} {expected}" if passed
                    else f"{entry['label']} {shown} does not satisfy {_SYMBOLS[rule['operator']]} {expected}")
        items.append({"filter_id": rule["id"], "field": rule["field"], "label": entry["label"],
                      "operator": rule["operator"], "value": wanted, "observed": observed,
                      "passed": passed, "missing": observed is None, "text": text})
    return {"state": "MATCHED" if all(item["passed"] for item in items) else "NOT_MATCHED", "items": items}


# ------------------------------------------------------------ why it may be moving
def move_window_start(now: datetime) -> datetime:
    """Start of the evidence window: 16:00 ET on the weekday before the move's session day."""

    moment = now.astimezone(ET)
    day = moment.date() - timedelta(days=1 if moment.hour < 4 else 0)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    previous = day - timedelta(days=1)
    while previous.weekday() >= 5:
        previous -= timedelta(days=1)
    return datetime(previous.year, previous.month, previous.day, 16, tzinfo=ET)


def _headline_time(item: dict[str, Any]) -> datetime | None:
    raw = str((item.get("raw_fields") or {}).get("Date") or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%m/%d/%Y %H:%M"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=ET)  # Finviz export times are US Eastern.
        except ValueError:
            continue
    published = str(item.get("published_time") or "")
    try:
        parsed = datetime.fromisoformat(published.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else None


def current_headlines(news: dict[str, Any], symbol: str, now: datetime) -> list[dict[str, Any]]:
    start = move_window_start(now)
    found = []
    for item in news.get("items") or []:
        if symbol.upper() not in (item.get("tickers") or []):
            continue
        published = _headline_time(item)
        if published is None or not start <= published <= now:
            continue
        found.append({"headline": str(item.get("headline") or "").strip(), "url": item.get("url") or None,
                      "publisher": item.get("publisher_source") or "Finviz", "published_at": published.astimezone(UTC).isoformat().replace("+00:00", "Z"),
                      "provider": "FINVIZ_ELITE"})
    found.sort(key=lambda item: item["published_at"], reverse=True)
    return [item for item in found if item["headline"]][:MAX_HEADLINES]


def explain_movement(*, row: dict[str, Any], quote: dict[str, Any], levels: dict[str, Any],
                     futures: dict[str, Any], news: dict[str, Any], now: datetime) -> dict[str, Any]:
    """Classed evidence. Observed facts and derived context are never stated as causes."""

    fields = row.get("fields", {})
    items: list[dict[str, Any]] = []

    def add(kind: str, epistemic: str, text: str, source: str, as_of: str | None) -> None:
        items.append({"class": epistemic, "kind": kind, "text": text, "source": source, "as_of": as_of})

    change = fields.get("change_pct", {})
    if change.get("value") is not None:
        add("PRICE_MOVE", "OBSERVED", f"Change {format_value('change_pct', change['value'], 'percent')} on the session",
            change.get("source", "FINVIZ_ELITE"), change.get("as_of"))
    live_volume = quote.get("fields", {}).get("volume", {})
    volume = live_volume if quote.get("state") == "LIVE" and live_volume.get("value") is not None else fields.get("volume", {})
    if volume.get("value") is not None:
        add("VOLUME", "OBSERVED", f"Volume {_compact(volume['value'])}", volume.get("source", "FINVIZ_ELITE"),
            volume.get("as_of") or (_iso(volume["as_of_ns"]) if volume.get("as_of_ns") else None))
    headlines: list[dict[str, Any]] = []
    if news.get("success"):
        headlines = current_headlines(news, row["symbol"], now)
        for headline in headlines:
            add("HEADLINE", "OBSERVED", f"Headline: {headline['headline']} ({headline['publisher']})",
                "FINVIZ_ELITE", headline["published_at"])
    rvol = fields.get("rel_volume", {})
    if rvol.get("value") is not None:
        add("RELATIVE_VOLUME", "DERIVED", f"Relative volume {rvol['value']:.2f}× versus average volume",
            rvol.get("source", "FINVIZ_ELITE"), rvol.get("as_of"))
    short = fields.get("short_float_pct", {})
    if short.get("value") is not None:
        add("SHORT_INTEREST", "DERIVED", f"Short float {short['value']:.2f}% (published short-interest snapshot, not live borrow)",
            short.get("source", "FINVIZ_ELITE"), short.get("as_of"))
    resistance, support, testing = levels.get("resistance"), levels.get("support"), levels.get("testing")
    frame = f"{METHOD} · {levels.get('timeframe')}"
    # Proximity is relative to the price the levels were classified at, so it carries that clock.
    price_as_of = (levels.get("price") or {}).get("as_of")
    if testing:
        add("SR_PROXIMITY", "DERIVED", f"Price is inside a structure zone ${testing['lower']:.2f}–${testing['upper']:.2f} ({frame})",
            METHOD, price_as_of)
    if resistance:
        add("SR_PROXIMITY", "DERIVED", f"Price is {resistance['distance_pct']:.2f}% below the nearest resistance zone ${resistance['lower']:.2f}–${resistance['upper']:.2f} ({frame})",
            METHOD, price_as_of)
    if support:
        add("SR_PROXIMITY", "DERIVED", f"Price is {support['distance_pct']:.2f}% above the nearest support zone ${support['lower']:.2f}–${support['upper']:.2f} ({frame})",
            METHOD, price_as_of)
    for future in futures.get("items") or []:
        quote_row = future.get("quote") or {}
        if quote_row.get("state") == "LIVE" and quote_row.get("change_pct") is not None:
            contract = future["contract"].get("contract_id") or future["root"]
            add("FUTURES_CONTEXT", "DERIVED",
                f"Related {contract} {quote_row['change_pct']:+.2f}%: {future['relationship_reason'].rstrip('.').lower()}; contextual, not evidence of causation",
                quote_row.get("provider", ""), quote_row.get("as_of"))
    if not news.get("success"):
        add("CATALYST", "UNAVAILABLE", "Current news source unavailable; catalyst status cannot be checked",
            "FINVIZ_ELITE", None)
    if headlines:
        add("CAUSATION", "INSUFFICIENT_EVIDENCE", "Headline timing is observed; a causal link to this move is not established",
            "IMP", None)
    else:
        add("CAUSATION", "INSUFFICIENT_EVIDENCE", "No verified catalyst or causal driver identified from currently available evidence",
            "IMP", None)
    return {"items": items, "headline_window_start": move_window_start(now).astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "ai_synthesis": None}


# ------------------------------------------------------------------- the service
def _default_news() -> dict[str, Any]:
    from ..finviz.news import FinvizNewsClient

    try:
        return FinvizNewsClient().fetch_news()
    except Exception as exc:  # noqa: BLE001 — surfaced as an unavailable source
        return {"success": False, "error": type(exc).__name__, "items": []}


class ScreenerPreviewService:
    def __init__(self, *, screener: ScreenerService | None = None, bars: CurrentBarsService | None = None,
                 futures: FuturesContextService | None = None, news: Callable[[], dict[str, Any]] = _default_news,
                 now_ns: Callable[[], int] = time.time_ns) -> None:
        self._screener = screener or screener_service()
        self._bars = bars or current_bars_service()
        self._futures = futures or FuturesContextService(transport_getter=self._bars.transport)
        self._news = news
        self._now_ns = now_ns
        self._lock = threading.Lock()
        self._levels: dict[tuple[Any, ...], tuple[Structure, int]] = {}

    def _structure(self, series: BarSeries) -> tuple[Structure, int]:
        key = (series.instrument_id, series.timeframe, series.session_scope, series.latest_end_ns,
               len(series.bars), METHOD)
        with self._lock:
            cached = self._levels.get(key)
            if cached is None:
                cached = (build_structure(series.bars), self._now_ns())
                if len(self._levels) >= LEVEL_CACHE_SIZE:
                    self._levels.pop(next(iter(self._levels)))
                self._levels[key] = cached
            return cached

    def levels(self, series: BarSeries, quote: dict[str, Any]) -> dict[str, Any]:
        base = {"method": METHOD, "timeframe": series.timeframe, "session_scope": series.session_scope,
                "bar_source": BAR_SOURCE_ID, "provider": BAR_PROVIDER, "bar_state": series.state,
                "min_strength": MIN_STRENGTH, "strength_semantics": STRENGTH_SEMANTICS,
                "input_bar_count": len(series.bars),
                "input_latest_bar_end": _iso(series.latest_end_ns) if series.latest_end_ns else None}
        empty = {"calculated_at": None, "atr": None, "tolerance": None, "zones": [], "price": None,
                 "support": None, "resistance": None, "testing": None}
        if series.state == "UNAVAILABLE":
            reason = series.reason or "BAR_SOURCE_UNAVAILABLE"
            return {**base, **empty, "state": "UNAVAILABLE", "reason": reason, "reasons": [reason]}
        if series.state == "STALE":
            return {**base, **empty, "state": "UNAVAILABLE", "reason": "STALE_BAR_SOURCE", "reasons": ["STALE_BAR_SOURCE"]}
        structure, calculated_ns = self._structure(series)
        live_price = quote.get("fields", {}).get("price", {}).get("value") if quote.get("state") == "LIVE" else None
        if live_price is not None:
            price = {"value": live_price, "source": "L1_QUOTE", "state": "LIVE",
                     "as_of": _iso(quote["fields"]["price"]["as_of_ns"])}
        elif series.bars:
            price = {"value": series.bars[-1].close, "source": "LAST_BAR_CLOSE", "state": series.state,
                     "as_of": _iso(series.bars[-1].end_ns)}
        else:
            price = None
        result = classify(structure, price["value"] if price else None)
        if price is None and structure.reason is None:
            result = {**result, "reason": "MARKET_DATA_UNAVAILABLE", "reasons": ["MARKET_DATA_UNAVAILABLE"]}
        return {**base, **result, "calculated_at": _iso(calculated_ns), "atr": structure.atr,
                "volatility_basis": structure.volatility_basis,
                "tolerance": structure.tolerance, "zones": [zone.to_dict() for zone in structure.zones], "price": price}

    def read(self, instrument_id: str, *, timeframe: str = "5m", scope: str = "EXTENDED",
             filters: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
        rules = validate_filters([] if filters is None else filters)
        row, _error = self._screener.row_for(instrument_id)
        if row is None:
            return None
        series = self._bars.read(instrument_id, timeframe=timeframe, scope=scope)
        quote = self._screener.quote_for(instrument_id)
        levels = self.levels(series, quote)
        market_cap = row["fields"].get("market_cap", {}).get("value")
        futures = self._futures.read(sector=row.get("sector"), industry=row.get("industry"), market_cap=market_cap)
        now = datetime.fromtimestamp(self._now_ns() / 1_000_000_000, tz=UTC)
        news = self._news()
        key_data = []
        for field in KEY_FIELDS:
            live = quote.get("fields", {}).get(field)
            source = live if field in QUOTE_FIELDS and quote.get("state") == "LIVE" and live and live.get("value") is not None else row["fields"].get(field)
            label, unit = _LABELS.get(field) or (catalog_entry(field)["label"], catalog_entry(field)["unit"])
            key_data.append({"field": field, "label": label, "unit": unit,
                             "value": None if source is None else source.get("value"),
                             "source": None if source is None else source.get("source"),
                             "state": "UNAVAILABLE" if source is None or source.get("value") is None else source.get("state"),
                             "as_of": None if source is None else source.get("as_of") or (_iso(source["as_of_ns"]) if source.get("as_of_ns") else None)})
        return {
            "schema_version": SCHEMA_VERSION,
            "generated_at": _iso(self._now_ns()),
            "market_session": us_equity_session_label(),
            "instrument": {**row["instrument"], "symbol": row["symbol"], "company": row["company"],
                           "sector": row.get("sector"), "industry": row.get("industry")},
            "snapshot_as_of": row["fields"].get("price", {}).get("as_of"),
            "quote": quote,
            "key_data": key_data,
            "bars": series.to_dict(),
            "levels": levels,
            "why": {"matched": explain_matches(row, rules),
                    "moving": explain_movement(row=row, quote=quote, levels=levels, futures=futures, news=news, now=now)},
            "futures": futures,
        }


_PREVIEW: ScreenerPreviewService | None = None
_PREVIEW_LOCK = threading.Lock()


def read_preview(instrument_id: str, **kwargs: Any) -> dict[str, Any] | None:
    global _PREVIEW
    with _PREVIEW_LOCK:
        if _PREVIEW is None:
            _PREVIEW = ScreenerPreviewService()
    return _PREVIEW.read(instrument_id, **kwargs)


__all__ = ["ScreenerPreviewService", "explain_matches", "explain_movement", "format_value", "move_window_start",
           "read_preview"]
