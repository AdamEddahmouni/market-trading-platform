"""Cross-cutting no-look-ahead proof: one before/after-as_of pair per new selector path (not per
metric -- the underlying point-in-time mechanism is identical across every metric built on the
same selector). Per-metric correction/cancellation cases already live in
test_relative_volume.py, test_volume_standardization.py, test_return_baselines.py, and
test_return_standardization.py; this file exists to make the "one representative case per
selector path" cross-check explicit per docs/phase-2b-test-plan.md Section 4, not to duplicate
those already-passing cases.
"""

from datetime import UTC, datetime
from decimal import Decimal

from squeeze_core.adapters.market_bars import BarInterval
from squeeze_core.contracts import AssetClass, QualityState
from squeeze_core.metrics import (
    RelativeVolumeRequest,
    ReturnBaselineRequest,
    ReturnCountWindow,
    TrailingWindow,
    VolumeZScoreRequest,
    build_mean_percentage_return_baseline_result,
    build_relative_volume_result,
    build_volume_z_score_result,
)

from .conftest import bar_boundary, make_bar

AS_OF = datetime(2026, 1, 25, 22, 0, tzinfo=UTC)
BEFORE = datetime(2026, 1, 17, 0, 0, tzinfo=UTC)


def _daily_bar(day: int, *, close="10.00", volume="10000", status="COMPLETED", **overrides):
    values = {
        "source_record_id": f"lc-bar-{day}",
        "bar_start": f"2026-01-{day:02d}T00:00:00-05:00",
        "bar_end": f"2026-01-{day + 1:02d}T00:00:00-05:00",
        "session_date": f"2026-01-{day:02d}",
        "publication_timestamp": f"2026-01-{day:02d}T16:01:00-05:00",
        "ingested_at": f"2026-01-{day:02d}T21:02:00Z",
        "high": "1000.00", "low": "0.01", "open": close, "close": close, "volume": volume, "status": status,
    }
    values.update(overrides)
    return make_bar(**values)


def test_relative_volume_target_bar_correction_never_changes_the_earlier_result():
    bars = [_daily_bar(d, volume="1000") for d in (12, 13, 14)]
    original = _daily_bar(15, volume="1000", provider_record_id="lc-rv-orig")
    corrected = _daily_bar(
        15, volume="5000", provider_record_id="lc-rv-corrected", source_record_id="lc-bar-15-corrected",
        status="CORRECTED", revision_number=1, supersedes_provider_record_id="lc-rv-orig",
        publication_timestamp="2026-01-18T09:00:00-05:00", ingested_at="2026-01-18T09:05:00Z",
    )
    window = TrailingWindow(requested_count=3, minimum_samples=3)
    s, e = bar_boundary(corrected)
    observations = [*bars, original, corrected]
    request_before = RelativeVolumeRequest(
        symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=BEFORE, source_interval=BarInterval.ONE_DAY,
        target_bar_start=s, target_bar_end=e, window=window,
    )
    request_after = RelativeVolumeRequest(
        symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF, source_interval=BarInterval.ONE_DAY,
        target_bar_start=s, target_bar_end=e, window=window,
    )
    before_value = build_relative_volume_result(observations, request_before).value
    # Recomputing "before" again after the correction has arrived must be byte-identical --
    # a result computed at an earlier as_of is never mutated by later evidence.
    before_value_again = build_relative_volume_result(observations, request_before).value
    after_value = build_relative_volume_result(observations, request_after).value
    assert before_value == before_value_again == Decimal(1)
    assert after_value == Decimal(5)
    assert before_value != after_value


