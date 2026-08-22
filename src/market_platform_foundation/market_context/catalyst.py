"""MC8 catalyst fusion and short-thesis invalidation evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..contracts.market_context import (
    CatalystEvidence,
    ContextQualityFlag,
    PublicationState,
    ShortThesisInvalidationEvidence,
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
from .impact_components import ImpactComponentSummary, SCORING_METHOD as IMPACT_SCORING_METHOD

PRODUCER_VERSION = "market_context_catalyst_v1"
SCORING_METHOD = "catalyst_fusion_v1"

CATALYST_GATE_THRESHOLD = 0.40
CATALYST_STRENGTH_THRESHOLD = 0.50
THESIS_INVALIDATION_THRESHOLD = 0.55
SURPRISE_BOOST_THRESHOLD = 0.65

_WEIGHTS_WITH_SURPRISE: dict[str, float] = {
    "materiality": 0.35,
    "credibility": 0.30,
    "novelty": 0.20,
    "surprise": 0.15,
}
_WEIGHTS_WITHOUT_SURPRISE: dict[str, float] = {
    "materiality": 0.40,
    "credibility": 0.35,
    "novelty": 0.25,
}

_BULLISH_EVENT_TYPES = frozenset({"earnings_beat", "fda_clearance", "analyst_upgrade"})
_BEARISH_EVENT_TYPES = frozenset({"offering_risk", "macro_headwind"})


@dataclass(frozen=True, slots=True)
class CatalystSummary:
    event_id: str
    canonical_event_type: str
    entity_ids: tuple[str, ...]
    catalyst_strength: float | None
    novelty_score: float | None
    surprise_score: float | None
    materiality_score: float | None
    credibility_score: float | None
    lean: str
    gate_ok: bool
    event_time: str
    available_time: str
    publication_state: str
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    catalyst_available: bool = False
    headline: str = ""
    synthesis_enrichment: SynthesisEnrichmentMetadata | None = None


def _event_lean(canonical_event_type: str) -> str:
    if canonical_event_type in _BULLISH_EVENT_TYPES:
        return "BULLISH"
    if canonical_event_type in _BEARISH_EVENT_TYPES:
        return "BEARISH"
    return "NEUTRAL"


def compute_catalyst_strength(
    *,
    novelty_score: float | None,
    materiality_score: float | None,
    credibility_score: float | None,
    surprise_score: float | None,
) -> tuple[float | None, tuple[str, ...]]:
    flags: list[str] = []
    if novelty_score is None or materiality_score is None or credibility_score is None:
        flags.append(ContextQualityFlag.CATALYST_COMPONENTS_INCOMPLETE.value)
        return None, tuple(flags)

    components: dict[str, float] = {
        "novelty": float(novelty_score),
        "materiality": float(materiality_score),
        "credibility": float(credibility_score),
    }
    weights = dict(_WEIGHTS_WITHOUT_SURPRISE)
    if surprise_score is not None:
        components["surprise"] = min(1.0, abs(float(surprise_score)))
        weights = dict(_WEIGHTS_WITH_SURPRISE)

    total_weight = sum(weights[key] for key in components)
    if total_weight <= 0:
        flags.append(ContextQualityFlag.CATALYST_COMPONENTS_INCOMPLETE.value)
        return None, tuple(flags)

    fused = sum(components[key] * weights[key] for key in components) / total_weight
    return round(min(1.0, fused), 6), tuple(flags)


def build_catalyst_evidence(
    summary: ImpactComponentSummary,
    *,
    entity_ids: tuple[str, ...] | None = None,
) -> CatalystEvidence:
    strength, flags = compute_catalyst_strength(
        novelty_score=summary.novelty_score,
        materiality_score=summary.materiality_score,
        credibility_score=summary.source_credibility,
        surprise_score=summary.surprise_score,
    )
    publication = (
        PublicationState.PUBLISHED
        if strength is not None
        else PublicationState.UNAVAILABLE
    )
    merged_flags = tuple(dict.fromkeys(tuple(summary.quality_flags) + flags))
    resolved_entity_ids = entity_ids or (
        (summary.entity_id,) if summary.entity_id else ()
    )
    return CatalystEvidence(
        event_id=summary.event_id,
        entity_ids=resolved_entity_ids,
        catalyst_strength=strength,
        novelty_score=summary.novelty_score,
        surprise_score=summary.surprise_score,
        materiality_score=summary.materiality_score,
        credibility_score=summary.source_credibility,
        event_time=summary.event_time,
        available_time=summary.available_time,
        publication_state=publication,
        provenance_ref=f"{PRODUCER_VERSION}:{IMPACT_SCORING_METHOD}",
        quality_flags=merged_flags,
    )


def build_catalyst_summary(
    evidence: CatalystEvidence,
    *,
    canonical_event_type: str,
    headline: str = "",
) -> CatalystSummary:
    lean = _event_lean(canonical_event_type)
    gate_ok = (
        evidence.catalyst_strength is not None
        and evidence.catalyst_strength >= CATALYST_GATE_THRESHOLD
    )
    return CatalystSummary(
        event_id=evidence.event_id,
        canonical_event_type=canonical_event_type,
        entity_ids=evidence.entity_ids,
        catalyst_strength=evidence.catalyst_strength,
        novelty_score=evidence.novelty_score,
        surprise_score=evidence.surprise_score,
        materiality_score=evidence.materiality_score,
        credibility_score=evidence.credibility_score,
        lean=lean,
        gate_ok=gate_ok,
        event_time=evidence.event_time,
        available_time=evidence.available_time,
        publication_state=evidence.publication_state.value,
        quality_flags=evidence.quality_flags,
        catalyst_available=evidence.catalyst_strength is not None,
        headline=headline,
    )


def _invalidation_mechanism(
    summary: CatalystSummary,
) -> str:
    if (
        summary.canonical_event_type == "earnings_beat"
        and summary.surprise_score is not None
        and summary.surprise_score >= SURPRISE_BOOST_THRESHOLD
    ):
        return "earnings_beat_surprise"
    if (
        summary.canonical_event_type == "fda_clearance"
        and summary.credibility_score is not None
        and summary.credibility_score >= 0.90
    ):
        return "fda_clearance_official"
    return "bullish_catalyst_cluster"


def build_short_thesis_invalidation(
    summaries: list[CatalystSummary],
    *,
    entity_id: str,
    prediction_cutoff: int,
) -> ShortThesisInvalidationEvidence | None:
    gated_bullish = [
        item
        for item in summaries
        if item.gate_ok
        and item.lean == "BULLISH"
        and (entity_id in item.entity_ids or not item.entity_ids)
        and iso_to_epoch_ns(item.available_time) <= prediction_cutoff
        and item.catalyst_strength is not None
    ]
    if not gated_bullish:
        return None

    best = max(gated_bullish, key=lambda row: row.catalyst_strength or 0.0)
    mechanism = _invalidation_mechanism(best)
    strength = best.catalyst_strength
    return ShortThesisInvalidationEvidence(
        entity_id=entity_id,
        affected_short_theses=(f"short:{entity_id}",),
        invalidation_strength=strength,
        confidence=strength,
        source_evidence_ids=tuple(item.event_id for item in gated_bullish),
        event_time=best.event_time,
        available_time=best.available_time,
        publication_state=PublicationState.PUBLISHED,
        provenance_ref=f"{PRODUCER_VERSION}:{mechanism}",
        quality_flags=best.quality_flags,
    )


def build_fixture_catalyst_pipeline(
    impact_summaries: list[ImpactComponentSummary],
    *,
    prediction_cutoff: int,
    entity_id: str,
    headlines_by_event: dict[str, str] | None = None,
) -> tuple[
    list[CatalystEvidence],
    list[CatalystSummary],
    ShortThesisInvalidationEvidence | None,
    list[dict[str, Any]],
]:
    headlines = headlines_by_event or {}
    evidence_rows: list[CatalystEvidence] = []
    summary_rows: list[CatalystSummary] = []
    adapter_rows: list[dict[str, Any]] = []

    for item in impact_summaries:
        if iso_to_epoch_ns(item.available_time) > prediction_cutoff:
            continue
        evidence = build_catalyst_evidence(item, entity_ids=(entity_id,))
        summary = build_catalyst_summary(
            evidence,
            canonical_event_type=item.canonical_event_type,
            headline=headlines.get(item.event_id, item.canonical_event_type.replace("_", " ")),
        )
        evidence_rows.append(evidence)
        summary_rows.append(summary)
        adapter_rows.append(catalyst_summary_to_adapter_row(summary))

    thesis = build_short_thesis_invalidation(
        summary_rows,
        entity_id=entity_id,
        prediction_cutoff=prediction_cutoff,
    )
    return evidence_rows, summary_rows, thesis, adapter_rows


def catalyst_summary_to_dict(item: CatalystSummary) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "event_id": item.event_id,
        "canonical_event_type": item.canonical_event_type,
        "entity_ids": list(item.entity_ids),
        "catalyst_strength": item.catalyst_strength,
        "novelty_score": item.novelty_score,
        "surprise_score": item.surprise_score,
        "materiality_score": item.materiality_score,
        "credibility_score": item.credibility_score,
        "lean": item.lean,
        "gate_ok": item.gate_ok,
        "event_time": item.event_time,
        "available_time": item.available_time,
        "publication_state": item.publication_state,
        "quality_flags": list(item.quality_flags),
        "catalyst_available": item.catalyst_available,
        "headline": item.headline,
        "scoring_method": SCORING_METHOD,
    }
    if item.synthesis_enrichment is not None:
        payload["synthesis_enrichment"] = synthesis_enrichment_to_dict(
            item.synthesis_enrichment
        )
    return payload


def catalyst_summary_to_adapter_row(item: CatalystSummary) -> dict[str, Any]:
    """Legacy adapter row shape for donor_bridge market_context_adapter."""
    return {
        "normalized_event_id": item.event_id,
        "catalyst_type": item.canonical_event_type,
        "confidence": item.catalyst_strength,
        "lean": item.lean,
        "gate_ok": item.gate_ok,
        "event_time": item.event_time,
        "headline": item.headline,
        "novelty_score": item.novelty_score,
        "surprise_score": item.surprise_score,
        "materiality_score": item.materiality_score,
        "credibility_score": item.credibility_score,
        "scoring_method": SCORING_METHOD,
    }


def short_thesis_invalidation_to_dict(
    item: ShortThesisInvalidationEvidence,
) -> dict[str, Any]:
    return {
        "entity_id": item.entity_id,
        "affected_short_theses": list(item.affected_short_theses),
        "invalidation_strength": item.invalidation_strength,
        "confidence": item.confidence,
        "source_evidence_ids": list(item.source_evidence_ids),
        "event_time": item.event_time,
        "available_time": item.available_time,
        "publication_state": item.publication_state.value,
        "provenance_ref": item.provenance_ref,
        "quality_flags": list(item.quality_flags),
    }


def _catalyst_strength_label(score: float | None) -> str:
    if score is None:
        return "LOW"
    if score >= CATALYST_STRENGTH_THRESHOLD + 0.15:
        return "HIGH"
    if score >= CATALYST_STRENGTH_THRESHOLD:
        return "MODERATE"
    return "LOW"


def build_catalyst_cross_lane_evidence(
    summaries: list[CatalystSummary],
    thesis: ShortThesisInvalidationEvidence | None,
    *,
    symbol: str,
    prediction_cutoff: int,
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for item in summaries:
        if iso_to_epoch_ns(item.available_time) > prediction_cutoff:
            continue
        if item.catalyst_strength is None or not item.gate_ok:
            continue
        if item.catalyst_strength < CATALYST_STRENGTH_THRESHOLD:
            continue
        row = lane_evidence_to_dict(
            NormalizedLaneEvidence(
                lane=LaneId.MARKET_CONTEXT,
                signal=EvidenceSignal.CATALYST_STRENGTH,
                strength=_catalyst_strength_label(item.catalyst_strength),
                available=True,
                source_ref=item.event_id,
                detail=(
                    f"MC8 catalyst fusion on {item.canonical_event_type} "
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
            "catalyst_strength": item.catalyst_strength,
            "novelty_score": item.novelty_score,
            "surprise_score": item.surprise_score,
            "materiality_score": item.materiality_score,
            "credibility_score": item.credibility_score,
            "lean": item.lean,
            "scoring_method": SCORING_METHOD,
        }
        evidence.append(row)

    if (
        thesis is not None
        and thesis.invalidation_strength is not None
        and thesis.invalidation_strength >= THESIS_INVALIDATION_THRESHOLD
        and iso_to_epoch_ns(thesis.available_time) <= prediction_cutoff
    ):
        row = lane_evidence_to_dict(
            NormalizedLaneEvidence(
                lane=LaneId.MARKET_CONTEXT,
                signal=EvidenceSignal.SHORT_THESIS_INVALIDATION,
                strength="HIGH" if thesis.invalidation_strength >= 0.75 else "MODERATE",
                available=True,
                source_ref=f"thesis:{thesis.entity_id}",
                detail="Bullish MC8 catalyst cluster invalidates short thesis",
                observed_at=thesis.available_time,
                quality_flags=thesis.quality_flags,
                provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
            )
        )
        row["metadata"] = {
            "symbol": symbol,
            "entity_id": thesis.entity_id,
            "invalidation_strength": thesis.invalidation_strength,
            "source_evidence_ids": list(thesis.source_evidence_ids),
            "provenance_ref": thesis.provenance_ref,
            "scoring_method": SCORING_METHOD,
        }
        evidence.append(row)

    return evidence


__all__ = [
    "CATALYST_GATE_THRESHOLD",
    "CATALYST_STRENGTH_THRESHOLD",
    "CatalystSummary",
    "PRODUCER_VERSION",
    "SCORING_METHOD",
    "THESIS_INVALIDATION_THRESHOLD",
    "build_catalyst_cross_lane_evidence",
    "build_catalyst_evidence",
    "build_catalyst_summary",
    "build_fixture_catalyst_pipeline",
    "build_short_thesis_invalidation",
    "catalyst_summary_to_adapter_row",
    "catalyst_summary_to_dict",
    "compute_catalyst_strength",
    "short_thesis_invalidation_to_dict",
]
