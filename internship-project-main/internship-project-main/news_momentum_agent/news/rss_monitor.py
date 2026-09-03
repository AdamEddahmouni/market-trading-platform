"""RSS / Atom monitor for fresh ticker-specific catalyst headlines.

Purpose
-------
Maintains configurable wire-feed sources (PR Newswire, Globe, BusinessWire,
Newsfile, Access Newswire, optional EDGAR) and returns ticker-matched articles
within a freshness window.

Pipeline role
-------------
Primary discovery for Path A per-ticker news. ``find_recent_ticker_articles`` is
called by ``news_aggregator``; broadcast scan helpers feed ``catalyst_scanner``.

Key outputs
-----------
List of ``{source, headline, url, published_utc, source_key?}`` dicts.
Optional ``state/seen_articles.json`` when ``persist_seen=True`` (Path A.2).

Handoff notes
-------------
**Reusable (equity/futures):** Source registry, headline ticker/company matching,
feed cache, seen-URL dedupe — adapt ``DEFAULT_SOURCES`` for futures newswires.

**Options-only coupling:** ``include_edgar`` and ``html_ticker`` kinds are equity
page scrapes; disable or replace for non-equity assets.

**Settings:** ``settings.news.sources`` merges over ``DEFAULT_SOURCES``.
"""

from __future__ import annotations

import json
import re
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import feedparser
from dateutil import parser as date_parser


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = PROJECT_ROOT / "state"
SETTINGS_PATH = PROJECT_ROOT / "settings.json"
SEEN_ARTICLES_PATH = STATE_DIR / "seen_articles.json"

USER_AGENT = "NewsMomentumAgent/1.0 (internship research; contact=local-dev)"

# In-process cache for multi-URL category feeds (Globe / Newsfile industry, etc.).
_FEED_ENTRY_CACHE: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}
_FEED_CACHE_TTL_SEC = 90.0

DEFAULT_GLOBE_SUBJECT_CODES = [
    "9",   # Company Announcement
    "10",  # Company Regulatory Filings
    "13",  # Earnings
    "17",  # Financing Agreements
    "20",  # Health
    "27",  # M&A
    "57",  # Changes In Share Capital (reverse splits)
    "58",  # Changes In Company's Own Shares
    "61",  # Corporate Action
    "70",  # Exchange Announcement
    "72",  # Press Releases
    "90",  # Clinical Study
]

DEFAULT_SOURCES: Dict[str, Dict[str, Any]] = {
    "pr_newswire": {
        "enabled": True,
        "kind": "rss",
        "display_name": "PR Newswire",
        "url": "https://www.prnewswire.com/rss/news-releases-list.rss",
    },
    "globe_newswire": {
        "enabled": True,
        "kind": "rss_multi",
        "display_name": "Globe Newswire",
        "urls": [
            f"https://www.globenewswire.com/RssFeed/subjectcode/{code}"
            for code in DEFAULT_GLOBE_SUBJECT_CODES
        ],
    },
    "business_wire": {
        "enabled": True,
        "kind": "rss",
        "display_name": "BusinessWire",
        "url": "https://feed.businesswire.com/rss/home/?rss=G1",
    },
    "newsfile": {
        "enabled": True,
        "kind": "rss_multi",
        "display_name": "Newsfile",
        "urls": [
            "https://feeds.newsfilecorp.com/global/Last25Stories",
            "https://feeds.newsfilecorp.com/industry/biotechnology",
            "https://feeds.newsfilecorp.com/industry/mining",
            "https://feeds.newsfilecorp.com/industry/financial-services",
        ],
    },
    "access_newswire": {
        "enabled": True,
        "kind": "rss",
        "display_name": "Access Newswire",
        "url": "https://www.accessnewswire.com/feed/rss2",
    },
    "sec_edgar": {
        "enabled": True,
        "kind": "edgar_atom",
        "display_name": "SEC EDGAR",
        "forms": ["8-K"],
    },
    "yahoo": {"enabled": True, "kind": "html_ticker", "display_name": "Yahoo"},
    "benzinga": {"enabled": True, "kind": "html_ticker", "display_name": "Benzinga"},
    "marketwatch": {"enabled": True, "kind": "html_ticker", "display_name": "MarketWatch"},
}


