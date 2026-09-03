"""Runtime models for BUILD 12 expert council coordination."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..contracts import ContractReference, EvidenceV1, ExpertDomain
from ..specialists.models import SpecialistExecutionStatus


class CouncilPhase(StrEnum):
    PLANNED = "PLANNED"
    BLIND_RUNNING = "BLIND_RUNNING"
    BLIND_TERMINAL = "BLIND_TERMINAL"
    BLACKBOARD_PUBLISHED = "BLACKBOARD_PUBLISHED"
    RELATIONS_ANALYZED = "RELATIONS_ANALYZED"
    DELIBERATION_NOT_REQUIRED = "DELIBERATION_NOT_REQUIRED"
    DELIBERATION_REQUIRED = "DELIBERATION_REQUIRED"
    DELIBERATION_COMPLETE = "DELIBERATION_COMPLETE"
    CLOSED = "CLOSED"


class CouncilExecutionPhase(StrEnum):
    BLIND_FIRST_PASS = "BLIND_FIRST_PASS"
    DELIBERATION_PASS = "DELIBERATION_PASS"


class BlackboardPhase(StrEnum):
    BLIND_PASS = "BLIND_PASS"
    DELIBERATION_PASS = "DELIBERATION_PASS"


class SourceIndependence(StrEnum):
    SOURCE_INDEPENDENT = "SOURCE_INDEPENDENT"
    CORRELATED = "CORRELATED"
    STRONGLY_CORRELATED = "STRONGLY_CORRELATED"
    UNKNOWN = "UNKNOWN"


class EvidenceRelationType(StrEnum):
    AGREES = "AGREES"
    CONFLICTS = "CONFLICTS"
    ORTHOGONAL = "ORTHOGONAL"
    INCOMPARABLE = "INCOMPARABLE"


class DeliberationDecision(StrEnum):
    NOT_REQUIRED = "NOT_REQUIRED"
    REQUIRED = "REQUIRED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NO_COMPARABLE_EVIDENCE = "NO_COMPARABLE_EVIDENCE"
    DELIBERATION_UNAVAILABLE = "DELIBERATION_UNAVAILABLE"


class DeliberationReasonCode(StrEnum):
    INDEPENDENT_CONFLICT = "INDEPENDENT_CONFLICT"
    CORRELATED_CONFLICT = "CORRELATED_CONFLICT"
    INTERPRETATION_CONFLICT_SHARED_SOURCE = "INTERPRETATION_CONFLICT_SHARED_SOURCE"
    ALL_AGREEMENT = "ALL_AGREEMENT"
    ORTHOGONAL_ONLY = "ORTHOGONAL_ONLY"
    SINGLE_EXPERT = "SINGLE_EXPERT"
    INSUFFICIENT_MULTI_EXPERT_EVIDENCE = "INSUFFICIENT_MULTI_EXPERT_EVIDENCE"
    NO_COMPARABLE_EVIDENCE = "NO_COMPARABLE_EVIDENCE"
    DELIBERATION_DISABLED = "DELIBERATION_DISABLED"
    ROUND_LIMIT_REACHED = "ROUND_LIMIT_REACHED"


class CouncilDiagnosticCode(StrEnum):
    PARTICIPANT_ABSTAINED = "PARTICIPANT_ABSTAINED"
    PARTICIPANT_FAILED = "PARTICIPANT_FAILED"
    PARTICIPANT_STALE = "PARTICIPANT_STALE"
    PARTICIPANT_EXPIRED = "PARTICIPANT_EXPIRED"
    BLACKBOARD_NOT_READY = "BLACKBOARD_NOT_READY"
    NO_VALID_EVIDENCE = "NO_VALID_EVIDENCE"
    EVIDENCE_EXCLUDED_INVALID = "EVIDENCE_EXCLUDED_INVALID"
    EVIDENCE_EXCLUDED_DEGRADED = "EVIDENCE_EXCLUDED_DEGRADED"


@dataclass(frozen=True, slots=True)
class CouncilParticipant:
    expert_domain: ExpertDomain
    job_id: str
    job_ref: ContractReference

    def __post_init__(self) -> None:
        if not self.job_id:
            raise ValueError("COUNCIL_PARTICIPANT_JOB_ID_REQUIRED")


@dataclass(frozen=True, slots=True)
class ParticipantOutcome:
    expert_domain: ExpertDomain
    job_id: str
    status: SpecialistExecutionStatus
    evidence_refs: tuple[str, ...] = ()
    execution_phase: CouncilExecutionPhase = CouncilExecutionPhase.BLIND_FIRST_PASS
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_refs", tuple(sorted(set(self.evidence_refs))))


@dataclass(frozen=True, slots=True)
class CouncilDiagnostic:
    code: CouncilDiagnosticCode
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SourceSignature:
    signature_id: str
    terminal_source_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "terminal_source_ids", tuple(sorted(set(self.terminal_source_ids)))
        )


@dataclass(frozen=True, slots=True)
class SourceOverlap:
    evidence_a_id: str
    evidence_b_id: str
    intersection: tuple[str, ...]
    union: tuple[str, ...]
    independence: SourceIndependence
    overlap_count: int
    jaccard: float | None


@dataclass(frozen=True, slots=True)
class ComparableEvidenceView:
    evidence_id: str
    expert_domain: ExpertDomain
    scope_key: str
    comparison_key: str
    polarity: str
    quality_state: str
    strength: float | None
    source_signature_id: str
    terminal_source_ids: tuple[str, ...] = ()
    evidence_kind: str | None = None
    comparable: bool = True


@dataclass(frozen=True, slots=True)
class EvidenceRelation:
    evidence_a_id: str
    evidence_b_id: str
    relation_type: EvidenceRelationType
    source_independence: SourceIndependence
    agreement_subtype: str | None = None
    conflict_subtype: str | None = None


@dataclass(frozen=True, slots=True)
class ProvenanceGroup:
    group_id: str
    source_signature_id: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvidenceRelationReport:
    report_id: str
    blackboard_id: str
    policy_identity: str
    relations: tuple[EvidenceRelation, ...]
    agreement_groups: tuple[tuple[str, ...], ...]
    conflict_groups: tuple[tuple[str, ...], ...]
    orthogonal_evidence_ids: tuple[str, ...]
    incomparable_evidence_ids: tuple[str, ...]
    provenance_groups: tuple[ProvenanceGroup, ...]
    excluded_evidence_ids: tuple[str, ...]
    comparable_evidence_ids: tuple[str, ...]
    diagnostics: tuple[CouncilDiagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class CouncilDeliberationRequest:
    request_id: str
    council_id: str
    blackboard_id: str
    conflicting_evidence_refs: tuple[str, ...]
    invited_participant_domains: tuple[ExpertDomain, ...]
    reason_code: DeliberationReasonCode
    round_number: int
    relation_report_id: str
    policy_identity: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "conflicting_evidence_refs",
            tuple(sorted(set(self.conflicting_evidence_refs))),
        )
        object.__setattr__(
            self,
            "invited_participant_domains",
            tuple(sorted(set(self.invited_participant_domains), key=lambda d: d.value)),
        )


@dataclass(frozen=True, slots=True)
class CouncilResult:
    council_id: str
    phase: CouncilPhase
    policy_identity: str
    source_snapshot_id: str
    blind_blackboard_id: str | None
    deliberation_blackboard_id: str | None
    relation_report_id: str | None
    deliberation_decision: DeliberationDecision | None
    deliberation_request_id: str | None
    participant_outcomes: tuple[ParticipantOutcome, ...]
    diagnostics: tuple[CouncilDiagnostic, ...] = ()
    coverage: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DeliberationContext:
    """Bounded second-pass context — not a blind first-pass context."""

    council_id: str
    blackboard_id: str
    published_evidence: tuple[EvidenceV1, ...]
    conflicting_evidence_refs: tuple[str, ...]
    relation_report_id: str
    own_blind_evidence: tuple[EvidenceV1, ...] = ()
    round_number: int = 1


__all__ = [
    "BlackboardPhase",
    "ComparableEvidenceView",
    "CouncilDiagnostic",
    "CouncilDiagnosticCode",
    "CouncilDeliberationRequest",
    "CouncilExecutionPhase",
    "CouncilParticipant",
    "CouncilPhase",
    "CouncilResult",
    "DeliberationContext",
    "DeliberationDecision",
    "DeliberationReasonCode",
    "EvidenceRelation",
    "EvidenceRelationReport",
    "EvidenceRelationType",
    "ParticipantOutcome",
    "ProvenanceGroup",
    "SourceIndependence",
    "SourceOverlap",
    "SourceSignature",
]
