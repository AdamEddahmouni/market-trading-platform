from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from squeeze_core.adapters.market_bars import BarInterval
from squeeze_core.contracts import AssetClass, Quality, QualityState
from squeeze_core.metrics import MetricName, MetricResult, MetricUnit, ProviderScopeMode
from squeeze_core.serialization import canonical_json_bytes

AS_OF = datetime(2026, 1, 20, 22, 0, tzinfo=UTC)


def _known_value_result(**overrides) -> MetricResult:
    values = dict(
        metric_name=MetricName.ABSOLUTE_RETURN,
        metric_version="1.0.0",
        calculation_policy_version="close_to_close_completed.v1",
        symbol="TESTA",
        asset_class=AssetClass.EQUITY,
        as_of=AS_OF,
        source_interval=BarInterval.ONE_DAY,
        provider_scope=ProviderScopeMode.SINGLE_PROVIDER,
        value=Decimal("1.00"),
        unit=MetricUnit.PRICE,
        quality=Quality(state=QualityState.KNOWN_VALUE),
    )
    values.update(overrides)
    return MetricResult(**values)


def test_result_is_frozen_and_rejects_unknown_fields():
    result = _known_value_result()
    with pytest.raises(ValidationError):
        result.value = Decimal("2.00")
    with pytest.raises(ValidationError):
        _known_value_result(unexpected_field="nope")


def test_known_value_requires_a_value():
    with pytest.raises(ValidationError):
        _known_value_result(value=None)


def test_non_known_value_forbids_a_value():
    with pytest.raises(ValidationError):
        _known_value_result(
            value=Decimal("1.00"),
            quality=Quality(state=QualityState.UNAVAILABLE, reasons=("x",)),
        )


def test_non_known_value_with_none_value_is_valid():
    result = _known_value_result(value=None, quality=Quality(state=QualityState.UNAVAILABLE, reasons=("x",)))
    assert result.value is None


def test_deterministic_id_assigned_when_absent():
    result = _known_value_result()
    assert result.deterministic_id is not None


def test_deterministic_id_stable_for_identical_identity():
    first = _known_value_result()
    second = _known_value_result()
    assert first.deterministic_id == second.deterministic_id


@pytest.mark.parametrize(
    "override",
    [
        {"metric_name": MetricName.PERCENTAGE_RETURN, "unit": MetricUnit.PERCENT},
        {"metric_version": "2.0.0"},
        {"calculation_policy_version": "other.v1"},
        {"symbol": "OTHER"},
        {"as_of": datetime(2026, 1, 21, 22, 0, tzinfo=UTC)},
        {"source_interval": BarInterval.ONE_MINUTE},
        {"provider": "ALPACA_SHAPED"},
    ],
)
def test_deterministic_id_changes_when_identity_field_changes(override):
    baseline = _known_value_result()
    changed = _known_value_result(**override)
    assert baseline.deterministic_id != changed.deterministic_id


def test_deterministic_id_does_not_change_when_only_value_changes():
    a = _known_value_result(value=Decimal("1.00"))
    b = _known_value_result(value=Decimal("2.00"))
    assert a.deterministic_id == b.deterministic_id


def test_deterministic_id_does_not_change_when_only_diagnostics_change():
    from squeeze_core.metrics import MetricDiagnostic, MetricDiagnosticCode

    a = _known_value_result()
    b = _known_value_result(
        diagnostics=(
            MetricDiagnostic(
                code=MetricDiagnosticCode.RETURN_IDENTICAL_INPUT_BAR, severity="INFO", message="x"
            ),
        )
    )
    assert a.deterministic_id == b.deterministic_id


def test_input_observation_ids_are_sorted():
    result = _known_value_result(input_observation_ids=("zzz", "aaa", "mmm"))
    assert result.input_observation_ids == ("aaa", "mmm", "zzz")


def test_canonical_serialization_is_idempotent_and_order_stable():
    result = _known_value_result()
    first = canonical_json_bytes(result)
    second = canonical_json_bytes(result)
    assert first == second


def test_two_field_identical_results_serialize_byte_identical():
    a = _known_value_result()
    b = _known_value_result()
    assert canonical_json_bytes(a) == canonical_json_bytes(b)


def test_metric_name_values_are_stable():
    assert MetricName.ABSOLUTE_RETURN.value == "ABSOLUTE_RETURN"
    assert MetricName.PERCENTAGE_RETURN.value == "PERCENTAGE_RETURN"
    assert MetricName.ABSOLUTE_SESSION_GAP.value == "ABSOLUTE_SESSION_GAP"
    assert MetricName.PERCENTAGE_SESSION_GAP.value == "PERCENTAGE_SESSION_GAP"
    assert MetricName.ABSOLUTE_BAR_RANGE.value == "ABSOLUTE_BAR_RANGE"
    assert MetricName.PERCENTAGE_BAR_RANGE.value == "PERCENTAGE_BAR_RANGE"
    assert MetricName.MEAN_VOLUME_BASELINE.value == "MEAN_VOLUME_BASELINE"


def test_provider_scope_mode_values_are_stable():
    assert ProviderScopeMode.SINGLE_PROVIDER.value == "SINGLE_PROVIDER"
    assert ProviderScopeMode.EXPLICIT_PROVIDER_SET_PRESERVED_SEPARATELY.value == (
        "EXPLICIT_PROVIDER_SET_PRESERVED_SEPARATELY"
    )
