"""Calibration metrics for SS P3 baseline models."""

from __future__ import annotations

from typing import Sequence


def brier_score(predictions: Sequence[float], labels: Sequence[bool]) -> float:
    if not predictions or len(predictions) != len(labels):
        return 1.0
    total = 0.0
    for pred, label in zip(predictions, labels):
        y = 1.0 if label else 0.0
        total += (pred - y) ** 2
    return round(total / len(predictions), 6)


def pr_auc_approx(predictions: Sequence[float], labels: Sequence[bool]) -> float:
    """Approximate PR-AUC via step integration over sorted predictions."""
    pairs = sorted(
        [(float(pred), bool(label)) for pred, label in zip(predictions, labels)],
        key=lambda row: row[0],
        reverse=True,
    )
    positives = sum(1 for _, label in pairs if label)
    if positives == 0:
        return 0.0
    tp = 0
    fp = 0
    prev_recall = 0.0
    auc = 0.0
    for pred, label in pairs:
        if label:
            tp += 1
        else:
            fp += 1
        recall = tp / positives
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        auc += precision * (recall - prev_recall)
        prev_recall = recall
    return round(auc, 6)


def precision_at_k(
    predictions: Sequence[float],
    labels: Sequence[bool],
    *,
    k: int = 3,
) -> float:
    if not predictions or len(predictions) != len(labels) or k <= 0:
        return 0.0
    pairs = sorted(
        [(float(pred), bool(label)) for pred, label in zip(predictions, labels)],
        key=lambda row: row[0],
        reverse=True,
    )
    top_k = pairs[: min(k, len(pairs))]
    if not top_k:
        return 0.0
    hits = sum(1 for _, label in top_k if label)
    return round(hits / len(top_k), 6)


def calibration_report(
    predictions: Sequence[float],
    labels: Sequence[bool],
    *,
    precision_k: int = 3,
) -> dict[str, float]:
    return {
        "brier_score": brier_score(predictions, labels),
        "pr_auc": pr_auc_approx(predictions, labels),
        "precision_at_k": precision_at_k(predictions, labels, k=precision_k),
        "sample_count": float(len(predictions)),
    }


__all__ = ["brier_score", "calibration_report", "precision_at_k", "pr_auc_approx"]
