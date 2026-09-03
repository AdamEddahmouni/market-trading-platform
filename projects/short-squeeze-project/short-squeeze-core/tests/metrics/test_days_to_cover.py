from datetime import UTC, datetime
from decimal import Decimal

from squeeze_core.adapters.market_bars import BarInterval
from squeeze_core.contracts import AssetClass, QualityState
from squeeze_core.metrics import MetricUnit, TrailingWindow
from squeeze_core.metrics.days_to_cover import (
    DaysToCoverRequest,
    build_days_to_cover_components,
    build_days_to_cover_result,
)

from .conftest import make_bar, make_short_interest

AS_OF = datetime(2026, 2, 20, 22, 0, tzinfo=UTC)
SI_PROVIDER = "finra-provider-test"
VOL_PROVIDER = "SIM-VOLUME-PROVIDER"


def _daily_bar(day: int, *, volume="500000", **overrides):
    values = {
        "source_record_id": f"dtc-bar-{day}",
        "symbol": "TESTC",
        "provider": VOL_PROVIDER,
        "bar_start": f"2026-02-{day:02d}T00:00:00Z",
        "bar_end": f"2026-02-{day + 1:02d}T00:00:00Z",
        "session_date": f"2026-02-{day:02d}",
        "timezone": "UTC",
        "publication_timestamp": f"2026-02-{day:02d}T20:01:00Z",
        "ingested_at": f"2026-02-{day:02d}T21:02:00Z",
        "high": "1000.00",
        "low": "0.01",
        "open": "10.00",
        "close": "10.00",
        "volume": volume,
    }
    values.update(overrides)
    return make_bar(**values)


def _short_interest(shares="1250000", reporting_period="2026-01-31", **overrides):
    return make_short_interest(
        settlement_date=reporting_period, publication_date="2026-02-10", short_shares=shares, **overrides
    )


def _request(reporting_period, window: TrailingWindow, **overrides) -> DaysToCoverRequest:
    values = dict(
        symbol="TESTC",
        asset_class=AssetClass.EQUITY,
        as_of=AS_OF,
        short_interest_provider=SI_PROVIDER,
        short_interest_reporting_period=reporting_period,
        volume_provider=VOL_PROVIDER,
        volume_interval=BarInterval.ONE_DAY,
        volume_window=window,
    )
    values.update(overrides)
    return DaysToCoverRequest(**values)


def test_three_sample_days_to_cover():
    bars = [_daily_bar(d, volume="500000") for d in (10, 11, 12)]
    short_interest = _short_interest("1250000")
    window = TrailingWindow(requested_count=3, minimum_samples=3)
    request = _request(short_interest.payload.settlement_date, window)
    result = build_days_to_cover_result([short_interest, *bars], request)
    assert result.value == Decimal(1250000) / Decimal(500000)
    assert result.unit is MetricUnit.DAYS
    assert result.quality.state is QualityState.KNOWN_VALUE


def test_five_sample_days_to_cover():
    bars = [_daily_bar(d, volume=str(v)) for d, v in zip((10, 11, 12, 13, 14), (400000, 500000, 600000, 500000, 500000))]
    short_interest = _short_interest("2500000")
    window = TrailingWindow(requested_count=5, minimum_samples=5)
    request = _request(short_interest.payload.settlement_date, window)
    result = build_days_to_cover_result([short_interest, *bars], request)
    mean_volume = Decimal(400000 + 500000 + 600000 + 500000 + 500000) / Decimal(5)
    assert result.value == Decimal(2500000) / mean_volume


def test_exact_decimal_division():
    bars = [_daily_bar(d, volume="333333") for d in (10, 11, 12)]
    short_interest = _short_interest("1000000")
    window = TrailingWindow(requested_count=3, minimum_samples=3)
    request = _request(short_interest.payload.settlement_date, window)
    result = build_days_to_cover_result([short_interest, *bars], request)
    assert result.value == Decimal(1000000) / Decimal(333333)


def test_zero_volume_baseline():
    bars = [_daily_bar(d, volume="0") for d in (10, 11, 12)]
    short_interest = _short_interest("1000000")
    window = TrailingWindow(requested_count=3, minimum_samples=3)
    request = _request(short_interest.payload.settlement_date, window)
    result = build_days_to_cover_result([short_interest, *bars], request)
    assert result.value is None
    assert result.quality.state is QualityState.INVALID
    assert any(d.code.value == "DAYS_TO_COVER_ZERO_VOLUME_BASELINE" for d in result.diagnostics)


