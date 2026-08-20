"""Participant / Whale Intelligence canonical contracts (PI1–PI2 foundation).

Participant Intelligence owns participant-level identity, action semantics,
intent/mechanism inference contracts, skill, copyability, and cross-lane
evidence envelopes. It does NOT own CVD/OFI, options flow classification,
COT semantics, squeeze states, or news extraction.

Missing data must not collapse to neutral defaults.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .identity import NAMESPACE

CONTRACT_SCHEMA_VERSION = "participant.v1"


class ParticipantType(StrEnum):
    CORPORATE_INSIDER = "CORPORATE_INSIDER"
    ACTIVIST = "ACTIVIST"
    HEDGE_FUND = "HEDGE_FUND"
    MUTUAL_FUND = "MUTUAL_FUND"
    PENSION = "PENSION"
    ASSET_MANAGER = "ASSET_MANAGER"
    ETF = "ETF"
    INDEX_MANAGER = "INDEX_MANAGER"
    FAMILY_OFFICE = "FAMILY_OFFICE"
    MARKET_MAKER = "MARKET_MAKER"
    DEALER = "DEALER"
    PROP_TRADER = "PROP_TRADER"
    CTA = "CTA"
    COMMODITY_PRODUCER = "COMMODITY_PRODUCER"
    COMMERCIAL_HEDGER = "COMMERCIAL_HEDGER"
    MINER = "MINER"
    CORPORATE_TREASURY = "CORPORATE_TREASURY"
    SHORT_SELLER = "SHORT_SELLER"
    CRYPTO_WHALE = "CRYPTO_WHALE"
    CRYPTO_EXCHANGE = "CRYPTO_EXCHANGE"
    CRYPTO_CUSTODIAN = "CRYPTO_CUSTODIAN"
    CRYPTO_MARKET_MAKER = "CRYPTO_MARKET_MAKER"
    PROTOCOL_TREASURY = "PROTOCOL_TREASURY"
    PREDICTION_MARKET_PARTICIPANT = "PREDICTION_MARKET_PARTICIPANT"
    UNKNOWN_LARGE_PARTICIPANT = "UNKNOWN_LARGE_PARTICIPANT"
    UNKNOWN = "UNKNOWN"


class IdentityConfidence(StrEnum):
    KNOWN_IDENTITY = "KNOWN_IDENTITY"
    KNOWN_CATEGORY = "KNOWN_CATEGORY"
    PROBABLE_ENTITY = "PROBABLE_ENTITY"
    ANONYMOUS_INSTITUTIONAL_SCALE = "ANONYMOUS_INSTITUTIONAL_SCALE"
    UNKNOWN = "UNKNOWN"


class ParticipantResolutionMethod(StrEnum):
    REGULATORY_FILING_NAMED = "REGULATORY_FILING_NAMED"
    REGULATORY_FILING_CATEGORY = "REGULATORY_FILING_CATEGORY"
    WALLET_LABEL = "WALLET_LABEL"
    WALLET_CLUSTER = "WALLET_CLUSTER"
    FLOW_SCALE_INFERENCE = "FLOW_SCALE_INFERENCE"
    PROVIDER_ATTRIBUTION = "PROVIDER_ATTRIBUTION"
    MANUAL_CURATION = "MANUAL_CURATION"
    UNRESOLVED = "UNRESOLVED"


class ParticipantRelationshipType(StrEnum):
    OFFICER_OF = "officer_of"
    MANAGED_BY = "managed_by"
    OWNED_BY = "owned_by"
    CLUSTERED_WITH = "clustered_with"
    ATTRIBUTED_TO = "attributed_to"
    MEMBER_OF = "member_of"
    ADVISED_BY = "advised_by"


class ParticipantActionType(StrEnum):
    OPEN_MARKET_BUY = "OPEN_MARKET_BUY"
    OPEN_MARKET_SELL = "OPEN_MARKET_SELL"
    POSITION_INITIATED = "POSITION_INITIATED"
    POSITION_INCREASED = "POSITION_INCREASED"
    POSITION_REDUCED = "POSITION_REDUCED"
    POSITION_EXITED = "POSITION_EXITED"
    ACTIVIST_STAKE_INITIATED = "ACTIVIST_STAKE_INITIATED"
    ACTIVIST_STAKE_INCREASED = "ACTIVIST_STAKE_INCREASED"
    LARGE_FLOW_BUY = "LARGE_FLOW_BUY"
    LARGE_FLOW_SELL = "LARGE_FLOW_SELL"
    METAORDER_BUY = "METAORDER_BUY"
    METAORDER_SELL = "METAORDER_SELL"
    DERIVATIVE_POSITION = "DERIVATIVE_POSITION"
    FUTURES_POSITIONING_CHANGE = "FUTURES_POSITIONING_CHANGE"
    SHORT_POSITION = "SHORT_POSITION"
    CRYPTO_TRANSFER = "CRYPTO_TRANSFER"
    EXCHANGE_DEPOSIT = "EXCHANGE_DEPOSIT"
    EXCHANGE_WITHDRAWAL = "EXCHANGE_WITHDRAWAL"
    FORCED_LIQUIDATION = "FORCED_LIQUIDATION"
    REBALANCE = "REBALANCE"
    HEDGE = "HEDGE"
    INSIDER_OPTION_EXERCISE = "INSIDER_OPTION_EXERCISE"
    INSIDER_AWARD_GRANT = "INSIDER_AWARD_GRANT"
    INSIDER_TAX_WITHHOLDING = "INSIDER_TAX_WITHHOLDING"
    INSIDER_GIFT = "INSIDER_GIFT"
    INSIDER_CONVERSION = "INSIDER_CONVERSION"
    INSIDER_AUTOMATIC_PLAN = "INSIDER_AUTOMATIC_PLAN"
    INSTITUTIONAL_HOLDING_SNAPSHOT = "INSTITUTIONAL_HOLDING_SNAPSHOT"
    PUBLIC_STATEMENT = "PUBLIC_STATEMENT"
    UNKNOWN = "UNKNOWN"


class ActionDirection(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"
    AMBIGUOUS = "AMBIGUOUS"
    UNKNOWN = "UNKNOWN"


class DirectionalClarity(StrEnum):
    CLEAR = "CLEAR"
    PARTIAL = "PARTIAL"
    AMBIGUOUS = "AMBIGUOUS"
    UNKNOWN = "UNKNOWN"


class InsiderDiscretion(StrEnum):
    DISCRETIONARY = "DISCRETIONARY"
    PLAN_10B5_1 = "10B5_1_PLAN"
    COMPENSATION = "COMPENSATION"
    UNKNOWN = "UNKNOWN"


class ParticipantMechanism(StrEnum):
    INFORMED_DIRECTIONAL = "INFORMED_DIRECTIONAL"
    FUNDAMENTAL_CONVICTION = "FUNDAMENTAL_CONVICTION"
    STRATEGIC_CONTROL = "STRATEGIC_CONTROL"
    ACTIVIST_INFLUENCE = "ACTIVIST_INFLUENCE"
    MECHANICAL_FLOW = "MECHANICAL_FLOW"
    MOMENTUM_SYSTEMATIC = "MOMENTUM_SYSTEMATIC"
    PORTFOLIO_ALLOCATION = "PORTFOLIO_ALLOCATION"
    PASSIVE_INDEX = "PASSIVE_INDEX"
    REBALANCING = "REBALANCING"
    HEDGING = "HEDGING"
    MARKET_MAKING = "MARKET_MAKING"
    INVENTORY_MANAGEMENT = "INVENTORY_MANAGEMENT"
    FLOW_DRIVEN = "FLOW_DRIVEN"
    LIQUIDITY_NEED = "LIQUIDITY_NEED"
    FORCED_LIQUIDATION = "FORCED_LIQUIDATION"
    MARGIN_DELEVERAGING = "MARGIN_DELEVERAGING"
    TAX_PERSONAL = "TAX_PERSONAL"
    COMPENSATION = "COMPENSATION"
    REFLEXIVE_INFLUENCE = "REFLEXIVE_INFLUENCE"
    UNKNOWN = "UNKNOWN"


class ParticipantResearchClassification(StrEnum):
    ALIGNMENT_CANDIDATE = "ALIGNMENT_CANDIDATE"
    STRATEGIC_ALIGNMENT_CANDIDATE = "STRATEGIC_ALIGNMENT_CANDIDATE"
    FLOW_CONTINUATION_CANDIDATE = "FLOW_CONTINUATION_CANDIDATE"
    INFORMATIONAL_CONTEXT_ONLY = "INFORMATIONAL_CONTEXT_ONLY"
    PASSIVE_FLOW_LIKELY = "PASSIVE_FLOW_LIKELY"
    HEDGING_LIKELY = "HEDGING_LIKELY"
    FORCED_FLOW_LIKELY = "FORCED_FLOW_LIKELY"
    POST_FLOW_CONTRARIAN_CANDIDATE = "POST_FLOW_CONTRARIAN_CANDIDATE"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"


class ParticipantHorizon(StrEnum):
    MILLISECONDS = "MILLISECONDS"
    SECONDS_MINUTES = "SECONDS_MINUTES"
    INTRADAY = "INTRADAY"
    DAYS = "DAYS"
    WEEKS = "WEEKS"
    MONTHS = "MONTHS"
    YEARS = "YEARS"
    UNKNOWN = "UNKNOWN"


class MetaorderLifecycleState(StrEnum):
    """PI6 lifecycle interpretation — Participant-owned."""

    ACTIVE = "ACTIVE"
    LIKELY_COMPLETE = "LIKELY_COMPLETE"
    PAUSED = "PAUSED"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"


class SkillDimension(StrEnum):
    BUY_SKILL = "buy_skill"
    SELL_SKILL = "sell_skill"
    ACTIVISM_SUCCESS = "activism_success"


class ParticipantQualityFlag(StrEnum):
    PARTICIPANT_UNKNOWN = "PARTICIPANT_UNKNOWN"
    IDENTITY_LOW_CONFIDENCE = "IDENTITY_LOW_CONFIDENCE"
    ACTION_AMBIGUOUS = "ACTION_AMBIGUOUS"
    INTENT_UNKNOWN = "INTENT_UNKNOWN"
    INTENT_LOW_CONFIDENCE = "INTENT_LOW_CONFIDENCE"
    POSITION_STALE = "POSITION_STALE"
    DISCLOSURE_DELAYED = "DISCLOSURE_DELAYED"
    ENTRY_BASIS_UNKNOWN = "ENTRY_BASIS_UNKNOWN"
    HORIZON_UNKNOWN = "HORIZON_UNKNOWN"
    COPYABILITY_LOW = "COPYABILITY_LOW"
    CROWDING_DATA_STALE = "CROWDING_DATA_STALE"
    METAORDER_INFERENCE_LOW_CONFIDENCE = "METAORDER_INFERENCE_LOW_CONFIDENCE"
    WALLET_ENTITY_UNKNOWN = "WALLET_ENTITY_UNKNOWN"
    ENTITY_LABEL_RETROSPECTIVE = "ENTITY_LABEL_RETROSPECTIVE"
    FORCED_FLOW_UNCONFIRMED = "FORCED_FLOW_UNCONFIRMED"
    OPTIONS_DIRECTION_UNRESOLVED = "OPTIONS_DIRECTION_UNRESOLVED"
    OWNERSHIP_DELTA_UNAVAILABLE = "OWNERSHIP_DELTA_UNAVAILABLE"
    QUARTER_END_NOT_COPYABLE = "QUARTER_END_NOT_COPYABLE"
    SKILL_INSUFFICIENT_SAMPLE = "SKILL_INSUFFICIENT_SAMPLE"
    SKILL_STALE = "SKILL_STALE"
    OUTCOME_WINDOW_INCOMPLETE = "OUTCOME_WINDOW_INCOMPLETE"
    CATALYST_CONTEXT_MISSING = "CATALYST_CONTEXT_MISSING"


class ResearchStatus(StrEnum):
    RESEARCHED = "RESEARCHED"
    IMPLEMENTED = "IMPLEMENTED"
    VALIDATED = "VALIDATED"
    EXPERIMENTAL = "EXPERIMENTAL"
    UNAVAILABLE = "UNAVAILABLE"


FORM4_TRANSACTION_ACTION_MAP: dict[str, ParticipantActionType] = {
    "P": ParticipantActionType.OPEN_MARKET_BUY,
    "A": ParticipantActionType.OPEN_MARKET_BUY,
    "S": ParticipantActionType.OPEN_MARKET_SELL,
    "D": ParticipantActionType.OPEN_MARKET_SELL,
    "M": ParticipantActionType.OPEN_MARKET_SELL,
    "F": ParticipantActionType.INSIDER_TAX_WITHHOLDING,
    "G": ParticipantActionType.INSIDER_GIFT,
    "C": ParticipantActionType.INSIDER_CONVERSION,
    "E": ParticipantActionType.INSIDER_OPTION_EXERCISE,
    "I": ParticipantActionType.INSIDER_AWARD_GRANT,
}


def participant_id_from_source(
    *,
    source: str,
    source_record_id: str,
    participant_label: str,
) -> str:
    name = "|".join(("participant", source, source_record_id, participant_label))
    return str(uuid.uuid5(NAMESPACE, name))


@dataclass(frozen=True, slots=True)
class ParticipantIdentity:
    participant_id: str
    display_name: str
    participant_type: ParticipantType
    identity_confidence: IdentityConfidence
    resolution_method: ParticipantResolutionMethod
    source: str
    label_available_time: str | None = None
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ParticipantRelationship:
    from_entity_id: str
    to_entity_id: str
    relationship_type: ParticipantRelationshipType
    confidence: float | None
    available_time: str
    source: str


@dataclass(frozen=True, slots=True)
class InstitutionalHoldingLine:
    """Single 13F InfoTable line — PI4."""

    cusip: str
    issuer_name: str
    shares: float
    value_usd: float | None
    symbol: str | None = None
    put_call: str | None = None


@dataclass(frozen=True, slots=True)
class InstitutionalHoldingSnapshot:
    """13F filing context for a holding line — PI4."""

    quarter_end: str
    accession_number: str
    holding_line: InstitutionalHoldingLine


THIRTEEN_F_LIMITATIONS: tuple[str, ...] = ("shorts_omitted", "hedges_omitted")


@dataclass(frozen=True, slots=True)
class ParticipantAction:
    """Canonical participant action — PI2."""

    action_id: str
    participant_id: str
    participant_type: ParticipantType
    instrument_id: str
    asset_class: str
    action_type: ParticipantActionType
    direction: ActionDirection
    directional_clarity: DirectionalClarity
    quantity: float | None
    notional: float | None
    transaction_price: float | None
    estimated_basis: float | None
    basis_confidence: float | None
    action_time: str
    event_time: str
    available_time: str
    ingested_time: str | None
    source: str
    source_record_id: str
    identity_confidence: IdentityConfidence
    insider_discretion: InsiderDiscretion | None = None
    form_type: str | None = None
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    provenance_ref: str = ""


@dataclass(frozen=True, slots=True)
class SkillEstimate:
    """Single skill dimension estimate — PI5."""

    dimension: SkillDimension
    raw_mean: float | None
    shrunk_estimate: float | None
    sample_count: int
    outcome_window_days: int
    prior: float
    shrinkage_k: int
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ParticipantSkillSnapshot:
    """Walk-forward skill rollup for one participant group at prediction_cutoff — PI5."""

    skill_group_key: str
    participant_id: str
    display_name: str
    participant_type: ParticipantType
    prediction_cutoff: int
    estimates: tuple[SkillEstimate, ...]
    walk_forward_fold_count: int
    producer_version: str
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class MetaorderEvidence:
    """PI6 metaorder lifecycle evidence — no invented participant identity."""

    evidence_id: str
    primitive_id: str
    instrument_id: str
    venue: str
    lifecycle_state: MetaorderLifecycleState
    aggressor_side: str
    signed_volume: float
    trade_count: int
    event_time: str
    available_time: str
    participant_id: str
    participant_type: ParticipantType
    identity_confidence: IdentityConfidence
    mechanism: ParticipantMechanism
    research_classification: ParticipantResearchClassification
    horizon: ParticipantHorizon
    mbo_corroborated: bool
    producer_version: str
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    cross_lane_signal: str | None = None


@dataclass(frozen=True, slots=True)
class MechanismHypothesis:
    mechanism: ParticipantMechanism
    probability: float | None
    rationale: str


@dataclass(frozen=True, slots=True)
class MechanismInference:
    """PI7 contract stub — alternatives required when plausible."""

    primary_mechanism: ParticipantMechanism
    mechanism_probability: float | None
    intent_confidence: float | None
    alternative_explanations: tuple[MechanismHypothesis, ...] = field(default_factory=tuple)
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ContextualIntentEvidence:
    """PI8 contextual intent — participant action timing relative to catalyst windows."""

    action_id: str
    participant_id: str
    catalyst_event_id: str | None
    timing_relation: str
    intent_classification: str
    days_offset_from_catalyst: float | None
    event_time: str
    available_time: str
    producer_version: str
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    cross_lane_signal: str | None = None


@dataclass(frozen=True, slots=True)
class ParticipantEvidenceEnvelope:
    """Cross-lane evidence root for Participant Intelligence producers."""

    evidence_id: str
    producer: str
    producer_version: str
    event_time: str
    available_time: str
    participant_id: str
    participant_type: ParticipantType
    identity_confidence: IdentityConfidence
    mechanism: ParticipantMechanism
    mechanism_confidence: float | None
    directional_clarity: DirectionalClarity
    horizon: ParticipantHorizon
    freshness_hours: float | None
    research_classification: ParticipantResearchClassification
    provenance_class: str
    source_provenance: str
    supporting_evidence_ids: tuple[str, ...] = field(default_factory=tuple)
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    payload_type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


def infer_participant_type_from_form(form_type: str) -> ParticipantType:
    normalized = form_type.upper().replace("/A", "")
    if normalized == "4":
        return ParticipantType.CORPORATE_INSIDER
    if normalized == "13D":
        return ParticipantType.ACTIVIST
    if normalized == "13G":
        return ParticipantType.ASSET_MANAGER
    if normalized.startswith("13F"):
        return ParticipantType.HEDGE_FUND
    if normalized == "3":
        return ParticipantType.CORPORATE_INSIDER
    return ParticipantType.UNKNOWN


def infer_action_from_form4_transaction(
    transaction_code: str | None,
) -> tuple[ParticipantActionType, ActionDirection, DirectionalClarity]:
    if not transaction_code:
        return (
            ParticipantActionType.UNKNOWN,
            ActionDirection.UNKNOWN,
            DirectionalClarity.UNKNOWN,
        )
    code = transaction_code.upper()
    action = FORM4_TRANSACTION_ACTION_MAP.get(code, ParticipantActionType.UNKNOWN)
    if action == ParticipantActionType.OPEN_MARKET_BUY:
        return action, ActionDirection.BUY, DirectionalClarity.CLEAR
    if action == ParticipantActionType.OPEN_MARKET_SELL:
        return action, ActionDirection.SELL, DirectionalClarity.CLEAR
    if action in {
        ParticipantActionType.INSIDER_TAX_WITHHOLDING,
        ParticipantActionType.INSIDER_GIFT,
        ParticipantActionType.INSIDER_AWARD_GRANT,
        ParticipantActionType.INSIDER_OPTION_EXERCISE,
        ParticipantActionType.INSIDER_CONVERSION,
    }:
        return action, ActionDirection.AMBIGUOUS, DirectionalClarity.AMBIGUOUS
    return ParticipantActionType.UNKNOWN, ActionDirection.UNKNOWN, DirectionalClarity.UNKNOWN


def infer_action_from_disclosure(
    *,
    form_type: str,
    event_type: str,
    transaction_code: str | None,
) -> tuple[ParticipantActionType, ActionDirection, DirectionalClarity]:
    normalized_form = form_type.upper().replace("/A", "")
    if normalized_form == "4":
        return infer_action_from_form4_transaction(transaction_code)
    if normalized_form == "13D":
        return (
            ParticipantActionType.ACTIVIST_STAKE_INITIATED,
            ActionDirection.LONG,
            DirectionalClarity.PARTIAL,
        )
    if normalized_form == "13G":
        return (
            ParticipantActionType.INSTITUTIONAL_HOLDING_SNAPSHOT,
            ActionDirection.NEUTRAL,
            DirectionalClarity.AMBIGUOUS,
        )
    if normalized_form.startswith("13F"):
        return (
            ParticipantActionType.INSTITUTIONAL_HOLDING_SNAPSHOT,
            ActionDirection.NEUTRAL,
            DirectionalClarity.AMBIGUOUS,
        )
    if event_type == "public_statement":
        return (
            ParticipantActionType.PUBLIC_STATEMENT,
            ActionDirection.AMBIGUOUS,
            DirectionalClarity.AMBIGUOUS,
        )
    return ParticipantActionType.UNKNOWN, ActionDirection.UNKNOWN, DirectionalClarity.UNKNOWN


def disclosure_quality_flags(
    *,
    form_type: str,
    transaction_code: str | None,
    available_time: str,
    action_time: str,
) -> tuple[str, ...]:
    flags: list[str] = []
    normalized_form = form_type.upper().replace("/A", "")
    flags.append(ParticipantQualityFlag.DISCLOSURE_DELAYED.value)
    if normalized_form.startswith("13F"):
        flags.append(ParticipantQualityFlag.QUARTER_END_NOT_COPYABLE.value)
        flags.append(ParticipantQualityFlag.ENTRY_BASIS_UNKNOWN.value)
        flags.append(ParticipantQualityFlag.POSITION_STALE.value)
    if normalized_form == "4" and transaction_code is None:
        flags.append(ParticipantQualityFlag.ACTION_AMBIGUOUS.value)
    if normalized_form == "4" and transaction_code and transaction_code.upper() not in {
        "P",
        "A",
        "S",
    }:
        flags.append(ParticipantQualityFlag.ACTION_AMBIGUOUS.value)
        flags.append(ParticipantQualityFlag.INTENT_UNKNOWN.value)
    if available_time != action_time:
        flags.append(ParticipantQualityFlag.DISCLOSURE_DELAYED.value)
    flags.append(ParticipantQualityFlag.OWNERSHIP_DELTA_UNAVAILABLE.value)
    flags.append(ParticipantQualityFlag.ENTRY_BASIS_UNKNOWN.value)
    return tuple(sorted(set(flags)))


def participant_identity_to_dict(item: ParticipantIdentity) -> dict[str, Any]:
    return {
        "participant_id": item.participant_id,
        "display_name": item.display_name,
        "participant_type": item.participant_type.value,
        "identity_confidence": item.identity_confidence.value,
        "resolution_method": item.resolution_method.value,
        "source": item.source,
        "label_available_time": item.label_available_time,
        "quality_flags": list(item.quality_flags),
    }


def participant_action_to_dict(item: ParticipantAction) -> dict[str, Any]:
    return {
        "action_id": item.action_id,
        "participant_id": item.participant_id,
        "participant_type": item.participant_type.value,
        "instrument_id": item.instrument_id,
        "asset_class": item.asset_class,
        "action_type": item.action_type.value,
        "direction": item.direction.value,
        "directional_clarity": item.directional_clarity.value,
        "quantity": item.quantity,
        "notional": item.notional,
        "transaction_price": item.transaction_price,
        "estimated_basis": item.estimated_basis,
        "basis_confidence": item.basis_confidence,
        "action_time": item.action_time,
        "event_time": item.event_time,
        "available_time": item.available_time,
        "ingested_time": item.ingested_time,
        "source": item.source,
        "source_record_id": item.source_record_id,
        "identity_confidence": item.identity_confidence.value,
        "insider_discretion": item.insider_discretion.value if item.insider_discretion else None,
        "form_type": item.form_type,
        "quality_flags": list(item.quality_flags),
        "provenance_ref": item.provenance_ref,
        "schema_version": CONTRACT_SCHEMA_VERSION,
    }


def skill_estimate_to_dict(item: SkillEstimate) -> dict[str, Any]:
    return {
        "dimension": item.dimension.value,
        "raw_mean": item.raw_mean,
        "shrunk_estimate": item.shrunk_estimate,
        "sample_count": item.sample_count,
        "outcome_window_days": item.outcome_window_days,
        "prior": item.prior,
        "shrinkage_k": item.shrinkage_k,
        "quality_flags": list(item.quality_flags),
    }


def participant_skill_snapshot_to_dict(item: ParticipantSkillSnapshot) -> dict[str, Any]:
    return {
        "skill_group_key": item.skill_group_key,
        "participant_id": item.participant_id,
        "display_name": item.display_name,
        "participant_type": item.participant_type.value,
        "prediction_cutoff": item.prediction_cutoff,
        "estimates": [skill_estimate_to_dict(row) for row in item.estimates],
        "walk_forward_fold_count": item.walk_forward_fold_count,
        "producer_version": item.producer_version,
        "quality_flags": list(item.quality_flags),
        "schema_version": CONTRACT_SCHEMA_VERSION,
    }


def metaorder_evidence_to_dict(item: MetaorderEvidence) -> dict[str, Any]:
    return {
        "evidence_id": item.evidence_id,
        "primitive_id": item.primitive_id,
        "instrument_id": item.instrument_id,
        "venue": item.venue,
        "lifecycle_state": item.lifecycle_state.value,
        "aggressor_side": item.aggressor_side,
        "signed_volume": item.signed_volume,
        "trade_count": item.trade_count,
        "event_time": item.event_time,
        "available_time": item.available_time,
        "participant_id": item.participant_id,
        "participant_type": item.participant_type.value,
        "identity_confidence": item.identity_confidence.value,
        "mechanism": item.mechanism.value,
        "research_classification": item.research_classification.value,
        "horizon": item.horizon.value,
        "mbo_corroborated": item.mbo_corroborated,
        "producer_version": item.producer_version,
        "quality_flags": list(item.quality_flags),
        "cross_lane_signal": item.cross_lane_signal,
        "schema_version": CONTRACT_SCHEMA_VERSION,
    }


def contextual_intent_evidence_to_dict(item: ContextualIntentEvidence) -> dict[str, Any]:
    return {
        "action_id": item.action_id,
        "participant_id": item.participant_id,
        "catalyst_event_id": item.catalyst_event_id,
        "timing_relation": item.timing_relation,
        "intent_classification": item.intent_classification,
        "days_offset_from_catalyst": item.days_offset_from_catalyst,
        "event_time": item.event_time,
        "available_time": item.available_time,
        "producer_version": item.producer_version,
        "quality_flags": list(item.quality_flags),
        "cross_lane_signal": item.cross_lane_signal,
        "payload_type": "ContextualIntentEvidence",
        "schema_version": CONTRACT_SCHEMA_VERSION,
    }


def participant_evidence_envelope_to_dict(item: ParticipantEvidenceEnvelope) -> dict[str, Any]:
    return {
        "evidence_id": item.evidence_id,
        "producer": item.producer,
        "producer_version": item.producer_version,
        "event_time": item.event_time,
        "available_time": item.available_time,
        "participant_id": item.participant_id,
        "participant_type": item.participant_type.value,
        "identity_confidence": item.identity_confidence.value,
        "mechanism": item.mechanism.value,
        "mechanism_confidence": item.mechanism_confidence,
        "directional_clarity": item.directional_clarity.value,
        "horizon": item.horizon.value,
        "freshness_hours": item.freshness_hours,
        "research_classification": item.research_classification.value,
        "provenance_class": item.provenance_class,
        "source_provenance": item.source_provenance,
        "supporting_evidence_ids": list(item.supporting_evidence_ids),
        "quality_flags": list(item.quality_flags),
        "payload_type": item.payload_type,
        "payload": dict(item.payload),
        "schema_version": CONTRACT_SCHEMA_VERSION,
    }


def mechanism_inference_unavailable() -> tuple[MechanismInference | None, tuple[str, ...]]:
    """Fail closed: unknown intent is not directional conviction."""
    flags = (
        ParticipantQualityFlag.INTENT_UNKNOWN.value,
        ParticipantQualityFlag.INTENT_LOW_CONFIDENCE.value,
    )
    return None, flags
