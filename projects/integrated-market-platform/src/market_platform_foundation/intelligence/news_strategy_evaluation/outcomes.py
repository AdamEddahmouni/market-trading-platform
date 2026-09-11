"""Realized outcome measurement — subsequent return after event, not causal P&L."""

from __future__ import annotations

from ...canonical import canonical_bytes, sha256_bytes

from .contracts import (
    DirectionalLabel,
    OutcomeHorizon,
    OutcomeQuality,
    RealizedOutcome,
    StrategyEvaluationDecision,
)
from .market_data import FixtureMarketDataProvider


def _directional_label(raw_return: float | None, flat_threshold_bps: float) -> DirectionalLabel | None:
    if raw_return is None:
        return None
    threshold = flat_threshold_bps / 10000.0
    if raw_return > threshold:
        return DirectionalLabel.UP
    if raw_return < -threshold:
        return DirectionalLabel.DOWN
    return DirectionalLabel.FLAT


def measure_outcome(
    *,
    decision: StrategyEvaluationDecision,
    horizon: OutcomeHorizon,
    market_provider: FixtureMarketDataProvider,
    flat_threshold_bps: float,
) -> RealizedOutcome:
    series = market_provider.get_series(decision.instrument_id)
    warnings: list[str] = []
    if series is None:
        missing_id = sha256_bytes(
            canonical_bytes({"decision_id": decision.decision_id, "horizon_id": horizon.horizon_id, "missing": True})
        )
        return RealizedOutcome(
            outcome_id=f"EVOUT-{missing_id[:16]}",
            decision_id=decision.decision_id,
            sample_id=decision.sample_id,
            horizon_id=horizon.horizon_id,
            start_time=decision.as_of,
            end_time=decision.as_of,
            start_price=None,
            end_price=None,
            high_price=None,
            low_price=None,
            raw_return=None,
            normalized_directional_return=None,
            maximum_favorable_excursion=None,
            maximum_adverse_excursion=None,
            directional_label=None,
            quality=OutcomeQuality.INSUFFICIENT_MARKET_DATA,
            data_provenance="missing_series",
            warnings=("NO_MARKET_SERIES",),
        )

    start_bar = series.bar_at_or_before(decision.as_of)
    end_time = market_provider.window_end_iso(decision.as_of, horizon.duration_seconds)
    end_bar = series.bar_at_or_before(end_time)
    window_bars = series.bars_in_window(decision.as_of, end_time)

    if start_bar is None:
        quality = OutcomeQuality.MISSING_START_BAR
    elif end_bar is None:
        quality = OutcomeQuality.MISSING_END_BAR
    elif not window_bars:
        quality = OutcomeQuality.PARTIAL_HORIZON
    else:
        quality = OutcomeQuality.COMPLETE

    start_price = start_bar.close if start_bar else None
    end_price = end_bar.close if end_bar else None
    raw_return = None
    if start_price and end_price and start_price != 0:
        raw_return = (end_price - start_price) / start_price

    high_price = max((b.high for b in window_bars), default=None) if window_bars else None
    low_price = min((b.low for b in window_bars), default=None) if window_bars else None

    mfe = None
    mae = None
    if start_price and window_bars:
        highs = [b.high for b in window_bars]
        lows = [b.low for b in window_bars]
        mfe = (max(highs) - start_price) / start_price
        mae = (min(lows) - start_price) / start_price

    normalized = None
    if raw_return is not None and decision.normalized_directional_units != 0:
        normalized = raw_return * decision.normalized_directional_units
    elif raw_return is not None and decision.normalized_directional_units == 0:
        normalized = 0.0

    if quality != OutcomeQuality.COMPLETE:
        warnings.append(f"OUTCOME_QUALITY_{quality.value}")

    outcome_identity = sha256_bytes(
        canonical_bytes(
            {
                "decision_id": decision.decision_id,
                "horizon_id": horizon.horizon_id,
                "start_time": decision.as_of,
                "end_time": end_time,
                "raw_return": raw_return,
            }
        )
    )
    return RealizedOutcome(
        outcome_id=f"EVOUT-{outcome_identity[:16]}",
        decision_id=decision.decision_id,
        sample_id=decision.sample_id,
        horizon_id=horizon.horizon_id,
        start_time=decision.as_of,
        end_time=end_time,
        start_price=start_price,
        end_price=end_price,
        high_price=high_price,
        low_price=low_price,
        raw_return=raw_return,
        normalized_directional_return=normalized,
        maximum_favorable_excursion=mfe,
        maximum_adverse_excursion=mae,
        directional_label=_directional_label(raw_return, flat_threshold_bps),
        quality=quality,
        data_provenance=series.series_ref,
        warnings=tuple(warnings),
    )


__all__ = ["measure_outcome"]
