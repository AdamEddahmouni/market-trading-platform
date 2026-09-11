"""Canonical normalized news/article event contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class PublicationTimeQuality(StrEnum):
    """How confidently IMP knows when the source published the item."""

    KNOWN = "KNOWN"
    INFERRED_LOW_CONFIDENCE = "INFERRED_LOW_CONFIDENCE"
    UNKNOWN = "UNKNOWN"


class SourceAvailability(StrEnum):
    """Whether a catalog source is merely known or operationally wired."""

    KNOWN = "KNOWN"
    CONFIGURED = "CONFIGURED"
    AVAILABLE_PROVIDER = "AVAILABLE_PROVIDER"
    OPERATIONAL = "OPERATIONAL"


class DuplicateRelationship(StrEnum):
    DISTINCT = "DISTINCT"
    EXACT_DUPLICATE = "EXACT_DUPLICATE"
    LIKELY_SYNDICATED = "LIKELY_SYNDICATED"


class FilterStage(StrEnum):
    OBSERVABILITY = "OBSERVABILITY"
    DEDUPLICATION = "DEDUPLICATION"
    RECENCY = "RECENCY"
    SOURCE_POLICY = "SOURCE_POLICY"
    CATALYST_KEYWORD = "CATALYST_KEYWORD"


@dataclass(frozen=True, slots=True)
class InstrumentLinkage:
    """Association between a news item and a canonical IMP instrument."""

    instrument_id: str
    provider_symbol: str = ""
    asset_class: str = ""
    linkage_method: str = "PROVIDER_SYMBOL"
    confidence: str = "EXPLICIT"


@dataclass(frozen=True, slots=True)
class NewsArticleEvent:
    """Canonical normalized news event — publication and retrieval times are never conflated."""

    event_id: str
    provider_id: str
    provider_native_id: str
    source_id: str
    published_time: str
    published_time_quality: PublicationTimeQuality
    retrieved_time: str
    headline: str
    summary: str = ""
    url: str = ""
    language: str = "en"
    instrument_linkages: tuple[InstrumentLinkage, ...] = ()
    publisher_source: str = ""
    raw_reference: str = ""
    quality_flags: tuple[str, ...] = ()
    normalization_version: str = "news/contracts/1.0.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "provider_id": self.provider_id,
            "provider_native_id": self.provider_native_id,
            "source_id": self.source_id,
            "published_time": self.published_time,
            "published_time_quality": self.published_time_quality.value,
            "retrieved_time": self.retrieved_time,
            "headline": self.headline,
            "summary": self.summary,
            "url": self.url,
            "language": self.language,
            "instrument_linkages": [
                {
                    "instrument_id": link.instrument_id,
                    "provider_symbol": link.provider_symbol,
                    "asset_class": link.asset_class,
                    "linkage_method": link.linkage_method,
                    "confidence": link.confidence,
                }
                for link in self.instrument_linkages
            ],
            "publisher_source": self.publisher_source,
            "raw_reference": self.raw_reference,
            "quality_flags": list(self.quality_flags),
            "normalization_version": self.normalization_version,
        }


@dataclass(frozen=True, slots=True)
class FilterDecision:
    """Explainable acceptance or rejection from one deterministic filter stage."""

    stage: FilterStage
    accepted: bool
    reason_code: str
    detail: str = ""
    matched_catalyst_ids: tuple[str, ...] = ()
    policy_version: str = ""
    event_age_seconds: int | None = None


@dataclass(frozen=True, slots=True)
class PipelineEventResult:
    """Outcome of processing one event through the deterministic pipeline."""

    event: NewsArticleEvent
    accepted: bool
    decisions: tuple[FilterDecision, ...] = ()
    duplicate_of: str = ""
    duplicate_relationship: DuplicateRelationship = DuplicateRelationship.DISTINCT


@dataclass(frozen=True, slots=True)
class PipelineConfig:
    """Governed configuration for the deterministic news pipeline."""

    recency_max_age_seconds: int = 72 * 3600
    recency_reject_future_seconds: int = 300
    recency_unknown_publication_policy: str = "USE_RETRIEVED_FOR_AGE_ONLY"
    require_catalyst_match: bool = True
    source_policy_version: str = "news/sources/1.0.0"
    catalyst_registry_version: str = "news/catalysts/1.0.0"
    filter_chain_version: str = "news/filters/1.0.0"
    enabled_source_ids: frozenset[str] = frozenset()
    enabled_catalyst_ids: frozenset[str] = frozenset()

    def to_dict(self) -> dict[str, Any]:
        return {
            "recency_max_age_seconds": self.recency_max_age_seconds,
            "recency_reject_future_seconds": self.recency_reject_future_seconds,
            "recency_unknown_publication_policy": self.recency_unknown_publication_policy,
            "require_catalyst_match": self.require_catalyst_match,
            "source_policy_version": self.source_policy_version,
            "catalyst_registry_version": self.catalyst_registry_version,
            "filter_chain_version": self.filter_chain_version,
            "enabled_source_ids": sorted(self.enabled_source_ids),
            "enabled_catalyst_ids": sorted(self.enabled_catalyst_ids),
        }


__all__ = [
    "DuplicateRelationship",
    "FilterDecision",
    "FilterStage",
    "InstrumentLinkage",
    "NewsArticleEvent",
    "PipelineConfig",
    "PipelineEventResult",
    "PublicationTimeQuality",
    "SourceAvailability",
]
