"""Multi-provider news aggregation layer.

Orchestrates: Finviz Elite news -> Finnhub company news -> NewsAPI.
Supports: deterministic dedup, per-provider TTL/cache, last-good cache,
RATE_LIMITED status with Retry-After/backoff, provider provenance,
publication timestamps/freshness.
"""
from __future__ import annotations

import hashlib
import threading
import time
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from typing import Any


FINNHUB_NEWS_URL = "https://finnhub.io/api/v1/company-news"
NEWSAPI_URL = "https://newsapi.org/v2/everything"

import requests


def _now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def _now_epoch() -> float:
    return datetime.now(tz=UTC).timestamp()


def _headline_hash(text: str) -> str:
    return hashlib.sha256(
        " ".join(str(text).lower().split()).encode("utf-8")
    ).hexdigest()


def _normalize_timestamp(raw: str | None) -> str:
    if not raw:
        return ""
    try:
        return datetime.fromisoformat(
            str(raw).replace("Z", "+00:00").replace("+0000", "+00:00")
        ).isoformat().replace("+00:00", "Z")
    except (ValueError, TypeError):
        return str(raw)


def _parse_timestamp(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(
            str(raw).replace("Z", "+00:00").replace("+0000", "+00:00")
        )
    except (ValueError, TypeError):
        return None


def _sort_timestamp(raw: str | None) -> datetime:
    return _parse_timestamp(raw) or datetime.min.replace(tzinfo=UTC)


_PROVIDER_ORDER_ALIASES: dict[str, str] = {
    "Finviz News": "Finviz Elite",
    "finviz news": "Finviz Elite",
    "finviz elite": "Finviz Elite",
}


class NewsProvider(ABC):
    @property
    @abstractmethod
    def configured(self) -> bool:
        pass

    @property
    def provider_name(self) -> str:
        return type(self).__name__

    @abstractmethod
    def fetch_news(
        self, symbol: str, *, force: bool = False
    ) -> list[dict[str, Any]]:
        pass

    def status(self) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "configured": self.configured,
        }


class FinvizNewsProvider(NewsProvider):
    def __init__(self, finviz_client: Any) -> None:
        self._client = finviz_client

    @property
    def configured(self) -> bool:
        return getattr(self._client, "configured", False)

    @property
    def provider_name(self) -> str:
        return "Finviz Elite"

    def fetch_news(
        self, symbol: str, *, force: bool = False
    ) -> list[dict[str, Any]]:
        if not self.configured:
            return []
        try:
            raw = self._client.get_news_for(symbol)
            return [_normalize_item(item) for item in raw]
        except Exception:
            return []

    def status(self) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "configured": self.configured,
        }


class NewsApiProvider(NewsProvider):
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key
        self._cache: dict[str, list[dict[str, Any]]] = {}
        self._last_good: dict[str, list[dict[str, Any]]] = {}
        self._cache_times: dict[str, float] = {}
        self._request_count = 0
        self._window_start = time.time()
        self._lock = threading.Lock()
        self._last_error: str | None = None
        self._rate_limited_until: float = 0.0

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    @property
    def api_key(self) -> str | None:
        return self._api_key

    @property
    def is_rate_limited(self) -> bool:
        return time.time() < self._rate_limited_until

    @property
    def provider_name(self) -> str:
        return "NewsAPI"

    def _redact(self, message: object) -> str:
        text = str(message)
        return text.replace(str(self._api_key or ""), "[REDACTED]")

    def status(self) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "configured": self.configured,
            "quota_remaining": max(0, 90 - self._request_count),
            "cached_symbols": len(self._cache),
            "last_error": self._last_error,
            "rate_limited": self.is_rate_limited,
            "rate_limited_until": (
                datetime.fromtimestamp(self._rate_limited_until, tz=UTC).isoformat()
                if self.is_rate_limited else None
            ),
        }

    def _quota_available(self) -> bool:
        now = time.time()
        if now - self._window_start >= 86400:
            self._request_count = 0
            self._window_start = now
        return self._request_count < 90

    def _from_cache(self, symbol: str) -> list[dict[str, Any]]:
        cached = self._cache.get(symbol)
        if cached:
            return cached
        return self._last_good.get(symbol, [])

    def fetch_news(
        self, symbol: str, *, force: bool = False
    ) -> list[dict[str, Any]]:
        with self._lock:
            now = time.time()
            if not force and symbol in self._cache:
                if now - self._cache_times.get(symbol, 0) < 900:
                    return self._cache[symbol]

            if self.is_rate_limited:
                return self._from_cache(symbol)

            if not self.api_key:
                return []

            if not self._quota_available():
                self._rate_limited_until = now + 300
                return self._from_cache(symbol)

            try:
                resp = requests.get(
                    NEWSAPI_URL,
                    params={
                        "q": symbol, "pageSize": 10, "sortBy": "publishedAt",
                        "language": "en", "apiKey": self.api_key,
                    },
                    timeout=10,
                )
                self._request_count += 1
                if resp.status_code == 429:
                    retry = resp.headers.get("Retry-After", "300")
                    try:
                        delay = int(retry)
                    except (ValueError, TypeError):
                        delay = 300
                    self._rate_limited_until = now + delay
                    self._last_error = "NewsAPI 429 rate-limited"
                    return self._from_cache(symbol)
                resp.raise_for_status()
                articles = resp.json().get("articles", [])
            except Exception as exc:
                emsg = str(exc)
                if "429" in emsg:
                    self._rate_limited_until = now + 300
                    self._last_error = "NewsAPI 429 rate-limited"
                else:
                    self._last_error = self._redact(f"{type(exc).__name__}: {exc}")
                return self._from_cache(symbol)

            headlines = []
            for article in articles:
                title = article.get("title")
                if not title:
                    continue
                headlines.append({
                    "headline": title,
                    "timestamp": article.get("publishedAt", ""),
                    "url": article.get("url", ""),
                    "tickers": [symbol.upper()],
                    "provider": self.provider_name,
                    "provider_news_id": f"newsapi:{title[:80]}",
                    "summary": article.get("description", ""),
                    "source": (article.get("source") or {}).get("name", ""),
                    "author": article.get("author", ""),
                })
            self._cache[symbol] = headlines
            self._cache_times[symbol] = now
            self._last_good[symbol] = list(headlines)
            self._last_error = None
            return headlines


