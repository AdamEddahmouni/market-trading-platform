"""Screener S11: cross-universe News, Headlines, Sentiment & Analysis.

News is an intelligence *view* over the active universe (US Equities, ETFs,
Futures, Bonds, Crypto), never a universe of its own. Three read models:

* ``feed``        — the Screener News view: current stories for the universe;
* ``instrument``  — the News & Analysis panel / Quick Preview for one instrument;
* ``synthesis``   — explicit, cached AI synthesis on the canonical inference boundary.

Every provider is fetched behind its adapter and reported independently
(Finviz Elite bulk export, NewsAPI, Finnhub, public RSS/Atom catalog, SEC EDGAR
filings, local FinBERT, AI). Items are normalized to the canonical
``NewsArticleEvent``, exact duplicates removed with canonical ``dedupe``, then
grouped into stories (``news.story_clusters``), categorized
(``news.event_taxonomy``), and associated to instruments with an explicit match
basis (``news.instrument_matching``). Epistemic classes stay separate:
OBSERVED (headline, publisher, times), DERIVED (category, match, sentiment,
attention, post-headline reaction), AI_SYNTHESIS, UNAVAILABLE, INSUFFICIENT_EVIDENCE.
Nothing here reads fixture, replay, or frozen donor data.
"""

from __future__ import annotations

import os
import re
import threading
import time
from collections import Counter
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from ..news.contracts import NewsArticleEvent, PublicationTimeQuality
from ..news.dedupe import dedupe_events
from ..news.event_taxonomy import METHOD as TAXONOMY_METHOD
from ..news.event_taxonomy import EventCategory, classify_text
from ..news.finbert_sentiment import FinbertSentiment, finbert_sentiment, summarize
from ..news.instrument_matching import (
    AMBIGUOUS, CONTEXT, CRYPTO_CONTEXT_CATEGORIES, EXACT, InstrumentProfile, MatchResult, is_relevant, match_profile,
    profile_for_row,
)
from ..news.normalize import normalize_raw_item
from ..news.rss_feeds import RssNewsSource, aggregate_state
from ..news.sec_filings_news import SecFilingNews
from ..news.story_clusters import METHOD as CLUSTER_METHOD
from ..news.story_clusters import ClusterInput, cluster_stories
from ..news.timestamps import parse_utc_iso
from .screener_squeeze_sources import BackgroundCache
from .screener_universes import BONDS, CRYPTO, FUTURES, UNIVERSES, US_EQUITIES, US_ETFS

SCHEMA_VERSION = "screener-news/1.0.0"
INSTRUMENT_SCHEMA_VERSION = "screener-news-instrument/1.0.0"
ET = ZoneInfo("America/New_York")
WINDOWS = {"1h": 3600, "4h": 4 * 3600, "24h": 24 * 3600, "72h": 72 * 3600}
INSTRUMENT_WINDOW = "72h"
SORTS = (("newest", "Newest"), ("oldest", "Oldest"), ("sources", "Most sources"), ("relevance", "Match strength"))
SENTIMENT_FILTERS = ("POSITIVE", "NEUTRAL", "NEGATIVE")
DEFAULT_LIMIT, MAX_LIMIT = 100, 200
MAX_INSTRUMENT_STORIES, COMPACT_STORIES = 50, 5
MAX_SCORED_STORIES = 400
PER_SYMBOL_TTL_S = {"newsapi": 900.0, "finnhub": 600.0, "sec_filings": 600.0}
RSS_TTL_S = 300.0
INDEX_TTL_S = 600.0
PROVIDER_WAIT_S = 8.0
NEWSAPI_DAILY_GUARD = 90  # Donor quota discipline: the free NewsAPI tier allows 100 requests/day.
REACTION_HORIZONS = (("+5m", 5), ("+15m", 15), ("+1h", 60))
ATTENTION_WINDOWS = (("15m", 15 * 60), ("1h", 3600), ("4h", 4 * 3600), ("24h", 24 * 3600))
ATTENTION_METHOD = ("Headline and story counts per trailing window over current provider coverage; prior = the "
                    "preceding window of equal length. A provider outage lowers coverage, never attention.")
REACTION_NOTE = ("Post-headline price reaction: the instrument's price change after the headline's publication time, "
                 "from completed 5-minute bars. Temporal association only, not evidence that the story caused the move.")
BRIEF_METHOD = ("Deterministic brief: current stories in the window grouped by keyword category, with story, "
                "headline, and source counts. No model; no narrative beyond the grouped headlines.")

PROVIDER_LABELS = {"finviz": "Finviz Elite", "newsapi": "NewsAPI", "finnhub": "Finnhub", "rss": "RSS (public feeds)",
                   "sec_filings": "SEC EDGAR filings", "finbert": "FinBERT (local)", "ai": "AI synthesis"}
PROVIDER_KINDS = {"finviz": "NEWS", "newsapi": "NEWS", "finnhub": "NEWS", "rss": "NEWS", "sec_filings": "OFFICIAL_FILING",
                  "finbert": "SENTIMENT", "ai": "AI"}
# Usable states. DELAYED is a working provider whose plan delays articles (NewsAPI Developer): it contributes
# stories and never makes the whole view PARTIAL, but it is never shown as CURRENT.
USABLE_STATES = frozenset({"CURRENT", "STALE", "DELAYED"})


def _provider_terms() -> dict[str, dict[str, Any]]:
    from ..news.providers import FINNHUB_PLAN_TERMS, NEWSAPI_PLAN_TERMS

    return {"newsapi": NEWSAPI_PLAN_TERMS, "finnhub": FINNHUB_PLAN_TERMS,
            "finbert": {"runtime": "LOCAL_MODEL", "cost_usd": 0, "basis": "IMP_DERIVED_FINBERT"}}
# Category families that are meaningful per universe (an equity "SEC" story is not crypto regulation).
UNIVERSE_GROUPS = {
    US_EQUITIES: frozenset({"CORPORATE", "REGULATORY", "MACRO", "FILING"}),
    US_ETFS: frozenset({"CORPORATE", "REGULATORY", "MACRO", "CRYPTO", "FILING"}),
    FUTURES: frozenset({"MACRO", "CRYPTO"}),
    BONDS: frozenset({"MACRO"}),
    CRYPTO: frozenset({"CRYPTO", "MACRO"}),
}
CHART_UNIVERSES = frozenset({US_EQUITIES, US_ETFS, CRYPTO})
_TICKER_TEXT = re.compile(r"\$([A-Z]{1,5})\b|\((?:(?:NASDAQ|NYSE|NYSEARCA|NYSE ARCA|AMEX|CBOE)\s*:\s*)([A-Z.]{1,6})\)")
_CUSIP_TEXT = re.compile(r"\b(912[0-9A-Z]{6})\b")
_CONF_RANK = {EXACT: 0, CONTEXT: 1, AMBIGUOUS: 2}


def _iso(moment: datetime | None) -> str | None:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ") if moment else None


def _env_set(env: Callable[[str], str | None], name: str) -> bool:
    return bool((env(name) or "").strip())


# ------------------------------------------------------------------ records
@dataclass(slots=True)
class NewsRecord:
    event: NewsArticleEvent
    provider_id: str
    source_type: str
    tickers: tuple[str, ...]
    cik: str | None
    available_time: str | None
    ingested_time: str
    categories: tuple[EventCategory, ...] = ()
    matches: list[MatchResult] = field(default_factory=list)

    @property
    def published(self) -> datetime | None:
        return parse_utc_iso(self.event.published_time) if self.event.published_time_quality == PublicationTimeQuality.KNOWN else None

    @property
    def moment(self) -> datetime | None:
        """Publication time when known; the retrieval time only as an explicit age proxy."""

        return self.published or parse_utc_iso(self.event.retrieved_time)


