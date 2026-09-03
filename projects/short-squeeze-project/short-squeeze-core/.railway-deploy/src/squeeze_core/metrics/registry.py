from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

from squeeze_core.adapters.market_bars import BarInterval, BarSession
from squeeze_core.contracts import AssetClass, Observation

from .borrow_availability_changes import (
    BorrowAvailabilityComparisonRequest,
    build_borrow_availability_change_result,
)
from .borrow_fee_changes import BorrowComparisonRequest, build_borrow_fee_change_result
from .days_to_cover import DaysToCoverRequest, build_days_to_cover_components, build_days_to_cover_result
from .gaps import GapRequest, build_gap_result
from .models import MetricName, MetricResult, PriceField, ProviderScopeMode, TrailingWindow
from .normalized_models import NormalizedMetricResult, ReturnCountWindow
from .pressure_models import DaysToCoverComponents, PressureMetricResult
from .ranges import RangeRequest, build_range_result
from .short_interest_changes import (
    ShortInterestComparisonRequest,
    ShortInterestRevisionRequest,
    build_short_interest_change_result,
    build_short_interest_revision_delta_result,
)
from .relative_volume import (
    RelativeVolumeRequest,
    build_relative_volume_result,
    build_volume_percent_deviation_result,
)
from .return_baselines import (
    ReturnBaselineRequest,
    build_mean_percentage_return_baseline_result,
    build_percentage_return_standard_deviation_baseline_result,
)
from .return_standardization import ReturnZScoreRequest, build_percentage_return_z_score_result
from .returns import ReturnRequest, build_return_result
from .volume_baselines import VolumeBaselineRequest, build_volume_baseline_result
from .volume_standardization import VolumeZScoreRequest, build_volume_z_score_result


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _common_kwargs(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": str(spec["symbol"]).strip().upper(),
        "asset_class": AssetClass(spec.get("asset_class", "EQUITY")),
        "as_of": _parse_datetime(spec["as_of"]),
        "source_interval": BarInterval(spec["source_interval"]),
        "session_scope": tuple(BarSession(item) for item in spec.get("session_scope", ())),
        "provider_scope": ProviderScopeMode(spec.get("provider_scope", ProviderScopeMode.SINGLE_PROVIDER.value)),
        "provider": spec.get("provider"),
    }


def _return_count_window(window_spec: dict[str, Any]) -> ReturnCountWindow:
    return ReturnCountWindow(
        requested_count=int(window_spec["requested_count"]),
        exclude_current_bar=bool(window_spec.get("exclude_current_bar", True)),
        minimum_samples=int(window_spec["minimum_samples"]),
    )


def _bar_count_window(window_spec: dict[str, Any]) -> TrailingWindow:
    return TrailingWindow(
        requested_count=int(window_spec["requested_count"]),
        exclude_current_bar=bool(window_spec.get("exclude_current_bar", True)),
        minimum_samples=int(window_spec["minimum_samples"]),
    )