class FinnhubNewsProvider(NewsProvider):
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key
        self._cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
        self._lock = threading.Lock()
        self._last_error: str | None = None
        self._rate_limited_until: float = 0.0

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    @property
    def api_key(self) -> str | None:
        return self._api_key

    @property
    def is_rate_limited(self) -> bool:
        return time.time() < self._rate_limited_until

    @property
    def provider_name(self) -> str:
        return "Finnhub News"

    def status(self) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "configured": self.configured,
            "rate_limited": self.is_rate_limited,
            "last_error": self._last_error,
        }

    def fetch_news(
        self, symbol: str, *, force: bool = False
    ) -> list[dict[str, Any]]:
        with self._lock:
            now = time.time()
            cached = self._cache.get(symbol)
            if not force and cached and (now - cached[0]) < 600:
                return cached[1]

            if self.is_rate_limited:
                return []

            if not self.api_key:
                return []

            try:
                today = datetime.now(tz=UTC).date()
                week_ago = today - timedelta(days=7)
                resp = requests.get(
                    FINNHUB_NEWS_URL,
                    params={
                        "symbol": symbol.strip().upper(),
                        "from": week_ago.isoformat(),
                        "to": today.isoformat(),
                        "token": self.api_key,
                    },
                    timeout=10,
                )
                if resp.status_code == 429:
                    self._rate_limited_until = now + 60
                    self._last_error = "Finnhub news 429 rate-limited"
                    return []
                if resp.status_code == 403:
                    self._last_error = (
                        "Finnhub account access to company news was denied for this request."
                    )
                    return []
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                emsg = str(exc)
                if "429" in emsg:
                    self._rate_limited_until = now + 60
                self._last_error = f"{type(exc).__name__}: {exc}"
                return []

            if not isinstance(data, list):
                return []

            headlines = []
            for item in data[:15]:
                htext = item.get("headline", "")
                if not htext:
                    continue
                dt = item.get("datetime", now)
                published = datetime.fromtimestamp(dt, tz=UTC).isoformat().replace(
                    "+00:00", "Z"
                )
                headlines.append({
                    "headline": htext,
                    "timestamp": published,
                    "url": item.get("url", ""),
                    "tickers": [symbol.strip().upper()],
                    "provider": self.provider_name,
                    "provider_news_id": f"finnhub:{item.get('id', htext[:80])}",
                    "summary": item.get("summary", ""),
                    "source": item.get("source", ""),
                    "publisher": item.get("source", ""),
                })
            self._cache[symbol] = (now, headlines)
            self._last_error = None
            return headlines


def _normalize_item(raw: dict[str, Any]) -> dict[str, Any]:
    result = dict(raw)
    if "provider" not in result:
        result["provider"] = "Unknown"
    if "provider_news_id" not in result:
        result["provider_news_id"] = (
            f"{result['provider']}:{_headline_hash(result.get('headline', ''))}"
        )
    return result


