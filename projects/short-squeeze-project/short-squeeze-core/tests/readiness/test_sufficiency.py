from squeeze_core.readiness import StructuralState, build_input_sufficiency_result
from squeeze_core.readiness.policies import UnsupportedOperationError, UnsupportedPolicyVersionError

from .conftest import build_bundle, make_bar, make_borrow, make_short_interest


def test_sufficient_inputs_for_absolute_return():
    bar = make_bar()
    bundle = build_bundle("TESTD", [bar], "2026-03-01T12:00:00Z", include_market_bars_domain=True)
    result = build_input_sufficiency_result(bundle, "ABSOLUTE_RETURN")
    assert result.structural_state is StructuralState.SUFFICIENT
    assert not result.missing_inputs


def test_missing_bar_for_absolute_return():
    si = make_short_interest()
    bundle = build_bundle(
        "TESTD", [si], "2026-03-01T12:00:00Z", include_market_bars_domain=True
    )
    result = build_input_sufficiency_result(bundle, "ABSOLUTE_RETURN")
    assert result.structural_state is StructuralState.INSUFFICIENT
    assert "domain:MARKET_BARS" in result.missing_inputs


def test_sufficient_inputs_for_relative_volume_with_referenced_metric():
    from squeeze_core.contracts import AssetClass, Quality, QualityState
    from squeeze_core.metrics import MetricName, MetricUnit, ProviderScopeMode, SampleCounts
    from squeeze_core.metrics.models import MetricResult
    from datetime import UTC, datetime

    bar = make_bar()
    bundle = build_bundle("TESTD", [bar], "2026-03-01T12:00:00Z", include_market_bars_domain=True)
    baseline = MetricResult(
        metric_name=MetricName.MEAN_VOLUME_BASELINE,
        metric_version="1.0.0",
        calculation_policy_version="trailing_mean_exclude_current.v1",
        symbol="TESTD",
        asset_class=AssetClass.EQUITY,
        as_of=datetime(2026, 3, 1, 12, 0, tzinfo=UTC),
        source_interval=bar.payload.timeframe,
        provider_scope=ProviderScopeMode.SINGLE_PROVIDER,
        value=None,
        unit=MetricUnit.SHARES,
        sample_counts=SampleCounts(requested=5, eligible=5, used=5, missing=0),
        quality=Quality(state=QualityState.UNAVAILABLE, reasons=("insufficient window",)),
    )
    result = build_input_sufficiency_result(
        bundle, "RELATIVE_VOLUME", metric_results=(baseline,)
    )
    assert baseline.deterministic_id in result.referenced_metric_ids
    assert result.structural_state is StructuralState.INSUFFICIENT
    assert "metric:MEAN_VOLUME_BASELINE" in result.missing_inputs


def test_insufficient_volume_history_for_relative_volume():
    from squeeze_core.contracts import AssetClass, Quality, QualityState
    from squeeze_core.metrics import MetricName, MetricUnit, ProviderScopeMode, SampleCounts
    from squeeze_core.metrics.models import MetricResult
    from datetime import UTC, datetime

    bar = make_bar()
    bundle = build_bundle("TESTD", [bar], "2026-03-01T12:00:00Z", include_market_bars_domain=True)
    baseline = MetricResult(
        metric_name=MetricName.MEAN_VOLUME_BASELINE,
        metric_version="1.0.0",
        calculation_policy_version="trailing_mean_exclude_current.v1",
        symbol="TESTD",
        asset_class=AssetClass.EQUITY,
        as_of=datetime(2026, 3, 1, 12, 0, tzinfo=UTC),
        source_interval=bar.payload.timeframe,
        provider_scope=ProviderScopeMode.SINGLE_PROVIDER,
        value=1000,
        unit=MetricUnit.SHARES,
        sample_counts=SampleCounts(requested=5, eligible=3, used=3, missing=0),
        quality=Quality(state=QualityState.KNOWN_VALUE),
    )
    result = build_input_sufficiency_result(
        bundle, "RELATIVE_VOLUME", metric_results=(baseline,)
    )
    assert result.structural_state is StructuralState.INSUFFICIENT
    assert "metric:MEAN_VOLUME_BASELINE" in result.insufficient_history_inputs


def test_sufficient_inputs_for_short_interest_change():
    si = make_short_interest()
    bundle = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    result = build_input_sufficiency_result(
        bundle, "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE"
    )
    assert result.structural_state is StructuralState.SUFFICIENT


def test_missing_short_interest_domain_is_insufficient():
    bundle = build_bundle(
        "TESTD", [], "2026-03-01T12:00:00Z", include_published_short_interest_domain=True
    )
    result = build_input_sufficiency_result(
        bundle, "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE"
    )
    assert result.structural_state is StructuralState.INSUFFICIENT
    assert "domain:PUBLISHED_SHORT_INTEREST" in result.missing_inputs


def test_sufficient_inputs_for_days_to_cover():
    si = make_short_interest()
    bar = make_bar()
    bundle = build_bundle(
        "TESTD", [si, bar], "2026-03-01T12:00:00Z", include_market_bars_domain=True
    )
    result = build_input_sufficiency_result(bundle, "DAYS_TO_COVER")
    assert result.structural_state is StructuralState.SUFFICIENT


