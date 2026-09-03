"""Bounded deterministic derived options activity features — predictive=False."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import (
    OptionsFeatureLayer,
    OptionsMarketStatisticObservation,
    OptionsStatisticFamily,
)
from .quality import default_activity_flags


@dataclass(frozen=True, slots=True)
class DerivedPutCallRatio:
    canonical_statistic_id: str
    put_call_ratio: float | None
    call_share: float | None
    put_share: float | None
    available_time: str
    feature_layer: OptionsFeatureLayer = OptionsFeatureLayer.DETERMINISTIC_DERIVED
    predictive: bool = False


@dataclass(frozen=True, slots=True)
class DerivedIntradayInterval:
    trade_date: str
    bucket_start: str
    bucket_end: str
    interval_calls: int | None
    interval_puts: int | None
    interval_total: int | None
    interval_put_call_ratio: float | None
    available_time: str
    feature_layer: OptionsFeatureLayer = OptionsFeatureLayer.DETERMINISTIC_DERIVED
    predictive: bool = False


def derive_put_call_features(
    obs: OptionsMarketStatisticObservation,
) -> DerivedPutCallRatio | None:
    """Put/call ratio is activity mix — not bullish/bearish direction."""

    if obs.statistic_family not in {
        OptionsStatisticFamily.PUT_CALL_RATIO,
        OptionsStatisticFamily.INTRADAY_CUMULATIVE,
    }:
        return None
    ratio = obs.derived_ratio if obs.derived_ratio is not None else obs.source_ratio
    call_share = put_share = None
    if obs.call_value is not None and obs.put_value is not None:
        total = obs.call_value + obs.put_value
        if total > 0:
            call_share = obs.call_value / total
            put_share = obs.put_value / total
    return DerivedPutCallRatio(
        canonical_statistic_id=obs.canonical_statistic_id,
        put_call_ratio=ratio,
        call_share=call_share,
        put_share=put_share,
        available_time=obs.available_time,
    )


def derive_intraday_interval(
    current: OptionsMarketStatisticObservation,
    previous: OptionsMarketStatisticObservation | None,
) -> DerivedIntradayInterval | None:
    if current.statistic_family != OptionsStatisticFamily.INTRADAY_CUMULATIVE:
        return None
    if previous is None:
        return None
    interval_calls = (
        None
        if current.call_value is None or previous.call_value is None
        else current.call_value - previous.call_value
    )
    interval_puts = (
        None
        if current.put_value is None or previous.put_value is None
        else current.put_value - previous.put_value
    )
    interval_total = (
        None
        if current.total_value is None or previous.total_value is None
        else current.total_value - previous.total_value
    )
    ratio = None
    if interval_calls and interval_calls > 0 and interval_puts is not None:
        ratio = interval_puts / interval_calls
    return DerivedIntradayInterval(
        trade_date=current.trade_date,
        bucket_start=current.bucket_start,
        bucket_end=current.bucket_end,
        interval_calls=interval_calls,
        interval_puts=interval_puts,
        interval_total=interval_total,
        interval_put_call_ratio=ratio,
        available_time=current.available_time,
    )


def derive_market_share_fraction(
    obs: OptionsMarketStatisticObservation,
) -> float | None:
    if obs.statistic_family != OptionsStatisticFamily.MARKET_SHARE:
        return None
    return obs.normalized_value if obs.normalized_value is not None else obs.source_value


def derived_quality_flags() -> tuple[str, ...]:
    return default_activity_flags()


__all__ = [
    "DerivedIntradayInterval",
    "DerivedPutCallRatio",
    "derive_intraday_interval",
    "derive_market_share_fraction",
    "derive_put_call_features",
    "derived_quality_flags",
]