def test_missing_volume_baseline():
    short_interest = _short_interest("1000000")
    window = TrailingWindow(requested_count=3, minimum_samples=3)
    request = _request(short_interest.payload.settlement_date, window)
    result = build_days_to_cover_result([short_interest], request)
    assert result.value is None
    assert result.quality.state is QualityState.UNAVAILABLE
    assert any(d.code.value == "DAYS_TO_COVER_VOLUME_BASELINE_UNAVAILABLE" for d in result.diagnostics)


def test_insufficient_volume_history():
    bars = [_daily_bar(d, volume="500000") for d in (10, 11)]
    short_interest = _short_interest("1000000")
    window = TrailingWindow(requested_count=5, minimum_samples=5)
    request = _request(short_interest.payload.settlement_date, window)
    result = build_days_to_cover_result([short_interest, *bars], request)
    assert result.value is None
    assert result.quality.state is QualityState.UNAVAILABLE


def test_zero_short_interest_is_a_valid_numerator():
    bars = [_daily_bar(d, volume="500000") for d in (10, 11, 12)]
    short_interest = _short_interest("0")
    window = TrailingWindow(requested_count=3, minimum_samples=3)
    request = _request(short_interest.payload.settlement_date, window)
    result = build_days_to_cover_result([short_interest, *bars], request)
    assert result.value == 0
    assert result.quality.state is QualityState.KNOWN_VALUE


def test_missing_short_interest():
    bars = [_daily_bar(d, volume="500000") for d in (10, 11, 12)]
    short_interest = _short_interest(shares=None)
    window = TrailingWindow(requested_count=3, minimum_samples=3)
    request = _request(short_interest.payload.settlement_date, window)
    result = build_days_to_cover_result([short_interest, *bars], request)
    assert result.value is None
    assert any(d.code.value == "SHORT_INTEREST_MISSING_VALUE" for d in result.diagnostics)


def test_incompatible_volume_interval_rejected():
    short_interest = _short_interest("1000000")
    window = TrailingWindow(requested_count=3, minimum_samples=3)
    request = _request(
        short_interest.payload.settlement_date, window, volume_interval=BarInterval.ONE_HOUR
    )
    result = build_days_to_cover_result([short_interest], request)
    assert result.value is None
    assert result.quality.state is QualityState.INVALID
    assert any(d.code.value == "DAYS_TO_COVER_INCOMPATIBLE_VOLUME_INTERVAL" for d in result.diagnostics)


def test_mixed_volume_providers_rejected():
    bars = [_daily_bar(d, volume="500000") for d in (10, 11, 12)]
    other_provider_bar = _daily_bar(13, volume="999", provider="OTHER-VOL-PROVIDER", source_record_id="dtc-bar-other")
    short_interest = _short_interest("1000000")
    window = TrailingWindow(requested_count=4, minimum_samples=4)
    request = _request(short_interest.payload.settlement_date, window)
    result = build_days_to_cover_result([short_interest, *bars, other_provider_bar], request)
    # Only 3 same-provider samples are eligible against a requested/minimum of 4 -- insufficient.
    assert result.value is None


def test_explicit_volume_provider():
    bars = [_daily_bar(d, volume="500000") for d in (10, 11, 12)]
    short_interest = _short_interest("1000000")
    window = TrailingWindow(requested_count=3, minimum_samples=3)
    request = _request(short_interest.payload.settlement_date, window)
    components = build_days_to_cover_components([short_interest, *bars], request)
    assert components.volume_provider == VOL_PROVIDER


def test_current_or_future_bar_excluded_from_baseline():
    bars = [_daily_bar(d, volume="500000") for d in (10, 11, 12)]
    future_bar = _daily_bar(25, volume="999999999", source_record_id="dtc-bar-future")
    short_interest = _short_interest("1000000")
    window = TrailingWindow(requested_count=3, minimum_samples=3)
    request = _request(short_interest.payload.settlement_date, window)
    with_future = build_days_to_cover_result([short_interest, *bars, future_bar], request)
    without_future = build_days_to_cover_result([short_interest, *bars], request)
    assert with_future.value == without_future.value


