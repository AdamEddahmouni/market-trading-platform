"""Finviz news export normalization."""

from __future__ import annotations

import csv
import io
import time
from datetime import datetime, timezone
from typing import Any

from .config import FINVIZ_NEWS_URL, NEWS_CACHE_TTL_S, finviz_api_key
from .request_manager import FinvizRequestManager, RequestPriority, get_finviz_request_manager, redact_text


def _utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


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
        headlines.append(
            {
                "headline": row.get("Title", ""),
                "published_time": published,
                "url": row.get("Url", ""),
                "tickers": tickers,
                "provider": "FINVIZ_ELITE",
                "publisher_source": row.get("Source", "") or "Finviz",
                "provider_news_id": f"finviz:{hash(row.get('Title', '')) & 0xFFFFFFFF:08x}",
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
