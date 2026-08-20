"""Participant Intelligence evidence builders (PI3).

Builds InsiderEvidence, ActivistEvidence, and cross-lane publishable signals
from ParticipantAction dicts. Missing semantics produce no directional signal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..contracts.participant import (
    DirectionalClarity,
    IdentityConfidence,
    InsiderDiscretion,
    MetaorderEvidence,
    DerivativeParticipantEvidence,
    ForcedFlowEvidence,
    ParticipantActionType,
    ParticipantEvidenceEnvelope,
    ParticipantHorizon,
    ParticipantMechanism,
    ParticipantQualityFlag,
    ParticipantResearchClassification,
    ParticipantType,
    metaorder_evidence_to_dict,
    participant_evidence_envelope_to_dict,
    derivative_participant_evidence_to_dict,
    forced_flow_evidence_to_dict,
)
from ..cross_lane.evidence import (
    EvidenceProvenanceClass,
    EvidenceSignal,
    LaneId,
    NormalizedLaneEvidence,
    lane_evidence_to_dict,
)
from ..normalization.equity_bars import iso_to_epoch_ns

PRODUCER_ID = "participant_intelligence"
PRODUCER_VERSION = "participant_evidence_v1"
SKILL_PRODUCER_VERSION = "participant_skill_v1"


@dataclass(frozen=True, slots=True)
class InsiderEvidence:
    """PI3 insider disclosure evidence."""

    action_id: str
    participant_id: str
    display_name: str
    action_type: str
    insider_discretion: str | None
    direction: str
    quantity: float | None
    notional: float | None
    transaction_price: float | None
    event_time: str
    available_time: str
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    cross_lane_signal: str | None = None


@dataclass(frozen=True, slots=True)
class ActivistEvidence:
    """PI3 activist disclosure evidence."""

    action_id: str
    participant_id: str
    display_name: str
    action_type: str
    stake_percent: float | None
    campaign_objective: str | None
    is_passive: bool | None
    event_time: str
    available_time: str
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    cross_lane_signal: str | None = None


@dataclass(frozen=True, slots=True)
class InstitutionalHoldingEvidence:
    """PI4 institutional 13F QoQ position change evidence."""

    action_id: str
    participant_id: str
    display_name: str
    action_type: str
    instrument_id: str
    cusip: str | None
    share_delta: float | None
    prior_shares: float | None
    current_shares: float | None
    quarter_end: str | None
    event_time: str
    available_time: str
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    cross_lane_signal: str | None = None


@dataclass(frozen=True, slots=True)
class ParticipantSkillEvidence:
    """PI5 walk-forward skill evidence for one participant group."""

    skill_group_key: str
    participant_id: str
    display_name: str
    dimension: str
    raw_mean: float | None
    shrunk_estimate: float | None
    sample_count: int
    outcome_window_days: int
    walk_forward_fold_count: int
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    cross_lane_signal: str | None = None


def insider_evidence_to_dict(item: InsiderEvidence) -> dict[str, Any]:
    return {
        "action_id": item.action_id,
        "participant_id": item.participant_id,
        "display_name": item.display_name,
        "action_type": item.action_type,
        "insider_discretion": item.insider_discretion,
        "direction": item.direction,
        "quantity": item.quantity,
        "notional": item.notional,
        "transaction_price": item.transaction_price,
        "event_time": item.event_time,
        "available_time": item.available_time,
        "quality_flags": list(item.quality_flags),
        "cross_lane_signal": item.cross_lane_signal,
        "payload_type": "InsiderEvidence",
        "producer_version": PRODUCER_VERSION,
    }


def activist_evidence_to_dict(item: ActivistEvidence) -> dict[str, Any]:
    return {
        "action_id": item.action_id,
        "participant_id": item.participant_id,
        "display_name": item.display_name,
        "action_type": item.action_type,
        "stake_percent": item.stake_percent,
        "campaign_objective": item.campaign_objective,
        "is_passive": item.is_passive,
        "event_time": item.event_time,
        "available_time": item.available_time,
        "quality_flags": list(item.quality_flags),
        "cross_lane_signal": item.cross_lane_signal,
        "payload_type": "ActivistEvidence",
        "producer_version": PRODUCER_VERSION,
    }


def institutional_holding_evidence_to_dict(item: InstitutionalHoldingEvidence) -> dict[str, Any]:
    return {
        "action_id": item.action_id,
        "participant_id": item.participant_id,
        "display_name": item.display_name,
        "action_type": item.action_type,
        "instrument_id": item.instrument_id,
        "cusip": item.cusip,
        "share_delta": item.share_delta,
        "prior_shares": item.prior_shares,
        "current_shares": item.current_shares,
        "quarter_end": item.quarter_end,
        "event_time": item.event_time,
        "available_time": item.available_time,
        "quality_flags": list(item.quality_flags),
        "cross_lane_signal": item.cross_lane_signal,
        "payload_type": "InstitutionalHoldingEvidence",
        "producer_version": PRODUCER_VERSION,
    }


def participant_skill_evidence_to_dict(item: ParticipantSkillEvidence) -> dict[str, Any]:
    return {
        "skill_group_key": item.skill_group_key,
        "participant_id": item.participant_id,
        "display_name": item.display_name,
        "dimension": item.dimension,
        "raw_mean": item.raw_mean,
        "shrunk_estimate": item.shrunk_estimate,
        "sample_count": item.sample_count,
        "outcome_window_days": item.outcome_window_days,
        "walk_forward_fold_count": item.walk_forward_fold_count,
        "quality_flags": list(item.quality_flags),
        "cross_lane_signal": item.cross_lane_signal,
        "payload_type": "ParticipantSkillEvidence",
        "producer_version": SKILL_PRODUCER_VERSION,
    }


def build_participant_skill_evidence(
    snapshot: dict[str, Any],
    *,
    dimension: str,
) -> ParticipantSkillEvidence | None:
    dimensions = snapshot.get("dimensions", {})
    if not isinstance(dimensions, dict):
        return None
    estimate = dimensions.get(dimension)
    if not isinstance(estimate, dict):
        return None
    flags = tuple(estimate.get("quality_flags", []))
    if ParticipantQualityFlag.SKILL_INSUFFICIENT_SAMPLE.value in flags:
        return None
    shrunk = estimate.get("shrunk_estimate")
    signal: str | None = None
    if dimension == "buy_skill" and shrunk is not None:
        if float(shrunk) >= 0.05:
            signal = EvidenceSignal.PARTICIPANT_SKILL_ELEVATED.value
        elif float(shrunk) <= -0.02:
            signal = EvidenceSignal.PARTICIPANT_SKILL_BELOW_BASELINE.value
    return ParticipantSkillEvidence(
        skill_group_key=str(snapshot.get("skill_group_key", "")),
        participant_id=str(snapshot.get("participant_id", "")),
        display_name=str(snapshot.get("display_name", "")),
        dimension=dimension,
        raw_mean=estimate.get("raw_mean"),
        shrunk_estimate=shrunk,
        sample_count=int(estimate.get("sample_count", 0)),
        outcome_window_days=int(estimate.get("outcome_window_days", 20)),
        walk_forward_fold_count=int(snapshot.get("walk_forward_fold_count", 0)),
        quality_flags=flags,
        cross_lane_signal=signal,
    )


def build_insider_evidence(action: dict[str, Any]) -> InsiderEvidence | None:
    form_type = str(action.get("form_type", "")).upper().replace("/A", "")
    if form_type != "4":
        return None
    action_type = str(action.get("action_type", ""))
    discretion = action.get("insider_discretion")
    signal: str | None = None
    if (
        action_type == ParticipantActionType.OPEN_MARKET_BUY.value
        and discretion == InsiderDiscretion.DISCRETIONARY.value
    ):
        signal = EvidenceSignal.INSIDER_DISCRETIONARY_PURCHASE.value
    elif action_type in {
        ParticipantActionType.INSIDER_AWARD_GRANT.value,
        ParticipantActionType.INSIDER_TAX_WITHHOLDING.value,
        ParticipantActionType.INSIDER_GIFT.value,
    } or discretion in {
        InsiderDiscretion.COMPENSATION.value,
        InsiderDiscretion.PLAN_10B5_1.value,
    }:
        signal = EvidenceSignal.INSIDER_SALE_NON_DISCRETIONARY.value
    return InsiderEvidence(
        action_id=str(action.get("action_id", "")),
        participant_id=str(action.get("participant_id", "")),
        display_name=str(action.get("display_name", "")),
        action_type=action_type,
        insider_discretion=str(discretion) if discretion is not None else None,
        direction=str(action.get("direction", "")),
        quantity=action.get("quantity"),
        notional=action.get("notional"),
        transaction_price=action.get("transaction_price"),
        event_time=str(action.get("event_time", "")),
        available_time=str(action.get("available_time", "")),
        quality_flags=tuple(action.get("quality_flags", [])),
        cross_lane_signal=signal,
    )


def build_activist_evidence(action: dict[str, Any]) -> ActivistEvidence | None:
    form_type = str(action.get("form_type", "")).upper().replace("/A", "")
    activist_context = action.get("activist_context")
    if form_type == "13D":
        context = activist_context if isinstance(activist_context, dict) else {}
        return ActivistEvidence(
            action_id=str(action.get("action_id", "")),
            participant_id=str(action.get("participant_id", "")),
            display_name=str(action.get("display_name", "")),
            action_type=str(action.get("action_type", "")),
            stake_percent=context.get("stake_percent"),
            campaign_objective=context.get("campaign_objective"),
            is_passive=context.get("is_passive"),
            event_time=str(action.get("event_time", "")),
            available_time=str(action.get("available_time", "")),
            quality_flags=tuple(action.get("quality_flags", [])),
            cross_lane_signal=EvidenceSignal.ACTIVIST_STAKE_DISCLOSED.value,
        )
    if form_type == "13G":
        context = activist_context if isinstance(activist_context, dict) else {}
        return ActivistEvidence(
            action_id=str(action.get("action_id", "")),
            participant_id=str(action.get("participant_id", "")),
            display_name=str(action.get("display_name", "")),
            action_type=str(action.get("action_type", "")),
            stake_percent=context.get("stake_percent"),
            campaign_objective=None,
            is_passive=context.get("is_passive", True),
            event_time=str(action.get("event_time", "")),
            available_time=str(action.get("available_time", "")),
            quality_flags=tuple(action.get("quality_flags", [])),
            cross_lane_signal=None,
        )
    return None


_POSITION_CHANGE_TYPES = {
    ParticipantActionType.POSITION_INITIATED.value,
    ParticipantActionType.POSITION_INCREASED.value,
    ParticipantActionType.POSITION_REDUCED.value,
    ParticipantActionType.POSITION_EXITED.value,
}


def build_institutional_holding_evidence(action: dict[str, Any]) -> InstitutionalHoldingEvidence | None:
    action_type = str(action.get("action_type", ""))
    if action_type not in _POSITION_CHANGE_TYPES:
        return None
    return InstitutionalHoldingEvidence(
        action_id=str(action.get("action_id", "")),
        participant_id=str(action.get("participant_id", "")),
        display_name=str(action.get("display_name", "")),
        action_type=action_type,
        instrument_id=str(action.get("instrument_id", "")),
        cusip=str(action.get("cusip")) if action.get("cusip") is not None else None,
        share_delta=action.get("share_delta", action.get("quantity")),
        prior_shares=action.get("prior_shares"),
        current_shares=action.get("current_shares"),
        quarter_end=str(action.get("quarter_end")) if action.get("quarter_end") is not None else None,
        event_time=str(action.get("event_time", "")),
        available_time=str(action.get("available_time", "")),
        quality_flags=tuple(action.get("quality_flags", [])),
        cross_lane_signal=EvidenceSignal.INSTITUTIONAL_HOLDING_CHANGE.value,
    )


def build_participant_evidence_envelope(
    *,
    evidence_id: str,
    action: dict[str, Any],
    payload_type: str,
    payload: dict[str, Any],
    mechanism: ParticipantMechanism,
    research_classification: ParticipantResearchClassification,
    horizon: ParticipantHorizon,
) -> ParticipantEvidenceEnvelope:
    return ParticipantEvidenceEnvelope(
        evidence_id=evidence_id,
        producer=PRODUCER_ID,
        producer_version=PRODUCER_VERSION,
        event_time=str(action.get("event_time", "")),
        available_time=str(action.get("available_time", "")),
        participant_id=str(action.get("participant_id", "")),
        participant_type=ParticipantType(str(action.get("participant_type", ParticipantType.UNKNOWN.value))),
        identity_confidence=IdentityConfidence(
            str(action.get("identity_confidence", IdentityConfidence.UNKNOWN.value))
        ),
        mechanism=mechanism,
        mechanism_confidence=None,
        directional_clarity=DirectionalClarity(
            str(action.get("directional_clarity", DirectionalClarity.UNKNOWN.value))
        ),
        horizon=horizon,
        freshness_hours=None,
        research_classification=research_classification,
        provenance_class=EvidenceProvenanceClass.DERIVED.value,
        source_provenance=str(action.get("source", "regulatory_disclosure")),
        supporting_evidence_ids=(str(action.get("action_id", "")),),
        quality_flags=tuple(action.get("quality_flags", [])),
        payload_type=payload_type,
        payload=payload,
    )


def build_evidence_payloads_from_actions(
    actions: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (typed_evidence_payloads, envelope_dicts)."""
    typed: list[dict[str, Any]] = []
    envelopes: list[dict[str, Any]] = []
    for action in actions:
        insider = build_insider_evidence(action)
        if insider is not None:
            payload = insider_evidence_to_dict(insider)
            typed.append(payload)
            envelopes.append(
                participant_evidence_envelope_to_dict(
                    build_participant_evidence_envelope(
                        evidence_id=f"participant:insider:{insider.action_id}",
                        action=action,
                        payload_type="InsiderEvidence",
                        payload=payload,
                        mechanism=(
                            ParticipantMechanism.INFORMED_DIRECTIONAL
                            if insider.cross_lane_signal
                            == EvidenceSignal.INSIDER_DISCRETIONARY_PURCHASE.value
                            else ParticipantMechanism.COMPENSATION
                        ),
                        research_classification=ParticipantResearchClassification(
                            str(action.get("research_classification", ParticipantResearchClassification.INSUFFICIENT_INFORMATION.value))
                        ),
                        horizon=ParticipantHorizon(str(action.get("estimated_horizon", ParticipantHorizon.MONTHS.value))),
                    )
                )
            )
        activist = build_activist_evidence(action)
        if activist is not None:
            payload = activist_evidence_to_dict(activist)
            typed.append(payload)
            envelopes.append(
                participant_evidence_envelope_to_dict(
                    build_participant_evidence_envelope(
                        evidence_id=f"participant:activist:{activist.action_id}",
                        action=action,
                        payload_type="ActivistEvidence",
                        payload=payload,
                        mechanism=(
                            ParticipantMechanism.ACTIVIST_INFLUENCE
                            if activist.cross_lane_signal
                            else ParticipantMechanism.PORTFOLIO_ALLOCATION
                        ),
                        research_classification=(
                            ParticipantResearchClassification.STRATEGIC_ALIGNMENT_CANDIDATE
                            if activist.cross_lane_signal
                            else ParticipantResearchClassification.INFORMATIONAL_CONTEXT_ONLY
                        ),
                        horizon=ParticipantHorizon.YEARS,
                    )
                )
            )
        institutional = build_institutional_holding_evidence(action)
        if institutional is not None:
            payload = institutional_holding_evidence_to_dict(institutional)
            typed.append(payload)
            envelopes.append(
                participant_evidence_envelope_to_dict(
                    build_participant_evidence_envelope(
                        evidence_id=f"participant:institutional:{institutional.action_id}",
                        action=action,
                        payload_type="InstitutionalHoldingEvidence",
                        payload=payload,
                        mechanism=ParticipantMechanism.PORTFOLIO_ALLOCATION,
                        research_classification=ParticipantResearchClassification.INFORMATIONAL_CONTEXT_ONLY,
                        horizon=ParticipantHorizon.MONTHS,
                    )
                )
            )
    return typed, envelopes


