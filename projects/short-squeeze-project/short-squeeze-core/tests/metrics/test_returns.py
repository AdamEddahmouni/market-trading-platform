from datetime import UTC, datetime
from decimal import Decimal

import pytest

from squeeze_core.adapters.market_bars import BarInterval, BarSession
from squeeze_core.contracts import AssetClass, QualityState
from squeeze_core.metrics import (
    MetricDiagnosticCode,
    MetricName,
    ProviderScopeMode,
    ReturnRequest,
    build_return_result,
)
from squeeze_core.metrics.returns import compute_absolute_return, compute_percentage_return

from .conftest import bar_boundary, make_bar

AS_OF = datetime(2026, 1, 20, 22, 0, tzinfo=UTC)


def _daily_bar(day: int, *, close: str = "10.25", status: str = "COMPLETED", **overrides):
    values = {
        "source_record_id": f"bar-{day}",
        "bar_start": f"2026-01-{day:02d}T00:00:00-05:00",
        "bar_end": f"2026-01-{day + 1:02d}T00:00:00-05:00",
        "session_date": f"2026-01-{day:02d}",
        "publication_timestamp": f"2026-01-{day:02d}T16:01:00-05:00",
        "open": "1.00",
        "high": "1000.00",
        "low": "0.01",
        "close": close,
        "status": status,
    }
    values.update(overrides)
    return make_bar(**values)


def _request(start, end, **overrides) -> ReturnRequest:
    start_start, start_end = bar_boundary(start)
    end_start, end_end = bar_boundary(end)
    values = dict(
        symbol="TESTA",
        asset_class=AssetClass.EQUITY,
        as_of=AS_OF,
        source_interval=BarInterval.ONE_DAY,
        start_bar_start=start_start,
        start_bar_end=start_end,
        end_bar_start=end_start,
        end_bar_end=end_end,
    )
    values.update(overrides)
    return ReturnRequest(**values)


# --- pure formula unit tests (structurally unreachable-from-a-real-bar cases live here) ---


def test_compute_absolute_return_positive():
    value, code = compute_absolute_return(Decimal("10.00"), Decimal("12.50"))
    assert value == Decimal("2.50")
    assert code is None


def test_compute_absolute_return_negative():
    value, code = compute_absolute_return(Decimal("12.50"), Decimal("10.00"))
    assert value == Decimal("-2.50")


def test_compute_absolute_return_zero():
    value, code = compute_absolute_return(Decimal("10.00"), Decimal("10.00"))
    assert value == Decimal("0")


def test_compute_percentage_return_positive():
    value, code = compute_percentage_return(Decimal("10.00"), Decimal("12.50"))
    assert value == Decimal("25")
    assert code is None


def test_compute_percentage_return_negative():
    value, _ = compute_percentage_return(Decimal("12.50"), Decimal("10.00"))
    assert value == Decimal("-20")


def test_compute_percentage_return_zero():
    value, _ = compute_percentage_return(Decimal("10.00"), Decimal("10.00"))
    assert value == Decimal("0")


def test_compute_percentage_return_zero_denominator():
    value, code = compute_percentage_return(Decimal("0"), Decimal("10.00"))
    assert value is None
    assert code is MetricDiagnosticCode.METRIC_ZERO_DENOMINATOR


def test_compute_return_missing_start_price():
    value, code = compute_absolute_return(None, Decimal("10.00"))
    assert value is None
    assert code is MetricDiagnosticCode.METRIC_MISSING_START_PRICE


def test_compute_return_missing_end_price():
    value, code = compute_absolute_return(Decimal("10.00"), None)
    assert value is None
    assert code is MetricDiagnosticCode.METRIC_MISSING_END_PRICE


def test_exact_decimal_preservation_no_float_math():
    value, _ = compute_percentage_return(Decimal("10.10"), Decimal("10.25"))
    # (10.25 - 10.10) / 10.10 * 100, computed exactly in Decimal
    assert value == (Decimal("10.25") - Decimal("10.10")) / Decimal("10.10") * Decimal(100)
    assert isinstance(value, Decimal)


