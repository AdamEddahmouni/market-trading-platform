from datetime import UTC, datetime
from decimal import Decimal

from squeeze_core.adapters.market_bars import BarInterval
from squeeze_core.contracts import AssetClass, Quality, QualityState
from squeeze_core.metrics import (
    MetricDiagnosticCode,
    TrailingWindow,
    VolumeBaselineRequest,
    build_volume_baseline_result,
)
from squeeze_core.metrics.volume_baselines import compute_mean_volume

from .conftest import bar_boundary, make_bar

AS_OF = datetime(2026, 1, 25, 22, 0, tzinfo=UTC)


def _daily_bar(day: int, *, volume="10000", status="COMPLETED", **overrides):
    values = {
        "source_record_id": f"vol-bar-{day}",
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


def _request(target, window: TrailingWindow, **overrides) -> VolumeBaselineRequest:
    start, end = bar_boundary(target)
    values = dict(
        symbol="TESTA",
        asset_class=AssetClass.EQUITY,
        as_of=AS_OF,
        source_interval=BarInterval.ONE_DAY,
        target_bar_start=start,
        target_bar_end=end,
        window=window,
    )
    values.update(overrides)
    return VolumeBaselineRequest(**values)


def test_compute_mean_volume_exact():
    assert compute_mean_volume([Decimal(1000), Decimal(1001), Decimal(1002)]) == Decimal(1001)


def test_compute_mean_volume_nonterminating_stays_exact_decimal():
    value = compute_mean_volume([Decimal(1000), Decimal(1000), Decimal(1001)])
    assert value == (Decimal(3001) / Decimal(3))
    assert isinstance(value, Decimal)


def test_mean_baseline_over_three_completed_bars():
    bars = [_daily_bar(d, volume=str(v)) for d, v in [(12, 1000), (13, 2000), (14, 3000)]]
    target = _daily_bar(15, volume="9999")
    window = TrailingWindow(requested_count=3, minimum_samples=3)
    result = build_volume_baseline_result([*bars, target], _request(target, window))
    assert result.value == Decimal(2000)
    assert result.sample_counts.used == 3
    assert result.quality.state is QualityState.KNOWN_VALUE


def test_mean_baseline_over_five_completed_bars():
    bars = [_daily_bar(d, volume=str(v)) for d, v in [(10, 1000), (11, 1000), (12, 1000), (13, 1000), (14, 5000)]]
    target = _daily_bar(15, volume="9999")
    window = TrailingWindow(requested_count=5, minimum_samples=5)
    result = build_volume_baseline_result([*bars, target], _request(target, window))
    assert result.value == Decimal(1800)
    assert result.sample_counts.used == 5


def test_current_bar_excluded_by_default():
    bars = [_daily_bar(d, volume="1000") for d in (12, 13, 14)]
    target = _daily_bar(15, volume="999999")
    window = TrailingWindow(requested_count=3, minimum_samples=3)
    result = build_volume_baseline_result([*bars, target], _request(target, window))
    assert result.value == Decimal(1000)
    assert target.observation_id not in result.input_observation_ids
    assert any(d.code is MetricDiagnosticCode.VOLUME_BASELINE_CURRENT_BAR_EXCLUDED for d in result.diagnostics)


def test_explicit_target_bar_before_window_only_counts_earlier_bars():
    earlier = _daily_bar(10, volume="1000")
    target = _daily_bar(12, volume="2000")
    later = _daily_bar(14, volume="3000")
    window = TrailingWindow(requested_count=5, minimum_samples=1)
    result = build_volume_baseline_result([earlier, target, later], _request(target, window))
    assert result.value == Decimal(1000)
    assert later.observation_id not in result.input_observation_ids


def test_zero_volume_sample_retained():
    bars = [_daily_bar(12, volume="0"), _daily_bar(13, volume="2000")]
    target = _daily_bar(14, volume="9999")
    window = TrailingWindow(requested_count=2, minimum_samples=2)
    result = build_volume_baseline_result([*bars, target], _request(target, window))
    assert result.value == Decimal(1000)
    assert result.sample_counts.used == 2
    assert any(d.code is MetricDiagnosticCode.METRIC_ZERO_VOLUME_SAMPLE for d in result.diagnostics)


def test_missing_volume_sample_excluded_and_counted():
    bars = [_daily_bar(12, volume=None), _daily_bar(13, volume="2000")]
    target = _daily_bar(14, volume="9999")
    window = TrailingWindow(requested_count=2, minimum_samples=1)
    result = build_volume_baseline_result([*bars, target], _request(target, window))
    assert result.sample_counts.used == 1
    assert result.sample_counts.missing == 1
    assert result.value == Decimal(2000)
    assert any(d.code is MetricDiagnosticCode.METRIC_MISSING_VOLUME for d in result.diagnostics)


def test_insufficient_history():
    bars = [_daily_bar(14, volume="1000")]
    target = _daily_bar(15, volume="9999")
    window = TrailingWindow(requested_count=5, minimum_samples=3)
    result = build_volume_baseline_result([*bars, target], _request(target, window))
    assert result.value is None
    assert result.quality.state is QualityState.UNAVAILABLE
    assert any(d.code is MetricDiagnosticCode.VOLUME_BASELINE_INSUFFICIENT_SAMPLES for d in result.diagnostics)


def test_empty_window():
    target = _daily_bar(15, volume="9999")
    window = TrailingWindow(requested_count=3, minimum_samples=1)
    result = build_volume_baseline_result([target], _request(target, window))
    assert result.value is None
    assert any(d.code is MetricDiagnosticCode.VOLUME_BASELINE_WINDOW_EMPTY for d in result.diagnostics)


def test_mixed_intervals_are_excluded_by_interval_filter():
    daily = _daily_bar(12, volume="1000")
    minute = make_bar(
        source_record_id="vol-minute-13",
        interval="1_MINUTE",
        bar_start="2026-01-13T09:30:00-05:00",
        bar_end="2026-01-13T09:31:00-05:00",
        session_date="2026-01-13",
        publication_timestamp="2026-01-13T09:31:01-05:00",
        ingested_at="2026-01-13T21:02:00Z",
        volume="777777",
    )
    target = _daily_bar(15, volume="9999")
    window = TrailingWindow(requested_count=5, minimum_samples=1)
    result = build_volume_baseline_result([daily, minute, target], _request(target, window))
    assert result.value == Decimal(1000)
    assert minute.observation_id not in result.input_observation_ids


def test_mixed_sessions_are_excluded_by_session_filter():
    regular = _daily_bar(12, volume="1000", session="REGULAR")
    premarket = make_bar(
        source_record_id="vol-premarket-13",
        interval="1_DAY",
        session="PREMARKET",
        bar_start="2026-01-13T00:00:00-05:00",
        bar_end="2026-01-14T00:00:00-05:00",
        session_date="2026-01-13",
        publication_timestamp="2026-01-13T16:01:00-05:00",
        ingested_at="2026-01-13T21:02:00Z",
        volume="777777",
    )
    target = _daily_bar(15, volume="9999", session="REGULAR")
    window = TrailingWindow(requested_count=5, minimum_samples=1)
    from squeeze_core.adapters.market_bars import BarSession

    result = build_volume_baseline_result(
        [regular, premarket, target], _request(target, window, session_scope=(BarSession.REGULAR,))
    )
    assert result.value == Decimal(1000)
    assert premarket.observation_id not in result.input_observation_ids


def test_mixed_providers_ambiguous_without_explicit_provider():
    a = _daily_bar(12, volume="1000", provider="ALPACA_SHAPED", source_record_id="vol-a-12")
    b = _daily_bar(13, volume="2000", provider="SCHWAB_SHAPED", source_record_id="vol-b-13")
    target = _daily_bar(15, volume="9999", provider="ALPACA_SHAPED")
    window = TrailingWindow(requested_count=5, minimum_samples=1)
    result = build_volume_baseline_result([a, b, target], _request(target, window))
    assert result.value is None
    assert any(d.code is MetricDiagnosticCode.METRIC_AMBIGUOUS_PROVIDER for d in result.diagnostics)


def test_mixed_volume_units_excluded():
    same_unit = _daily_bar(12, volume="1000", volume_unit="SHARES")
    other_unit = _daily_bar(13, volume="2000", volume_unit="CONTRACTS", source_record_id="vol-contracts-13")
    target = _daily_bar(15, volume="9999", volume_unit="SHARES")
    window = TrailingWindow(requested_count=5, minimum_samples=1)
    result = build_volume_baseline_result([same_unit, other_unit, target], _request(target, window))
    assert result.value == Decimal(1000)
    assert any(d.code is MetricDiagnosticCode.VOLUME_BASELINE_MIXED_UNITS for d in result.diagnostics)


def test_partial_bar_excluded_from_window():
    partial = _daily_bar(12, volume="1000", status="PARTIAL")
    completed = _daily_bar(13, volume="2000")
    target = _daily_bar(15, volume="9999")
    window = TrailingWindow(requested_count=5, minimum_samples=1)
    result = build_volume_baseline_result([partial, completed, target], _request(target, window))
    assert result.value == Decimal(2000)
    assert partial.observation_id not in result.input_observation_ids
    assert any(d.code is MetricDiagnosticCode.METRIC_PARTIAL_INPUT for d in result.diagnostics)


def test_corrected_bar_before_and_after_correction_receipt():
    original = _daily_bar(12, volume="1000", provider_record_id="vol-original-12")
    corrected = _daily_bar(
        12,
        volume="1500",
        provider_record_id="vol-corrected-12",
        source_record_id="vol-bar-12-corrected",
        status="CORRECTED",
        revision_number=1,
        supersedes_provider_record_id="vol-original-12",
        publication_timestamp="2026-01-18T09:00:00-05:00",
        ingested_at="2026-01-18T09:05:00Z",
    )
    target = _daily_bar(19, volume="9999")
    window = TrailingWindow(requested_count=1, minimum_samples=1)
    observations = [original, corrected, target]

    before = _request(target, window, as_of=datetime(2026, 1, 17, 0, 0, tzinfo=UTC))
    after = _request(target, window, as_of=AS_OF)

    result_before = build_volume_baseline_result(observations, before)
    result_after = build_volume_baseline_result(observations, after)

    assert result_before.value == Decimal(1000)
    assert result_after.value == Decimal(1500)


def test_cancelled_bar_before_and_after_cancellation_receipt():
    original = _daily_bar(12, volume="1000", provider_record_id="vol-original-cancel")
    cancelled = _daily_bar(
        12,
        volume="1000",
        provider_record_id="vol-cancelled-12",
        source_record_id="vol-bar-12-cancelled",
        status="CANCELLED",
        revision_number=1,
        supersedes_provider_record_id="vol-original-cancel",
        publication_timestamp="2026-01-18T09:00:00-05:00",
        ingested_at="2026-01-18T09:05:00Z",
    )
    fallback = _daily_bar(11, volume="500")
    target = _daily_bar(19, volume="9999")
    window = TrailingWindow(requested_count=1, minimum_samples=1)
    observations = [fallback, original, cancelled, target]

    before = _request(target, window, as_of=datetime(2026, 1, 17, 0, 0, tzinfo=UTC))
    after = _request(target, window, as_of=AS_OF)

    result_before = build_volume_baseline_result(observations, before)
    result_after = build_volume_baseline_result(observations, after)

    assert result_before.value == Decimal(1000)
    assert result_after.value == Decimal(500)


def test_out_of_order_input_observations():
    bars = [_daily_bar(d, volume=str(v)) for d, v in [(12, 1000), (13, 2000), (14, 3000)]]
    target = _daily_bar(15, volume="9999")
    window = TrailingWindow(requested_count=3, minimum_samples=3)
    forward = build_volume_baseline_result([*bars, target], _request(target, window))
    reversed_ = build_volume_baseline_result([target, *reversed(bars)], _request(target, window))
    assert forward.value == reversed_.value
    assert forward.deterministic_id == reversed_.deterministic_id


def test_same_boundary_provider_conflict_excluded():
    a = _daily_bar(12, volume="1000", source_record_id="vol-conflict-12-a")
    b = a.model_copy(
        update={
            "observation_id": "conflict-b",
            "quality": Quality(state=QualityState.CONFLICTED, reasons=("same provider record ID has conflicting market-bar content",)),
        }
    )
    a_conflicted = a.model_copy(
        update={"quality": Quality(state=QualityState.CONFLICTED, reasons=("same provider record ID has conflicting market-bar content",))}
    )
    fallback = _daily_bar(11, volume="500")
    target = _daily_bar(15, volume="9999")
    window = TrailingWindow(requested_count=1, minimum_samples=1)
    result = build_volume_baseline_result([fallback, a_conflicted, b, target], _request(target, window))
    assert result.value == Decimal(500)
    assert any(d.code is MetricDiagnosticCode.METRIC_CONFLICTED_INPUT for d in result.diagnostics)


def test_requested_count_larger_than_available_count():
    bars = [_daily_bar(d, volume="1000") for d in (12, 13)]
    target = _daily_bar(15, volume="9999")
    window = TrailingWindow(requested_count=10, minimum_samples=1)
    result = build_volume_baseline_result([*bars, target], _request(target, window))
    assert result.sample_counts.requested == 10
    assert result.sample_counts.used == 2
    assert result.value == Decimal(1000)


def test_minimum_sample_threshold_met_and_not_met():
    bars = [_daily_bar(d, volume="1000") for d in (13, 14)]
    target = _daily_bar(15, volume="9999")
    met = build_volume_baseline_result(
        [*bars, target], _request(target, TrailingWindow(requested_count=2, minimum_samples=2))
    )
    not_met = build_volume_baseline_result(
        [*bars, target], _request(target, TrailingWindow(requested_count=5, minimum_samples=3))
    )
    assert met.quality.state is QualityState.KNOWN_VALUE
    assert not_met.quality.state is QualityState.UNAVAILABLE


def test_no_relative_volume_output():
    assert not hasattr(build_volume_baseline_result.__annotations__.get("return"), "relative_volume")
    bars = [_daily_bar(d, volume="1000") for d in (12, 13, 14)]
    target = _daily_bar(15, volume="9999")
    result = build_volume_baseline_result(
        [*bars, target], _request(target, TrailingWindow(requested_count=3, minimum_samples=3))
    )
    assert "relative_volume" not in type(result).model_fields
    assert "rvol" not in type(result).model_fields


def test_supporting_observation_ids_preserved_and_sorted():
    bars = [_daily_bar(d, volume=str(v)) for d, v in [(12, 1000), (13, 2000), (14, 3000)]]
    target = _daily_bar(15, volume="9999")
    result = build_volume_baseline_result(
        [*bars, target], _request(target, TrailingWindow(requested_count=3, minimum_samples=3))
    )
    assert set(result.input_observation_ids) == {b.observation_id for b in bars}
    assert result.input_observation_ids == tuple(sorted(result.input_observation_ids))


def test_stable_series_and_result_hash_across_two_runs():
    from squeeze_core.metrics import metric_result_hash

    bars = [_daily_bar(d, volume=str(v)) for d, v in [(12, 1000), (13, 2000), (14, 3000)]]
    target = _daily_bar(15, volume="9999")
    request = _request(target, TrailingWindow(requested_count=3, minimum_samples=3))
    first = build_volume_baseline_result([*bars, target], request)
    second = build_volume_baseline_result([*bars, target], request)
    assert metric_result_hash(first) == metric_result_hash(second)
