"""Deliberation gate for BUILD 12."""

from __future__ import annotations

from dataclasses import dataclass

from .identity import derive_deliberation_request_id
from .models import (
    CouncilDeliberationRequest,
    DeliberationDecision,
    DeliberationReasonCode,
    EvidenceRelationReport,
    EvidenceRelationType,
    SourceIndependence,
)
from ..contracts import EvidenceV1, ExpertDomain
from .policy import CouncilPolicy


@dataclass(frozen=True, slots=True)
class DeliberationGate:
    policy: CouncilPolicy

    def evaluate(
        self,
        *,
        council_id: str,
        blackboard_id: str,
        relation_report: EvidenceRelationReport,
        evidence_by_id: dict[str, EvidenceV1],
        current_round: int = 0,
    ) -> tuple[DeliberationDecision, DeliberationReasonCode | None, CouncilDeliberationRequest | None]:
        if not self.policy.deliberation_enabled:
            return DeliberationDecision.NOT_REQUIRED, DeliberationReasonCode.DELIBERATION_DISABLED, None
        if current_round >= self.policy.max_deliberation_rounds:
            return DeliberationDecision.NOT_REQUIRED, DeliberationReasonCode.ROUND_LIMIT_REACHED, None

        comparable_count = len(relation_report.comparable_evidence_ids)
        if comparable_count == 0:
            return (
                DeliberationDecision.NO_COMPARABLE_EVIDENCE,
                DeliberationReasonCode.NO_COMPARABLE_EVIDENCE,
                None,
            )
        if comparable_count < self.policy.min_comparable_evidence_for_conflict:
            return (
                DeliberationDecision.INSUFFICIENT_EVIDENCE,
                DeliberationReasonCode.INSUFFICIENT_MULTI_EXPERT_EVIDENCE,
                None,
            )

        conflicts = [
            relation
            for relation in relation_report.relations
            if relation.relation_type == EvidenceRelationType.CONFLICTS
        ]
        if not conflicts:
            if relation_report.agreement_groups:
                return DeliberationDecision.NOT_REQUIRED, DeliberationReasonCode.ALL_AGREEMENT, None
            if relation_report.orthogonal_evidence_ids:
                return DeliberationDecision.NOT_REQUIRED, DeliberationReasonCode.ORTHOGONAL_ONLY, None
            return DeliberationDecision.NOT_REQUIRED, DeliberationReasonCode.NO_COMPARABLE_EVIDENCE, None

        independent_conflicts = [
            relation
            for relation in conflicts
            if relation.conflict_subtype == "INDEPENDENT_CONFLICT"
            or relation.source_independence == SourceIndependence.SOURCE_INDEPENDENT
        ]
        correlated_conflicts = [
            relation
            for relation in conflicts
            if relation.conflict_subtype == "CORRELATED_CONFLICT"
            or relation.source_independence
            in {SourceIndependence.CORRELATED, SourceIndependence.STRONGLY_CORRELATED}
        ]

        selected_conflicts = independent_conflicts or correlated_conflicts
        if not selected_conflicts:
            return DeliberationDecision.NOT_REQUIRED, DeliberationReasonCode.NO_COMPARABLE_EVIDENCE, None

        selected = selected_conflicts[0]
        if (
            selected.source_independence != SourceIndependence.SOURCE_INDEPENDENT
            and self.policy.require_source_independence_for_deliberation
        ):
            return (
                DeliberationDecision.NOT_REQUIRED,
                DeliberationReasonCode.INTERPRETATION_CONFLICT_SHARED_SOURCE,
                None,
            )
        if (
            selected.source_independence != SourceIndependence.SOURCE_INDEPENDENT
            and not self.policy.deliberation_on_correlated_conflict
        ):
            return (
                DeliberationDecision.NOT_REQUIRED,
                DeliberationReasonCode.INTERPRETATION_CONFLICT_SHARED_SOURCE,
                None,
            )

        reason = (
            DeliberationReasonCode.INDEPENDENT_CONFLICT
            if selected.source_independence == SourceIndependence.SOURCE_INDEPENDENT
            else DeliberationReasonCode.INTERPRETATION_CONFLICT_SHARED_SOURCE
        )
        conflict_refs = tuple(
            sorted({selected.evidence_a_id, selected.evidence_b_id})
        )
        invited_domains = _invited_domains(conflict_refs, evidence_by_id)
        request_id = derive_deliberation_request_id(
            council_id=council_id,
            blackboard_id=blackboard_id,
            conflicting_evidence_refs=conflict_refs,
            invited_participant_domains=tuple(domain.value for domain in invited_domains),
            round_number=current_round + 1,
            policy_identity=self.policy.policy_identity,
        )
        request = CouncilDeliberationRequest(
            request_id=request_id,
            council_id=council_id,
            blackboard_id=blackboard_id,
            conflicting_evidence_refs=conflict_refs,
            invited_participant_domains=invited_domains,
            reason_code=reason,
            round_number=current_round + 1,
            relation_report_id=relation_report.report_id,
            policy_identity=self.policy.policy_identity,
        )
        return DeliberationDecision.REQUIRED, reason, request


def _invited_domains(
    conflict_refs: tuple[str, ...],
    evidence_by_id: dict[str, EvidenceV1],
) -> tuple[ExpertDomain, ...]:
    invited: set[ExpertDomain] = set()
    for evidence_id in conflict_refs:
        evidence = evidence_by_id.get(evidence_id)
        if evidence is None:
            continue
        domain = evidence.metadata.get("expert_domain")
        if domain:
            invited.add(ExpertDomain(str(domain)))
            continue
        invited.add(_infer_expert_domain(evidence.expert_id))
    return tuple(sorted(invited, key=lambda row: row.value))


def _infer_expert_domain(expert_id: str) -> ExpertDomain:
    normalized = expert_id.lower().replace("-specialist", "").replace("-", "_").upper()
    for domain in ExpertDomain:
        if domain.value == normalized or domain.value in expert_id.upper():
            return domain
    return ExpertDomain.MICROSTRUCTURE


__all__ = ["DeliberationGate"]
