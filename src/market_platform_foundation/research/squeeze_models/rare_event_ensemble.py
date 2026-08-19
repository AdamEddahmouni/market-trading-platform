"""SS P7 rare-event logistic ensemble baseline — stdlib only."""

from __future__ import annotations

from typing import Any, Sequence

from .logistic_hazard import hazard_horizon_probability, logistic_probability

MODEL_VERSION = "ss_rare_event_ensemble_v1"

# Fixture-tuned heads with rare-positive class-weight multipliers
ENSEMBLE_HEADS: tuple[tuple[tuple[float, ...], float], ...] = (
    ((0.8, 0.5, 0.3), 1.0),
    ((1.0, 0.4, 0.2), 2.5),
    ((0.6, 0.7, 0.35), 1.8),
)


def _head_probability(
    features: Sequence[float],
    weights: Sequence[float],
    rare_boost: float,
) -> float:
    padded = list(features) + [0.0] * max(0, len(weights) - len(features))
    base = logistic_probability(padded[: len(weights)], weights)
    if base >= 0.5:
        return min(base * rare_boost, 0.99)
    return base


def predict_squeeze_ensemble(
    features: Sequence[float],
    *,
    weights: Sequence[float] | None = None,
    horizon_days: int = 5,
) -> dict[str, Any]:
    """Weighted ensemble of logistic heads with rare-event boost."""
    heads = ENSEMBLE_HEADS
    if weights is not None:
        heads = ((tuple(weights), 1.0),)

    probs: list[float] = []
    head_weights: list[float] = []
    for head_weights_tuple, rare_boost in heads:
        prob = _head_probability(features, head_weights_tuple, rare_boost)
        probs.append(prob)
        head_weights.append(1.0 / len(heads))

    occurrence = round(sum(p * w for p, w in zip(probs, head_weights)), 6)
    magnitude_boost = float(features[0]) if features else 0.0
    hazard = hazard_horizon_probability(
        base_rate=occurrence,
        feature_boost=magnitude_boost,
        horizon_days=horizon_days,
    )
    hazard_by_horizon = {
        days: hazard_horizon_probability(
            base_rate=occurrence,
            feature_boost=magnitude_boost,
            horizon_days=days,
        )
        for days in (1, 3, 5, 10, 20)
    }
    return {
        "ensemble_weights": [round(w, 4) for w in head_weights],
        "head_probabilities": [round(p, 6) for p in probs],
        "hazard_by_horizon": hazard_by_horizon,
        "hazard_probability": hazard,
        "horizon_days": horizon_days,
        "model_version": MODEL_VERSION,
        "occurrence_probability": occurrence,
    }


__all__ = ["ENSEMBLE_HEADS", "MODEL_VERSION", "predict_squeeze_ensemble"]
