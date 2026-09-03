"""Validation metric computation using BUILD 16 primitives (BUILD 19)."""

from __future__ import annotations

from ..evaluation.metrics import compute_brier_contribution, compute_log_loss_contribution
from .types import ValidationExample


def compute_example_primary_metric(
    example: ValidationExample,
    *,
    primary_metric: str,
    log_loss_epsilon: float = 1e-15,
    for_candidate: bool = True,
) -> float:
    probability = example.candidate_probability if for_candidate else example.control_probability
    if primary_metric == "brier_score":
        return compute_brier_contribution(probability, example.binary_label)
    if primary_metric == "log_loss":
        return compute_log_loss_contribution(probability, example.binary_label, log_loss_epsilon)
    raise ValueError(f"PRIMARY_METRIC_UNSUPPORTED:{primary_metric}")


def aggregate_metric_values(values: tuple[float, ...]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def evaluate_guardrails(
    examples: tuple[ValidationExample, ...],
    guardrail_metrics: tuple[str, ...],
    *,
    thresholds: dict[str, float] | None = None,
) -> dict[str, bool | None]:
    thresholds = thresholds or {}
    results: dict[str, bool | None] = {}
    for metric in guardrail_metrics:
        if metric not in thresholds:
            results[metric] = None
            continue
        values = tuple(
            compute_example_primary_metric(example, primary_metric=metric, for_candidate=True)
            for example in examples
        )
        aggregate = aggregate_metric_values(values)
        if aggregate is None:
            results[metric] = None
        else:
            results[metric] = aggregate <= thresholds[metric]
    return results


__all__ = [
    "aggregate_metric_values",
    "compute_example_primary_metric",
    "evaluate_guardrails",
]
