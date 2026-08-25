"""Deterministic evidence relation analysis for BUILD 12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ..contracts import EvidenceV1
from .blackboard import BlackboardSnapshot
from .comparison import ComparisonAdapterRegistry, evidence_operational
from .identity import derive_relation_report_id
from .models import (
    CouncilDiagnostic,
    CouncilDiagnosticCode,
    EvidenceRelation,
    EvidenceRelationReport,
    EvidenceRelationType,
    ProvenanceGroup,
    SourceIndependence,
)
from .policy import CouncilPolicy
from .provenance import EvidenceProvenanceResolver


_OPPOSING_POLARITIES = {
    frozenset({"BULLISH", "BEARISH"}),
    frozenset({"POSITIVE", "NEGATIVE"}),
}


@dataclass(frozen=True, slots=True)
class EvidenceRelationAnalyzer:
    comparison_registry: ComparisonAdapterRegistry
    provenance_resolver: EvidenceProvenanceResolver

    def analyze(
        self,
        *,
        blackboard: BlackboardSnapshot,
        evidence_by_id: Mapping[str, EvidenceV1],
        policy: CouncilPolicy,
    ) -> EvidenceRelationReport:
        diagnostics: list[CouncilDiagnostic] = []
        excluded: list[str] = []
        comparable_views = []
        for evidence_id in blackboard.evidence_refs:
            evidence = evidence_by_id.get(evidence_id)
            if evidence is None:
                raise ValueError(f"RELATION_MISSING_EVIDENCE:{evidence_id}")
            if not evidence_operational(evidence, allow_degraded=policy.allow_degraded_evidence):
                excluded.append(evidence_id)
                if evidence.quality.state.value == "INVALID":
                    diagnostics.append(
                        CouncilDiagnostic(
                            code=CouncilDiagnosticCode.EVIDENCE_EXCLUDED_INVALID,
                            message="invalid evidence excluded",
                            details={"evidence_id": evidence_id},
                        )
                    )
                elif evidence.quality.state.value == "DEGRADED":
                    diagnostics.append(
                        CouncilDiagnostic(
                            code=CouncilDiagnosticCode.EVIDENCE_EXCLUDED_DEGRADED,
                            message="degraded evidence excluded by policy",
                            details={"evidence_id": evidence_id},
                        )
                    )
                continue
            comparable_views.append(
                self.comparison_registry.to_comparable_view(
                    evidence,
                    provenance_resolver=self.provenance_resolver,
                )
            )

        comparable_views = sorted(comparable_views, key=lambda row: row.evidence_id)
        relations: list[EvidenceRelation] = []
        for index, left in enumerate(comparable_views):
            for right in comparable_views[index + 1 :]:
                relations.append(self._pair_relation(left, right))

        relations = tuple(sorted(relations, key=lambda row: (row.evidence_a_id, row.evidence_b_id)))
        agreement_groups = _group_by_relation(relations, EvidenceRelationType.AGREES)
        conflict_groups = _group_by_relation(relations, EvidenceRelationType.CONFLICTS)
        orthogonal_ids = tuple(
            sorted(
                {
                    relation.evidence_a_id
                    for relation in relations
                    if relation.relation_type == EvidenceRelationType.ORTHOGONAL
                }
                | {
                    relation.evidence_b_id
                    for relation in relations
                    if relation.relation_type == EvidenceRelationType.ORTHOGONAL
                }
            )
        )
        incomparable_ids = tuple(
            sorted(
                view.evidence_id
                for view in comparable_views
                if not view.comparable
            )
            + [evidence_id for evidence_id in excluded]
        )
        provenance_groups = _build_provenance_groups(comparable_views)
        report_id = derive_relation_report_id(
            blackboard_id=blackboard.blackboard_id,
            policy_identity=policy.policy_identity,
            comparison_adapter_version=policy.comparison_adapter_version,
        )
        return EvidenceRelationReport(
            report_id=report_id,
            blackboard_id=blackboard.blackboard_id,
            policy_identity=policy.policy_identity,
            relations=relations,
            agreement_groups=agreement_groups,
            conflict_groups=conflict_groups,
            orthogonal_evidence_ids=orthogonal_ids,
            incomparable_evidence_ids=tuple(sorted(set(incomparable_ids))),
            provenance_groups=provenance_groups,
            excluded_evidence_ids=tuple(sorted(set(excluded))),
            comparable_evidence_ids=tuple(view.evidence_id for view in comparable_views if view.comparable),
            diagnostics=tuple(diagnostics),
        )

    def _classify_independence(self, left, right) -> SourceIndependence:
        set_a = set(left.terminal_source_ids)
        set_b = set(right.terminal_source_ids)
        if not set_a or not set_b:
            return SourceIndependence.UNKNOWN
        if set_a == set_b:
            return SourceIndependence.STRONGLY_CORRELATED
        if set_a & set_b:
            return SourceIndependence.CORRELATED
        return SourceIndependence.SOURCE_INDEPENDENT

    def _pair_relation(self, left, right) -> EvidenceRelation:
        if not left.comparable or not right.comparable:
            return EvidenceRelation(
                evidence_a_id=left.evidence_id,
                evidence_b_id=right.evidence_id,
                relation_type=EvidenceRelationType.INCOMPARABLE,
                source_independence=SourceIndependence.UNKNOWN,
            )
        if left.scope_key != right.scope_key:
            return EvidenceRelation(
                evidence_a_id=left.evidence_id,
                evidence_b_id=right.evidence_id,
                relation_type=EvidenceRelationType.INCOMPARABLE,
                source_independence=SourceIndependence.UNKNOWN,
            )
        independence = self._classify_independence(left, right)
        if left.evidence_kind != right.evidence_kind:
            return EvidenceRelation(
                evidence_a_id=left.evidence_id,
                evidence_b_id=right.evidence_id,
                relation_type=EvidenceRelationType.ORTHOGONAL,
                source_independence=independence,
            )
        if left.comparison_key != right.comparison_key:
            return EvidenceRelation(
                evidence_a_id=left.evidence_id,
                evidence_b_id=right.evidence_id,
                relation_type=EvidenceRelationType.ORTHOGONAL,
                source_independence=independence,
            )
        if _same_polarity(left.polarity, right.polarity):
            subtype = (
                "INDEPENDENT_AGREEMENT"
                if independence == SourceIndependence.SOURCE_INDEPENDENT
                else "CORRELATED_AGREEMENT"
            )
            return EvidenceRelation(
                evidence_a_id=left.evidence_id,
                evidence_b_id=right.evidence_id,
                relation_type=EvidenceRelationType.AGREES,
                source_independence=independence,
                agreement_subtype=subtype,
            )
        if _opposing_polarity(left.polarity, right.polarity):
            subtype = (
                "INDEPENDENT_CONFLICT"
                if independence == SourceIndependence.SOURCE_INDEPENDENT
                else "CORRELATED_CONFLICT"
            )
            return EvidenceRelation(
                evidence_a_id=left.evidence_id,
                evidence_b_id=right.evidence_id,
                relation_type=EvidenceRelationType.CONFLICTS,
                source_independence=independence,
                conflict_subtype=subtype,
            )
        return EvidenceRelation(
            evidence_a_id=left.evidence_id,
            evidence_b_id=right.evidence_id,
            relation_type=EvidenceRelationType.ORTHOGONAL,
            source_independence=independence,
        )


def _same_polarity(left: str, right: str) -> bool:
    return left == right and left not in {"UNKNOWN", "STRESSED"}


def _opposing_polarity(left: str, right: str) -> bool:
    return frozenset({left, right}) in _OPPOSING_POLARITIES


def _source_independence(left_signature: str, right_signature: str) -> SourceIndependence:
    if not left_signature or not right_signature:
        return SourceIndependence.UNKNOWN
    if left_signature == right_signature:
        return SourceIndependence.STRONGLY_CORRELATED
    return SourceIndependence.SOURCE_INDEPENDENT


def _group_by_relation(
    relations: tuple[EvidenceRelation, ...],
    relation_type: EvidenceRelationType,
) -> tuple[tuple[str, ...], ...]:
    groups: list[tuple[str, ...]] = []
    for relation in relations:
        if relation.relation_type != relation_type:
            continue
        group = tuple(sorted({relation.evidence_a_id, relation.evidence_b_id}))
        if group not in groups:
            groups.append(group)
    return tuple(sorted(groups))


def _build_provenance_groups(views) -> tuple[ProvenanceGroup, ...]:
    by_signature: dict[str, list[str]] = {}
    for view in views:
        by_signature.setdefault(view.source_signature_id, []).append(view.evidence_id)
    groups: list[ProvenanceGroup] = []
    for signature_id, evidence_ids in sorted(by_signature.items()):
        groups.append(
            ProvenanceGroup(
                group_id=f"PG-{signature_id}",
                source_signature_id=signature_id,
                evidence_ids=tuple(sorted(evidence_ids)),
            )
        )
    return tuple(groups)


__all__ = ["EvidenceRelationAnalyzer"]
