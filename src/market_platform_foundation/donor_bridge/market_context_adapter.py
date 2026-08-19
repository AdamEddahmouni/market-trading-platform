"""Market Context → Short Squeeze cross-lane adapter (SS P2 / MC8 fixture scope)."""

from __future__ import annotations

from typing import Any

from ..contracts.squeeze_structural import (
    AttentionFeature,
    CatalystStrength,
    PublicationState,
    ShortThesisInvalidation,
    attention_feature_to_dict,
    catalyst_strength_to_dict,
    short_thesis_invalidation_to_dict,
)
from ..cross_lane.evidence import (
    EvidenceProvenanceClass,
    EvidenceSignal,
    LaneId,
    NormalizedLaneEvidence,
    lane_evidence_to_dict,
)

CATALYST_STRENGTH_THRESHOLD = 0.5
THESIS_INVALIDATION_THRESHOLD = 0.55
ATTENTION_ACCELERATION_THRESHOLD = 0.05


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _gated_catalysts(catalyst_payload: dict[str, Any]) -> list[dict[str, Any]]:
    catalysts = catalyst_payload.get("catalysts") or []
    if not isinstance(catalysts, list):
        return []
    gated: list[dict[str, Any]] = []
    for row in catalysts:
        if not isinstance(row, dict):
            continue
        if row.get("gate_ok") is False:
            continue
        gated.append(row)
    return gated


def _thesis_invalidation_score(catalysts: list[dict[str, Any]]) -> float | None:
    """Bullish gated catalyst confidence — invalidates short thesis when elevated."""
    scores: list[float] = []
    for row in catalysts:
        lean = str(row.get("lean", "")).upper()
        confidence = _optional_float(row.get("confidence"))
        if confidence is None:
            continue
        if lean == "BULLISH" and confidence >= CATALYST_STRENGTH_THRESHOLD:
            scores.append(confidence)
    if not scores:
        return None
    return max(scores)


def _attention_metrics(catalysts: list[dict[str, Any]]) -> tuple[float | None, float | None]:
    """Derive attention velocity/acceleration from gated catalyst confidence series."""
    confidences = [
        value
        for value in (_optional_float(row.get("confidence")) for row in catalysts)
        if value is not None
    ]
    if not confidences:
        return None, None
    attention_score = confidences[-1]
    if len(confidences) == 1:
        return attention_score, attention_score * 0.5
    velocity = confidences[-1] - confidences[-2]
    if len(confidences) >= 3:
        prior_velocity = confidences[-2] - confidences[-3]
        acceleration = velocity - prior_velocity
    else:
        acceleration = velocity
    return attention_score, acceleration


