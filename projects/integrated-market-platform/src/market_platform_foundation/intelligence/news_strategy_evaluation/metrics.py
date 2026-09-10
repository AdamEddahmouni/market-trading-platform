"""Baseline comparison, calibration, and evaluation metrics."""

from __future__ import annotations

import statistics
from typing import Iterable

from .contracts import (
    CalibrationBucket,
    CalibrationReport,
    DirectionalLabel,
    EvaluationSampleResult,
    OutcomeQuality,
    PolicyClassification,
    PolicyMetrics,
    RealizedOutcome,
    StrategyEvaluationDecision,
)
from .decisions import is_abstention


def _primary_horizon_outcomes(
    outcomes: tuple[RealizedOutcome, ...],
    horizon_id: str,
) -> RealizedOutcome | None:
    for outcome in outcomes:
        if outcome.horizon_id == horizon_id:
            return outcome
    return outcomes[0] if outcomes else None


def _directional_correct(
    decision: StrategyEvaluationDecision,
    outcome: RealizedOutcome,
) -> bool | None:
    if outcome.quality != OutcomeQuality.COMPLETE or outcome.directional_label is None:
        return None
    if decision.normalized_directional_units == 0:
        return outcome.directional_label == DirectionalLabel.FLAT
    if decision.normalized_directional_units > 0:
        return outcome.directional_label == DirectionalLabel.UP
    return outcome.directional_label == DirectionalLabel.DOWN


def compute_policy_metrics(
    *,
    policy_id: str,
    policy_version: str,
    classification: PolicyClassification,
    samples: Iterable[EvaluationSampleResult],
    primary_horizon_id: str,
    decisions_attr: str,
    outcomes_attr: str,
) -> PolicyMetrics:
    sample_list = list(samples)
    evaluated = [
        s
        for s in sample_list
        if not s.excluded
        and getattr(s, decisions_attr) is not None
        and getattr(s, outcomes_attr)
    ]
    decisions = [getattr(s, decisions_attr) for s in evaluated]
    abstentions = sum(1 for d in decisions if d and is_abstention(d))

    correctness: list[bool] = []
    forward_returns: list[float] = []
    normalized_returns: list[float] = []
    mfes: list[float] = []
    maes: list[float] = []

    for sample in evaluated:
        decision = getattr(sample, decisions_attr)
        outcomes = getattr(sample, outcomes_attr)
        if decision is None:
            continue
        outcome = _primary_horizon_outcomes(outcomes, primary_horizon_id)
        if outcome is None:
            continue
        correct = _directional_correct(decision, outcome)
        if correct is not None:
            correctness.append(correct)
        if outcome.raw_return is not None:
            forward_returns.append(outcome.raw_return)
        if outcome.normalized_directional_return is not None:
            normalized_returns.append(outcome.normalized_directional_return)
        if outcome.maximum_favorable_excursion is not None:
            mfes.append(outcome.maximum_favorable_excursion)
        if outcome.maximum_adverse_excursion is not None:
            maes.append(outcome.maximum_adverse_excursion)

    def _mean(values: list[float]) -> float | None:
        return statistics.mean(values) if values else None

    def _median(values: list[float]) -> float | None:
        return statistics.median(values) if values else None

    positive_rate = None
    if normalized_returns:
        positive_rate = sum(1 for v in normalized_returns if v > 0) / len(normalized_returns)

    return PolicyMetrics(
        policy_id=policy_id,
        policy_version=policy_version,
        policy_classification=classification,
        sample_count=len(sample_list),
        evaluated_count=len(evaluated),
        excluded_count=sum(1 for s in sample_list if s.excluded),
        abstention_count=abstentions,
        directional_accuracy=(sum(correctness) / len(correctness)) if correctness else None,
        mean_forward_return=_mean(forward_returns),
        median_forward_return=_median(forward_returns),
        positive_outcome_rate=positive_rate,
        mean_mfe=_mean(mfes),
        mean_mae=_mean(maes),
    )