def participant_cross_lane_evidence_from_actions(
    actions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Publish cross-lane signals for unambiguous participant semantics."""
    evidence: list[dict[str, Any]] = []
    for action in actions:
        insider = build_insider_evidence(action)
        if insider is not None and insider.cross_lane_signal:
            evidence.append(
                lane_evidence_to_dict(
                    NormalizedLaneEvidence(
                        lane=LaneId.PARTICIPANT_INTELLIGENCE,
                        signal=EvidenceSignal(insider.cross_lane_signal),
                        strength="MODERATE",
                        available=True,
                        source_ref=f"participant:insider:{insider.action_id}",
                        detail=(
                            f"{insider.display_name} {insider.action_type} "
                            f"discretion={insider.insider_discretion}; delayed SEC disclosure"
                        ),
                        observed_at=insider.available_time,
                        quality_flags=insider.quality_flags,
                        provenance_class=EvidenceProvenanceClass.DERIVED,
                    )
                )
            )
        activist = build_activist_evidence(action)
        if activist is not None and activist.cross_lane_signal:
            stake = activist.stake_percent
            detail = f"{activist.display_name} activist stake disclosed"
            if stake is not None:
                detail += f" stake={stake}%"
            if activist.campaign_objective:
                detail += f" objective={activist.campaign_objective}"
            evidence.append(
                lane_evidence_to_dict(
                    NormalizedLaneEvidence(
                        lane=LaneId.PARTICIPANT_INTELLIGENCE,
                        signal=EvidenceSignal(activist.cross_lane_signal),
                        strength="HIGH" if stake is not None and float(stake) >= 5.0 else "MODERATE",
                        available=True,
                        source_ref=f"participant:activist:{activist.action_id}",
                        detail=detail,
                        observed_at=activist.available_time,
                        quality_flags=activist.quality_flags,
                        provenance_class=EvidenceProvenanceClass.DERIVED,
                    )
                )
            )
        institutional = build_institutional_holding_evidence(action)
        if institutional is not None and institutional.cross_lane_signal:
            detail = (
                f"{institutional.display_name} {institutional.action_type} "
                f"instrument={institutional.instrument_id}"
            )
            if institutional.share_delta is not None:
                detail += f" delta={institutional.share_delta}"
            evidence.append(
                lane_evidence_to_dict(
                    NormalizedLaneEvidence(
                        lane=LaneId.PARTICIPANT_INTELLIGENCE,
                        signal=EvidenceSignal(institutional.cross_lane_signal),
                        strength="MODERATE",
                        available=True,
                        source_ref=f"participant:institutional:{institutional.action_id}",
                        detail=detail,
                        observed_at=institutional.available_time,
                        quality_flags=institutional.quality_flags,
                        provenance_class=EvidenceProvenanceClass.DERIVED,
                    )
                )
            )
    if evidence:
        evidence.append(
            lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.PARTICIPANT_INTELLIGENCE,
                    signal=EvidenceSignal.PARTICIPANT_DATA_CONFIDENCE,
                    strength="MODERATE",
                    available=True,
                    source_ref="participant:disclosure_bundle",
                    detail=f"{len(evidence)} participant disclosure signal(s) on admitted ledger",
                    provenance_class=EvidenceProvenanceClass.DERIVED,
                )
            )
        )
    return evidence


def summarize_participant_actions(actions: list[dict[str, Any]]) -> dict[str, Any]:
    """Mechanism-aware summary for institutional query (PI-D01)."""
    discretionary_buy_count = 0
    activist_disclosure_count = 0
    compensation_count = 0
    ambiguous_count = 0
    open_market_sell_count = 0
    institutional_snapshot_count = 0
    institutional_position_change_count = 0
    signals: list[str] = []

    for action in actions:
        insider = build_insider_evidence(action)
        if insider is not None:
            if insider.cross_lane_signal == EvidenceSignal.INSIDER_DISCRETIONARY_PURCHASE.value:
                discretionary_buy_count += 1
                signals.append(insider.cross_lane_signal)
            elif insider.cross_lane_signal == EvidenceSignal.INSIDER_SALE_NON_DISCRETIONARY.value:
                compensation_count += 1
            elif insider.direction == "SELL":
                open_market_sell_count += 1
            elif ParticipantQualityFlag.ACTION_AMBIGUOUS.value in insider.quality_flags:
                ambiguous_count += 1
            continue
        activist = build_activist_evidence(action)
        if activist is not None:
            if activist.cross_lane_signal:
                activist_disclosure_count += 1
                signals.append(activist.cross_lane_signal)
            else:
                institutional_snapshot_count += 1
            continue
        institutional = build_institutional_holding_evidence(action)
        if institutional is not None:
            institutional_position_change_count += 1
            if institutional.cross_lane_signal:
                signals.append(institutional.cross_lane_signal)
            continue
        if str(action.get("action_type")) == ParticipantActionType.INSTITUTIONAL_HOLDING_SNAPSHOT.value:
            institutional_snapshot_count += 1
        else:
            ambiguous_count += 1

    if discretionary_buy_count > activist_disclosure_count:
        direction = "bullish_participant"
    elif activist_disclosure_count > discretionary_buy_count:
        direction = "activist_context"
    elif open_market_sell_count > discretionary_buy_count:
        direction = "bearish_participant"
    elif ambiguous_count > 0 and discretionary_buy_count == 0 and activist_disclosure_count == 0:
        direction = "ambiguous"
    elif not actions:
        direction = "unavailable"
    else:
        direction = "neutral_context"

    return {
        "direction": direction,
        "discretionary_buy_count": discretionary_buy_count,
        "activist_disclosure_count": activist_disclosure_count,
        "compensation_count": compensation_count,
        "open_market_sell_count": open_market_sell_count,
        "ambiguous_count": ambiguous_count,
        "institutional_snapshot_count": institutional_snapshot_count,
        "institutional_position_change_count": institutional_position_change_count,
        "cross_lane_signals": sorted(set(signals)),
        "action_count": len(actions),
    }


def participant_skill_cross_lane_evidence(skill_summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Publish PI5 skill signals when sample gates pass."""
    if not skill_summary.get("skill_available"):
        return []
    evidence: list[dict[str, Any]] = []
    participants = skill_summary.get("participants", {})
    if not isinstance(participants, dict):
        return []
    for participant_payload in participants.values():
        if not isinstance(participant_payload, dict):
            continue
        skill_item = build_participant_skill_evidence(participant_payload, dimension="buy_skill")
        if skill_item is None or skill_item.cross_lane_signal is None:
            continue
        detail = (
            f"{skill_item.display_name} buy_skill shrunk={skill_item.shrunk_estimate:.4f} "
            f"n={skill_item.sample_count}; walk-forward research only"
        )
        evidence.append(
            lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.PARTICIPANT_INTELLIGENCE,
                    signal=EvidenceSignal(skill_item.cross_lane_signal),
                    strength="MODERATE",
                    available=True,
                    source_ref=f"participant:skill:{skill_item.skill_group_key}:buy_skill",
                    detail=detail,
                    quality_flags=skill_item.quality_flags,
                    provenance_class=EvidenceProvenanceClass.DERIVED,
                )
            )
        )
    return evidence