def build_ss_p2_structures_from_catalyst(
    catalyst_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    """Map catalyst workspace payload into SS P2 contract dicts (fail-closed)."""
    symbol = str((catalyst_payload or {}).get("symbol", "")).upper()
    if not catalyst_payload or not catalyst_payload.get("available") or not symbol:
        return {
            "catalyst_strength": None,
            "attention_feature": None,
            "thesis_invalidation": None,
        }

    gated = _gated_catalysts(catalyst_payload)
    if not gated:
        return {
            "catalyst_strength": None,
            "attention_feature": None,
            "thesis_invalidation": None,
        }

    latest = gated[-1]
    observation_time = str(latest.get("event_time", ""))
    available_time = observation_time
    confidence = _optional_float(latest.get("confidence"))
    catalyst_type = str(latest.get("catalyst_type", "unknown"))

    catalyst_strength_obj: CatalystStrength | None = None
    if confidence is not None:
        catalyst_strength_obj = CatalystStrength(
            symbol=symbol,
            catalyst_id=str(latest.get("normalized_event_id", f"catalyst:{symbol}:{catalyst_type}")),
            strength=round(confidence * 100.0, 2),
            catalyst_type=catalyst_type,
            observation_time=observation_time,
            available_time=available_time,
            publication_state=PublicationState.PUBLISHED,
            provenance_ref=str(catalyst_payload.get("provider_id", "market_context")),
        )

    attention_score, attention_acceleration = _attention_metrics(gated)
    attention_obj: AttentionFeature | None = None
    if attention_score is not None:
        attention_obj = AttentionFeature(
            symbol=symbol,
            attention_score=round(attention_score * 100.0, 2),
            attention_velocity=round((attention_acceleration or 0.0) * 100.0, 2)
            if attention_acceleration is not None
            else None,
            attention_acceleration=round(attention_acceleration * 100.0, 2)
            if attention_acceleration is not None
            else None,
            observation_time=observation_time,
            available_time=available_time,
            publication_state=PublicationState.PUBLISHED,
            provenance_ref=str(catalyst_payload.get("provider_id", "market_context")),
        )

    invalidation_score = _thesis_invalidation_score(gated)
    thesis_obj: ShortThesisInvalidation | None = None
    if invalidation_score is not None:
        thesis_obj = ShortThesisInvalidation(
            symbol=symbol,
            invalidation_score=round(invalidation_score * 100.0, 2),
            mechanism="bullish_catalyst_cluster",
            observation_time=observation_time,
            available_time=available_time,
            publication_state=PublicationState.PUBLISHED,
            provenance_ref=str(catalyst_payload.get("provider_id", "market_context")),
        )

    return {
        "catalyst_strength": catalyst_strength_to_dict(catalyst_strength_obj)
        if catalyst_strength_obj
        else None,
        "attention_feature": attention_feature_to_dict(attention_obj) if attention_obj else None,
        "thesis_invalidation": short_thesis_invalidation_to_dict(thesis_obj)
        if thesis_obj
        else None,
    }


def build_cross_lane_snapshot_from_catalyst(
    catalyst_payload: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Derive cross-lane snapshot + normalized evidence from catalyst workspace payload."""
    if not catalyst_payload or not catalyst_payload.get("available"):
        return None, []

    gated = _gated_catalysts(catalyst_payload)
    if not gated:
        return None, []

    latest = gated[-1]
    confidence = _optional_float(latest.get("confidence"))
    if confidence is None:
        return None, []

    catalyst_strength = round(confidence * 100.0, 2)
    invalidation_raw = _thesis_invalidation_score(gated)
    _attention_score, attention_acceleration = _attention_metrics(gated)
    attention_accel_scaled = (
        round(attention_acceleration * 100.0, 2) if attention_acceleration is not None else None
    )
    attention_available = (
        attention_accel_scaled is not None
        and abs(attention_accel_scaled) >= ATTENTION_ACCELERATION_THRESHOLD * 100.0
    )

    snapshot: dict[str, Any] = {
        "catalyst_available": True,
        "catalyst_strength": catalyst_strength,
        "thesis_invalidation_score": round(invalidation_raw * 100.0, 2)
        if invalidation_raw is not None
        else None,
        "attention_available": attention_available,
        "attention_acceleration": attention_accel_scaled,
    }

    evidence: list[dict[str, Any]] = []
    if catalyst_strength >= CATALYST_STRENGTH_THRESHOLD * 100.0:
        strength_label = "HIGH" if catalyst_strength >= 75.0 else "MODERATE"
        evidence.append(
            lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.MARKET_CONTEXT,
                    signal=EvidenceSignal.CATALYST_STRENGTH,
                    strength=strength_label,
                    available=True,
                    source_ref="market_context:catalyst",
                    detail=str(latest.get("headline", "Gated catalyst strength elevated")),
                    provenance_class=EvidenceProvenanceClass.DERIVED,
                )
            )
        )

    if invalidation_raw is not None and invalidation_raw >= THESIS_INVALIDATION_THRESHOLD:
        evidence.append(
            lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.MARKET_CONTEXT,
                    signal=EvidenceSignal.SHORT_THESIS_INVALIDATION,
                    strength="HIGH" if invalidation_raw >= 0.75 else "MODERATE",
                    available=True,
                    source_ref="market_context:thesis_invalidation",
                    detail="Bullish gated catalyst cluster invalidates short thesis",
                    provenance_class=EvidenceProvenanceClass.DERIVED,
                )
            )
        )

    if attention_available and attention_accel_scaled is not None:
        evidence.append(
            lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.MARKET_CONTEXT,
                    signal=EvidenceSignal.ATTENTION_ACCELERATION,
                    strength="MODERATE",
                    available=True,
                    source_ref="market_context:attention",
                    detail=f"Attention acceleration {attention_accel_scaled:.1f}",
                    provenance_class=EvidenceProvenanceClass.DERIVED,
                )
            )
        )

    return snapshot, evidence


__all__ = [
    "ATTENTION_ACCELERATION_THRESHOLD",
    "CATALYST_STRENGTH_THRESHOLD",
    "THESIS_INVALIDATION_THRESHOLD",
    "build_cross_lane_snapshot_from_catalyst",
    "build_ss_p2_structures_from_catalyst",
]