@dataclass(slots=True)
class Story:
    story_id: str
    members: list[NewsRecord]

    @property
    def representative(self) -> NewsRecord:
        known = [record for record in self.members if record.published]
        pool = known or self.members
        return min(pool, key=lambda record: (record.moment or datetime.max.replace(tzinfo=UTC), record.event.event_id))

    @property
    def published(self) -> datetime | None:
        times = [record.published for record in self.members if record.published]
        return min(times) if times else None

    @property
    def moment(self) -> datetime | None:
        return self.published or min((record.moment for record in self.members if record.moment), default=None)

    @property
    def categories(self) -> list[EventCategory]:
        seen: dict[str, EventCategory] = {}
        for record in self.members:
            for item in record.categories:
                seen.setdefault(item.id, item)
        return list(seen.values())

    @property
    def matches(self) -> list[MatchResult]:
        best: dict[tuple[str, str], MatchResult] = {}
        for record in self.members:
            for match in record.matches:
                key = (match.symbol, match.basis)
                if key not in best or _CONF_RANK[match.confidence] < _CONF_RANK[best[key].confidence]:
                    best[key] = match
        return sorted(best.values(), key=lambda match: (_CONF_RANK[match.confidence], match.symbol, match.basis))

    @property
    def strength(self) -> int:
        return min((_CONF_RANK[match.confidence] for match in self.matches), default=3)

    @property
    def source_count(self) -> int:
        return len({record.event.publisher_source.lower() or record.provider_id for record in self.members})

    @property
    def source_type(self) -> str:
        types = {record.source_type for record in self.members}
        return "OFFICIAL_FILING" if "OFFICIAL_FILING" in types else "OFFICIAL_RELEASE" if "OFFICIAL_RELEASE" in types else "NEWS"

    def to_dict(self, sentiment: dict[str, Any]) -> dict[str, Any]:
        rep = self.representative
        published = [record.published for record in self.members if record.published]
        retrieved = [parse_utc_iso(record.event.retrieved_time) for record in self.members]
        flags = sorted({flag for record in self.members for flag in record.event.quality_flags})
        return {
            "story_id": self.story_id, "headline": rep.event.headline, "summary": rep.event.summary or None,
            "url": rep.event.url or None, "published_at": _iso(self.published),
            "published_time_quality": PublicationTimeQuality.KNOWN.value if self.published else PublicationTimeQuality.UNKNOWN.value,
            "latest_published_at": _iso(max(published)) if published else None,
            "first_retrieved_at": _iso(min(item for item in retrieved if item)) if any(retrieved) else rep.event.retrieved_time,
            "source_type": self.source_type,
            "sources": [{"provider_id": record.provider_id, "provider_label": PROVIDER_LABELS.get(record.provider_id, record.provider_id),
                         "publisher": record.event.publisher_source or PROVIDER_LABELS.get(record.provider_id, record.provider_id),
                         "url": record.event.url or None, "published_at": _iso(record.published),
                         "retrieved_at": record.event.retrieved_time, "available_at": record.available_time,
                         "ingested_at": record.ingested_time, "source_type": record.source_type}
                        for record in sorted(self.members, key=lambda item: (item.moment or datetime.max.replace(tzinfo=UTC), item.event.event_id))],
            "source_count": self.source_count, "provider_count": len({record.provider_id for record in self.members}),
            "categories": [item.to_dict() for item in self.categories],
            "matches": [match.to_dict() for match in self.matches[:8]],
            "sentiment": sentiment, "quality_flags": flags,
        }


