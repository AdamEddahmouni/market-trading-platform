"""Immutable evidence blackboard for BUILD 12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ..contracts import EvidenceV1
from .errors import BlackboardNotReadyError, CouncilIntegrityError
from .identity import derive_blackboard_id
from .models import BlackboardPhase, ParticipantOutcome


@dataclass(frozen=True, slots=True)
class BlackboardSnapshot:
    blackboard_id: str
    council_id: str
    source_snapshot_id: str
    evidence_refs: tuple[str, ...]
    participant_outcomes: tuple[ParticipantOutcome, ...]
    phase: BlackboardPhase
    revision: int
    publication_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_refs", tuple(sorted(set(self.evidence_refs))))

    def query_all(self) -> tuple[str, ...]:
        return self.evidence_refs

    def query_by_expert_domain(self, domain_value: str) -> tuple[str, ...]:
        allowed = {
            outcome.job_id
            for outcome in self.participant_outcomes
            if outcome.expert_domain.value == domain_value
        }
        return tuple(
            evidence_id
            for outcome in self.participant_outcomes
            if outcome.job_id in allowed
            for evidence_id in outcome.evidence_refs
            if evidence_id in self.evidence_refs
        )

    def query_by_polarity(
        self,
        evidence_by_id: Mapping[str, EvidenceV1],
        polarity: str,
    ) -> tuple[str, ...]:
        result: list[str] = []
        for evidence_id in self.evidence_refs:
            evidence = evidence_by_id.get(evidence_id)
            if evidence is None:
                continue
            assessment = evidence.assessment or {}
            if assessment.get("pressure_direction") == polarity:
                result.append(evidence_id)
        return tuple(sorted(result))

    def query_by_comparison_key(
        self,
        evidence_by_id: Mapping[str, EvidenceV1],
        comparison_key: str,
        *,
        scope_key: str | None = None,
    ) -> tuple[str, ...]:
        result: list[str] = []
        for evidence_id in self.evidence_refs:
            evidence = evidence_by_id.get(evidence_id)
            if evidence is None:
                continue
            assessment = evidence.assessment or {}
            evidence_kind = str(assessment.get("evidence_kind") or "")
            semantic_event = str(assessment.get("semantic_event") or evidence.metadata.get("semantic_event") or "")
            scope = _scope_key(evidence)
            key = _comparison_key(scope, evidence_kind, semantic_event)
            if key == comparison_key and (scope_key is None or scope == scope_key):
                result.append(evidence_id)
        return tuple(sorted(result))


def _scope_key(evidence: EvidenceV1) -> str:
    instruments = ",".join(sorted(evidence.scope.instrument_ids))
    context = evidence.scope.context_id or ""
    return f"{instruments}|{context}"


def _comparison_key(scope_key: str, evidence_kind: str, semantic_event: str) -> str:
    return f"{scope_key}:{evidence_kind}:{semantic_event}"


def publish_blackboard_snapshot(
    *,
    council_id: str,
    source_snapshot_id: str,
    evidence_refs: tuple[str, ...],
    participant_outcomes: tuple[ParticipantOutcome, ...],
    phase: BlackboardPhase,
    revision: int,
    publication_version: str = "1",
    strict_integrity: bool = True,
    resolved_evidence: Mapping[str, EvidenceV1] | None = None,
) -> BlackboardSnapshot:
    ordered_refs = tuple(sorted(set(evidence_refs)))
    if strict_integrity and resolved_evidence is not None:
        for evidence_id in ordered_refs:
            if evidence_id not in resolved_evidence:
                raise CouncilIntegrityError(f"COUNCIL_MISSING_EVIDENCE:{evidence_id}")
    blackboard_id = derive_blackboard_id(
        council_id=council_id,
        evidence_ids=ordered_refs,
        participant_outcomes=participant_outcomes,
        phase=phase.value,
        revision=revision,
    )
    return BlackboardSnapshot(
        blackboard_id=blackboard_id,
        council_id=council_id,
        source_snapshot_id=source_snapshot_id,
        evidence_refs=ordered_refs,
        participant_outcomes=participant_outcomes,
        phase=phase,
        revision=revision,
        publication_version=publication_version,
    )


def ensure_blackboard_ready(*, barrier_complete: bool) -> None:
    if not barrier_complete:
        raise BlackboardNotReadyError("BLACKBOARD_NOT_READY")


__all__ = [
    "BlackboardSnapshot",
    "ensure_blackboard_ready",
    "publish_blackboard_snapshot",
]
