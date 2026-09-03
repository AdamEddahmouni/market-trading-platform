from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from typing import Any

import requests

from .base import EvidenceCollector
from .models import CollectorRecord
from .rss_news import _parse_rss

_SOURCE = "SecRss"


def _now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


class SecRssCollector(EvidenceCollector):
    """SEC EDGAR company RSS (public Atom/RSS) for catalyst bucket context."""

    name = _SOURCE

    def __init__(
        self,
        *,
        enabled: bool = True,
        user_agent: str = "ResearchScreener/1.0 integration@example.invalid",
        cache_ttl_s: int = 1800,
    ) -> None:
        self._enabled = enabled
        self._user_agent = user_agent
        self._cache_ttl_s = cache_ttl_s
        self._cik_by_symbol: dict[str, str] = {}
        self._feed_cache: dict[str, tuple[float, list[dict[str, str]]]] = {}
        self._last_error: str | None = None

    @property
    def configured(self) -> bool:
        return self._enabled and "/" in self._user_agent

    @property
    def capabilities(self) -> list[str]:
        return ["sec_rss_filings"]

    def _lookup_cik(self, symbol: str) -> str | None:
        symbol = symbol.strip().upper()
        if symbol in self._cik_by_symbol:
            return self._cik_by_symbol[symbol]
        url = f"https://www.sec.gov/files/company_tickers.json"
        headers = {"User-Agent": self._user_agent, "Accept": "application/json"}
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        for entry in data.values():
            if str(entry.get("ticker", "")).upper() == symbol:
                cik = str(entry.get("cik_str", "")).zfill(10)
                self._cik_by_symbol[symbol] = cik
                return cik
        return None

    def _fetch_filings(self, symbol: str, *, force: bool) -> list[dict[str, str]]:
        symbol = symbol.strip().upper()
        now = time.time()
        cached = self._feed_cache.get(symbol)
        if not force and cached and (now - cached[0]) < self._cache_ttl_s:
            return cached[1]
        cik = self._lookup_cik(symbol)
        if not cik:
            return []
        feed_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=&dateb=&owner=include&count=10&output=atom"
        headers = {"User-Agent": self._user_agent, "Accept": "application/atom+xml"}
        response = requests.get(feed_url, headers=headers, timeout=30)
        response.raise_for_status()
        try:
            items = _parse_rss(response.text)
        except ET.ParseError:
            items = []
        self._feed_cache[symbol] = (now, items)
        return items

    def poll(
        self, symbols: list[str], *, force: bool = False
    ) -> list[CollectorRecord]:
        if not self.configured:
            return []
        received = _now()
        records: list[CollectorRecord] = []
        for symbol in symbols:
            try:
                items = self._fetch_filings(symbol, force=force)
            except Exception as exc:  # noqa: BLE001
                self._last_error = f"{type(exc).__name__}: {exc}"
                continue
            if not items:
                continue
            records.append(
                CollectorRecord(
                    symbol=symbol.upper(),
                    payload={"filings": items},
                    received_at=received,
                    source_id=_SOURCE,
                    field_hints={
                        "sec_rss_count": len(items),
                        "headlines": [
                            {"headline": i["headline"], "timestamp": i.get("timestamp"), "provider": _SOURCE}
                            for i in items
                        ],
                        "research_admissibility": "RESEARCH_INADMISSIBLE",
                    },
                    dedupe_key=f"{_SOURCE}:{symbol}:{len(items)}",
                )
            )
        return records

    @property
    def rate_limit_state(self) -> dict[str, Any]:
        return {"configured": self.configured, "last_error": self._last_error}


__all__ = ["SecRssCollector"]
