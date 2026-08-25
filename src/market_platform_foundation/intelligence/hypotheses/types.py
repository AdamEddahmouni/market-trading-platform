"""Runtime types for BUILD 13 composite hypothesis evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..contracts import EvidenceV1, HypothesisV1, SnapshotV1
from ..council.blackboard import BlackboardSnapshot
from ..council.models import EvidenceRelationReport


class HypothesisType(StrEnum):
    SHORT_SQUEEZE_SETUP = "SHORT_SQUEEZE_SETUP"


class HypothesisEvaluationStatus(StrEnum):
    EMITTED = "EMITTED"
    EMITTED_CONTESTED = "EMITTED_CONTESTED"
    INSUFFICIENT_REQUIRED_EVIDENCE = "INSUFFICIENT_REQUIRED_EVIDENCE"
    INSUFFICIENT_INDEPENDENCE = "INSUFFICIENT_INDEPENDENCE"
    INSUFFICIENT_DOMAIN_COVERAGE = "INSUFFICIENT_DOMAIN_COVERAGE"
    CONTRADICTED = "CONTRADICTED"
    NO_APPLICABLE_EVIDENCE = "NO_APPLICABLE_EVIDENCE"
    INVALID_INPUT = "INVALID_INPUT"


class HypothesisEvidencePhasePolicy(StrEnum):
    BLIND_ONLY = "BLIND_ONLY"
    BLIND_PLUS_DELIBERATION = "BLIND_PLUS_DELIBERATION"


class HypothesisDiagnosticCode(StrEnum):
    MISSING_REQUIRED_FACTOR = "MISSING_REQUIRED_FACTOR"
    INSUFFICIENT_DOMAIN_COVERAGE = "INSUFFICIENT_DOMAIN_COVERAGE"
    INSUFFICIENT_INDEPENDENT_PROVENANCE = "INSUFFICIENT_INDEPENDENT_PROVENANCE"
    REQUIRED_FACTOR_OPPOSED = "REQUIRED_FACTOR_OPPOSED"
    REQUIRED_FACTOR_CONTESTED = "REQUIRED_FACTOR_CONTESTED"
    DEGRADED_REQUIRED_EVIDENCE = "DEGRADED_REQUIRED_EVIDENCE"
    UNSUPPORTED_EVIDENCE = "UNSUPPORTED_EVIDENCE"
    INVALID_EVIDENCE_EXCLUDED = "INVALID_EVIDENCE_EXCLUDED"
    BLACKBOARD_PHASE_NOT_ALLOWED = "BLACKBOARD_PHASE_NOT_ALLOWED"
    BLACKBOARD_RELATION_MISMATCH = "BLACKBOARD_RELATION_MISMATCH"
    HYPOTHESIS_PERSISTENCE_CONFLICT = "HYPOTHESIS_PERSISTENCE_CONFLICT"


@dataclass(frozen=True, slots=True)
class HypothesisDiagnostic:
    code: HypothesisDiagnosticCode
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class HypothesisEvaluationContext:
    blackboard: BlackboardSnapshot
    relation_report: EvidenceRelationReport
    evidence_by_id: dict[str, EvidenceV1]
    snapshot: SnapshotV1 | None = None
    decision_time_ns: int | None = None


@dataclass(frozen=True, slots=True)
class HypothesisEvaluationResult:
    status: HypothesisEvaluationStatus
    hypothesis: HypothesisV1 | None = None
    supporting_evidence_ids: tuple[str, ...] = ()
    opposing_evidence_ids: tuple[str, ...] = ()
    excluded_evidence_ids: tuple[str, ...] = ()
    diagnostics: tuple[HypothesisDiagnostic, ...] = ()
    coverage: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "HypothesisDiagnostic",
    "HypothesisDiagnosticCode",
    "HypothesisEvaluationContext",
    "HypothesisEvaluationResult",
    "HypothesisEvaluationStatus",
    "HypothesisEvidencePhasePolicy",
    "HypothesisType",
]
