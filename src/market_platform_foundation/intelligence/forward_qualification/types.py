"""Forward shadow qualification contracts (BUILD 26)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


FORWARD_QUALIFICATION_SCHEMA_VERSION = "1"
FORWARD_QUALIFICATION_IMPLEMENTATION_VERSION = "build26-v1"

DEFAULT_INSTRUMENT_UNIVERSE: tuple[str, ...] = (
    "AAPL",
    "NVDA",
    "MSFT",
    "AMD",
    "TSLA",
    "SPY",
    "QQQ",
)

DEFAULT_TARGET_KIND = "direction_up_down"
DEFAULT_HORIZON_NS = 5 * 60 * 1_000_000_000
DEFAULT_MINIMUM_PREDICTION_COUNT = 10
DEFAULT_MINIMUM_LABELABLE_COUNT = 5
DEFAULT_MINIMUM_DURATION_NS = 60 * 60 * 1_000_000_000


class QualificationKind(StrEnum):
    FORWARD_SHADOW = "FORWARD_SHADOW"


class EvidenceClass(StrEnum):
    ACTUAL_FORWARD = "ACTUAL_FORWARD"
    REPLAY = "REPLAY"
    COUNTERFACTUAL = "COUNTERFACTUAL"


class QualificationDisposition(StrEnum):
    QUALIFIED = "QUALIFIED"
    QUALIFIED_WITH_LIMITATIONS = "QUALIFIED_WITH_LIMITATIONS"
    INSUFFICIENT_FORWARD_EVIDENCE = "INSUFFICIENT_FORWARD_EVIDENCE"
    INVALID_FORWARD_INTEGRITY = "INVALID_FORWARD_INTEGRITY"
    INVALID_PROVIDER_QUALITY = "INVALID_PROVIDER_QUALITY"
    INVALID_RUNTIME_INTEGRITY = "INVALID_RUNTIME_INTEGRITY"


class ForwardIntegrityStatus(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"
    PENDING = "PENDING"


class IntegrityFailureCode(StrEnum):
    RETROACTIVE_FORECAST = "RETROACTIVE_FORECAST"
    LEDGER_AFTER_TARGET = "LEDGER_AFTER_TARGET"
    FUTURE_DATA_ACCESS = "FUTURE_DATA_ACCESS"
    REPLAY_MASQUERADING_AS_FORWARD = "REPLAY_MASQUERADING_AS_FORWARD"
    COUNTERFACTUAL_MASQUERADING_AS_FORWARD = "COUNTERFACTUAL_MASQUERADING_AS_FORWARD"
    ALTERED_FORECAST_AFTER_OUTCOME = "ALTERED_FORECAST_AFTER_OUTCOME"
    ALTERED_LEDGER_AFTER_OUTCOME = "ALTERED_LEDGER_AFTER_OUTCOME"
    RC_INTEGRITY_MISMATCH = "RC_INTEGRITY_MISMATCH"
    CHAMPION_CHANGED_MID_RUN = "CHAMPION_CHANGED_MID_RUN"
    POLICY_CHANGED_MID_RUN = "POLICY_CHANGED_MID_RUN"
    FEATURE_SCHEMA_CHANGED_MID_RUN = "FEATURE_SCHEMA_CHANGED_MID_RUN"


class ProviderRuntimeStatus(StrEnum):
    CONNECTED_LIVE = "CONNECTED_LIVE"
    CONNECTED_DELAYED = "CONNECTED_DELAYED"
    CONNECTED_POLLING = "CONNECTED_POLLING"
    CONNECTED_REPLAY_ONLY = "CONNECTED_REPLAY_ONLY"
    CONFIGURED_NOT_AVAILABLE = "CONFIGURED_NOT_AVAILABLE"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True)
class ProviderCapabilityEntryV1:
    provider_id: str
    capability: str
    market: str
    instrument_class: str
    delivery_mode: str
    streaming: bool
    timestamp_semantics: str
    available_time_semantics: str
    entitlement_status: str
    runtime_availability: ProviderRuntimeStatus
    qualification_eligible: bool
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "capability": self.capability,
            "market": self.market,
            "instrument_class": self.instrument_class,
            "delivery_mode": self.delivery_mode,
            "streaming": self.streaming,
            "timestamp_semantics": self.timestamp_semantics,
            "available_time_semantics": self.available_time_semantics,
            "entitlement_status": self.entitlement_status,
            "runtime_availability": self.runtime_availability.value,
            "qualification_eligible": self.qualification_eligible,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ForwardQualificationSpecV1:
    qualification_spec_id: str
    schema_version: str
    release_candidate_ref: str
    source_head: str
    contract_inventory_hash: str
    qualification_kind: QualificationKind
    allowed_providers: tuple[str, ...]
    instrument_universe: tuple[str, ...]
    target_kind: str
    horizon_ns: int
    champion_scope: str
    qualification_start_ns: int
    qualification_end_ns: int | None
    minimum_prediction_count: int
    minimum_labelable_count: int
    minimum_duration_ns: int
    required_quality_states: tuple[str, ...]
    control_set: tuple[str, ...]
    execution_mode_requirement: str
    execution_authority_requirement: str
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ForwardQualificationRunV1:
    qualification_run_id: str
    schema_version: str
    qualification_spec_ref: str
    release_candidate_ref: str
    source_head: str
    runtime_activation_ref: str | None
    champion_assignment_ref: str | None
    provider_capability_snapshot: tuple[ProviderCapabilityEntryV1, ...]
    instrument_universe: tuple[str, ...]
    run_start_ns: int
    run_end_ns: int | None
    data_mode: str
    execution_mode: str
    execution_authority: str
    policy_stack_refs: tuple[str, ...]
    implementation_version: str
    lineage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ForwardPredictionReceiptV1:
    receipt_id: str
    schema_version: str
    forecast_id: str
    ledger_entry_id: str
    decision_time_ns: int
    target_time_ns: int
    registered_at_ns: int
    recorded_at_ns: int
    qualification_run_ref: str
    evidence_class: EvidenceClass
    content_hash: str
    forward_integrity_status: ForwardIntegrityStatus
    integrity_failure_codes: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ForwardQualificationReportV1:
    qualification_report_id: str
    schema_version: str
    qualification_spec_ref: str
    qualification_run_ref: str
    release_candidate_ref: str
    evaluation_as_of_ns: int
    provider_capability_summary: dict[str, Any]
    provider_health_summary: dict[str, Any]
    data_quality_summary: dict[str, Any]
    prediction_counts: dict[str, int]
    settlement_counts: dict[str, int]
    labelability_counts: dict[str, int]
    primary_forward_metrics: dict[str, Any]
    control_comparison: dict[str, Any]
    calibration_diagnostics: dict[str, Any]
    ood_diagnostics: dict[str, Any]
    operational_errors: tuple[str, ...]
    runtime_incidents: tuple[str, ...]
    forward_integrity_status: ForwardIntegrityStatus
    forward_integrity_failures: tuple[str, ...]
    qualification_disposition: QualificationDisposition
    disposition_reason_codes: tuple[str, ...]
    limitations: tuple[str, ...]
    lineage: dict[str, Any]
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)
