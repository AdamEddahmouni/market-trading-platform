"""Finviz/normalized news → EventV1 admission for LIVE_OBSERVATIONAL (software path).

Runs the canonical ``NewsPipeline`` PIT/recency/dedupe chain. Stamps server receive
time separately from client ``retrieved_time``. Does not fetch HTTP (#207) or enable
broker execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..clock import monotonic_wall_ns
from ..intelligence.contracts.event import EventV1
from ..intelligence.observation_ingress.router import ObservationIngressRouter
from ..intelligence.observation_ingress.types import IngressDispatchReceiptV1
from .contracts import NewsArticleEvent, PipelineConfig, PublicationTimeQuality
from .event_v1 import news_article_to_event_v1
from .event_v1_ingress import admit_news_article_event
from .normalize import normalize_finviz_export_item
from .pipeline import NewsPipeline
from .timestamps import epoch_ns_from_iso


@dataclass(frozen=True, slots=True)
class NewsObservationalAdmitOutcome:
    accepted: bool
    event: EventV1 | None = None
    receipt: IngressDispatchReceiptV1 | None = None
    reason_code: str | None = None
    detail: str | None = None


def validate_news_pit_clocks(article: NewsArticleEvent, *, server_received_time_ns: int) -> str | None:
    retrieved_ns = epoch_ns_from_iso(article.retrieved_time)
    if retrieved_ns is None:
        return "NEWS_RETRIEVED_TIME_REQUIRED"
    if int(retrieved_ns) > int(server_received_time_ns):
        return "NEWS_RETRIEVED_AFTER_SERVER_RECEIVE"
    published_ns = epoch_ns_from_iso(article.published_time)
    if published_ns is not None and int(published_ns) > int(retrieved_ns):
        return "NEWS_PUBLICATION_AFTER_RETRIEVAL"
    if published_ns is None and article.published_time_quality == PublicationTimeQuality.UNKNOWN:
        return "NEWS_PUBLICATION_TIME_REQUIRED"
    return None


def admit_news_article_for_observation(
    article: NewsArticleEvent,
    *,
    router: ObservationIngressRouter,
    store: Any | None = None,
    server_received_time_ns: int | None = None,
    pipeline_config: PipelineConfig | None = None,
    source_label: str = "finviz_elite_news",
) -> NewsObservationalAdmitOutcome:
    when = int(server_received_time_ns if server_received_time_ns is not None else monotonic_wall_ns())
    pit_reason = validate_news_pit_clocks(article, server_received_time_ns=when)
    if pit_reason is not None:
        return NewsObservationalAdmitOutcome(accepted=False, reason_code=pit_reason)

    pipeline = NewsPipeline()
    config = pipeline_config or PipelineConfig()
    results = pipeline.process([article], as_of_ns=when, config=config)
    if not results or not results[0].accepted:
        reason = "NEWS_PIPELINE_REJECTED"
        detail = ""
        if results and results[0].decisions:
            last = results[0].decisions[-1]
            reason = str(last.reason_code or reason)
            detail = str(last.detail or "")
        return NewsObservationalAdmitOutcome(accepted=False, reason_code=reason, detail=detail or None)

    event = news_article_to_event_v1(article, server_received_time_ns=when)
    event, receipt = admit_news_article_event(
        article,
        router=router,
        store=store,
        dispatch_time_ns=when,
        source_label=source_label,
        prebuilt_event=event,
    )
    return NewsObservationalAdmitOutcome(accepted=True, event=event, receipt=receipt)


def admit_finviz_export_item_for_observation(
    item: dict[str, Any],
    *,
    retrieved_time: str,
    router: ObservationIngressRouter,
    store: Any | None = None,
    server_received_time_ns: int | None = None,
    pipeline_config: PipelineConfig | None = None,
    source_label: str = "finviz_elite_news",
) -> NewsObservationalAdmitOutcome:
    """Runtime convergence entry: normalized Finviz export row → EventV1 admit."""

    article = normalize_finviz_export_item(item, retrieved_time=retrieved_time)
    return admit_news_article_for_observation(
        article,
        router=router,
        store=store,
        server_received_time_ns=server_received_time_ns,
        pipeline_config=pipeline_config,
        source_label=source_label,
    )


__all__ = [
    "NewsObservationalAdmitOutcome",
    "admit_finviz_export_item_for_observation",
    "admit_news_article_for_observation",
    "validate_news_pit_clocks",
]
