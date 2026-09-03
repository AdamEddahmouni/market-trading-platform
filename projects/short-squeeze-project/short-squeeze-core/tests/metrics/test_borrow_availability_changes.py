from datetime import UTC, datetime

from squeeze_core.contracts import AssetClass, QualityState
from squeeze_core.metrics import MetricName, MetricUnit
from squeeze_core.metrics.borrow_availability_changes import (
    BorrowAvailabilityComparisonRequest,
    build_borrow_availability_change_result,
)

from .conftest import borrow_record, make_borrow_availability, make_borrow_records

AS_OF = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
PROVIDER = "ibkr-provider-test"


def _request(starting, ending, **overrides):
    values = dict(
        symbol="TESTC", asset_class=AssetClass.EQUITY, as_of=AS_OF, provider=PROVIDER,
        starting_effective_timestamp=starting, ending_effective_timestamp=ending,
    )
    values.update(overrides)
    return BorrowAvailabilityComparisonRequest(**values)


def _pair(start_available, end_available):
    start = make_borrow_availability(
        source_record_id="avail-start", provider_timestamp="2026-01-10T00:00:00Z", available_shares=str(start_available),
    )
    end = make_borrow_availability(
        source_record_id="avail-end", provider_timestamp="2026-01-20T00:00:00Z", available_shares=str(end_available),
    )
    return start, end


def test_positive_absolute_change():
    start, end = _pair(100_000, 150_000)
    request = _request(start.effective_timestamp, end.effective_timestamp)
    result = build_borrow_availability_change_result(
        [start, end], request, MetricName.BORROW_AVAILABILITY_ABSOLUTE_CHANGE
    )
    assert result.value == 50_000
    assert result.unit is MetricUnit.SHARES
    assert result.quality.state is QualityState.KNOWN_VALUE


def test_negative_absolute_change():
    start, end = _pair(150_000, 100_000)
    request = _request(start.effective_timestamp, end.effective_timestamp)
    result = build_borrow_availability_change_result(
        [start, end], request, MetricName.BORROW_AVAILABILITY_ABSOLUTE_CHANGE
    )
    assert result.value == -50_000


def test_zero_absolute_change():
    start, end = _pair(100_000, 100_000)
    request = _request(start.effective_timestamp, end.effective_timestamp)
    result = build_borrow_availability_change_result(
        [start, end], request, MetricName.BORROW_AVAILABILITY_ABSOLUTE_CHANGE
    )
    assert result.value == 0


def test_positive_percentage_change():
    start, end = _pair(100_000, 150_000)
    request = _request(start.effective_timestamp, end.effective_timestamp)
    result = build_borrow_availability_change_result(
        [start, end], request, MetricName.BORROW_AVAILABILITY_PERCENTAGE_CHANGE
    )
    assert result.value == 50
    assert result.unit is MetricUnit.PERCENT


def test_negative_percentage_change():
    start, end = _pair(100_000, 75_000)
    request = _request(start.effective_timestamp, end.effective_timestamp)
    result = build_borrow_availability_change_result(
        [start, end], request, MetricName.BORROW_AVAILABILITY_PERCENTAGE_CHANGE
    )
    assert result.value == -25


def test_zero_percentage_change():
    start, end = _pair(100_000, 100_000)
    request = _request(start.effective_timestamp, end.effective_timestamp)
    result = build_borrow_availability_change_result(
        [start, end], request, MetricName.BORROW_AVAILABILITY_PERCENTAGE_CHANGE
    )
    assert result.value == 0


def test_zero_starting_denominator_invalidates_percentage_change():
    start, end = _pair(0, 50_000)
    request = _request(start.effective_timestamp, end.effective_timestamp)
    result = build_borrow_availability_change_result(
        [start, end], request, MetricName.BORROW_AVAILABILITY_PERCENTAGE_CHANGE
    )
    assert result.value is None
    assert result.quality.state is QualityState.INVALID
    assert any(d.code.value == "BORROW_AVAILABILITY_ZERO_START_DENOMINATOR" for d in result.diagnostics)


def test_missing_starting_availability():
    start = make_borrow_availability(
        source_record_id="avail-start", provider_timestamp="2026-01-10T00:00:00Z", available_shares=None
    )
    end = make_borrow_availability(
        source_record_id="avail-end", provider_timestamp="2026-01-20T00:00:00Z", available_shares="50000"
    )
    request = _request(start.effective_timestamp, end.effective_timestamp)
    result = build_borrow_availability_change_result(
        [start, end], request, MetricName.BORROW_AVAILABILITY_ABSOLUTE_CHANGE
    )
    assert result.value is None
    assert any(d.code.value == "BORROW_AVAILABILITY_MISSING_VALUE" for d in result.diagnostics)


def test_missing_ending_availability():
    start = make_borrow_availability(
        source_record_id="avail-start", provider_timestamp="2026-01-10T00:00:00Z", available_shares="50000"
    )
    end = make_borrow_availability(
        source_record_id="avail-end", provider_timestamp="2026-01-20T00:00:00Z", available_shares=None
    )
    request = _request(start.effective_timestamp, end.effective_timestamp)
    result = build_borrow_availability_change_result(
        [start, end], request, MetricName.BORROW_AVAILABILITY_ABSOLUTE_CHANGE
    )
    assert result.value is None


