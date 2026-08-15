"""Bar-derived features from supported BAR_OHLCV_1M capability."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

SUPPORTED_CAPABILITY = "BAR_OHLCV_1M"
BAR_FEATURE_IDS = ("bar_close", "bar_high", "bar_low", "bar_open", "bar_range", "bar_volume")


def _decimal(value: object) -> Decimal:
    return Decimal(str(value))


def derive_bar_features(
    bars_by_instrument: dict[str, dict[str, Any]],
    *,
    prediction_cutoff: int,
) -> tuple[list[dict[str, object]], list[str]]:
    features: list[dict[str, object]] = []
    reason_codes: list[str] = []
    for instrument_id in sorted(bars_by_instrument):
        bar = bars_by_instrument[instrument_id]
        available_time = int(bar["available_time"])
        if available_time > prediction_cutoff:
            reason_codes.append("PIT_FEATURE_FUTURE_INPUT")
            continue
        payload = bar.get("bar_payload", {})
        if not isinstance(payload, dict):
            reason_codes.append("BAR_FEATURE_INVALID_PAYLOAD")
            continue
        open_px = _decimal(payload.get("open", "0"))
        high_px = _decimal(payload.get("high", "0"))
        low_px = _decimal(payload.get("low", "0"))
        close_px = _decimal(payload.get("close", "0"))
        volume = int(payload.get("volume", 0))
        bar_range = high_px - low_px
        base = {
            "available_time": available_time,
            "capability": SUPPORTED_CAPABILITY,
            "instrument_id": instrument_id,
            "normalized_event_id": str(bar.get("normalized_event_id", "")),
            "provenance": {
                "feature_definition_version": "1.0.0",
                "source_event_type": SUPPORTED_CAPABILITY,
            },
        }
        for feature_id, value in (
            ("bar_open", str(open_px)),
            ("bar_high", str(high_px)),
            ("bar_low", str(low_px)),
            ("bar_close", str(close_px)),
            ("bar_range", str(bar_range)),
            ("bar_volume", str(volume)),
        ):
            features.append({"feature_id": feature_id, "value": value, **base})
    return features, sorted(set(reason_codes))
