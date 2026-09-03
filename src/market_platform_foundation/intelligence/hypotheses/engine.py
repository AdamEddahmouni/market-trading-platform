"""Factor evaluation and composite hypothesis engine protocol."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..contracts import ExpertDomain
from ..council.models import ProvenanceGroup
from .contributions import ContributionStance, HypothesisContribution
from .factors import (
    OPPOSING_SHORT_SQUEEZE_FACTORS,
    OPTIONAL_SHORT_SQUEEZE_FACTORS,
    REQUIRED_SHORT_SQUEEZE_FACTORS,
    FactorEvaluation,
    FactorState,
    ShortSqueezeFactor,
)


def _factor_state(
  *,
  support_refs: tuple[str, ...],
  oppose_refs: tuple[str, ...],
  required: bool,
) -> FactorState:
    if support_refs and oppose_refs:
        return FactorState.CONTESTED
    if oppose_refs and not support_refs:
        return FactorState.OPPOSED if required else FactorState.ABSENT
    if support_refs:
        return FactorState.SUPPORTED if required else FactorState.PRESENT
    return FactorState.MISSING if required else FactorState.ABSENT


@dataclass(frozen=True, slots=True)
class FactorEvaluator:
    def evaluate(
        self,
        contributions: tuple[HypothesisContribution, ...],
        *,
        provenance_groups: tuple[ProvenanceGroup, ...],
    ) -> tuple[FactorEvaluation, ...]:
        by_factor: dict[str, list[HypothesisContribution]] = {}
        for row in contributions:
            by_factor.setdefault(row.factor, []).append(row)

        evaluations: list[FactorEvaluation] = []
        all_factors = (
            *REQUIRED_SHORT_SQUEEZE_FACTORS,
            *OPTIONAL_SHORT_SQUEEZE_FACTORS,
            *OPPOSING_SHORT_SQUEEZE_FACTORS,
        )
        for factor in all_factors:
            rows = by_factor.get(factor.value, [])
            support_refs = tuple(
                sorted(
                    {
                        row.evidence_ref
                        for row in rows
                        if row.stance in {ContributionStance.SUPPORTS, ContributionStance.CONTEXT}
                    }
                )
            )
            oppose_refs = tuple(
                sorted({row.evidence_ref for row in rows if row.stance == ContributionStance.OPPOSES})
            )
            domains = tuple(sorted({row.expert_domain.value for row in rows}))
            group_ids = tuple(
                sorted(
                    {
                        row.provenance_group_id
                        for row in rows
                        if row.provenance_group_id and row.evidence_ref in support_refs
                    }
                )
            )
            required = factor in REQUIRED_SHORT_SQUEEZE_FACTORS
            state = _factor_state(
                support_refs=support_refs,
                oppose_refs=oppose_refs,
                required=required,
            )
            evaluations.append(
                FactorEvaluation(
                    factor=factor,
                    state=state,
                    support_refs=support_refs,
                    oppose_refs=oppose_refs,
                    domains=domains,
                    provenance_groups=group_ids,
                )
            )
        return tuple(evaluations)


def independent_provenance_groups_for_support(
    *,
    factor_evaluations: tuple[FactorEvaluation, ...],
    required_factors: tuple[str, ...],
    provenance_groups: tuple[ProvenanceGroup, ...],
) -> tuple[str, ...]:
    support_refs: set[str] = set()
    for row in factor_evaluations:
        if row.factor.value in required_factors and row.support_refs:
            support_refs.update(row.support_refs)
    matched: set[str] = set()
    for group in provenance_groups:
        if any(evidence_id in support_refs for evidence_id in group.evidence_ids):
            matched.add(group.group_id)
    return tuple(sorted(matched))


def domains_for_required_support(
    factor_evaluations: tuple[FactorEvaluation, ...],
    required_factors: tuple[str, ...],
) -> tuple[str, ...]:
    domains: set[str] = set()
    for row in factor_evaluations:
        if row.factor.value in required_factors and row.support_refs:
            domains.update(row.domains)
    return tuple(sorted(domains))


def factor_domains_for_required_support(
    factor_evaluations: tuple[FactorEvaluation, ...],
    required_factors: tuple[str, ...],
) -> dict[str, tuple[str, ...]]:
    result: dict[str, set[str]] = {factor: set() for factor in required_factors}
    for row in factor_evaluations:
        if row.factor.value in required_factors and row.support_refs:
            result[row.factor.value].update(row.domains)
    return {factor: tuple(sorted(domains)) for factor, domains in sorted(result.items())}


class CompositeHypothesisEngine(Protocol):
    hypothesis_type: str
    engine_id: str
    engine_version: str

    def evaluate(self, context):  # noqa: ANN001 - protocol boundary
        ...


__all__ = [
    "CompositeHypothesisEngine",
    "FactorEvaluator",
    "domains_for_required_support",
    "factor_domains_for_required_support",
    "independent_provenance_groups_for_support",
]
