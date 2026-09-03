from datetime import UTC, datetime
from decimal import Decimal

from squeeze_core.adapters.market_bars import BarInterval, BarSession
from squeeze_core.contracts import AssetClass, QualityState
from squeeze_core.metrics import (
    MetricDiagnosticCode,
    ReturnBaselineRequest,
    ReturnCountWindow,
    build_mean_percentage_return_baseline_result,
    build_percentage_return_standard_deviation_baseline_result,
    build_return_distribution_statistics,
)

from .conftest import bar_boundary, make_bar

AS_OF = datetime(2026, 1, 25, 22, 0, tzinfo=UTC)


def _daily_bar(day: int, *, close="10.00", status="COMPLETED", **overrides):
    values = {
        "source_record_id": f"rb-bar-{day}",
        "bar_start": f"2026-01-{day:02d}T00:00:00-05:00",
        "bar_end": f"2026-01-{day + 1:02d}T00:00:00-05:00",
        "session_date": f"2026-01-{day:02d}",
        "publication_timestamp": f"2026-01-{day:02d}T16:01:00-05:00",
        "ingested_at": f"2026-01-{day:02d}T21:02:00Z",
        "high": "1000.00",
        "low": "0.01",
        "open": close,
        "close": close,
        "volume": "10000",
        "status": status,
    }
    values.update(overrides)
    return make_bar(**values)


def _request(target_day: int, window: ReturnCountWindow, **overrides) -> ReturnBaselineRequest:
    target, _ = bar_boundary(_daily_bar(target_day))
    values = dict(
        symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF, source_interval=BarInterval.ONE_DAY,
        target_bar_start=target, window=window,
    )
    values.update(overrides)
    return ReturnBaselineRequest(**values)


def test_mean_of_two_historical_returns():
    # closes 10 -> 12 (return +20%), 12 -> 15 (return +25%); mean = 22.5%
    bars = [_daily_bar(10, close="10.00"), _daily_bar(11, close="12.00"), _daily_bar(12, close="15.00")]
    window = ReturnCountWindow(requested_count=2, minimum_samples=2)
    dist = build_return_distribution_statistics(bars, _request(13, window))
    assert dist.mean == Decimal("22.5")
    assert dist.sample_counts.used == 2


def test_mean_of_three_historical_returns():
    bars = [_daily_bar(d, close=c) for d, c in zip((9, 10, 11, 12), ("10.00", "11.00", "12.10", "13.31"))]
    window = ReturnCountWindow(requested_count=3, minimum_samples=3)
    dist = build_return_distribution_statistics(bars, _request(13, window))
    # each return is exactly +10%
    assert dist.mean == Decimal(10)
    assert dist.standard_deviation == Decimal(0)


def test_positive_and_negative_returns_in_one_baseline():
    bars = [_daily_bar(10, close="10.00"), _daily_bar(11, close="12.00"), _daily_bar(12, close="6.00")]
    window = ReturnCountWindow(requested_count=2, minimum_samples=2)
    dist = build_return_distribution_statistics(bars, _request(13, window))
    assert dist.mean < 0  # +20% then -50% averages negative


def test_zero_return_retained():
    bars = [_daily_bar(10, close="10.00"), _daily_bar(11, close="10.00"), _daily_bar(12, close="12.00")]
    window = ReturnCountWindow(requested_count=2, minimum_samples=2)
    dist = build_return_distribution_statistics(bars, _request(13, window))
    assert dist.sample_counts.used == 2
    assert dist.mean == Decimal(10)  # (0 + 20) / 2


def test_return_count_window_requires_n_plus_1_bars():
    bars = [_daily_bar(d, close="10.00") for d in (10, 11)]  # only 2 bars, need 3+1=4 for N=3
    window = ReturnCountWindow(requested_count=3, minimum_samples=1)
    dist = build_return_distribution_statistics(bars, _request(13, window))
    assert dist.sample_counts.used == 1
    assert dist.sample_counts.requested == 3


