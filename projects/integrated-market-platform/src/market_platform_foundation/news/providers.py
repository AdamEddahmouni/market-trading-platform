"""Read-only NewsAPI and Finnhub adapters with explicit live gates."""

from __future__ import annotations

import hashlib
import http.client
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from ..finviz.news import normalize_news_timestamp
from .config import (
    FINNHUB_URL,
    NEWSAPI_URL,
    finnhub_api_key,
    finnhub_live_enabled,
    newsapi_api_key,
    newsapi_live_enabled,
)


HttpGetter = Callable[..., Any]


def _utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _default_get(
    url: str,
    *,
    params: dict[str, Any],
    timeout: float,
    headers: dict[str, str],
) -> Any:
    target = f"{url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(target, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return type(
            "NewsHTTPResponse",
            (),
            {
                "status_code": int(getattr(response, "status", 200)),
                "text": response.read().decode("utf-8", errors="replace"),
                "headers": {
                    str(key).lower(): str(value)
                    for key, value in response.headers.items()
                },
            },
        )()


def _network_error(exc: BaseException) -> str:
    if isinstance(exc, (urllib.error.URLError, http.client.HTTPException, OSError)):
        return "NETWORK_ERROR"
    return "PROVIDER_ERROR"


def _date_range(
    from_date: str | None,
    to_date: str | None,
) -> tuple[str, str]:
    end = to_date or date.today().isoformat()
    start = from_date or (date.today() - timedelta(days=7)).isoformat()
    return start, end


def _ticker_list(symbol: str, related: Any = None) -> list[str]:
    values = [symbol.strip().upper()]
    if isinstance(related, str):
        values.extend(item.strip().upper() for item in related.split(",") if item.strip())
    elif isinstance(related, list):
        values.extend(str(item).strip().upper() for item in related if str(item).strip())
    return list(dict.fromkeys(values))


class _NewsClientBase:
    provider_id = ""

    def __init__(
        self,
        *,
        api_key: str | None,
        http_getter: HttpGetter | None,
        live_enabled: bool,
        min_interval_s: float,
    ) -> None:
        self._api_key = api_key
        self._http_getter = http_getter or _default_get
        self._live_enabled = live_enabled
        self._min_interval_s = max(0.0, min_interval_s)
        self._last_request_at = 0.0

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self._min_interval_s:
            time.sleep(self._min_interval_s - elapsed)
        self._last_request_at = time.monotonic()

    def _unavailable(self, reason: str, received_at: str) -> dict[str, Any]:
        return {
            "success": False,
            "error": reason,
            "items": [],
            "provider": self.provider_id,
            "received_at": received_at,
        }

    def _request(
        self,
        *,
        url: str,
        params: dict[str, Any],
        received_at: str,
    ) -> tuple[Any | None, dict[str, Any] | None]:
        self._wait()
        try:
            response = self._http_getter(
                url,
                params=params,
                timeout=15,
                headers={"User-Agent": "integrated-market-platform-news/1.0"},
            )
        except Exception as exc:
            return None, self._unavailable(_network_error(exc), received_at)
        status = int(getattr(response, "status_code", 0))
        if status != 200:
            return None, self._unavailable(f"HTTP_{status}", received_at)
        try:
            return json.loads(getattr(response, "text", "") or ""), None
        except (TypeError, ValueError, json.JSONDecodeError):
            return None, self._unavailable("INVALID_JSON", received_at)


