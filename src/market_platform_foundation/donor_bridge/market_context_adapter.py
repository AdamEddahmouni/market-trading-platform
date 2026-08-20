"""Market Context → Short Squeeze cross-lane adapter (SS P2 / MC8–MC9 fixture scope)."""

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
from ..market_context.attention import ATTENTION_ACCELERATION_THRESHOLD

CATALYST_STRENGTH_THRESHOLD = 0.5
THESIS_INVALIDATION_THRESHOLD = 0.55


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


def _attention_summaries(catalyst_payload: dict[str, Any]) -> list[dict[str, Any]]:
    summaries = catalyst_payload.get("attention_summaries") or []
    if not isinstance(summaries, list):
        return []
    return [row for row in summaries if isinstance(row, dict)]


def _latest_attention_summary(catalyst_payload: dict[str, Any]) -> dict[str, Any] | None:
    summaries = _attention_summaries(catalyst_payload)
    if not summaries:
        return None
    return summaries[-1]


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

    mc8_thesis = catalyst_payload.get("thesis_invalidation_evidence")
    if isinstance(mc8_thesis, dict) and mc8_thesis.get("invalidation_strength") is not None:
        gated = _gated_catalysts(catalyst_payload)
        latest = gated[-1] if gated else {}
        observation_time = str(
            mc8_thesis.get("available_time") or latest.get("event_time", "")
        )
        invalidation_raw = float(mc8_thesis["invalidation_strength"])
        thesis_obj = ShortThesisInvalidation(
            symbol=symbol,
            invalidation_score=round(invalidation_raw * 100.0, 2),
            mechanism=str(mc8_thesis.get("provenance_ref", "bullish_catalyst_cluster")).split(":")[-1],
            observation_time=observation_time,
            available_time=observation_time,
            publication_state=PublicationState.PUBLISHED,
            provenance_ref=str(catalyst_payload.get("provider_id", "market_context.catalyst")),
        )
    else:
        thesis_obj = None

    gated = _gated_catalysts(catalyst_payload)
    if not gated and not _attention_summaries(catalyst_payload):
        return {
            "catalyst_strength": None,
            "attention_feature": None,
            "thesis_invalidation": None,
        }

    latest = gated[-1] if gated else {}
    attention_latest = _latest_attention_summary(catalyst_payload) or {}
    observation_time = str(
        attention_latest.get("available_time")
        or latest.get("event_time", "")
    )
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

    attention_level = _optional_float(attention_latest.get("attention_level"))
    attention_velocity = _optional_float(attention_latest.get("attention_velocity"))
    attention_acceleration = _optional_float(attention_latest.get("attention_acceleration"))
    information_value = _optional_float(attention_latest.get("information_value"))
    reflexive_impact = _optional_float(attention_latest.get("reflexive_impact"))

    attention_obj: AttentionFeature | None = None
    if attention_level is not None:
        attention_obj = AttentionFeature(
            symbol=symbol,
            attention_score=round(attention_level * 100.0, 2),
            attention_velocity=round(attention_velocity * 100.0, 2)
            if attention_velocity is not None
            else None,
            attention_acceleration=round(attention_acceleration * 100.0, 2)
            if attention_acceleration is not None
            else None,
            observation_time=observation_time,
            available_time=available_time,
            publication_state=PublicationState.PUBLISHED,
            provenance_ref="market_context.attention",
            quality_flags=tuple(attention_latest.get("quality_flags") or ()),
        )

    invalidation_score = _thesis_invalidation_score(gated)
    if thesis_obj is None and invalidation_score is not None:
        thesis_obj = ShortThesisInvalidation(
            symbol=symbol,
            invalidation_score=round(invalidation_score * 100.0, 2),
            mechanism="bullish_catalyst_cluster",
            observation_time=observation_time,
            available_time=available_time,
            publication_state=PublicationState.PUBLISHED,
            provenance_ref=str(catalyst_payload.get("provider_id", "market_context")),
        )

    result = {
        "catalyst_strength": catalyst_strength_to_dict(catalyst_strength_obj)
        if catalyst_strength_obj
        else None,
        "attention_feature": attention_feature_to_dict(attention_obj) if attention_obj else None,
        "thesis_invalidation": short_thesis_invalidation_to_dict(thesis_obj)
        if thesis_obj
        else None,
    }
    if information_value is not None:
        result["information_value"] = round(information_value * 100.0, 2)
    if reflexive_impact is not None:
        result["reflexive_impact"] = round(reflexive_impact * 100.0, 2)
    return result