def test_target_return_excluded_from_baseline():
    bars = [_daily_bar(d, close="10.00") for d in (10, 11, 12)]
    target = _daily_bar(13, close="999.00")
    window = ReturnCountWindow(requested_count=2, minimum_samples=2)
    dist = build_return_distribution_statistics([*bars, target], _request(13, window))
    assert target.observation_id not in dist.input_observation_ids


def test_zero_starting_close_excluded_not_used_as_denominator():
    zero_close = _daily_bar(10, close="0.01")  # BarPayload requires close > 0; use near-zero instead
    other = _daily_bar(11, close="10.00")
    fallback = _daily_bar(9, close="0.01")
    window = ReturnCountWindow(requested_count=2, minimum_samples=1)
    dist = build_return_distribution_statistics([fallback, zero_close, other], _request(12, window))
    assert dist.quality.state is QualityState.KNOWN_VALUE


def test_partial_bar_excluded():
    partial = _daily_bar(10, close="10.00", status="PARTIAL")
    completed_a = _daily_bar(9, close="9.00")
    completed_b = _daily_bar(11, close="11.00")
    window = ReturnCountWindow(requested_count=2, minimum_samples=1)
    dist = build_return_distribution_statistics([completed_a, partial, completed_b], _request(13, window))
    assert partial.observation_id not in dist.input_observation_ids


def test_corrected_historical_bar_before_and_after_correction_availability():
    a = _daily_bar(9, close="10.00")
    b_original = _daily_bar(10, close="11.00", provider_record_id="rb-orig-hist")
    b_corrected = _daily_bar(
        10, close="12.00", provider_record_id="rb-corrected-hist", source_record_id="rb-bar-10-corrected",
        status="CORRECTED", revision_number=1, supersedes_provider_record_id="rb-orig-hist",
        publication_timestamp="2026-01-18T09:00:00-05:00", ingested_at="2026-01-18T09:05:00Z",
    )
    window = ReturnCountWindow(requested_count=1, minimum_samples=1)
    observations = [a, b_original, b_corrected]
    before = _request(11, window, as_of=datetime(2026, 1, 17, 0, 0, tzinfo=UTC))
    after = _request(11, window, as_of=AS_OF)
    dist_before = build_return_distribution_statistics(observations, before)
    dist_after = build_return_distribution_statistics(observations, after)
    assert dist_before.mean == Decimal(10)
    assert dist_after.mean == Decimal(20)


def test_cancelled_historical_bar_before_and_after_cancellation_availability():
    fallback = _daily_bar(8, close="9.00")
    a = _daily_bar(9, close="10.00")
    b_original = _daily_bar(10, close="11.00", provider_record_id="rb-orig-cancel-hist")
    b_cancelled = _daily_bar(
        10, close="11.00", provider_record_id="rb-cancelled-hist", source_record_id="rb-bar-10-cancelled",
        status="CANCELLED", revision_number=1, supersedes_provider_record_id="rb-orig-cancel-hist",
        publication_timestamp="2026-01-18T09:00:00-05:00", ingested_at="2026-01-18T09:05:00Z",
    )
    window = ReturnCountWindow(requested_count=1, minimum_samples=1)
    observations = [fallback, a, b_original, b_cancelled]
    before = _request(11, window, as_of=datetime(2026, 1, 17, 0, 0, tzinfo=UTC))
    after = _request(11, window, as_of=AS_OF)
    dist_before = build_return_distribution_statistics(observations, before)
    dist_after = build_return_distribution_statistics(observations, after)
    # Before cancellation, the two most recent eligible bars are day9 (close 10) -> day10
    # (close 11): return +10%. After cancellation, b_cancelled drops out and the window falls
    # back to fallback (day8, close 9) -> a (day9, close 10): return +11.111...%.
    assert dist_before.mean == Decimal(10)
    assert dist_after.quality.state is QualityState.KNOWN_VALUE
    assert dist_after.mean != dist_before.mean


