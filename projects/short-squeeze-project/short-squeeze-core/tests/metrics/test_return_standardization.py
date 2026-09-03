from datetime import UTC, datetime
from decimal import Decimal

from squeeze_core.adapters.market_bars import BarInterval, BarSession
from squeeze_core.contracts import AssetClass, QualityState
from squeeze_core.metrics import (
    MetricDiagnosticCode,
    ReturnCountWindow,
    ReturnZScoreRequest,
    build_percentage_return_z_score_result,
)

from .conftest import bar_boundary, make_bar

AS_OF = datetime(2026, 1, 25, 22, 0, tzinfo=UTC)


def _daily_bar(day: int, *, close="10.00", status="COMPLETED", **overrides):
    values = {
        "source_record_id": f"rz-bar-{day}",
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


def _request(start_day: int, end_day: int, window: ReturnCountWindow, **overrides) -> ReturnZScoreRequest:
    start_bar = _daily_bar(start_day)
    end_bar = _daily_bar(end_day)
    s0, s1 = bar_boundary(start_bar)
    e0, e1 = bar_boundary(end_bar)
    values = dict(
        symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF, source_interval=BarInterval.ONE_DAY,
        target_start_bar_start=s0, target_start_bar_end=s1, target_end_bar_start=e0, target_end_bar_end=e1,
        window=window,
    )
    values.update(overrides)
    return ReturnZScoreRequest(**values)


def _history(days_closes):
    return [_daily_bar(d, close=c) for d, c in days_closes]


# Shared baseline: three historical bars (days 6,7,8) all strictly before the target return's
# start boundary (day 9) -- exactly enough for a requested_count=2 (N+1=3 bars) window. The
# target return is bar9 -> bar10, never itself among days 6-8.
FLAT_HISTORY = [(6, "10.00"), (7, "11.00"), (8, "12.10")]  # each step exactly +10%
MIXED_HISTORY = [(6, "10.00"), (7, "12.00"), (8, "9.00")]  # +20%, -25%; mean=-2.5, std>0
WINDOW_2 = ReturnCountWindow(requested_count=2, minimum_samples=2)


def test_positive_z_score():
    history = _history(MIXED_HISTORY)
    target_start = _daily_bar(9, close="9.00")
    target_end = _daily_bar(10, close="18.00")  # +100%, far above the mixed history's mean
    result = build_percentage_return_z_score_result(
        [*history, target_start, target_end], _request(9, 10, WINDOW_2)
    )
    assert result.quality.state is QualityState.KNOWN_VALUE
    assert result.value > 0


def test_negative_z_score():
    history = _history(MIXED_HISTORY)
    target_start = _daily_bar(9, close="9.00")
    target_end = _daily_bar(10, close="4.50")  # -50%, well below the mixed history's mean
    result = build_percentage_return_z_score_result(
        [*history, target_start, target_end], _request(9, 10, WINDOW_2)
    )
    assert result.value < 0


def test_zero_z_score_when_target_equals_historical_mean():
    history = _history(MIXED_HISTORY)
    target_start = _daily_bar(9, close="9.00")
    target_end = _daily_bar(10, close="8.775")  # exactly -2.5%, matching the historical mean
    result = build_percentage_return_z_score_result(
        [*history, target_start, target_end], _request(9, 10, WINDOW_2)
    )
    assert result.quality.state is QualityState.KNOWN_VALUE
    assert result.value == Decimal(0)


def test_zero_variance_baseline_makes_z_score_undefined():
    history = _history(FLAT_HISTORY)
    target_start = _daily_bar(9, close="12.10")
    target_end = _daily_bar(10, close="20.00")
    result = build_percentage_return_z_score_result(
        [*history, target_start, target_end], _request(9, 10, WINDOW_2)
    )
    assert result.value is None
    assert result.quality.state is QualityState.INVALID
    assert any(d.code is MetricDiagnosticCode.RETURN_DISTRIBUTION_ZERO_VARIANCE for d in result.diagnostics)
    assert any(d.code is MetricDiagnosticCode.NORMALIZED_METRIC_ZERO_VARIANCE for d in result.diagnostics)


def test_missing_target_return_start_bar_not_found():
    history = _history(FLAT_HISTORY)
    target_end = _daily_bar(10, close="10.00")
    result = build_percentage_return_z_score_result([*history, target_end], _request(9, 10, WINDOW_2))
    assert result.value is None
    assert result.quality.state is QualityState.UNAVAILABLE
    assert any(d.code is MetricDiagnosticCode.RETURN_TARGET_NOT_FOUND for d in result.diagnostics)


def test_insufficient_baseline_history():
    target_start = _daily_bar(9, close="10.00")
    target_end = _daily_bar(10, close="11.00")
    request = _request(9, 10, ReturnCountWindow(requested_count=3, minimum_samples=3))
    result = build_percentage_return_z_score_result([target_start, target_end], request)
    assert result.value is None
    assert result.quality.state is QualityState.UNAVAILABLE


def test_target_excluded_from_baseline():
    from squeeze_core.metrics import ReturnBaselineRequest, build_return_distribution_statistics

    history = _history(MIXED_HISTORY)
    target_start = _daily_bar(9, close="9.00")
    target_end = _daily_bar(10, close="8.775")
    result = build_percentage_return_z_score_result(
        [*history, target_start, target_end], _request(9, 10, WINDOW_2)
    )
    baseline_request = ReturnBaselineRequest(
        symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF, source_interval=BarInterval.ONE_DAY,
        target_bar_start=bar_boundary(target_start)[0], window=WINDOW_2,
    )
    distribution = build_return_distribution_statistics(
        [*history, target_start, target_end], baseline_request
    )
    assert target_start.observation_id not in distribution.input_observation_ids
    assert result.quality.state is QualityState.KNOWN_VALUE


def test_mixed_provider_rejection():
    a = _daily_bar(6, close="10.00", provider="ALPACA_SHAPED", source_record_id="rz-a-6")
    b = _daily_bar(7, close="12.00", provider="SCHWAB_SHAPED", source_record_id="rz-b-7")
    target_start = _daily_bar(9, close="9.00")
    target_end = _daily_bar(10, close="8.775")
    request = _request(9, 10, ReturnCountWindow(requested_count=2, minimum_samples=1))
    result = build_percentage_return_z_score_result([a, b, target_start, target_end], request)
    assert result.value is None


def test_mixed_session_rejection():
    regular = _daily_bar(6, close="10.00", session="REGULAR")
    premarket = make_bar(
        source_record_id="rz-premarket-7", interval="1_DAY", session="PREMARKET",
        bar_start="2026-01-07T00:00:00-05:00", bar_end="2026-01-08T00:00:00-05:00", session_date="2026-01-07",
        publication_timestamp="2026-01-07T16:01:00-05:00", ingested_at="2026-01-07T21:02:00Z",
        high="1000.00", low="0.01", open="500.00", close="500.00",
    )
    target_start = _daily_bar(9, close="9.00", session="REGULAR")
    target_end = _daily_bar(10, close="8.775", session="REGULAR")
    request = _request(
        9, 10, ReturnCountWindow(requested_count=2, minimum_samples=1), session_scope=(BarSession.REGULAR,)
    )
    result = build_percentage_return_z_score_result([regular, premarket, target_start, target_end], request)
    assert premarket.observation_id not in result.input_observation_ids


def test_correction_before_and_after_availability():
    history = _history(MIXED_HISTORY)
    target_start = _daily_bar(9, close="9.00")
    target_end = _daily_bar(10, close="8.775")
    observations = [*history, target_start, target_end]
    before = _request(9, 10, WINDOW_2, as_of=datetime(2026, 1, 22, 0, 0, tzinfo=UTC))
    after = _request(9, 10, WINDOW_2, as_of=AS_OF)
    result_before = build_percentage_return_z_score_result(observations, before)
    result_after = build_percentage_return_z_score_result(observations, after)
    assert result_before.value == result_after.value == Decimal(0)


def test_cancellation_before_and_after_availability():
    history = _history([(6, "10.00"), (7, "12.00")])
    day8_original = _daily_bar(8, close="9.00", provider_record_id="rz-orig-cancel-8")
    day8_cancelled = _daily_bar(
        8, close="9.00", provider_record_id="rz-cancelled-8", source_record_id="rz-bar-8-cancelled",
        status="CANCELLED", revision_number=1, supersedes_provider_record_id="rz-orig-cancel-8",
        publication_timestamp="2026-01-23T09:00:00-05:00", ingested_at="2026-01-23T09:05:00Z",
    )
    target_start = _daily_bar(9, close="9.00")
    target_end = _daily_bar(10, close="8.775")
    observations = [*history, day8_original, day8_cancelled, target_start, target_end]
    before = _request(9, 10, WINDOW_2, as_of=datetime(2026, 1, 22, 0, 0, tzinfo=UTC))
    after = _request(9, 10, WINDOW_2, as_of=AS_OF)
    result_before = build_percentage_return_z_score_result(observations, before)
    result_after = build_percentage_return_z_score_result(observations, after)
    # Before cancellation: bars 6,7,8 (3 bars) -> 2 returns -> KNOWN_VALUE.
    assert result_before.quality.state is QualityState.KNOWN_VALUE
    # After cancellation: only bars 6,7 remain (2 bars) -> 1 return, below minimum_samples=2.
    assert result_after.quality.state is QualityState.UNAVAILABLE


def test_future_target_and_baseline_excluded():
    history = _history(MIXED_HISTORY)
    future = _daily_bar(15, close="500.00")
    target_start = _daily_bar(9, close="9.00")
    target_end = _daily_bar(10, close="8.775")
    result = build_percentage_return_z_score_result(
        [*history, future, target_start, target_end], _request(9, 10, WINDOW_2)
    )
    assert future.observation_id not in result.input_observation_ids


def test_input_reordering_invariance():
    history = _history(MIXED_HISTORY)
    target_start = _daily_bar(9, close="9.00")
    target_end = _daily_bar(10, close="8.775")
    request = _request(9, 10, WINDOW_2)
    forward = build_percentage_return_z_score_result([*history, target_start, target_end], request)
    backward = build_percentage_return_z_score_result(
        [target_end, target_start, *reversed(history)], request
    )
    assert forward.value == backward.value
    assert forward.deterministic_id == backward.deterministic_id


def test_exact_decimal_behavior():
    history = _history(MIXED_HISTORY)
    target_start = _daily_bar(9, close="9.00")
    target_end = _daily_bar(10, close="8.775")
    result = build_percentage_return_z_score_result(
        [*history, target_start, target_end], _request(9, 10, WINDOW_2)
    )
    assert isinstance(result.value, Decimal)


def test_stable_deterministic_id_and_serialized_output():
    from squeeze_core.metrics import normalized_metric_result_hash

    history = _history(MIXED_HISTORY)
    target_start = _daily_bar(9, close="9.00")
    target_end = _daily_bar(10, close="8.775")
    request = _request(9, 10, WINDOW_2)
    first = build_percentage_return_z_score_result([*history, target_start, target_end], request)
    second = build_percentage_return_z_score_result([*history, target_start, target_end], request)
    assert first.deterministic_id == second.deterministic_id
    assert normalized_metric_result_hash(first) == normalized_metric_result_hash(second)


def test_no_momentum_score_or_recommendation_fields():
    from squeeze_core.metrics import BaselineStatistics, NormalizedMetricResult

    for model in (NormalizedMetricResult, BaselineStatistics):
        field_names = set(model.model_fields)
        for needle in ("momentum", "score", "recommendation"):
            assert not any(needle in name for name in field_names)
