"""Cross-cutting revision/cancellation/no-look-ahead proofs (docs/phase-2c-design.md Section
12, docs/phase-2c-test-plan.md Section 4). Each case proves a result computed at an earlier
as_of is byte-identical when recomputed, and only changes once the later fact becomes
point-in-time eligible."""

from datetime import UTC, datetime

from squeeze_core.contracts import AssetClass, EventType
from squeeze_core.metrics import (
    MetricName,
    pressure_metric_result_hash,
)
from squeeze_core.metrics.borrow_fee_changes import (
    BorrowComparisonRequest,
    build_borrow_fee_change_result,
)
from squeeze_core.metrics.days_to_cover import DaysToCoverRequest, build_days_to_cover_result
from squeeze_core.metrics.short_interest_changes import (
    ShortInterestComparisonRequest,
    ShortInterestRevisionRequest,
    build_short_interest_change_result,
    build_short_interest_revision_delta_result,
)
from squeeze_core.adapters.finra import normalize_finra_short_interest_records
from squeeze_core.adapters.market_bars import BarInterval
from squeeze_core.metrics import TrailingWindow

from .conftest import make_bar, make_borrow_observations, pressure_context, short_interest_record

AS_OF = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


def test_ending_period_revision_before_after_publication_receipt():
    records = [
        short_interest_record(
            source_record_id="lc-orig", settlement_date="2026-01-31", publication_date="2026-02-05",
            short_shares="1000000",
        ),
        short_interest_record(
            source_record_id="lc-rev", settlement_date="2026-01-31", publication_date="2026-02-20",
            short_shares="1300000", revision_status="REVISED", revision_number=1,
            supersedes_source_record_id="lc-orig",
        ),
    ]
    batch = normalize_finra_short_interest_records(records, pressure_context(at="2026-01-25T00:00:00Z"))
    assert batch.accepted, batch.rejection
    starting = short_interest_record(source_record_id="lc-start", settlement_date="2026-01-15", publication_date="2026-01-20")
    starting_batch = normalize_finra_short_interest_records([starting], pressure_context(at="2026-01-21T00:00:00Z"))
    assert starting_batch.accepted

    observations = [*batch.observations, *starting_batch.observations]
    request = ShortInterestComparisonRequest(
        symbol="TESTC", asset_class=AssetClass.EQUITY, as_of=AS_OF, provider="finra-provider-test",
        starting_reporting_period=starting_batch.observations[0].payload.settlement_date,
        ending_reporting_period=batch.observations[0].payload.settlement_date,
    )
    before_as_of = datetime(2026, 2, 10, tzinfo=UTC)
    before = build_short_interest_change_result(
        observations, ShortInterestComparisonRequest(**{**request.__dict__, "as_of": before_as_of}),
        MetricName.PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE,
    )
    before_again = build_short_interest_change_result(
        observations, ShortInterestComparisonRequest(**{**request.__dict__, "as_of": before_as_of}),
        MetricName.PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE,
    )
    after = build_short_interest_change_result(
        observations, request, MetricName.PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE
    )

    assert pressure_metric_result_hash(before) == pressure_metric_result_hash(before_again)
    assert before.value != after.value
    assert before.value == 0  # original 1,000,000 vs starting 1,000,000
    assert after.value == 300000  # revision 1,300,000 vs starting 1,000,000


def test_revision_delta_before_after_availability():
    records = [
        short_interest_record(
            source_record_id="lc-rd-orig", settlement_date="2026-01-31", publication_date="2026-02-05",
            short_shares="1000000",
        ),
        short_interest_record(
            source_record_id="lc-rd-rev", settlement_date="2026-01-31", publication_date="2026-02-20",
            short_shares="1050000", revision_status="REVISED", revision_number=1,
            supersedes_source_record_id="lc-rd-orig",
        ),
    ]
    batch = normalize_finra_short_interest_records(records, pressure_context(at="2026-01-25T00:00:00Z"))
    assert batch.accepted, batch.rejection
    period = batch.observations[0].payload.settlement_date
    before_as_of = datetime(2026, 2, 10, tzinfo=UTC)

    before = build_short_interest_revision_delta_result(
        batch.observations,
        ShortInterestRevisionRequest(
            symbol="TESTC", asset_class=AssetClass.EQUITY, as_of=before_as_of, provider="finra-provider-test",
            reporting_period=period,
        ),
    )
    before_again = build_short_interest_revision_delta_result(
        batch.observations,
        ShortInterestRevisionRequest(
            symbol="TESTC", asset_class=AssetClass.EQUITY, as_of=before_as_of, provider="finra-provider-test",
            reporting_period=period,
        ),
    )
    after = build_short_interest_revision_delta_result(
        batch.observations,
        ShortInterestRevisionRequest(
            symbol="TESTC", asset_class=AssetClass.EQUITY, as_of=AS_OF, provider="finra-provider-test",
            reporting_period=period,
        ),
    )
    assert pressure_metric_result_hash(before) == pressure_metric_result_hash(before_again)
    assert before.value is None
    assert after.value == 50000


