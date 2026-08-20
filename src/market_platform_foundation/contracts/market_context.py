"""Market Context / Information Intelligence canonical contracts (MC1 foundation).

Sentiment is one intermediate feature. Semantic sentiment, economic surprise,
novelty, materiality, credibility, attention, and market reaction are modeled
separately. Missing data must not collapse to neutral defaults.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any

from .identity import NAMESPACE


CONTRACT_SCHEMA_VERSION = "market_context.v1"


class PublicationState(StrEnum):
    PUBLISHED = "PUBLISHED"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"


class InformationSourceType(StrEnum):
    REGULATORY_FILING = "REGULATORY_FILING"
    COMPANY_RELEASE = "COMPANY_RELEASE"
    EXCHANGE_NOTICE = "EXCHANGE_NOTICE"
    GOVERNMENT_RELEASE = "GOVERNMENT_RELEASE"
    COURT_DOCUMENT = "COURT_DOCUMENT"
    NEWSWIRE = "NEWSWIRE"
    FINANCIAL_MEDIA = "FINANCIAL_MEDIA"
    ANALYST = "ANALYST"
    INDUSTRY_SOURCE = "INDUSTRY_SOURCE"
    SOCIAL = "SOCIAL"
    BLOG = "BLOG"
    FORUM = "FORUM"
    RUMOR = "RUMOR"
    OTHER = "OTHER"


class InformationOriginClass(StrEnum):
    PRIMARY_INFORMATION = "PRIMARY_INFORMATION"
    PRIMARY_FILING = "PRIMARY_FILING"
    OFFICIAL_RELEASE = "OFFICIAL_RELEASE"
    ANALYSIS_OF_NEW_INFORMATION = "ANALYSIS_OF_NEW_INFORMATION"
    REACTION_TO_MARKET_MOVE = "REACTION_TO_MARKET_MOVE"
    COMMENTARY = "COMMENTARY"
    RECAP = "RECAP"
    OPINION = "OPINION"
    RUMOR = "RUMOR"
    SOCIAL_REACTION = "SOCIAL_REACTION"


class TimingClass(StrEnum):
    PRE_PRICE_INFORMATION = "PRE_PRICE_INFORMATION"
    CONTEMPORANEOUS_INFORMATION = "CONTEMPORANEOUS_INFORMATION"
    POST_PRICE_COMMENTARY = "POST_PRICE_COMMENTARY"
    UNKNOWN = "UNKNOWN"


class CorroborationState(StrEnum):
    UNVERIFIED = "UNVERIFIED"
    PARTIALLY_CORROBORATED = "PARTIALLY_CORROBORATED"
    CORROBORATED = "CORROBORATED"
    CONFIRMED = "CONFIRMED"
    DENIED = "DENIED"
    RETRACTED = "RETRACTED"


class VerificationStatus(StrEnum):
    UNVERIFIED = "UNVERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    VERIFIED = "VERIFIED"
    DISPUTED = "DISPUTED"
    RETRACTED = "RETRACTED"


class SemanticSentimentLabel(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class BaselineSentimentModel(StrEnum):
    """Canonical baseline financial sentiment models — not trade direction."""

    FINBERT_BASELINE = "BaselineFinancialSentiment/FinBERT"
    KEYWORD_BASELINE = "BaselineFinancialSentiment/keyword-v1"
    LEXICON_BASELINE = "BaselineFinancialSentiment/lexicon-v1"


class EconomicChannel(StrEnum):
    REVENUE_UP = "REVENUE_UP"
    REVENUE_DOWN = "REVENUE_DOWN"
    DEMAND_UP = "DEMAND_UP"
    DEMAND_DOWN = "DEMAND_DOWN"
    COST_UP = "COST_UP"
    COST_DOWN = "COST_DOWN"
    MARGIN_UP = "MARGIN_UP"
    MARGIN_DOWN = "MARGIN_DOWN"
    CAPEX_UP = "CAPEX_UP"
    CAPEX_DOWN = "CAPEX_DOWN"
    LIQUIDITY_RISK_UP = "LIQUIDITY_RISK_UP"
    LIQUIDITY_RISK_DOWN = "LIQUIDITY_RISK_DOWN"
    DEFAULT_RISK_UP = "DEFAULT_RISK_UP"
    DEFAULT_RISK_DOWN = "DEFAULT_RISK_DOWN"
    DILUTION_UP = "DILUTION_UP"
    REGULATORY_RISK_UP = "REGULATORY_RISK_UP"
    REGULATORY_RISK_DOWN = "REGULATORY_RISK_DOWN"
    COMPETITIVE_POSITION_UP = "COMPETITIVE_POSITION_UP"
    COMPETITIVE_POSITION_DOWN = "COMPETITIVE_POSITION_DOWN"
    ADDRESSABLE_MARKET_UP = "ADDRESSABLE_MARKET_UP"
    ADDRESSABLE_MARKET_DOWN = "ADDRESSABLE_MARKET_DOWN"
    SUPPLY_CONSTRAINT_UP = "SUPPLY_CONSTRAINT_UP"
    UNCERTAINTY_UP = "UNCERTAINTY_UP"
    UNCERTAINTY_DOWN = "UNCERTAINTY_DOWN"


class CompanyEventType(StrEnum):
    """Versioned company-event ontology — extensible, not exhaustive."""

    EARNINGS = "EARNINGS"
    GUIDANCE = "GUIDANCE"
    REVENUE = "REVENUE"
    MARGIN = "MARGIN"
    CONTRACT_WIN = "CONTRACT_WIN"
    CONTRACT_LOSS = "CONTRACT_LOSS"
    PRODUCT_LAUNCH = "PRODUCT_LAUNCH"
    PRODUCT_FAILURE = "PRODUCT_FAILURE"
    REGULATORY_APPROVAL = "REGULATORY_APPROVAL"
    REGULATORY_REJECTION = "REGULATORY_REJECTION"
    FDA_APPROVAL = "FDA_APPROVAL"
    FDA_REJECTION = "FDA_REJECTION"
    MERGER = "MERGER"
    ACQUISITION = "ACQUISITION"
    DIVESTITURE = "DIVESTITURE"
    FINANCING = "FINANCING"
    DEBT_REFINANCING = "DEBT_REFINANCING"
    EQUITY_ISSUANCE = "EQUITY_ISSUANCE"
    BUYBACK = "BUYBACK"
    DIVIDEND = "DIVIDEND"
    MANAGEMENT_CHANGE = "MANAGEMENT_CHANGE"
    CEO_CHANGE = "CEO_CHANGE"
    LEGAL_WIN = "LEGAL_WIN"
    LEGAL_LOSS = "LEGAL_LOSS"
    BANKRUPTCY = "BANKRUPTCY"
    RESTRUCTURING = "RESTRUCTURING"
    LAYOFF = "LAYOFF"
    CYBERSECURITY_INCIDENT = "CYBERSECURITY_INCIDENT"
    FRAUD_ALLEGATION = "FRAUD_ALLEGATION"
    ACCOUNTING_ISSUE = "ACCOUNTING_ISSUE"
    ANALYST_UPGRADE = "ANALYST_UPGRADE"
    ANALYST_DOWNGRADE = "ANALYST_DOWNGRADE"
    ACTIVIST_INVOLVEMENT = "ACTIVIST_INVOLVEMENT"
    INSIDER_TRANSACTION = "INSIDER_TRANSACTION"
    OTHER = "OTHER"


class MacroEventType(StrEnum):
    CPI = "CPI"
    PCE = "PCE"
    NFP = "NFP"
    UNEMPLOYMENT = "UNEMPLOYMENT"
    JOBLESS_CLAIMS = "JOBLESS_CLAIMS"
    GDP = "GDP"
    PMI = "PMI"
    ISM = "ISM"
    RETAIL_SALES = "RETAIL_SALES"
    FOMC_DECISION = "FOMC_DECISION"
    FOMC_MINUTES = "FOMC_MINUTES"
    CENTRAL_BANK_SPEECH = "CENTRAL_BANK_SPEECH"
    TREASURY_AUCTION = "TREASURY_AUCTION"
    ENERGY_INVENTORY = "ENERGY_INVENTORY"
    OPEC_DECISION = "OPEC_DECISION"
    TARIFF = "TARIFF"
    SANCTION = "SANCTION"
    ELECTION = "ELECTION"
    GEOPOLITICAL_EVENT = "GEOPOLITICAL_EVENT"
    REGULATORY_CHANGE = "REGULATORY_CHANGE"
    OTHER = "OTHER"


class ReactionConfirmationState(StrEnum):
    CONFIRMED = "CONFIRMED"
    PARTIALLY_CONFIRMED = "PARTIALLY_CONFIRMED"
    MIXED = "MIXED"
    CONTRADICTED = "CONTRADICTED"
    NO_MEANINGFUL_REACTION = "NO_MEANINGFUL_REACTION"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class InformationDecayClass(StrEnum):
    SECONDS = "SECONDS"
    MINUTES = "MINUTES"
    HOURS = "HOURS"
    DAYS = "DAYS"
    WEEKS = "WEEKS"
    STRUCTURAL = "STRUCTURAL"


class ContextQualityFlag(StrEnum):
    SOURCE_UNKNOWN = "SOURCE_UNKNOWN"
    SOURCE_LOW_CREDIBILITY = "SOURCE_LOW_CREDIBILITY"
    SOURCE_UNVERIFIED = "SOURCE_UNVERIFIED"
    EVENT_DUPLICATE = "EVENT_DUPLICATE"
    EVENT_CLUSTER_UNCERTAIN = "EVENT_CLUSTER_UNCERTAIN"
    ENTITY_AMBIGUOUS = "ENTITY_AMBIGUOUS"
    ENTITY_RESOLUTION_FAILED = "ENTITY_RESOLUTION_FAILED"
    NUMERIC_EXTRACTION_UNCERTAIN = "NUMERIC_EXTRACTION_UNCERTAIN"
    EXPECTATION_MISSING = "EXPECTATION_MISSING"
    EXPECTATION_STALE = "EXPECTATION_STALE"
    SURPRISE_UNAVAILABLE = "SURPRISE_UNAVAILABLE"
    NOVELTY_UNCERTAIN = "NOVELTY_UNCERTAIN"
    MATERIALITY_UNKNOWN = "MATERIALITY_UNKNOWN"
    CATALYST_COMPONENTS_INCOMPLETE = "CATALYST_COMPONENTS_INCOMPLETE"
    CORROBORATION_INCOMPLETE = "CORROBORATION_INCOMPLETE"
    SOCIAL_DATA_STALE = "SOCIAL_DATA_STALE"
    ATTENTION_DATA_PARTIAL = "ATTENTION_DATA_PARTIAL"
    ATTENTION_HISTORY_INSUFFICIENT = "ATTENTION_HISTORY_INSUFFICIENT"
    NARRATIVE_HISTORY_INSUFFICIENT = "NARRATIVE_HISTORY_INSUFFICIENT"
    NARRATIVE_DATA_PARTIAL = "NARRATIVE_DATA_PARTIAL"
    SOCIAL_ATTENTION_UNAVAILABLE = "SOCIAL_ATTENTION_UNAVAILABLE"
    LLM_EXTRACTION_LOW_CONFIDENCE = "LLM_EXTRACTION_LOW_CONFIDENCE"
    EXTRACTION_ENTITY_AMBIGUOUS = "EXTRACTION_ENTITY_AMBIGUOUS"
    EXTRACTION_METRIC_CONFLICT = "EXTRACTION_METRIC_CONFLICT"
    REVISION_LINEAGE_INCOMPLETE = "REVISION_LINEAGE_INCOMPLETE"
    MARKET_REACTION_DATA_MISSING = "MARKET_REACTION_DATA_MISSING"
    RETROSPECTIVE_KNOWLEDGE_RISK = "RETROSPECTIVE_KNOWLEDGE_RISK"


@dataclass(frozen=True, slots=True)
class ModelVersionRef:
    model_id: str
    model_version: str
    prompt_version: str | None = None
    schema_version: str = CONTRACT_SCHEMA_VERSION
    feature_version: str | None = None


@dataclass(frozen=True, slots=True)
class EvidenceSpan:
    source_document_id: str
    start_offset: int | None
    end_offset: int | None
    excerpt: str
    extraction_model: ModelVersionRef | None = None
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class InformationSource:
    source_id: str
    source_type: InformationSourceType
    publisher: str | None
    author: str | None
    domain: str | None
    primary_or_secondary: str | None
    official: bool
    first_party: bool
    source_tier: str | None
    source_origin_id: str | None
    syndication_parent_id: str | None
    provider: str
    event_time: str
    available_time: str
    ingested_time: str | None = None
    verification_state: VerificationStatus = VerificationStatus.UNVERIFIED
    historical_quality: float | None = None
    historical_informativeness: float | None = None
    provenance_ref: str = ""
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class RawDocument:
    document_id: str
    source: InformationSource
    title: str | None
    body: str | None
    url: str | None
    revision_id: str | None
    revision_of_document_id: str | None
    origin_class: InformationOriginClass
    timing_class: TimingClass = TimingClass.UNKNOWN
    associated_entity_ids: tuple[str, ...] = field(default_factory=tuple)
    associated_symbols: tuple[str, ...] = field(default_factory=tuple)
    event_time: str = ""
    available_time: str = ""
    ingested_time: str | None = None
    provenance_ref: str = ""
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class EntityClaim:
    """MC2 identity claim extracted from a raw document or provider row."""

    symbol: str | None = None
    issuer_name: str | None = None
    exchange: str | None = None
    security_type: str | None = None
    source_record_id: str = ""


@dataclass(frozen=True, slots=True)
class EntityResolution:
    entity_id: str | None
    instrument_ids: tuple[str, ...] = field(default_factory=tuple)
    resolution_confidence: float | None = None
    ambiguous: bool = False
    candidate_entity_ids: tuple[str, ...] = field(default_factory=tuple)
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


def entity_id_from_symbol(symbol: str, *, exchange: str = "US") -> str:
    """Deterministic entity identifier for fixture-scope symbol resolution."""
    normalized = "|".join(("entity", exchange.upper(), symbol.strip().upper()))
    return str(uuid.uuid5(NAMESPACE, normalized))


@dataclass(frozen=True, slots=True)
class BaselineFinancialSentiment:
    """Document- or span-level semantic sentiment — not economic surprise or trade direction."""

    target_entity_id: str | None
    label: SemanticSentimentLabel
    confidence: float | None
    uncertainty_score: float | None
    model: BaselineSentimentModel
    model_version: ModelVersionRef
    source_span: EvidenceSpan | None = None
    event_time: str = ""
    available_time: str = ""
    publication_state: PublicationState = PublicationState.UNAVAILABLE
    provenance_ref: str = ""
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class TargetedSentiment:
    """Entity-specific sentiment within a multi-entity document."""

    entity_id: str
    label: SemanticSentimentLabel
    confidence: float | None
    uncertainty_score: float | None
    direction_rationale: str | None = None
    source_span: EvidenceSpan | None = None
    model_version: ModelVersionRef | None = None
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ExtractedMetric:
    metric_name: str
    reported_value: Decimal | None
    units: str | None
    period: str | None
    currency: str | None
    comparison_period: str | None
    source_span: EvidenceSpan | None = None
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class InformationEvent:
    event_id: str
    canonical_event_type: str
    entity_ids: tuple[str, ...]
    document_ids: tuple[str, ...]
    first_known_time: str
    first_source_id: str | None
    event_time: str
    available_time: str
    document_count: int
    source_count: int
    independent_source_count: int | None
    corroboration_state: CorroborationState = CorroborationState.UNVERIFIED
    revision_lineage: tuple[str, ...] = field(default_factory=tuple)
    economic_channels: tuple[str, ...] = field(default_factory=tuple)
    extracted_metrics: tuple[ExtractedMetric, ...] = field(default_factory=tuple)
    publication_state: PublicationState = PublicationState.UNAVAILABLE
    provenance_ref: str = ""
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ExpectationSnapshot:
    metric_name: str
    entity_id: str | None
    expected_value: Decimal | None
    median: Decimal | None
    high: Decimal | None
    low: Decimal | None
    dispersion: Decimal | None
    sample_size: int | None
    source: str
    event_time: str
    available_time: str
    publication_state: PublicationState = PublicationState.UNAVAILABLE
    provenance_ref: str = ""
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class SurpriseEvidence:
    metric_name: str
    entity_id: str | None
    actual_value: Decimal | None
    expectation_snapshot_id: str | None
    surprise: Decimal | None
    surprise_percent: Decimal | None
    standardized_surprise: Decimal | None
    event_time: str
    available_time: str
    publication_state: PublicationState = PublicationState.UNAVAILABLE
    provenance_ref: str = ""
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class NoveltyEvidence:
    event_id: str
    novelty_score: float | None
    duplicate_probability: float | None
    incremental_information_score: float | None
    event_time: str
    available_time: str
    publication_state: PublicationState = PublicationState.UNAVAILABLE
    provenance_ref: str = ""
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class MaterialityEvidence:
    event_id: str
    entity_id: str | None
    materiality_score: float | None
    materiality_basis: str | None
    event_time: str
    available_time: str
    publication_state: PublicationState = PublicationState.UNAVAILABLE
    provenance_ref: str = ""
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class CredibilityEvidence:
    event_id: str
    source_credibility: float | None
    historical_signal_value: float | None
    corroboration_state: CorroborationState
    official_source_found: bool
    official_confirmation: bool
    official_denial: bool
    independent_source_count: int | None
    event_time: str
    available_time: str
    publication_state: PublicationState = PublicationState.UNAVAILABLE
    provenance_ref: str = ""
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class CatalystEvidence:
    """Semantic catalyst strength — separate from semantic sentiment."""

    event_id: str
    entity_ids: tuple[str, ...]
    catalyst_strength: float | None
    novelty_score: float | None
    surprise_score: float | None
    materiality_score: float | None
    credibility_score: float | None
    semantic_sentiment: SemanticSentimentLabel | None = None
    event_time: str = ""
    available_time: str = ""
    publication_state: PublicationState = PublicationState.UNAVAILABLE
    provenance_ref: str = ""
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ShortThesisInvalidationEvidence:
    entity_id: str
    affected_short_theses: tuple[str, ...]
    invalidation_strength: float | None
    confidence: float | None
    source_evidence_ids: tuple[str, ...] = field(default_factory=tuple)
    event_time: str = ""
    available_time: str = ""
    publication_state: PublicationState = PublicationState.UNAVAILABLE
    provenance_ref: str = ""
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class AttentionEvidence:
    entity_id: str
    attention_level: float | None
    attention_velocity: float | None
    attention_acceleration: float | None
    attention_zscore: float | None
    attention_percentile: float | None
    information_value: float | None
    reflexive_impact: float | None
    event_time: str
    available_time: str
    publication_state: PublicationState = PublicationState.UNAVAILABLE
    provenance_ref: str = ""
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class NarrativeEvidence:
    narrative_id: str
    narrative_text: str
    entity_ids: tuple[str, ...]
    prevalence: float | None
    velocity: float | None
    acceleration: float | None
    sentiment_dispersion: float | None
    narrative_dispersion: float | None
    event_time: str
    available_time: str
    publication_state: PublicationState = PublicationState.UNAVAILABLE
    provenance_ref: str = ""
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class MacroContextEvidence:
    growth_regime: str | None
    inflation_regime: str | None
    monetary_policy_regime: str | None
    risk_regime: str | None
    volatility_regime: str | None
    liquidity_regime: str | None
    event_time: str
    available_time: str
    publication_state: PublicationState = PublicationState.UNAVAILABLE
    provenance_ref: str = ""
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class MarketReactionEvidence:
    entity_id: str
    event_id: str | None
    semantic_direction: str | None
    predicted_economic_direction: str | None
    observed_market_direction: str | None
    reaction_mismatch: bool
    confirmation_state: ReactionConfirmationState
    abnormal_return: float | None
    volume_multiple: float | None
    priced_in_probability: float | None
    remaining_information_edge: float | None
    horizon: str | None
    event_time: str
    available_time: str
    publication_state: PublicationState = PublicationState.UNAVAILABLE
    provenance_ref: str = ""
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ContextEvidenceEnvelope:
    """Cross-lane evidence root for Market Context producers."""

    evidence_id: str
    producer: str
    producer_version: str
    event_time: str
    available_time: str
    confidence: float | None
    provenance_class: str
    source_provenance: str
    supporting_evidence_ids: tuple[str, ...] = field(default_factory=tuple)
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    payload_type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


def entity_resolution_to_dict(item: EntityResolution) -> dict[str, Any]:
    return {
        "entity_id": item.entity_id,
        "instrument_ids": list(item.instrument_ids),
        "resolution_confidence": item.resolution_confidence,
        "ambiguous": item.ambiguous,
        "candidate_entity_ids": list(item.candidate_entity_ids),
        "quality_flags": list(item.quality_flags),
    }


def information_event_to_dict(item: InformationEvent) -> dict[str, Any]:
    return {
        "event_id": item.event_id,
        "canonical_event_type": item.canonical_event_type,
        "entity_ids": list(item.entity_ids),
        "document_ids": list(item.document_ids),
        "first_known_time": item.first_known_time,
        "first_source_id": item.first_source_id,
        "event_time": item.event_time,
        "available_time": item.available_time,
        "document_count": item.document_count,
        "source_count": item.source_count,
        "independent_source_count": item.independent_source_count,
        "corroboration_state": item.corroboration_state.value,
        "revision_lineage": list(item.revision_lineage),
        "economic_channels": list(item.economic_channels),
        "extracted_metrics": [extracted_metric_to_dict(metric) for metric in item.extracted_metrics],
        "publication_state": item.publication_state.value,
        "provenance_ref": item.provenance_ref,
        "quality_flags": list(item.quality_flags),
    }


def extracted_metric_to_dict(item: ExtractedMetric) -> dict[str, Any]:
    return {
        "metric_name": item.metric_name,
        "reported_value": str(item.reported_value) if item.reported_value is not None else None,
        "units": item.units,
        "period": item.period,
        "currency": item.currency,
        "comparison_period": item.comparison_period,
        "quality_flags": list(item.quality_flags),
    }


def raw_document_to_dict(item: RawDocument) -> dict[str, Any]:
    return {
        "document_id": item.document_id,
        "title": item.title,
        "body": item.body,
        "url": item.url,
        "revision_id": item.revision_id,
        "revision_of_document_id": item.revision_of_document_id,
        "origin_class": item.origin_class.value,
        "timing_class": item.timing_class.value,
        "associated_entity_ids": list(item.associated_entity_ids),
        "associated_symbols": list(item.associated_symbols),
        "event_time": item.event_time,
        "available_time": item.available_time,
        "ingested_time": item.ingested_time,
        "provenance_ref": item.provenance_ref,
        "quality_flags": list(item.quality_flags),
    }


def baseline_sentiment_to_dict(item: BaselineFinancialSentiment) -> dict[str, Any]:
    return {
        "target_entity_id": item.target_entity_id,
        "label": item.label.value,
        "confidence": item.confidence,
        "uncertainty_score": item.uncertainty_score,
        "model": item.model.value,
        "model_version": {
            "model_id": item.model_version.model_id,
            "model_version": item.model_version.model_version,
            "prompt_version": item.model_version.prompt_version,
            "schema_version": item.model_version.schema_version,
            "feature_version": item.model_version.feature_version,
        },
        "event_time": item.event_time,
        "available_time": item.available_time,
        "publication_state": item.publication_state.value,
        "provenance_ref": item.provenance_ref,
        "quality_flags": list(item.quality_flags),
    }


def catalyst_evidence_to_dict(item: CatalystEvidence) -> dict[str, Any]:
    return {
        "event_id": item.event_id,
        "entity_ids": list(item.entity_ids),
        "catalyst_strength": item.catalyst_strength,
        "novelty_score": item.novelty_score,
        "surprise_score": item.surprise_score,
        "materiality_score": item.materiality_score,
        "credibility_score": item.credibility_score,
        "semantic_sentiment": item.semantic_sentiment.value if item.semantic_sentiment else None,
        "event_time": item.event_time,
        "available_time": item.available_time,
        "publication_state": item.publication_state.value,
        "provenance_ref": item.provenance_ref,
        "quality_flags": list(item.quality_flags),
    }


def novelty_evidence_to_dict(item: NoveltyEvidence) -> dict[str, Any]:
    return {
        "event_id": item.event_id,
        "novelty_score": item.novelty_score,
        "duplicate_probability": item.duplicate_probability,
        "incremental_information_score": item.incremental_information_score,
        "event_time": item.event_time,
        "available_time": item.available_time,
        "publication_state": item.publication_state.value,
        "provenance_ref": item.provenance_ref,
        "quality_flags": list(item.quality_flags),
    }


def materiality_evidence_to_dict(item: MaterialityEvidence) -> dict[str, Any]:
    return {
        "event_id": item.event_id,
        "entity_id": item.entity_id,
        "materiality_score": item.materiality_score,
        "materiality_basis": item.materiality_basis,
        "event_time": item.event_time,
        "available_time": item.available_time,
        "publication_state": item.publication_state.value,
        "provenance_ref": item.provenance_ref,
        "quality_flags": list(item.quality_flags),
    }


def credibility_evidence_to_dict(item: CredibilityEvidence) -> dict[str, Any]:
    return {
        "event_id": item.event_id,
        "source_credibility": item.source_credibility,
        "historical_signal_value": item.historical_signal_value,
        "corroboration_state": item.corroboration_state.value,
        "official_source_found": item.official_source_found,
        "official_confirmation": item.official_confirmation,
        "official_denial": item.official_denial,
        "independent_source_count": item.independent_source_count,
        "event_time": item.event_time,
        "available_time": item.available_time,
        "publication_state": item.publication_state.value,
        "provenance_ref": item.provenance_ref,
        "quality_flags": list(item.quality_flags),
    }


def attention_evidence_to_dict(item: AttentionEvidence) -> dict[str, Any]:
    return {
        "entity_id": item.entity_id,
        "attention_level": item.attention_level,
        "attention_velocity": item.attention_velocity,
        "attention_acceleration": item.attention_acceleration,
        "attention_zscore": item.attention_zscore,
        "attention_percentile": item.attention_percentile,
        "information_value": item.information_value,
        "reflexive_impact": item.reflexive_impact,
        "event_time": item.event_time,
        "available_time": item.available_time,
        "publication_state": item.publication_state.value,
        "provenance_ref": item.provenance_ref,
        "quality_flags": list(item.quality_flags),
    }


def narrative_evidence_to_dict(item: NarrativeEvidence) -> dict[str, Any]:
    return {
        "narrative_id": item.narrative_id,
        "narrative_text": item.narrative_text,
        "entity_ids": list(item.entity_ids),
        "prevalence": item.prevalence,
        "velocity": item.velocity,
        "acceleration": item.acceleration,
        "sentiment_dispersion": item.sentiment_dispersion,
        "narrative_dispersion": item.narrative_dispersion,
        "event_time": item.event_time,
        "available_time": item.available_time,
        "publication_state": item.publication_state.value,
        "provenance_ref": item.provenance_ref,
        "quality_flags": list(item.quality_flags),
    }


def market_reaction_evidence_to_dict(item: MarketReactionEvidence) -> dict[str, Any]:
    return {
        "entity_id": item.entity_id,
        "event_id": item.event_id,
        "semantic_direction": item.semantic_direction,
        "predicted_economic_direction": item.predicted_economic_direction,
        "observed_market_direction": item.observed_market_direction,
        "reaction_mismatch": item.reaction_mismatch,
        "confirmation_state": item.confirmation_state.value,
        "abnormal_return": item.abnormal_return,
        "volume_multiple": item.volume_multiple,
        "priced_in_probability": item.priced_in_probability,
        "remaining_information_edge": item.remaining_information_edge,
        "horizon": item.horizon,
        "event_time": item.event_time,
        "available_time": item.available_time,
        "publication_state": item.publication_state.value,
        "provenance_ref": item.provenance_ref,
        "quality_flags": list(item.quality_flags),
    }


def context_evidence_envelope_to_dict(item: ContextEvidenceEnvelope) -> dict[str, Any]:
    return {
        "evidence_id": item.evidence_id,
        "producer": item.producer,
        "producer_version": item.producer_version,
        "event_time": item.event_time,
        "available_time": item.available_time,
        "confidence": item.confidence,
        "provenance_class": item.provenance_class,
        "source_provenance": item.source_provenance,
        "supporting_evidence_ids": list(item.supporting_evidence_ids),
        "quality_flags": list(item.quality_flags),
        "payload_type": item.payload_type,
        "payload": dict(item.payload),
    }


def expectation_snapshot_to_dict(item: ExpectationSnapshot) -> dict[str, Any]:
    return {
        "metric_name": item.metric_name,
        "entity_id": item.entity_id,
        "expected_value": str(item.expected_value) if item.expected_value is not None else None,
        "median": str(item.median) if item.median is not None else None,
        "high": str(item.high) if item.high is not None else None,
        "low": str(item.low) if item.low is not None else None,
        "dispersion": str(item.dispersion) if item.dispersion is not None else None,
        "sample_size": item.sample_size,
        "source": item.source,
        "event_time": item.event_time,
        "available_time": item.available_time,
        "publication_state": item.publication_state.value,
        "provenance_ref": item.provenance_ref,
        "quality_flags": list(item.quality_flags),
    }


def surprise_evidence_to_dict(item: SurpriseEvidence) -> dict[str, Any]:
    return {
        "metric_name": item.metric_name,
        "entity_id": item.entity_id,
        "actual_value": str(item.actual_value) if item.actual_value is not None else None,
        "expectation_snapshot_id": item.expectation_snapshot_id,
        "surprise": str(item.surprise) if item.surprise is not None else None,
        "surprise_percent": str(item.surprise_percent) if item.surprise_percent is not None else None,
        "standardized_surprise": (
            str(item.standardized_surprise) if item.standardized_surprise is not None else None
        ),
        "event_time": item.event_time,
        "available_time": item.available_time,
        "publication_state": item.publication_state.value,
        "provenance_ref": item.provenance_ref,
        "quality_flags": list(item.quality_flags),
    }


def surprise_unavailable_when_expectation_missing(
    expectation: ExpectationSnapshot | None,
    *,
    actual_present: bool,
) -> tuple[SurpriseEvidence | None, tuple[str, ...]]:
    """Fail closed: missing expectation does not imply zero surprise."""
    flags: list[str] = []
    if expectation is None:
        flags.append(ContextQualityFlag.EXPECTATION_MISSING.value)
        flags.append(ContextQualityFlag.SURPRISE_UNAVAILABLE.value)
        return None, tuple(flags)
    if expectation.publication_state == PublicationState.STALE:
        flags.append(ContextQualityFlag.EXPECTATION_STALE.value)
    if not actual_present:
        flags.append(ContextQualityFlag.SURPRISE_UNAVAILABLE.value)
        return None, tuple(flags)
    return None, tuple(flags)