def load_news_settings(settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Load ``settings.news`` block from passed settings or ``settings.json``."""
    if isinstance(settings, dict) and isinstance(settings.get("news"), dict):
        return dict(settings["news"])
    try:
        if SETTINGS_PATH.exists():
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("news"), dict):
                return dict(data["news"])
    except Exception as error:
        print(f"[rss_monitor] Failed reading settings.json: {error}")
    return {}


def resolve_source_configs(settings: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, Any]]:
    """Merge defaults with settings.news.sources overrides."""
    news_cfg = load_news_settings(settings)
    overrides = news_cfg.get("sources") if isinstance(news_cfg.get("sources"), dict) else {}
    merged: Dict[str, Dict[str, Any]] = {}
    for key, default in DEFAULT_SOURCES.items():
        item = dict(default)
        raw = overrides.get(key)
        if isinstance(raw, dict):
            item.update(raw)
        merged[key] = item
    for key, raw in overrides.items():
        if key in merged or not isinstance(raw, dict):
            continue
        merged[key] = dict(raw)
    return merged


def source_enabled(key: str, settings: Optional[Dict[str, Any]] = None) -> bool:
    """Return whether a named news source key is enabled in settings."""
    cfg = resolve_source_configs(settings).get(key) or {}
    return bool(cfg.get("enabled", True))


def get_rss_sources(
    ticker: str = "",
    settings: Optional[Dict[str, Any]] = None,
    *,
    include_edgar: bool = False,
) -> List[Dict[str, str]]:
    """
    Backward-compatible flat list of {name, url} for broadcast RSS feeds.

    EDGAR is per-ticker and omitted unless include_edgar=True (then url is a placeholder).
    """
    sources: List[Dict[str, str]] = []
    for key, cfg in resolve_source_configs(settings).items():
        if not bool(cfg.get("enabled", True)):
            continue
        kind = str(cfg.get("kind") or "")
        name = str(cfg.get("display_name") or key)
        if kind == "rss":
            url = str(cfg.get("url") or "").strip()
            if url:
                sources.append({"name": name, "url": url, "key": key})
        elif kind == "rss_multi":
            for url in cfg.get("urls") or []:
                u = str(url).strip()
                if u:
                    sources.append({"name": name, "url": u, "key": key})
        elif kind == "edgar_atom" and include_edgar:
            sources.append({"name": name, "url": f"edgar://{ticker}", "key": key})
    return sources


def load_seen_articles() -> Set[str]:
    """Load persisted seen article URLs from ``state/seen_articles.json``."""
    try:
        if not SEEN_ARTICLES_PATH.exists():
            return set()
        data = json.loads(SEEN_ARTICLES_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return set(str(item) for item in data)
        return set()
    except Exception as error:
        print(f"[rss_monitor] Could not load seen articles: {error}")
        return set()


def save_seen_articles(seen_articles: Set[str]) -> None:
    """Persist seen URLs (capped ~5000) for cross-cycle dedupe."""
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        temp_path = SEEN_ARTICLES_PATH.with_suffix(SEEN_ARTICLES_PATH.suffix + ".tmp")
        # Cap growth — keep most recent ~5000 URLs.
        ordered = sorted(seen_articles)
        if len(ordered) > 5000:
            ordered = ordered[-5000:]
        temp_path.write_text(json.dumps(ordered, indent=2), encoding="utf-8")
        temp_path.replace(SEEN_ARTICLES_PATH)
    except Exception as error:
        print(f"[rss_monitor] Could not save seen articles: {error}")


def parse_entry_datetime(entry: Dict[str, Any]) -> datetime | None:
    """Parse RSS/Atom entry published/updated timestamp to UTC."""
    for key in ("published", "updated", "created"):
        raw_value = entry.get(key)
        if not raw_value:
            continue
        try:
            parsed = date_parser.parse(str(raw_value))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            continue
    return None


def is_recent(publication_time: datetime | None, max_age_hours: int = 4) -> bool:
    """True when ``publication_time`` is within ``max_age_hours`` of now (UTC)."""
    if publication_time is None:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    return publication_time >= cutoff


def _company_match_needles(company_name: str) -> List[str]:
    """Build match strings from a company name (strip Inc/Ltd/etc.)."""
    raw = str(company_name or "").lower().strip()
    if not raw:
        return []
    cleaned = raw
    for suffix in (
        "incorporated",
        "corporation",
        "company",
        "limited",
        "inc.",
        "ltd.",
        "corp.",
        "inc",
        "ltd",
        "corp",
        "co.",
        "co",
        "plc",
        "llc",
        "sa",
        "ag",
        "nv",
    ):
        cleaned = re.sub(rf"\b{re.escape(suffix)}\b\.?", " ", cleaned)
    cleaned = re.sub(r"[^\w\s&-]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -")
    needles: List[str] = []
    if len(cleaned) >= 4:
        needles.append(cleaned)
    parts = [p for p in cleaned.split() if p]
    if len(parts) >= 2:
        two = " ".join(parts[:2])
        if len(two) >= 4 and two not in needles:
            needles.append(two)
    return needles


def headline_matches_ticker(headline: str, ticker: str, company_name: str = "") -> bool:
    """Word-boundary ticker match and/or company-name substring match."""
    text = str(headline or "")
    lower = text.lower()
    sym = str(ticker or "").upper().strip()
    if sym:
        if re.search(rf"(?<![A-Z0-9]){re.escape(sym)}(?![A-Z0-9])", text.upper()):
            return True
        if re.search(rf"\${re.escape(sym)}\b", text.upper()):
            return True
    for needle in _company_match_needles(company_name):
        if needle in lower:
            return True
    return False


def _fetch_feed_bytes(url: str, timeout: float = 15.0) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _parse_feed_entries(url: str, source_name: str, source_key: str) -> List[Dict[str, Any]]:
    now = time.time()
    cached = _FEED_ENTRY_CACHE.get(url)
    if cached and (now - cached[0]) < _FEED_CACHE_TTL_SEC:
        return list(cached[1])

    try:
        raw = _fetch_feed_bytes(url)
        parsed = feedparser.parse(raw)
    except Exception as error:
        print(f"[rss_monitor] Failed source {source_name} ({url}): {error}")
        _FEED_ENTRY_CACHE[url] = (now, [])
        return []

    entries: List[Dict[str, Any]] = []
    for entry in parsed.entries:
        title = str(entry.get("title", "")).strip()
        link = str(entry.get("link", "")).strip()
        if not title:
            continue
        published_at = parse_entry_datetime(entry)
        entries.append(
            {
                "source": source_name,
                "source_key": source_key,
                "headline": title,
                "url": link,
                "published_utc": published_at.isoformat() if published_at else None,
                "_published_dt": published_at,
            }
        )
    _FEED_ENTRY_CACHE[url] = (now, entries)
    return list(entries)


def find_recent_ticker_articles(
    ticker: str,
    company_name: str,
    max_article_age_hours: int = 4,
    settings: Optional[Dict[str, Any]] = None,
    *,
    persist_seen: bool = False,
    include_edgar: bool = True,
) -> List[Dict[str, Any]]:
    """
    Scan configured RSS/Atom sources (+ optional EDGAR) for ticker matches.

    persist_seen=False (Path A lookup): return matches even if URL was seen before;
    still dedupe within this call. persist_seen=True (Path A.2): skip + record URLs.
    """
    news_cfg = load_news_settings(settings)
    # Caller-supplied max_article_age_hours wins; settings used by aggregator when invoking.
    age_hours = max(1, int(max_article_age_hours or news_cfg.get("max_article_age_hours") or 4))
    configs = resolve_source_configs(settings)
    seen_articles = load_seen_articles() if persist_seen else set()
    new_articles: List[Dict[str, Any]] = []
    seen_urls_this_call: Set[str] = set()
    ticker_text = ticker.upper().strip()

    for key, cfg in configs.items():
        if not bool(cfg.get("enabled", True)):
            continue
        kind = str(cfg.get("kind") or "")
        name = str(cfg.get("display_name") or key)

        if kind == "edgar_atom":
            if not include_edgar:
                continue
            try:
                from news.edgar_client import fetch_recent_filings
            except ImportError:
                from edgar_client import fetch_recent_filings
            try:
                forms = cfg.get("forms") if isinstance(cfg.get("forms"), list) else ["8-K"]
                for article in fetch_recent_filings(
                    ticker_text,
                    forms=[str(f) for f in forms],
                    max_article_age_hours=age_hours,
                ):
                    link = str(article.get("url") or "")
                    if persist_seen and link and link in seen_articles:
                        continue
                    if link and link in seen_urls_this_call:
                        continue
                    if link:
                        seen_urls_this_call.add(link)
                        if persist_seen:
                            seen_articles.add(link)
                    new_articles.append(article)
            except Exception as error:
                print(f"[rss_monitor] EDGAR failed for {ticker_text}: {error}")
            continue

        if kind not in {"rss", "rss_multi"}:
            continue

        urls: List[str] = []
        if kind == "rss":
            url = str(cfg.get("url") or "").strip()
            if url:
                urls = [url]
        else:
            urls = [str(u).strip() for u in (cfg.get("urls") or []) if str(u).strip()]

        for url in urls:
            for entry in _parse_feed_entries(url, name, key):
                title = str(entry.get("headline") or "")
                link = str(entry.get("url") or "")
                published_at = entry.get("_published_dt")
                if not headline_matches_ticker(title, ticker_text, company_name):
                    continue
                if not is_recent(published_at, max_age_hours=age_hours):
                    continue
                if persist_seen and link and link in seen_articles:
                    continue
                if link and link in seen_urls_this_call:
                    continue
                if link:
                    seen_urls_this_call.add(link)
                    if persist_seen:
                        seen_articles.add(link)
                new_articles.append(
                    {
                        "source": name,
                        "source_key": key,
                        "headline": title,
                        "url": link,
                        "published_utc": entry.get("published_utc"),
                    }
                )

    if persist_seen:
        save_seen_articles(seen_articles)
    return new_articles


def main() -> None:
    """CLI smoke test: scan AAPL headlines across configured feeds."""
    articles = find_recent_ticker_articles(ticker="AAPL", company_name="Apple", max_article_age_hours=4)
    print(f"Found {len(articles)} recent new article(s) for AAPL.")
    for article in articles:
        print("-" * 100)
        print(f"Source: {article['source']}")
        print(f"Headline: {article['headline']}")
        print(f"URL: {article['url']}")
        print(f"Published (UTC): {article['published_utc']}")


if __name__ == "__main__":
    main()
