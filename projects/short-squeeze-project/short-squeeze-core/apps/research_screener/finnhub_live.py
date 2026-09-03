"""Finnhub.io free real-time price and company news adapter.

Official API: https://finnhub.io/api/v1/quote
Free tier: 60 requests/min, real-time US equity quotes from IEX feed.
Company News endpoint: https://finnhub.io/api/v1/company-news
Used as a priority price source when IBKR delivers delayed data.
Also provides company news as a fallback news source.
"""
from __future__ import annotations

import threading
import time
from datetime import UTC, datetime
from typing import Any

import requests

FINNHUB_URL = "https://finnhub.io/api/v1/quote"
FINNHUB_NEWS_URL = "https://finnhub.io/api/v1/company-news"
MAX_REQUESTS_PER_MINUTE = 55
CACHE_TTL_S = 15
NEWS_CACHE_TTL_S = 600
MAX_NEWS_PER_SYMBOL = 15


def _now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


class FinnhubClient:
    def __init__(self, api_key: str | None = None) -> None:
        self._cache: dict[str, tuple[float, float | None]] = {}
        self._news_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
        self._request_count = 0
        self._window_start = time.time()
        self._lock = threading.Lock()
        self._api_key = api_key
        self._last_news_error: str | None = None
        self._news_rate_limited_until: float = 0.0

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    @property
    def api_key(self) -> str | None:
        return self._api_key

    @property
    def news_rate_limited(self) -> bool:
        return time.time() < self._news_rate_limited_until

    def status(self) -> dict[str, Any]:
        return {
            "provider": "Finnhub",
            "configured": self.configured,
            "quota_remaining": max(0, MAX_REQUESTS_PER_MINUTE - self._request_count),
            "news_rate_limited": self.news_rate_limited,
            "news_last_error": self._last_news_error,
        }

    def _quota_available(self) -> bool:
        now = time.time()
        if now - self._window_start >= 60:
            self._request_count = 0
            self._window_start = now
        return self._request_count < MAX_REQUESTS_PER_MINUTE

    def fetch_price(self, symbol: str) -> float | None:
        with self._lock:
            now = time.time()
            cached = self._cache.get(symbol)
            if cached and (now - cached[0]) < CACHE_TTL_S:
                return cached[1]

            api_key = self.api_key
            if not api_key:
                return None
            if not self._quota_available():
                return None

            try:
                resp = requests.get(
                    FINNHUB_URL,
                    params={"symbol": symbol, "token": api_key},
                    timeout=5,
                )
                self._request_count += 1
                resp.raise_for_status()
                data = resp.json()
            except Exception:
                return None

            price = data.get("c")
            if not price or price <= 0:
                return None

            self._cache[symbol] = (now, price)
            return price

    def fetch_company_news(
        self, symbol: str, from_date: str = "", to_date: str = ""
    ) -> list[dict[str, Any]]:
        with self._lock:
            now = time.time()
            cached = self._news_cache.get(symbol)
            if cached and (now - cached[0]) < NEWS_CACHE_TTL_S:
                return cached[1]

            if self.news_rate_limited:
                return []

            api_key = self.api_key
            if not api_key:
                return []

            try:
                params: dict[str, str] = {
                    "symbol": symbol.strip().upper(),
                    "token": api_key,
                }
                if from_date:
                    params["from"] = from_date
                if to_date:
                    params["to"] = to_date
                resp = requests.get(
                    FINNHUB_NEWS_URL,
                    params=params,
                    timeout=10,
                )
                if resp.status_code == 429:
                    self._news_rate_limited_until = now + 60
                    self._last_news_error = "Finnhub news 429 rate-limited"
                    return []

                if resp.status_code == 403:
                    self._last_news_error = (
                        "Finnhub account access to company news was denied for this request."
                    )
                    return []

                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                error_msg = str(exc)
                if "429" in error_msg:
                    self._news_rate_limited_until = now + 60
                    self._last_news_error = "Finnhub news 429 rate-limited"
                else:
                    self._last_news_error = f"{type(exc).__name__}: {exc}"
                return []

            if not isinstance(data, list):
                self._last_news_error = f"Unexpected response type: {type(data).__name__}"
                return []

            headlines: list[dict[str, Any]] = []
            for item in data[:MAX_NEWS_PER_SYMBOL]:
                headline_text = item.get("headline", "")
                if not headline_text:
                    continue
                published = datetime.fromtimestamp(
                    item.get("datetime", now), tz=UTC
                ).isoformat().replace("+00:00", "Z")
                headlines.append({
                    "headline": headline_text,
                    "timestamp": published,
                    "url": item.get("url", ""),
                    "tickers": [symbol.strip().upper()],
                    "provider": "Finnhub",
                    "provider_news_id": f"finnhub:{item.get('id', headline_text[:80])}",
                    "summary": item.get("summary", ""),
                    "source": item.get("source", ""),
                    "publisher": item.get("source", ""),
                })
            self._news_cache[symbol] = (now, headlines)
            self._last_news_error = None
            return headlines


_FINNHUB: FinnhubClient | None = None
_FH_LOCK = threading.Lock()


def get_finnhub_client() -> FinnhubClient:
    global _FINNHUB
    with _FH_LOCK:
        if _FINNHUB is None:
            _FINNHUB = FinnhubClient()
        return _FINNHUB