def build_metaorder_evidence_envelope(item: MetaorderEvidence) -> ParticipantEvidenceEnvelope:
    """Wrap PI6 metaorder evidence in cross-lane envelope."""
    return ParticipantEvidenceEnvelope(
        evidence_id=item.evidence_id,
        producer=PRODUCER_ID,
        producer_version=item.producer_version,
        event_time=item.event_time,
        available_time=item.available_time,
        participant_id=item.participant_id,
        participant_type=item.participant_type,
        identity_confidence=item.identity_confidence,
        mechanism=item.mechanism,
        mechanism_confidence=None,
        directional_clarity=DirectionalClarity.CLEAR
        if item.lifecycle_state.value == "ACTIVE"
        else DirectionalClarity.AMBIGUOUS,
        horizon=item.horizon,
        freshness_hours=None,
        research_classification=item.research_classification,
        provenance_class="DERIVED",
        source_provenance="order_flow:metaorder_primitive",
        quality_flags=item.quality_flags,
        payload_type="MetaorderEvidence",
        payload=metaorder_evidence_to_dict(item),
    )


def publish_metaorder_signals(items: list[MetaorderEvidence]) -> list[dict[str, Any]]:
    """Publish PI6 metaorder cross-lane signals when lifecycle gates pass."""
    evidence: list[dict[str, Any]] = []
    for item in items:
        if item.cross_lane_signal is None:
            continue
        if item.lifecycle_state.value == "INSUFFICIENT_INFORMATION":
            continue
        detail = (
            f"{item.instrument_id} metaorder {item.lifecycle_state.value} "
            f"signed_volume={item.signed_volume:.0f}; research only"
        )
        evidence.append(
            lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.PARTICIPANT_INTELLIGENCE,
                    signal=EvidenceSignal(item.cross_lane_signal),
                    strength="MODERATE",
                    available=True,
                    source_ref=f"participant:metaorder:{item.primitive_id}",
                    detail=detail,
                    quality_flags=item.quality_flags,
                    provenance_class=EvidenceProvenanceClass.DERIVED,
                )
            )
        )
    return evidence


