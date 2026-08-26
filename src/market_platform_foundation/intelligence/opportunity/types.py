"""Opportunity governance contracts (BUILD 21)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION, ContractReference, IntelligenceScope
from ..contracts.opportunity import OpportunityV1
from ..evaluation.types import ProbabilityView
from ..fusion.types import FINAL_FORECAST_STAGE
from ..promotion.types import ChampionScopeV1
from ..quality.models import DecisionAction, IntelligenceCapability, QualityDecision

OPPORTUNITY_IMPLEMENTATION_VERSION = "governed-opportunity-engine-v1"


class AssessmentAction(StrEnum):
    EMIT = "EMIT"
    SUPPRESS = "SUPPRESS"
    ABSTAIN = "ABSTAIN"
    FAIL_CLOSED = "FAIL_CLOSED"


class AssessmentReasonCode(StrEnum):
    OPPORTUNITY_EMITTED = "OPPORTUNITY_EMITTED"
    FORECAST_NOT_FROM_GOVERNED_CHAMPION = "FORECAST_NOT_FROM_GOVERNED_CHAMPION"
    CHAMPION_CHANGED_SINCE_FORECAST = "CHAMPION_CHANGED_SINCE_FORECAST"
    CHAMPION_NOT_EFFECTIVE = "CHAMPION_NOT_EFFECTIVE"
    FORECAST_ABSTAINED = "FORECAST_ABSTAINED"
    FORECAST_STAGE_NOT_ALLOWED = "FORECAST_STAGE_NOT_ALLOWED"
    FORECAST_ROLE_NOT_ALLOWED = "FORECAST_ROLE_NOT_ALLOWED"
    FORECAST_TOO_OLD = "FORECAST_TOO_OLD"
    FORECAST_EXPIRED = "FORECAST_EXPIRED"
    PROBABILITY_UNAVAILABLE = "PROBABILITY_UNAVAILABLE"
    CALIBRATED_PROBABILITY_UNAVAILABLE = "CALIBRATED_PROBABILITY_UNAVAILABLE"
    PROBABILITY_EDGE_TOO_SMALL = "PROBABILITY_EDGE_TOO_SMALL"
    INVALID_PROBABILITY = "INVALID_PROBABILITY"
    QUALITY_ABSTAIN = "QUALITY_ABSTAIN"
    QUALITY_FAIL_CLOSED = "QUALITY_FAIL_CLOSED"
    QUALITY_DEGRADED_NOT_ALLOWED = "QUALITY_DEGRADED_NOT_ALLOWED"
    CAPABILITY_REQUIRED_MISSING = "CAPABILITY_REQUIRED_MISSING"
    OOD_NOT_ALLOWED = "OOD_NOT_ALLOWED"
    UNCERTAINTY_TOO_HIGH = "UNCERTAINTY_TOO_HIGH"
    UNCERTAINTY_UNAVAILABLE = "UNCERTAINTY_UNAVAILABLE"
    SPREAD_INVALID = "SPREAD_INVALID"
    SPREAD_TOO_WIDE = "SPREAD_TOO_WIDE"
    LIQUIDITY_CONTEXT_UNAVAILABLE = "LIQUIDITY_CONTEXT_UNAVAILABLE"
    REGIME_NOT_ALLOWED = "REGIME_NOT_ALLOWED"
    REGIME_CONTEXT_UNAVAILABLE = "REGIME_CONTEXT_UNAVAILABLE"
    ECONOMIC_VALUE_UNAVAILABLE = "ECONOMIC_VALUE_UNAVAILABLE"
    ECONOMIC_HURDLE_NOT_MET = "ECONOMIC_HURDLE_NOT_MET"
    TEMPORAL_INTEGRITY_VIOLATION = "TEMPORAL_INTEGRITY_VIOLATION"
    OPPORTUNITY_TIME_BEFORE_FORECAST = "OPPORTUNITY_TIME_BEFORE_FORECAST"
    RUNTIME_GOVERNANCE_DISABLED = "RUNTIME_GOVERNANCE_DISABLED"


class EconomicValueStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE_DIRECTION_ONLY = "UNAVAILABLE_DIRECTION_ONLY"
    UNAVAILABLE_NO_MAGNITUDE = "UNAVAILABLE_NO_MAGNITUDE"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class OpportunityPolicyV1:
    """Immutable versioned opportunity gate configuration."""

    opportunity_policy_id: str
    schema_version: str
    champion_scope: ChampionScopeV1
    allowed_forecast_stages: tuple[str, ...] = (FINAL_FORECAST_STAGE,)
    allowed_contributor_roles: tuple[str, ...] = ("PRODUCTION",)
    probability_view: ProbabilityView = ProbabilityView.OPERATIONAL
    reference_probability: float = 0.5
    minimum_probability_edge: float = 0.0
    minimum_probability_edge_strict: bool = False
    require_calibrated_probability: bool = False
    max_forecast_age_ns: int | None = None
    max_opportunity_lifetime_ns: int | None = None
    max_spread_bps: float | None = None
    require_spread_bps: bool = False
    max_predictive_entropy: float | None = None
    require_uncertainty: bool = False
    allow_ood: bool = False
    allow_degraded_quality: bool = False
    required_capabilities: tuple[IntelligenceCapability, ...] = ()
    allowed_regimes: tuple[str, ...] = ()
    require_regime: bool = False
    minimum_net_economic_edge_bps: float | None = None
    implementation_version: str = OPPORTUNITY_IMPLEMENTATION_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.opportunity_policy_id:
            raise ValueError("OPPORTUNITY_POLICY_ID_REQUIRED")
        if not 0.0 <= self.reference_probability <= 1.0:
            raise ValueError("REFERENCE_PROBABILITY_INVALID")
        if self.minimum_probability_edge < 0.0:
            raise ValueError("MINIMUM_PROBABILITY_EDGE_INVALID")


@dataclass(frozen=True, slots=True)
class OpportunityContext:
    """Point-in-time market and quality context for opportunity assessment."""

    snapshot_ref: ContractReference | None = None
    snapshot_available_time_ns: int | None = None
    signal_refs: tuple[ContractReference, ...] = ()
    spread_bps: float | None = None
    spread_available_time_ns: int | None = None
    depth_imbalance: float | None = None
    depth_available_time_ns: int | None = None
    quality_decision: QualityDecision | None = None
    regime: str | None = None
    regime_available_time_ns: int | None = None
    mode: str = "ACTUAL_LIVE"
    scenario_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class OpportunityAssessmentV1:
    """Auditable opportunity decision for every evaluated forecast."""

    assessment_id: str
    schema_version: str
    forecast_id: str
    champion_assignment_id: str
    opportunity_policy_id: str
    opportunity_decision_time_ns: int
    forecast_decision_time_ns: int
    probability_view: ProbabilityView
    probability: float | None
    reference_probability: float
    probability_edge: float | None
    side: str | None
    quality_action: str | None
    uncertainty_entropy: float | None
    spread_bps: float | None
    economic_value_status: EconomicValueStatus
    assessment_action: AssessmentAction
    reason_codes: tuple[AssessmentReasonCode, ...] = ()
    expected_gross_move_bps: float | None = None
    estimated_friction_bps: float | None = None
    expected_net_edge_bps: float | None = None
    regime: str | None = None
    opportunity_id: str | None = None
    expires_at_ns: int | None = None
    context_refs: tuple[ContractReference, ...] = ()
    lineage_refs: tuple[ContractReference, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    implementation_version: str = OPPORTUNITY_IMPLEMENTATION_VERSION


@dataclass(frozen=True, slots=True)
class OpportunityAssessmentResult:
    """Engine output bundle."""

    assessment: OpportunityAssessmentV1
    opportunity: OpportunityV1 | None = None


__all__ = [
    "OPPORTUNITY_IMPLEMENTATION_VERSION",
    "AssessmentAction",
    "AssessmentReasonCode",
    "EconomicValueStatus",
    "OpportunityAssessmentResult",
    "OpportunityAssessmentV1",
    "OpportunityContext",
    "OpportunityPolicyV1",
]
