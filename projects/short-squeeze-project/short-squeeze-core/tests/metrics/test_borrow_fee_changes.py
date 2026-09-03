from datetime import UTC, datetime

from squeeze_core.contracts import AssetClass, QualityState
from squeeze_core.metrics import MetricName, MetricUnit
from squeeze_core.metrics.borrow_fee_changes import (
    BorrowComparisonRequest,
    build_borrow_fee_change_result,
)

from .conftest import borrow_record, make_borrow_fee, make_borrow_records

AS_OF = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
PROVIDER = "ibkr-provider-test"


def _request(starting, ending, **overrides):
    values = dict(
        symbol="TESTC", asset_class=AssetClass.EQUITY, as_of=AS_OF, provider=PROVIDER,
        starting_effective_timestamp=starting, ending_effective_timestamp=ending,
    )
    values.update(overrides)
    return BorrowComparisonRequest(**values)


def _pair(start_fee, end_fee, **kwargs):
    start = make_borrow_fee(
        source_record_id="fee-start", provider_timestamp="2026-01-10T00:00:00Z", fee_rate=str(start_fee),
    )
    end = make_borrow_fee(
        source_record_id="fee-end", provider_timestamp="2026-01-20T00:00:00Z", fee_rate=str(end_fee),
    )
    return start, end


def test_positive_absolute_percentage_point_change():
    start, end = _pair(5.0, 8.0)
    request = _request(start.effective_timestamp, end.effective_timestamp)
    result = build_borrow_fee_change_result([start, end], request, MetricName.BORROW_FEE_ABSOLUTE_CHANGE)
    assert result.value == 3
    assert result.unit is MetricUnit.PERCENTAGE_POINTS
    assert result.quality.state is QualityState.KNOWN_VALUE


def test_negative_absolute_percentage_point_change():
    start, end = _pair(8.0, 5.0)
    request = _request(start.effective_timestamp, end.effective_timestamp)
    result = build_borrow_fee_change_result([start, end], request, MetricName.BORROW_FEE_ABSOLUTE_CHANGE)
    assert result.value == -3


def test_zero_absolute_change():
    start, end = _pair(5.0, 5.0)
    request = _request(start.effective_timestamp, end.effective_timestamp)
    result = build_borrow_fee_change_result([start, end], request, MetricName.BORROW_FEE_ABSOLUTE_CHANGE)
    assert result.value == 0


def test_positive_relative_percentage_change():
    start, end = _pair(4.0, 5.0)
    request = _request(start.effective_timestamp, end.effective_timestamp)
    result = build_borrow_fee_change_result(
        [start, end], request, MetricName.BORROW_FEE_RELATIVE_PERCENTAGE_CHANGE
    )
    assert result.value == 25
    assert result.unit is MetricUnit.PERCENT


def test_negative_relative_percentage_change():
    start, end = _pair(5.0, 4.0)
    request = _request(start.effective_timestamp, end.effective_timestamp)
    result = build_borrow_fee_change_result(
        [start, end], request, MetricName.BORROW_FEE_RELATIVE_PERCENTAGE_CHANGE
    )
    assert result.value == -20


def test_zero_relative_percentage_change():
    start, end = _pair(5.0, 5.0)
    request = _request(start.effective_timestamp, end.effective_timestamp)
    result = build_borrow_fee_change_result(
        [start, end], request, MetricName.BORROW_FEE_RELATIVE_PERCENTAGE_CHANGE
    )
    assert result.value == 0


def test_zero_starting_denominator_invalidates_relative_change():
    start, end = _pair(0.0, 5.0)
    request = _request(start.effective_timestamp, end.effective_timestamp)
    result = build_borrow_fee_change_result(
        [start, end], request, MetricName.BORROW_FEE_RELATIVE_PERCENTAGE_CHANGE
    )
    assert result.value is None
    assert result.quality.state is QualityState.INVALID
    assert any(d.code.value == "BORROW_FEE_ZERO_START_DENOMINATOR" for d in result.diagnostics)


def test_missing_starting_fee():
    start = make_borrow_fee(source_record_id="fee-start", provider_timestamp="2026-01-10T00:00:00Z", fee_rate=None)
    end = make_borrow_fee(source_record_id="fee-end", provider_timestamp="2026-01-20T00:00:00Z", fee_rate="5.0")
    request = _request(start.effective_timestamp, end.effective_timestamp)
    result = build_borrow_fee_change_result([start, end], request, MetricName.BORROW_FEE_ABSOLUTE_CHANGE)
    assert result.value is None
    assert any(d.code.value == "BORROW_FEE_MISSING_VALUE" for d in result.diagnostics)


def test_missing_ending_fee():
    start = make_borrow_fee(source_record_id="fee-start", provider_timestamp="2026-01-10T00:00:00Z", fee_rate="5.0")
    end = make_borrow_fee(source_record_id="fee-end", provider_timestamp="2026-01-20T00:00:00Z", fee_rate=None)
    request = _request(start.effective_timestamp, end.effective_timestamp)
    result = build_borrow_fee_change_result([start, end], request, MetricName.BORROW_FEE_ABSOLUTE_CHANGE)
    assert result.value is None


