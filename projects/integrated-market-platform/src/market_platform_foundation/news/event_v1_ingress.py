"""Admit NewsArticleEvent into production observation ingress (EventV1 + put_event)."""

from __future__ import annotations

from typing import Any

from ..clock import monotonic_wall_ns
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
    prebuilt_event: EventV1 | None = None,
    ingestion_mode: IngestionMode | None = None,
) -> tuple[EventV1, IngressDispatchReceiptV1]:
    """Map one news article to EventV1 and dispatch through the production router.

    Updates ``store.last_source_time_ns`` / ``as_of_time_ns`` from **server**
    ``received_time_ns`` when a store is provided. Does not auto-fetch Finviz or
    enable Live broker execution.
    """

    when = int(
        dispatch_time_ns
        if dispatch_time_ns is not None
        else (prebuilt_event.received_time_ns if prebuilt_event is not None else monotonic_wall_ns())
    )
    mode = ingestion_mode if ingestion_mode is not None else IngestionMode.LIVE_OBSERVED
    event = prebuilt_event or news_article_to_event_v1(
        article,
        server_received_time_ns=when,
        ingestion_mode=mode,
    )
    received_ns = event.received_time_ns
    if received_ns is None:
        raise ValueError("NEWS_SERVER_RECEIVED_TIME_REQUIRED")
    context = IngressDispatchContext(
        dispatch_time_ns=when,
        ingestion_mode=mode,
        source_label=source_label,
    )
    receipt = router.dispatch(event, context=context)
    if store is not None:
        store.last_source_time_ns = int(received_ns)
        existing = getattr(store, "as_of_time_ns", None)
        store.as_of_time_ns = int(received_ns) if existing is None else max(int(existing), int(received_ns))
    return event, receipt


__all__ = ["admit_news_article_event"]
