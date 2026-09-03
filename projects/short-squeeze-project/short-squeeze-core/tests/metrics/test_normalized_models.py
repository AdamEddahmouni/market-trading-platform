from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from squeeze_core.adapters.market_bars import BarInterval
from squeeze_core.contracts import AssetClass, Quality, QualityState
from squeeze_core.metrics import (
    BaselineKind,
    BaselineStatistics,
    MetricName,
    MetricUnit,
    NormalizedMetricResult,
    ProviderScopeMode,
    ReturnCountWindow,
    SampleCounts,
    StandardDeviationPolicy,
    TrailingWindow,
)

AS_OF = datetime(2026, 1, 1, tzinfo=UTC)


def _baseline(**overrides) -> BaselineStatistics:
    values = dict(
        baseline_kind=BaselineKind.VOLUME,
        baseline_version="1.0.0",
        calculation_policy_version="trailing_bar_count_exclude_current.v1",
        standard_deviation_policy=StandardDeviationPolicy.POPULATION_DECIMAL_V1,
        symbol="TESTA",
        asset_class=AssetClass.EQUITY,
        as_of=AS_OF,
        source_interval=BarInterval.ONE_DAY,
        provider_scope=ProviderScopeMode.SINGLE_PROVIDER,
        window=TrailingWindow(requested_count=3, minimum_samples=2),
        sample_counts=SampleCounts(requested=3, eligible=3, used=3, missing=0),
        mean=Decimal(100),
        variance=Decimal(4),
        standard_deviation=Decimal(2),
        unit=MetricUnit.SHARES,
        quality=Quality(state=QualityState.KNOWN_VALUE),
    )
    values.update(overrides)
    return BaselineStatistics(**values)


def _normalized_result(**overrides) -> NormalizedMetricResult:
    values = dict(
        metric_name=MetricName.VOLUME_Z_SCORE,
        metric_version="1.0.0",
        calculation_policy_version="volume_distribution_z_score.v1",
        standard_deviation_policy=StandardDeviationPolicy.POPULATION_DECIMAL_V1,
        symbol="TESTA",
        asset_class=AssetClass.EQUITY,
        as_of=AS_OF,
        source_interval=BarInterval.ONE_DAY,
        provider_scope=ProviderScopeMode.SINGLE_PROVIDER,
        value=Decimal("1.5"),
        unit=MetricUnit.STANDARD_DEVIATIONS,
        quality=Quality(state=QualityState.KNOWN_VALUE),
    )
    values.update(overrides)
    return NormalizedMetricResult(**values)


def test_baseline_statistics_is_immutable():
    baseline = _baseline()
    with pytest.raises(ValidationError):
        baseline.mean = Decimal(999)


def test_normalized_metric_result_is_immutable():
    result = _normalized_result()
    with pytest.raises(ValidationError):
        result.value = Decimal(999)


def test_baseline_statistics_rejects_extra_fields():
    with pytest.raises(ValidationError):
        _baseline(unexpected_field="nope")


def test_normalized_metric_result_rejects_extra_fields():
    with pytest.raises(ValidationError):
        _normalized_result(unexpected_field="nope")


def test_baseline_statistics_known_value_requires_numeric_fields():
    with pytest.raises(ValidationError):
        _baseline(mean=None)


def test_baseline_statistics_non_known_value_forbids_numeric_fields():
    with pytest.raises(ValidationError):
        _baseline(
            quality=Quality(state=QualityState.UNAVAILABLE, reasons=("x",)),
        )  # mean/variance/standard_deviation still set -> invalid


def test_normalized_metric_result_known_value_requires_value():
    with pytest.raises(ValidationError):
        _normalized_result(value=None)


def test_normalized_metric_result_non_known_value_forbids_value():
    with pytest.raises(ValidationError):
        _normalized_result(quality=Quality(state=QualityState.UNAVAILABLE, reasons=("x",)))


def test_return_count_window_rejects_minimum_above_requested():
    with pytest.raises(ValidationError):
        ReturnCountWindow(requested_count=2, minimum_samples=3)


def test_return_count_window_is_frozen():
    window = ReturnCountWindow(requested_count=3, minimum_samples=2)
    with pytest.raises(ValidationError):
        window.requested_count = 10


def test_standard_deviation_policy_has_one_stable_member():
    assert {item.value for item in StandardDeviationPolicy} == {"population_standard_deviation_decimal.v1"}


def test_metric_name_gains_exactly_the_six_phase_2b_members():
    expected_new = {
        "RELATIVE_VOLUME",
        "VOLUME_PERCENT_DEVIATION",
        "VOLUME_Z_SCORE",
        "MEAN_PERCENTAGE_RETURN_BASELINE",
        "PERCENTAGE_RETURN_STANDARD_DEVIATION_BASELINE",
        "PERCENTAGE_RETURN_Z_SCORE",
    }
    assert expected_new <= {item.value for item in MetricName}


def test_metric_unit_gains_ratio_and_standard_deviations():
    assert {"RATIO", "STANDARD_DEVIATIONS"} <= {item.value for item in MetricUnit}


def test_deterministic_identity_stable_across_construction():
    a = _baseline()
    b = _baseline()
    assert a.deterministic_id == b.deterministic_id

    x = _normalized_result()
    y = _normalized_result()
    assert x.deterministic_id == y.deterministic_id


def test_canonical_serialization_round_trips():
    from squeeze_core.metrics import (
        deserialize_baseline_statistics,
        deserialize_normalized_metric_result,
        serialize_baseline_statistics,
        serialize_normalized_metric_result,
    )

    baseline = _baseline()
    raw = serialize_baseline_statistics(baseline)
    restored = deserialize_baseline_statistics(raw)
    assert restored.mean == baseline.mean
    assert restored.deterministic_id == baseline.deterministic_id

    result = _normalized_result()
    raw2 = serialize_normalized_metric_result(result)
    restored2 = deserialize_normalized_metric_result(raw2)
    assert restored2.value == result.value
    assert restored2.deterministic_id == result.deterministic_id


def test_metric_result_defines_no_baseline_metric_id_field():
    from squeeze_core.metrics import MetricResult

    # Phase 2A's MetricResult is untouched -- these Phase 2B-only fields must never appear on it.
    for needle in ("baseline_metric_id", "target_boundary", "input_metric_ids", "standard_deviation_policy"):
        assert needle not in MetricResult.model_fields