# --- integration tests through selection + build_return_result ---


def test_positive_absolute_return_end_to_end():
    start = _daily_bar(15, close="10.00")
    end = _daily_bar(16, close="12.50")
    result = build_return_result([start, end], _request(start, end), MetricName.ABSOLUTE_RETURN)
    assert result.value == Decimal("2.50")
    assert result.quality.state is QualityState.KNOWN_VALUE
    assert result.deterministic_id is not None


def test_negative_absolute_return_end_to_end():
    start = _daily_bar(15, close="12.50")
    end = _daily_bar(16, close="10.00")
    result = build_return_result([start, end], _request(start, end), MetricName.ABSOLUTE_RETURN)
    assert result.value == Decimal("-2.50")


def test_zero_absolute_return_end_to_end():
    start = _daily_bar(15, close="10.00")
    end = _daily_bar(16, close="10.00")
    result = build_return_result([start, end], _request(start, end), MetricName.ABSOLUTE_RETURN)
    assert result.value == Decimal("0")


def test_positive_percentage_return_end_to_end():
    start = _daily_bar(15, close="10.00")
    end = _daily_bar(16, close="12.50")
    result = build_return_result([start, end], _request(start, end), MetricName.PERCENTAGE_RETURN)
    assert result.value == Decimal("25")
    assert result.unit.value == "PERCENT"


def test_negative_percentage_return_end_to_end():
    start = _daily_bar(15, close="12.50")
    end = _daily_bar(16, close="10.00")
    result = build_return_result([start, end], _request(start, end), MetricName.PERCENTAGE_RETURN)
    assert result.value == Decimal("-20")


def test_zero_percentage_return_end_to_end():
    start = _daily_bar(15, close="10.00")
    end = _daily_bar(16, close="10.00")
    result = build_return_result([start, end], _request(start, end), MetricName.PERCENTAGE_RETURN)
    assert result.value == Decimal("0")


def test_start_bar_unavailable_at_as_of():
    start = _daily_bar(15, close="10.00", publication_timestamp="2026-01-25T16:01:00-05:00")
    end = _daily_bar(16, close="12.50")
    result = build_return_result([start, end], _request(start, end), MetricName.ABSOLUTE_RETURN)
    assert result.value is None
    assert result.quality.state is QualityState.UNAVAILABLE
    assert any(d.code is MetricDiagnosticCode.RETURN_START_BAR_NOT_FOUND for d in result.diagnostics)


def test_end_bar_unavailable_at_as_of():
    start = _daily_bar(15, close="10.00")
    end = _daily_bar(16, close="12.50", publication_timestamp="2026-01-25T16:01:00-05:00")
    result = build_return_result([start, end], _request(start, end), MetricName.ABSOLUTE_RETURN)
    assert result.value is None
    assert any(d.code is MetricDiagnosticCode.RETURN_END_BAR_NOT_FOUND for d in result.diagnostics)


def test_start_bar_partial_is_excluded():
    start = _daily_bar(15, close="10.00", status="PARTIAL")
    end = _daily_bar(16, close="12.50")
    result = build_return_result([start, end], _request(start, end), MetricName.ABSOLUTE_RETURN)
    assert result.value is None
    assert any(d.code is MetricDiagnosticCode.METRIC_PARTIAL_INPUT for d in result.diagnostics)


def test_end_bar_partial_is_excluded():
    start = _daily_bar(15, close="10.00")
    end = _daily_bar(16, close="12.50", status="PARTIAL")
    result = build_return_result([start, end], _request(start, end), MetricName.ABSOLUTE_RETURN)
    assert result.value is None
    assert any(d.code is MetricDiagnosticCode.METRIC_PARTIAL_INPUT for d in result.diagnostics)