def test_corrected_volume_sample_before_and_after_correction_receipt():
    baseline = [_daily_bar(d, volume="500000") for d in (10, 11)]
    original = _daily_bar(12, volume="500000", provider_record_id="dtc-orig")
    receipt = datetime(2026, 2, 16, 9, 5, tzinfo=UTC)
    corrected = _daily_bar(
        12, volume="800000", source_record_id="dtc-bar-12-corrected", provider_record_id="dtc-corrected",
        status="CORRECTED", revision_number=1, supersedes_provider_record_id="dtc-orig",
        publication_timestamp="2026-02-16T09:00:00Z", ingested_at="2026-02-16T09:05:00Z",
    )
    short_interest = _short_interest("1000000")
    window = TrailingWindow(requested_count=3, minimum_samples=3)

    before_as_of = receipt.replace(hour=0)
    request_before = _request(short_interest.payload.settlement_date, window, as_of=before_as_of)
    result_before = build_days_to_cover_result([short_interest, *baseline, original, corrected], request_before)

    request_after = _request(short_interest.payload.settlement_date, window, as_of=AS_OF)
    result_after = build_days_to_cover_result([short_interest, *baseline, original, corrected], request_after)

    assert result_before.value != result_after.value
    assert result_before.value == Decimal(1000000) / (Decimal(1000000) / Decimal(2))
    assert result_after.value == Decimal(1000000) / (Decimal(1800000) / Decimal(3))


def test_cancelled_volume_sample_before_and_after_cancellation_receipt():
    baseline = [_daily_bar(d, volume="500000") for d in (10, 11)]
    original = _daily_bar(12, volume="500000", provider_record_id="dtc-cancel-orig")
    receipt = datetime(2026, 2, 16, 9, 5, tzinfo=UTC)
    cancelled = _daily_bar(
        12, volume="500000", source_record_id="dtc-bar-12-cancelled", provider_record_id="dtc-cancelled",
        status="CANCELLED", revision_number=1, supersedes_provider_record_id="dtc-cancel-orig",
        publication_timestamp="2026-02-16T09:00:00Z", ingested_at="2026-02-16T09:05:00Z",
    )
    short_interest = _short_interest("1000000")
    window = TrailingWindow(requested_count=3, minimum_samples=3)

    before_as_of = receipt.replace(hour=0)
    result_before = build_days_to_cover_result(
        [short_interest, *baseline, original, cancelled],
        _request(short_interest.payload.settlement_date, window, as_of=before_as_of),
    )
    result_after = build_days_to_cover_result(
        [short_interest, *baseline, original, cancelled],
        _request(short_interest.payload.settlement_date, window, as_of=AS_OF),
    )
    assert result_before.value is not None
    # After cancellation, only the two baseline bars remain -- below minimum_samples=3.
    assert result_after.value is None


def test_original_short_interest_record_before_revision():
    from squeeze_core.adapters.finra import normalize_finra_short_interest_records
    from .conftest import pressure_context, short_interest_record

    bars = [_daily_bar(d, volume="500000") for d in (10, 11, 12)]
    records = [
        short_interest_record(
            source_record_id="dtc-si-orig", settlement_date="2026-01-31", publication_date="2026-02-05",
            short_shares="1000000",
        ),
        short_interest_record(
            source_record_id="dtc-si-rev", settlement_date="2026-01-31", publication_date="2026-02-25",
            short_shares="1200000", revision_status="REVISED", revision_number=1,
            supersedes_source_record_id="dtc-si-orig",
        ),
    ]
    result = normalize_finra_short_interest_records(records, pressure_context(at="2026-02-06T12:00:00Z"))
    assert result.accepted, result.rejection
    window = TrailingWindow(requested_count=3, minimum_samples=3)
    early_as_of = datetime(2026, 2, 13, tzinfo=UTC)
    request = _request(datetime(2026, 1, 31).date(), window, as_of=early_as_of)
    outcome = build_days_to_cover_result([*result.observations, *bars], request)
    assert outcome.value == Decimal(1000000) / Decimal(500000)


def test_revised_short_interest_record_after_revision_availability():
    from squeeze_core.adapters.finra import normalize_finra_short_interest_records
    from .conftest import pressure_context, short_interest_record

    bars = [_daily_bar(d, volume="500000") for d in (10, 11, 12)]
    records = [
        short_interest_record(
            source_record_id="dtc-si-orig", settlement_date="2026-01-31", publication_date="2026-02-05",
            short_shares="1000000",
        ),
        short_interest_record(
            source_record_id="dtc-si-rev", settlement_date="2026-01-31", publication_date="2026-02-10",
            short_shares="1200000", revision_status="REVISED", revision_number=1,
            supersedes_source_record_id="dtc-si-orig",
        ),
    ]
    result = normalize_finra_short_interest_records(records, pressure_context())
    assert result.accepted, result.rejection
    window = TrailingWindow(requested_count=3, minimum_samples=3)
    request = _request(datetime(2026, 1, 31).date(), window, as_of=AS_OF)
    outcome = build_days_to_cover_result([*result.observations, *bars], request)
    assert outcome.value == Decimal(1200000) / Decimal(500000)


