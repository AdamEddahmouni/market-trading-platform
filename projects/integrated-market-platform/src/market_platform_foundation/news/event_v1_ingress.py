"""Admit NewsArticleEvent into production observation ingress (EventV1 + put_event)."""

from __future__ import annotations

from typing import Any

from ..intelligence.contracts.event import EventV1
from ..intelligence.normalization.models import IngestionMode
from ..intelligence.observation_ingress.router import ObservationIngressRouter
from ..intelligence.observation_ingress.types import IngressDispatchContext, IngressDispatchReceiptV1
from .contracts import NewsArticleEvent
from .event_v1 import news_article_to_event_v1


def admit_news_article_event(
    article: NewsArticleEvent,
    *,
    router: ObservationIngressRouter,
    dispatch_time_ns: int | None = None,
    store: Any | None = None,
    source_label: str = "finviz_elite_news",
) -> tuple[EventV1, IngressDispatchReceiptV1]:
    """Map one news article to EventV1 and dispatch through the production router.

    Called by ``UiApiHandler`` ``POST /intelligence/ingest/news`` for already-fetched
    rows. Updates ``store.last_source_time_ns`` / ``as_of_time_ns`` from retrieval
    time when a store is provided. Does not auto-fetch Finviz or enable Live
    execution. Opportunity minting is the observational detector's job.
    """

    event = news_article_to_event_v1(article)
    received_ns = event.received_time_ns if event.received_time_ns is not None else event.available_time_ns
    context = IngressDispatchContext(
        dispatch_time_ns=dispatch_time_ns if dispatch_time_ns is not None else received_ns,
        ingestion_mode=IngestionMode.LIVE_OBSERVED,
        source_label=source_label,
    )
    receipt = router.dispatch(event, context=context)
    if store is not None and received_ns is not None:
        store.last_source_time_ns = int(received_ns)
        existing = getattr(store, "as_of_time_ns", None)
        store.as_of_time_ns = int(received_ns) if existing is None else max(int(existing), int(received_ns))
    return event, receipt


__all__ = ["admit_news_article_event"]