def test_corrected_end_bar_before_and_after_correction_receipt():
    start = _daily_bar(15, close="10.00", ingested_at="2026-01-15T21:02:00Z")
    original = _daily_bar(16, close="12.00", provider_record_id="end-original", ingested_at="2026-01-16T21:02:00Z")
    corrected = _daily_bar(
        16,
        close="12.50",
        provider_record_id="end-corrected",
        source_record_id="bar-16-corrected",
        status="CORRECTED",
        revision_number=1,
        supersedes_provider_record_id="end-original",
        publication_timestamp="2026-01-18T09:00:00-05:00",
        ingested_at="2026-01-18T09:05:00Z",
    )
    observations = [start, original, corrected]

    before = _request(start, original, as_of=datetime(2026, 1, 17, 0, 0, tzinfo=UTC))
    after = _request(start, original, as_of=datetime(2026, 1, 20, 22, 0, tzinfo=UTC))

    result_before = build_return_result(observations, before, MetricName.ABSOLUTE_RETURN)
    result_after = build_return_result(observations, after, MetricName.ABSOLUTE_RETURN)

    assert result_before.value == Decimal("2.00")
    assert result_after.value == Decimal("2.50")

    # Recomputing "before" again is byte-identical (history is never mutated).
    result_before_again = build_return_result(observations, before, MetricName.ABSOLUTE_RETURN)
    assert result_before_again.deterministic_id == result_before.deterministic_id
    assert result_before_again.value == result_before.value


def test_cancelled_bar_before_and_after_cancellation_receipt():
    start = _daily_bar(15, close="10.00", ingested_at="2026-01-15T21:02:00Z")
    original = _daily_bar(16, close="12.00", provider_record_id="end-original-2", ingested_at="2026-01-16T21:02:00Z")
    cancelled = _daily_bar(
        16,
        close="12.00",
        provider_record_id="end-cancelled",
        source_record_id="bar-16-cancelled",
        status="CANCELLED",
        revision_number=1,
        supersedes_provider_record_id="end-original-2",
        publication_timestamp="2026-01-18T09:00:00-05:00",
        ingested_at="2026-01-18T09:05:00Z",
    )
    observations = [start, original, cancelled]

    before = _request(start, original, as_of=datetime(2026, 1, 17, 0, 0, tzinfo=UTC))
    after = _request(start, original, as_of=datetime(2026, 1, 20, 22, 0, tzinfo=UTC))

    result_before = build_return_result(observations, before, MetricName.ABSOLUTE_RETURN)
    result_after = build_return_result(observations, after, MetricName.ABSOLUTE_RETURN)

    assert result_before.value == Decimal("2.00")
    assert result_after.value is None
    assert any(d.code is MetricDiagnosticCode.METRIC_CANCELLED_INPUT for d in result_after.diagnostics)


def test_mixed_providers_without_explicit_provider_is_ambiguous():
    start = _daily_bar(15, close="10.00")
    end_a = _daily_bar(16, close="12.00", provider="ALPACA_SHAPED", source_record_id="bar-16-alpaca")
    end_b = _daily_bar(16, close="12.10", provider="SCHWAB_SHAPED", source_record_id="bar-16-schwab")
    result = build_return_result([start, end_a, end_b], _request(start, end_a), MetricName.ABSOLUTE_RETURN)
    assert result.value is None
    assert any(d.code is MetricDiagnosticCode.METRIC_AMBIGUOUS_PROVIDER for d in result.diagnostics)


def test_explicit_single_provider_selection_resolves_ambiguity():
    start = _daily_bar(15, close="10.00")
    end_a = _daily_bar(16, close="12.00", provider="ALPACA_SHAPED", source_record_id="bar-16-alpaca")
    end_b = _daily_bar(16, close="12.10", provider="SCHWAB_SHAPED", source_record_id="bar-16-schwab")
    result = build_return_result(
        [start, end_a, end_b], _request(start, end_a, provider="ALPACA_SHAPED"), MetricName.ABSOLUTE_RETURN
    )
    assert result.value == Decimal("2.00")


