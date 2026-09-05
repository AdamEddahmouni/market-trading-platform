from __future__ import annotations

from copy import deepcopy

import pytest

from apps.research_screener.methodologies.adam_v1 import evaluate_adam
from apps.research_screener.methodologies.evidence import EvidenceInput
from apps.research_screener.methodologies.legacy import evaluate_legacy
from apps.research_screener.methodologies.normalization import inverse_linear, linear
from apps.research_screener.methodologies.peer_reference import describe_peer
from apps.research_screener.methodologies.projection import (
    filter_projections,
    project_candidate,
    sort_projections,
)


UNITS = {
    "price": "PRICE",
    "today_percentage_change": "PERCENT",
    "published_short_interest_pct": "PERCENT",
    "days_to_cover": "DAYS",
    "cost_to_borrow": "PERCENT_ANNUALIZED",
    "borrow_availability_pct_float": "PERCENT_OF_FLOAT",
    "float_shares": "SHARES",
    "current_percentage_change": "PERCENT",
    "relative_volume": "RATIO",
    "completed_bar_acceleration": "PERCENTAGE_POINTS",
    "catalyst_age_hours": "HOURS",
    "short_float_pct": "PERCENT",
}


def evidence(
    key: str, value: float, *, admissible: bool = True, conflict: bool = False,
    unit: str | None = None,
):
    return EvidenceInput(
        key=key,
        value=value,
        unit=unit or UNITS[key],
        provider="Synthetic",
        provider_field=key,
        event_time="2026-07-25T16:00:00Z",
        received_time="2026-07-25T16:00:01Z",
        display_available=True,
        research_admissible=admissible,
        point_in_time_eligible=True,
        fresh=True,
        conflict=conflict,
        evidence_id=f"synthetic:{key}",
        selection_reason="ONLY_AVAILABLE",
    )


def full_adam_inputs() -> dict[str, EvidenceInput]:
    return {
        "published_short_interest_pct": evidence("published_short_interest_pct", 30),
        "days_to_cover": evidence("days_to_cover", 7),
        "cost_to_borrow": evidence("cost_to_borrow", 50),
        "borrow_availability_pct_float": evidence("borrow_availability_pct_float", 0.1),
        "float_shares": evidence("float_shares", 10_000_000),
        "current_percentage_change": evidence("current_percentage_change", 20),
        "relative_volume": evidence("relative_volume", 10),
        "completed_bar_acceleration": evidence("completed_bar_acceleration", 5),
        "catalyst_age_hours": evidence("catalyst_age_hours", 12),
    }


def test_normalizations_are_clamped_and_inverse():
    assert linear(-1, 0, 20) == 0
    assert linear(10, 0, 20) == 50
    assert linear(30, 0, 20) == 100
    assert inverse_linear(0.1, 0.1, 10) == 100
    assert inverse_linear(10, 0.1, 10) == 0


def test_legacy_requires_exact_admissible_inputs_and_never_substitutes_short_float():
    inputs = {
        "price": evidence("price", 10),
        "today_percentage_change": evidence("today_percentage_change", 12),
        "relative_volume": evidence("relative_volume", 6),
        "published_short_interest_pct": evidence("published_short_interest_pct", 8),
    }
    assert evaluate_legacy(inputs).classification == "PRIME"
    inputs["price"] = evidence("price", 21)
    assert evaluate_legacy(inputs).classification == "NOT_QUALIFIED"
    inputs.pop("published_short_interest_pct")
    inputs["short_float_pct"] = evidence("short_float_pct", 40)
    result = evaluate_legacy(inputs)
    assert result.classification == "UNEVALUABLE"
    assert result.pressure is None
    assert "published_short_interest_pct" in result.missing_inputs


def test_peer_reference_preserves_known_definition_without_inventing_scores():
    result = describe_peer({})
    assert result.classification == "REFERENCE_DEFINITION_INCOMPLETE"
    assert result.pressure is None and result.ignition is None
    assert result.metadata["pressure_weights"]["estimated_si_pct"] == 45
    assert result.metadata["ignition_weights"]["relative_volume"] == 40
    assert result.metadata["prime_thresholds"] == {"pressure_gte": 55, "ignition_gte": 50}
    assert "normalization_functions" in result.metadata["missing_definitions"]


def test_adam_full_evidence_is_prime_and_matches_preregistered_weights():
    result = evaluate_adam(full_adam_inputs())
    assert result.classification == "PRIME"
    assert result.pressure == 100
    assert result.ignition == 100
    assert result.evidence_coverage["category"] == "HIGH_COVERAGE"
    assert result.evidence_coverage["percent"] == 100.0
    assert result.evidence_coverage["total_fields_available"] == 9
    assert result.evidence_coverage["total_fields_required"] == 9
    assert result.metadata["pressure_supported_weight"] == 100
    assert result.metadata["ignition_supported_weight"] == 100
    assert result.metadata["weights_validated"] is True
    assert result.metadata["thresholds_optimal"] is True


def test_adam_field_coverage_percent_is_field_based_not_weight_average():
    result = evaluate_adam(full_adam_inputs())
    cov = result.evidence_coverage
    assert cov["field_coverage_percent"] == 100.0
    assert cov["weight_coverage_percent"] == 100.0


