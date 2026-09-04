"""Deterministic moving-block bootstrap for paired metric deltas (BUILD 19)."""

from __future__ import annotations

import math

from .errors import ValidationError
from .types import PairedMetricDelta, StatisticalPlan


def _deterministic_uniform(seed: int, index: int) -> float:
    """Simple deterministic pseudo-random in [0, 1)."""
    x = (seed * 1_000_003 + index * 97_531) & 0xFFFFFFFF
    x = (x * 1_103_515_245 + 12_345) & 0x7FFFFFFF
    return x / 0x7FFFFFFF


def paired_metric_deltas(
    candidate_losses: tuple[float, ...],
    control_losses: tuple[float, ...],
) -> tuple[float, ...]:
    if len(candidate_losses) != len(control_losses):
        raise ValidationError("PAIRED_LOSS_LENGTH_MISMATCH")
    return tuple(c - t for c, t in zip(candidate_losses, control_losses, strict=True))


def moving_block_bootstrap_ci(
    deltas: tuple[float, ...],
    plan: StatisticalPlan,
) -> PairedMetricDelta:
    n = len(deltas)
    if n == 0:
        return PairedMetricDelta(metric_name="paired_delta", mean_delta=0.0, sample_count=0)
    if plan.block_length > n:
        raise ValidationError(
            "BLOCK_LENGTH_EXCEEDS_SAMPLE",
            details={"block_length": plan.block_length, "sample_size": n},
        )

    mean_delta = sum(deltas) / n
    replicate_means: list[float] = []
    blocks_needed = math.ceil(n / plan.block_length)
    max_start = max(0, n - plan.block_length)

    for rep in range(plan.replicate_count):
        sample: list[float] = []
        for block_idx in range(blocks_needed):
            if max_start == 0:
                start = 0
            else:
                draw = _deterministic_uniform(plan.seed, rep * blocks_needed + block_idx)
                start = int(draw * (max_start + 1))
            block = list(deltas[start : start + plan.block_length])
            sample.extend(block)
        sample = sample[:n]
        replicate_means.append(sum(sample) / len(sample))

    replicate_means.sort()
    alpha = 1.0 - plan.confidence_level
    lower_idx = int((alpha / 2) * plan.replicate_count)
    upper_idx = min(plan.replicate_count - 1, int((1 - alpha / 2) * plan.replicate_count))
    return PairedMetricDelta(
        metric_name="paired_delta",
        mean_delta=mean_delta,
        sample_count=n,
        ci_lower=replicate_means[lower_idx],
        ci_upper=replicate_means[upper_idx],
        block_length=plan.block_length,
        replicate_count=plan.replicate_count,
        seed=plan.seed,
    )


def evaluate_statistical_criteria(
    paired: PairedMetricDelta,
    plan: StatisticalPlan,
) -> str:
    if paired.sample_count < plan.minimum_paired_sample:
        return "INCONCLUSIVE_INSUFFICIENT_SAMPLE"
    if plan.criterion_upper_ci_bound_lt_zero:
        if paired.ci_upper is not None and paired.ci_upper < 0:
            return "MEETS_PRE_REGISTERED_CRITERIA"
        return "DOES_NOT_MEET_PRE_REGISTERED_CRITERIA"
    return "INCONCLUSIVE"


__all__ = [
    "evaluate_statistical_criteria",
    "moving_block_bootstrap_ci",
    "paired_metric_deltas",
]
