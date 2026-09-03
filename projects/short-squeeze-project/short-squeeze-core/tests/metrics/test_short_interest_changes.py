from datetime import UTC, datetime

from squeeze_core.contracts import AssetClass, QualityState
from squeeze_core.metrics import MetricName, MetricUnit
from squeeze_core.metrics.short_interest_changes import (
    ShortInterestComparisonRequest,
    build_short_interest_change_result,
)

from .conftest import make_short_interest, make_short_interest_records, short_interest_record

AS_OF = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
PROVIDER = "finra-provider-test"


def _request(starting, ending, **overrides):
    values = dict(
        symbol="TESTC",
        asset_class=AssetClass.EQUITY,
        as_of=AS_OF,
        provider=PROVIDER,
        starting_reporting_period=starting,
        ending_reporting_period=ending,
    )
    values.update(overrides)
    return ShortInterestComparisonRequest(**values)


def _pair(start_shares, end_shares, **kwargs):
    start = make_short_interest(
        source_record_id="si-start", settlement_date="2026-01-15", publication_date="2026-01-25",
        short_shares=str(start_shares),
    )
    end = make_short_interest(
        source_record_id="si-end", settlement_date="2026-01-31", publication_date="2026-02-10",
        short_shares=str(end_shares),
    )
    return start, end


def test_positive_absolute_change():
    start, end = _pair(1_000_000, 1_250_000)
    request = _request(start.payload.settlement_date, end.payload.settlement_date)
    result = build_short_interest_change_result(
        [start, end], request, MetricName.PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE
    )
    assert result.value == 250_000
    assert result.unit is MetricUnit.SHARES
    assert result.quality.state is QualityState.KNOWN_VALUE


def test_negative_absolute_change():
    start, end = _pair(1_250_000, 1_000_000)
    request = _request(start.payload.settlement_date, end.payload.settlement_date)
    result = build_short_interest_change_result(
        [start, end], request, MetricName.PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE
    )
    assert result.value == -250_000


def test_zero_absolute_change():
    start, end = _pair(1_000_000, 1_000_000)
    request = _request(start.payload.settlement_date, end.payload.settlement_date)
    result = build_short_interest_change_result(
        [start, end], request, MetricName.PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE
    )
    assert result.value == 0
    assert result.quality.state is QualityState.KNOWN_VALUE


def test_positive_percentage_change():
    start, end = _pair(1_000_000, 1_250_000)
    request = _request(start.payload.settlement_date, end.payload.settlement_date)
    result = build_short_interest_change_result(
        [start, end], request, MetricName.PUBLISHED_SHORT_INTEREST_PERCENTAGE_CHANGE
    )
    assert result.value == 25
    assert result.unit is MetricUnit.PERCENT


def test_negative_percentage_change():
    start, end = _pair(1_000_000, 750_000)
    request = _request(start.payload.settlement_date, end.payload.settlement_date)
    result = build_short_interest_change_result(
        [start, end], request, MetricName.PUBLISHED_SHORT_INTEREST_PERCENTAGE_CHANGE
    )
    assert result.value == -25


def test_zero_percentage_change():
    start, end = _pair(1_000_000, 1_000_000)
    request = _request(start.payload.settlement_date, end.payload.settlement_date)
    result = build_short_interest_change_result(
        [start, end], request, MetricName.PUBLISHED_SHORT_INTEREST_PERCENTAGE_CHANGE
    )
    assert result.value == 0


def test_zero_starting_denominator_invalidates_percentage_change():
    start, end = _pair(0, 500_000)
    request = _request(start.payload.settlement_date, end.payload.settlement_date)
    result = build_short_interest_change_result(
        [start, end], request, MetricName.PUBLISHED_SHORT_INTEREST_PERCENTAGE_CHANGE
    )
    assert result.value is None
    assert result.quality.state is QualityState.INVALID
    codes = {d.code.value for d in result.diagnostics}
    assert "SHORT_INTEREST_ZERO_START_DENOMINATOR" in codes


