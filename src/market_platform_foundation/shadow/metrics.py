"""Post-hoc join metrics for shadow runs (Platformization P6).

All metrics are computed exclusively from already-appended predictions and
outcome labels — nothing is estimated at write time. Observed-outcome metrics
(hit rate, Brier, calibration, abstention) live in the ``"observed"`` output
namespace; slippage/assumption overlays are hypothetical what-if numbers and
live in a strictly disjoint ``"overlay"`` namespace. The two are never merged.

Deterministic by construction: orderings are content/timestamp-based with id
tiebreaks, bucketing is positional (no bin-edge conventions), and no wall
clock participates.
"""

from __future__ import annotations

from typing import Any, Iterable

from .records import (
    SHADOW_SCHEMA,
    ShadowOutcomeLabel,
    ShadowPredictionRecord,
    ShadowRunManifest,
)

METRICS_VERSION = "platform/shadow/metrics/1.0.0"
CALIBRATION_BUCKETS = 10

REPORT_ID_PREFIX = "SHREP-"


class WalkForwardLeakageError(ValueError):
    """Raised when the eval window starts before the train window ends."""


def join_pairs(
    predictions: Iterable[ShadowPredictionRecord],
    labels: Iterable[ShadowOutcomeLabel],
) -> list[dict[str, Any]]:
    """Join predictions with labels by prediction_id; unlabeled stay pending."""
    by_prediction: dict[str, ShadowOutcomeLabel] = {
        label.prediction_id: label for label in labels
    }
    pairs: list[dict[str, Any]] = []
    for record in predictions:
        pairs.append(
            {
                "prediction": record,
                "label": by_prediction.get(record.prediction_id),
            }
        )
    return pairs


def _scored(pairs: list[dict[str, Any]]) -> list[tuple[ShadowPredictionRecord, ShadowOutcomeLabel]]:
    return [
        (pair["prediction"], pair["label"])
        for pair in pairs
        if pair["label"] is not None and not pair["prediction"].abstained
    ]


def observed_metrics(
    pairs: list[dict[str, Any]],
    *,
    bucket_count: int = CALIBRATION_BUCKETS,
) -> dict[str, Any]:
    """Observed-outcome metrics over joined pairs (see design spec §5)."""
    total = len(pairs)
    abstained = sum(1 for pair in pairs if pair["prediction"].abstained)
    scored = _scored(pairs)
    pending = total - abstained - len(scored)
    hits = sum(
        1
        for record, label in scored
        if bool(record.predicted_positive) == label.observed_positive
    )
    if scored:
        hit_rate = hits / len(scored)
        brier = sum(
            (record.predicted_probability - (1.0 if label.observed_positive else 0.0)) ** 2
            for record, label in scored
        ) / len(scored)
        calibration = calibration_buckets(scored, bucket_count=bucket_count)
    else:
        hit_rate = None
        brier = None
        calibration = []
    return {
        "total_predictions": total,
        "scored": len(scored),
        "pending_labels": pending,
        "abstained": abstained,
        "abstention_rate": (abstained / total) if total else 0.0,
        "hits": hits,
        "hit_rate": hit_rate,
        "brier_score": brier,
        "calibration_buckets": calibration,
    }


def calibration_buckets(
    scored: list[tuple[ShadowPredictionRecord, ShadowOutcomeLabel]],
    *,
    bucket_count: int = CALIBRATION_BUCKETS,
) -> list[dict[str, Any]]:
    """Positional deciles of predicted probability vs observed frequency."""
    ordered = sorted(scored, key=lambda item: (item[0].predicted_probability, item[0].prediction_id))
    n = len(ordered)
    buckets: list[dict[str, Any]] = []
    for index in range(bucket_count):
        start = index * n // bucket_count
        end = (index + 1) * n // bucket_count
        members = ordered[start:end]
        if not members:
            buckets.append(
                {
                    "bucket": index,
                    "n": 0,
                    "mean_predicted_probability": None,
                    "observed_frequency": None,
                    "gap": None,
                }
            )
            continue
        mean_p = sum(m.predicted_probability for m, _ in members) / len(members)
        freq = sum(1 for _, lbl in members if lbl.observed_positive) / len(members)
        buckets.append(
            {
                "bucket": index,
                "n": len(members),
                "mean_predicted_probability": mean_p,
                "observed_frequency": freq,
                "gap": mean_p - freq,
            }
        )
    return buckets


