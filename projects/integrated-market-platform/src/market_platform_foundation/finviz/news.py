"""Finviz news export normalization."""

from __future__ import annotations

import csv
import hashlib
import io
import re
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from .config import FINVIZ_NEWS_URL, NEWS_CACHE_TTL_S, finviz_api_key
from .request_manager import FinvizRequestManager, RequestPriority, get_finviz_request_manager, redact_text

_FINVIZ_PROVIDER_ID = "finviz"
_FINVIZ_SOURCE_ID = "finviz_elite"


def _utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _canonical_news_url(url: str) -> str:
    text = (url or "").strip().lower()
    if not text:
        return ""
    parsed = urlparse(text)
    if not parsed.scheme or not parsed.netloc:
        return ""
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def _normalize_headline_for_id(headline: str) -> str:
    text = " ".join(str(headline or "").lower().split())
    text = re.sub(r"[^\w\s]", "", text)
    return text.strip()


def stable_finviz_provider_news_id(
    *,
    url: str = "",
    headline: str = "",
    source_id: str = _FINVIZ_SOURCE_ID,
    provider_id: str = _FINVIZ_PROVIDER_ID,
) -> str | None:
    """Process-stable Finviz item id. No ``hash()`` salt; no retrieval timestamp.

    Prefer canonical URL when present; otherwise require a non-empty headline and
    hash stable fields. Missing identity inputs fail closed (``None``) instead of
    minting a random or process-salted id.
    """

    canonical_url = _canonical_news_url(url)
    if canonical_url:
        digest = hashlib.sha256(
            f"{provider_id}|url|{canonical_url}".encode("utf-8")
        ).hexdigest()[:16]
        return f"{provider_id}:{digest}"
    headline_key = _normalize_headline_for_id(headline)
    if not headline_key:
        return None
    source_key = str(source_id or _FINVIZ_SOURCE_ID).strip() or _FINVIZ_SOURCE_ID
    payload = "|".join(
        [
            str(provider_id or _FINVIZ_PROVIDER_ID).strip() or _FINVIZ_PROVIDER_ID,
            canonical_url,
            headline_key,
            source_key,
        ]
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{provider_id}:{digest}"


def normalize_news_timestamp(raw: str | None) -> str:
    if not raw:
        return ""
    text = str(raw).strip()
    if not text:
        return ""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.isoformat().replace("+00:00", "Z")
    except (ValueError, TypeError):
        pass
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%m/%d/%Y",
        "%b-%d-%y %I:%M%p",
        "%b-%d-%y",
        "%b-%d-%Y %I:%M%p",
        "%b-%d-%Y",
    ):
        try:
            parsed = datetime.strptime(text, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.isoformat().replace("+00:00", "Z")
        except ValueError:
            continue
    return text


def parse_news_csv(text: str) -> tuple[list[dict[str, Any]], str | None]:
    lowered = text[:10_000].lower()
    if "<html" in lowered:
        return [], "FINVIZ_NEWS_LOGIN_PAGE"
    reader = csv.DictReader(io.StringIO(text))
    headlines: list[dict[str, Any]] = []
    for row in reader:
        tickers_raw = (row.get("Ticker", "") or "").strip()
        tickers = [t.strip().upper() for t in tickers_raw.split(",") if t.strip()]
        published = normalize_news_timestamp(row.get("Date", ""))
        headline = row.get("Title", "") or ""
        url = row.get("Url", "") or ""
        provider_news_id = stable_finviz_provider_news_id(url=url, headline=headline)
        if provider_news_id is None:
            # Fail closed: no process salt / random id when identity inputs are missing.
            continue
        headlines.append(
            {
                "headline": headline,
                "published_time": published,
                "url": url,
                "tickers": tickers,
                "provider": "FINVIZ_ELITE",
                "publisher_source": row.get("Source", "") or "Finviz",
                "provider_news_id": provider_news_id,
                "raw_fields": dict(row),
            }
        )
    return headlines, None


class FinvizNewsClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        request_manager: FinvizRequestManager | None = None,
    ) -> None:
        self._api_key = api_key or finviz_api_key()
        self._manager = request_manager or get_finviz_request_manager()

    def fetch_news(self, *, force: bool = False) -> dict[str, Any]:
        received_at = _utc_iso()
        received_ns = time.time_ns()
        if not self._api_key:
            return {"success": False, "error": "NOT_CONFIGURED", "items": [], "received_at": received_at}
        if force:
            self._manager.clear_cache()
        params = {"v": 3, "auth": self._api_key}
        status, body, meta = self._manager.get(
            FINVIZ_NEWS_URL,
            params=params,
            priority=RequestPriority.NEWS_CATALYST,
            cache_ttl_s=None if force else NEWS_CACHE_TTL_S,
            api_key=self._api_key,
        )
        available_ns = time.time_ns()
        if status != 200:
            return {
                "success": False,
                "error": redact_text(f"HTTP_{status}", self._api_key),
                "items": [],
                "received_at": received_at,
                "available_time_ns": available_ns,
            }
        items, err = parse_news_csv(body)
        if err:
            return {
                "success": False,
                "error": err,
                "items": [],
                "received_at": received_at,
                "available_time_ns": available_ns,
            }
        for item in items:
            item["received_time"] = received_at
            item["available_time_ns"] = available_ns
        return {
            "success": True,
            "error": None,
            "items": items,
            "received_at": received_at,
            "available_time_ns": available_ns,
            "meta": meta,
        }

    def news_for_symbol(self, symbol: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        needle = symbol.strip().upper()
        return [item for item in items if needle in item.get("tickers", [])]


__all__ = [
    "FinvizNewsClient",
    "normalize_news_timestamp",
    "parse_news_csv",
    "stable_finviz_provider_news_id",
]
