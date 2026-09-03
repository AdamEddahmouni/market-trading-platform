"""LOB engineered feature vector assembly — Order Flow OF12 (M7 inputs)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .forecast import _l1_from_snapshot
from .impact import AGGRESSION_THRESHOLD
from .ofi import snapshot_book_state_valid

FEATURE_METHOD = "lob_feature_vector_v1"
FEATURE_VERSION = "1"
OFI_SCALE = 200.0


@dataclass(frozen=True, slots=True)
class LobFeatureVector:
    ofi_signal: float
    pressure_signal: float
    queue_imbalance_signal: float
    trade_signal: float
    fragility_signal: float
    absorption_dampener: float
    queue_ahead_fraction: float | None
    feature_method: str
    feature_version: str
    book_state_valid: bool
    quality_flags: tuple[str, ...] = ()


def _tanh_scale(value: float, scale: float) -> float:
    if scale <= 0:
        return 0.0
    return math.tanh(value / scale)


def _clamp01(value: float) -> float:
    return min(max(value, 0.0), 1.0)


def build_lob_feature_vector(
    snapshot: dict[str, Any],
    *,
    ofi_value: float | None = None,
    book_state_valid: bool | None = None,
    fragility_score: float | None = None,
    absorption_score: float | None = None,
    bar_delta: float | None = None,
    cvd_slope: float | None = None,
    queue_ahead_fraction: float | None = None,
) -> LobFeatureVector:
    """Assemble normalized M7 LOB features for OF12 baseline scoring."""
    valid = book_state_valid if book_state_valid is not None else snapshot_book_state_valid(snapshot)
    if not valid:
        return LobFeatureVector(
            ofi_signal=0.0,
            pressure_signal=0.0,
            queue_imbalance_signal=0.0,
            trade_signal=0.0,
            fragility_signal=0.0,
            absorption_dampener=0.0,
            queue_ahead_fraction=None,
            feature_method=FEATURE_METHOD,
            feature_version=FEATURE_VERSION,
            book_state_valid=False,
            quality_flags=("BOOK_STATE_INVALID",),
        )

    quality_flags: list[str] = []
    l1_metrics = _l1_from_snapshot(snapshot)
    if l1_metrics is None:
        return LobFeatureVector(
            ofi_signal=0.0,
            pressure_signal=0.0,
            queue_imbalance_signal=0.0,
            trade_signal=0.0,
            fragility_signal=0.0,
            absorption_dampener=0.0,
            queue_ahead_fraction=None,
            feature_method=FEATURE_METHOD,
            feature_version=FEATURE_VERSION,
            book_state_valid=False,
            quality_flags=("BOOK_STATE_INVALID",),
        )

    spread, _relative_spread, microprice_minus_mid, queue_imbalance = l1_metrics
    ofi_signal = _tanh_scale(ofi_value or 0.0, OFI_SCALE)

    pressure_signal = 0.0
    if spread > 0:
        pressure_signal = _clamp01(abs(microprice_minus_mid) / spread) * (
            1.0 if microprice_minus_mid > 0 else -1.0 if microprice_minus_mid < 0 else 0.0
        )

    trade_signal = 0.0
    if bar_delta is not None:
        trade_signal = _tanh_scale(bar_delta, AGGRESSION_THRESHOLD)
    elif cvd_slope is not None:
        trade_signal = _tanh_scale(cvd_slope, AGGRESSION_THRESHOLD)
    else:
        quality_flags.append("MISSING_TRADE_FLOW")

    fragility_signal = _clamp01(fragility_score if fragility_score is not None else 0.0)
    absorption_dampener = _clamp01(absorption_score if absorption_score is not None else 0.0)

    queue_ahead: float | None = None
    if queue_ahead_fraction is not None:
        queue_ahead = _clamp01(float(queue_ahead_fraction))
    else:
        quality_flags.append("MBO_UNAVAILABLE")

    return LobFeatureVector(
        ofi_signal=round(ofi_signal, 6),
        pressure_signal=round(pressure_signal, 6),
        queue_imbalance_signal=round(queue_imbalance, 6),
        trade_signal=round(trade_signal, 6),
        fragility_signal=round(fragility_signal, 6),
        absorption_dampener=round(absorption_dampener, 6),
        queue_ahead_fraction=queue_ahead,
        feature_method=FEATURE_METHOD,
        feature_version=FEATURE_VERSION,
        book_state_valid=True,
        quality_flags=tuple(quality_flags),
    )


def lob_feature_vector_to_dict(vector: LobFeatureVector) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "feature_method": vector.feature_method,
        "feature_version": vector.feature_version,
        "ofi_signal": vector.ofi_signal,
        "pressure_signal": vector.pressure_signal,
        "queue_imbalance_signal": vector.queue_imbalance_signal,
        "trade_signal": vector.trade_signal,
        "fragility_signal": vector.fragility_signal,
        "absorption_dampener": vector.absorption_dampener,
        "book_state_valid": vector.book_state_valid,
        "quality_flags": list(vector.quality_flags),
    }
    if vector.queue_ahead_fraction is not None:
        payload["queue_ahead_fraction"] = vector.queue_ahead_fraction
    return payload


__all__ = [
    "FEATURE_METHOD",
    "FEATURE_VERSION",
    "LobFeatureVector",
    "build_lob_feature_vector",
    "lob_feature_vector_to_dict",
]
