"""PI6 metaorder lifecycle interpretation from OF11 primitives."""

from __future__ import annotations

import uuid

from ..contracts.participant import (
    DirectionalClarity,
    IdentityConfidence,
    MetaorderEvidence,
    MetaorderLifecycleState,
    ParticipantHorizon,
    ParticipantMechanism,
    ParticipantQualityFlag,
    ParticipantResearchClassification,
    ParticipantType,
)
from ..order_flow.contracts import AggressorSide, MetaorderFlowState, MetaorderPrimitive, OrderFlowEvidence
from ..normalization.equity_bars import iso_to_epoch_ns

PRODUCER_VERSION = "participant_metaorder_v1"
ANONYMOUS_PARTICIPANT_ID = "participant:anonymous:institutional_scale"


def _map_flow_state(flow_state: MetaorderFlowState) -> MetaorderLifecycleState:
    if flow_state == MetaorderFlowState.FLOW_ACTIVE:
        return MetaorderLifecycleState.ACTIVE
    if flow_state == MetaorderFlowState.FLOW_STALLED:
        return MetaorderLifecycleState.LIKELY_COMPLETE
    if flow_state == MetaorderFlowState.FLOW_WEAKENING:
        return MetaorderLifecycleState.PAUSED
    return MetaorderLifecycleState.INSUFFICIENT_INFORMATION


def _cross_lane_signal_for_state(
    lifecycle_state: MetaorderLifecycleState,
    aggressor_side: AggressorSide,
) -> str | None:
    if lifecycle_state == MetaorderLifecycleState.ACTIVE:
        if aggressor_side == AggressorSide.BUY:
            return "METAORDER_LIKELY_ACTIVE"
        if aggressor_side == AggressorSide.SELL:
            return "METAORDER_LIKELY_ACTIVE"
    if lifecycle_state == MetaorderLifecycleState.LIKELY_COMPLETE:
        return "METAORDER_LIKELY_COMPLETE"
    return None


def interpret_metaorder_primitives(
    primitives: list[MetaorderPrimitive],
    *,
    prediction_cutoff: int,
    of_context: OrderFlowEvidence | None = None,
) -> list[MetaorderEvidence]:
    """Interpret OF11 primitives into PI6 lifecycle evidence."""
    del of_context  # reserved for future corroboration features
    evidence_rows: list[MetaorderEvidence] = []
    for primitive in primitives:
        available_ns = iso_to_epoch_ns(primitive.available_time)
        if available_ns > prediction_cutoff:
            continue
        lifecycle_state = _map_flow_state(primitive.flow_state)
        quality_flags = list(primitive.quality_flags)
        research_classification = ParticipantResearchClassification.FLOW_CONTINUATION_CANDIDATE
        if lifecycle_state == MetaorderLifecycleState.LIKELY_COMPLETE:
            research_classification = ParticipantResearchClassification.POST_FLOW_CONTRARIAN_CANDIDATE
        elif lifecycle_state == MetaorderLifecycleState.INSUFFICIENT_INFORMATION:
            research_classification = ParticipantResearchClassification.INSUFFICIENT_INFORMATION
            quality_flags.append(ParticipantQualityFlag.METAORDER_INFERENCE_LOW_CONFIDENCE.value)
        cross_lane_signal = _cross_lane_signal_for_state(lifecycle_state, primitive.aggressor_side)
        evidence_rows.append(
            MetaorderEvidence(
                evidence_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"metaorder:{primitive.primitive_id}")),
                primitive_id=primitive.primitive_id,
                instrument_id=primitive.instrument,
                venue=primitive.venue,
                lifecycle_state=lifecycle_state,
                aggressor_side=primitive.aggressor_side.value,
                signed_volume=primitive.signed_volume,
                trade_count=primitive.trade_count,
                event_time=primitive.end_time,
                available_time=primitive.available_time,
                participant_id=ANONYMOUS_PARTICIPANT_ID,
                participant_type=ParticipantType.UNKNOWN_LARGE_PARTICIPANT,
                identity_confidence=IdentityConfidence.ANONYMOUS_INSTITUTIONAL_SCALE,
                mechanism=ParticipantMechanism.MECHANICAL_FLOW,
                research_classification=research_classification,
                horizon=ParticipantHorizon.SECONDS_MINUTES,
                mbo_corroborated=primitive.mbo_corroborated,
                producer_version=PRODUCER_VERSION,
                quality_flags=tuple(quality_flags),
                cross_lane_signal=cross_lane_signal,
            )
        )
    return evidence_rows


__all__ = [
    "ANONYMOUS_PARTICIPANT_ID",
    "PRODUCER_VERSION",
    "interpret_metaorder_primitives",
]