def test_zero_starting_denominator_is_valid_for_absolute_change():
    start, end = _pair(0, 500_000)
    request = _request(start.payload.settlement_date, end.payload.settlement_date)
    result = build_short_interest_change_result(
        [start, end], request, MetricName.PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE
    )
    assert result.value == 500_000
    assert result.quality.state is QualityState.KNOWN_VALUE


def test_missing_starting_value():
    start = make_short_interest(
        source_record_id="si-start", settlement_date="2026-01-15", publication_date="2026-01-25", short_shares=None
    )
    end = make_short_interest(
        source_record_id="si-end", settlement_date="2026-01-31", publication_date="2026-02-10", short_shares="500000"
    )
    request = _request(start.payload.settlement_date, end.payload.settlement_date)
    result = build_short_interest_change_result(
        [start, end], request, MetricName.PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE
    )
    assert result.value is None
    assert result.quality.state is QualityState.UNAVAILABLE
    assert any(d.code.value == "SHORT_INTEREST_MISSING_VALUE" for d in result.diagnostics)


def test_missing_ending_value():
    start = make_short_interest(
        source_record_id="si-start", settlement_date="2026-01-15", publication_date="2026-01-25", short_shares="500000"
    )
    end = make_short_interest(
        source_record_id="si-end", settlement_date="2026-01-31", publication_date="2026-02-10", short_shares=None
    )
    request = _request(start.payload.settlement_date, end.payload.settlement_date)
    result = build_short_interest_change_result(
        [start, end], request, MetricName.PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE
    )
    assert result.value is None
    assert result.quality.state is QualityState.UNAVAILABLE


def test_starting_record_unavailable_at_as_of():
    start = make_short_interest(
        source_record_id="si-start", settlement_date="2026-01-15", publication_date="2026-02-25"
    )
    end = make_short_interest(
        source_record_id="si-end", settlement_date="2026-01-31", publication_date="2026-01-10"
    )
    early_as_of = datetime(2026, 1, 15, tzinfo=UTC)
    request = _request(start.payload.settlement_date, end.payload.settlement_date, as_of=early_as_of)
    result = build_short_interest_change_result(
        [start, end], request, MetricName.PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE
    )
    assert result.value is None
    assert result.quality.state is QualityState.UNAVAILABLE


def test_publication_after_as_of_excludes_record():
    start = make_short_interest(
        source_record_id="si-start", settlement_date="2026-01-15", publication_date="2026-01-20",
        ingested_at="2026-01-21T00:00:00Z",
    )
    end = make_short_interest(
        source_record_id="si-end", settlement_date="2026-01-31", publication_date="2026-02-10",
        ingested_at="2026-02-11T00:00:00Z",
    )
    early_as_of = start.effective_timestamp
    request = _request(start.payload.settlement_date, end.payload.settlement_date, as_of=early_as_of)
    result = build_short_interest_change_result(
        [start, end], request, MetricName.PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE
    )
    assert result.value is None


def test_receipt_after_as_of_excludes_record():
    late_receipt = make_short_interest(
        source_record_id="si-late", settlement_date="2026-01-31", publication_date="2026-01-05",
        short_shares="500000", ingested_at="2026-05-01T00:00:00Z",
    )
    start = make_short_interest(source_record_id="si-start", settlement_date="2026-01-15", publication_date="2026-01-20")
    request = _request(start.payload.settlement_date, late_receipt.payload.settlement_date)
    result = build_short_interest_change_result(
        [start, late_receipt], request, MetricName.PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE
    )
    assert result.value is None


def test_reversed_periods_rejected():
    start, end = _pair(1_000_000, 1_250_000)
    request = _request(end.payload.settlement_date, start.payload.settlement_date)
    result = build_short_interest_change_result(
        [start, end], request, MetricName.PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE
    )
    assert result.value is None
    assert any(d.code.value == "PRESSURE_METRIC_START_AFTER_END" for d in result.diagnostics)


