"""MC9 attention diffusion — separate information value from reflexive impact."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any

from ..contracts.market_context import (
    AttentionEvidence,
    ContextQualityFlag,
    CorroborationState,
    InformationEvent,
    PublicationState,
    entity_id_from_symbol,
)
from ..cross_lane.evidence import (
    EvidenceProvenanceClass,
    EvidenceSignal,
    LaneId,
    NormalizedLaneEvidence,
    lane_evidence_to_dict,
)
from ..normalization.equity_bars import iso_to_epoch_ns
from .catalyst import CatalystSummary

PRODUCER_VERSION = "market_context_attention_v1"
SCORING_METHOD = "attention_diffusion_v1"

ATTENTION_ACCELERATION_THRESHOLD = 0.05
DIFFUSION_ELEVATED_THRESHOLD = 0.60

_CORROBORATION_SCORES: dict[CorroborationState, float] = {
    CorroborationState.UNVERIFIED: 0.25,
    CorroborationState.PARTIALLY_CORROBORATED: 0.60,
    CorroborationState.CORROBORATED: 1.0,
    CorroborationState.CONFIRMED: 1.0,
    CorroborationState.DENIED: 0.0,
    CorroborationState.RETRACTED: 0.0,
}

_INFORMATION_VALUE_WEIGHTS: dict[str, float] = {
    "catalyst": 0.50,
    "credibility": 0.30,
    "novelty": 0.20,
}


@dataclass(frozen=True, slots=True)
class AttentionSummary:
    event_id: str
    entity_id: str
    canonical_event_type: str
    attention_level: float | None
    attention_velocity: float | None
    attention_acceleration: float | None
    attention_zscore: float | None
    attention_percentile: float | None
    information_value: float | None
    reflexive_impact: float | None
    diffusion_score: float | None
    independent_source_growth: int | None
    corroboration_improving: bool
    event_time: str
    available_time: str
    publication_state: str
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    attention_available: bool = False
    headline: str = ""


def _corroboration_score(state: CorroborationState) -> float:
    return _CORROBORATION_SCORES.get(state, 0.25)


def compute_cluster_attention_level(event: InformationEvent) -> float:
    doc_norm = min(1.0, event.document_count / 4.0)
    source_norm = min(1.0, (event.independent_source_count or 0) / 3.0)
    corr_score = _corroboration_score(event.corroboration_state)
    return round(min(1.0, 0.4 * doc_norm + 0.3 * source_norm + 0.3 * corr_score), 6)


def compute_information_value(catalyst: CatalystSummary | None) -> float | None:
    if catalyst is None:
        return None
    components: dict[str, float] = {}
    weights: dict[str, float] = {}
    if catalyst.catalyst_strength is not None:
        components["catalyst"] = float(catalyst.catalyst_strength)
        weights["catalyst"] = _INFORMATION_VALUE_WEIGHTS["catalyst"]
    if catalyst.credibility_score is not None:
        components["credibility"] = float(catalyst.credibility_score)
        weights["credibility"] = _INFORMATION_VALUE_WEIGHTS["credibility"]
    if catalyst.novelty_score is not None:
        components["novelty"] = float(catalyst.novelty_score)
        weights["novelty"] = _INFORMATION_VALUE_WEIGHTS["novelty"]
    if not components:
        return None
    total_weight = sum(weights[key] for key in components)
    if total_weight <= 0:
        return None
    value = sum(components[key] * weights[key] for key in components) / total_weight
    return round(min(1.0, value), 6)


def compute_diffusion_score(
    event: InformationEvent,
    previous: InformationEvent | None,
) -> tuple[float | None, int | None, bool]:
    arrival_rate = min(1.0, event.document_count / 2.0)
    source_growth = 0.0
    growth_count: int | None = None
    if previous is not None:
        prev_sources = previous.independent_source_count or 0
        curr_sources = event.independent_source_count or 0
        growth_count = curr_sources - prev_sources
        source_growth = min(1.0, max(0.0, growth_count / 2.0))
    prev_score = _corroboration_score(previous.corroboration_state) if previous else 0.0
    curr_score = _corroboration_score(event.corroboration_state)
    corroboration_improving = curr_score > prev_score
    corroboration_delta = min(1.0, max(0.0, curr_score - prev_score)) if corroboration_improving else 0.0
    if previous is None:
        return round(min(1.0, 0.4 * arrival_rate), 6), growth_count, corroboration_improving
    score = min(1.0, 0.4 * arrival_rate + 0.3 * source_growth + 0.3 * corroboration_delta)
    return round(score, 6), growth_count, corroboration_improving


def _history_stats(
    levels: list[float],
    current: float,
) -> tuple[float | None, float | None]:
    if len(levels) < 2:
        return None, None
    history = levels + [current]
    mean = statistics.fmean(history)
    try:
        stdev = statistics.pstdev(history)
    except statistics.StatisticsError:
        stdev = 0.0
    zscore = round((current - mean) / stdev, 6) if stdev > 0 else 0.0
    sorted_history = sorted(history)
    rank = sorted_history.index(current) + 1
    percentile = round(rank / len(sorted_history), 6)
    return zscore, percentile


def build_attention_evidence(
    summary: AttentionSummary,
) -> AttentionEvidence:
    publication = (
        PublicationState.PUBLISHED
        if summary.attention_level is not None
        else PublicationState.UNAVAILABLE
    )
    return AttentionEvidence(
        entity_id=summary.entity_id,
        attention_level=summary.attention_level,
        attention_velocity=summary.attention_velocity,
        attention_acceleration=summary.attention_acceleration,
        attention_zscore=summary.attention_zscore,
        attention_percentile=summary.attention_percentile,
        information_value=summary.information_value,
        reflexive_impact=summary.reflexive_impact,
        event_time=summary.event_time,
        available_time=summary.available_time,
        publication_state=publication,
        provenance_ref=f"{PRODUCER_VERSION}:{SCORING_METHOD}",
        quality_flags=summary.quality_flags,
    )


def _entity_events(
    events: list[InformationEvent],
    *,
    entity_id: str,
    prediction_cutoff: int,
) -> list[InformationEvent]:
    resolved_ids = {entity_id, entity_id_from_symbol(entity_id)}
    visible: list[InformationEvent] = []
    for event in events:
        if iso_to_epoch_ns(event.available_time) > prediction_cutoff:
            continue
        if event.entity_ids and not resolved_ids.intersection(event.entity_ids):
            continue
        visible.append(event)
    return sorted(visible, key=lambda item: (item.available_time, item.event_id))


def build_fixture_attention_pipeline(
    enriched_events: list[InformationEvent],
    catalyst_summaries: list[CatalystSummary],
    *,
    prediction_cutoff: int,
    entity_id: str,
    headlines_by_event: dict[str, str] | None = None,
) -> tuple[
    list[AttentionEvidence],
    list[AttentionSummary],
    list[dict[str, Any]],
]:
    headlines = headlines_by_event or {}
    catalyst_by_event = {item.event_id: item for item in catalyst_summaries}
    entity_events = _entity_events(
        enriched_events,
        entity_id=entity_id,
        prediction_cutoff=prediction_cutoff,
    )

    evidence_rows: list[AttentionEvidence] = []
    summary_rows: list[AttentionSummary] = []
    adapter_rows: list[dict[str, Any]] = []

    level_history: list[float] = []
    velocity_history: list[float | None] = []
    previous_event: InformationEvent | None = None

    for event in entity_events:
        catalyst = catalyst_by_event.get(event.event_id)
        level = compute_cluster_attention_level(event)
        diffusion_score, source_growth, corroboration_improving = compute_diffusion_score(
            event,
            previous_event,
        )
        information_value = compute_information_value(catalyst)

        quality_flags: list[str] = [
            ContextQualityFlag.SOCIAL_ATTENTION_UNAVAILABLE.value,
        ]
        if information_value is None:
            quality_flags.append(ContextQualityFlag.ATTENTION_DATA_PARTIAL.value)

        velocity: float | None = None
        acceleration: float | None = None
        if len(level_history) >= 1:
            velocity = round(level - level_history[-1], 6)
        else:
            quality_flags.append(ContextQualityFlag.ATTENTION_HISTORY_INSUFFICIENT.value)

        if len(velocity_history) >= 1 and velocity is not None:
            prior_velocity = velocity_history[-1]
            if prior_velocity is not None:
                acceleration = round(velocity - prior_velocity, 6)
        elif len(level_history) < 2:
            quality_flags.append(ContextQualityFlag.ATTENTION_HISTORY_INSUFFICIENT.value)

        zscore, percentile = _history_stats(level_history, level)

        reflexive_impact: float | None = None
        if velocity is not None and information_value is not None:
            reflexive_impact = round(min(1.0, velocity * (1.0 - information_value)), 6)

        headline = headlines.get(
            event.event_id,
            catalyst.headline if catalyst else event.canonical_event_type.replace("_", " "),
        )
        summary = AttentionSummary(
            event_id=event.event_id,
            entity_id=entity_id,
            canonical_event_type=event.canonical_event_type,
            attention_level=level,
            attention_velocity=velocity,
            attention_acceleration=acceleration,
            attention_zscore=zscore,
            attention_percentile=percentile,
            information_value=information_value,
            reflexive_impact=reflexive_impact,
            diffusion_score=diffusion_score,
            independent_source_growth=source_growth,
            corroboration_improving=corroboration_improving,
            event_time=event.event_time,
            available_time=event.available_time,
            publication_state=PublicationState.PUBLISHED.value,
            quality_flags=tuple(dict.fromkeys(quality_flags)),
            attention_available=True,
            headline=headline,
        )
        evidence = build_attention_evidence(summary)
        evidence_rows.append(evidence)
        summary_rows.append(summary)
        adapter_rows.append(attention_summary_to_adapter_row(summary))

        level_history.append(level)
        velocity_history.append(velocity)
        previous_event = event

    return evidence_rows, summary_rows, adapter_rows


def attention_summary_to_dict(item: AttentionSummary) -> dict[str, Any]:
    return {
        "event_id": item.event_id,
        "entity_id": item.entity_id,
        "canonical_event_type": item.canonical_event_type,
        "attention_level": item.attention_level,
        "attention_velocity": item.attention_velocity,
        "attention_acceleration": item.attention_acceleration,
        "attention_zscore": item.attention_zscore,
        "attention_percentile": item.attention_percentile,
        "information_value": item.information_value,
        "reflexive_impact": item.reflexive_impact,
        "diffusion_score": item.diffusion_score,
        "independent_source_growth": item.independent_source_growth,
        "corroboration_improving": item.corroboration_improving,
        "event_time": item.event_time,
        "available_time": item.available_time,
        "publication_state": item.publication_state,
        "quality_flags": list(item.quality_flags),
        "attention_available": item.attention_available,
        "headline": item.headline,
        "scoring_method": SCORING_METHOD,
    }


def attention_summary_to_adapter_row(item: AttentionSummary) -> dict[str, Any]:
    return {
        "event_id": item.event_id,
        "entity_id": item.entity_id,
        "canonical_event_type": item.canonical_event_type,
        "attention_level": item.attention_level,
        "attention_velocity": item.attention_velocity,
        "attention_acceleration": item.attention_acceleration,
        "information_value": item.information_value,
        "reflexive_impact": item.reflexive_impact,
        "diffusion_score": item.diffusion_score,
        "corroboration_improving": item.corroboration_improving,
        "event_time": item.event_time,
        "available_time": item.available_time,
        "headline": item.headline,
        "scoring_method": SCORING_METHOD,
    }


def build_attention_cross_lane_evidence(
    summaries: list[AttentionSummary],
    *,
    symbol: str,
    prediction_cutoff: int,
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for item in summaries:
        if iso_to_epoch_ns(item.available_time) > prediction_cutoff:
            continue
        if (
            item.attention_acceleration is not None
            and item.attention_acceleration >= ATTENTION_ACCELERATION_THRESHOLD
        ):
            row = lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.MARKET_CONTEXT,
                    signal=EvidenceSignal.ATTENTION_ACCELERATION,
                    strength="MODERATE" if item.attention_acceleration < 0.15 else "HIGH",
                    available=True,
                    source_ref=item.event_id,
                    detail=(
                        f"MC9 attention acceleration {item.attention_acceleration:.4f} "
                        f"on {item.canonical_event_type}"
                    ),
                    observed_at=item.available_time,
                    quality_flags=item.quality_flags,
                    provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
                )
            )
            row["metadata"] = {
                "symbol": symbol,
                "event_id": item.event_id,
                "attention_acceleration": item.attention_acceleration,
                "attention_velocity": item.attention_velocity,
                "information_value": item.information_value,
                "reflexive_impact": item.reflexive_impact,
                "scoring_method": SCORING_METHOD,
            }
            evidence.append(row)

        if (
            item.diffusion_score is not None
            and item.diffusion_score >= DIFFUSION_ELEVATED_THRESHOLD
            and item.corroboration_improving
        ):
            row = lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.MARKET_CONTEXT,
                    signal=EvidenceSignal.INFORMATION_DIFFUSION_ELEVATED,
                    strength="MODERATE" if item.diffusion_score < 0.80 else "HIGH",
                    available=True,
                    source_ref=item.event_id,
                    detail=(
                        f"MC9 information diffusion elevated on {item.canonical_event_type} "
                        f"(corroboration improving)"
                    ),
                    observed_at=item.available_time,
                    quality_flags=item.quality_flags,
                    provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
                )
            )
            row["metadata"] = {
                "symbol": symbol,
                "event_id": item.event_id,
                "diffusion_score": item.diffusion_score,
                "independent_source_growth": item.independent_source_growth,
                "corroboration_improving": item.corroboration_improving,
                "scoring_method": SCORING_METHOD,
            }
            evidence.append(row)

    return evidence


__all__ = [
    "ATTENTION_ACCELERATION_THRESHOLD",
    "DIFFUSION_ELEVATED_THRESHOLD",
    "AttentionSummary",
    "PRODUCER_VERSION",
    "SCORING_METHOD",
    "attention_summary_to_adapter_row",
    "attention_summary_to_dict",
    "build_attention_cross_lane_evidence",
    "build_attention_evidence",
    "build_fixture_attention_pipeline",
    "compute_cluster_attention_level",
    "compute_diffusion_score",
    "compute_information_value",
]