def build_cross_lane_snapshot_from_catalyst(
    catalyst_payload: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Derive cross-lane snapshot + normalized evidence from catalyst workspace payload."""
    if not catalyst_payload or not catalyst_payload.get("available"):
        return None, []

    gated = _gated_catalysts(catalyst_payload)
    attention_latest = _latest_attention_summary(catalyst_payload)
    if not gated and attention_latest is None:
        return None, []

    latest = gated[-1] if gated else {}
    confidence = _optional_float(latest.get("confidence"))
    catalyst_strength = round(confidence * 100.0, 2) if confidence is not None else None

    invalidation_raw = _thesis_invalidation_score(gated)
    mc8_thesis = catalyst_payload.get("thesis_invalidation_evidence")
    if isinstance(mc8_thesis, dict) and mc8_thesis.get("invalidation_strength") is not None:
        invalidation_raw = float(mc8_thesis["invalidation_strength"])

    attention_acceleration = (
        _optional_float(attention_latest.get("attention_acceleration"))
        if attention_latest
        else None
    )
    attention_available = (
        attention_acceleration is not None
        and attention_acceleration >= ATTENTION_ACCELERATION_THRESHOLD
    )
    diffusion_elevated = False
    if attention_latest:
        diffusion_score = _optional_float(attention_latest.get("diffusion_score"))
        diffusion_elevated = (
            diffusion_score is not None
            and diffusion_score >= 0.60
            and bool(attention_latest.get("corroboration_improving"))
        )

    snapshot: dict[str, Any] = {
        "catalyst_available": catalyst_strength is not None,
        "catalyst_strength": catalyst_strength,
        "thesis_invalidation_score": round(invalidation_raw * 100.0, 2)
        if invalidation_raw is not None
        else None,
        "attention_available": attention_available,
        "attention_acceleration": round(attention_acceleration * 100.0, 2)
        if attention_acceleration is not None
        else None,
        "information_diffusion_elevated": diffusion_elevated,
    }
    if attention_latest:
        information_value = _optional_float(attention_latest.get("information_value"))
        reflexive_impact = _optional_float(attention_latest.get("reflexive_impact"))
        if information_value is not None:
            snapshot["information_value"] = round(information_value * 100.0, 2)
        if reflexive_impact is not None:
            snapshot["reflexive_impact"] = round(reflexive_impact * 100.0, 2)

    evidence: list[dict[str, Any]] = []
    if catalyst_strength is not None and catalyst_strength >= CATALYST_STRENGTH_THRESHOLD * 100.0:
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

    if attention_available and attention_acceleration is not None:
        evidence.append(
            lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.MARKET_CONTEXT,
                    signal=EvidenceSignal.ATTENTION_ACCELERATION,
                    strength="MODERATE",
                    available=True,
                    source_ref="market_context:attention",
                    detail=f"MC9 attention acceleration {attention_acceleration:.4f}",
                    provenance_class=EvidenceProvenanceClass.DERIVED,
                )
            )
        )

    if diffusion_elevated:
        evidence.append(
            lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.MARKET_CONTEXT,
                    signal=EvidenceSignal.INFORMATION_DIFFUSION_ELEVATED,
                    strength="MODERATE",
                    available=True,
                    source_ref="market_context:attention_diffusion",
                    detail="MC9 information diffusion elevated with corroboration improving",
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
