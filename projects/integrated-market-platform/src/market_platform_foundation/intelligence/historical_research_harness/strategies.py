"""Predeclared baseline direction predictors (HISTORICAL_BASELINE_V1)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

BASELINE_STRATEGY_NO_TRADE_V1 = "baseline_0_no_trade_v1"
BASELINE_STRATEGY_MOMENTUM_5M_SIGN_V1 = "baseline_1_momentum_5m_sign_v1"
BASELINE_STRATEGY_MEAN_REVERSION_5M_SIGN_V1 = "baseline_2_mean_reversion_5m_sign_v1"
BASELINE_STRATEGY_VOLUME_MOMENTUM_5M_V1 = "baseline_3_volume_momentum_5m_v1"
HISTORICAL_MOMENTUM_SIGN_V1 = "historical_momentum_sign_v1"

_VOLUME_MOMENTUM_RELATIVE_VOLUME_THRESHOLD = 1.0


def _sign_from_momentum(momentum: float | None) -> int:
    if momentum is None:
        return 0
    if momentum > 0:
        return 1
    if momentum < 0:
        return -1
    return 0


def predict_baseline_0_no_trade(_features: Mapping[str, Any]) -> int:
    return 0


def predict_baseline_1_momentum_5m_sign(features: Mapping[str, Any]) -> int:
    values = features.get("values", {})
    if not isinstance(values, Mapping):
        return 0
    return _sign_from_momentum(values.get("momentum_5m"))


def predict_baseline_2_mean_reversion_5m_sign(features: Mapping[str, Any]) -> int:
    values = features.get("values", {})
    if not isinstance(values, Mapping):
        return 0
    momentum = values.get("momentum_5m")
    if momentum is None:
        return 0
    sign = _sign_from_momentum(momentum)
    return -sign if sign != 0 else 0


def predict_baseline_3_volume_momentum_5m_sign(features: Mapping[str, Any]) -> int:
    values = features.get("values", {})
    if not isinstance(values, Mapping):
        return 0
    rel_vol = values.get("relative_volume_10m")
    if rel_vol is None or float(rel_vol) < _VOLUME_MOMENTUM_RELATIVE_VOLUME_THRESHOLD:
        return 0
    return _sign_from_momentum(values.get("momentum_5m"))


def predict_historical_momentum_sign(features: Mapping[str, Any]) -> int:
    return predict_baseline_1_momentum_5m_sign(features)


_BASELINE_PREDICTORS: dict[str, Callable[[Mapping[str, Any]], int]] = {
    BASELINE_STRATEGY_NO_TRADE_V1: predict_baseline_0_no_trade,
    BASELINE_STRATEGY_MOMENTUM_5M_SIGN_V1: predict_baseline_1_momentum_5m_sign,
    BASELINE_STRATEGY_MEAN_REVERSION_5M_SIGN_V1: predict_baseline_2_mean_reversion_5m_sign,
    BASELINE_STRATEGY_VOLUME_MOMENTUM_5M_V1: predict_baseline_3_volume_momentum_5m_sign,
    HISTORICAL_MOMENTUM_SIGN_V1: predict_historical_momentum_sign,
}


def resolve_direction_predictor(strategy_id: str) -> Callable[[Mapping[str, Any]], int]:
    try:
        return _BASELINE_PREDICTORS[strategy_id]
    except KeyError:
        raise ValueError(f"UNKNOWN_HISTORICAL_RESEARCH_STRATEGY:{strategy_id}") from None


def predict_direction(strategy_id: str, features: Mapping[str, Any]) -> int:
    return resolve_direction_predictor(strategy_id)(features)


__all__ = [
    "BASELINE_STRATEGY_MEAN_REVERSION_5M_SIGN_V1",
    "BASELINE_STRATEGY_MOMENTUM_5M_SIGN_V1",
    "BASELINE_STRATEGY_NO_TRADE_V1",
    "BASELINE_STRATEGY_VOLUME_MOMENTUM_5M_V1",
    "HISTORICAL_MOMENTUM_SIGN_V1",
    "predict_direction",
    "resolve_direction_predictor",
]
