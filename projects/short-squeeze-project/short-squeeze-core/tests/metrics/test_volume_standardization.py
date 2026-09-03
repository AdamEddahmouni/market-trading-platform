from datetime import UTC, datetime
from decimal import Decimal

from squeeze_core.adapters.market_bars import BarInterval, BarSession
from squeeze_core.contracts import AssetClass, QualityState
from squeeze_core.metrics import (
    MetricDiagnosticCode,
    TrailingWindow,
    VolumeZScoreRequest,
    build_volume_distribution_statistics,
    build_volume_z_score_result,
    normalized_metric_result_hash,
)

from .conftest import bar_boundary, make_bar

AS_OF = datetime(2026, 1, 25, 22, 0, tzinfo=UTC)


def _daily_bar(day: int, *, volume="10000", status="COMPLETED", **overrides):
    values = {
        "source_record_id": f"vz-bar-{day}",
        "bar_start": f"2026-01-{day:02d}T00:00:00-05:00",
        "bar_end": f"2026-01-{day + 1:02d}T00:00:00-05:00",
        "session_date": f"2026-01-{day:02d}",
        "publication_timestamp": f"2026-01-{day:02d}T16:01:00-05:00",
        "ingested_at": f"2026-01-{day:02d}T21:02:00Z",
        "high": "1000.00",
        "low": "0.01",
        "open": "10.00",
        "close": "10.00",
        "volume": volume,
        "status": status,
    }
    values.update(overrides)
    return make_bar(**values)


def _request(target, window: TrailingWindow, **overrides) -> VolumeZScoreRequest:
    start, end = bar_boundary(target)
    values = dict(
        symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF, source_interval=BarInterval.ONE_DAY,
        target_bar_start=start, target_bar_end=end, window=window,
    )
    values.update(overrides)
    return VolumeZScoreRequest(**values)


# population [2,4,4,4,5,5,7,9]: mean=5 variance=4 stddev=2
DISTRIBUTION_VOLUMES = [2, 4, 4, 4, 5, 5, 7, 9]


def _distribution_bars(target_day=20):
    days = list(range(target_day - len(DISTRIBUTION_VOLUMES), target_day))
    return [_daily_bar(d, volume=str(v)) for d, v in zip(days, DISTRIBUTION_VOLUMES)]


def test_positive_z_score():
    bars = _distribution_bars()
    target = _daily_bar(20, volume="9")
    window = TrailingWindow(requested_count=8, minimum_samples=2)
    result = build_volume_z_score_result([*bars, target], _request(target, window))
    assert result.value == Decimal(2)
    assert result.quality.state is QualityState.KNOWN_VALUE


def test_negative_z_score():
    bars = _distribution_bars()
    target = _daily_bar(20, volume="1")
    window = TrailingWindow(requested_count=8, minimum_samples=2)
    result = build_volume_z_score_result([*bars, target], _request(target, window))
    assert result.value == Decimal(-2)


def test_zero_z_score_when_target_equals_mean():
    bars = _distribution_bars()
    target = _daily_bar(20, volume="5")
    window = TrailingWindow(requested_count=8, minimum_samples=2)
    result = build_volume_z_score_result([*bars, target], _request(target, window))
    assert result.value == Decimal(0)


def test_two_sample_baseline():
    bars = [_daily_bar(18, volume="100"), _daily_bar(19, volume="100")]
    target = _daily_bar(20, volume="150")
    window = TrailingWindow(requested_count=2, minimum_samples=2)
    result = build_volume_z_score_result([*bars, target], _request(target, window))
    # two identical samples -> stddev 0 -> undefined
    assert result.value is None
    assert result.quality.state is QualityState.INVALID


def test_three_sample_baseline():
    bars = [_daily_bar(d, volume=str(v)) for d, v in zip((17, 18, 19), (10, 20, 30))]
    target = _daily_bar(20, volume="60")
    window = TrailingWindow(requested_count=3, minimum_samples=2)
    result = build_volume_z_score_result([*bars, target], _request(target, window))
    assert result.quality.state is QualityState.KNOWN_VALUE
    assert result.value is not None


