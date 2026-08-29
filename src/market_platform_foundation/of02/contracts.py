"""Common OF-02 attribution contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from market_platform_foundation.of01.records import (
    ActionCategory,
    ConsequenceProfile,
    FailureReasonFamily,
    InitiatorClass,
    OutcomeValidity,
    ProvenanceQualifier,
    ReproducibilityClass,
    SensitivityClass,
    TerminalResult,
    TriggerType,
)


class CompletenessState(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


class AttributionStatus(StrEnum):
    COMMITTED = "COMMITTED"
    EXISTING = "EXISTING"
    DISABLED = "DISABLED"
    BEST_EFFORT_FAILED = "BEST_EFFORT_FAILED"
    WITHHELD = "WITHHELD"
    FAILED_CLOSED = "FAILED_CLOSED"
    DRY_RUN = "DRY_RUN"
    SKIPPED = "SKIPPED"
    CONFLICTED = "CONFLICTED"


@dataclass(frozen=True, slots=True)
class DomainIdentity:
    system: str
    id_type: str
    value: str


@dataclass(frozen=True, slots=True)
class AttemptSpec:
    sequence: int
    terminal_result: TerminalResult
    reason_code: str
    reason_family: FailureReasonFamily | None = None
    invocation_ref: str = "invocation://unspecified"
    environment_ref: str = "environment://unspecified"
    started_at_ns: int | None = None
    ended_at_ns: int | None = None
    skipped: bool = False


@dataclass(frozen=True, slots=True)
class ArtifactCapture:
    logical_role: str
    logical_name: str
    payload: bytes
    media_type: str = "application/json"


@dataclass(frozen=True, slots=True)
class AttributionRequest:
    adapter_id: str
    operation_class: str
    objective: str
    consequence_profile: ConsequenceProfile
    provenance_qualifier: ProvenanceQualifier
    initiator_class: InitiatorClass = InitiatorClass.SYSTEM
    initiator_ref: str | None = "of02"
    trigger_type: TriggerType | None = None
    trigger_ref: str | None = None
    reproducibility_class: ReproducibilityClass = ReproducibilityClass.R1_OBSERVATION_ONLY
    domain_identities: tuple[DomainIdentity, ...] = ()
    attempts: tuple[AttemptSpec, ...] = ()
    outcome_type: str = "DOMAIN_RESULT"
    result_ref: str = "result://unspecified"
    validity: OutcomeValidity = OutcomeValidity.NOT_EVALUATED
    disposition_action: ActionCategory = ActionCategory.NO_ACTION
    disposition_domain_code: str = "UNSET"
    outcome_limitations: str | None = None
    known_missing: tuple[str, ...] = ()
    event_time_ns: int | None = None
    repository_identity: str | None = None
    root_identity: str | None = None
    base_revision: str | None = None
    artifact: ArtifactCapture | None = None
    extra: Mapping[str, Any] = field(default_factory=dict)
    sensitivity_class: SensitivityClass = SensitivityClass.INTERNAL


@dataclass(frozen=True, slots=True)
class AttributionResult:
    adapter_id: str
    status: AttributionStatus
    provenance_qualifier: ProvenanceQualifier
    attribution_completeness: CompletenessState
    run_id: str | None = None
    attempt_ids: tuple[str, ...] = ()
    commit_ids: tuple[str, ...] = ()
    artifact_ids: tuple[str, ...] = ()
    outcome_id: str | None = None
    disposition_id: str | None = None
    known_missing: tuple[str, ...] = ()
    withheld_acceptance: bool = False
    error_code: str | None = None
    error_message: str | None = None
    dry_run: bool = False