def test_explicit_zero_availability_is_known_value():
    start, end = _pair(0, 50_000)
    request = _request(start.effective_timestamp, end.effective_timestamp)
    result = build_borrow_availability_change_result(
        [start, end], request, MetricName.BORROW_AVAILABILITY_ABSOLUTE_CHANGE
    )
    assert result.value == 50_000
    assert result.quality.state is QualityState.KNOWN_VALUE


def test_mixed_providers_excluded():
    start, _ = _pair(100_000, 150_000)
    other = make_borrow_availability(
        source_record_id="avail-other", provider_timestamp="2026-01-20T00:00:00Z", available_shares="1", provider="other-borrow",
    )
    request = _request(start.effective_timestamp, other.effective_timestamp)
    result = build_borrow_availability_change_result(
        [start, other], request, MetricName.BORROW_AVAILABILITY_ABSOLUTE_CHANGE
    )
    assert result.value is None


def test_mixed_scope_has_no_scope_field_to_mix():
    # IBKR borrow observations carry no venue/scope field at all.
    from squeeze_core.contracts import BorrowAvailabilityPayload

    assert "scope" not in BorrowAvailabilityPayload.model_fields
    assert "venue" not in BorrowAvailabilityPayload.model_fields


def test_starting_record_unavailable_at_as_of():
    start, end = _pair(100_000, 150_000)
    request = _request(start.effective_timestamp, end.effective_timestamp, as_of=datetime(2026, 1, 5, tzinfo=UTC))
    result = build_borrow_availability_change_result(
        [start, end], request, MetricName.BORROW_AVAILABILITY_ABSOLUTE_CHANGE
    )
    assert result.value is None


def test_out_of_order_inputs_deterministic():
    start, end = _pair(100_000, 150_000)
    request = _request(start.effective_timestamp, end.effective_timestamp)
    forward = build_borrow_availability_change_result(
        [start, end], request, MetricName.BORROW_AVAILABILITY_ABSOLUTE_CHANGE
    )
    backward = build_borrow_availability_change_result(
        [end, start], request, MetricName.BORROW_AVAILABILITY_ABSOLUTE_CHANGE
    )
    assert forward.deterministic_id == backward.deterministic_id


def test_duplicate_record_does_not_change_result():
    start, end = _pair(100_000, 150_000)
    request = _request(start.effective_timestamp, end.effective_timestamp)
    result = build_borrow_availability_change_result(
        [start, start, end], request, MetricName.BORROW_AVAILABILITY_ABSOLUTE_CHANGE
    )
    assert result.value == 50_000


def test_conflict_record_yields_conflicted_quality():
    records = [
        borrow_record(source_record_id="avail-a", provider_timestamp="2026-01-20T00:00:00Z", available_shares="10000"),
        borrow_record(source_record_id="avail-b", provider_timestamp="2026-01-20T00:00:00Z", available_shares="20000"),
    ]
    observations = make_borrow_records(records)
    conflicted = [o for o in observations if o.event_type.value == "BORROW_AVAILABILITY"]
    start = make_borrow_availability(source_record_id="avail-start", provider_timestamp="2026-01-10T00:00:00Z", available_shares="5000")
    request = _request(start.effective_timestamp, conflicted[0].effective_timestamp)
    result = build_borrow_availability_change_result(
        [start, *conflicted], request, MetricName.BORROW_AVAILABILITY_ABSOLUTE_CHANGE
    )
    assert result.value is None
    assert result.quality.state is QualityState.CONFLICTED


def test_exact_arithmetic():
    start, end = _pair(3, 10)
    request = _request(start.effective_timestamp, end.effective_timestamp)
    result = build_borrow_availability_change_result(
        [start, end], request, MetricName.BORROW_AVAILABILITY_PERCENTAGE_CHANGE
    )
    from decimal import Decimal

    assert result.value == (Decimal(7) / Decimal(3)) * 100


def test_stable_deterministic_result():
    start, end = _pair(100_000, 150_000)
    request = _request(start.effective_timestamp, end.effective_timestamp)
    from squeeze_core.metrics import pressure_metric_result_hash

    first = build_borrow_availability_change_result([start, end], request, MetricName.BORROW_AVAILABILITY_ABSOLUTE_CHANGE)
    second = build_borrow_availability_change_result([start, end], request, MetricName.BORROW_AVAILABILITY_ABSOLUTE_CHANGE)
    assert pressure_metric_result_hash(first) == pressure_metric_result_hash(second)


def test_no_tightening_or_loosening_classification():
    import inspect

    from squeeze_core.metrics import borrow_availability_changes

    source = inspect.getsource(borrow_availability_changes)
    for needle in ("tighten", "loosen", "hard_to_borrow"):
        assert needle not in source.lower()