def test_cancelled_short_interest_record():
    from squeeze_core.adapters.finra import normalize_finra_short_interest_records
    from .conftest import pressure_context, short_interest_record

    bars = [_daily_bar(d, volume="500000") for d in (10, 11, 12)]
    records = [
        short_interest_record(
            source_record_id="dtc-si-orig", settlement_date="2026-01-31", publication_date="2026-02-05",
            short_shares="1000000",
        ),
        short_interest_record(
            source_record_id="dtc-si-cancel", settlement_date="2026-01-31", publication_date="2026-02-10",
            short_shares="1000000", revision_status="CANCELLED", revision_number=1,
            supersedes_source_record_id="dtc-si-orig",
        ),
    ]
    result = normalize_finra_short_interest_records(records, pressure_context())
    assert result.accepted, result.rejection
    window = TrailingWindow(requested_count=3, minimum_samples=3)
    request = _request(datetime(2026, 1, 31).date(), window, as_of=AS_OF)
    outcome = build_days_to_cover_result([*result.observations, *bars], request)
    assert outcome.value is None
    assert any(d.code.value == "SHORT_INTEREST_CANCELLED_INPUT" for d in outcome.diagnostics)


def test_publication_lag_reporting_period_age_and_availability_age_preserved():
    bars = [_daily_bar(d, volume="500000") for d in (10, 11, 12)]
    short_interest = _short_interest("1000000")
    window = TrailingWindow(requested_count=3, minimum_samples=3)
    request = _request(short_interest.payload.settlement_date, window)
    components = build_days_to_cover_components([short_interest, *bars], request)
    assert components.short_interest_source_age.publication_lag_seconds is not None
    assert components.short_interest_source_age.reporting_period_age_days is not None
    assert components.short_interest_source_age.availability_age_seconds >= 0


def test_supporting_ids_are_recorded():
    bars = [_daily_bar(d, volume="500000") for d in (10, 11, 12)]
    short_interest = _short_interest("1000000")
    window = TrailingWindow(requested_count=3, minimum_samples=3)
    request = _request(short_interest.payload.settlement_date, window)
    components = build_days_to_cover_components([short_interest, *bars], request)
    assert components.short_interest_observation_id == short_interest.observation_id
    assert set(bar.observation_id for bar in bars) <= set(components.input_observation_ids)
    assert components.volume_baseline_metric_id is not None
    assert components.volume_baseline_metric_id in components.input_metric_ids


def test_stable_component_and_final_identity():
    bars = [_daily_bar(d, volume="500000") for d in (10, 11, 12)]
    short_interest = _short_interest("1000000")
    window = TrailingWindow(requested_count=3, minimum_samples=3)
    request = _request(short_interest.payload.settlement_date, window)
    first_components = build_days_to_cover_components([short_interest, *bars], request)
    second_components = build_days_to_cover_components(list(reversed([short_interest, *bars])), request)
    assert first_components.deterministic_id == second_components.deterministic_id

    first_result = build_days_to_cover_result([short_interest, *bars], request)
    second_result = build_days_to_cover_result(list(reversed([short_interest, *bars])), request)
    assert first_result.deterministic_id == second_result.deterministic_id
    assert first_result.days_to_cover_components_id == first_components.deterministic_id


def test_input_reordering_invariance():
    bars = [_daily_bar(d, volume="500000") for d in (10, 11, 12)]
    short_interest = _short_interest("1000000")
    window = TrailingWindow(requested_count=3, minimum_samples=3)
    request = _request(short_interest.payload.settlement_date, window)
    forward = build_days_to_cover_result([short_interest, *bars], request)
    backward = build_days_to_cover_result([*reversed(bars), short_interest], request)
    assert forward.value == backward.value


def test_no_interpretation_or_threshold_label():
    import inspect

    from squeeze_core.metrics import days_to_cover

    body_lines = [
        line for line in inspect.getsource(days_to_cover).splitlines()
        if not line.strip().startswith(("import ", "from "))
    ]
    body = "\n".join(body_lines).lower()
    for needle in (
        "squeeze_score", "squeeze_probability", "pressure_score", "hard_to_borrow",
        "recommendation", "candidate_rank", "prime_subprime", "\"strong\"", "\"weak\"",
    ):
        assert needle not in body