def segment_by_regime(
    pairs: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Per-regime-tag segmentation; regime tags pass through uninterpreted."""
    segments: dict[str, list[dict[str, Any]]] = {}
    for pair in pairs:
        tag = pair["prediction"].regime_tag or "UNTAGGED"
        segments.setdefault(tag, []).append(pair)
    return {tag: observed_metrics(members) for tag, members in sorted(segments.items())}


def walk_forward_split(
    pairs: list[dict[str, Any]],
    manifest: ShadowRunManifest,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split into (train-side, eval-side) coverage windows without peeking.

    Assignment is by decision_time_ns against the manifest's pre-declared
    window boundaries. Eval start must be >= train end; equality is allowed
    (the train side is boundary-exclusive).
    """
    if manifest.eval_window_start_ns < manifest.train_window_end_ns:
        raise WalkForwardLeakageError("EVAL_WINDOW_OVERLAPS_TRAIN_WINDOW")
    train: list[dict[str, Any]] = []
    evaluation: list[dict[str, Any]] = []
    for pair in pairs:
        decision_ns = pair["prediction"].decision_time_ns
        if decision_ns < manifest.train_window_end_ns:
            train.append(pair)
        elif (
            manifest.eval_window_start_ns <= decision_ns <= manifest.eval_window_end_ns
        ):
            evaluation.append(pair)
    return train, evaluation


def walk_forward_evaluation(
    pairs: list[dict[str, Any]],
    manifest: ShadowRunManifest,
) -> dict[str, Any]:
    """Coverage on the train side, quality metrics only from the eval side."""
    train, evaluation = walk_forward_split(pairs, manifest)
    outside = (
        len(pairs) - len(train) - len(evaluation)
    )
    return {
        "windows": {
            "train_window_end_ns": manifest.train_window_end_ns,
            "eval_window_start_ns": manifest.eval_window_start_ns,
            "eval_window_end_ns": manifest.eval_window_end_ns,
        },
        "train_coverage": {"n": len(train)},
        "eval": observed_metrics(evaluation),
        "outside_windows": outside,
    }


def assumption_overlay(
    pairs: list[dict[str, Any]],
    *,
    slippage_bps: float,
    cost_model_version: str,
) -> dict[str, Any]:
    """Hypothetical what-if overlay under a fixed slippage assumption.

    This is NOT an observation: it re-states each labeled outcome's return
    net of the assumed cost. It must be reported only inside the disjoint
    ``overlay`` namespace and never quoted as an observed result.
    """
    overlay_rows: list[dict[str, Any]] = []
    for record, label in _scored(pairs):
        gross_bps = label.observed_return_bps
        if gross_bps is None:
            continue
        direction_multiplier = 1.0 if record.predicted_positive else -1.0
        net_bps = direction_multiplier * gross_bps - slippage_bps
        overlay_rows.append(
            {
                "prediction_id": record.prediction_id,
                "gross_bps": gross_bps,
                "net_of_assumed_slippage_bps": net_bps,
            }
        )
    positive_nets = sum(1 for row in overlay_rows if row["net_of_assumed_slippage_bps"] > 0)
    return {
        "cost_model_version": cost_model_version,
        "assumed_slippage_bps": slippage_bps,
        "n_overlaid": len(overlay_rows),
        "positive_after_assumed_costs": positive_nets,
        "rows": overlay_rows,
        "disclaimer": "ASSUMPTION_ONLY_NOT_AN_OBSERVED_OUTCOME",
    }


__all__ = [
    "CALIBRATION_BUCKETS",
    "METRICS_VERSION",
    "REPORT_ID_PREFIX",
    "WalkForwardLeakageError",
    "assumption_overlay",
    "calibration_buckets",
    "join_pairs",
    "observed_metrics",
    "segment_by_regime",
    "walk_forward_evaluation",
    "walk_forward_split",
]
