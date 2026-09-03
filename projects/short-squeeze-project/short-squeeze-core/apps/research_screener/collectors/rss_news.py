from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import requests

from .base import EvidenceCollector
from .models import CollectorRecord

_SOURCE = "RssNews"
_NOW = lambda: datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")

_DEFAULT_FEEDS = (
    "https://news.google.com/rss/search?q={symbol}+stock&hl=en-US&gl=US&ceid=US:en",
)


def _parse_rss(xml_text: str) -> list[dict[str, str]]:
    root = ET.fromstring(xml_text)
    channel = root.find("channel")
    if channel is None:
        channel = root
    items: list[dict[str, str]] = []
    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or item.findtext("published") or "").strip()
        if title:
            items.append({"headline": title, "url": link, "timestamp": pub})
    return items


def _mentions_symbol(headline: str, symbol: str) -> bool:
    pattern = rf"\b{re.escape(symbol)}\b"
    return bool(re.search(pattern, headline, flags=re.IGNORECASE))


class RssNewsCollector(EvidenceCollector):
    name = _SOURCE

    def __init__(
        self,
        *,
        enabled: bool = True,
        feed_templates: tuple[str, ...] = _DEFAULT_FEEDS,
        cache_ttl_s: int = 900,
    ) -> None:
        self._enabled = enabled
        self._feeds = feed_templates
        self._cache_ttl_s = cache_ttl_s
        self._cache: dict[str, tuple[float, list[dict[str, str]]]] = {}
        self._last_error: str | None = None

    @property
    def configured(self) -> bool:
        return self._enabled

    @property
    def capabilities(self) -> list[str]:
        return ["news_headlines"]

    def _fetch_symbol_feeds(self, symbol: str, *, force: bool) -> list[dict[str, str]]:
        symbol = symbol.strip().upper()
        now = time.time()
        cached = self._cache.get(symbol)
        if not force and cached and (now - cached[0]) < self._cache_ttl_s:
            return cached[1]
        headlines: list[dict[str, str]] = []
        for template in self._feeds:
            url = template.format(symbol=quote(symbol))
            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                for item in _parse_rss(response.text):
                    if _mentions_symbol(item["headline"], symbol):
                        headlines.append(item)
            except Exception:
                continue
        self._cache[symbol] = (now, headlines)
        return headlines

    def poll(
        self, symbols: list[str], *, force: bool = False
    ) -> list[CollectorRecord]:
        if not self.configured:
            return []
        received = _NOW()
        records: list[CollectorRecord] = []
        for symbol in symbols:
            try:
                items = self._fetch_symbol_feeds(symbol, force=force)
            except Exception as exc:  # noqa: BLE001
                self._last_error = f"{type(exc).__name__}: {exc}"
                continue
            if not items:
                continue
            records.append(
                CollectorRecord(
                    symbol=symbol.upper(),
                    payload={"headlines": items},
                    received_at=received,
                    source_id=_SOURCE,
                    field_hints={"headlines": items},
                    dedupe_key=f"{_SOURCE}:{symbol}:{len(items)}",
                )
            )
        return records

    @property
    def rate_limit_state(self) -> dict[str, Any]:
        return {"configured": self.configured, "last_error": self._last_error}


__all__ = ["RssNewsCollector", "_parse_rss"]
