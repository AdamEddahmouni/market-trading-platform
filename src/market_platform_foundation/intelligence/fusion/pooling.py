"""Dependency-group-equalized linear probability pooling for BUILD 14."""

from __future__ import annotations

import math

from ..contracts.common import validate_probability
from .errors import FusionInputError
from .types import ForecastDependenceGroup, FusionContributorRef


def validate_probability_finite(value: float) -> None:
    if not math.isfinite(value):
        raise FusionInputError("INVALID_PROBABILITY_NOT_FINITE")
    validate_probability(value)


def within_group_probability(
    contributors: tuple[FusionContributorRef, ...],
    *,
    contributor_weights: dict[str, float] | None = None,
) -> float:
    if not contributors:
        raise FusionInputError("EMPTY_GROUP")
    weighted_sum = 0.0
    weight_total = 0.0
    for ref in contributors:
        probability = ref.forecast.estimate.probability
        if probability is None:
            raise FusionInputError(f"MISSING_PROBABILITY:{ref.forecast.forecast_id}")
        validate_probability_finite(probability)
        weight = 1.0
        if contributor_weights is not None:
            weight = contributor_weights.get(ref.forecast.forecast_id, 1.0)
        weighted_sum += weight * probability
        weight_total += weight
    if weight_total <= 0:
        raise FusionInputError("GROUP_WEIGHT_TOTAL_INVALID")
    return weighted_sum / weight_total


def across_group_probability(
    groups: tuple[ForecastDependenceGroup, ...],
    group_probabilities: dict[str, float],
    *,
    group_weights: dict[str, float] | None = None,
) -> float:
    if not groups:
        raise FusionInputError("NO_GROUPS")
    if len(groups) == 1:
        group = groups[0]
        return group_probabilities[group.group_id]
    weighted_sum = 0.0
    weight_total = 0.0
    for group in groups:
        probability = group_probabilities[group.group_id]
        validate_probability_finite(probability)
        weight = 1.0
        if group_weights is not None:
            weight = group_weights.get(group.group_id, 1.0)
        weighted_sum += weight * probability
        weight_total += weight
    if weight_total <= 0:
        raise FusionInputError("CROSS_GROUP_WEIGHT_TOTAL_INVALID")
    return weighted_sum / weight_total


__all__ = ["across_group_probability", "validate_probability_finite", "within_group_probability"]