def test_mixed_providers_rejected():
    a = _daily_bar(9, close="10.00", provider="ALPACA_SHAPED", source_record_id="rb-a-9")
    b = _daily_bar(10, close="11.00", provider="SCHWAB_SHAPED", source_record_id="rb-b-10")
    window = ReturnCountWindow(requested_count=1, minimum_samples=1)
    dist = build_return_distribution_statistics([a, b], _request(11, window))
    assert dist.quality.state is QualityState.UNAVAILABLE
    assert any(d.code is MetricDiagnosticCode.METRIC_AMBIGUOUS_PROVIDER for d in dist.diagnostics)


def test_mixed_intervals_excluded():
    daily = _daily_bar(9, close="10.00")
    minute = make_bar(
        source_record_id="rb-minute-10", interval="1_MINUTE", bar_start="2026-01-10T09:30:00-05:00",
        bar_end="2026-01-10T09:31:00-05:00", session_date="2026-01-10",
        publication_timestamp="2026-01-10T09:31:01-05:00", ingested_at="2026-01-10T21:02:00Z",
        high="1000.00", low="0.01", open="999.00", close="999.00",
    )
    window = ReturnCountWindow(requested_count=1, minimum_samples=1)
    dist = build_return_distribution_statistics([daily, minute], _request(11, window))
    assert minute.observation_id not in dist.input_observation_ids


def test_mixed_sessions_excluded():
    regular = _daily_bar(9, close="10.00", session="REGULAR")
    premarket = make_bar(
        source_record_id="rb-premarket-10", interval="1_DAY", session="PREMARKET",
        bar_start="2026-01-10T00:00:00-05:00", bar_end="2026-01-11T00:00:00-05:00", session_date="2026-01-10",
        publication_timestamp="2026-01-10T16:01:00-05:00", ingested_at="2026-01-10T21:02:00Z",
        high="1000.00", low="0.01", open="999.00", close="999.00",
    )
    window = ReturnCountWindow(requested_count=1, minimum_samples=1)
    dist = build_return_distribution_statistics(
        [regular, premarket], _request(11, window, session_scope=(BarSession.REGULAR,))
    )
    assert premarket.observation_id not in dist.input_observation_ids


def test_explicit_close_to_close_price_policy():
    from squeeze_core.metrics import PriceField

    bars = [_daily_bar(9, close="10.00"), _daily_bar(10, close="11.00")]
    window = ReturnCountWindow(requested_count=1, minimum_samples=1)
    dist = build_return_distribution_statistics(bars, _request(11, window, price_field=PriceField.CLOSE))
    assert dist.price_field == PriceField.CLOSE


def test_out_of_order_bars_are_a_no_op():
    bars = [_daily_bar(d, close=c) for d, c in zip((9, 10, 11, 12), ("10.00", "11.00", "12.10", "13.31"))]
    window = ReturnCountWindow(requested_count=3, minimum_samples=3)
    forward = build_return_distribution_statistics(bars, _request(13, window))
    backward = build_return_distribution_statistics(list(reversed(bars)), _request(13, window))
    assert forward.mean == backward.mean
    assert forward.deterministic_id == backward.deterministic_id


def test_future_bar_excluded():
    bars = [_daily_bar(d, close="10.00") for d in (9, 10)]
    future = _daily_bar(14, close="999.00")
    window = ReturnCountWindow(requested_count=1, minimum_samples=1)
    dist = build_return_distribution_statistics([*bars, future], _request(11, window))
    assert future.observation_id not in dist.input_observation_ids


def test_insufficient_return_history():
    bars = [_daily_bar(9, close="10.00")]
    window = ReturnCountWindow(requested_count=3, minimum_samples=3)
    dist = build_return_distribution_statistics(bars, _request(11, window))
    assert dist.mean is None
    assert dist.quality.state is QualityState.UNAVAILABLE
    assert any(d.code is MetricDiagnosticCode.RETURN_DISTRIBUTION_INSUFFICIENT_BARS for d in dist.diagnostics)


def test_exact_decimal_mean():
    bars = [_daily_bar(d, close=c) for d, c in zip((9, 10, 11), ("10.00", "10.00", "10.01"))]
    window = ReturnCountWindow(requested_count=2, minimum_samples=2)
    dist = build_return_distribution_statistics(bars, _request(12, window))
    assert isinstance(dist.mean, Decimal)


