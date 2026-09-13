"""Bridge NewsAggregator dict items to canonical NewsArticleEvent ingress."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from .contracts import NewsArticleEvent
from .normalize import normalize_raw_item


def received_time_to_retrieved_iso(received_time: str | int | float | None) -> str:
    """Map aggregator ``received_time`` to canonical ``retrieved_time`` (UTC ISO)."""
    if received_time is None:
        raise ValueError("NEWS_AGGREGATOR_RECEIVED_TIME_REQUIRED")
    if isinstance(received_time, (int, float)):
        seconds = float(received_time)
        if seconds > 1e15:
            seconds /= 1_000_000_000.0
        elif seconds > 1e12:
            seconds /= 1_000.0
        instant = datetime.fromtimestamp(seconds, tz=timezone.utc)
        return instant.isoformat().replace("+00:00", "Z")
    text = str(received_time).strip()
    if not text:
        raise ValueError("NEWS_AGGREGATOR_RECEIVED_TIME_REQUIRED")
    return text


def aggregator_item_to_event(
    item: Mapping[str, Any],
    *,
    retrieved_time: str | None = None,
    source_id: str = "news_aggregator",
) -> NewsArticleEvent:
    """Normalize one aggregated provider dict into ``NewsArticleEvent``."""
    provider = str(item.get("provider") or "NEWS_AGGREGATE")
    received = retrieved_time
    if received is None:
        received = received_time_to_retrieved_iso(item.get("received_time"))
    payload = dict(item)
    provenance = item.get("source_provenance")
    if isinstance(provenance, list) and provenance:
        payload["aggregator_source_provenance"] = provenance
    return normalize_raw_item(
        payload,
        provider_id=provider,
        source_id=source_id,
        retrieved_time=received,
    )


def aggregator_items_to_events(
    items: Sequence[Mapping[str, Any]],
    *,
    retrieved_time: str | None = None,
    source_id: str = "news_aggregator",
) -> tuple[NewsArticleEvent, ...]:
    return tuple(
        aggregator_item_to_event(
            item,
            retrieved_time=retrieved_time,
            source_id=source_id,
        )
        for item in items
        if isinstance(item, Mapping)
    )


__all__ = [
    "aggregator_item_to_event",
    "aggregator_items_to_events",
    "received_time_to_retrieved_iso",
]