def _finviz_published(item: dict[str, Any]) -> str:
    """Finviz export times are US Eastern wall clock (S3 rule); converted to UTC, never assumed UTC."""

    raw = str((item.get("raw_fields") or {}).get("Date") or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%m/%d/%Y %H:%M"):
        try:
            return _iso(datetime.strptime(raw, fmt).replace(tzinfo=ET)) or ""
        except ValueError:
            continue
    return ""


def provider_status(provider_id: str, result: dict[str, Any] | None, *, scope: str, pending: bool = False) -> dict[str, Any]:
    base = {"id": provider_id, "label": PROVIDER_LABELS.get(provider_id, provider_id),
            "kind": PROVIDER_KINDS.get(provider_id, "NEWS"), "scope": scope}
    terms = _provider_terms().get(provider_id)
    if terms:
        base["terms"] = dict(terms)
    if pending:
        return {**base, "state": "PENDING", "reason": "FETCHING", "fetched_at": None, "item_count": None}
    if result is None:
        return {**base, "state": "NOT_APPLICABLE", "reason": "NOT_APPLICABLE_FOR_UNIVERSE", "fetched_at": None, "item_count": None}
    fetched = result.get("received_at")
    if result.get("state") in ("NOT_APPLICABLE",):
        return {**base, "state": "NOT_APPLICABLE", "reason": result.get("reason"), "fetched_at": None, "item_count": None}
    if result.get("success"):
        return {**base, "state": result.get("state") or "CURRENT", "reason": result.get("reason"), "fetched_at": fetched,
                "item_count": len(result.get("items") or [])}
    error = str(result.get("error") or "PROVIDER_ERROR")
    env_reason = {"newsapi": ("IMP_NEWSAPI_LIVE_NOT_SET", "NEWSAPI_API_KEY_NOT_SET"),
                  "finnhub": ("IMP_FINNHUB_LIVE_NOT_SET", "FINNHUB_API_KEY_NOT_SET"),
                  "finviz": ("FINVIZ_LIVE_DISABLED", "FINVIZ_API_KEY_NOT_SET")}.get(provider_id, (error, error))
    if error == "LIVE_DISABLED" or result.get("state") == "LIVE_DISABLED":
        return {**base, "state": "LIVE_DISABLED", "reason": env_reason[0] if error == "LIVE_DISABLED" else error, "fetched_at": None, "item_count": None}
    if error == "NOT_CONFIGURED" or result.get("state") == "NOT_CONFIGURED":
        return {**base, "state": "NOT_CONFIGURED", "reason": env_reason[1] if error == "NOT_CONFIGURED" else error, "fetched_at": None, "item_count": None}
    if error in ("HTTP_429", "DAILY_QUOTA_GUARD") or result.get("state") == "RATE_LIMITED":
        state = "RATE_LIMITED"
    elif error in ("HTTP_401", "HTTP_403", "FINVIZ_NEWS_LOGIN_PAGE") or result.get("state") == "AUTH_FAILED":
        state = "AUTH_FAILED"
    else:
        state = "ERROR"
    return {**base, "state": state, "reason": error, "fetched_at": fetched, "item_count": None}


# ------------------------------------------------------------------ the service
def _default_finviz() -> dict[str, Any]:
    from ..finviz.news import FinvizNewsClient

    try:
        return FinvizNewsClient().fetch_news()
    except Exception as exc:  # noqa: BLE001 — surfaced as an unavailable provider, never raised
        return {"success": False, "error": type(exc).__name__, "items": []}


def _default_catalog(universe: str) -> tuple[list[dict[str, Any]], str | None]:
    from .screener_projections import read_screener
    from .screener_query import MAX_PAGE_LIMIT

    if universe == BONDS:
        # News keys BONDS on Treasury CUSIPs only; paging the whole universe (hundreds of thousands of fund-held
        # rows since S16) truncated at 20,000 rows in maturity order and missed most Treasuries.
        from .screener_bonds import bond_screener_service

        return bond_screener_service().treasury_rows()
    rows: list[dict[str, Any]] = []
    offset, result_set = 0, None
    for _ in range(40):  # bounded: 20,000 rows
        page = read_screener(universe=universe, offset=offset, limit=MAX_PAGE_LIMIT, result_set=result_set)
        if page.get("source_error") and not page.get("rows"):
            return rows, str(page["source_error"])
        rows.extend(page.get("rows") or [])
        result_set = page.get("result_set_id")
        if not page.get("has_more") or not result_set:
            break
        offset += len(page.get("rows") or [])
    return rows, None


def _default_row(instrument_id: str, universe: str) -> dict[str, Any] | None:
    from .screener_multi import multi_screener_service

    row, _error = multi_screener_service().row_for(instrument_id, universe=universe)
    return row


def _default_chart(instrument_id: str, universe: str) -> dict[str, Any] | None:
    from .screener_preview import preview_service

    return preview_service().chart(instrument_id, timeframe="5m", scope="EXTENDED", universe=universe)


def _default_synthesizer():
    """Production synthesis provider: Anthropic when its key is configured, else a configured local model."""

    from ..intelligence.inference.local_provider import select_synthesis_provider
    from ..intelligence.inference.screener_synthesis import ScreenerSynthesizer
    from ..local_state.external_cache import imp_cache_dir
    from ..news.config import configured_value

    selection = select_synthesis_provider(configured_value, cache_dir=imp_cache_dir())
    return ScreenerSynthesizer(provider=selection.provider,
                               not_configured_reason=selection.reason or "NO_SYNTHESIS_PROVIDER_CONFIGURED")


@dataclass(slots=True)
class _UniverseIndex:
    built_at: float
    error: str | None
    by_ticker: dict[str, tuple[str, str]]        # ticker → (instrument_id, symbol)
    profiles: list[InstrumentProfile]            # context profiles (futures roots, crypto bases, ETF themes, Treasury)
    cusips: dict[str, tuple[str, str]]
    # Matches depend only on the event and this index, so they are computed once per event per index build.
    matches: dict[str, list[MatchResult]] = field(default_factory=dict)


class ScreenerNewsService:
    def __init__(self, *, finviz: Callable[[], dict[str, Any]] = _default_finviz, rss: RssNewsSource | None = None,
                 newsapi_factory: Callable[[], Any] | None = None, finnhub_factory: Callable[[], Any] | None = None,
                 sec: SecFilingNews | None = None, sentiment: FinbertSentiment | None = None,
                 catalog: Callable[[str], tuple[list[dict[str, Any]], str | None]] = _default_catalog,
                 row_for: Callable[[str, str], dict[str, Any] | None] = _default_row,
                 chart: Callable[[str, str], dict[str, Any] | None] = _default_chart,
                 synthesizer_factory: Callable[[], Any] = _default_synthesizer,
                 cache: BackgroundCache | None = None, clock: Callable[[], float] = time.time,
                 wait_s: float = PROVIDER_WAIT_S, env: Callable[[str], str | None] = os.environ.get,
                 newsapi_quota_path: Path | None = None) -> None:
        self._finviz = finviz
        self._rss = rss or RssNewsSource()
        self._newsapi_factory = newsapi_factory
        self._finnhub_factory = finnhub_factory
        self._sec = sec or SecFilingNews()
        self._sentiment = sentiment
        self._catalog = catalog
        self._row_for = row_for
        self._chart = chart
        self._synthesizer_factory = synthesizer_factory
        self._synthesizer: Any = None
        self._cache = cache or BackgroundCache(clock=clock)
        self._clock = clock
        self._wait_s = wait_s
        self._env = env
        self._lock = threading.Lock()
        self._indexes: dict[str, _UniverseIndex] = {}
        self._newsapi_day: tuple[str, int] = ("", 0)
        # Persisted so an API restart does not reset the Developer plan's 100 requests/day budget.
        self._newsapi_quota_path = newsapi_quota_path
        if newsapi_quota_path is not None:
            from ..local_state.external_cache import read_manifest

            saved = read_manifest(newsapi_quota_path) or {}
            if isinstance(saved.get("day"), str) and isinstance(saved.get("count"), int):
                self._newsapi_day = (saved["day"], saved["count"])
        self.provider_requests: Counter[str] = Counter()

    # -------------------------------------------------------------- providers
    def sentiment_model(self) -> FinbertSentiment:
        return self._sentiment or finbert_sentiment()

    def _await(self, key: tuple[Any, ...], job: Callable[[], Any], ttl_s: float) -> Any:
        """Background fetch with a bounded wait; returns the entry or None while still pending."""

        entry = self._cache.get(key, job, ttl_s=ttl_s)
        deadline = time.monotonic() + self._wait_s
        while entry is None and time.monotonic() < deadline:
            time.sleep(0.05)
            entry = self._cache.get(key, job, ttl_s=ttl_s)
        return entry

    def _finviz_items(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        def job() -> dict[str, Any]:
            self.provider_requests["finviz"] += 1
            return self._finviz()

        entry = self._await(("finviz",), job, ttl_s=120.0)
        if entry is None:
            return [], provider_status("finviz", None, scope="UNIVERSE", pending=True)
        result = entry.value if entry.ok else {"success": False, "error": entry.reason, "items": []}
        items = []
        for item in result.get("items") or []:
            published = _finviz_published(item)
            items.append({**item, "published_time": published or item.get("published_time") or "",
                          "quality_flags": ["PUBLISHED_TIME_US_EASTERN_WALL_CLOCK"] if published else []})
        status = provider_status("finviz", {**result, "received_at": result.get("received_at") or entry.fetched_at},
                                 scope="UNIVERSE")
        return items, status

    def _rss_items(self, universe: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if not self._rss.feeds_for(universe):
            return [], provider_status("rss", None, scope="UNIVERSE")

        def job() -> dict[str, Any]:
            self.provider_requests["rss"] += 1
            return self._rss.collect(universe)

        entry = self._await(("rss", universe), job, ttl_s=RSS_TTL_S)
        if entry is None:
            return [], provider_status("rss", None, scope="UNIVERSE", pending=True)
        if not entry.ok:
            return [], provider_status("rss", {"success": False, "error": entry.reason}, scope="UNIVERSE")
        state, reason = aggregate_state(entry.value["feeds"])
        fetched = max((feed["fetched_at"] for feed in entry.value["feeds"] if feed["fetched_at"]), default=None)
        status = {"id": "rss", "label": PROVIDER_LABELS["rss"], "kind": "NEWS", "scope": "UNIVERSE", "state": state,
                  "reason": reason, "fetched_at": fetched, "item_count": len(entry.value["items"]),
                  "feeds": entry.value["feeds"]}
        return entry.value["items"], status

    def _newsapi_guard(self) -> bool:
        today = datetime.fromtimestamp(self._clock(), tz=UTC).date().isoformat()
        with self._lock:
            day, count = self._newsapi_day
            if day != today:
                day, count = today, 0
            if count >= NEWSAPI_DAILY_GUARD:
                self._newsapi_day = (day, count)
                return False
            self._newsapi_day = (day, count + 1)
            if self._newsapi_quota_path is not None:
                from ..local_state.external_cache import write_json_atomic

                try:
                    write_json_atomic(self._newsapi_quota_path, {"day": day, "count": count + 1, "limit": NEWSAPI_DAILY_GUARD})
                except OSError:
                    pass  # the in-memory guard still applies
            return True

    def _per_symbol(self, provider_id: str, query: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        def job() -> dict[str, Any]:
            self.provider_requests[provider_id] += 1
            if provider_id == "newsapi":
                from ..news.providers import NewsApiClient

                client = self._newsapi_factory() if self._newsapi_factory else NewsApiClient()
                if getattr(client, "_live_enabled", True) and getattr(client, "_api_key", "x") and not self._newsapi_guard():
                    return {"success": False, "error": "DAILY_QUOTA_GUARD", "items": []}
                return client.fetch_news(query)
            if provider_id == "finnhub":
                from ..news.providers import FinnhubNewsClient

                client = self._finnhub_factory() if self._finnhub_factory else FinnhubNewsClient()
                return client.fetch_news(query)
            return self._sec.fetch(query)

        entry = self._await((provider_id, query.upper()), job, ttl_s=PER_SYMBOL_TTL_S[provider_id])
        if entry is None:
            return [], provider_status(provider_id, None, scope="INSTRUMENT", pending=True)
        result = entry.value if entry.ok else {"success": False, "error": entry.reason, "items": []}
        return list(result.get("items") or []), provider_status(provider_id, result, scope="INSTRUMENT")

    # ------------------------------------------------------------ normalizing
    def _records(self, raw: list[tuple[str, dict[str, Any]]], universe: str) -> list[NewsRecord]:
        ingested = _iso(datetime.fromtimestamp(self._clock(), tz=UTC)) or ""
        events: list[NewsArticleEvent] = []
        meta: dict[str, tuple[str, dict[str, Any]]] = {}
        for provider_id, item in raw:
            retrieved = str(item.get("received_time") or item.get("received_at") or ingested)
            try:
                event = normalize_raw_item({**item, "tickers": item.get("tickers") or [], "asset_class": UNIVERSES[universe].asset_class},
                                           provider_id=provider_id, source_id=str(item.get("feed_id") or provider_id),
                                           retrieved_time=retrieved)
            except ValueError:
                continue  # fail closed: no identity material
            if not event.headline.strip():
                continue
            extra = tuple(str(flag) for flag in item.get("quality_flags") or ())
            if extra:
                event = replace(event, quality_flags=tuple(dict.fromkeys((*event.quality_flags, *extra))))
            events.append(event)
            meta[event.event_id] = (provider_id, item)
        kept, _duplicates = dedupe_events(events)
        groups = UNIVERSE_GROUPS[universe]
        records = []
        for event in kept:
            provider_id, item = meta[event.event_id]
            available_ns = item.get("available_time_ns")
            available = _iso(datetime.fromtimestamp(available_ns / 1e9, tz=UTC)) if isinstance(available_ns, int) else None
            record = NewsRecord(event=event, provider_id=provider_id,
                                source_type=str(item.get("source_type") or ("OFFICIAL_FILING" if provider_id == "sec_filings" else "NEWS")),
                                tickers=tuple(str(ticker).upper() for ticker in item.get("tickers") or ()),
                                cik=str(item["cik"]) if item.get("cik") else None, available_time=available,
                                ingested_time=ingested)
            record.categories = classify_text(event.headline, event.summary, groups=groups)
            if record.source_type == "OFFICIAL_FILING":
                from ..news.event_taxonomy import FILING

                record.categories = (FILING, *record.categories)
            records.append(record)
        return records

    # -------------------------------------------------------- universe index
    def _index(self, universe: str) -> _UniverseIndex:
        now = self._clock()
        with self._lock:
            cached = self._indexes.get(universe)
        if cached is not None and cached.built_at + INDEX_TTL_S > now:
            return cached
        rows, error = self._catalog(universe)
        by_ticker: dict[str, tuple[str, str]] = {}
        profiles: list[InstrumentProfile] = []
        cusips: dict[str, tuple[str, str]] = {}
        if universe in (US_EQUITIES, US_ETFS):
            for row in rows:
                by_ticker[str(row.get("symbol") or "").upper()] = (row["instrument"]["instrument_id"], str(row.get("symbol")))
            if universe == US_ETFS:
                from ..news.instrument_matching import ETF_THEMES

                profiles = [profile_for_row(universe, row) for row in rows if str(row.get("symbol") or "").upper() in ETF_THEMES]
        elif universe == FUTURES:
            leads: dict[str, dict[str, Any]] = {}
            for row in rows:
                root = str(row.get("root") or "")
                if root and (root not in leads or row.get("lead")):
                    leads[root] = row
            profiles = [profile_for_row(universe, row) for _root, row in sorted(leads.items())]
        elif universe == BONDS:
            for row in rows:
                cusip = str(row.get("cusip") or (row.get("instrument") or {}).get("cusip") or "").upper()
                if cusip:
                    cusips[cusip] = (row["instrument"]["instrument_id"], str(row.get("symbol") or cusip))
            profiles = [profile_for_row(universe, {"instrument": {"instrument_id": ""}, "symbol": "U.S. Treasury",
                                                   "company": "U.S. Treasury securities"})]
        elif universe == CRYPTO:
            bases: dict[str, dict[str, Any]] = {}
            for row in rows:
                base = str(row.get("base_asset") or "")
                if base and (base not in bases or row.get("quote_asset") == "USD"):
                    bases[base] = row
            profiles = [profile_for_row(universe, row) for _base, row in sorted(bases.items())]
        index = _UniverseIndex(now, error, by_ticker, profiles, cusips)
        with self._lock:
            self._indexes[universe] = index
        return index

    def _universe_matches(self, record: NewsRecord, universe: str, index: _UniverseIndex) -> list[MatchResult]:
        cached = index.matches.get(record.event.event_id)
        if cached is not None:
            return cached
        event = record.event
        matches: list[MatchResult] = []
        if universe in (US_EQUITIES, US_ETFS):
            for ticker in record.tickers:
                hit = index.by_ticker.get(ticker)
                if hit:
                    matches.append(MatchResult(hit[0], hit[1], "PROVIDER_TICKER", EXACT, ticker))
            for found in _TICKER_TEXT.finditer(f"{event.headline} {event.summary}"):
                ticker = (found.group(1) or found.group(2) or "").upper()
                hit = index.by_ticker.get(ticker)
                if hit:
                    matches.append(MatchResult(hit[0], hit[1], "EXACT_TICKER", EXACT, ticker))
        if universe == BONDS:
            for found in _CUSIP_TEXT.finditer(f"{event.headline} {event.summary}"):
                hit = index.cusips.get(found.group(1))
                if hit:
                    matches.append(MatchResult(hit[0], hit[1], "EXACT_CUSIP", EXACT, found.group(1)))
        categories = [item.id for item in record.categories]
        for profile in index.profiles:
            for match in match_profile(profile, headline=event.headline, summary=event.summary, tickers=record.tickers,
                                       categories=categories):
                if universe == CRYPTO and match.basis in ("MACRO_CONTEXT", "VENUE_MATCH"):
                    # Sector- or venue-wide evidence is one match, never repeated for every pair.
                    label = "Crypto sector" if match.basis == "MACRO_CONTEXT" else f"{match.term} (venue)"
                    matches.append(MatchResult(None, label, match.basis, CONTEXT, match.term))
                    continue
                matches.append(MatchResult(profile.instrument_id or None, profile.symbol, match.basis, match.confidence, match.term))
        best: dict[tuple[str, str], MatchResult] = {}
        for match in matches:
            key = (match.symbol, match.basis)
            if key not in best or _CONF_RANK[match.confidence] < _CONF_RANK[best[key].confidence]:
                best[key] = match
        result = sorted(best.values(), key=lambda match: (_CONF_RANK[match.confidence], match.symbol))
        if len(index.matches) < 20_000:
            index.matches[event.event_id] = result
        return result

    # ------------------------------------------------------------- stories
    @staticmethod
    def _stories(records: list[NewsRecord]) -> list[Story]:
        by_key = {record.event.event_id: record for record in records}
        clusters = cluster_stories([ClusterInput(key=record.event.event_id, headline=record.event.headline,
                                                 url=record.event.url, provider_id=record.provider_id,
                                                 provider_native_id=record.event.provider_native_id,
                                                 published_time=_iso(record.published) or "",
                                                 retrieved_time=record.event.retrieved_time)
                                    for record in records])
        return [Story(cluster.cluster_id, [by_key[key] for key in cluster.member_keys]) for cluster in clusters]

    def _score(self, stories: list[Story]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
        model = self.sentiment_model()
        status = model.status()
        if status["state"] == "NOT_CONFIGURED" or not stories:
            state = {"state": status["state"] if status["state"] != "CURRENT" else "NOT_SCORED", "label": None,
                     "probabilities": None, "model_id": None}
            return {story.story_id: dict(state) for story in stories}, status
        bounded = stories[:MAX_SCORED_STORIES]
        scores = model.score([story.representative.event.headline for story in bounded])
        result = {story.story_id: score for story, score in zip(bounded, scores)}
        for story in stories[MAX_SCORED_STORIES:]:
            result[story.story_id] = {"state": "NOT_SCORED", "label": None, "probabilities": None, "model_id": None}
        return result, model.status()

    @staticmethod
    def _window(window: str, now: datetime) -> dict[str, Any]:
        return {"id": window, "start": _iso(now - timedelta(seconds=WINDOWS[window])), "end": _iso(now)}

    @staticmethod
    def _in_window(story: Story, start: datetime, end: datetime) -> bool:
        moment = story.moment
        return moment is not None and start <= moment <= end + timedelta(minutes=5)

    # ---------------------------------------------------------------- feed
    def feed(self, *, universe: str, window: str = "24h", sort: str = "newest", source: str | None = None,
             category: str | None = None, sentiment: str | None = None, instrument: str | None = None,
             offset: int = 0, limit: int = DEFAULT_LIMIT, view: str = "feed") -> dict[str, Any]:
        if universe not in UNIVERSES:
            raise ValueError("UNKNOWN_UNIVERSE")
        if window not in WINDOWS:
            raise ValueError("INVALID_WINDOW")
        if sort not in dict(SORTS):
            raise ValueError("INVALID_SORT")
        if sentiment is not None and sentiment not in SENTIMENT_FILTERS:
            raise ValueError("INVALID_SENTIMENT")
        if view not in ("feed", "brief"):
            raise ValueError("INVALID_VIEW")
        if not 0 <= offset <= 100_000 or not 1 <= limit <= MAX_LIMIT:
            raise ValueError("INVALID_PAGE")
        now = datetime.fromtimestamp(self._clock(), tz=UTC)
        index = self._index(universe)
        raw: list[tuple[str, dict[str, Any]]] = []
        finviz_items, finviz_status = self._finviz_items()
        rss_items, rss_status = self._rss_items(universe)
        raw += [("finviz", item) for item in finviz_items]
        raw += [("rss", item) for item in rss_items]
        providers = [finviz_status, rss_status,
                     {**provider_status("newsapi", None, scope="INSTRUMENT"), "reason": "INSTRUMENT_SCOPE_ONLY"},
                     {**provider_status("finnhub", None, scope="INSTRUMENT"), "reason": "INSTRUMENT_SCOPE_ONLY"},
                     {**provider_status("sec_filings", None, scope="INSTRUMENT"), "reason": "INSTRUMENT_SCOPE_ONLY"}]
        records = self._records(raw, universe)
        for record in records:
            record.matches = self._universe_matches(record, universe, index)
        relevant = [record for record in records if is_relevant(record.matches)]
        start = now - timedelta(seconds=WINDOWS[window])
        stories = [story for story in self._stories(relevant) if self._in_window(story, start, now)]
        headline_count = sum(len(story.members) for story in stories)
        sentiments, model_status = self._score(stories)
        sentiment_enabled = bool(stories) and all(sentiments[story.story_id]["state"] == "SCORED" for story in stories)
        sentiment_reason = None if sentiment_enabled else (
            model_status.get("reason") if model_status["state"] != "CURRENT" else "NOT_ALL_STORIES_SCORED" if stories else "NO_STORIES")
        source_counts = Counter(provider for story in stories for provider in {record.provider_id for record in story.members})
        category_counts: Counter[str] = Counter()
        category_meta: dict[str, EventCategory] = {}
        for story in stories:
            for item in story.categories:
                category_counts[item.id] += 1
                category_meta[item.id] = item
        filtered = stories
        if source:
            filtered = [story for story in filtered if any(record.provider_id == source for record in story.members)]
        if category:
            filtered = [story for story in filtered if any(item.id == category for item in story.categories)]
        applied_sentiment = sentiment if sentiment and sentiment_enabled else None
        if applied_sentiment:
            filtered = [story for story in filtered if sentiments[story.story_id].get("label") == applied_sentiment]
        if instrument:
            filtered = [story for story in filtered if any(match.instrument_id == instrument and match.confidence != AMBIGUOUS
                                                           for match in story.matches)]
        filtered = self._sorted(filtered, sort)
        page = filtered[offset:offset + limit]
        states = {status["state"] for status in providers if status["scope"] == "UNIVERSE" and status["state"] != "NOT_APPLICABLE"}
        state, reason = self._overall(states, index.error)
        payload = {
            "schema_version": SCHEMA_VERSION, "generated_at": _iso(now), "universe": universe,
            "window": self._window(window, now), "state": state, "reason": reason, "providers": providers,
            "sentiment_model": {key: model_status.get(key) for key in ("state", "reason", "model_id", "model_revision", "loaded",
                                                                       "runtime", "basis", "model_source")},
            "filters": {
                "sources": [{"id": key, "label": PROVIDER_LABELS.get(key, key), "count": count}
                            for key, count in sorted(source_counts.items())],
                "categories": [{**category_meta[key].to_dict(), "count": count}
                               for key, count in sorted(category_counts.items(), key=lambda item: (-item[1], item[0]))],
                "sentiment": {"enabled": sentiment_enabled, "reason": sentiment_reason},
                "applied": {"source": source, "category": category, "sentiment": applied_sentiment, "instrument": instrument},
            },
            "sorts": [{"id": key, "label": label} for key, label in SORTS],
            "sort": sort, "result_count": len(filtered), "headline_count": headline_count,
            "offset": offset, "limit": limit, "has_more": offset + limit < len(filtered),
            "stories": [story.to_dict(sentiments[story.story_id]) for story in page],
            "brief": self._brief(stories, providers, now, window) if view == "brief" else None,
            "methods": {"clusters": CLUSTER_METHOD, "categories": TAXONOMY_METHOD},
        }
        return payload

    @staticmethod
    def _sorted(stories: list[Story], sort: str) -> list[Story]:
        epoch = datetime.min.replace(tzinfo=UTC)
        if sort == "oldest":
            return sorted(stories, key=lambda story: (story.moment or epoch, story.story_id))
        if sort == "sources":
            return sorted(stories, key=lambda story: (-story.source_count, -(story.moment or epoch).timestamp(), story.story_id))
        if sort == "relevance":
            return sorted(stories, key=lambda story: (story.strength, -(story.moment or epoch).timestamp(), story.story_id))
        return sorted(stories, key=lambda story: (-(story.moment or epoch).timestamp(), story.story_id))

    @staticmethod
    def _overall(states: set[str], index_error: str | None) -> tuple[str, str | None]:
        good = states & USABLE_STATES
        if "PENDING" in states and not good:
            return "PENDING", "PROVIDERS_FETCHING"
        if not good:
            if states and states <= {"NOT_CONFIGURED", "LIVE_DISABLED"}:
                return "NOT_CONFIGURED", "NO_NEWS_PROVIDER_CONFIGURED"
            return "UNAVAILABLE", "NO_CURRENT_NEWS_PROVIDER"
        if good == {"DELAYED"}:
            # Only delayed development data is available: usable, but never a current picture.
            return "PARTIAL", "ONLY_DELAYED_PROVIDERS"
        if states - {"CURRENT", "DELAYED"} or index_error:
            return "PARTIAL", index_error or "SOME_PROVIDERS_NOT_CURRENT"
        return "CURRENT", None

    def _brief(self, stories: list[Story], providers: list[dict[str, Any]], now: datetime, window: str) -> dict[str, Any]:
        groups: dict[str, list[Story]] = {}
        uncategorized = 0
        for story in stories:
            if not story.categories:
                uncategorized += 1
            for item in story.categories:
                groups.setdefault(item.id, []).append(story)
        meta = {item.id: item for story in stories for item in story.categories}
        publishers = {record.event.publisher_source.lower() for story in stories for record in story.members}
        missing = sorted(status["id"] for status in providers if status["scope"] == "UNIVERSE" and status["state"] not in ("CURRENT", "NOT_APPLICABLE"))
        current = [status["id"] for status in providers if status["scope"] == "UNIVERSE" and status["state"] == "CURRENT"]
        note = (f"Sparse coverage: {len(stories)} stories from {len(current)} current provider(s); read as a partial picture."
                if len(stories) < 5 or len(current) < 2 else
                f"{len(stories)} stories from {len(current)} current providers.")
        return {
            "generated_at": _iso(now), "window": self._window(window, now), "method": BRIEF_METHOD,
            "story_count": len(stories), "headline_count": sum(len(story.members) for story in stories),
            "source_count": len(publishers), "missing_providers": missing,
            "groups": [{"category": meta[key].to_dict(), "story_count": len(items),
                        "source_count": len({record.event.publisher_source.lower() for story in items for record in story.members}),
                        "latest_published_at": _iso(max((story.moment for story in items if story.moment), default=None)),
                        "story_ids": [story.story_id for story in self._sorted(items, "newest")[:8]]}
                       for key, items in sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))],
            "uncategorized_count": uncategorized, "coverage_note": note,
        }

    # ---------------------------------------------------------- instrument
    def _instrument_sources(self, universe: str, profile: InstrumentProfile, row: dict[str, Any]
                            ) -> tuple[list[tuple[str, dict[str, Any]]], list[dict[str, Any]]]:
        raw: list[tuple[str, dict[str, Any]]] = []
        providers: list[dict[str, Any]] = []
        finviz_items, finviz_status = self._finviz_items()
        if universe in (US_EQUITIES, US_ETFS):
            finviz_items = [item for item in finviz_items if profile.symbol.upper() in (item.get("tickers") or [])]
        raw += [("finviz", item) for item in finviz_items]
        providers.append(finviz_status)
        rss_items, rss_status = self._rss_items(universe)
        raw += [("rss", item) for item in rss_items]
        providers.append(rss_status)
        if universe in (US_EQUITIES, US_ETFS, CRYPTO):
            from ..news.instrument_matching import CRYPTO_ASSET_NAMES, entity_name

            if universe == CRYPTO:
                names = CRYPTO_ASSET_NAMES.get(str(row.get("base_asset") or "").upper())
                query = names[0] if names else None
            else:
                name = entity_name(row.get("company"))
                query = name if name and len(name) >= 4 else profile.symbol
            if query:
                items, status = self._per_symbol("newsapi", query)
                raw += [("newsapi", {**item, "tickers": [t for t in item.get("tickers") or [] if t == profile.symbol.upper()]})
                        for item in items]
                providers.append(status)
            else:
                providers.append({**provider_status("newsapi", None, scope="INSTRUMENT"), "reason": "NO_QUERYABLE_NAME"})
        else:
            providers.append(provider_status("newsapi", None, scope="INSTRUMENT"))
        if universe in (US_EQUITIES, US_ETFS):
            items, status = self._per_symbol("finnhub", profile.symbol)
            raw += [("finnhub", item) for item in items]
            providers.append(status)
        else:
            providers.append(provider_status("finnhub", None, scope="INSTRUMENT"))
        if universe == US_EQUITIES:
            items, status = self._per_symbol("sec_filings", profile.symbol)
            raw += [("sec_filings", item) for item in items]
            providers.append(status)
        else:
            providers.append(provider_status("sec_filings", None, scope="INSTRUMENT"))
        return raw, providers

    def instrument(self, *, universe: str, instrument_id: str, compact: bool = False) -> dict[str, Any] | None:
        if universe not in UNIVERSES:
            raise ValueError("UNKNOWN_UNIVERSE")
        if not instrument_id or len(instrument_id) > 128:
            raise ValueError("INVALID_INSTRUMENT")
        row = self._row_for(instrument_id, universe)
        if row is None:
            return None
        profile = profile_for_row(universe, row)
        now = datetime.fromtimestamp(self._clock(), tz=UTC)
        raw, providers = self._instrument_sources(universe, profile, row)
        records = self._records(raw, universe)
        for record in records:
            record.matches = match_profile(profile, headline=record.event.headline, summary=record.event.summary,
                                           tickers=record.tickers, categories=[item.id for item in record.categories],
                                           cik=record.cik)
            if universe == CRYPTO and not any(item.id in CRYPTO_CONTEXT_CATEGORIES for item in record.categories):
                # A pair's panel takes sector context only from regulatory/exchange events; generic
                # crypto-market commentary stays in the universe News view.
                record.matches = [match for match in record.matches if match.basis != "MACRO_CONTEXT"]
            if record.source_type == "OFFICIAL_FILING" and profile.symbol.upper() in record.tickers:
                record.matches = [MatchResult(profile.instrument_id, profile.symbol, "EXACT_ENTITY", EXACT,
                                              f"CIK {record.cik}" if record.cik else profile.symbol), *record.matches]
        relevant = [record for record in records if is_relevant(record.matches)]
        start = now - timedelta(seconds=WINDOWS[INSTRUMENT_WINDOW])
        stories = self._sorted([story for story in self._stories(relevant) if self._in_window(story, start, now)], "newest")
        shown = stories[:COMPACT_STORIES if compact else MAX_INSTRUMENT_STORIES]
        sentiments, model_status = self._score(stories)
        summary = summarize([sentiments[story.story_id] for story in stories], model_status=model_status)
        latest_scored = next((story for story in stories if sentiments[story.story_id].get("state") == "SCORED"), None)
        summary["latest"] = ({"story_id": latest_scored.story_id, "label": sentiments[latest_scored.story_id]["label"],
                              "published_at": _iso(latest_scored.published)} if latest_scored else None)
        providers.append({"id": "finbert", "label": PROVIDER_LABELS["finbert"], "kind": "SENTIMENT", "scope": "INSTRUMENT",
                          "state": model_status["state"], "reason": model_status.get("reason"), "fetched_at": None,
                          "item_count": summary["scored"], "terms": _provider_terms()["finbert"],
                          "model_id": model_status.get("model_id")})
        ai = self._ai_status()
        providers.append({"id": "ai", "label": PROVIDER_LABELS["ai"], "kind": "AI", "scope": "INSTRUMENT",
                          "state": "CURRENT" if ai["state"] == "AVAILABLE" else ai["state"], "reason": ai["reason"],
                          "fetched_at": None, "item_count": None, "runtime": ai.get("runtime"),
                          "model_id": ai.get("model_id")})
        news_states = {status["state"] for status in providers if status["kind"] in ("NEWS", "OFFICIAL_FILING")
                       and status["state"] != "NOT_APPLICABLE"}
        state, reason = self._overall(news_states, None)
        capability_state = profile.capability
        if state in ("NOT_CONFIGURED", "UNAVAILABLE"):
            capability_state, capability_reason = state, reason
        else:
            capability_reason = profile.capability_reason
            if state == "PARTIAL" and capability_state == "SUPPORTED":
                capability_state, capability_reason = "PARTIAL", "SOME_PROVIDERS_NOT_CURRENT"
        catalysts: dict[str, list[Story]] = {}
        for story in stories:
            for item in story.categories:
                catalysts.setdefault(item.id, []).append(story)
        category_meta = {item.id: item for story in stories for item in story.categories}
        attention = self._attention(stories, now, state)
        reaction = (self._reaction(universe, instrument_id, stories, now) if not compact else
                    {"state": "NOT_SUPPORTED", "reason": "COMPACT_VIEW", "basis": "", "timeframe": None,
                     "note": REACTION_NOTE, "items": []})
        return {
            "schema_version": INSTRUMENT_SCHEMA_VERSION, "generated_at": _iso(now), "universe": universe,
            "instrument": {"instrument_id": instrument_id, "symbol": profile.symbol, "label": profile.label},
            "capability": {"state": capability_state, "reason": capability_reason, "match_bases": profile.match_bases,
                           "terms": profile.terms[:24], "notes": list(profile.notes)},
            "window": self._window(INSTRUMENT_WINDOW, now), "state": state, "reason": reason, "providers": providers,
            "coverage": {"story_count": len(stories), "headline_count": sum(len(story.members) for story in stories),
                         "source_count": len({record.event.publisher_source.lower() for story in stories for record in story.members}),
                         "latest_published_at": _iso(max((story.published for story in stories if story.published), default=None))},
            "stories": [story.to_dict(sentiments[story.story_id]) for story in shown],
            "sentiment": summary,
            "catalysts": [{"category": category_meta[key].to_dict(), "story_count": len(items),
                           "latest_published_at": _iso(max((story.moment for story in items if story.moment), default=None)),
                           "story_ids": [story.story_id for story in items[:8]]}
                          for key, items in sorted(catalysts.items(), key=lambda item: (-len(item[1]), item[0]))],
            "attention": attention, "reaction": reaction,
            "analysis": self._analysis(profile, stories, summary, attention, reaction, providers),
            "ai": ai,
        }

    def _attention(self, stories: list[Story], now: datetime, state: str) -> dict[str, Any]:
        if state in ("NOT_CONFIGURED", "UNAVAILABLE", "PENDING"):
            return {"state": "UNAVAILABLE", "reason": "NO_CURRENT_COVERAGE", "class": "DERIVED", "windows": [],
                    "independent_sources": 0, "latest_published_at": None, "method": ATTENTION_METHOD}
        members = [(record.moment, story.story_id) for story in stories for record in story.members if record.moment]
        windows = []
        coverage = timedelta(seconds=WINDOWS[INSTRUMENT_WINDOW])
        for window_id, seconds in ATTENTION_WINDOWS:
            span = timedelta(seconds=seconds)
            current = [(moment, sid) for moment, sid in members if now - span <= moment <= now + timedelta(minutes=5)]
            prior = ([(moment, sid) for moment, sid in members if now - 2 * span <= moment < now - span]
                     if 2 * span <= coverage else None)
            windows.append({"id": window_id, "headline_count": len(current), "story_count": len({sid for _m, sid in current}),
                            "prior_headline_count": len(prior) if prior is not None else None})
        day = [record for story in stories for record in story.members if record.moment and record.moment >= now - timedelta(hours=24)]
        return {"state": "CURRENT" if state == "CURRENT" else "PARTIAL",
                "reason": None if state == "CURRENT" else "PARTIAL_PROVIDER_COVERAGE", "class": "DERIVED",
                "windows": windows, "independent_sources": len({record.event.publisher_source.lower() for record in day}),
                "latest_published_at": _iso(max((story.published for story in stories if story.published), default=None)),
                "method": ATTENTION_METHOD}

    def _reaction(self, universe: str, instrument_id: str, stories: list[Story], now: datetime) -> dict[str, Any]:
        base = {"basis": "Completed 5m bars; reference = close of the last bar ending at or before publication",
                "timeframe": "5m", "note": REACTION_NOTE, "items": []}
        if universe not in CHART_UNIVERSES:
            return {**base, "state": "NOT_SUPPORTED", "reason": "NO_RELIABLE_PRICE_HISTORY_FOR_UNIVERSE", "timeframe": None}
        candidates = [story for story in stories if story.published][:5]
        if not candidates:
            return {**base, "state": "UNAVAILABLE", "reason": "NO_STORY_WITH_KNOWN_PUBLICATION_TIME"}
        try:
            chart = self._chart(instrument_id, universe)
        except Exception:  # noqa: BLE001 — bars are optional evidence
            chart = None
        bars = [bar for bar in ((chart or {}).get("bars") or {}).get("bars") or []
                if isinstance(bar, dict) and bar.get("end") and bar.get("close") is not None]
        if not bars:
            reason = ((chart or {}).get("bars") or {}).get("reason") or "BARS_UNAVAILABLE"
            return {**base, "state": "UNAVAILABLE", "reason": reason}
        series = sorted(((parse_utc_iso(str(bar["end"])), float(bar["close"]), str(bar.get("start") or "")) for bar in bars),
                        key=lambda item: item[0] or now)
        series = [item for item in series if item[0] is not None]
        items = []
        for story in candidates:
            published = story.published
            before = [item for item in series if item[0] <= published]
            if not before or published - before[-1][0] > timedelta(minutes=10):
                continue  # headline outside bar coverage (e.g. overnight gap): no reference, no claim
            reference = before[-1]
            horizons = []
            for horizon_id, minutes in REACTION_HORIZONS:
                target = published + timedelta(minutes=minutes)
                after = [item for item in series if item[0] >= target]
                if target > series[-1][0]:
                    horizons.append({"id": horizon_id, "change_pct": None, "price": None, "bar_end": None, "state": "PENDING"})
                elif not after or after[0][0] - target > timedelta(minutes=10):
                    horizons.append({"id": horizon_id, "change_pct": None, "price": None, "bar_end": None, "state": "UNAVAILABLE"})
                else:
                    price = after[0][1]
                    horizons.append({"id": horizon_id, "change_pct": round((price / reference[1] - 1) * 100, 3) if reference[1] else None,
                                     "price": price, "bar_end": _iso(after[0][0]), "state": "OBSERVED"})
            items.append({"story_id": story.story_id, "published_at": _iso(published),
                          "reference": {"price": reference[1], "bar_start": reference[2] or None, "bar_end": _iso(reference[0])},
                          "horizons": horizons})
        if not items:
            return {**base, "state": "UNAVAILABLE", "reason": "HEADLINES_OUTSIDE_BAR_COVERAGE"}
        return {**base, "state": "CURRENT", "reason": None, "items": items}

    @staticmethod
    def _analysis(profile: InstrumentProfile, stories: list[Story], sentiment: dict[str, Any], attention: dict[str, Any],
                  reaction: dict[str, Any], providers: list[dict[str, Any]]) -> dict[str, Any]:
        observed, derived, insufficient = [], [], []
        for story in stories[:3]:
            rep = story.representative
            when = _iso(story.published)
            observed.append({"text": f"{rep.event.publisher_source or rep.provider_id}: {rep.event.headline}"
                                     + (f" ({story.source_count} sources)" if story.source_count > 1 else ""),
                             "source": rep.provider_id, "as_of": when or rep.event.retrieved_time, "story_id": story.story_id})
        filings = [story for story in stories if story.source_type == "OFFICIAL_FILING"]
        if filings:
            observed.append({"text": f"{len(filings)} SEC filing(s) in the window; latest: {filings[0].representative.event.headline}",
                             "source": "sec_filings", "as_of": _iso(filings[0].published), "story_id": filings[0].story_id})
        if stories:
            cats = Counter(item.label for story in stories for item in story.categories)
            if cats:
                derived.append({"text": "Categories: " + ", ".join(f"{label} ({count})" for label, count in cats.most_common(4)),
                                "source": "IMP event taxonomy", "as_of": None, "story_id": None})
        if sentiment.get("scored"):
            counts = sentiment["counts"]
            derived.append({"text": f"Headline language (FinBERT, {sentiment['scored']} scored): {counts['positive']} positive, "
                                    f"{counts['neutral']} neutral, {counts['negative']} negative — language, not a forecast.",
                            "source": sentiment.get("model_id") or "FinBERT", "as_of": None, "story_id": None})
        hour = next((item for item in attention.get("windows", []) if item["id"] == "1h"), None)
        if hour and hour["prior_headline_count"] is not None and attention["state"] in ("CURRENT", "PARTIAL"):
            derived.append({"text": f"Headlines in the last hour: {hour['headline_count']} (prior hour {hour['prior_headline_count']})"
                                    + ("; coverage is partial" if attention["state"] == "PARTIAL" else ""),
                            "source": "IMP attention", "as_of": None, "story_id": None})
        for item in reaction.get("items", [])[:2]:
            observed_h = [h for h in item["horizons"] if h["state"] == "OBSERVED" and h["change_pct"] is not None]
            if observed_h:
                last = observed_h[-1]
                derived.append({"text": f"Post-headline price reaction: {last['change_pct']:+.2f}% by {last['id']} after the "
                                        f"story published at {item['published_at']} (temporal association, not causation).",
                                "source": "IMP post-headline reaction", "as_of": last["bar_end"], "story_id": item["story_id"]})
        insufficient.append({"text": "No causal link between any headline and price movement is established by this evidence.",
                             "source": "IMP", "as_of": None, "story_id": None})
        missing = [status["label"] for status in providers if status["kind"] in ("NEWS", "OFFICIAL_FILING")
                   and status["state"] not in ("CURRENT", "NOT_APPLICABLE", "STALE", "DELAYED")]
        delayed = [status["label"] for status in providers if status["state"] == "DELAYED"]
        if delayed:
            insufficient.append({"text": "Delayed development-plan source (not current news): " + ", ".join(delayed) + ".",
                                 "source": "IMP", "as_of": None, "story_id": None})
        if missing:
            insufficient.append({"text": "Coverage excludes: " + ", ".join(missing) + ". Absent stories may reflect missing providers.",
                                 "source": "IMP", "as_of": None, "story_id": None})
        if not stories:
            insufficient.append({"text": "No current stories matched this instrument in the window.",
                                 "source": "IMP", "as_of": None, "story_id": None})
        for note in profile.notes:
            insufficient.append({"text": note, "source": "IMP matching", "as_of": None, "story_id": None})
        return {"observed": observed, "derived": derived, "insufficient": insufficient}

    # ------------------------------------------------------------- AI
    def _get_synthesizer(self) -> Any:
        with self._lock:
            if self._synthesizer is None:
                self._synthesizer = self._synthesizer_factory()
            return self._synthesizer

    def _ai_status(self) -> dict[str, Any]:
        synthesizer = self._get_synthesizer()
        provider = getattr(synthesizer, "_provider", None)
        if provider is None:
            return {"state": "NOT_CONFIGURED", "reason": getattr(synthesizer, "not_configured_reason", "ANTHROPIC_API_KEY_NOT_SET"),
                    "provider_id": None, "model_id": None, "runtime": None}
        runtime = getattr(provider, "runtime", None) or "PAID_API"
        # A managed local model starts on the first request; say so rather than implying it is loaded.
        server = getattr(provider, "_server", None)
        reason = "STARTS_ON_REQUEST" if server is not None and not server.running() else None
        # A paid provider states today's usage against its hard daily limits.
        budget = provider.budget_status() if callable(getattr(provider, "budget_status", None)) else None
        state = "AVAILABLE"
        if budget is not None and (budget["requests"] >= budget["max_requests"] or budget["tokens"] >= budget["max_tokens"]):
            state, reason = "UNAVAILABLE", "SYNTHESIS_DAILY_BUDGET_EXHAUSTED"
        return {"state": state, "reason": reason, "provider_id": getattr(provider, "provider_id", None),
                "model_id": getattr(provider, "model_id", None), "runtime": runtime, "budget": budget}

    def synthesis(self, *, universe: str, scope: str, instrument_id: str | None = None, window: str = "24h") -> dict[str, Any] | None:
        from ..intelligence.inference.screener_synthesis import SynthesisStory

        if scope not in ("INSTRUMENT", "UNIVERSE"):
            raise ValueError("INVALID_SCOPE")
        if scope == "INSTRUMENT":
            payload = self.instrument(universe=universe, instrument_id=instrument_id or "", compact=False)
            if payload is None:
                return None
            instruments: tuple[str, ...] = (payload["instrument"]["symbol"],)
        else:
            payload = self.feed(universe=universe, window=window, sort="sources", limit=MAX_LIMIT)
            instruments = (UNIVERSES[universe].label,)
        stories = payload["stories"]
        story_inputs = [SynthesisStory(story_id=item["story_id"], headline=item["headline"], summary=item["summary"] or "",
                                       published_time=item["published_at"] or "", retrieved_time=item["first_retrieved_at"],
                                       source_type=item["source_type"], source_count=item["source_count"],
                                       publishers=tuple(dict.fromkeys(source["publisher"] for source in item["sources"])),
                                       categories=tuple(category["id"] for category in item["categories"]))
                        for item in sorted(stories, key=lambda story: (story["source_type"] == "NEWS", -story["source_count"],
                                                                        story["published_at"] or ""))]
        result = self._get_synthesizer().synthesize(story_inputs, instruments=instruments,
                                                    as_of=_iso(datetime.fromtimestamp(self._clock(), tz=UTC)) or "")
        missing = sorted(status["id"] for status in payload["providers"]
                         if status["kind"] in ("NEWS", "OFFICIAL_FILING")
                         and status["state"] not in ("CURRENT", "NOT_APPLICABLE", "DELAYED"))
        publishers = {source["publisher"].lower() for story in stories for source in story["sources"]}
        # story_count = matched stories; synthesized_story_count = those the model was given (capped).
        return {**result, "coverage": {"story_count": len(stories), "synthesized_story_count": len(result["story_ids"]),
                                       "source_count": len(publishers), "window": payload["window"],
                                       "missing_providers": missing}}


_SERVICE: ScreenerNewsService | None = None
_SERVICE_LOCK = threading.Lock()


def news_service() -> ScreenerNewsService:
    global _SERVICE
    with _SERVICE_LOCK:
        if _SERVICE is None:
            from ..local_state.external_cache import imp_cache_dir

            _SERVICE = ScreenerNewsService(newsapi_quota_path=imp_cache_dir() / "quota" / "newsapi-developer.json")
        return _SERVICE


def read_news_feed(**kwargs: Any) -> dict[str, Any]:
    return news_service().feed(**kwargs)


def read_instrument_news(**kwargs: Any) -> dict[str, Any] | None:
    return news_service().instrument(**kwargs)


def request_news_synthesis(**kwargs: Any) -> dict[str, Any] | None:
    return news_service().synthesis(**kwargs)


__all__ = ["INSTRUMENT_SCHEMA_VERSION", "SCHEMA_VERSION", "ScreenerNewsService", "news_service", "provider_status",
           "read_instrument_news", "read_news_feed", "request_news_synthesis"]
