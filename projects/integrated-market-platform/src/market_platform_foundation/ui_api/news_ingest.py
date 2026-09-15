"""UiApiHandler request-path for already-fetched Finviz/news → EventV1 admission.

Does not auto-fetch providers or start a retry loop. Observational only.
"""

from __future__ import annotations

from typing import Any

from ..news.event_v1_ingress import admit_news_article_event
from ..news.normalize import normalize_finviz_export_item
from ..news.observational_opportunity import observational_news_opportunity_id
from .live_intelligence import bind_ui_api_intelligence
from .store import ReplayStore

NEWS_INGEST_MAX_BODY_BYTES = 65_536
NEWS_INGEST_ROUTE = "/intelligence/ingest/news"


def enforce_news_ingest_body_limit(content_length: int) -> None:
    if content_length < 0:
        raise ValueError("NEWS_INGEST_CONTENT_LENGTH_INVALID")
    if content_length > NEWS_INGEST_MAX_BODY_BYTES:
        raise ValueError("NEWS_INGEST_BODY_TOO_LARGE")


def handle_news_ingest_post(store: ReplayStore, body: dict[str, Any]) -> dict[str, Any]:
    """Admit already-fetched news rows through ObservationIngressRouter.put_event."""

    bind_ui_api_intelligence(store)
    router = getattr(store, "observation_ingress_router", None)
    if router is None:
        raise ValueError("NEWS_INGEST_ROUTER_UNAVAILABLE")
    articles_raw = body.get("articles")
    if articles_raw is None:
        raise ValueError("NEWS_INGEST_ARTICLES_REQUIRED")
    if not isinstance(articles_raw, list):
        raise ValueError("NEWS_INGEST_ARTICLES_INVALID")
    retrieved_time = str(body.get("retrieved_time") or "").strip()
    admitted: list[dict[str, Any]] = []
    opportunity_ids: list[str] = []
    skipped: list[dict[str, str]] = []
    repository = getattr(store, "strategy_repository", None)
    for item in articles_raw:
        if not isinstance(item, dict):
            skipped.append({"reason": "NEWS_INGEST_ITEM_NOT_OBJECT"})
            continue
        item_retrieved = str(item.get("retrieved_time") or retrieved_time).strip()
        if not item_retrieved:
            skipped.append({"reason": "NEWS_RETRIEVED_TIME_REQUIRED"})
            continue
        article = normalize_finviz_export_item(item, retrieved_time=item_retrieved)
        event, receipt = admit_news_article_event(article, router=router, store=store)
        detector_detail = None
        for row in receipt.outcomes:
            if str(row.kind) == "DETECTOR":
                detector_detail = row.detail
                break
        opportunity_id = observational_news_opportunity_id(event.event_id)
        persisted = None
        getter = getattr(repository, "get_opportunity", None)
        if callable(getter):
            persisted = getter(opportunity_id)
        if persisted is None:
            opportunity_id = None
        else:
            opportunity_ids.append(opportunity_id)
        admitted.append(
            {
                "event_id": event.event_id,
                "opportunity_id": opportunity_id,
                "detector_detail": detector_detail,
                "event_time_ns": event.event_time_ns,
                "available_time_ns": event.available_time_ns,
                "received_time_ns": event.received_time_ns,
                "provider_time_ns": event.provider_time_ns,
            }
        )
    return {
        "admitted_count": len(admitted),
        "opportunity_count": len(opportunity_ids),
        "zero_qualifying_count": len(admitted) - len(opportunity_ids),
        "skipped_count": len(skipped),
        "events": admitted,
        "opportunity_ids": opportunity_ids,
        "skipped": skipped,
        "live_authority": False,
        "auto_fetch": False,
        "news_event_build09": "INACTIVE",
    }


__all__ = [
    "NEWS_INGEST_MAX_BODY_BYTES",
    "NEWS_INGEST_ROUTE",
    "enforce_news_ingest_body_limit",
    "handle_news_ingest_post",
]
