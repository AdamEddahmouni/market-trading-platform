"""Cross-domain compatibility (docs/phase-2c-design.md Section 8.3/11, handoff Section 28):
DAYS_TO_COVER combines only compatible units, keeps short-interest and volume providers
separately identified, and never substitutes a cross-domain source silently."""

import inspect
from datetime import UTC, datetime

from squeeze_core.adapters.market_bars import BarInterval
from squeeze_core.contracts import AssetClass, QualityState
from squeeze_core.metrics import MetricUnit, TrailingWindow
from squeeze_core.metrics import days_to_cover
from squeeze_core.metrics.days_to_cover import (
    DaysToCoverRequest,
    build_days_to_cover_components,
    build_days_to_cover_result,
)

from .conftest import make_bar, make_short_interest

AS_OF = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
SI_PROVIDER = "finra-provider-test"
VOL_PROVIDER = "SIM-VOLUME-PROVIDER"


def _bars():
    return [
        make_bar(
            source_record_id=f"cd-bar-{d}", symbol="TESTC", provider=VOL_PROVIDER,
            bar_start=f"2026-02-{d:02d}T00:00:00Z", bar_end=f"2026-02-{d + 1:02d}T00:00:00Z",
            session_date=f"2026-02-{d:02d}", timezone="UTC",
            publication_timestamp=f"2026-02-{d:02d}T20:01:00Z", ingested_at=f"2026-02-{d:02d}T21:02:00Z",
            volume="500000",
        )
        for d in (10, 11, 12)
    ]


def _request(reporting_period):
    return DaysToCoverRequest(
        symbol="TESTC", asset_class=AssetClass.EQUITY, as_of=AS_OF,
        short_interest_provider=SI_PROVIDER, short_interest_reporting_period=reporting_period,
        volume_provider=VOL_PROVIDER, volume_interval=BarInterval.ONE_DAY,
        volume_window=TrailingWindow(requested_count=3, minimum_samples=3),
    )


def test_days_to_cover_only_combines_shares_units():
    short_interest = make_short_interest(settlement_date="2026-01-31", publication_date="2026-02-10", short_shares="1000000")
    components = build_days_to_cover_components([short_interest, *_bars()], _request(short_interest.payload.settlement_date))
    assert components.short_interest_unit is MetricUnit.SHARES
    assert components.volume_unit is MetricUnit.SHARES


def test_short_interest_and_volume_providers_kept_separate():
    short_interest = make_short_interest(settlement_date="2026-01-31", publication_date="2026-02-10", short_shares="1000000")
    components = build_days_to_cover_components([short_interest, *_bars()], _request(short_interest.payload.settlement_date))
    assert components.short_interest_provider == SI_PROVIDER
    assert components.volume_provider == VOL_PROVIDER
    assert components.short_interest_provider != components.volume_provider

    result = build_days_to_cover_result([short_interest, *_bars()], _request(short_interest.payload.settlement_date))
    assert result.provider == SI_PROVIDER
    assert result.volume_provider == VOL_PROVIDER


def test_stale_short_interest_numerator_still_computable_with_explicit_age():
    old_short_interest = make_short_interest(settlement_date="2020-01-31", publication_date="2020-02-10", short_shares="1000000")
    components = build_days_to_cover_components(
        [old_short_interest, *_bars()], _request(old_short_interest.payload.settlement_date)
    )
    assert components.quality.state is QualityState.KNOWN_VALUE
    assert components.short_interest_source_age.reporting_period_age_days > 1000


def test_recent_volume_does_not_make_old_short_interest_report_fresh():
    old_short_interest = make_short_interest(settlement_date="2020-01-31", publication_date="2020-02-10", short_shares="1000000")
    components = build_days_to_cover_components(
        [old_short_interest, *_bars()], _request(old_short_interest.payload.settlement_date)
    )
    # The recent volume baseline (Feb 2026 bars) has no bearing on the short-interest age.
    assert components.short_interest_source_age.reporting_period_age_days > 2000


def test_short_float_percent_field_never_read_by_days_to_cover_or_short_interest_change():
    from squeeze_core.metrics import short_interest_changes

    for module in (days_to_cover, short_interest_changes):
        source = inspect.getsource(module)
        assert "short_float_percent" not in source


def test_provider_days_to_cover_field_never_read():
    # PublishedShortInterestPayload.days_to_cover is the provider's own published figure and
    # must never be substituted for Phase 2C's own computed DAYS_TO_COVER.
    source = inspect.getsource(days_to_cover)
    assert "payload.days_to_cover" not in source


def test_mean_volume_baseline_policy_matches_phase_2a_reused_arithmetic():
    from squeeze_core.metrics.volume_baselines import CALCULATION_POLICY_VERSION as PHASE_2A_POLICY

    short_interest = make_short_interest(settlement_date="2026-01-31", publication_date="2026-02-10", short_shares="1000000")
    components = build_days_to_cover_components([short_interest, *_bars()], _request(short_interest.payload.settlement_date))
    assert components.volume_baseline_metric_id is not None
    # days_to_cover.py constructs its internal MEAN_VOLUME_BASELINE MetricResult with the
    # identical Phase 2A policy string -- proving no divergent parallel averaging formula.
    assert days_to_cover.VOLUME_BASELINE_POLICY_VERSION == PHASE_2A_POLICY


def test_hard_to_borrow_field_never_read_by_borrow_pressure_metrics():
    from squeeze_core.metrics import borrow_availability_changes, borrow_fee_changes

    for module in (borrow_fee_changes, borrow_availability_changes, days_to_cover):
        source = inspect.getsource(module)
        assert "hard_to_borrow" not in source