def test_explicit_zero_fee_is_known_value():
    start, end = _pair(0.0, 5.0)
    request = _request(start.effective_timestamp, end.effective_timestamp)
    result = build_borrow_fee_change_result([start, end], request, MetricName.BORROW_FEE_ABSOLUTE_CHANGE)
    assert result.value == 5
    assert result.quality.state is QualityState.KNOWN_VALUE


def test_mixed_providers_excluded():
    start, end = _pair(5.0, 8.0)
    other = make_borrow_fee(
        source_record_id="fee-other", provider_timestamp="2026-01-20T00:00:00Z", fee_rate="9.0", provider="other-borrow",
    )
    request = _request(start.effective_timestamp, other.effective_timestamp)
    result = build_borrow_fee_change_result([start, other], request, MetricName.BORROW_FEE_ABSOLUTE_CHANGE)
    assert result.value is None


def test_percentage_vs_percentage_point_distinction():
    start, end = _pair(4.0, 5.0)
    request = _request(start.effective_timestamp, end.effective_timestamp)
    absolute = build_borrow_fee_change_result([start, end], request, MetricName.BORROW_FEE_ABSOLUTE_CHANGE)
    relative = build_borrow_fee_change_result(
        [start, end], request, MetricName.BORROW_FEE_RELATIVE_PERCENTAGE_CHANGE
    )
    assert absolute.unit is MetricUnit.PERCENTAGE_POINTS
    assert relative.unit is MetricUnit.PERCENT
    assert absolute.value == 1
    assert relative.value == 25


def test_starting_record_unavailable_at_as_of():
    start, end = _pair(5.0, 8.0)
    request = _request(start.effective_timestamp, end.effective_timestamp, as_of=datetime(2026, 1, 5, tzinfo=UTC))
    result = build_borrow_fee_change_result([start, end], request, MetricName.BORROW_FEE_ABSOLUTE_CHANGE)
    assert result.value is None


def test_out_of_order_inputs_deterministic():
    start, end = _pair(5.0, 8.0)
    request = _request(start.effective_timestamp, end.effective_timestamp)
    forward = build_borrow_fee_change_result([start, end], request, MetricName.BORROW_FEE_ABSOLUTE_CHANGE)
    backward = build_borrow_fee_change_result([end, start], request, MetricName.BORROW_FEE_ABSOLUTE_CHANGE)
    assert forward.deterministic_id == backward.deterministic_id


def test_duplicate_record_does_not_change_result():
    start, end = _pair(5.0, 8.0)
    request = _request(start.effective_timestamp, end.effective_timestamp)
    result = build_borrow_fee_change_result([start, start, end], request, MetricName.BORROW_FEE_ABSOLUTE_CHANGE)
    assert result.value == 3


def test_conflict_record_yields_conflicted_quality():
    records = [
        borrow_record(source_record_id="fee-a", provider_timestamp="2026-01-20T00:00:00Z", fee_rate="5.0"),
        borrow_record(source_record_id="fee-b", provider_timestamp="2026-01-20T00:00:00Z", fee_rate="9.0"),
    ]
    observations = make_borrow_records(records)
    conflicted = [o for o in observations if o.event_type.value == "BORROW_FEE"]
    start = make_borrow_fee(source_record_id="fee-start", provider_timestamp="2026-01-10T00:00:00Z", fee_rate="4.0")
    request = _request(start.effective_timestamp, conflicted[0].effective_timestamp)
    result = build_borrow_fee_change_result([start, *conflicted], request, MetricName.BORROW_FEE_ABSOLUTE_CHANGE)
    assert result.value is None
    assert result.quality.state is QualityState.CONFLICTED


def test_exact_decimal_behavior():
    start, end = _pair("3.0", "10.0")
    request = _request(start.effective_timestamp, end.effective_timestamp)
    result = build_borrow_fee_change_result(
        [start, end], request, MetricName.BORROW_FEE_RELATIVE_PERCENTAGE_CHANGE
    )
    from decimal import Decimal

    assert result.value == (Decimal(7) / Decimal(3)) * 100


def test_stable_deterministic_result():
    start, end = _pair(5.0, 8.0)
    request = _request(start.effective_timestamp, end.effective_timestamp)
    from squeeze_core.metrics import pressure_metric_result_hash

    first = build_borrow_fee_change_result([start, end], request, MetricName.BORROW_FEE_ABSOLUTE_CHANGE)
    second = build_borrow_fee_change_result([start, end], request, MetricName.BORROW_FEE_ABSOLUTE_CHANGE)
    assert pressure_metric_result_hash(first) == pressure_metric_result_hash(second)


def test_no_hard_to_borrow_classification_anywhere():
    import inspect

    from squeeze_core.metrics import borrow_fee_changes

    source = inspect.getsource(borrow_fee_changes)
    assert "hard_to_borrow" not in source
    from squeeze_core.metrics import PressureMetricResult

    assert "hard_to_borrow" not in PressureMetricResult.model_fields
