"""MC7 impact components — novelty, materiality, and credibility evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..contracts.market_context import (
    ContextQualityFlag,
    CorroborationState,
    CredibilityEvidence,
    InformationEvent,
    MaterialityEvidence,
    NoveltyEvidence,
    PublicationState,
    SynthesisEnrichmentMetadata,
    synthesis_enrichment_to_dict,
)
from ..cross_lane.evidence import (
    EvidenceProvenanceClass,
    EvidenceSignal,
    LaneId,
    NormalizedLaneEvidence,
    lane_evidence_to_dict,
)
from ..normalization.equity_bars import iso_to_epoch_ns
from .entity_resolution import ContextDocumentRecord

PRODUCER_VERSION = "market_context_impact_components_v1"
SCORING_METHOD = "impact_components_v1"

NOVELTY_HIGH_THRESHOLD = 0.65
MATERIALITY_HIGH_THRESHOLD = 0.70
CREDIBILITY_HIGH_THRESHOLD = 0.75

_EVENT_TYPE_MATERIALITY_BASE: dict[str, float] = {
    "fda_clearance": 0.85,
    "earnings_beat": 0.75,
    "offering_risk": 0.70,
    "analyst_upgrade": 0.45,
    "macro_headwind": 0.35,
}

_METRIC_MATERIALITY_BOOST: dict[str, float] = {
    "revenue": 0.15,
    "margin": 0.10,
    "price_target": 0.05,
}


@dataclass(frozen=True, slots=True)
class ImpactComponentSummary:
    """Workspace-friendly rollup per information event."""

    event_id: str
    canonical_event_type: str
    entity_id: str | None
    novelty_score: float | None
    duplicate_probability: float | None
    incremental_information_score: float | None
    materiality_score: float | None
    materiality_basis: str | None
    source_credibility: float | None
    corroboration_state: str
    official_source_found: bool
    surprise_score: float | None
    event_time: str
    available_time: str
    publication_state: str
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    impact_available: bool = False
    synthesis_enrichment: SynthesisEnrichmentMetadata | None = None


def _event_records(
    event: InformationEvent,
    records_by_document_id: dict[str, ContextDocumentRecord],
) -> list[ContextDocumentRecord]:
    return [
        records_by_document_id[document_id]
        for document_id in event.document_ids
        if document_id in records_by_document_id
    ]


def _document_credibility(record: ContextDocumentRecord) -> float:
    source = record.document.source
    tier = (source.source_tier or "").lower()
    if source.official and source.first_party:
        if tier in {"company", "regulatory"}:
            return 0.95
        return 0.90
    if source.official:
        return 0.88
    if tier == "regulatory":
        return 0.90
    if tier == "company":
        return 0.85
    if tier == "wire":
        return 0.65
    if tier == "analyst":
        return 0.55
    if tier in {"media", "industry"}:
        return 0.45
    return 0.40


def _corroboration_bonus(state: CorroborationState) -> float:
    if state == CorroborationState.CORROBORATED:
        return 0.05
    if state == CorroborationState.PARTIALLY_CORROBORATED:
        return 0.02
    return 0.0


def compute_novelty_evidence(
    event: InformationEvent,
    records: list[ContextDocumentRecord],
) -> NoveltyEvidence:
    quality_flags = list(event.quality_flags)
    document_count = event.document_count or len(records)
    independent_count = event.independent_source_count or 0

    syndicated_count = sum(
        1 for record in records if record.document.source.syndication_parent_id
    )
    duplicate_probability: float | None = None
    incremental_information_score: float | None = None
    novelty_score: float | None = None

    if document_count > 0:
        duplicate_probability = round(syndicated_count / document_count, 6)
        incremental_information_score = round(independent_count / document_count, 6)
        novelty_score = round(max(0.0, 1.0 - duplicate_probability), 6)

    if ContextQualityFlag.EVENT_CLUSTER_UNCERTAIN.value in quality_flags:
        quality_flags.append(ContextQualityFlag.NOVELTY_UNCERTAIN.value)

    publication_state = (
        PublicationState.UNAVAILABLE
        if ContextQualityFlag.NOVELTY_UNCERTAIN.value in quality_flags and novelty_score is None
        else PublicationState.PUBLISHED
    )

    return NoveltyEvidence(
        event_id=event.event_id,
        novelty_score=novelty_score,
        duplicate_probability=duplicate_probability,
        incremental_information_score=incremental_information_score,
        event_time=event.event_time,
        available_time=event.available_time,
        publication_state=publication_state,
        provenance_ref=event.provenance_ref or event.event_id,
        quality_flags=tuple(dict.fromkeys(quality_flags)),
    )


def compute_materiality_evidence(
    event: InformationEvent,
) -> MaterialityEvidence:
    quality_flags = list(event.quality_flags)
    base = _EVENT_TYPE_MATERIALITY_BASE.get(event.canonical_event_type, 0.30)
    score = base
    basis_parts = [f"event_type:{event.canonical_event_type}"]

    for metric in event.extracted_metrics:
        boost = _METRIC_MATERIALITY_BOOST.get(metric.metric_name)
        if boost is None:
            continue
        score += boost
        value = str(metric.reported_value) if metric.reported_value is not None else "unknown"
        units = metric.units or ""
        basis_parts.append(f"metric:{metric.metric_name}={value}{units}")

    score = round(min(score, 1.0), 6)
    if base < 0.40 and not event.extracted_metrics:
        quality_flags.append(ContextQualityFlag.MATERIALITY_UNKNOWN.value)

    entity_id = event.entity_ids[0] if event.entity_ids else None
    publication_state = (
        PublicationState.UNAVAILABLE
        if ContextQualityFlag.MATERIALITY_UNKNOWN.value in quality_flags and not event.extracted_metrics
        else PublicationState.PUBLISHED
    )

    return MaterialityEvidence(
        event_id=event.event_id,
        entity_id=entity_id,
        materiality_score=score,
        materiality_basis="+".join(basis_parts),
        event_time=event.event_time,
        available_time=event.available_time,
        publication_state=publication_state,
        provenance_ref=event.provenance_ref or event.event_id,
        quality_flags=tuple(dict.fromkeys(quality_flags)),
    )


def compute_credibility_evidence(
    event: InformationEvent,
    records: list[ContextDocumentRecord],
) -> CredibilityEvidence:
    quality_flags = list(event.quality_flags)
    doc_scores = [_document_credibility(record) for record in records]
    base_score = max(doc_scores) if doc_scores else None
    official_source_found = any(record.document.source.official for record in records)

    source_credibility: float | None = None
    if base_score is not None:
        source_credibility = round(
            min(1.0, base_score + _corroboration_bonus(event.corroboration_state)),
            6,
        )

    if (
        event.corroboration_state == CorroborationState.UNVERIFIED
        and not official_source_found
        and (source_credibility is None or source_credibility < 0.60)
    ):
        quality_flags.append(ContextQualityFlag.SOURCE_LOW_CREDIBILITY.value)

    if event.corroboration_state in {
        CorroborationState.UNVERIFIED,
        CorroborationState.PARTIALLY_CORROBORATED,
    }:
        quality_flags.append(ContextQualityFlag.CORROBORATION_INCOMPLETE.value)

    return CredibilityEvidence(
        event_id=event.event_id,
        source_credibility=source_credibility,
        historical_signal_value=None,
        corroboration_state=event.corroboration_state,
        official_source_found=official_source_found,
        official_confirmation=False,
        official_denial=False,
        independent_source_count=event.independent_source_count,
        event_time=event.event_time,
        available_time=event.available_time,
        publication_state=PublicationState.PUBLISHED,
        provenance_ref=event.provenance_ref or event.event_id,
        quality_flags=tuple(dict.fromkeys(quality_flags)),
    )


def _surprise_score_by_event_id(
    surprise_summaries: list[Any] | None,
) -> dict[str, float]:
    scores: dict[str, float] = {}
    if not surprise_summaries:
        return scores
    for item in surprise_summaries:
        event_id = getattr(item, "event_id", None)
        if not event_id or not getattr(item, "surprise_available", False):
            continue
        standardized = getattr(item, "standardized_surprise", None)
        if standardized is None:
            continue
        try:
            scores[str(event_id)] = round(abs(float(standardized)), 6)
        except (TypeError, ValueError):
            continue
    return scores


def build_fixture_impact_pipeline(
    records: list[ContextDocumentRecord],
    enriched_events: list[InformationEvent],
    *,
    prediction_cutoff: int,
    surprise_summaries: list[Any] | None = None,
) -> tuple[
    list[NoveltyEvidence],
    list[MaterialityEvidence],
    list[CredibilityEvidence],
    list[ImpactComponentSummary],
]:
    records_by_id = {record.document.document_id: record for record in records}
    surprise_by_event = _surprise_score_by_event_id(surprise_summaries)

    novelty_rows: list[NoveltyEvidence] = []
    materiality_rows: list[MaterialityEvidence] = []
    credibility_rows: list[CredibilityEvidence] = []
    summaries: list[ImpactComponentSummary] = []

    for event in enriched_events:
        if iso_to_epoch_ns(event.available_time) > prediction_cutoff:
            continue

        member_records = _event_records(event, records_by_id)
        if not member_records:
            continue

        novelty = compute_novelty_evidence(event, member_records)
        materiality = compute_materiality_evidence(event)
        credibility = compute_credibility_evidence(event, member_records)

        novelty_rows.append(novelty)
        materiality_rows.append(materiality)
        credibility_rows.append(credibility)

        entity_id = event.entity_ids[0] if event.entity_ids else None
        summaries.append(
            ImpactComponentSummary(
                event_id=event.event_id,
                canonical_event_type=event.canonical_event_type,
                entity_id=entity_id,
                novelty_score=novelty.novelty_score,
                duplicate_probability=novelty.duplicate_probability,
                incremental_information_score=novelty.incremental_information_score,
                materiality_score=materiality.materiality_score,
                materiality_basis=materiality.materiality_basis,
                source_credibility=credibility.source_credibility,
                corroboration_state=credibility.corroboration_state.value,
                official_source_found=credibility.official_source_found,
                surprise_score=surprise_by_event.get(event.event_id),
                event_time=event.event_time,
                available_time=event.available_time,
                publication_state=novelty.publication_state.value,
                quality_flags=tuple(
                    dict.fromkeys(
                        novelty.quality_flags
                        + materiality.quality_flags
                        + credibility.quality_flags
                    )
                ),
                impact_available=True,
            )
        )

    return novelty_rows, materiality_rows, credibility_rows, summaries


def impact_component_summary_to_dict(item: ImpactComponentSummary) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "event_id": item.event_id,
        "canonical_event_type": item.canonical_event_type,
        "entity_id": item.entity_id,
        "novelty_score": item.novelty_score,
        "duplicate_probability": item.duplicate_probability,
        "incremental_information_score": item.incremental_information_score,
        "materiality_score": item.materiality_score,
        "materiality_basis": item.materiality_basis,
        "source_credibility": item.source_credibility,
        "corroboration_state": item.corroboration_state,
        "official_source_found": item.official_source_found,
        "surprise_score": item.surprise_score,
        "event_time": item.event_time,
        "available_time": item.available_time,
        "publication_state": item.publication_state,
        "quality_flags": list(item.quality_flags),
        "impact_available": item.impact_available,
    }
    if item.synthesis_enrichment is not None:
        payload["synthesis_enrichment"] = synthesis_enrichment_to_dict(
            item.synthesis_enrichment
        )
    return payload


def _component_strength(score: float | None, threshold: float) -> str:
    if score is None:
        return "LOW"
    if score >= threshold + 0.15:
        return "HIGH"
    if score >= threshold:
        return "MODERATE"
    return "LOW"


def build_impact_cross_lane_evidence(
    summaries: list[ImpactComponentSummary],
    *,
    symbol: str,
    prediction_cutoff: int,
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for item in summaries:
        if iso_to_epoch_ns(item.available_time) > prediction_cutoff:
            continue
        if not item.impact_available:
            continue

        component_signals: list[tuple[EvidenceSignal, float | None, float]] = []
        if item.novelty_score is not None and item.novelty_score >= NOVELTY_HIGH_THRESHOLD:
            component_signals.append(
                (EvidenceSignal.NOVELTY_HIGH, item.novelty_score, NOVELTY_HIGH_THRESHOLD)
            )
        if (
            item.materiality_score is not None
            and item.materiality_score >= MATERIALITY_HIGH_THRESHOLD
        ):
            component_signals.append(
                (
                    EvidenceSignal.MATERIALITY_HIGH,
                    item.materiality_score,
                    MATERIALITY_HIGH_THRESHOLD,
                )
            )
        if (
            item.source_credibility is not None
            and item.source_credibility >= CREDIBILITY_HIGH_THRESHOLD
        ):
            component_signals.append(
                (
                    EvidenceSignal.CREDIBILITY_HIGH,
                    item.source_credibility,
                    CREDIBILITY_HIGH_THRESHOLD,
                )
            )

        for signal, score, threshold in component_signals:
            row = lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.MARKET_CONTEXT,
                    signal=signal,
                    strength=_component_strength(score, threshold),
                    available=True,
                    source_ref=item.event_id,
                    detail=(
                        f"MC7 impact component on {item.canonical_event_type} "
                        f"(display-only, not trade signal)"
                    ),
                    observed_at=item.available_time,
                    quality_flags=item.quality_flags,
                    provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
                )
            )
            row["metadata"] = {
                "symbol": symbol,
                "event_id": item.event_id,
                "canonical_event_type": item.canonical_event_type,
                "novelty_score": item.novelty_score,
                "duplicate_probability": item.duplicate_probability,
                "incremental_information_score": item.incremental_information_score,
                "materiality_score": item.materiality_score,
                "materiality_basis": item.materiality_basis,
                "source_credibility": item.source_credibility,
                "corroboration_state": item.corroboration_state,
                "official_source_found": item.official_source_found,
                "surprise_score": item.surprise_score,
                "scoring_method": SCORING_METHOD,
            }
            evidence.append(row)

    return evidence


__all__ = [
    "CREDIBILITY_HIGH_THRESHOLD",
    "ImpactComponentSummary",
    "MATERIALITY_HIGH_THRESHOLD",
    "NOVELTY_HIGH_THRESHOLD",
    "PRODUCER_VERSION",
    "SCORING_METHOD",
    "build_fixture_impact_pipeline",
    "build_impact_cross_lane_evidence",
    "compute_credibility_evidence",
    "compute_materiality_evidence",
    "compute_novelty_evidence",
    "impact_component_summary_to_dict",
]
