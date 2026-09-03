"""Pure predictive metrics over frozen cohort rows (BUILD 16)."""

from __future__ import annotations

import math

from .errors import EvaluationError
from .provenance import probability_for_view, validate_evaluated_probability
from .types import AggregateStatus, EvaluationCohortRow, EvaluationSpec, PredictiveMetrics


def clip_probability(p: float, epsilon: float) -> tuple[float, bool]:
    clipped = min(max(p, epsilon), 1.0 - epsilon)
    return clipped, clipped != p


def compute_brier_contribution(p: float, y: int) -> float:
    return (p - y) ** 2


def compute_log_loss_contribution(p: float, y: int, epsilon: float) -> float:
    clipped, _ = clip_probability(p, epsilon)
    if y == 1:
        return -math.log(clipped)
    return -math.log(1.0 - clipped)


def compute_predictive_metrics(
    rows: tuple[EvaluationCohortRow, ...],
    spec: EvaluationSpec,
) -> PredictiveMetrics:
    if not rows:
        return PredictiveMetrics(
            status=AggregateStatus.EMPTY_COHORT,
            sample_count=0,
            brier_score=None,
            log_loss=None,
            directional_hit_rate=None,
            mean_confidence=None,
        )

    contributions_brier: list[tuple[str, float]] = []
    contributions_log: list[tuple[str, float]] = []
    clip_count = 0
    hits = 0
    confidences: list[float] = []

    for row in rows:
        probability = probability_for_view(row.forecast, spec.probability_view)
        if probability is None or row.binary_label is None:
            continue
        try:
            p = validate_evaluated_probability(probability)
        except EvaluationError:
            raise
        clipped, was_clipped = clip_probability(p, spec.log_loss_epsilon)
        if was_clipped:
            clip_count += 1
        y = row.binary_label
        brier = compute_brier_contribution(p, y)
        log_loss = compute_log_loss_contribution(p, y, spec.log_loss_epsilon)
        contributions_brier.append((row.forecast.forecast_id, brier))
        contributions_log.append((row.forecast.forecast_id, log_loss))
        confidences.append(max(p, 1.0 - p))
        predicted_up = p >= 0.5
        actual_up = y == 1
        if predicted_up == actual_up:
            hits += 1

    count = len(contributions_brier)
    if count == 0:
        return PredictiveMetrics(
            status=AggregateStatus.PROBABILITY_UNAVAILABLE,
            sample_count=len(rows),
            brier_score=None,
            log_loss=None,
            directional_hit_rate=None,
            mean_confidence=None,
            boundary_clip_count=clip_count,
        )

    brier_score = sum(value for _, value in contributions_brier) / count
    log_loss = sum(value for _, value in contributions_log) / count
    hit_rate = hits / count
    mean_confidence = sum(confidences) / count

    return PredictiveMetrics(
        status=AggregateStatus.OK,
        sample_count=count,
        brier_score=brier_score,
        log_loss=log_loss,
        directional_hit_rate=hit_rate,
        mean_confidence=mean_confidence,
        boundary_clip_count=clip_count,
        per_row_brier=tuple(sorted(contributions_brier, key=lambda item: (-item[1], item[0]))),
        per_row_log_loss=tuple(sorted(contributions_log, key=lambda item: (-item[1], item[0]))),
    )


__all__ = [
    "clip_probability",
    "compute_brier_contribution",
    "compute_log_loss_contribution",
    "compute_predictive_metrics",
]
