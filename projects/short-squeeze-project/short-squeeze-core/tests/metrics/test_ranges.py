from datetime import UTC, datetime
from decimal import Decimal

from squeeze_core.adapters.market_bars import BarInterval
from squeeze_core.contracts import AssetClass, QualityState
from squeeze_core.metrics import MetricDiagnosticCode, MetricName, RangeRequest, build_range_result
from squeeze_core.metrics.ranges import compute_absolute_range, compute_percentage_range

from .conftest import bar_boundary, make_bar

AS_OF = datetime(2026, 1, 20, 22, 0, tzinfo=UTC)


def _bar(*, high="10.50", low="9.90", status="COMPLETED", **overrides):
    values = {
        "source_record_id": "bar-range-1",
        "bar_start": "2026-01-15T00:00:00-05:00",
        "bar_end": "2026-01-16T00:00:00-05:00",
        "session_date": "2026-01-15",
        "publication_timestamp": "2026-01-15T16:01:00-05:00",
        "high": high,
        "low": low,
        "status": status,
    }
    values.update(overrides)
    return make_bar(**values)


def _request(bar, **overrides) -> RangeRequest:
    start, end = bar_boundary(bar)
    values = dict(
        symbol="TESTA",
        asset_class=AssetClass.EQUITY,
        as_of=AS_OF,
        source_interval=BarInterval.ONE_DAY,
        target_bar_start=start,
        target_bar_end=end,
    )
    values.update(overrides)
    return RangeRequest(**values)


def test_compute_absolute_range():
    assert compute_absolute_range(Decimal("10.50"), Decimal("9.90")) == Decimal("0.60")


def test_compute_absolute_range_zero():
    assert compute_absolute_range(Decimal("10.00"), Decimal("10.00")) == Decimal("0")


def test_compute_percentage_range():
    value, code = compute_percentage_range(Decimal("11.00"), Decimal("10.00"))
    assert value == Decimal("10")
    assert code is None


def test_compute_percentage_range_zero_denominator_is_unreachable_from_a_real_bar_but_guarded():
    # BarPayload.low requires gt=0, so this path can never be hit via a normalized bar; the
    # pure formula still guards it defensively and is unit-tested directly here.
    value, code = compute_percentage_range(Decimal("11.00"), Decimal("0"))
    assert value is None
    assert code is MetricDiagnosticCode.RANGE_ZERO_DENOMINATOR


def test_positive_absolute_range_end_to_end():
    bar = _bar(high="10.50", low="9.90")
    result = build_range_result([bar], _request(bar), MetricName.ABSOLUTE_BAR_RANGE)
    assert result.value == Decimal("0.60")
    assert result.quality.state is QualityState.KNOWN_VALUE


def test_zero_absolute_range_end_to_end():
    bar = _bar(high="10.00", low="10.00", close="10.00", open="10.00")
    result = build_range_result([bar], _request(bar), MetricName.ABSOLUTE_BAR_RANGE)
    assert result.value == Decimal("0")


def test_positive_percentage_range_end_to_end():
    bar = _bar(high="11.00", low="10.00", open="10.00", close="10.50")
    result = build_range_result([bar], _request(bar), MetricName.PERCENTAGE_BAR_RANGE)
    assert result.value == Decimal("10")
    assert result.unit.value == "PERCENT"


def test_partial_bar_is_unsupported():
    bar = _bar(status="PARTIAL")
    result = build_range_result([bar], _request(bar), MetricName.ABSOLUTE_BAR_RANGE)
    assert result.value is None
    assert result.quality.state is QualityState.UNAVAILABLE
    assert any(d.code is MetricDiagnosticCode.RANGE_PARTIAL_BAR_UNSUPPORTED for d in result.diagnostics)


def test_completed_bar_is_the_baseline_positive_case():
    bar = _bar(status="COMPLETED")
    result = build_range_result([bar], _request(bar), MetricName.ABSOLUTE_BAR_RANGE)
    assert result.quality.state is QualityState.KNOWN_VALUE