def test_five_sample_baseline():
    bars = [_daily_bar(d, volume=str(v)) for d, v in zip(range(15, 20), (10, 20, 30, 40, 50))]
    target = _daily_bar(20, volume="60")
    window = TrailingWindow(requested_count=5, minimum_samples=2)
    result = build_volume_z_score_result([*bars, target], _request(target, window))
    assert result.quality.state is QualityState.KNOWN_VALUE


def test_insufficient_sample_count():
    bars = [_daily_bar(19, volume="100")]
    target = _daily_bar(20, volume="150")
    window = TrailingWindow(requested_count=5, minimum_samples=3)
    result = build_volume_z_score_result([*bars, target], _request(target, window))
    assert result.value is None
    assert result.quality.state is QualityState.UNAVAILABLE
    assert any(d.code is MetricDiagnosticCode.VOLUME_DISTRIBUTION_INSUFFICIENT_SAMPLES for d in result.diagnostics)


def test_zero_variance_all_samples_identical():
    bars = [_daily_bar(d, volume="100") for d in (17, 18, 19)]
    target = _daily_bar(20, volume="150")
    window = TrailingWindow(requested_count=3, minimum_samples=2)
    result = build_volume_z_score_result([*bars, target], _request(target, window))
    assert result.value is None
    assert result.quality.state is QualityState.INVALID
    assert any(d.code is MetricDiagnosticCode.VOLUME_DISTRIBUTION_ZERO_VARIANCE for d in result.diagnostics)
    assert any(d.code is MetricDiagnosticCode.NORMALIZED_METRIC_ZERO_VARIANCE for d in result.diagnostics)


def test_zero_volume_samples_retained_in_distribution():
    bars = [_daily_bar(18, volume="0"), _daily_bar(19, volume="10")]
    target = _daily_bar(20, volume="5")
    window = TrailingWindow(requested_count=2, minimum_samples=2)
    distribution = build_volume_distribution_statistics([*bars, target], _request(target, window))
    assert distribution.mean == Decimal(5)
    assert any(d.code is MetricDiagnosticCode.METRIC_ZERO_VOLUME_SAMPLE for d in distribution.diagnostics)


def test_missing_volume_sample_excluded_and_counted():
    bars = [_daily_bar(18, volume=None), _daily_bar(19, volume="10")]
    target = _daily_bar(20, volume="5")
    window = TrailingWindow(requested_count=2, minimum_samples=1)
    distribution = build_volume_distribution_statistics([*bars, target], _request(target, window))
    assert distribution.sample_counts.used == 1
    assert distribution.sample_counts.missing == 1
    assert any(d.code is MetricDiagnosticCode.METRIC_MISSING_VOLUME for d in distribution.diagnostics)


def test_exact_population_variance_and_decimal_sqrt():
    bars = _distribution_bars()
    target = _daily_bar(20, volume="9")
    window = TrailingWindow(requested_count=8, minimum_samples=2)
    distribution = build_volume_distribution_statistics([*bars, target], _request(target, window))
    assert distribution.mean == Decimal(5)
    assert distribution.variance == Decimal(4)
    assert distribution.standard_deviation == Decimal(2)
    assert isinstance(distribution.standard_deviation, Decimal)


def test_no_float_conversion_anywhere_in_result():
    bars = _distribution_bars()
    target = _daily_bar(20, volume="9")
    window = TrailingWindow(requested_count=8, minimum_samples=2)
    result = build_volume_z_score_result([*bars, target], _request(target, window))
    assert isinstance(result.value, Decimal)