def test_adam_typical_scanner_profile_separates_field_and_weight_coverage():
    inputs = {
        "published_short_interest_pct": evidence("published_short_interest_pct", 30),
        "days_to_cover": evidence("days_to_cover", 7),
        "float_shares": evidence("float_shares", 10_000_000),
        "current_percentage_change": evidence("current_percentage_change", 20),
        "relative_volume": evidence("relative_volume", 10),
        "completed_bar_acceleration": evidence("completed_bar_acceleration", 5),
        "catalyst_age_hours": evidence("catalyst_age_hours", 12),
    }
    result = evaluate_adam(inputs)
    cov = result.evidence_coverage
    assert cov["total_fields_available"] == 7
    assert cov["percent"] == round(100.0 * 7 / 9, 1)
    assert cov["percent"] != 82.5
    assert cov["weight_coverage_percent"] == 82.5


def test_adam_withholds_below_seventy_percent_and_excludes_display_only():
    inputs = full_adam_inputs()
    for key in ("days_to_cover", "cost_to_borrow"):
        inputs[key] = evidence(key, inputs[key].value, admissible=False)
    result = evaluate_adam(inputs)
    assert result.pressure is None
    assert result.classification == "UNEVALUABLE"
    assert "days_to_cover" in result.metadata["display_only_inputs"]
    assert result.metadata["pressure_supported_weight"] == 55


def test_exact_unit_contract_blocks_semantically_incompatible_values():
    legacy = full_adam_inputs()
    legacy["price"] = evidence("price", 10, unit="SHARES")
    legacy["today_percentage_change"] = evidence("today_percentage_change", 12)
    assert evaluate_legacy(legacy).classification == "UNEVALUABLE"

    inputs = full_adam_inputs()
    inputs["relative_volume"] = evidence("relative_volume", 10, unit="PERCENT")
    result = evaluate_adam(inputs)
    assert result.ignition is None
    assert result.classification == "UNEVALUABLE"


def test_adam_critical_domain_and_material_conflict_precedence():
    inputs = full_adam_inputs()
    inputs.pop("published_short_interest_pct")
    assert evaluate_adam(inputs).pressure is None
    assert evaluate_adam(inputs).classification == "UNEVALUABLE"
    inputs = full_adam_inputs()
    inputs["cost_to_borrow"] = evidence("cost_to_borrow", 50, conflict=True)
    result = evaluate_adam(inputs)
    assert result.classification == "CONFLICTED"
    assert result.conflict_reasons


@pytest.mark.parametrize(
    ("pressure_value", "ignition_value", "expected"),
    [
        (100, 60, "SUBPRIME"),
        (60, 60, "WATCH"),
        (40, 40, "NOT_QUALIFIED"),
    ],
)
def test_adam_classification_thresholds(pressure_value, ignition_value, expected):
    inputs = full_adam_inputs()
    # All components in each dimension share the requested normalized value.
    pct = pressure_value
    inputs["published_short_interest_pct"] = evidence(
        "published_short_interest_pct", 5 + 25 * pct / 100
    )
    inputs["days_to_cover"] = evidence("days_to_cover", 1 + 6 * pct / 100)
    inputs["cost_to_borrow"] = evidence("cost_to_borrow", 2 + 48 * pct / 100)
    inputs["borrow_availability_pct_float"] = evidence(
        "borrow_availability_pct_float", 10 - 9.9 * pct / 100
    )
    inputs["float_shares"] = evidence("float_shares", 50_000_000 - 40_000_000 * pct / 100)
    ign = ignition_value
    inputs["current_percentage_change"] = evidence("current_percentage_change", 20 * ign / 100)
    inputs["relative_volume"] = evidence("relative_volume", 1 + 9 * ign / 100)
    inputs["completed_bar_acceleration"] = evidence(
        "completed_bar_acceleration", 5 * ign / 100
    )
    inputs["catalyst_age_hours"] = evidence(
        "catalyst_age_hours", 12 if ign >= 75 else 48 if ign >= 50 else 73
    )
    assert evaluate_adam(inputs).classification == expected


def test_projection_filters_and_sorts_without_mutating_candidates_and_missing_last():
    rows = [
        {"symbol": "B", "fields": {}, "discovery_source": "IBKR broad mover"},
        {"symbol": "A", "fields": {}, "discovery_source": "manual symbol"},
    ]
    before = deepcopy(rows)
    projected = [project_candidate(row) for row in rows]
    assert rows == before
    assert [row["symbol"] for row in sort_projections(projected, "pressure", False)] == ["A", "B"]
    assert [row["symbol"] for row in sort_projections(projected, "pressure", True)] == ["A", "B"]
    assert len(filter_projections(projected, classifications={"UNEVALUABLE"})) == 2
    assert rows == before


def test_result_contract_has_explicit_nulls_and_no_prohibited_keys():
    payload = evaluate_adam({}).as_dict()
    assert payload["pressure"] is None
    assert payload["ignition"] is None
    for key in ("probability", "expected_return", "trade_recommendation", "buy_signal"):
        assert key not in payload
