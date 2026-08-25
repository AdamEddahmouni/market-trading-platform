"""Quality and capability value types (BUILD 04)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..contracts.common import QualityState


class QualityFindingCode(StrEnum):
    """Canonical objective quality finding codes — reuse platform taxonomy."""

    CROSSED_BOOK = "CROSSED_BOOK"
    INVALID_QUOTE = "INVALID_QUOTE"
    LOCKED_BOOK = "LOCKED_BOOK"
    PARTIAL_DATA = "PARTIAL_DATA"
    PROVIDER_DISCONNECTED = "PROVIDER_DISCONNECTED"
    CAPABILITY_UNAVAILABLE = "CAPABILITY_UNAVAILABLE"
    NOT_ENTITLED = "NOT_ENTITLED"
    NOT_SUBSCRIBED = "NOT_SUBSCRIBED"
    BORROW_STALE = "BORROW_STALE"
    SHORT_INTEREST_STALE = "SHORT_INTEREST_STALE"
    CLOCK_DRIFT = "CLOCK_DRIFT"
    PROVIDER_CONFLICT = "PROVIDER_CONFLICT"
    STALE_INFERENCE = "STALE_INFERENCE"
    FUTURE_INFORMATION = "FUTURE_INFORMATION"
    STALE_INFORMATION = "STALE_INFORMATION"
    CONFLICTING_DUPLICATE = "CONFLICTING_DUPLICATE"
    EXACT_DUPLICATE = "EXACT_DUPLICATE"
    OUT_OF_ORDER = "OUT_OF_ORDER"


class FindingSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class DecisionAction(StrEnum):
    USE = "USE"
    DEGRADE = "DEGRADE"
    ABSTAIN = "ABSTAIN"
    FAIL_CLOSED = "FAIL_CLOSED"


class IntelligenceCapability(StrEnum):
    """Provider-neutral capability vocabulary for the intelligence plane."""

    QUOTES = "QUOTES"
    TRADES = "TRADES"
    DEPTH = "DEPTH"
    OPTIONS_CHAIN = "OPTIONS_CHAIN"
    BORROW = "BORROW"
    SHORT_INTEREST = "SHORT_INTEREST"
    FTD = "FTD"
    FILINGS = "FILINGS"
    MACRO = "MACRO"
    DISCOVERY = "DISCOVERY"
    NEWS = "NEWS"


class SupportState(StrEnum):
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


class AvailabilityState(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    DEGRADED = "DEGRADED"
    UNKNOWN = "UNKNOWN"


class FreshnessState(StrEnum):
    FRESH = "FRESH"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class CompletenessState(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


class ValidityState(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"
    UNKNOWN = "UNKNOWN"


class ConflictState(StrEnum):
    NONE = "NONE"
    CONFLICTED = "CONFLICTED"
    UNKNOWN = "UNKNOWN"


class UnavailabilityReason(StrEnum):
    UNSUPPORTED = "UNSUPPORTED"
    NOT_ENTITLED = "NOT_ENTITLED"
    DISCONNECTED = "DISCONNECTED"
    NOT_SUBSCRIBED = "NOT_SUBSCRIBED"
    STALE = "STALE"
    INVALID = "INVALID"
    UNKNOWN = "UNKNOWN"


class ConnectionState(StrEnum):
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    RECONNECTING = "RECONNECTING"
    UNKNOWN = "UNKNOWN"


EVENT_TYPE_TO_CAPABILITY: dict[str, IntelligenceCapability] = {
    "QUOTE": IntelligenceCapability.QUOTES,
    "L1": IntelligenceCapability.QUOTES,
    "TRADE": IntelligenceCapability.TRADES,
    "TICK": IntelligenceCapability.TRADES,
    "DEPTH": IntelligenceCapability.DEPTH,
    "ORDER_BOOK": IntelligenceCapability.DEPTH,
    "SHORT_INTEREST": IntelligenceCapability.SHORT_INTEREST,
    "FAIL_TO_DELIVER": IntelligenceCapability.FTD,
    "BORROW": IntelligenceCapability.BORROW,
    "FILING": IntelligenceCapability.FILINGS,
    "MACRO_RELEASE": IntelligenceCapability.MACRO,
    "DISCOVERY_CANDIDATE": IntelligenceCapability.DISCOVERY,
}


def capability_for_event_type(event_type: str) -> IntelligenceCapability | None:
    return EVENT_TYPE_TO_CAPABILITY.get(str(event_type).upper())


@dataclass(frozen=True, slots=True)
class QualityFinding:
    """Objective detected quality fact — not a policy decision."""

    code: str
    severity: FindingSeverity
    message: str
    provider_id: str | None = None
    capability: IntelligenceCapability | None = None
    instrument_id: str | None = None
    observed_at_ns: int | None = None
    event_id: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)

    def sort_key(self) -> tuple[Any, ...]:
        return (
            -_SEVERITY_ORDER.get(self.severity, 0),
            self.code,
            self.provider_id or "",
            self.capability.value if self.capability else "",
            self.instrument_id or "",
            self.event_id or "",
        )

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
        }
        if self.provider_id is not None:
            body["provider_id"] = self.provider_id
        if self.capability is not None:
            body["capability"] = self.capability.value
        if self.instrument_id is not None:
            body["instrument_id"] = self.instrument_id
        if self.observed_at_ns is not None:
            body["observed_at_ns"] = self.observed_at_ns
        if self.event_id is not None:
            body["event_id"] = self.event_id
        if self.evidence:
            body["evidence"] = dict(self.evidence)
        return body


_SEVERITY_ORDER = {
    FindingSeverity.CRITICAL: 4,
    FindingSeverity.ERROR: 3,
    FindingSeverity.WARNING: 2,
    FindingSeverity.INFO: 1,
}


@dataclass(frozen=True, slots=True)
class CapabilityDimensions:
    """Multi-dimensional capability health — never a single boolean."""

    support: SupportState = SupportState.UNKNOWN
    availability: AvailabilityState = AvailabilityState.UNKNOWN
    freshness: FreshnessState = FreshnessState.UNKNOWN
    completeness: CompletenessState = CompletenessState.UNKNOWN
    validity: ValidityState = ValidityState.UNKNOWN
    conflict: ConflictState = ConflictState.NONE
    temporally_legal: bool | None = None
    unavailability_reason: UnavailabilityReason | None = None


@dataclass(frozen=True, slots=True)
class CapabilityAssessment:
    """State of a capability from a particular source at a decision point."""

    provider_id: str
    capability: IntelligenceCapability
    dimensions: CapabilityDimensions
    quality_state: QualityState
    instrument_id: str | None = None
    findings: tuple[QualityFinding, ...] = ()
    event_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "capability": self.capability.value,
            "instrument_id": self.instrument_id,
            "quality_state": self.quality_state.value,
            "dimensions": {
                "support": self.dimensions.support.value,
                "availability": self.dimensions.availability.value,
                "freshness": self.dimensions.freshness.value,
                "completeness": self.dimensions.completeness.value,
                "validity": self.dimensions.validity.value,
                "conflict": self.dimensions.conflict.value,
                "temporally_legal": self.dimensions.temporally_legal,
                "unavailability_reason": (
                    self.dimensions.unavailability_reason.value
                    if self.dimensions.unavailability_reason is not None
                    else None
                ),
            },
            "findings": [finding.to_dict() for finding in self.findings],
            "event_ids": list(self.event_ids),
        }


@dataclass(frozen=True, slots=True)
class CapabilityRequirement:
    """Caller-declared information need for a specific capability."""

    capability: IntelligenceCapability
    required: bool = True
    failure_action: DecisionAction = DecisionAction.FAIL_CLOSED
    minimum_quality_state: QualityState = QualityState.GOOD
    allow_degraded: bool = False
    max_age_ns: int | None = None
    require_complete: bool = False
    acceptable_providers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "acceptable_providers",
            tuple(sorted({str(p) for p in self.acceptable_providers})),
        )


@dataclass(frozen=True, slots=True)
class RequirementSet:
    """Multiple capability requirements evaluated together."""

    requirements: tuple[CapabilityRequirement, ...] = ()

    @classmethod
    def of(cls, *requirements: CapabilityRequirement) -> RequirementSet:
        return cls(requirements=requirements)


@dataclass(frozen=True, slots=True)
class ProviderCapabilityObservation:
    """Runtime provider/capability observation supplied to the quality engine."""

    provider_id: str
    capability: IntelligenceCapability
    support: SupportState = SupportState.UNKNOWN
    availability: AvailabilityState = AvailabilityState.UNKNOWN
    connection: ConnectionState = ConnectionState.UNKNOWN
    entitled: bool | None = None
    subscribed: bool | None = None
    instrument_id: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderHealthSnapshot:
    """Immutable provider health at an as-of time — not intelligence SnapshotV1."""

    provider_id: str
    as_of_time_ns: int
    connection: ConnectionState
    observations: tuple[ProviderCapabilityObservation, ...] = ()
    findings: tuple[QualityFinding, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "as_of_time_ns": self.as_of_time_ns,
            "connection": self.connection.value,
            "observations": [
                {
                    "provider_id": row.provider_id,
                    "capability": row.capability.value,
                    "support": row.support.value,
                    "availability": row.availability.value,
                    "connection": row.connection.value,
                    "entitled": row.entitled,
                    "subscribed": row.subscribed,
                    "instrument_id": row.instrument_id,
                }
                for row in self.observations
            ],
            "findings": [finding.to_dict() for finding in self.findings],
        }


@dataclass(frozen=True, slots=True)
class QualityAssessment:
    """Structured quality/capability assessment — findings plus capability states."""

    decision_time_ns: int
    findings: tuple[QualityFinding, ...] = ()
    capability_assessments: tuple[CapabilityAssessment, ...] = ()
    provider_health: tuple[ProviderHealthSnapshot, ...] = ()
    policy_id: str = "default"
    policy_version: str = "1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_time_ns": self.decision_time_ns,
            "findings": [finding.to_dict() for finding in self.findings],
            "capability_assessments": [row.to_dict() for row in self.capability_assessments],
            "provider_health": [row.to_dict() for row in self.provider_health],
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
        }


@dataclass(frozen=True, slots=True)
class QualityDecision:
    """Caller-facing use decision with structured reasons."""

    action: DecisionAction
    quality_state: QualityState
    assessment: QualityAssessment
    reasons: tuple[str, ...] = ()
    missing_requirements: tuple[IntelligenceCapability, ...] = ()
    degraded_requirements: tuple[IntelligenceCapability, ...] = ()
    satisfied_requirements: tuple[IntelligenceCapability, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "quality_state": self.quality_state.value,
            "reasons": list(self.reasons),
            "missing_requirements": [cap.value for cap in self.missing_requirements],
            "degraded_requirements": [cap.value for cap in self.degraded_requirements],
            "satisfied_requirements": [cap.value for cap in self.satisfied_requirements],
            "policy_id": self.assessment.policy_id,
            "policy_version": self.assessment.policy_version,
            "decision_time_ns": self.assessment.decision_time_ns,
        }


__all__ = [
    "AvailabilityState",
    "CapabilityAssessment",
    "CapabilityDimensions",
    "CapabilityRequirement",
    "CompletenessState",
    "ConflictState",
    "ConnectionState",
    "DecisionAction",
    "EVENT_TYPE_TO_CAPABILITY",
    "FindingSeverity",
    "FreshnessState",
    "IntelligenceCapability",
    "ProviderCapabilityObservation",
    "ProviderHealthSnapshot",
    "QualityAssessment",
    "QualityDecision",
    "QualityFinding",
    "QualityFindingCode",
    "RequirementSet",
    "SupportState",
    "UnavailabilityReason",
    "ValidityState",
    "capability_for_event_type",
]
