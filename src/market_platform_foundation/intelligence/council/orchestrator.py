"""Blind council orchestrator for BUILD 12."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from ..contracts import EvidenceV1
from ..persistence.repository import IntelligenceRepository
from ..specialists.models import SpecialistExecutionStatus
from .barrier import BlindExecutionBarrier
from .blackboard import BlackboardSnapshot, publish_blackboard_snapshot
from .comparison import ComparisonAdapterRegistry, DEFAULT_COMPARISON_REGISTRY
from .deliberation import DeliberationGate
from .errors import CouncilIntegrityError, CouncilStateError
from .models import (
    BlackboardPhase,
    CouncilDiagnostic,
    CouncilDiagnosticCode,
    CouncilExecutionPhase,
    CouncilPhase,
    CouncilResult,
    DeliberationDecision,
    ParticipantOutcome,
)
from .plan import CouncilPlan
from .policy import CouncilPolicy
from .provenance import EvidenceProvenanceResolver
from .relations import EvidenceRelationAnalyzer


@dataclass
class BlindCouncilOrchestrator:
    plan: CouncilPlan
    repository: IntelligenceRepository
    comparison_registry: ComparisonAdapterRegistry = DEFAULT_COMPARISON_REGISTRY
    phase: CouncilPhase = CouncilPhase.PLANNED
    barrier: BlindExecutionBarrier | None = None
    blind_blackboard: BlackboardSnapshot | None = None
    deliberation_blackboard: BlackboardSnapshot | None = None
    relation_report = None
    deliberation_decision: DeliberationDecision | None = None
    deliberation_request = None
    deliberation_round: int = 0
    diagnostics: list[CouncilDiagnostic] = field(default_factory=list)

    def start_blind_phase(self) -> None:
        if self.phase != CouncilPhase.PLANNED:
            raise CouncilStateError("COUNCIL_ALREADY_STARTED")
        self.barrier = BlindExecutionBarrier(participants=self.plan.participants)
        self.phase = CouncilPhase.BLIND_RUNNING

    def record_participant_terminal(self, outcome: ParticipantOutcome) -> None:
        if self.barrier is None:
            raise CouncilStateError("COUNCIL_BLIND_PHASE_NOT_STARTED")
        if outcome.execution_phase != CouncilExecutionPhase.BLIND_FIRST_PASS:
            raise CouncilStateError("COUNCIL_INVALID_EXECUTION_PHASE")
        self.barrier.record_terminal(outcome)
        if self.barrier.all_terminal():
            self.phase = CouncilPhase.BLIND_TERMINAL

    def publish_blind_blackboard(self, *, strict_integrity: bool = True) -> BlackboardSnapshot:
        if self.barrier is None or not self.barrier.can_publish_blackboard():
            raise CouncilStateError("COUNCIL_BLACKBOARD_NOT_READY")
        outcomes = self.barrier.participant_outcomes()
        evidence_refs = self._collect_evidence_refs(outcomes)
        evidence_by_id = self._resolve_evidence(evidence_refs, strict_integrity=strict_integrity)
        blackboard = publish_blackboard_snapshot(
            council_id=self.plan.council_id,
            source_snapshot_id=self.plan.source_snapshot_id,
            evidence_refs=evidence_refs,
            participant_outcomes=outcomes,
            phase=BlackboardPhase.BLIND_PASS,
            revision=1,
            publication_version=self.plan.policy.blackboard_version,
            strict_integrity=strict_integrity,
            resolved_evidence=evidence_by_id,
        )
        self.blind_blackboard = blackboard
        self.phase = CouncilPhase.BLACKBOARD_PUBLISHED
        return blackboard

    def analyze_relations(self) -> object:
        if self.blind_blackboard is None:
            raise CouncilStateError("COUNCIL_BLACKBOARD_NOT_PUBLISHED")
        evidence_by_id = self._resolve_evidence(self.blind_blackboard.evidence_refs)
        analyzer = EvidenceRelationAnalyzer(
            comparison_registry=self.comparison_registry,
            provenance_resolver=EvidenceProvenanceResolver(self.repository),
        )
        self.relation_report = analyzer.analyze(
            blackboard=self.blind_blackboard,
            evidence_by_id=evidence_by_id,
            policy=self.plan.policy,
        )
        self.phase = CouncilPhase.RELATIONS_ANALYZED
        return self.relation_report

    def evaluate_deliberation(self) -> tuple[DeliberationDecision, object | None]:
        if self.relation_report is None or self.blind_blackboard is None:
            raise CouncilStateError("COUNCIL_RELATIONS_NOT_ANALYZED")
        evidence_by_id = self._resolve_evidence(self.blind_blackboard.evidence_refs)
        gate = DeliberationGate(self.plan.policy)
        decision, reason, request = gate.evaluate(
            council_id=self.plan.council_id,
            blackboard_id=self.blind_blackboard.blackboard_id,
            relation_report=self.relation_report,
            evidence_by_id=evidence_by_id,
            current_round=self.deliberation_round,
        )
        self.deliberation_decision = decision
        self.deliberation_request = request
        if decision == DeliberationDecision.REQUIRED:
            self.phase = CouncilPhase.DELIBERATION_REQUIRED
        else:
            self.phase = CouncilPhase.DELIBERATION_NOT_REQUIRED
        return decision, request

    def record_second_pass_outcome(self, outcome: ParticipantOutcome) -> None:
        if outcome.execution_phase != CouncilExecutionPhase.DELIBERATION_PASS:
            raise CouncilStateError("COUNCIL_INVALID_EXECUTION_PHASE")
        if self.blind_blackboard is None:
            raise CouncilStateError("COUNCIL_BLACKBOARD_NOT_PUBLISHED")
        blind_outcomes = self.blind_blackboard.participant_outcomes
        merged_outcomes = tuple(sorted((*blind_outcomes, outcome), key=lambda row: (row.expert_domain.value, row.job_id)))
        evidence_refs = self._collect_evidence_refs(merged_outcomes)
        evidence_by_id = self._resolve_evidence(evidence_refs)
        self.deliberation_blackboard = publish_blackboard_snapshot(
            council_id=self.plan.council_id,
            source_snapshot_id=self.plan.source_snapshot_id,
            evidence_refs=evidence_refs,
            participant_outcomes=merged_outcomes,
            phase=BlackboardPhase.DELIBERATION_PASS,
            revision=2,
            publication_version=self.plan.policy.blackboard_version,
            resolved_evidence=evidence_by_id,
        )
        self.deliberation_round += 1
        self.phase = CouncilPhase.DELIBERATION_COMPLETE

    def close(self) -> CouncilResult:
        self.phase = CouncilPhase.CLOSED
        outcomes = self.barrier.participant_outcomes() if self.barrier else ()
        return CouncilResult(
            council_id=self.plan.council_id,
            phase=self.phase,
            policy_identity=self.plan.policy.policy_identity,
            source_snapshot_id=self.plan.source_snapshot_id,
            blind_blackboard_id=self.blind_blackboard.blackboard_id if self.blind_blackboard else None,
            deliberation_blackboard_id=(
                self.deliberation_blackboard.blackboard_id if self.deliberation_blackboard else None
            ),
            relation_report_id=self.relation_report.report_id if self.relation_report else None,
            deliberation_decision=self.deliberation_decision,
            deliberation_request_id=(
                self.deliberation_request.request_id if self.deliberation_request else None
            ),
            participant_outcomes=outcomes,
            diagnostics=tuple(self.diagnostics),
            coverage=self._coverage(outcomes),
        )

    def run_to_deliberation_gate(self, *, strict_integrity: bool = True) -> CouncilResult:
        if self.phase == CouncilPhase.PLANNED:
            self.start_blind_phase()
        if self.phase == CouncilPhase.BLIND_RUNNING:
            raise CouncilStateError("COUNCIL_PARTICIPANTS_NOT_TERMINAL")
        if self.phase == CouncilPhase.BLIND_TERMINAL:
            self.publish_blind_blackboard(strict_integrity=strict_integrity)
        if self.phase == CouncilPhase.BLACKBOARD_PUBLISHED:
            self.analyze_relations()
        if self.phase == CouncilPhase.RELATIONS_ANALYZED:
            self.evaluate_deliberation()
        return self.close()

    def _collect_evidence_refs(self, outcomes: tuple[ParticipantOutcome, ...]) -> tuple[str, ...]:
        refs: list[str] = []
        seen: set[str] = set()
        for outcome in outcomes:
            if outcome.status != SpecialistExecutionStatus.COMPLETED:
                continue
            for evidence_id in outcome.evidence_refs:
                if evidence_id in seen:
                    continue
                seen.add(evidence_id)
                refs.append(evidence_id)
        return tuple(sorted(refs))

    def _resolve_evidence(
        self,
        evidence_refs: tuple[str, ...],
        *,
        strict_integrity: bool = True,
    ) -> dict[str, EvidenceV1]:
        resolved: dict[str, EvidenceV1] = {}
        for evidence_id in evidence_refs:
            evidence = self.repository.get_evidence(evidence_id)
            if evidence is None:
                if strict_integrity:
                    raise CouncilIntegrityError(f"COUNCIL_MISSING_EVIDENCE:{evidence_id}")
                continue
            resolved[evidence_id] = evidence
        return resolved

    def _coverage(self, outcomes: tuple[ParticipantOutcome, ...]) -> dict[str, int]:
        return {
            "planned": len(self.plan.participants),
            "terminal": len(outcomes),
            "completed": sum(1 for row in outcomes if row.status == SpecialistExecutionStatus.COMPLETED),
            "abstained": sum(1 for row in outcomes if row.status == SpecialistExecutionStatus.ABSTAINED),
            "failed": sum(1 for row in outcomes if row.status == SpecialistExecutionStatus.FAILED),
            "stale": sum(1 for row in outcomes if row.status == SpecialistExecutionStatus.STALE),
            "evidence_producing": sum(1 for row in outcomes if row.evidence_refs),
        }


def create_council_orchestrator(
    *,
    source_snapshot_id: str,
    participants,
    repository: IntelligenceRepository,
    policy: CouncilPolicy | None = None,
    decision_time_ns: int,
) -> BlindCouncilOrchestrator:
    plan = CouncilPlan.create(
        source_snapshot_id=source_snapshot_id,
        participants=participants,
        policy=policy or CouncilPolicy(),
        decision_time_ns=decision_time_ns,
    )
    return BlindCouncilOrchestrator(plan=plan, repository=repository)


__all__ = ["BlindCouncilOrchestrator", "create_council_orchestrator"]
