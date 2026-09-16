"""Finviz/normalized news → EventV1 admission for LIVE_OBSERVATIONAL (software path).

Runs the canonical ``NewsPipeline`` PIT/recency/dedupe chain. Stamps server receive
time separately from client ``retrieved_time``. Consumes in-tree
``ProspectiveCatalystIngressResult`` / ``prospective_ingress`` receipt rows from #207
without re-implementing Finviz HTTP. Does not enable broker execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..clock import monotonic_wall_ns
from ..intelligence.normalization.models import IngestionMode
from ..intelligence.paper_forward_bridge.ftep_prospective_catalyst_ingress import (
    CLASS_SUCCESS,
    ProspectiveCatalystIngressResult,
)
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
    ingestion_mode: IngestionMode = IngestionMode.LIVE_OBSERVED,
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

    event = news_article_to_event_v1(
        article,
        server_received_time_ns=when,
        ingestion_mode=ingestion_mode,
    )
    event, receipt = admit_news_article_event(
        article,
        router=router,
        store=store,
        dispatch_time_ns=when,
        source_label=source_label,
        prebuilt_event=event,
        ingestion_mode=ingestion_mode,
    )
    return NewsObservationalAdmitOutcome(accepted=True, event=event, receipt=receipt)


def finviz_export_item_from_prospective_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Map a prospective ingress attention row back to Finviz export shape."""

    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    symbol = str(row.get("symbol") or row.get("instrument_id") or metadata.get("instrument_id") or "").strip()
    tickers = [symbol] if symbol else []
    published = str(
        row.get("published_time") or metadata.get("published_time") or ""
    ).strip()
    retrieved = str(row.get("retrieved_time") or metadata.get("retrieved_time") or "").strip()
    headline = str(row.get("headline") or metadata.get("headline") or "").strip()
    native_id = str(
        row.get("source_event_id")
        or row.get("provider_native_id")
        or metadata.get("provider_native_id")
        or ""
    ).strip()
    item: dict[str, Any] = {
        "headline": headline,
        "published_time": published,
        "url": str(row.get("url") or metadata.get("url") or ""),
        "tickers": tickers,
        "provider_native_id": native_id or None,
        "publisher_source": str(row.get("publisher_source") or metadata.get("publisher_source") or "Wire"),
    }
    if retrieved:
        item["retrieved_time"] = retrieved
    return item


def admit_prospective_catalyst_ingress_result(
    ingress: ProspectiveCatalystIngressResult | Mapping[str, Any],
    *,
    router: ObservationIngressRouter,
    store: Any | None = None,
    pipeline_config: PipelineConfig | None = None,
    source_label: str = "finviz_elite_news",
) -> tuple[NewsObservationalAdmitOutcome, ...]:
    """Admit pipeline-accepted Finviz rows from a #207 ``ProspectiveCatalystIngressResult``."""

    if isinstance(ingress, ProspectiveCatalystIngressResult):
        report = ingress.to_report_dict()
        rows = ingress.rows
        stats = ingress.stats
    else:
        report = dict(ingress)
        prospective = report.get("prospective_ingress")
        if isinstance(prospective, dict):
            report = {**report, **prospective}
        rows = tuple(report.get("rows") or ())
        stats = report.get("stats") if isinstance(report.get("stats"), dict) else {}
    classification = str(report.get("classification") or "")
    if classification and classification not in {CLASS_SUCCESS}:
        reason = str(report.get("reason") or classification or "INGRESS_NOT_ADMITTABLE")
        return (
            NewsObservationalAdmitOutcome(accepted=False, reason_code=reason, detail=classification),
        )
    server_received_time_ns = stats.get("as_of_ns") if isinstance(stats, dict) else None
    if server_received_time_ns is not None:
        server_received_time_ns = int(server_received_time_ns)
    else:
        server_received_time_ns = int(monotonic_wall_ns())
    outcomes: list[NewsObservationalAdmitOutcome] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        export_item = finviz_export_item_from_prospective_row(row)
        retrieved_time = str(export_item.pop("retrieved_time", "") or "").strip()
        if not retrieved_time:
            outcomes.append(
                NewsObservationalAdmitOutcome(
                    accepted=False,
                    reason_code="NEWS_RETRIEVED_TIME_REQUIRED",
                )
            )
            continue
        outcomes.append(
            admit_finviz_export_item_for_observation(
                export_item,
                retrieved_time=retrieved_time,
                router=router,
                store=store,
                server_received_time_ns=server_received_time_ns,
                pipeline_config=pipeline_config,
                source_label=source_label,
            )
        )
    return tuple(outcomes)


def admit_finviz_export_item_for_observation(
    item: dict[str, Any],
    *,
    retrieved_time: str,
    router: ObservationIngressRouter,
    store: Any | None = None,
    server_received_time_ns: int | None = None,
    pipeline_config: PipelineConfig | None = None,
    source_label: str = "finviz_elite_news",
    ingestion_mode: IngestionMode = IngestionMode.LIVE_OBSERVED,
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
        ingestion_mode=ingestion_mode,
    )


__all__ = [
    "NewsObservationalAdmitOutcome",
    "admit_finviz_export_item_for_observation",
    "admit_news_article_for_observation",
    "admit_prospective_catalyst_ingress_result",
    "finviz_export_item_from_prospective_row",
    "validate_news_pit_clocks",
]