def test_mixed_interval_bar_is_not_selected():
    start = _daily_bar(15, close="10.00")
    minute_bar = make_bar(
        source_record_id="bar-16-minute",
        interval="1_MINUTE",
        bar_start="2026-01-16T09:30:00-05:00",
        bar_end="2026-01-16T09:31:00-05:00",
        session_date="2026-01-16",
        publication_timestamp="2026-01-16T09:31:01-05:00",
        open="1.00",
        high="1000.00",
        low="0.01",
        close="99.99",
    )
    request = ReturnRequest(
        symbol="TESTA",
        asset_class=AssetClass.EQUITY,
        as_of=AS_OF,
        source_interval=BarInterval.ONE_DAY,
        start_bar_start=bar_boundary(start)[0],
        start_bar_end=bar_boundary(start)[1],
        end_bar_start=bar_boundary(minute_bar)[0],
        end_bar_end=bar_boundary(minute_bar)[1],
    )
    result = build_return_result([start, minute_bar], request, MetricName.ABSOLUTE_RETURN)
    assert result.value is None
    assert any(d.code is MetricDiagnosticCode.RETURN_END_BAR_NOT_FOUND for d in result.diagnostics)


def test_mixed_session_bar_is_not_selected():
    start = _daily_bar(15, close="10.00")
    premarket_bar = make_bar(
        source_record_id="bar-16-premarket",
        interval="1_MINUTE",
        session="PREMARKET",
        bar_start="2026-01-16T08:00:00-05:00",
        bar_end="2026-01-16T08:01:00-05:00",
        session_date="2026-01-16",
        publication_timestamp="2026-01-16T08:01:01-05:00",
        open="1.00",
        high="1000.00",
        low="0.01",
        close="99.99",
    )
    request = ReturnRequest(
        symbol="TESTA",
        asset_class=AssetClass.EQUITY,
        as_of=AS_OF,
        source_interval=BarInterval.ONE_MINUTE,
        session_scope=(BarSession.REGULAR,),
        start_bar_start=bar_boundary(premarket_bar)[0],
        start_bar_end=bar_boundary(premarket_bar)[1],
        end_bar_start=bar_boundary(premarket_bar)[0],
        end_bar_end=bar_boundary(premarket_bar)[1],
    )
    result = build_return_result([premarket_bar], request, MetricName.ABSOLUTE_RETURN)
    assert result.value is None
    assert any(d.code is MetricDiagnosticCode.RETURN_START_BAR_NOT_FOUND for d in result.diagnostics)


def test_same_input_bar_used_twice_is_a_well_defined_zero_return():
    bar = _daily_bar(15, close="10.00")
    result = build_return_result([bar], _request(bar, bar), MetricName.ABSOLUTE_RETURN)
    assert result.value == Decimal("0")
    assert result.quality.state is QualityState.KNOWN_VALUE
    assert any(d.code is MetricDiagnosticCode.RETURN_IDENTICAL_INPUT_BAR for d in result.diagnostics)


def test_out_of_order_input_and_deterministic_reordering_invariance():
    start = _daily_bar(15, close="10.00")
    end = _daily_bar(16, close="12.50")
    forward = build_return_result([start, end], _request(start, end), MetricName.ABSOLUTE_RETURN)
    reversed_ = build_return_result([end, start], _request(start, end), MetricName.ABSOLUTE_RETURN)
    assert forward.value == reversed_.value
    assert forward.deterministic_id == reversed_.deterministic_id


def test_deterministic_id_stable_across_repeated_construction():
    start = _daily_bar(15, close="10.00")
    end = _daily_bar(16, close="12.50")
    first = build_return_result([start, end], _request(start, end), MetricName.ABSOLUTE_RETURN)
    second = build_return_result([start, end], _request(start, end), MetricName.ABSOLUTE_RETURN)
    assert first.deterministic_id == second.deterministic_id
