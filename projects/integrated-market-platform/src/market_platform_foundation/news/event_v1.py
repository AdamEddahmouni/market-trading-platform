"""Map canonical NewsArticleEvent into EventV1 with PIT clocks.

Publication time and retrieval time are never conflated. ``event_time_ns`` is
source publication when known; ``available_time_ns`` / ``received_time_ns`` are
IMP retrieval/observation time.
"""

from __future__ import annotations

from ..intelligence.contracts.common import QualityState, SourceReference
from ..intelligence.contracts.event import EventV1
from ..intelligence.normalization.event_builder import build_event_v1
from ..intelligence.normalization.models import (
    AvailabilityBasis,
    AvailabilityConfidence,
    AvailabilityDerivation,
    IngestionMode,
    ProviderProvenance,
    SourcePrecision,
)
from .contracts import NewsArticleEvent, PublicationTimeQuality
from .timestamps import epoch_ns_from_iso

NEWS_EVENT_TYPE = "NEWS_ARTICLE"
ADAPTER_ID = "finviz.news"
ADAPTER_VERSION = "1"
NORMALIZATION_VERSION = "intelligence/normalization/finviz-news/1"


def news_article_to_event_v1(
    article: NewsArticleEvent,
    *,
    server_received_time_ns: int | None = None,
) -> EventV1:
    """Convert a normalized news article into EventV1. Does not persist."""

    retrieved_ns = epoch_ns_from_iso(article.retrieved_time)
    if retrieved_ns is None:
        raise ValueError("NEWS_RETRIEVED_TIME_REQUIRED")
    published_ns = epoch_ns_from_iso(article.published_time)
    if published_ns is None:
        raise ValueError("NEWS_PUBLICATION_TIME_REQUIRED")
    event_time_ns = published_ns
    received_ns = int(server_received_time_ns) if server_received_time_ns is not None else int(retrieved_ns)
    available_ns = int(retrieved_ns)
    instrument_id = None
    native_symbol = None
    if article.instrument_linkages:
        instrument_id = article.instrument_linkages[0].instrument_id
        native_symbol = article.instrument_linkages[0].provider_symbol or instrument_id
    availability = AvailabilityDerivation(
        basis=AvailabilityBasis.LOCAL_RECEIPT,
        confidence=AvailabilityConfidence.DIRECTLY_OBSERVED,
        source_precision=SourcePrecision.SECOND,
        provider_reported_available_time_ns=available_ns,
        notes="available_time_ns is client retrieval; received_time_ns is server receive when stamped",
    )
    provenance = ProviderProvenance(
        provider_id=article.provider_id,
        source_record_type="news_article",
        adapter_id=ADAPTER_ID,
        adapter_version=ADAPTER_VERSION,
        normalization_version=NORMALIZATION_VERSION,
        provider_native_symbol=native_symbol,
        provider_native_record_id=article.provider_native_id or article.event_id,
        provider_event_type=NEWS_EVENT_TYPE,
        raw_payload_ref=article.raw_reference or None,
        availability=availability,
        ingestion_mode=IngestionMode.LIVE_OBSERVED,
        source_publication_id=article.url or None,
    )
    source = SourceReference(
        provider_id=article.provider_id,
        source_type="NEWS",
        source_record_id=article.event_id,
        raw_reference=article.raw_reference or None,
        external_id=article.provider_native_id or None,
    )
    quality_state = (
        QualityState.GOOD
        if article.published_time_quality == PublicationTimeQuality.KNOWN
        else QualityState.DEGRADED
    )
    return build_event_v1(
        event_id=article.event_id,
        event_type=NEWS_EVENT_TYPE,
        event_time_ns=event_time_ns,
        available_time_ns=available_ns,
        payload=article.to_dict(),
        source=source,
        provenance=provenance,
        instrument_id=instrument_id,
        provider_time_ns=published_ns,
        received_time_ns=received_ns,
        quality_state=quality_state,
        quality_flags=article.quality_flags,
    )


__all__ = ["NEWS_EVENT_TYPE", "news_article_to_event_v1"]
