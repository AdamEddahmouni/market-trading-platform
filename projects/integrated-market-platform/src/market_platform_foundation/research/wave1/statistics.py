"""Deterministic moving-block bootstrap for Wave 1 (vendored from validation/statistics)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .errors import Wave1HarnessError


@dataclass(frozen=True, slots=True)
class Wave1StatisticalPlan:
    block_length: int
    replicate_count: int
    seed: int
    confidence_level: float
    minimum_paired_sample: int
    criterion_upper_ci_bound_lt_zero: bool = False


@dataclass(frozen=True, slots=True)
class Wave1PairedMetricDelta:
    metric_name: str
    mean_delta: float
    sample_count: int
    ci_lower: float | None = None
    ci_upper: float | None = None
    block_length: int | None = None
    replicate_count: int | None = None
    seed: int | None = None


DEFAULT_WAVE1_STATISTICAL_PLAN = Wave1StatisticalPlan(
    block_length=5,
    replicate_count=400,
    seed=20260914,
    confidence_level=0.95,
    minimum_paired_sample=20,
    criterion_upper_ci_bound_lt_zero=False,
)


def _deterministic_uniform(seed: int, index: int) -> float:
    x = (seed * 1_000_003 + index * 97_531) & 0xFFFFFFFF
    x = (x * 1_103_515_245 + 12_345) & 0x7FFFFFFF
    return x / 0x7FFFFFFF


def paired_metric_deltas(
    candidate_losses: tuple[float, ...],
    control_losses: tuple[float, ...],
) -> tuple[float, ...]:
    if len(candidate_losses) != len(control_losses):
        raise Wave1HarnessError("W1_PAIRED_LOSS_LENGTH_MISMATCH")
    return tuple(c - t for c, t in zip(candidate_losses, control_losses, strict=True))


def moving_block_bootstrap_ci(
    deltas: tuple[float, ...],
    plan: Wave1StatisticalPlan,
) -> Wave1PairedMetricDelta:
    n = len(deltas)
    if n == 0:
        return Wave1PairedMetricDelta(metric_name="paired_delta", mean_delta=0.0, sample_count=0)
    if plan.block_length > n:
        raise Wave1HarnessError(
            "W1_BLOCK_LENGTH_EXCEEDS_SAMPLE",
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
    return Wave1PairedMetricDelta(
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
    paired: Wave1PairedMetricDelta,
    plan: Wave1StatisticalPlan,
) -> str:
    if paired.sample_count < plan.minimum_paired_sample:
        return "INCONCLUSIVE_INSUFFICIENT_SAMPLE"
    if plan.criterion_upper_ci_bound_lt_zero:
        if paired.ci_upper is not None and paired.ci_upper < 0:
            return "MEETS_PRE_REGISTERED_CRITERIA"
        return "DOES_NOT_MEET_PRE_REGISTERED_CRITERIA"
    return "INCONCLUSIVE"


def evaluate_wave1_paired_delta(
    candidate_losses: tuple[float, ...],
    control_losses: tuple[float, ...],
    *,
    plan: Wave1StatisticalPlan | None = None,
) -> dict[str, object]:
    plan = plan or DEFAULT_WAVE1_STATISTICAL_PLAN
    deltas = paired_metric_deltas(candidate_losses, control_losses)
    paired = moving_block_bootstrap_ci(deltas, plan)
    criterion = evaluate_statistical_criteria(paired, plan)
    return {
        "criterion_status": criterion,
        "deltas": deltas,
        "paired": paired,
        "plan": plan,
    }