def test_same_period_supplied_twice_rejected():
    start, _ = _pair(1_000_000, 1_250_000)
    request = _request(start.payload.settlement_date, start.payload.settlement_date)
    result = build_short_interest_change_result(
        [start], request, MetricName.PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE
    )
    assert result.value is None
    assert any(d.code.value == "PRESSURE_METRIC_IDENTICAL_INPUT" for d in result.diagnostics)


def test_mixed_providers_excluded_by_explicit_single_provider_scope():
    start, end = _pair(1_000_000, 1_250_000)
    other_provider_end = make_short_interest(
        source_record_id="si-other", settlement_date="2026-01-31", publication_date="2026-02-10",
        short_shares="999999", provider="other-provider",
    )
    request = _request(start.payload.settlement_date, end.payload.settlement_date)
    result = build_short_interest_change_result(
        [start, other_provider_end], request, MetricName.PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE
    )
    assert result.value is None


def test_explicit_provider_selection():
    start, end = _pair(1_000_000, 1_250_000)
    request = _request(start.payload.settlement_date, end.payload.settlement_date, provider=PROVIDER)
    result = build_short_interest_change_result(
        [start, end], request, MetricName.PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE
    )
    assert result.provider == PROVIDER
    assert result.value == 250_000


def test_duplicate_records_do_not_change_result():
    start, end = _pair(1_000_000, 1_250_000)
    request = _request(start.payload.settlement_date, end.payload.settlement_date)
    result = build_short_interest_change_result(
        [start, start, end, end], request, MetricName.PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE
    )
    assert result.value == 250_000


def test_same_period_conflict_yields_conflicted_quality():
    records = [
        short_interest_record(
            source_record_id="conflict-a", settlement_date="2026-01-31", publication_date="2026-02-10",
            short_shares="1000000",
        ),
        short_interest_record(
            source_record_id="conflict-b", settlement_date="2026-01-31", publication_date="2026-02-10",
            short_shares="2000000",
        ),
    ]
    observations = make_short_interest_records(records)
    start = make_short_interest(source_record_id="si-start", settlement_date="2026-01-15", publication_date="2026-01-20")
    request = _request(start.payload.settlement_date, observations[0].payload.settlement_date)
    result = build_short_interest_change_result(
        [start, *observations], request, MetricName.PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE
    )
    assert result.value is None
    assert result.quality.state is QualityState.CONFLICTED


def test_out_of_order_inputs_are_deterministic():
    start, end = _pair(1_000_000, 1_250_000)
    request = _request(start.payload.settlement_date, end.payload.settlement_date)
    forward = build_short_interest_change_result(
        [start, end], request, MetricName.PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE
    )
    backward = build_short_interest_change_result(
        [end, start], request, MetricName.PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE
    )
    assert forward.deterministic_id == backward.deterministic_id
    assert forward.value == backward.value


def test_exact_decimal_behavior():
    start, end = _pair(3, 10)
    request = _request(start.payload.settlement_date, end.payload.settlement_date)
    result = build_short_interest_change_result(
        [start, end], request, MetricName.PUBLISHED_SHORT_INTEREST_PERCENTAGE_CHANGE
    )
    from decimal import Decimal

    assert result.value == (Decimal(7) / Decimal(3)) * 100


def test_age_metadata_present_on_both_sides():
    start, end = _pair(1_000_000, 1_250_000)
    request = _request(start.payload.settlement_date, end.payload.settlement_date)
    result = build_short_interest_change_result(
        [start, end], request, MetricName.PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE
    )
    assert result.starting_source_age is not None
    assert result.ending_source_age is not None
    assert result.starting_source_age.reporting_period_age_days is not None
    assert result.starting_source_age.availability_age_seconds >= 0
    assert result.ending_source_age.publication_lag_seconds is not None


def test_no_qualitative_pressure_label_on_model():
    field_names = set(build_short_interest_change_result.__annotations__)
    from squeeze_core.metrics import PressureMetricResult

    for needle in ("pressure", "score", "rank", "recommendation", "signal", "strong", "weak"):
        assert not any(needle in name.lower() for name in PressureMetricResult.model_fields)