def test_missing_short_interest_for_days_to_cover():
    bar = make_bar()
    bundle = build_bundle(
        "TESTD",
        [bar],
        "2026-03-01T12:00:00Z",
        include_market_bars_domain=True,
        include_published_short_interest_domain=True,
    )
    result = build_input_sufficiency_result(bundle, "DAYS_TO_COVER")
    assert result.structural_state is StructuralState.INSUFFICIENT
    assert "domain:PUBLISHED_SHORT_INTEREST" in result.missing_inputs


def test_sufficient_inputs_for_borrow_fee_change():
    fee, _ = make_borrow()
    bundle = build_bundle("TESTD", [fee], "2026-03-01T12:00:00Z")
    result = build_input_sufficiency_result(bundle, "BORROW_FEE_ABSOLUTE_CHANGE")
    assert result.structural_state is StructuralState.SUFFICIENT


def test_sufficient_inputs_for_borrow_availability_change():
    _, availability = make_borrow()
    bundle = build_bundle("TESTD", [availability], "2026-03-01T12:00:00Z")
    result = build_input_sufficiency_result(bundle, "BORROW_AVAILABILITY_ABSOLUTE_CHANGE")
    assert result.structural_state is StructuralState.SUFFICIENT


def test_conflicted_required_input_yields_conflicted_state():
    a = make_short_interest(source_record_id="si-a", settlement_date="2026-01-15", short_shares="1000000")
    b = make_short_interest(source_record_id="si-b", settlement_date="2026-01-15", short_shares="2000000")
    bundle = build_bundle("TESTD", [a, b], "2026-03-01T12:00:00Z")
    result = build_input_sufficiency_result(
        bundle, "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE"
    )
    assert result.structural_state is StructuralState.CONFLICTED
    assert "domain:PUBLISHED_SHORT_INTEREST" in result.conflicted_inputs


def test_unknown_availability_yields_unknown_state():
    bundle = build_bundle("TESTD", [], "2026-03-01T12:00:00Z")
    result = build_input_sufficiency_result(bundle, "BORROW_FEE_ABSOLUTE_CHANGE")
    # BORROW_FEE is always-evaluated by Phase 1 (no include-flag gate), so with zero
    # input observations it resolves MISSING, not UNKNOWN -- exercise a genuinely
    # never-evaluated domain instead (MARKET_BARS with no bar observation supplied
    # and no include flag set).
    bundle_unknown = build_bundle("TESTD", [], "2026-03-01T12:00:00Z")
    result_unknown = build_input_sufficiency_result(bundle_unknown, "ABSOLUTE_RETURN")
    assert result_unknown.structural_state is StructuralState.UNKNOWN


def test_future_input_excluded_from_sufficiency():
    si = make_short_interest(publication_date="2026-04-01", settlement_date="2026-03-25")
    bundle = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    result = build_input_sufficiency_result(
        bundle, "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE"
    )
    assert si.observation_id not in result.input_observation_ids
    assert result.structural_state is StructuralState.INSUFFICIENT


def test_correction_after_as_of_excluded_before_correction_available_after():
    original = make_short_interest(
        source_record_id="si-orig", settlement_date="2026-01-15", short_shares="900000"
    )
    correction = make_short_interest(
        source_record_id="si-corr",
        settlement_date="2026-01-15",
        publication_date="2026-02-05",
        short_shares="950000",
        revision_status="CORRECTED",
        revision_number=1,
        supersedes_source_record_id="si-orig",
    )
    early_bundle = build_bundle("TESTD", [original, correction], "2026-01-26T00:00:00Z")
    later_bundle = build_bundle("TESTD", [original, correction], "2026-03-01T12:00:00Z")

    early_result = build_input_sufficiency_result(
        early_bundle, "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE"
    )
    later_result = build_input_sufficiency_result(
        later_bundle, "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE"
    )
    assert correction.observation_id not in early_result.input_observation_ids
    assert correction.observation_id in later_result.input_observation_ids


def test_no_downstream_metric_recalculation_import():
    import ast
    from pathlib import Path

    source = Path("src/squeeze_core/readiness/sufficiency.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_prefixes = ("build_return", "build_gap", "build_range", "build_days_to_cover")
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            assert not node.id.startswith(forbidden_prefixes)


def test_operation_policy_identity_stable():
    si = make_short_interest()
    bundle_a = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    bundle_b = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    a = build_input_sufficiency_result(bundle_a, "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE")
    b = build_input_sufficiency_result(bundle_b, "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE")
    assert a.deterministic_id == b.deterministic_id
    assert a.policy_version == b.policy_version


def test_structural_state_has_no_trading_readiness_values():
    assert {member.value for member in StructuralState} == {
        "SUFFICIENT",
        "INSUFFICIENT",
        "UNKNOWN",
        "CONFLICTED",
    }


def test_unsupported_operation_raises():
    bundle = build_bundle("TESTD", [], "2026-03-01T12:00:00Z")
    try:
        build_input_sufficiency_result(bundle, "COMPOSITE_SQUEEZE_SCORE")
        assert False, "expected UnsupportedOperationError"
    except UnsupportedOperationError:
        pass


def test_unsupported_policy_version_raises():
    bundle = build_bundle("TESTD", [], "2026-03-01T12:00:00Z")
    try:
        build_input_sufficiency_result(
            bundle, "ABSOLUTE_RETURN", policy_version="phase_2d_readiness_policy.v99"
        )
        assert False, "expected UnsupportedPolicyVersionError"
    except UnsupportedPolicyVersionError:
        pass