def build_derivative_evidence_envelope(item: DerivativeParticipantEvidence) -> ParticipantEvidenceEnvelope:
    """Wrap PI12 derivative participant evidence in cross-lane envelope."""
    directional_clarity = (
        DirectionalClarity.CLEAR
        if item.flow_regime.value == "CONFIRMED_DIRECTIONAL"
        else DirectionalClarity.AMBIGUOUS
    )
    return ParticipantEvidenceEnvelope(
        evidence_id=item.evidence_id,
        producer=PRODUCER_ID,
        producer_version=item.producer_version,
        event_time=item.event_time,
        available_time=item.available_time,
        participant_id=item.participant_id,
        participant_type=item.participant_type,
        identity_confidence=item.identity_confidence,
        mechanism=item.mechanism,
        mechanism_confidence=None,
        directional_clarity=directional_clarity,
        horizon=item.horizon,
        freshness_hours=None,
        research_classification=item.research_classification,
        provenance_class=EvidenceProvenanceClass.DERIVED.value,
        source_provenance="options:signed_flow",
        quality_flags=item.quality_flags,
        payload_type="DerivativeParticipantEvidence",
        payload=derivative_participant_evidence_to_dict(item),
    )


def publish_derivatives_signals(
    items: list[DerivativeParticipantEvidence],
    *,
    prediction_cutoff: int,
) -> list[dict[str, Any]]:
    """Publish PI12 derivatives participant cross-lane signals when gates pass."""
    evidence: list[dict[str, Any]] = []
    for item in items:
        if item.cross_lane_signal is None:
            continue
        if iso_to_epoch_ns(item.available_time) > prediction_cutoff:
            continue
        if item.flow_regime.value == "INSUFFICIENT_DATA":
            continue
        detail = (
            f"{item.instrument_id} derivatives flow_regime={item.flow_regime.value} "
            f"confirmed_trades={item.confirmed_trade_count}; anonymous scale research only"
        )
        evidence.append(
            lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.PARTICIPANT_INTELLIGENCE,
                    signal=EvidenceSignal(item.cross_lane_signal),
                    strength="MODERATE",
                    available=True,
                    source_ref=f"participant:derivatives:{item.instrument_id}",
                    detail=detail,
                    observed_at=item.available_time,
                    quality_flags=item.quality_flags,
                    provenance_class=EvidenceProvenanceClass.DERIVED,
                )
            )
        )
    return evidence


