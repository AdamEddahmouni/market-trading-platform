"""EVIDENCE-01 longer forward evidence qualification contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ...contracts.forecast import ForecastV1
from ...contracts.prediction_ledger import PredictionLedgerEntryV1
from ..types import ForwardPredictionReceiptV1


FORWARD_EVIDENCE_QUALIFICATION_SCHEMA_VERSION = "1"
FORWARD_EVIDENCE_QUALIFICATION_IMPLEMENTATION_VERSION = "evidence01-v1"

# BUILD 26 frozen floors (ForwardQualificationSpecV1 defaults).
BUILD26_MINIMUM_PREDICTION_COUNT = 10
BUILD26_MINIMUM_LABELABLE_COUNT = 5
BUILD26_MINIMUM_DURATION_NS = 60 * 60 * 1_000_000_000

# EVIDENCE-01 extensions: 5x BUILD 26 sample floors and P6 shadow-run session
# precedent (complete_sessions >= 5). Documented as provisional governance in
# docs/engineering/EVIDENCE_01_LONGER_FORWARD_QUALIFICATION.md.
EVIDENCE01_MINIMUM_ELIGIBLE_PREDICTIONS = BUILD26_MINIMUM_PREDICTION_COUNT * 5
EVIDENCE01_MINIMUM_SETTLED_PREDICTIONS = BUILD26_MINIMUM_LABELABLE_COUNT * 5
EVIDENCE01_MINIMUM_SETTLEMENT_RATE = 0.80
EVIDENCE01_MINIMUM_DURATION_NS = 5 * 24 * 60 * 60 * 1_000_000_000
EVIDENCE01_MINIMUM_DISTINCT_TRADING_DAYS = 5
EVIDENCE01_MINIMUM_DISTINCT_SESSIONS = 5
EVIDENCE01_MINIMUM_CLASS_SUPPORT = 3
EVIDENCE01_MAX_ADMISSIBLE_GAP_NS = 24 * 60 * 60 * 1_000_000_000
EVIDENCE01_DEFAULT_HORIZON_NS = 5 * 60 * 1_000_000_000


class ForwardEvidenceDisposition(StrEnum):
    QUALIFIED = "QUALIFIED"
    QUALIFIED_WITH_LIMITATIONS = "QUALIFIED_WITH_LIMITATIONS"
    INSUFFICIENT_FORWARD_EVIDENCE = "INSUFFICIENT_FORWARD_EVIDENCE"
    INVALID_EVIDENCE = "INVALID_EVIDENCE"
    INCOMPLETE_SETTLEMENT = "INCOMPLETE_SETTLEMENT"
    DATA_QUALITY_INSUFFICIENT = "DATA_QUALITY_INSUFFICIENT"


class ObservationExclusionReason(StrEnum):
    DUPLICATE_FORECAST = "DUPLICATE_FORECAST"
    NOT_ACTUAL_FORWARD = "NOT_ACTUAL_FORWARD"
    INTEGRITY_INVALID = "INTEGRITY_INVALID"
    AFTER_OBSERVATION_CUTOFF = "AFTER_OBSERVATION_CUTOFF"
    QUALITY_INELIGIBLE = "QUALITY_INELIGIBLE"
    FUTURE_EVENT_TIME = "FUTURE_EVENT_TIME"
    FUTURE_AVAILABLE_TIME = "FUTURE_AVAILABLE_TIME"
    INSIDE_UNRESOLVED_HORIZON = "INSIDE_UNRESOLVED_HORIZON"
    PROVIDER_DISCONNECTED = "PROVIDER_DISCONNECTED"


@dataclass(frozen=True)
class ForwardObservationInputV1:
    receipt: ForwardPredictionReceiptV1
    forecast: ForecastV1 | None = None
    ledger_entry: PredictionLedgerEntryV1 | None = None
    quality_state: str | None = None
    session_id: str | None = None
    provider_connected: bool = True


@dataclass(frozen=True)
class ForwardEvidenceQualificationPolicyV1:
    policy_id: str
    schema_version: str
    build26_spec_ref: str
    horizon_ns: int
    minimum_eligible_predictions: int
    minimum_settled_predictions: int
    minimum_settlement_rate: float
    minimum_duration_ns: int
    minimum_distinct_trading_days: int
    minimum_distinct_sessions: int
    minimum_class_support: int
    maximum_admissible_gap_ns: int
    required_quality_states: tuple[str, ...]
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ForwardObservationSummaryV1:
    observation_cutoff_ns: int
    settlement_cutoff_ns: int
    first_eligible_decision_ns: int | None
    last_eligible_decision_ns: int | None
    elapsed_qualifying_duration_ns: int
    distinct_trading_days: int
    distinct_sessions: int
    raw_observations: int
    eligible_predictions: int
    settled_predictions: int
    unsettled_predictions: int
    abstentions: int
    excluded_observations: int
    exclusions_by_reason: dict[str, int]
    up_support: int
    down_support: int
    settlement_rate: float
    maximum_observation_gap_ns: int
    provider_disconnected_exclusions: int


@dataclass(frozen=True)
class ForwardEvidenceQualificationAssessmentV1:
    assessment_id: str
    schema_version: str
    policy_ref: str
    observation_cutoff_ns: int
    settlement_cutoff_ns: int
    source_evidence_fingerprint: str
    observation_summary: ForwardObservationSummaryV1
    evidence_sufficiency_passed: bool
    performance_evaluated: bool
    qualification_disposition: ForwardEvidenceDisposition
    disposition_reason_codes: tuple[str, ...]
    limitations: tuple[str, ...]
    remaining_requirements: tuple[str, ...]
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ForwardEvidenceQualificationReportV1:
    report_id: str
    schema_version: str
    policy_ref: str
    assessment_ref: str
    build26_historical_disposition: str
    build26_historical_report_ref: str
    evidence01_disposition: ForwardEvidenceDisposition
    limitation_status: str
    observation_summary: ForwardObservationSummaryV1
    remaining_requirements: tuple[str, ...]
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)