def test_corrected_bar_before_and_after_correction_receipt():
    original = _bar(high="10.50", low="9.90", provider_record_id="range-original", ingested_at="2026-01-15T21:02:00Z")
    corrected = _bar(
        high="11.00",
        low="9.80",
        provider_record_id="range-corrected",
        source_record_id="bar-range-corrected",
        status="CORRECTED",
        revision_number=1,
        supersedes_provider_record_id="range-original",
        publication_timestamp="2026-01-18T09:00:00-05:00",
        ingested_at="2026-01-18T09:05:00Z",
    )
    observations = [original, corrected]

    before = _request(original, as_of=datetime(2026, 1, 17, 0, 0, tzinfo=UTC))
    after = _request(original, as_of=datetime(2026, 1, 20, 22, 0, tzinfo=UTC))

    result_before = build_range_result(observations, before, MetricName.ABSOLUTE_BAR_RANGE)
    result_after = build_range_result(observations, after, MetricName.ABSOLUTE_BAR_RANGE)

    assert result_before.value == Decimal("0.60")
    assert result_after.value == Decimal("1.20")


def test_cancelled_bar_excluded():
    bar = _bar(status="CANCELLED")
    result = build_range_result([bar], _request(bar), MetricName.ABSOLUTE_BAR_RANGE)
    assert result.value is None
    assert any(d.code is MetricDiagnosticCode.METRIC_CANCELLED_INPUT for d in result.diagnostics)


def test_mixed_provider_ambiguity():
    a = _bar(high="10.50", low="9.90", provider="ALPACA_SHAPED", source_record_id="range-a")
    b = _bar(high="10.60", low="9.80", provider="SCHWAB_SHAPED", source_record_id="range-b")
    result = build_range_result([a, b], _request(a), MetricName.ABSOLUTE_BAR_RANGE)
    assert result.value is None
    assert any(d.code is MetricDiagnosticCode.METRIC_AMBIGUOUS_PROVIDER for d in result.diagnostics)


def test_exact_decimal_precision():
    bar = _bar(high="10.503", low="9.901", open="10.00", close="10.20")
    result = build_range_result([bar], _request(bar), MetricName.ABSOLUTE_BAR_RANGE)
    assert result.value == Decimal("0.602")


def test_unknown_session():
    bar = _bar(session="UNKNOWN")
    result = build_range_result([bar], _request(bar), MetricName.ABSOLUTE_BAR_RANGE)
    assert result.quality.state is QualityState.KNOWN_VALUE


def test_daily_bar_range():
    bar = _bar(interval="1_DAY")
    result = build_range_result([bar], _request(bar, source_interval=BarInterval.ONE_DAY), MetricName.ABSOLUTE_BAR_RANGE)
    assert result.quality.state is QualityState.KNOWN_VALUE


def test_intraday_bar_range():
    bar = make_bar(
        source_record_id="bar-range-intraday",
        interval="1_MINUTE",
        bar_start="2026-01-15T09:30:00-05:00",
        bar_end="2026-01-15T09:31:00-05:00",
        session_date="2026-01-15",
        publication_timestamp="2026-01-15T09:31:01-05:00",
        high="10.30",
        low="10.00",
    )
    request = RangeRequest(
        symbol="TESTA",
        asset_class=AssetClass.EQUITY,
        as_of=AS_OF,
        source_interval=BarInterval.ONE_MINUTE,
        target_bar_start=bar_boundary(bar)[0],
        target_bar_end=bar_boundary(bar)[1],
    )
    result = build_range_result([bar], request, MetricName.ABSOLUTE_BAR_RANGE)
    assert result.value == Decimal("0.30")


def test_deterministic_repeated_output():
    bar = _bar()
    request = _request(bar)
    first = build_range_result([bar], request, MetricName.ABSOLUTE_BAR_RANGE)
    second = build_range_result([bar], request, MetricName.ABSOLUTE_BAR_RANGE)
    assert first.deterministic_id == second.deterministic_id
    assert first.value == second.value
