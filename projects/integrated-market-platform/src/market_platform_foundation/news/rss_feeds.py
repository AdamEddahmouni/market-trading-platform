"""Bounded public RSS/Atom headline adapter (S11).

Re-implemented natively from two donors: the Short Squeeze collector
(``collectors/rss_news.py``: one Google News query, unparsed ``pubDate``, no
Atom) and the Claude Code News source list (``news/live/sources.mjs``: official
Fed feeds plus wire/markets feeds, regex parser that stamped a missing
``pubDate`` as "now"). Here:

* an explicit, reviewed feed catalog — no arbitrary subscriptions;
* RSS ``<item>`` and Atom ``<entry>`` parsing with the standard library;
* RFC 822 / ISO publication times parsed to UTC; a missing or malformed time
  stays unknown and is flagged, never replaced by the retrieval time;
* bounded response size and timeout, per-feed cache, per-feed status;
* headline plus a short publisher-provided excerpt only — never article bodies.

Live access is opt-in (``IMP_NEWS_RSS_LIVE=1``). ``sec.gov`` feeds additionally
require a declared ``SEC_USER_AGENT`` (SEC Fair Access).
"""

from __future__ import annotations

import html
import re
import threading
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, Callable

RSS_VERSION = "news/rss/1.0.0"
LIVE_ENV = "IMP_NEWS_RSS_LIVE"
MAX_BYTES = 2_000_000
TIMEOUT_S = 10.0
CACHE_TTL_S = 300.0
FAILURE_TTL_S = 120.0
MAX_ITEMS_PER_FEED = 60
EXCERPT_CHARS = 280
USER_AGENT = "integrated-market-platform-news/1.0 (+headline metadata only)"


@dataclass(frozen=True, slots=True)
class Feed:
    id: str
    publisher: str
    url: str
    source_type: str                 # NEWS | OFFICIAL_RELEASE
    universes: tuple[str, ...]       # universe feeds this source contributes to
    requires_sec_user_agent: bool = False


FEEDS: tuple[Feed, ...] = (
    Feed("fed_press_all", "Federal Reserve", "https://www.federalreserve.gov/feeds/press_all.xml", "OFFICIAL_RELEASE",
         ("FUTURES", "BONDS", "US_ETFS")),
    Feed("fed_press_monetary", "Federal Reserve", "https://www.federalreserve.gov/feeds/press_monetary.xml",
         "OFFICIAL_RELEASE", ("FUTURES", "BONDS", "US_ETFS")),
    Feed("fed_speeches", "Federal Reserve", "https://www.federalreserve.gov/feeds/speeches.xml", "OFFICIAL_RELEASE",
         ("FUTURES", "BONDS")),
    Feed("sec_press", "U.S. SEC", "https://www.sec.gov/news/pressreleases.rss", "OFFICIAL_RELEASE",
         ("CRYPTO", "US_EQUITIES"), requires_sec_user_agent=True),
    Feed("cnbc_economy", "CNBC", "https://www.cnbc.com/id/20910258/device/rss/rss.html", "NEWS",
         ("FUTURES", "BONDS", "US_ETFS", "US_EQUITIES")),
    Feed("cnbc_top", "CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html", "NEWS",
         ("FUTURES", "BONDS", "US_ETFS", "US_EQUITIES")),
    Feed("marketwatch_top", "MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_topstories", "NEWS",
         ("FUTURES", "BONDS", "US_ETFS", "US_EQUITIES")),
    Feed("oilprice", "OilPrice.com", "https://oilprice.com/rss/main", "NEWS", ("FUTURES",)),
    Feed("coindesk", "CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/", "NEWS", ("CRYPTO",)),
    Feed("cointelegraph", "Cointelegraph", "https://cointelegraph.com/rss", "NEWS", ("CRYPTO",)),
)
FEEDS_BY_ID = {feed.id: feed for feed in FEEDS}

_ATOM = "{http://www.w3.org/2005/Atom}"
_TAG = re.compile(r"<[^>]+>")

Fetcher = Callable[[str, dict[str, str], float], bytes]