def build_metric_result(
    observations: Iterable[Observation], spec: dict[str, Any]
) -> MetricResult | NormalizedMetricResult | PressureMetricResult | DaysToCoverComponents:
    if "metric_name" not in spec:
        raise ValueError("metric request is missing required field: metric_name")
    try:
        metric_name = MetricName(spec["metric_name"])
    except ValueError as error:
        raise ValueError(f"unsupported metric_name: {spec['metric_name']!r}") from error

    observations = tuple(observations)

    if metric_name in _PRESSURE_METRIC_NAMES:
        return _build_pressure_metric_result(observations, spec, metric_name)

    common = _common_kwargs(spec)

    if metric_name in (MetricName.ABSOLUTE_RETURN, MetricName.PERCENTAGE_RETURN):
        request = ReturnRequest(
            **common,
            start_bar_start=_parse_datetime(spec["start_bar_start"]),
            start_bar_end=_parse_datetime(spec["start_bar_end"]),
            end_bar_start=_parse_datetime(spec["end_bar_start"]),
            end_bar_end=_parse_datetime(spec["end_bar_end"]),
            price_field=PriceField(spec.get("price_field", PriceField.CLOSE.value)),
        )
        return build_return_result(observations, request, metric_name)

    if metric_name in (MetricName.ABSOLUTE_SESSION_GAP, MetricName.PERCENTAGE_SESSION_GAP):
        request = GapRequest(
            **common,
            prior_bar_start=_parse_datetime(spec["prior_bar_start"]),
            prior_bar_end=_parse_datetime(spec["prior_bar_end"]),
            current_bar_start=_parse_datetime(spec["current_bar_start"]),
            current_bar_end=_parse_datetime(spec["current_bar_end"]),
        )
        return build_gap_result(observations, request, metric_name)

    if metric_name in (MetricName.ABSOLUTE_BAR_RANGE, MetricName.PERCENTAGE_BAR_RANGE):
        request = RangeRequest(
            **common,
            target_bar_start=_parse_datetime(spec["target_bar_start"]),
            target_bar_end=_parse_datetime(spec["target_bar_end"]),
        )
        return build_range_result(observations, request, metric_name)

    if metric_name is MetricName.MEAN_VOLUME_BASELINE:
        window_spec = spec["window"]
        request = VolumeBaselineRequest(
            **common,
            target_bar_start=_parse_datetime(spec["target_bar_start"]),
            target_bar_end=_parse_datetime(spec["target_bar_end"]),
            window=TrailingWindow(
                requested_count=int(window_spec["requested_count"]),
                exclude_current_bar=bool(window_spec.get("exclude_current_bar", True)),
                minimum_samples=int(window_spec["minimum_samples"]),
            ),
        )
        return build_volume_baseline_result(observations, request)

    if metric_name in (MetricName.RELATIVE_VOLUME, MetricName.VOLUME_PERCENT_DEVIATION):
        window_spec = spec["window"]
        request = RelativeVolumeRequest(
            **common,
            target_bar_start=_parse_datetime(spec["target_bar_start"]),
            target_bar_end=_parse_datetime(spec["target_bar_end"]),
            window=_bar_count_window(window_spec),
        )
        if metric_name is MetricName.RELATIVE_VOLUME:
            return build_relative_volume_result(observations, request)
        return build_volume_percent_deviation_result(observations, request)

    if metric_name is MetricName.VOLUME_Z_SCORE:
        window_spec = spec["window"]
        request = VolumeZScoreRequest(
            **common,
            target_bar_start=_parse_datetime(spec["target_bar_start"]),
            target_bar_end=_parse_datetime(spec["target_bar_end"]),
            window=_bar_count_window(window_spec),
        )
        return build_volume_z_score_result(observations, request)

    if metric_name in (
        MetricName.MEAN_PERCENTAGE_RETURN_BASELINE,
        MetricName.PERCENTAGE_RETURN_STANDARD_DEVIATION_BASELINE,
    ):
        window_spec = spec["window"]
        request = ReturnBaselineRequest(
            **common,
            target_bar_start=_parse_datetime(spec["target_bar_start"]),
            window=_return_count_window(window_spec),
            price_field=PriceField(spec.get("price_field", PriceField.CLOSE.value)),
        )
        if metric_name is MetricName.MEAN_PERCENTAGE_RETURN_BASELINE:
            return build_mean_percentage_return_baseline_result(observations, request)
        return build_percentage_return_standard_deviation_baseline_result(observations, request)

    if metric_name is MetricName.PERCENTAGE_RETURN_Z_SCORE:
        window_spec = spec["window"]
        request = ReturnZScoreRequest(
            **common,
            target_start_bar_start=_parse_datetime(spec["target_start_bar_start"]),
            target_start_bar_end=_parse_datetime(spec["target_start_bar_end"]),
            target_end_bar_start=_parse_datetime(spec["target_end_bar_start"]),
            target_end_bar_end=_parse_datetime(spec["target_end_bar_end"]),
            window=_return_count_window(window_spec),
            price_field=PriceField(spec.get("price_field", PriceField.CLOSE.value)),
        )
        return build_percentage_return_z_score_result(observations, request)

    raise ValueError(f"unsupported metric_name: {metric_name}")