def test_current_target_excluded_from_its_own_distribution():
    bars = _distribution_bars()
    target = _daily_bar(20, volume="9")
    window = TrailingWindow(requested_count=8, minimum_samples=2)
    result = build_volume_z_score_result([*bars, target], _request(target, window))
    assert any(d.code is MetricDiagnosticCode.VOLUME_BASELINE_CURRENT_BAR_EXCLUDED for d in result.diagnostics)


def test_future_sample_excluded_by_point_in_time():
    bars = _distribution_bars()
    future = _daily_bar(21, volume="999999")
    target = _daily_bar(20, volume="9")
    window = TrailingWindow(requested_count=8, minimum_samples=2)
    result = build_volume_z_score_result([*bars, target, future], _request(target, window))
    assert result.value == Decimal(2)


def test_correction_before_and_after_availability():
    bars = _distribution_bars()
    original = _daily_bar(20, volume="9", provider_record_id="vz-orig-target")
    corrected = _daily_bar(
        20, volume="9", provider_record_id="vz-corrected-target", source_record_id="vz-bar-20-corrected",
        status="CORRECTED", revision_number=1, supersedes_provider_record_id="vz-orig-target",
        publication_timestamp="2026-01-23T09:00:00-05:00", ingested_at="2026-01-23T09:05:00Z",
    )
    window = TrailingWindow(requested_count=8, minimum_samples=2)
    observations = [*bars, original, corrected]
    before = _request(corrected, window, as_of=datetime(2026, 1, 22, 0, 0, tzinfo=UTC))
    after = _request(corrected, window, as_of=AS_OF)
    result_before = build_volume_z_score_result(observations, before)
    result_after = build_volume_z_score_result(observations, after)
    # Both as-of points see the same COMPLETED-then-CORRECTED bar (volume is unchanged by the
    # correction here); the two results are not required to share a deterministic_id since as_of
    # differs, but the computed value must be identical and stable either side of the correction.
    assert result_before.value == result_after.value == Decimal(2)


def test_cancellation_before_and_after_availability():
    bars = _distribution_bars()
    sample_original = _daily_bar(12, volume="4", provider_record_id="vz-orig-sample")
    sample_cancelled = _daily_bar(
        12, volume="4", provider_record_id="vz-cancelled-sample", source_record_id="vz-bar-12-cancelled",
        status="CANCELLED", revision_number=1, supersedes_provider_record_id="vz-orig-sample",
        publication_timestamp="2026-01-23T09:00:00-05:00", ingested_at="2026-01-23T09:05:00Z",
    )
    target = _daily_bar(20, volume="9")
    window = TrailingWindow(requested_count=8, minimum_samples=2)
    others = [b for b in bars if b.observation_id != sample_original.observation_id]
    observations = [*others, sample_original, sample_cancelled, target]
    before = _request(target, window, as_of=datetime(2026, 1, 22, 0, 0, tzinfo=UTC))
    after = _request(target, window, as_of=AS_OF)
    result_before = build_volume_z_score_result(observations, before)
    result_after = build_volume_z_score_result(observations, after)
    assert result_before.value != result_after.value


def test_mixed_provider_rejection():
    a = _daily_bar(18, volume="10", provider="ALPACA_SHAPED", source_record_id="vz-a-18")
    b = _daily_bar(19, volume="20", provider="SCHWAB_SHAPED", source_record_id="vz-b-19")
    target = _daily_bar(20, volume="30", provider="ALPACA_SHAPED")
    window = TrailingWindow(requested_count=5, minimum_samples=1)
    result = build_volume_z_score_result([a, b, target], _request(target, window))
    assert result.value is None
    assert any(d.code is MetricDiagnosticCode.METRIC_AMBIGUOUS_PROVIDER for d in result.diagnostics)