def _utc_iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_feed_time(raw: str | None) -> tuple[str, tuple[str, ...]]:
    """(UTC ISO or "", quality flags). Never substitutes another clock."""

    text = (raw or "").strip()
    if not text:
        return "", ("PUBLICATION_TIME_MISSING",)
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        parsed = None
    if parsed is None:
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return "", ("PUBLICATION_TIME_MALFORMED",)
    if parsed.tzinfo is None:
        return "", ("PUBLICATION_TIME_NO_TIMEZONE",)
    return _utc_iso(parsed), ()


def _text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return "".join(element.itertext()).strip()


def _excerpt(raw: str) -> str:
    text = " ".join(html.unescape(_TAG.sub(" ", raw or "")).split())
    return text if len(text) <= EXCERPT_CHARS else text[:EXCERPT_CHARS - 1].rstrip() + "…"


def parse_feed(body: bytes, feed: Feed, *, retrieved_time: str) -> list[dict[str, Any]]:
    """Raw provider items in the shape the canonical normalizer reads. Raises ValueError on malformed XML."""

    if len(body) > MAX_BYTES:
        raise ValueError("RSS_RESPONSE_TOO_LARGE")
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise ValueError("RSS_MALFORMED") from exc
    entries: list[tuple[str, str, str, str, str]] = []
    for item in root.iter("item"):
        entries.append((_text(item.find("title")), _text(item.find("link")), _text(item.find("pubDate")) or
                        _text(item.find("{http://purl.org/dc/elements/1.1/}date")), _text(item.find("description")),
                        _text(item.find("guid"))))
    for entry in root.iter(f"{_ATOM}entry"):
        link = entry.find(f"{_ATOM}link[@rel='alternate']")
        if link is None:  # Element truthiness is child count: compare with None explicitly.
            link = entry.find(f"{_ATOM}link")
        entries.append((_text(entry.find(f"{_ATOM}title")), (link.get("href") if link is not None else "") or "",
                        _text(entry.find(f"{_ATOM}published")) or _text(entry.find(f"{_ATOM}updated")),
                        _text(entry.find(f"{_ATOM}summary")), _text(entry.find(f"{_ATOM}id"))))
    items: list[dict[str, Any]] = []
    for title, link, raw_time, description, guid in entries[:MAX_ITEMS_PER_FEED]:
        headline = " ".join(html.unescape(title).split())
        if len(headline) < 5:
            continue
        published, flags = parse_feed_time(raw_time)
        items.append({
            "headline": headline, "url": link.strip(), "published_time": published,
            "summary": _excerpt(description), "publisher_source": feed.publisher,
            "provider_native_id": f"{feed.id}:{guid or link or headline}"[:300],
            "provider": "RSS", "feed_id": feed.id, "source_type": feed.source_type,
            "received_time": retrieved_time, "quality_flags": list(flags), "tickers": [],
        })
    return items


def _default_fetch(url: str, headers: dict[str, str], timeout: float) -> bytes:
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 — catalog URLs only
        status = int(getattr(response, "status", 200))
        if status != 200:
            raise urllib.error.HTTPError(url, status, "status", response.headers, None)
        body = response.read(MAX_BYTES + 1)
    return body


@dataclass(slots=True)
class _FeedCache:
    items: list[dict[str, Any]]
    fetched_at: str | None
    expires: float
    state: str
    reason: str | None