_PRESSURE_METRIC_NAMES = {
    MetricName.PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE,
    MetricName.PUBLISHED_SHORT_INTEREST_PERCENTAGE_CHANGE,
    MetricName.PUBLISHED_SHORT_INTEREST_REVISION_DELTA,
    MetricName.DAYS_TO_COVER_COMPONENTS,
    MetricName.DAYS_TO_COVER,
    MetricName.BORROW_FEE_ABSOLUTE_CHANGE,
    MetricName.BORROW_FEE_RELATIVE_PERCENTAGE_CHANGE,
    MetricName.BORROW_AVAILABILITY_ABSOLUTE_CHANGE,
    MetricName.BORROW_AVAILABILITY_PERCENTAGE_CHANGE,
}


def _pressure_common_kwargs(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": str(spec["symbol"]).strip().upper(),
        "asset_class": AssetClass(spec.get("asset_class", "EQUITY")),
        "as_of": _parse_datetime(spec["as_of"]),
    }


def _build_pressure_metric_result(
    observations: tuple[Observation, ...], spec: dict[str, Any], metric_name: MetricName
) -> PressureMetricResult | DaysToCoverComponents:
    common = _pressure_common_kwargs(spec)

    if metric_name in (
        MetricName.PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE,
        MetricName.PUBLISHED_SHORT_INTEREST_PERCENTAGE_CHANGE,
    ):
        request = ShortInterestComparisonRequest(
            **common,
            provider=str(spec["provider"]),
            starting_reporting_period=_parse_date(spec["starting_reporting_period"]),
            ending_reporting_period=_parse_date(spec["ending_reporting_period"]),
        )
        return build_short_interest_change_result(observations, request, metric_name)

    if metric_name is MetricName.PUBLISHED_SHORT_INTEREST_REVISION_DELTA:
        request = ShortInterestRevisionRequest(
            **common,
            provider=str(spec["provider"]),
            reporting_period=_parse_date(spec["reporting_period"]),
        )
        return build_short_interest_revision_delta_result(observations, request)

    if metric_name in (MetricName.DAYS_TO_COVER_COMPONENTS, MetricName.DAYS_TO_COVER):
        window_spec = spec["volume_window"]
        request = DaysToCoverRequest(
            **common,
            short_interest_provider=str(spec["short_interest_provider"]),
            short_interest_reporting_period=_parse_date(spec["short_interest_reporting_period"]),
            volume_provider=str(spec["volume_provider"]),
            volume_interval=BarInterval(spec["volume_interval"]),
            volume_session_scope=tuple(BarSession(item) for item in spec.get("volume_session", ())),
            volume_window=TrailingWindow(
                requested_count=int(window_spec["requested_count"]),
                exclude_current_bar=bool(window_spec.get("exclude_current_bar", True)),
                minimum_samples=int(window_spec["minimum_samples"]),
            ),
        )
        if metric_name is MetricName.DAYS_TO_COVER_COMPONENTS:
            return build_days_to_cover_components(observations, request)
        return build_days_to_cover_result(observations, request)

    if metric_name in (
        MetricName.BORROW_FEE_ABSOLUTE_CHANGE,
        MetricName.BORROW_FEE_RELATIVE_PERCENTAGE_CHANGE,
    ):
        fee_request = BorrowComparisonRequest(
            **common,
            provider=str(spec["provider"]),
            starting_effective_timestamp=_parse_datetime(spec["starting_effective_timestamp"]),
            ending_effective_timestamp=_parse_datetime(spec["ending_effective_timestamp"]),
        )
        return build_borrow_fee_change_result(observations, fee_request, metric_name)

    availability_request = BorrowAvailabilityComparisonRequest(
        **common,
        provider=str(spec["provider"]),
        starting_effective_timestamp=_parse_datetime(spec["starting_effective_timestamp"]),
        ending_effective_timestamp=_parse_datetime(spec["ending_effective_timestamp"]),
    )
    return build_borrow_availability_change_result(observations, availability_request, metric_name)


def build_metric_results(
    observations: Iterable[Observation], specs: Iterable[dict[str, Any]]
) -> tuple[MetricResult | NormalizedMetricResult | PressureMetricResult | DaysToCoverComponents, ...]:
    observations = tuple(observations)
    return tuple(build_metric_result(observations, spec) for spec in specs)