def test_mixed_session_rejection():
    regular = _daily_bar(18, volume="10", session="REGULAR")
    premarket = make_bar(
        source_record_id="vz-premarket-19", interval="1_DAY", session="PREMARKET",
        bar_start="2026-01-19T00:00:00-05:00", bar_end="2026-01-20T00:00:00-05:00", session_date="2026-01-19",
        publication_timestamp="2026-01-19T16:01:00-05:00", ingested_at="2026-01-19T21:02:00Z", volume="777777",
    )
    target = _daily_bar(20, volume="30", session="REGULAR")
    window = TrailingWindow(requested_count=5, minimum_samples=1)
    result = build_volume_z_score_result(
        [regular, premarket, target], _request(target, window, session_scope=(BarSession.REGULAR,))
    )
    assert premarket.observation_id not in result.input_observation_ids


def test_mixed_interval_rejection():
    daily = _daily_bar(18, volume="10")
    minute = make_bar(
        source_record_id="vz-minute-19", interval="1_MINUTE", bar_start="2026-01-19T09:30:00-05:00",
        bar_end="2026-01-19T09:31:00-05:00", session_date="2026-01-19",
        publication_timestamp="2026-01-19T09:31:01-05:00", ingested_at="2026-01-19T21:02:00Z", volume="777777",
    )
    target = _daily_bar(20, volume="30")
    window = TrailingWindow(requested_count=5, minimum_samples=1)
    result = build_volume_z_score_result([daily, minute, target], _request(target, window))
    assert minute.observation_id not in result.input_observation_ids


def test_mixed_unit_rejection():
    same_unit = _daily_bar(18, volume="10", volume_unit="SHARES")
    other_unit = _daily_bar(19, volume="20", volume_unit="CONTRACTS", source_record_id="vz-contracts-19")
    target = _daily_bar(20, volume="30", volume_unit="SHARES")
    window = TrailingWindow(requested_count=5, minimum_samples=1)
    result = build_volume_z_score_result([same_unit, other_unit, target], _request(target, window))
    assert other_unit.observation_id not in result.input_observation_ids
    assert any(d.code is MetricDiagnosticCode.VOLUME_BASELINE_MIXED_UNITS for d in result.diagnostics)


def test_input_order_invariance():
    bars = _distribution_bars()
    target = _daily_bar(20, volume="9")
    window = TrailingWindow(requested_count=8, minimum_samples=2)
    forward = build_volume_z_score_result([*bars, target], _request(target, window))
    backward = build_volume_z_score_result([target, *reversed(bars)], _request(target, window))
    assert forward.value == backward.value
    assert forward.deterministic_id == backward.deterministic_id


def test_repeated_serialization_invariance():
    bars = _distribution_bars()
    target = _daily_bar(20, volume="9")
    window = TrailingWindow(requested_count=8, minimum_samples=2)
    request = _request(target, window)
    first = build_volume_z_score_result([*bars, target], request)
    second = build_volume_z_score_result([*bars, target], request)
    assert normalized_metric_result_hash(first) == normalized_metric_result_hash(second)


def test_stable_baseline_statistics_identity():
    bars = _distribution_bars()
    target = _daily_bar(20, volume="9")
    window = TrailingWindow(requested_count=8, minimum_samples=2)
    first = build_volume_distribution_statistics([*bars, target], _request(target, window))
    second = build_volume_distribution_statistics([*bars, target], _request(target, window))
    assert first.deterministic_id == second.deterministic_id


def test_stable_normalized_result_identity():
    bars = _distribution_bars()
    target = _daily_bar(20, volume="9")
    window = TrailingWindow(requested_count=8, minimum_samples=2)
    first = build_volume_z_score_result([*bars, target], _request(target, window))
    second = build_volume_z_score_result([*bars, target], _request(target, window))
    assert first.deterministic_id == second.deterministic_id


def test_no_extreme_classification_or_alert_threshold_fields():
    from squeeze_core.metrics import BaselineStatistics, NormalizedMetricResult

    for model in (NormalizedMetricResult, BaselineStatistics):
        field_names = set(model.model_fields)
        for needle in ("extreme", "alert", "threshold"):
            assert not any(needle in name for name in field_names)
