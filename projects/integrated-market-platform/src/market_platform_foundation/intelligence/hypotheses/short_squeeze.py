"""Short squeeze composite hypothesis engine (BUILD 13)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ..contracts import ContractKind, ContractReference, EvidenceV1, HypothesisV1, QualityState, QualitySummary
from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION, IntelligenceScope
from ..council.models import BlackboardPhase, EvidenceRelationReport, ProvenanceGroup
from ..council.provenance import EvidenceProvenanceResolver
from .adapters import (
    DEFAULT_PRODUCTION_ADAPTER_REGISTRY,
    HypothesisEvidenceAdapterRegistry,
    provenance_group_for_evidence,
)
from .contributions import ContributionStance
from .engine import (
    FactorEvaluator,
    domains_for_required_support,
    factor_domains_for_required_support,
    independent_provenance_groups_for_support,
)
from .factors import (
    REQUIRED_SHORT_SQUEEZE_FACTORS,
    FactorState,
    factor_receipt,
    falsification_codes,
    falsification_receipt,
)
from .identity import derive_hypothesis_id, scope_key_from_instrument_ids
from .policy import DEFAULT_SHORT_SQUEEZE_POLICY, ShortSqueezeHypothesisPolicy
from .types import (
    HypothesisDiagnostic,
    HypothesisDiagnosticCode,
    HypothesisEvaluationContext,
    HypothesisEvaluationResult,
    HypothesisEvaluationStatus,
    HypothesisEvidencePhasePolicy,
    HypothesisType,
)


def _scope_instruments(evidence_by_id: Mapping[str, EvidenceV1], evidence_refs: tuple[str, ...]) -> tuple[str, ...]:
    instruments: set[str] = set()
    for evidence_id in evidence_refs:
        evidence = evidence_by_id.get(evidence_id)
        if evidence is not None:
            instruments.update(evidence.scope.instrument_ids)
    return tuple(sorted(instruments))


def _merge_quality(*summaries: QualitySummary) -> QualitySummary:
    states = [row.state for row in summaries]
    flags: set[str] = set()
    for row in summaries:
        flags.update(row.flags)
    if QualityState.INVALID in states:
        state = QualityState.INVALID
    elif QualityState.DEGRADED in states or QualityState.UNKNOWN in states:
        state = QualityState.DEGRADED
    else:
        state = QualityState.GOOD
    return QualitySummary(state=state, flags=tuple(sorted(flags)))


def _claim_text(*, contested: bool) -> str:
    core = (
        "Observed independent evidence is consistent with a short-squeeze setup: "
        "short-positioning pressure is present alongside positive demand activation."
    )
    if contested:
        return f"{core} Meaningful opposing evidence is also present."
    return core


@dataclass(frozen=True, slots=True)
class ShortSqueezeHypothesisEngine:
    hypothesis_type: str = HypothesisType.SHORT_SQUEEZE_SETUP.value
    engine_id: str = "short-squeeze-hypothesis-engine"
    engine_version: str = "1"
    policy: ShortSqueezeHypothesisPolicy = DEFAULT_SHORT_SQUEEZE_POLICY
    adapter_registry: HypothesisEvidenceAdapterRegistry = DEFAULT_PRODUCTION_ADAPTER_REGISTRY
    factor_evaluator: FactorEvaluator = FactorEvaluator()

    def evaluate(self, context: HypothesisEvaluationContext) -> HypothesisEvaluationResult:
        diagnostics: list[HypothesisDiagnostic] = []
        blackboard = context.blackboard
        relation_report = context.relation_report

        if relation_report.blackboard_id != blackboard.blackboard_id:
            return HypothesisEvaluationResult(
                status=HypothesisEvaluationStatus.INVALID_INPUT,
                diagnostics=(
                    HypothesisDiagnostic(
                        HypothesisDiagnosticCode.BLACKBOARD_RELATION_MISMATCH,
                        "relation report does not belong to input blackboard",
                        {
                            "blackboard_id": blackboard.blackboard_id,
                            "relation_blackboard_id": relation_report.blackboard_id,
                        },
                    ),
                ),
            )

        if self.policy.evidence_phase_policy == HypothesisEvidencePhasePolicy.BLIND_ONLY:
            if blackboard.phase != BlackboardPhase.BLIND_PASS:
                return HypothesisEvaluationResult(
                    status=HypothesisEvaluationStatus.INVALID_INPUT,
                    diagnostics=(
                        HypothesisDiagnostic(
                            HypothesisDiagnosticCode.BLACKBOARD_PHASE_NOT_ALLOWED,
                            "default policy accepts blind-pass blackboards only",
                            {"phase": blackboard.phase.value},
                        ),
                    ),
                )

        excluded = set(relation_report.excluded_evidence_ids)
        contributions = []
        unsupported: list[str] = []
        for evidence_id in blackboard.evidence_refs:
            evidence = context.evidence_by_id.get(evidence_id)
            if evidence is None:
                return HypothesisEvaluationResult(
                    status=HypothesisEvaluationStatus.INVALID_INPUT,
                    diagnostics=(
                        HypothesisDiagnostic(
                            HypothesisDiagnosticCode.INVALID_EVIDENCE_EXCLUDED,
                            "blackboard references missing evidence",
                            {"evidence_id": evidence_id},
                        ),
                    ),
                )
            if evidence_id in excluded:
                diagnostics.append(
                    HypothesisDiagnostic(
                        HypothesisDiagnosticCode.INVALID_EVIDENCE_EXCLUDED,
                        "evidence excluded by BUILD 12 relation analysis",
                        {"evidence_id": evidence_id},
                    )
                )
                continue
            group_id = provenance_group_for_evidence(evidence_id, relation_report.provenance_groups)
            source_signature = _source_signature_from_groups(evidence_id, relation_report.provenance_groups)
            if source_signature is None:
                unsupported.append(evidence_id)
                continue
            adapted = self.adapter_registry.adapt_all(
                evidence,
                source_signature=source_signature,
                provenance_group_id=group_id,
                allow_degraded=self.policy.allow_degraded_evidence,
            )
            if not adapted:
                unsupported.append(evidence_id)
                diagnostics.append(
                    HypothesisDiagnostic(
                        HypothesisDiagnosticCode.UNSUPPORTED_EVIDENCE,
                        "no registered hypothesis adapter mapped evidence",
                        {"evidence_id": evidence_id},
                    )
                )
                continue
            contributions.extend(adapted)

        contributions_tuple = tuple(
            sorted(contributions, key=lambda row: (row.evidence_ref, row.factor, row.stance.value))
        )
        if not contributions_tuple:
            return HypothesisEvaluationResult(
                status=HypothesisEvaluationStatus.NO_APPLICABLE_EVIDENCE,
                excluded_evidence_ids=tuple(sorted(excluded | set(unsupported))),
                diagnostics=tuple(diagnostics),
            )

        factor_evaluations = self.factor_evaluator.evaluate(
            contributions_tuple,
            provenance_groups=relation_report.provenance_groups,
        )
        factor_by_name = {row.factor.value: row for row in factor_evaluations}

        missing_required = [
            factor
            for factor in self.policy.required_factors
            if factor_by_name.get(factor, None) is None
            or factor_by_name[factor].state == FactorState.MISSING
        ]
        if missing_required:
            for factor in missing_required:
                diagnostics.append(
                    HypothesisDiagnostic(
                        HypothesisDiagnosticCode.MISSING_REQUIRED_FACTOR,
                        "required mechanism factor not satisfied",
                        {"factor": factor},
                    )
                )
            return HypothesisEvaluationResult(
                status=HypothesisEvaluationStatus.INSUFFICIENT_REQUIRED_EVIDENCE,
                excluded_evidence_ids=tuple(sorted(excluded | set(unsupported))),
                diagnostics=tuple(diagnostics),
                coverage={"missing_required_factors": tuple(missing_required)},
            )

        opposed_required = [
            factor
            for factor in self.policy.required_factors
            if factor_by_name[factor].state == FactorState.OPPOSED
        ]
        if opposed_required:
            for factor in opposed_required:
                diagnostics.append(
                    HypothesisDiagnostic(
                        HypothesisDiagnosticCode.REQUIRED_FACTOR_OPPOSED,
                        "required mechanism factor is opposed",
                        {"factor": factor},
                    )
                )
            return HypothesisEvaluationResult(
                status=HypothesisEvaluationStatus.CONTRADICTED,
                excluded_evidence_ids=tuple(sorted(excluded | set(unsupported))),
                diagnostics=tuple(diagnostics),
                coverage={"opposed_required_factors": tuple(opposed_required)},
            )

        contested_required = [
            factor
            for factor in self.policy.required_factors
            if factor_by_name[factor].state == FactorState.CONTESTED
        ]
        if contested_required and not self.policy.allow_contested_emission:
            return HypothesisEvaluationResult(
                status=HypothesisEvaluationStatus.CONTRADICTED,
                excluded_evidence_ids=tuple(sorted(excluded | set(unsupported))),
                diagnostics=tuple(
                    *diagnostics,
                    *(
                        HypothesisDiagnostic(
                            HypothesisDiagnosticCode.REQUIRED_FACTOR_CONTESTED,
                            "required factor contested and contested emission disabled",
                            {"factor": factor},
                        )
                        for factor in contested_required
                    ),
                ),
            )

        required_factor_domains = factor_domains_for_required_support(
            factor_evaluations,
            self.policy.required_factors,
        )
        if not all(required_factor_domains.get(factor) for factor in self.policy.required_factors):
            return HypothesisEvaluationResult(
                status=HypothesisEvaluationStatus.INSUFFICIENT_DOMAIN_COVERAGE,
                excluded_evidence_ids=tuple(sorted(excluded | set(unsupported))),
                diagnostics=(
                    *diagnostics,
                    HypothesisDiagnostic(
                        HypothesisDiagnosticCode.INSUFFICIENT_DOMAIN_COVERAGE,
                        "required factors must be supported by distinct expert domains",
                        {"required_factor_domains": required_factor_domains},
                    ),
                ),
            )

        support_domains = domains_for_required_support(factor_evaluations, self.policy.required_factors)
        if len(support_domains) < self.policy.minimum_expert_domains:
            return HypothesisEvaluationResult(
                status=HypothesisEvaluationStatus.INSUFFICIENT_DOMAIN_COVERAGE,
                excluded_evidence_ids=tuple(sorted(excluded | set(unsupported))),
                diagnostics=(
                    *diagnostics,
                    HypothesisDiagnostic(
                        HypothesisDiagnosticCode.INSUFFICIENT_DOMAIN_COVERAGE,
                        "insufficient distinct expert domains for required support",
                        {"domains": support_domains},
                    ),
                ),
            )

        independent_groups = independent_provenance_groups_for_support(
            factor_evaluations=factor_evaluations,
            required_factors=self.policy.required_factors,
            provenance_groups=relation_report.provenance_groups,
        )
        if any(not group for group in relation_report.provenance_groups):
            pass
        support_refs = {ref for row in factor_evaluations for ref in row.support_refs}
        unknown_provenance = any(
            evidence_id in support_refs
            and provenance_group_for_evidence(evidence_id, relation_report.provenance_groups) is None
            for evidence_id in blackboard.evidence_refs
        )
        if unknown_provenance or len(independent_groups) < self.policy.minimum_independent_provenance_groups:
            return HypothesisEvaluationResult(
                status=HypothesisEvaluationStatus.INSUFFICIENT_INDEPENDENCE,
                excluded_evidence_ids=tuple(sorted(excluded | set(unsupported))),
                diagnostics=(
                    *diagnostics,
                    HypothesisDiagnostic(
                        HypothesisDiagnosticCode.INSUFFICIENT_INDEPENDENT_PROVENANCE,
                        "required support does not span enough independent provenance groups",
                        {
                            "independent_groups": independent_groups,
                            "minimum_required": self.policy.minimum_independent_provenance_groups,
                        },
                    ),
                ),
            )

        supporting_ids: set[str] = set()
        opposing_ids: set[str] = set()
        required_qualities: list[QualitySummary] = []
        for row in contributions_tuple:
            if row.stance == ContributionStance.SUPPORTS:
                supporting_ids.add(row.evidence_ref)
                if row.factor in self.policy.required_factors:
                    required_qualities.append(row.quality)
            elif row.stance == ContributionStance.OPPOSES:
                opposing_ids.add(row.evidence_ref)
            elif row.stance == ContributionStance.CONTEXT and row.factor in self.policy.optional_factors:
                supporting_ids.add(row.evidence_ref)

        for row in factor_evaluations:
            if row.factor.value in self.policy.required_factors:
                supporting_ids.update(row.support_refs)
                opposing_ids.update(row.oppose_refs)

        supporting_ids = {value for value in supporting_ids if value in blackboard.evidence_refs}
        opposing_ids = {value for value in opposing_ids if value in blackboard.evidence_refs}

        if not self.policy.allow_degraded_evidence and any(
            row.quality.state == QualityState.DEGRADED for row in contributions_tuple if row.factor in self.policy.required_factors
        ):
            return HypothesisEvaluationResult(
                status=HypothesisEvaluationStatus.INSUFFICIENT_REQUIRED_EVIDENCE,
                diagnostics=(
                    HypothesisDiagnostic(
                        HypothesisDiagnosticCode.DEGRADED_REQUIRED_EVIDENCE,
                        "degraded required evidence excluded by policy",
                        {},
                    ),
                ),
            )

        instrument_ids = _scope_instruments(context.evidence_by_id, blackboard.evidence_refs)
        if len(instrument_ids) != 1:
            return HypothesisEvaluationResult(
                status=HypothesisEvaluationStatus.INVALID_INPUT,
                diagnostics=(
                    HypothesisDiagnostic(
                        HypothesisDiagnosticCode.INVALID_EVIDENCE_EXCLUDED,
                        "short squeeze hypothesis requires exactly one instrument scope",
                        {"instrument_ids": instrument_ids},
                    ),
                ),
            )

        scope_key = scope_key_from_instrument_ids(instrument_ids)
        generated_at_ns = context.decision_time_ns or context.snapshot.decision_time_ns if context.snapshot else 0
        hypothesis_id = derive_hypothesis_id(
            hypothesis_type=self.hypothesis_type,
            blackboard_id=blackboard.blackboard_id,
            snapshot_id=blackboard.source_snapshot_id,
            engine_id=self.engine_id,
            engine_version=self.engine_version,
            policy_identity=self.policy.policy_identity,
            scope_key=scope_key,
        )

        status = (
            HypothesisEvaluationStatus.EMITTED_CONTESTED
            if contested_required
            else HypothesisEvaluationStatus.EMITTED
        )
        receipt = factor_receipt(factor_evaluations)
        hypothesis = HypothesisV1(
            hypothesis_id=hypothesis_id,
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            hypothesis_type=self.hypothesis_type,
            scope=IntelligenceScope(instrument_ids=instrument_ids),
            generated_at_ns=generated_at_ns,
            snapshot_id=blackboard.source_snapshot_id,
            quality=_merge_quality(*required_qualities) if required_qualities else QualitySummary(state=QualityState.GOOD),
            supporting_evidence_ids=tuple(sorted(supporting_ids)),
            contradicting_evidence_ids=tuple(sorted(opposing_ids)),
            support_score=None,
            mechanism={
                "factor_receipt": receipt,
                "engine_id": self.engine_id,
                "engine_version": self.engine_version,
                "evaluation_status": status.value,
            },
            invalidation_conditions=falsification_codes(),
            missing_information=tuple(contested_required),
            lineage_refs=(
                ContractReference(kind=ContractKind.SNAPSHOT.value, id=blackboard.source_snapshot_id),
            ),
            explanation=_claim_text(contested=bool(contested_required)),
            metadata={
                "blackboard_id": blackboard.blackboard_id,
                "policy_identity": self.policy.policy_identity,
                "factor_receipt": receipt,
                "independent_provenance_groups": list(independent_groups),
                "expert_domains": list(support_domains),
                "falsification_receipt": falsification_receipt(),
                "falsification_criteria_version": self.policy.falsification_criteria_version,
                "evidence_phase_policy": self.policy.evidence_phase_policy.value,
            },
        )
        return HypothesisEvaluationResult(
            status=status,
            hypothesis=hypothesis,
            supporting_evidence_ids=tuple(sorted(supporting_ids)),
            opposing_evidence_ids=tuple(sorted(opposing_ids)),
            excluded_evidence_ids=tuple(sorted(excluded | set(unsupported))),
            diagnostics=tuple(diagnostics),
            coverage={
                "factor_receipt": receipt,
                "independent_provenance_groups": independent_groups,
                "expert_domains": support_domains,
                "contested_required_factors": tuple(contested_required),
            },
        )


def _source_signature_from_groups(
    evidence_id: str,
    provenance_groups: tuple[ProvenanceGroup, ...],
):
    from ..council.models import SourceSignature

    for group in provenance_groups:
        if evidence_id in group.evidence_ids:
            return SourceSignature(
                signature_id=group.source_signature_id,
                terminal_source_ids=(),
            )
    return None


__all__ = ["ShortSqueezeHypothesisEngine"]
