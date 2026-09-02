"""Provider-neutral aggregation for read-only company news."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Protocol

from ..finviz.news import FinvizNewsClient
from .providers import FinnhubNewsClient, NewsApiClient


class NewsSource(Protocol):
    provider_id: str

    def fetch_news(self, symbol: str) -> dict[str, Any]:
        ...


class _FinvizNewsSource:
    provider_id = "finviz"

    def __init__(self, client: FinvizNewsClient) -> None:
        self._client = client

    def fetch_news(self, symbol: str) -> dict[str, Any]:
        result = self._client.fetch_news()
        if result.get("success"):
            result = dict(result)
            result["items"] = self._client.news_for_symbol(
                symbol,
                list(result.get("items") or []),
            )
        return result


def _dedupe_key(item: dict[str, Any]) -> tuple[str, ...]:
    url = str(item.get("url") or "").strip().lower().rstrip("/")
    if url:
        return ("url", url)
    headline = " ".join(str(item.get("headline") or "").lower().split())
    published = str(item.get("published_time") or "")[:10]
    return ("content", headline, published)


def _provenance(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider": item.get("provider"),
        "provider_news_id": item.get("provider_news_id"),
        "publisher_source": item.get("publisher_source"),
        "url": item.get("url"),
    }


def aggregate_news_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, ...], dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        key = _dedupe_key(item)
        current = merged.get(key)
        if current is None:
            current = deepcopy(item)
            current["provider"] = "NEWS_AGGREGATE"
            current["providers"] = []
            current["provider_news_ids"] = []
            current["source_provenance"] = []
            merged[key] = current
        provider = str(item.get("provider") or "")
        provider_news_id = str(item.get("provider_news_id") or "")
        if provider and provider not in current["providers"]:
            current["providers"].append(provider)
        if provider_news_id and provider_news_id not in current["provider_news_ids"]:
            current["provider_news_ids"].append(provider_news_id)
        current["source_provenance"].append(_provenance(item))

    result = list(merged.values())
    for item in result:
        item["providers"] = sorted(item["providers"])
        item["provider_news_ids"] = sorted(item["provider_news_ids"])
        item["source_provenance"] = sorted(
            item["source_provenance"],
            key=lambda row: (
                str(row.get("provider") or ""),
                str(row.get("provider_news_id") or ""),
            ),
        )
    return sorted(
        result,
        key=lambda item: (
            str(item.get("published_time") or ""),
            str(item.get("url") or ""),
        ),
        reverse=True,
    )


class NewsAggregator:
    """Fetch Finviz, NewsAPI, and Finnhub without coupling source failures."""

    def __init__(
        self,
        *,
        sources: tuple[NewsSource, ...] | None = None,
        finviz_client: FinvizNewsClient | None = None,
    ) -> None:
        self._sources = sources or (
            _FinvizNewsSource(finviz_client or FinvizNewsClient()),
            NewsApiClient(),
            FinnhubNewsClient(),
        )

    def fetch_news(self, symbol: str) -> dict[str, Any]:
        source_status: dict[str, dict[str, Any]] = {}
        all_items: list[dict[str, Any]] = []
        errors: dict[str, str] = {}
        for source in self._sources:
            provider = str(source.provider_id)
            try:
                result = source.fetch_news(symbol)
            except Exception:
                result = {
                    "success": False,
                    "error": "PROVIDER_EXCEPTION",
                    "items": [],
                    "provider": provider,
                }
            source_status[provider] = {
                "success": bool(result.get("success")),
                "error": result.get("error"),
                "count": len(result.get("items") or []),
            }
            if result.get("success"):
                all_items.extend(
                    item for item in result.get("items", []) if isinstance(item, dict)
                )
            elif result.get("error"):
                errors[provider] = str(result["error"])
        items = aggregate_news_items(all_items)
        return {
            "success": bool(all_items),
            "error": None if all_items else "NO_PROVIDER_DATA",
            "items": items,
            "source_status": source_status,
            "errors": errors,
        }


__all__ = ["NewsAggregator", "aggregate_news_items"]