def test_ending_period_cancellation_before_after_receipt():
    records = [
        short_interest_record(
            source_record_id="lc-cx-orig", settlement_date="2026-01-31", publication_date="2026-02-05",
            short_shares="1000000",
        ),
        short_interest_record(
            source_record_id="lc-cx-cancel", settlement_date="2026-01-31", publication_date="2026-02-20",
            short_shares="1000000", revision_status="CANCELLED", revision_number=1,
            supersedes_source_record_id="lc-cx-orig",
        ),
    ]
    batch = normalize_finra_short_interest_records(records, pressure_context(at="2026-01-25T00:00:00Z"))
    assert batch.accepted, batch.rejection
    starting = short_interest_record(source_record_id="lc-cx-start", settlement_date="2026-01-15", publication_date="2026-01-20")
    starting_batch = normalize_finra_short_interest_records([starting], pressure_context(at="2026-01-21T00:00:00Z"))
    observations = [*batch.observations, *starting_batch.observations]
    period = batch.observations[0].payload.settlement_date
    starting_period = starting_batch.observations[0].payload.settlement_date

    before_as_of = datetime(2026, 2, 10, tzinfo=UTC)
    before = build_short_interest_change_result(
        observations,
        ShortInterestComparisonRequest(
            symbol="TESTC", asset_class=AssetClass.EQUITY, as_of=before_as_of, provider="finra-provider-test",
            starting_reporting_period=starting_period, ending_reporting_period=period,
        ),
        MetricName.PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE,
    )
    after = build_short_interest_change_result(
        observations,
        ShortInterestComparisonRequest(
            symbol="TESTC", asset_class=AssetClass.EQUITY, as_of=AS_OF, provider="finra-provider-test",
            starting_reporting_period=starting_period, ending_reporting_period=period,
        ),
        MetricName.PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE,
    )
    assert before.value == 0  # sees the un-cancelled original
    assert after.value is None  # sees the cancellation
    assert any(d.code.value == "SHORT_INTEREST_CANCELLED_INPUT" for d in after.diagnostics)


def test_days_to_cover_short_interest_revision_before_after_availability():
    records = [
        short_interest_record(
            source_record_id="lc-dtc-orig", settlement_date="2026-01-31", publication_date="2026-02-05",
            short_shares="1000000",
        ),
        short_interest_record(
            source_record_id="lc-dtc-rev", settlement_date="2026-01-31", publication_date="2026-02-20",
            short_shares="1500000", revision_status="REVISED", revision_number=1,
            supersedes_source_record_id="lc-dtc-orig",
        ),
    ]
    batch = normalize_finra_short_interest_records(records, pressure_context(at="2026-01-25T00:00:00Z"))
    assert batch.accepted, batch.rejection
    bars = [
        make_bar(
            source_record_id=f"lc-dtc-bar-{d}", symbol="TESTC", provider="SIM-VOLUME-PROVIDER",
            bar_start=f"2026-01-{d:02d}T00:00:00Z", bar_end=f"2026-01-{d + 1:02d}T00:00:00Z",
            session_date=f"2026-01-{d:02d}", timezone="UTC",
            publication_timestamp=f"2026-01-{d:02d}T20:01:00Z", ingested_at=f"2026-01-{d:02d}T21:02:00Z",
            volume="500000",
        )
        for d in (10, 11, 12)
    ]
    window = TrailingWindow(requested_count=3, minimum_samples=3)
    period = batch.observations[0].payload.settlement_date
    request_before = DaysToCoverRequest(
        symbol="TESTC", asset_class=AssetClass.EQUITY, as_of=datetime(2026, 2, 10, tzinfo=UTC),
        short_interest_provider="finra-provider-test", short_interest_reporting_period=period,
        volume_provider="SIM-VOLUME-PROVIDER", volume_interval=BarInterval.ONE_DAY, volume_window=window,
    )
    request_after = DaysToCoverRequest(**{**request_before.__dict__, "as_of": AS_OF})
    before = build_days_to_cover_result([*batch.observations, *bars], request_before)
    after = build_days_to_cover_result([*batch.observations, *bars], request_after)
    assert before.value == 2  # 1,000,000 / 500,000
    assert after.value == 3  # 1,500,000 / 500,000


def test_borrow_fee_later_observation_does_not_affect_earlier_as_of_result():
    observations = make_borrow_observations(
        source_record_id="lc-borrow-early", provider_timestamp="2026-01-10T00:00:00Z", fee_rate="5.0",
    )
    early = next(o for o in observations if o.event_type is EventType.BORROW_FEE)
    late_batch = make_borrow_observations(
        source_record_id="lc-borrow-late", provider_timestamp="2026-02-01T00:00:00Z", fee_rate="9.0",
        ingested_at="2026-02-01T00:05:00Z",
    )
    late = next(o for o in late_batch if o.event_type is EventType.BORROW_FEE)

    request = BorrowComparisonRequest(
        symbol="TESTC", asset_class=AssetClass.EQUITY, as_of=datetime(2026, 1, 15, tzinfo=UTC),
        provider="ibkr-provider-test", starting_effective_timestamp=early.effective_timestamp,
        ending_effective_timestamp=late.effective_timestamp,
    )
    result_early_as_of = build_borrow_fee_change_result(
        [early, late], request, MetricName.BORROW_FEE_ABSOLUTE_CHANGE
    )
    assert result_early_as_of.value is None  # `late` not yet eligible

    request_late = BorrowComparisonRequest(**{**request.__dict__, "as_of": AS_OF})
    result_after = build_borrow_fee_change_result(
        [early, late], request_late, MetricName.BORROW_FEE_ABSOLUTE_CHANGE
    )
    assert result_after.value == 4
