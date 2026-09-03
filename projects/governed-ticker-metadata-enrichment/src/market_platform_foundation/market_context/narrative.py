"""MC10 narrative intelligence — experimental theme clustering and thesis graph."""

from __future__ import annotations

import statistics
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from ..contracts.market_context import (
    ContextQualityFlag,
    NarrativeEvidence,
    PublicationState,
    SemanticSentimentLabel,
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
from .sentiment import EventSentimentSummary

PRODUCER_VERSION = "market_context_narrative_v1"
SCORING_METHOD = "narrative_clustering_v1"

NARRATIVE_VELOCITY_THRESHOLD = 0.10
NARRATIVE_ACCELERATION_THRESHOLD = 0.05

_THEME_BY_LEAN: dict[str, tuple[str, str]] = {
    "BULLISH": (
        "bullish_growth_narrative",
        "Bullish growth catalyst cluster",
    ),
    "BEARISH": (
        "bearish_risk_narrative",
        "Bearish risk narrative cluster",
    ),
}

_SENTIMENT_SCORES: dict[SemanticSentimentLabel, float] = {
    SemanticSentimentLabel.POSITIVE: 1.0,
    SemanticSentimentLabel.NEGATIVE: -1.0,
    SemanticSentimentLabel.MIXED: 0.0,
}


@dataclass(frozen=True, slots=True)
class NarrativeSummary:
    narrative_id: str
    narrative_text: str
    entity_id: str
    thesis_lean: str
    triggering_event_id: str
    supporting_event_ids: tuple[str, ...]
    opposing_event_ids: tuple[str, ...]
    prevalence: float | None
    velocity: float | None
    acceleration: float | None
    sentiment_dispersion: float | None
    narrative_dispersion: float | None
    event_time: str
    available_time: str
    publication_state: str
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    narrative_available: bool = False


def _sentiment_score(summary: EventSentimentSummary | None) -> float | None:
    if summary is None:
        return None
    source = summary.finbert or summary.keyword
    if source is None:
        return None
    return _SENTIMENT_SCORES.get(source.label)


def compute_narrative_dispersion(event_types: list[str]) -> float | None:
    if not event_types:
        return None
    if len(event_types) == 1:
        return 0.0
    counts = Counter(event_types)
    max_count = max(counts.values())
    return round(1.0 - (max_count / len(event_types)), 6)


def compute_sentiment_dispersion(scores: list[float]) -> float | None:
    if len(scores) < 2:
        return None
    return round(statistics.pstdev(scores), 6)


def build_narrative_evidence(summary: NarrativeSummary) -> NarrativeEvidence:
    publication = (
        PublicationState.PUBLISHED
        if summary.prevalence is not None
        else PublicationState.UNAVAILABLE
    )
    return NarrativeEvidence(
        narrative_id=summary.narrative_id,
        narrative_text=summary.narrative_text,
        entity_ids=(summary.entity_id,),
        prevalence=summary.prevalence,
        velocity=summary.velocity,
        acceleration=summary.acceleration,
        sentiment_dispersion=summary.sentiment_dispersion,
        narrative_dispersion=summary.narrative_dispersion,
        event_time=summary.event_time,
        available_time=summary.available_time,
        publication_state=publication,
        provenance_ref=f"{PRODUCER_VERSION}:{SCORING_METHOD}",
        quality_flags=summary.quality_flags,
    )


def build_fixture_narrative_pipeline(
    catalyst_summaries: list[CatalystSummary],
    event_sentiment_summaries: list[EventSentimentSummary],
    *,
    prediction_cutoff: int,
    entity_id: str,
) -> tuple[
    list[NarrativeEvidence],
    list[NarrativeSummary],
    list[dict[str, Any]],
]:
    sentiment_by_event = {item.event_id: item for item in event_sentiment_summaries}
    gated = [
        item
        for item in catalyst_summaries
        if item.gate_ok
        and iso_to_epoch_ns(item.available_time) <= prediction_cutoff
        and item.lean in _THEME_BY_LEAN
    ]
    gated = sorted(gated, key=lambda item: (item.available_time, item.event_id))

    theme_events: dict[str, list[CatalystSummary]] = {
        "bullish_growth_narrative": [],
        "bearish_risk_narrative": [],
    }
    bullish_ids: list[str] = []
    bearish_ids: list[str] = []
    prevalence_history: dict[str, list[float]] = {
        "bullish_growth_narrative": [],
        "bearish_risk_narrative": [],
    }
    velocity_history: dict[str, list[float | None]] = {
        "bullish_growth_narrative": [],
        "bearish_risk_narrative": [],
    }

    evidence_rows: list[NarrativeEvidence] = []
    summary_rows: list[NarrativeSummary] = []
    adapter_rows: list[dict[str, Any]] = []
    total_gated = 0

    for catalyst in gated:
        total_gated += 1
        narrative_id, narrative_text = _THEME_BY_LEAN[catalyst.lean]
        theme_events[narrative_id].append(catalyst)
        if catalyst.lean == "BULLISH":
            bullish_ids.append(catalyst.event_id)
        else:
            bearish_ids.append(catalyst.event_id)

        prevalence = round(len(theme_events[narrative_id]) / total_gated, 6)
        history = prevalence_history[narrative_id]
        velocity: float | None = None
        acceleration: float | None = None
        quality_flags: list[str] = []

        if len(history) >= 1:
            velocity = round(prevalence - history[-1], 6)
        else:
            quality_flags.append(ContextQualityFlag.NARRATIVE_HISTORY_INSUFFICIENT.value)

        vel_history = velocity_history[narrative_id]
        if len(vel_history) >= 1 and velocity is not None:
            prior_velocity = vel_history[-1]
            if prior_velocity is not None:
                acceleration = round(velocity - prior_velocity, 6)
        elif len(history) < 2:
            quality_flags.append(ContextQualityFlag.NARRATIVE_HISTORY_INSUFFICIENT.value)

        theme_list = theme_events[narrative_id]
        event_types = [item.canonical_event_type for item in theme_list]
        narrative_dispersion = compute_narrative_dispersion(event_types)

        sentiment_scores = [
            score
            for item in theme_list
            if (score := _sentiment_score(sentiment_by_event.get(item.event_id))) is not None
        ]
        sentiment_dispersion = compute_sentiment_dispersion(sentiment_scores)
        if sentiment_dispersion is None:
            quality_flags.append(ContextQualityFlag.NARRATIVE_DATA_PARTIAL.value)

        supporting_ids = tuple(item.event_id for item in theme_list)
        opposing_ids = tuple(bearish_ids if catalyst.lean == "BULLISH" else bullish_ids)

        summary = NarrativeSummary(
            narrative_id=narrative_id,
            narrative_text=narrative_text,
            entity_id=entity_id,
            thesis_lean=catalyst.lean,
            triggering_event_id=catalyst.event_id,
            supporting_event_ids=supporting_ids,
            opposing_event_ids=opposing_ids,
            prevalence=prevalence,
            velocity=velocity,
            acceleration=acceleration,
            sentiment_dispersion=sentiment_dispersion,
            narrative_dispersion=narrative_dispersion,
            event_time=catalyst.event_time,
            available_time=catalyst.available_time,
            publication_state=PublicationState.PUBLISHED.value,
            quality_flags=tuple(dict.fromkeys(quality_flags)),
            narrative_available=True,
        )
        evidence = build_narrative_evidence(summary)
        evidence_rows.append(evidence)
        summary_rows.append(summary)
        adapter_rows.append(narrative_summary_to_adapter_row(summary))

        history.append(prevalence)
        vel_history.append(velocity)

    return evidence_rows, summary_rows, adapter_rows


def narrative_summary_to_dict(item: NarrativeSummary) -> dict[str, Any]:
    return {
        "narrative_id": item.narrative_id,
        "narrative_text": item.narrative_text,
        "entity_id": item.entity_id,
        "thesis_lean": item.thesis_lean,
        "triggering_event_id": item.triggering_event_id,
        "supporting_event_ids": list(item.supporting_event_ids),
        "opposing_event_ids": list(item.opposing_event_ids),
        "prevalence": item.prevalence,
        "velocity": item.velocity,
        "acceleration": item.acceleration,
        "sentiment_dispersion": item.sentiment_dispersion,
        "narrative_dispersion": item.narrative_dispersion,
        "event_time": item.event_time,
        "available_time": item.available_time,
        "publication_state": item.publication_state,
        "quality_flags": list(item.quality_flags),
        "narrative_available": item.narrative_available,
        "scoring_method": SCORING_METHOD,
    }


def narrative_summary_to_adapter_row(item: NarrativeSummary) -> dict[str, Any]:
    return {
        "narrative_id": item.narrative_id,
        "entity_id": item.entity_id,
        "thesis_lean": item.thesis_lean,
        "triggering_event_id": item.triggering_event_id,
        "prevalence": item.prevalence,
        "velocity": item.velocity,
        "acceleration": item.acceleration,
        "sentiment_dispersion": item.sentiment_dispersion,
        "narrative_dispersion": item.narrative_dispersion,
        "event_time": item.event_time,
        "available_time": item.available_time,
        "scoring_method": SCORING_METHOD,
    }


def build_narrative_cross_lane_evidence(
    summaries: list[NarrativeSummary],
    *,
    symbol: str,
    prediction_cutoff: int,
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for item in summaries:
        if iso_to_epoch_ns(item.available_time) > prediction_cutoff:
            continue
        velocity_hit = (
            item.velocity is not None and abs(item.velocity) >= NARRATIVE_VELOCITY_THRESHOLD
        )
        acceleration_hit = (
            item.acceleration is not None
            and abs(item.acceleration) >= NARRATIVE_ACCELERATION_THRESHOLD
        )
        if not velocity_hit and not acceleration_hit:
            continue
        row = lane_evidence_to_dict(
            NormalizedLaneEvidence(
                lane=LaneId.MARKET_CONTEXT,
                signal=EvidenceSignal.NARRATIVE_SHIFT,
                strength="MODERATE"
                if (item.velocity or 0) < 0.20 and (item.acceleration or 0) < 0.10
                else "HIGH",
                available=True,
                source_ref=item.triggering_event_id,
                detail=(
                    f"MC10 narrative shift on {item.narrative_id} "
                    f"(experimental, not trade signal)"
                ),
                observed_at=item.available_time,
                quality_flags=item.quality_flags,
                provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
            )
        )
        row["metadata"] = {
            "symbol": symbol,
            "narrative_id": item.narrative_id,
            "thesis_lean": item.thesis_lean,
            "velocity": item.velocity,
            "acceleration": item.acceleration,
            "prevalence": item.prevalence,
            "scoring_method": SCORING_METHOD,
            "experimental": True,
        }
        evidence.append(row)
    return evidence


__all__ = [
    "NARRATIVE_ACCELERATION_THRESHOLD",
    "NARRATIVE_VELOCITY_THRESHOLD",
    "NarrativeSummary",
    "PRODUCER_VERSION",
    "SCORING_METHOD",
    "build_fixture_narrative_pipeline",
    "build_narrative_cross_lane_evidence",
    "build_narrative_evidence",
    "compute_narrative_dispersion",
    "compute_sentiment_dispersion",
    "narrative_summary_to_adapter_row",
    "narrative_summary_to_dict",
]