class RssNewsSource:
    """Catalog feeds with per-feed cache and status. Thread-safe; bounded."""

    provider_id = "rss"

    def __init__(self, *, fetch: Fetcher | None = None, env: Callable[[str], str | None] | None = None,
                 clock: Callable[[], float] = time.time, feeds: tuple[Feed, ...] = FEEDS) -> None:
        import os

        self._fetch = fetch or _default_fetch
        self._env = env or os.environ.get
        self._clock = clock
        self._feeds = feeds
        self._lock = threading.Lock()
        self._cache: dict[str, _FeedCache] = {}
        self.request_count = 0

    def enabled(self) -> bool:
        return (self._env(LIVE_ENV) or "").strip().lower() in {"1", "true", "yes"}

    def feeds_for(self, universe: str) -> tuple[Feed, ...]:
        return tuple(feed for feed in self._feeds if universe in feed.universes)

    def _headers(self, feed: Feed) -> dict[str, str] | None:
        if feed.requires_sec_user_agent:
            agent = (self._env("SEC_USER_AGENT") or "").strip()
            if not agent or "@" not in agent:
                return None
            return {"User-Agent": agent, "Accept": "application/rss+xml, application/xml;q=0.9"}
        return {"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9"}

    def fetch(self, feed: Feed) -> _FeedCache:
        now = self._clock()
        with self._lock:
            cached = self._cache.get(feed.id)
            if cached is not None and cached.expires > now:
                return cached
        if not self.enabled():
            return _FeedCache([], None, now + 30, "LIVE_DISABLED", f"{LIVE_ENV}_NOT_SET")
        headers = self._headers(feed)
        if headers is None:
            return _FeedCache([], None, now + 30, "NOT_CONFIGURED", "SEC_USER_AGENT_NOT_SET")
        retrieved = _utc_iso(datetime.fromtimestamp(now, tz=UTC))
        try:
            self.request_count += 1
            body = self._fetch(feed.url, headers, TIMEOUT_S)
            items = parse_feed(body, feed, retrieved_time=retrieved)
            result = _FeedCache(items, retrieved, now + CACHE_TTL_S, "CURRENT", None if items else "FEED_EMPTY")
        except urllib.error.HTTPError as exc:
            state = "RATE_LIMITED" if exc.code == 429 else "AUTH_FAILED" if exc.code in (401, 403) else "ERROR"
            result = _FeedCache([], retrieved, now + FAILURE_TTL_S, state, f"HTTP_{exc.code}")
        except ValueError as exc:
            result = _FeedCache([], retrieved, now + FAILURE_TTL_S, "ERROR", str(exc) if str(exc).startswith("RSS_") else "RSS_MALFORMED")
        except Exception:  # noqa: BLE001 — network failure is a status, never raised into a request
            result = _FeedCache([], retrieved, now + FAILURE_TTL_S, "ERROR", "NETWORK_ERROR")
        with self._lock:
            previous = self._cache.get(feed.id)
            # A failed refresh keeps the last good items visible, marked stale.
            if result.state != "CURRENT" and previous is not None and previous.state in ("CURRENT", "STALE") and previous.items:
                result = _FeedCache(previous.items, previous.fetched_at, result.expires, "STALE", result.reason)
            self._cache[feed.id] = result
        return result

    def collect(self, universe: str) -> dict[str, Any]:
        """All catalog feeds contributing to a universe: items plus per-feed status."""

        items: list[dict[str, Any]] = []
        statuses: list[dict[str, Any]] = []
        for feed in self.feeds_for(universe):
            result = self.fetch(feed)
            items.extend(result.items)
            statuses.append({"feed_id": feed.id, "publisher": feed.publisher, "state": result.state,
                             "reason": result.reason, "fetched_at": result.fetched_at, "item_count": len(result.items)})
        return {"items": items, "feeds": statuses}


def aggregate_state(statuses: list[dict[str, Any]]) -> tuple[str, str | None]:
    """One provider row for the RSS family, without hiding per-feed failures."""

    if not statuses:
        return "NOT_APPLICABLE", "NO_FEEDS_FOR_UNIVERSE"
    states = {status["state"] for status in statuses}
    if states == {"LIVE_DISABLED"}:
        return "LIVE_DISABLED", f"{LIVE_ENV}_NOT_SET"
    if "CURRENT" in states and states <= {"CURRENT"}:
        return "CURRENT", None
    if states & {"CURRENT", "STALE"}:
        failed = sorted(status["feed_id"] for status in statuses if status["state"] not in ("CURRENT",))
        return ("STALE" if "CURRENT" not in states else "CURRENT"), "PARTIAL_FEEDS:" + ",".join(failed)
    if states == {"NOT_CONFIGURED"}:
        return "NOT_CONFIGURED", "SEC_USER_AGENT_NOT_SET"
    reasons = sorted({status["reason"] or status["state"] for status in statuses})
    return ("RATE_LIMITED" if "RATE_LIMITED" in states else "ERROR"), ",".join(reasons)


__all__ = ["CACHE_TTL_S", "FEEDS", "FEEDS_BY_ID", "Feed", "LIVE_ENV", "RSS_VERSION", "RssNewsSource", "aggregate_state",
           "parse_feed", "parse_feed_time"]
