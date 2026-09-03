"""Complexity-adjusted promotion margins (BUILD 20)."""

from __future__ import annotations

from ..research_experiments.types import ComplexityBudget
from .types import ComplexityPolicy, ComplexityPolicyKind


def required_improvement_for_complexity(
    policy: ComplexityPolicy,
    *,
    champion_complexity: ComplexityBudget,
    challenger_complexity: ComplexityBudget,
) -> float:
    margin = policy.base_required_improvement
    if policy.kind != ComplexityPolicyKind.TIERED_MARGIN:
        return margin
    if challenger_complexity == champion_complexity:
        return margin
    if challenger_complexity == ComplexityBudget.MINOR_COMPLEXITY_INCREASE:
        return margin + policy.minor_complexity_additional_margin
    if challenger_complexity == ComplexityBudget.MAJOR_COMPLEXITY_INCREASE:
        return margin + policy.major_complexity_additional_margin
    if challenger_complexity == ComplexityBudget.SAME_COMPLEXITY:
        return margin
    # Lower complexity does not require extra margin.
    return margin


def complexity_order(budget: ComplexityBudget) -> int:
    return {
        ComplexityBudget.SAME_COMPLEXITY: 0,
        ComplexityBudget.MINOR_COMPLEXITY_INCREASE: 1,
        ComplexityBudget.MAJOR_COMPLEXITY_INCREASE: 2,
    }[budget]


def challenger_is_more_complex(
    champion_complexity: ComplexityBudget,
    challenger_complexity: ComplexityBudget,
) -> bool:
    return complexity_order(challenger_complexity) > complexity_order(champion_complexity)


__all__ = [
    "challenger_is_more_complex",
    "complexity_order",
    "required_improvement_for_complexity",
]
