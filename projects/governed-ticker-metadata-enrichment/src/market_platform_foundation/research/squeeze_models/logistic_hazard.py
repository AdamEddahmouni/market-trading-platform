"""SS P3 baseline squeeze probability models."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence


MODEL_VERSION = "ss_logistic_hazard_v1"


@dataclass(frozen=True, slots=True)
class MechanismLabelRow:
    symbol: str
    observation_time: str
    mechanism_label: str
    squeeze_occurred: bool
    features: tuple[float, ...]


def logistic_probability(features: Sequence[float], weights: Sequence[float]) -> float:
    z = sum(feature * weight for feature, weight in zip(features, weights))
    if z > 30:
        return 1.0
    if z < -30:
        return 0.0
    return 1.0 / (1.0 + math.exp(-z))


def hazard_horizon_probability(
    *,
    base_rate: float,
    feature_boost: float,
    horizon_days: int,
) -> float:
    """Simple hazard-style horizon probability for baseline SS P3."""
    daily_hazard = min(max(base_rate * (1.0 + feature_boost), 0.0), 0.99)
    return round(1.0 - (1.0 - daily_hazard) ** horizon_days, 6)


def predict_squeeze_probability(
    features: Sequence[float],
    *,
    weights: Sequence[float] | None = None,
    horizon_days: int = 5,
) -> dict[str, Any]:
    default_weights = (0.8, 0.5, 0.3)
    w = weights or default_weights
    padded = list(features) + [0.0] * max(0, len(w) - len(features))
    occurrence = logistic_probability(padded[:len(w)], w)
    magnitude_boost = padded[0] if padded else 0.0
    hazard = hazard_horizon_probability(
        base_rate=occurrence,
        feature_boost=magnitude_boost,
        horizon_days=horizon_days,
    )
    return {
        "horizon_days": horizon_days,
        "hazard_probability": hazard,
        "model_version": MODEL_VERSION,
        "occurrence_probability": round(occurrence, 6),
    }


__all__ = [
    "MechanismLabelRow",
    "MODEL_VERSION",
    "hazard_horizon_probability",
    "logistic_probability",
    "predict_squeeze_probability",
]