def test_relative_volume_baseline_sample_correction_never_changes_the_earlier_result():
    original = _daily_bar(12, volume="1000", provider_record_id="lc-base-orig")
    corrected = _daily_bar(
        12, volume="4000", provider_record_id="lc-base-corrected", source_record_id="lc-bar-12-corrected",
        status="CORRECTED", revision_number=1, supersedes_provider_record_id="lc-base-orig",
        publication_timestamp="2026-01-18T09:00:00-05:00", ingested_at="2026-01-18T09:05:00Z",
    )
    target = _daily_bar(15, volume="4000")
    window = TrailingWindow(requested_count=1, minimum_samples=1)
    s, e = bar_boundary(target)
    observations = [original, corrected, target]
    request_before = RelativeVolumeRequest(
        symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=BEFORE, source_interval=BarInterval.ONE_DAY,
        target_bar_start=s, target_bar_end=e, window=window,
    )
    request_after = RelativeVolumeRequest(
        symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF, source_interval=BarInterval.ONE_DAY,
        target_bar_start=s, target_bar_end=e, window=window,
    )
    assert build_relative_volume_result(observations, request_before).value == Decimal(4)
    assert build_relative_volume_result(observations, request_after).value == Decimal(1)


def test_volume_z_score_distribution_sample_cancellation_never_changes_the_earlier_result():
    distribution_days = list(range(20, 28))
    distribution_volumes = (2, 4, 4, 4, 5, 5, 7, 9)
    bars = [_daily_bar(d, volume=str(v)) for d, v in zip(distribution_days, distribution_volumes)]
    sample_original = _daily_bar(24, volume="5", provider_record_id="lc-vz-orig")
    sample_cancelled = _daily_bar(
        24, volume="5", provider_record_id="lc-vz-cancelled", source_record_id="lc-bar-24-cancelled",
        status="CANCELLED", revision_number=1, supersedes_provider_record_id="lc-vz-orig",
        publication_timestamp="2026-01-30T09:00:00-05:00", ingested_at="2026-01-30T09:05:00Z",
    )
    target = _daily_bar(28, volume="9")
    others = [b for b in bars if b.observation_id != sample_original.observation_id]
    observations = [*others, sample_original, sample_cancelled, target]
    window = TrailingWindow(requested_count=8, minimum_samples=2)
    s, e = bar_boundary(target)
    request_before = VolumeZScoreRequest(
        symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=datetime(2026, 1, 29, 0, 0, tzinfo=UTC),
        source_interval=BarInterval.ONE_DAY, target_bar_start=s, target_bar_end=e, window=window,
    )
    request_after = VolumeZScoreRequest(
        symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=datetime(2026, 2, 1, 0, 0, tzinfo=UTC),
        source_interval=BarInterval.ONE_DAY, target_bar_start=s, target_bar_end=e, window=window,
    )
    before_result = build_volume_z_score_result(observations, request_before)
    after_result = build_volume_z_score_result(observations, request_after)
    assert before_result.value == Decimal(2)
    assert after_result.value != before_result.value


def test_return_baseline_historical_bar_correction_never_changes_the_earlier_result():
    a = _daily_bar(9, close="10.00")
    b_original = _daily_bar(10, close="11.00", provider_record_id="lc-rb-orig")
    b_corrected = _daily_bar(
        10, close="15.00", provider_record_id="lc-rb-corrected", source_record_id="lc-bar-10-corrected",
        status="CORRECTED", revision_number=1, supersedes_provider_record_id="lc-rb-orig",
        publication_timestamp="2026-01-18T09:00:00-05:00", ingested_at="2026-01-18T09:05:00Z",
    )
    window = ReturnCountWindow(requested_count=1, minimum_samples=1)
    target_start, _ = bar_boundary(_daily_bar(11, close="0.01"))
    observations = [a, b_original, b_corrected]
    request_before = ReturnBaselineRequest(
        symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=BEFORE, source_interval=BarInterval.ONE_DAY,
        target_bar_start=target_start, window=window,
    )
    request_after = ReturnBaselineRequest(
        symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF, source_interval=BarInterval.ONE_DAY,
        target_bar_start=target_start, window=window,
    )
    before_result = build_mean_percentage_return_baseline_result(observations, request_before)
    after_result = build_mean_percentage_return_baseline_result(observations, request_after)
    assert before_result.value == Decimal(10)
    assert after_result.value == Decimal(50)
    assert before_result.quality.state is QualityState.KNOWN_VALUE