def compute_ai_incremental_delta(
    baseline: PolicyMetrics,
    enhanced: PolicyMetrics,
) -> dict[str, float | None]:
    def _delta(a: float | None, b: float | None) -> float | None:
        if a is None or b is None:
            return None
        return b - a

    return {
        "directional_accuracy_delta": _delta(baseline.directional_accuracy, enhanced.directional_accuracy),
        "mean_forward_return_delta": _delta(baseline.mean_forward_return, enhanced.mean_forward_return),
        "median_forward_return_delta": _delta(baseline.median_forward_return, enhanced.median_forward_return),
        "positive_outcome_rate_delta": _delta(baseline.positive_outcome_rate, enhanced.positive_outcome_rate),
        "mean_mfe_delta": _delta(baseline.mean_mfe, enhanced.mean_mfe),
        "mean_mae_delta": _delta(baseline.mean_mae, enhanced.mean_mae),
        "abstention_rate_delta": _delta(
            (baseline.abstention_count / baseline.evaluated_count) if baseline.evaluated_count else None,
            (enhanced.abstention_count / enhanced.evaluated_count) if enhanced.evaluated_count else None,
        ),
    }


def _bucket_calibration(
    samples: list[EvaluationSampleResult],
    *,
    bucket_key_fn,
    bucket_label_fn,
    primary_horizon_id: str,
) -> tuple[CalibrationBucket, ...]:
    buckets: dict[str, list[bool | None]] = {}
    labels: dict[str, str] = {}
    for sample in samples:
        if sample.excluded or not sample.enhanced_decision or not sample.feature_snapshot:
            continue
        intel = sample.feature_snapshot.intelligence
        if intel is None:
            continue
        key = bucket_key_fn(intel)
        if not key:
            continue
        labels[key] = bucket_label_fn(intel)
        outcome = _primary_horizon_outcomes(sample.enhanced_outcomes, primary_horizon_id)
        if outcome is None or sample.enhanced_decision is None:
            continue
        correct = _directional_correct(sample.enhanced_decision, outcome)
        buckets.setdefault(key, []).append(correct)

    result: list[CalibrationBucket] = []
    for key, values in sorted(buckets.items()):
        known = [v for v in values if v is not None]
        correct_count = sum(1 for v in known if v)
        incorrect = len(known) - correct_count
        rate = (correct_count / len(known)) if known else None
        result.append(
            CalibrationBucket(
                bucket_id=key,
                bucket_label=labels.get(key, key),
                count=len(known),
                realized_correct=correct_count,
                realized_incorrect=incorrect,
                empirical_correctness_rate=rate,
            )
        )
    return tuple(result)


def compute_calibration_report(
    samples: list[EvaluationSampleResult],
    *,
    primary_horizon_id: str,
) -> CalibrationReport:
    def sentiment_key(intel) -> str:
        return intel.sentiment_label or "UNKNOWN"

    def impact_key(intel) -> str:
        return intel.market_impact_level or "UNKNOWN"

    def confidence_key(intel) -> str:
        if intel.model_confidence is None:
            return "UNKNOWN"
        if intel.model_confidence < 0.4:
            return "LOW"
        if intel.model_confidence < 0.7:
            return "MEDIUM"
        return "HIGH"

    return CalibrationReport(
        sentiment_buckets=_bucket_calibration(
            samples,
            bucket_key_fn=sentiment_key,
            bucket_label_fn=lambda i: f"sentiment={i.sentiment_label}",
            primary_horizon_id=primary_horizon_id,
        ),
        impact_buckets=_bucket_calibration(
            samples,
            bucket_key_fn=impact_key,
            bucket_label_fn=lambda i: f"impact={i.market_impact_level}",
            primary_horizon_id=primary_horizon_id,
        ),
        confidence_buckets=_bucket_calibration(
            samples,
            bucket_key_fn=confidence_key,
            bucket_label_fn=lambda i: f"confidence_bucket={confidence_key(i)}",
            primary_horizon_id=primary_horizon_id,
        ),
    )


__all__ = [
    "compute_ai_incremental_delta",
    "compute_calibration_report",
    "compute_policy_metrics",
]