def build_forced_flow_evidence_envelope(item: ForcedFlowEvidence) -> ParticipantEvidenceEnvelope:
    """Wrap PI13 forced-flow evidence in cross-lane envelope."""
    directional_clarity = (
        DirectionalClarity.AMBIGUOUS
        if item.flow_regime.value == "DISLOCATION_AMBIGUOUS"
        else DirectionalClarity.UNKNOWN
        if item.flow_regime.value == "INSUFFICIENT_DATA"
        else DirectionalClarity.CLEAR
    )
    return ParticipantEvidenceEnvelope(
        evidence_id=item.evidence_id,
        producer=PRODUCER_ID,
        producer_version=item.producer_version,
        event_time=item.event_time,
        available_time=item.available_time,
        participant_id=item.participant_id,
        participant_type=item.participant_type,
        identity_confidence=item.identity_confidence,
        mechanism=item.mechanism,
        mechanism_confidence=None,
        directional_clarity=directional_clarity,
        horizon=item.horizon,
        freshness_hours=None,
        research_classification=item.research_classification,
        provenance_class=EvidenceProvenanceClass.DERIVED.value,
        source_provenance="participant:forced_flow",
        quality_flags=item.quality_flags,
        payload_type="ForcedFlowEvidence",
        payload=forced_flow_evidence_to_dict(item),
    )


def publish_forced_flow_signals(
    items: list[ForcedFlowEvidence],
    *,
    prediction_cutoff: int,
) -> list[dict[str, Any]]:
    """Publish PI13 forced-flow cross-lane signals when gates pass."""
    evidence: list[dict[str, Any]] = []
    for item in items:
        if item.cross_lane_signal is None:
            continue
        if iso_to_epoch_ns(item.available_time) > prediction_cutoff:
            continue
        if item.flow_regime.value != "FORCED_FLOW_LIKELY":
            continue
        detail = (
            f"{item.instrument_id} forced_flow_regime={item.flow_regime.value} "
            f"metaorder={item.metaorder_lifecycle_state}; fade research only"
        )
        evidence.append(
            lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.PARTICIPANT_INTELLIGENCE,
                    signal=EvidenceSignal(item.cross_lane_signal),
                    strength="MODERATE",
                    available=True,
                    source_ref=f"participant:forced_flow:{item.instrument_id}",
                    detail=detail,
                    observed_at=item.available_time,
                    quality_flags=item.quality_flags,
                    provenance_class=EvidenceProvenanceClass.DERIVED,
                )
            )
        )
    return evidence
