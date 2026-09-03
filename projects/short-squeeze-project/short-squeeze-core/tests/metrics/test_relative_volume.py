from datetime import UTC, datetime
from decimal import Decimal

from squeeze_core.adapters.market_bars import BarInterval, BarSession
from squeeze_core.contracts import AssetClass, Quality, QualityState
from squeeze_core.metrics import (
    MetricDiagnosticCode,
    NormalizedMetricResult,
    RelativeVolumeRequest,
    TrailingWindow,
    build_relative_volume_result,
    build_volume_percent_deviation_result,
    normalized_metric_result_hash,
)

from .conftest import bar_boundary, make_bar

AS_OF = datetime(2026, 1, 25, 22, 0, tzinfo=UTC)


def _daily_bar(day: int, *, volume="10000", status="COMPLETED", **overrides):
    values = {
        "source_record_id": f"rv-bar-{day}",
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


def _request(target, window: TrailingWindow, **overrides) -> RelativeVolumeRequest:
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
    return RelativeVolumeRequest(**values)


def _bars_and_target(volumes, target_volume, target_day=15):
    bars = [_daily_bar(d, volume=str(v)) for d, v in zip(range(target_day - len(volumes), target_day), volumes)]
    target = _daily_bar(target_day, volume=str(target_volume))
    return bars, target


# --- Case 1-3: above / below / equal baseline -------------------------------------------------


def test_target_volume_above_baseline():
    bars, target = _bars_and_target([1000, 1000, 1000], 3000)
    window = TrailingWindow(requested_count=3, minimum_samples=3)
    result = build_relative_volume_result([*bars, target], _request(target, window))
    assert result.value == Decimal(3)
    dev = build_volume_percent_deviation_result([*bars, target], _request(target, window))
    assert dev.value == Decimal(200)


def test_target_volume_below_baseline():
    bars, target = _bars_and_target([1000, 1000, 1000], 500)
    window = TrailingWindow(requested_count=3, minimum_samples=3)
    result = build_relative_volume_result([*bars, target], _request(target, window))
    assert result.value == Decimal("0.5")
    dev = build_volume_percent_deviation_result([*bars, target], _request(target, window))
    assert dev.value == Decimal(-50)


def test_target_volume_equal_baseline():
    bars, target = _bars_and_target([1000, 1000, 1000], 1000)
    window = TrailingWindow(requested_count=3, minimum_samples=3)
    result = build_relative_volume_result([*bars, target], _request(target, window))
    assert result.value == Decimal(1)
    dev = build_volume_percent_deviation_result([*bars, target], _request(target, window))
    assert dev.value == Decimal(0)


# --- Case 4: zero target volume ----------------------------------------------------------------


def test_target_volume_zero_is_valid():
    bars, target = _bars_and_target([1000, 1000, 1000], 0)
    window = TrailingWindow(requested_count=3, minimum_samples=3)
    result = build_relative_volume_result([*bars, target], _request(target, window))
    assert result.value == Decimal(0)
    assert result.quality.state is QualityState.KNOWN_VALUE
    dev = build_volume_percent_deviation_result([*bars, target], _request(target, window))
    assert dev.value == Decimal(-100)


# --- Case 5: baseline zero -----------------------------------------------------------------------


def test_baseline_zero_is_invalid_denominator():
    bars, target = _bars_and_target([0, 0, 0], 500)
    window = TrailingWindow(requested_count=3, minimum_samples=3)
    result = build_relative_volume_result([*bars, target], _request(target, window))
    assert result.value is None
    assert result.quality.state is QualityState.INVALID
    assert any(d.code is MetricDiagnosticCode.RELATIVE_VOLUME_BASELINE_ZERO for d in result.diagnostics)


# --- Case 6: missing target volume ---------------------------------------------------------------


def test_missing_target_volume_is_not_zero():
    bars = [_daily_bar(d, volume="1000") for d in (12, 13, 14)]
    target = _daily_bar(15, volume=None)
    window = TrailingWindow(requested_count=3, minimum_samples=3)
    result = build_relative_volume_result([*bars, target], _request(target, window))
    assert result.value is None
    assert result.quality.state is QualityState.UNAVAILABLE
    assert any(d.code is MetricDiagnosticCode.RELATIVE_VOLUME_TARGET_MISSING_VOLUME for d in result.diagnostics)


# --- Case 7: missing baseline (insufficient history) ----------------------------------------------


def test_missing_baseline_insufficient_history():
    bars = [_daily_bar(14, volume="1000")]
    target = _daily_bar(15, volume="9999")
    window = TrailingWindow(requested_count=5, minimum_samples=3)
    result = build_relative_volume_result([*bars, target], _request(target, window))
    assert result.value is None
    assert result.quality.state is QualityState.UNAVAILABLE
    assert any(d.code is MetricDiagnosticCode.RELATIVE_VOLUME_BASELINE_UNAVAILABLE for d in result.diagnostics)


# --- Case 8-9: three/five sample baselines --------------------------------------------------------


def test_three_sample_baseline():
    bars, target = _bars_and_target([1000, 2000, 3000], 6000)
    window = TrailingWindow(requested_count=3, minimum_samples=3)
    result = build_relative_volume_result([*bars, target], _request(target, window))
    assert result.value == Decimal(3)


def test_five_sample_baseline():
    bars, target = _bars_and_target([1000, 1000, 1000, 1000, 5000], 1800)
    window = TrailingWindow(requested_count=5, minimum_samples=5)
    result = build_relative_volume_result([*bars, target], _request(target, window))
    assert result.value == Decimal(1)


# --- Case 10-11: current bar excluded / accidental target inclusion --------------------------------


def test_current_bar_excluded_from_its_own_baseline_window():
    bars = [_daily_bar(d, volume="1000") for d in (12, 13, 14)]
    target = _daily_bar(15, volume="2000")
    window = TrailingWindow(requested_count=3, minimum_samples=3)
    result = build_relative_volume_result([*bars, target], _request(target, window))
    # The target bar is a legitimate numerator input to the ratio itself...
    assert target.observation_id in result.input_observation_ids
    # ...but is excluded from the trailing baseline window that forms the denominator.
    assert any(
        d.code is MetricDiagnosticCode.VOLUME_BASELINE_CURRENT_BAR_EXCLUDED for d in result.diagnostics
    )
    assert result.value == Decimal(2)


def test_target_bar_accidentally_included_in_input_still_excluded_from_baseline():
    bars = [_daily_bar(d, volume="1000") for d in (12, 13, 14)]
    target = _daily_bar(15, volume="2000")
    window = TrailingWindow(requested_count=3, minimum_samples=3)
    result = build_relative_volume_result([target, *bars, target], _request(target, window))
    assert result.value == Decimal(2)


# --- Case 12-16: mixed provider / interval / session / unit / partial ------------------------------


def test_mixed_providers_ambiguous_without_explicit_provider():
    a = _daily_bar(12, volume="1000", provider="ALPACA_SHAPED", source_record_id="rv-a-12")
    b = _daily_bar(13, volume="2000", provider="SCHWAB_SHAPED", source_record_id="rv-b-13")
    target = _daily_bar(15, volume="9999", provider="ALPACA_SHAPED")
    window = TrailingWindow(requested_count=5, minimum_samples=1)
    result = build_relative_volume_result([a, b, target], _request(target, window))
    assert result.value is None
    assert any(d.code is MetricDiagnosticCode.METRIC_AMBIGUOUS_PROVIDER for d in result.diagnostics)


def test_explicit_provider_selection_resolves_ambiguity():
    a = _daily_bar(12, volume="1000", provider="ALPACA_SHAPED", source_record_id="rv-a2-12")
    b = _daily_bar(13, volume="2000", provider="SCHWAB_SHAPED", source_record_id="rv-b2-13")
    target = _daily_bar(15, volume="9999", provider="ALPACA_SHAPED")
    window = TrailingWindow(requested_count=5, minimum_samples=1)
    result = build_relative_volume_result([a, b, target], _request(target, window, provider="ALPACA_SHAPED"))
    assert result.value == Decimal(9999) / Decimal(1000)


def test_mixed_intervals_excluded_by_interval_filter():
    daily = _daily_bar(12, volume="1000")
    minute = make_bar(
        source_record_id="rv-minute-13", interval="1_MINUTE", bar_start="2026-01-13T09:30:00-05:00",
        bar_end="2026-01-13T09:31:00-05:00", session_date="2026-01-13",
        publication_timestamp="2026-01-13T09:31:01-05:00", ingested_at="2026-01-13T21:02:00Z", volume="777777",
    )
    target = _daily_bar(15, volume="9999")
    window = TrailingWindow(requested_count=5, minimum_samples=1)
    result = build_relative_volume_result([daily, minute, target], _request(target, window))
    assert minute.observation_id not in result.input_observation_ids
    assert result.value == Decimal(9999) / Decimal(1000)


def test_mixed_sessions_excluded_by_session_filter():
    regular = _daily_bar(12, volume="1000", session="REGULAR")
    premarket = make_bar(
        source_record_id="rv-premarket-13", interval="1_DAY", session="PREMARKET",
        bar_start="2026-01-13T00:00:00-05:00", bar_end="2026-01-14T00:00:00-05:00", session_date="2026-01-13",
        publication_timestamp="2026-01-13T16:01:00-05:00", ingested_at="2026-01-13T21:02:00Z", volume="777777",
    )
    target = _daily_bar(15, volume="9999", session="REGULAR")
    window = TrailingWindow(requested_count=5, minimum_samples=1)
    result = build_relative_volume_result(
        [regular, premarket, target], _request(target, window, session_scope=(BarSession.REGULAR,))
    )
    assert premarket.observation_id not in result.input_observation_ids
    assert result.value == Decimal(9999) / Decimal(1000)


def test_mixed_volume_units_excluded():
    same_unit = _daily_bar(12, volume="1000", volume_unit="SHARES")
    other_unit = _daily_bar(13, volume="2000", volume_unit="CONTRACTS", source_record_id="rv-contracts-13")
    target = _daily_bar(15, volume="9999", volume_unit="SHARES")
    window = TrailingWindow(requested_count=5, minimum_samples=1)
    result = build_relative_volume_result([same_unit, other_unit, target], _request(target, window))
    assert result.value == Decimal(9999) / Decimal(1000)
    assert any(d.code is MetricDiagnosticCode.VOLUME_BASELINE_MIXED_UNITS for d in result.diagnostics)


def test_partial_target_bar_is_not_found():
    completed = _daily_bar(13, volume="2000")
    target = _daily_bar(15, volume="9999", status="PARTIAL")
    window = TrailingWindow(requested_count=5, minimum_samples=1)
    result = build_relative_volume_result([completed, target], _request(target, window))
    assert result.value is None
    assert any(d.code is MetricDiagnosticCode.METRIC_PARTIAL_INPUT for d in result.diagnostics)


# --- Case 18-25: correction / cancellation before and after receipt, for target and baseline -------


def test_corrected_target_before_and_after_correction_receipt():
    bars = [_daily_bar(d, volume="1000") for d in (12, 13, 14)]
    original = _daily_bar(15, volume="1000", provider_record_id="rv-orig-target")
    corrected = _daily_bar(
        15, volume="4000", provider_record_id="rv-corrected-target", source_record_id="rv-bar-15-corrected",
        status="CORRECTED", revision_number=1, supersedes_provider_record_id="rv-orig-target",
        publication_timestamp="2026-01-18T09:00:00-05:00", ingested_at="2026-01-18T09:05:00Z",
    )
    window = TrailingWindow(requested_count=3, minimum_samples=3)
    observations = [*bars, original, corrected]
    before = _request(corrected, window, as_of=datetime(2026, 1, 17, 0, 0, tzinfo=UTC))
    after = _request(corrected, window, as_of=AS_OF)
    result_before = build_relative_volume_result(observations, before)
    result_after = build_relative_volume_result(observations, after)
    assert result_before.value == Decimal(1)
    assert result_after.value == Decimal(4)


def test_cancelled_target_before_and_after_cancellation_receipt():
    bars = [_daily_bar(d, volume="1000") for d in (12, 13, 14)]
    original = _daily_bar(15, volume="1000", provider_record_id="rv-orig-cancel-target")
    cancelled = _daily_bar(
        15, volume="1000", provider_record_id="rv-cancelled-target", source_record_id="rv-bar-15-cancelled",
        status="CANCELLED", revision_number=1, supersedes_provider_record_id="rv-orig-cancel-target",
        publication_timestamp="2026-01-18T09:00:00-05:00", ingested_at="2026-01-18T09:05:00Z",
    )
    window = TrailingWindow(requested_count=3, minimum_samples=3)
    observations = [*bars, original, cancelled]
    before = _request(cancelled, window, as_of=datetime(2026, 1, 17, 0, 0, tzinfo=UTC))
    after = _request(cancelled, window, as_of=AS_OF)
    result_before = build_relative_volume_result(observations, before)
    result_after = build_relative_volume_result(observations, after)
    assert result_before.value == Decimal(1)
    assert result_after.value is None
    assert result_after.quality.state is QualityState.UNAVAILABLE


def test_corrected_baseline_sample_before_and_after_correction_receipt():
    original = _daily_bar(12, volume="1000", provider_record_id="rv-orig-baseline")
    corrected = _daily_bar(
        12, volume="4000", provider_record_id="rv-corrected-baseline", source_record_id="rv-bar-12-corrected",
        status="CORRECTED", revision_number=1, supersedes_provider_record_id="rv-orig-baseline",
        publication_timestamp="2026-01-18T09:00:00-05:00", ingested_at="2026-01-18T09:05:00Z",
    )
    target = _daily_bar(15, volume="4000")
    window = TrailingWindow(requested_count=1, minimum_samples=1)
    observations = [original, corrected, target]
    before = _request(target, window, as_of=datetime(2026, 1, 17, 0, 0, tzinfo=UTC))
    after = _request(target, window, as_of=AS_OF)
    result_before = build_relative_volume_result(observations, before)
    result_after = build_relative_volume_result(observations, after)
    assert result_before.value == Decimal(4)
    assert result_after.value == Decimal(1)


def test_cancelled_baseline_sample_before_and_after_cancellation_receipt():
    fallback = _daily_bar(11, volume="500")
    original = _daily_bar(12, volume="1000", provider_record_id="rv-orig-cancel-base")
    cancelled = _daily_bar(
        12, volume="1000", provider_record_id="rv-cancelled-base", source_record_id="rv-bar-12-cancelled",
        status="CANCELLED", revision_number=1, supersedes_provider_record_id="rv-orig-cancel-base",
        publication_timestamp="2026-01-18T09:00:00-05:00", ingested_at="2026-01-18T09:05:00Z",
    )
    target = _daily_bar(15, volume="1000")
    window = TrailingWindow(requested_count=1, minimum_samples=1)
    observations = [fallback, original, cancelled, target]
    before = _request(target, window, as_of=datetime(2026, 1, 17, 0, 0, tzinfo=UTC))
    after = _request(target, window, as_of=AS_OF)
    result_before = build_relative_volume_result(observations, before)
    result_after = build_relative_volume_result(observations, after)
    assert result_before.value == Decimal(1)
    assert result_after.value == Decimal(2)


# --- Case 26-28: out-of-order, duplicate, same-boundary conflict -----------------------------------


def test_out_of_order_input_observations_are_a_no_op():
    bars, target = _bars_and_target([1000, 2000, 3000], 6000)
    window = TrailingWindow(requested_count=3, minimum_samples=3)
    forward = build_relative_volume_result([*bars, target], _request(target, window))
    reversed_ = build_relative_volume_result([target, *reversed(bars)], _request(target, window))
    assert forward.value == reversed_.value
    assert forward.deterministic_id == reversed_.deterministic_id


def test_same_boundary_provider_conflict_excluded():
    a = _daily_bar(12, volume="1000", source_record_id="rv-conflict-12-a")
    b = a.model_copy(
        update={
            "observation_id": "rv-conflict-b",
            "quality": Quality(state=QualityState.CONFLICTED, reasons=("same provider record ID has conflicting market-bar content",)),
        }
    )
    a_conflicted = a.model_copy(
        update={"quality": Quality(state=QualityState.CONFLICTED, reasons=("same provider record ID has conflicting market-bar content",))}
    )
    fallback = _daily_bar(11, volume="500")
    target = _daily_bar(15, volume="500")
    window = TrailingWindow(requested_count=1, minimum_samples=1)
    result = build_relative_volume_result([fallback, a_conflicted, b, target], _request(target, window))
    assert result.value == Decimal(1)
    assert any(d.code is MetricDiagnosticCode.METRIC_CONFLICTED_INPUT for d in result.diagnostics)


# --- Case 29-32: exact Decimal, repeatable hash, no qualitative label, no threshold classification --


def test_exact_decimal_preservation_nonterminating():
    bars, target = _bars_and_target([1000, 1000, 1001], 2000)
    window = TrailingWindow(requested_count=3, minimum_samples=3)
    result = build_relative_volume_result([*bars, target], _request(target, window))
    assert result.value == Decimal(2000) / (Decimal(3001) / Decimal(3))
    assert isinstance(result.value, Decimal)


def test_repeated_result_is_byte_identical():
    bars, target = _bars_and_target([1000, 2000, 3000], 6000)
    window = TrailingWindow(requested_count=3, minimum_samples=3)
    request = _request(target, window)
    first = build_relative_volume_result([*bars, target], request)
    second = build_relative_volume_result([*bars, target], request)
    assert normalized_metric_result_hash(first) == normalized_metric_result_hash(second)


def test_no_qualitative_or_threshold_fields_on_result():
    field_names = set(NormalizedMetricResult.model_fields)
    for needle in ("label", "threshold", "classification", "strong", "weak", "bullish", "bearish"):
        assert not any(needle in name for name in field_names)
