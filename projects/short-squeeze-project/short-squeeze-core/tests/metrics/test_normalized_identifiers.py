from datetime import UTC, datetime
from decimal import Decimal

from squeeze_core.adapters.market_bars import BarInterval
from squeeze_core.contracts import AssetClass, Quality, QualityState
from squeeze_core.metrics import (
    METRIC_NAMESPACE,
    BaselineKind,
    BaselineStatistics,
    MetricName,
    MetricResult,
    MetricUnit,
    NormalizedMetricResult,
    ProviderScopeMode,
    SampleCounts,
    StandardDeviationPolicy,
    TrailingWindow,
    baseline_identity,
    deterministic_baseline_id,
    deterministic_metric_id,
    deterministic_normalized_metric_id,
    normalized_metric_identity,
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


def test_baseline_identity_excludes_value_fields():
    a = _baseline(mean=Decimal(100))
    b = _baseline(mean=Decimal(200))
    assert baseline_identity(a) == baseline_identity(b)
    assert a.deterministic_id == b.deterministic_id


def test_normalized_metric_identity_excludes_value_and_diagnostics():
    a = _normalized_result(value=Decimal("1.5"))
    b = _normalized_result(value=Decimal("-1.5"))
    assert normalized_metric_identity(a) == normalized_metric_identity(b)
    assert a.deterministic_id == b.deterministic_id


def test_identity_changes_with_baseline_metric_id():
    a = _normalized_result(baseline_metric_id="aaa")
    b = _normalized_result(baseline_metric_id="bbb")
    assert a.deterministic_id != b.deterministic_id


def test_identity_uses_shared_metric_namespace():
    baseline = _baseline()
    result = _normalized_result()
    assert deterministic_baseline_id(baseline_identity(baseline)) == baseline.deterministic_id
    assert deterministic_normalized_metric_id(normalized_metric_identity(result)) == result.deterministic_id
    assert METRIC_NAMESPACE is not None


def test_two_semantically_different_unavailable_results_do_not_collide():
    unavailable_a = _normalized_result(
        value=None,
        quality=Quality(state=QualityState.UNAVAILABLE, reasons=("x",)),
        input_observation_ids=("obs-a",),
    )
    unavailable_b = _normalized_result(
        value=None,
        quality=Quality(state=QualityState.UNAVAILABLE, reasons=("y",)),
        input_observation_ids=("obs-b",),
    )
    assert unavailable_a.deterministic_id != unavailable_b.deterministic_id


def test_baseline_statistics_id_and_normalized_result_id_do_not_collide_for_matching_scope():
    # Same symbol/as_of/interval/provider scope on both models -- structurally distinct identity
    # dict shapes (different key sets) must still avoid collision.
    baseline = _baseline()
    result = _normalized_result()
    assert baseline.deterministic_id != result.deterministic_id


def test_normalized_result_id_and_phase_2a_metric_result_id_do_not_collide():
    from squeeze_core.contracts import MarketSession

    phase_2a_result = MetricResult(
        metric_name=MetricName.MEAN_VOLUME_BASELINE,
        metric_version="1.0.0",
        calculation_policy_version="trailing_mean_exclude_current.v1",
        symbol="TESTA",
        asset_class=AssetClass.EQUITY,
        as_of=AS_OF,
        source_interval=BarInterval.ONE_DAY,
        provider_scope=ProviderScopeMode.SINGLE_PROVIDER,
        window=TrailingWindow(requested_count=3, minimum_samples=2),
        value=Decimal(100),
        unit=MetricUnit.SHARES,
        sample_counts=SampleCounts(requested=3, eligible=3, used=3, missing=0),
        quality=Quality(state=QualityState.KNOWN_VALUE),
    )
    phase_2b_result = _normalized_result(
        metric_name=MetricName.RELATIVE_VOLUME,
        window=TrailingWindow(requested_count=3, minimum_samples=2),
        standard_deviation_policy=None,
    )
    assert phase_2a_result.deterministic_id != phase_2b_result.deterministic_id