class NewsOrchestrator:
    def __init__(
        self,
        *,
        providers: list[NewsProvider] | None = None,
        provider_order: list[str] | None = None,
        cache_ttl_s: int = 300,
        max_headlines: int = 30,
    ) -> None:
        self._providers = providers or []
        self._provider_order = provider_order or []
        self._cache_ttl_s = cache_ttl_s
        self._max_headlines = max_headlines
        self._cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
        self._last_good: dict[str, list[dict[str, Any]]] = {}
        self._lock = threading.Lock()

    @property
    def configured(self) -> bool:
        return any(p.configured for p in self._providers)

    def _ordered_providers(self) -> list[NewsProvider]:
        if not self._provider_order:
            return list(self._providers)
        name_map = {p.provider_name: p for p in self._providers}
        ordered = []
        for name in self._provider_order:
            resolved = _PROVIDER_ORDER_ALIASES.get(name, name)
            if resolved in name_map:
                ordered.append(name_map[resolved])
        return ordered or list(self._providers)

    def status(self) -> dict[str, Any]:
        provider_statuses = {
            p.provider_name: p.status() for p in self._providers
        }
        return {
            "providers": provider_statuses,
            "any_configured": self.configured,
            "provider_order": (
                self._provider_order
                if self._provider_order
                else [p.provider_name for p in self._providers]
            ),
            "cached_symbols": len(self._cache),
            "cache_ttl_s": self._cache_ttl_s,
        }

    def fetch_news(
        self, symbol: str, *, force: bool = False
    ) -> list[dict[str, Any]]:
        symbol = symbol.strip().upper()
        with self._lock:
            now = time.time()
            cached = self._cache.get(symbol)
            if not force and cached and (now - cached[0]) < self._cache_ttl_s:
                return cached[1]

        all_headlines: list[dict[str, Any]] = []
        for provider in self._ordered_providers():
            if not provider.configured:
                continue
            try:
                raw = provider.fetch_news(symbol, force=force)
                for item in raw:
                    if "provider" not in item:
                        item["provider"] = provider.provider_name
                    item["retrieved_at"] = _now()
                all_headlines.extend(raw)
            except Exception:
                continue

        seen: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for item in all_headlines:
            h = _headline_hash(str(item.get("headline", "")))
            if h not in seen:
                seen.add(h)
                item["dedup_key"] = h
                deduped.append(item)

        deduped.sort(
            key=lambda x: _sort_timestamp(x.get("timestamp")),
            reverse=True,
        )
        deduped = deduped[: self._max_headlines]

        if not deduped:
            deduped = list(self._last_good.get(symbol, []))

        with self._lock:
            now = time.time()
            self._cache[symbol] = (now, deduped)
            if deduped:
                self._last_good[symbol] = list(deduped)

        return deduped

    def get_last_good(self, symbol: str) -> list[dict[str, Any]]:
        return self._last_good.get(symbol.strip().upper(), [])

    def invalidate(self, symbol: str | None = None) -> None:
        with self._lock:
            if symbol is None:
                self._cache.clear()
                self._last_good.clear()
            else:
                s = symbol.strip().upper()
                self._cache.pop(s, None)

    def register_external_headlines(
        self, symbol: str, items: list[dict[str, Any]]
    ) -> None:
        """Merge collector/RSS headlines into the deduped per-symbol cache."""
        symbol = symbol.strip().upper()
        if not items:
            return
        with self._lock:
            now = time.time()
            existing = list(self._cache.get(symbol, (0, []))[1])
            seen = {_headline_hash(str(item.get("headline", ""))) for item in existing}
            for item in items:
                headline = str(item.get("headline", "")).strip()
                if not headline:
                    continue
                h = _headline_hash(headline)
                if h in seen:
                    continue
                seen.add(h)
                normalized = _normalize_item(item)
                normalized["provider"] = item.get("provider", "Collector")
                normalized["retrieved_at"] = _now()
                normalized["dedup_key"] = h
                existing.append(normalized)
            existing.sort(
                key=lambda x: _sort_timestamp(x.get("timestamp")),
                reverse=True,
            )
            existing = existing[: self._max_headlines]
            self._cache[symbol] = (now, existing)
            if existing:
                self._last_good[symbol] = list(existing)


_ORCHESTRATOR: NewsOrchestrator | None = None
_ORCH_LOCK = threading.Lock()


def get_news_orchestrator() -> NewsOrchestrator:
    global _ORCHESTRATOR
    with _ORCH_LOCK:
        if _ORCHESTRATOR is None:
            _ORCHESTRATOR = NewsOrchestrator()
        return _ORCHESTRATOR


def configure_news_orchestrator(orchestrator: NewsOrchestrator) -> NewsOrchestrator:
    global _ORCHESTRATOR
    with _ORCH_LOCK:
        _ORCHESTRATOR = orchestrator
        return _ORCHESTRATOR


# Legacy compatibility
NewsApiClient = NewsApiProvider
get_newsapi_client = get_news_orchestrator


__all__ = [
    "FinnhubNewsProvider",
    "FinvizNewsProvider",
    "NewsApiProvider",
    "NewsApiClient",
    "NewsOrchestrator",
    "NewsProvider",
    "configure_news_orchestrator",
    "get_news_orchestrator",
    "get_newsapi_client",
]