class NewsApiClient(_NewsClientBase):
    """NewsAPI ``everything`` endpoint, limited to company-news discovery."""

    provider_id = "newsapi"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        http_getter: HttpGetter | None = None,
        live_enabled: bool | None = None,
        min_interval_s: float = 1.0,
    ) -> None:
        super().__init__(
            api_key=api_key or newsapi_api_key(),
            http_getter=http_getter,
            live_enabled=(
                newsapi_live_enabled() if live_enabled is None else live_enabled
            ),
            min_interval_s=min_interval_s,
        )

    def fetch_news(
        self,
        symbol: str,
        *,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> dict[str, Any]:
        received_at = _utc_iso()
        ticker = symbol.strip().upper()
        if not self._live_enabled:
            return self._unavailable("LIVE_DISABLED", received_at)
        if not self._api_key:
            return self._unavailable("NOT_CONFIGURED", received_at)
        start, end = _date_range(from_date, to_date)
        payload, error = self._request(
            url=NEWSAPI_URL,
            params={
                "apiKey": self._api_key,
                "q": f'"{ticker}"',
                "from": start,
                "to": end,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": 100,
            },
            received_at=received_at,
        )
        if error is not None:
            return error
        if not isinstance(payload, dict) or payload.get("status") != "ok":
            return self._unavailable("API_ERROR", received_at)
        items = [
            _normalize_newsapi_article(article, ticker, received_at)
            for article in payload.get("articles", [])
            if isinstance(article, dict)
        ]
        return {
            "success": True,
            "error": None,
            "items": items,
            "provider": self.provider_id,
            "received_at": received_at,
        }


class FinnhubNewsClient(_NewsClientBase):
    """Finnhub ``company-news`` endpoint for a bounded date window."""

    provider_id = "finnhub"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        http_getter: HttpGetter | None = None,
        live_enabled: bool | None = None,
        min_interval_s: float = 1.0,
    ) -> None:
        super().__init__(
            api_key=api_key or finnhub_api_key(),
            http_getter=http_getter,
            live_enabled=(
                finnhub_live_enabled() if live_enabled is None else live_enabled
            ),
            min_interval_s=min_interval_s,
        )

    def fetch_news(
        self,
        symbol: str,
        *,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> dict[str, Any]:
        received_at = _utc_iso()
        ticker = symbol.strip().upper()
        if not self._live_enabled:
            return self._unavailable("LIVE_DISABLED", received_at)
        if not self._api_key:
            return self._unavailable("NOT_CONFIGURED", received_at)
        start, end = _date_range(from_date, to_date)
        payload, error = self._request(
            url=FINNHUB_URL,
            params={
                "symbol": ticker,
                "from": start,
                "to": end,
                "token": self._api_key,
            },
            received_at=received_at,
        )
        if error is not None:
            return error
        if not isinstance(payload, list):
            return self._unavailable("API_ERROR", received_at)
        items = [
            _normalize_finnhub_article(article, ticker, received_at)
            for article in payload
            if isinstance(article, dict)
        ]
        return {
            "success": True,
            "error": None,
            "items": items,
            "provider": self.provider_id,
            "received_at": received_at,
        }


def _normalize_newsapi_article(
    article: dict[str, Any],
    symbol: str,
    received_at: str,
) -> dict[str, Any]:
    source = article.get("source") or {}
    url = str(article.get("url") or "")
    title = str(article.get("title") or "")
    news_id = f"newsapi:{hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]}"
    return {
        "headline": title,
        "published_time": normalize_news_timestamp(str(article.get("publishedAt") or "")),
        "url": url,
        "tickers": _ticker_list(symbol),
        "provider": "NEWSAPI",
        "publisher_source": str(source.get("name") or "NewsAPI"),
        "provider_news_id": news_id,
        "raw_fields": dict(article),
        "received_time": received_at,
        "available_time_ns": time.time_ns(),
    }


def _normalize_finnhub_article(
    article: dict[str, Any],
    symbol: str,
    received_at: str,
) -> dict[str, Any]:
    url = str(article.get("url") or "")
    title = str(article.get("headline") or "")
    raw_datetime = article.get("datetime")
    try:
        published = datetime.fromtimestamp(float(raw_datetime), tz=timezone.utc).isoformat()
        published = published.replace("+00:00", "Z")
    except (TypeError, ValueError, OverflowError, OSError):
        published = ""
    provider_id = article.get("id")
    news_id = (
        f"finnhub:{provider_id}"
        if provider_id is not None
        else f"finnhub:{hashlib.sha256((url or title).encode('utf-8')).hexdigest()[:16]}"
    )
    return {
        "headline": title,
        "published_time": published,
        "url": url,
        "tickers": _ticker_list(symbol, article.get("related")),
        "provider": "FINNHUB",
        "publisher_source": str(article.get("source") or "Finnhub"),
        "provider_news_id": news_id,
        "raw_fields": dict(article),
        "received_time": received_at,
        "available_time_ns": time.time_ns(),
    }


__all__ = ["FinnhubNewsClient", "NewsApiClient"]
