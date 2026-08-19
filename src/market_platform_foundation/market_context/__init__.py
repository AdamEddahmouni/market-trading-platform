"""Market Context lane — entity resolution, event clustering, and baseline sentiment."""

from .entity_resolution import (
    PRODUCER_VERSION as ENTITY_RESOLUTION_VERSION,
    ContextDocumentRecord,
    build_symbol_mapping_registry,
    load_context_document_records,
    raw_document_from_fixture_row,
    resolve_document_entities,
    resolve_entity_from_claims,
)
from .event_clustering import (
    cluster_fixture_records,
    cluster_information_events,
)
from .sentiment import (
    PRODUCER_VERSION as SENTIMENT_VERSION,
    DocumentSentimentResult,
    EventSentimentSummary,
    aggregate_event_sentiment,
    build_event_sentiment_summaries,
    build_fixture_sentiment_pipeline,
    build_sentiment_cross_lane_evidence,
    load_finbert_fixture_labels,
    score_document_sentiment,
    score_keyword_baseline,
)

__all__ = [
    "ENTITY_RESOLUTION_VERSION",
    "SENTIMENT_VERSION",
    "ContextDocumentRecord",
    "DocumentSentimentResult",
    "EventSentimentSummary",
    "aggregate_event_sentiment",
    "build_event_sentiment_summaries",
    "build_fixture_sentiment_pipeline",
    "build_sentiment_cross_lane_evidence",
    "build_symbol_mapping_registry",
    "cluster_fixture_records",
    "cluster_information_events",
    "load_context_document_records",
    "load_finbert_fixture_labels",
    "raw_document_from_fixture_row",
    "resolve_document_entities",
    "resolve_entity_from_claims",
    "score_document_sentiment",
    "score_keyword_baseline",
]