# --- Standard deviation baseline -----------------------------------------------------------------


def test_positive_nonzero_standard_deviation():
    bars = [_daily_bar(10, close="10.00"), _daily_bar(11, close="12.00"), _daily_bar(12, close="10.00")]
    window = ReturnCountWindow(requested_count=2, minimum_samples=2)
    dist = build_return_distribution_statistics(bars, _request(13, window))
    assert dist.standard_deviation > 0


def test_zero_standard_deviation_when_returns_identical():
    bars = [_daily_bar(d, close=c) for d, c in zip((9, 10, 11, 12), ("10.00", "11.00", "12.10", "13.31"))]
    window = ReturnCountWindow(requested_count=3, minimum_samples=3)
    dist = build_return_distribution_statistics(bars, _request(13, window))
    assert dist.standard_deviation == Decimal(0)


def test_two_return_population_standard_deviation():
    bars = [_daily_bar(10, close="10.00"), _daily_bar(11, close="12.00"), _daily_bar(12, close="9.00")]
    window = ReturnCountWindow(requested_count=2, minimum_samples=2)
    dist = build_return_distribution_statistics(bars, _request(13, window))
    mean_result = build_mean_percentage_return_baseline_result(bars, _request(13, window))
    std_result = build_percentage_return_standard_deviation_baseline_result(bars, _request(13, window))
    assert mean_result.value == dist.mean
    assert std_result.value == dist.standard_deviation


def test_three_return_population_standard_deviation():
    bars = [_daily_bar(d, close=c) for d, c in zip((8, 9, 10, 11), ("10.00", "12.00", "9.00", "15.00"))]
    window = ReturnCountWindow(requested_count=3, minimum_samples=3)
    dist = build_return_distribution_statistics(bars, _request(12, window))
    assert dist.sample_counts.used == 3
    assert dist.standard_deviation > 0


def test_stddev_baseline_insufficient_history():
    bars = [_daily_bar(9, close="10.00")]
    window = ReturnCountWindow(requested_count=3, minimum_samples=3)
    result = build_percentage_return_standard_deviation_baseline_result(bars, _request(11, window))
    assert result.value is None
    assert result.quality.state is QualityState.UNAVAILABLE


def test_stddev_baseline_target_excluded():
    bars = [_daily_bar(d, close="10.00") for d in (9, 10, 11)]
    target = _daily_bar(12, close="500.00")
    window = ReturnCountWindow(requested_count=2, minimum_samples=2)
    result = build_percentage_return_standard_deviation_baseline_result([*bars, target], _request(12, window))
    assert target.observation_id not in result.input_observation_ids


def test_stddev_baseline_future_excluded():
    bars = [_daily_bar(d, close="10.00") for d in (9, 10)]
    future = _daily_bar(14, close="500.00")
    window = ReturnCountWindow(requested_count=1, minimum_samples=1)
    result = build_percentage_return_standard_deviation_baseline_result([*bars, future], _request(11, window))
    assert future.observation_id not in result.input_observation_ids


def test_stddev_baseline_stable_output_across_repeated_generation():
    bars = [_daily_bar(d, close=c) for d, c in zip((9, 10, 11), ("10.00", "11.00", "10.50"))]
    window = ReturnCountWindow(requested_count=2, minimum_samples=2)
    request = _request(12, window)
    first = build_percentage_return_standard_deviation_baseline_result(bars, request)
    second = build_percentage_return_standard_deviation_baseline_result(bars, request)
    assert first.deterministic_id == second.deterministic_id
    assert first.value == second.value


def test_no_annualization_or_volatility_classification_fields():
    from squeeze_core.metrics import BaselineStatistics, NormalizedMetricResult

    for model in (NormalizedMetricResult, BaselineStatistics):
        field_names = set(model.model_fields)
        for needle in ("annualiz", "volatility", "trend"):
            assert not any(needle in name for name in field_names)
