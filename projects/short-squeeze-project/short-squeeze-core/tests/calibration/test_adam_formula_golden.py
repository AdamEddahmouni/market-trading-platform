"""Independently recompute ADAM weighted pressure/ignition from raw metrics."""

from __future__ import annotations

import json
from pathlib import Path

from apps.research_screener.methodologies.adam_v1 import PRESSURE, IGNITION, evaluate_adam
from apps.research_screener.methodologies.evidence import EvidenceInput
from apps.research_screener.methodologies.normalization import inverse_linear, linear

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "formulas" / "adam_weighted_pressure_ignition.json"

UNITS = {
    "published_short_interest_pct": "PERCENT",
    "days_to_cover": "DAYS",
    "cost_to_borrow": "PERCENT_ANNUALIZED",
    "borrow_availability_pct_float": "PERCENT_OF_FLOAT",
    "float_shares": "SHARES",
    "current_percentage_change": "PERCENT",
    "relative_volume": "RATIO",
    "completed_bar_acceleration": "PERCENTAGE_POINTS",
    "catalyst_age_hours": "HOURS",
}


def _item(key: str, value: float) -> EvidenceInput:
    return EvidenceInput(
        key=key,
        value=value,
        unit=UNITS[key],
        provider="Synthetic",
        provider_field=key,
        event_time="2026-08-17T12:00:00Z",
        received_time="2026-08-17T12:00:01Z",
        display_available=True,
        research_admissible=True,
        point_in_time_eligible=True,
        fresh=True,
        evidence_id=f"synthetic:{key}",
        selection_reason="ONLY_AVAILABLE",
    )


def _independent_score(policy: dict, raw: dict[str, float]) -> float:
    contribution = 0.0
    weight_sum = 0
    for key, (weight, normalize) in policy.items():
        contribution += weight * normalize(raw[key])
        weight_sum += weight
    return round(contribution / weight_sum, 1)


def test_adam_golden_vector_recomputes_weighted_dimensions():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    raw = payload["inputs"]
    expected_norm = payload["independent_normalized"]
    assert linear(raw["published_short_interest_pct"], 5, 30) == expected_norm["published_short_interest_pct"]
    assert linear(raw["days_to_cover"], 1, 7) == expected_norm["days_to_cover"]
    assert linear(raw["cost_to_borrow"], 2, 50) == expected_norm["cost_to_borrow"]
    assert inverse_linear(raw["borrow_availability_pct_float"], 0.1, 10) == expected_norm[
        "borrow_availability_pct_float"
    ]
    assert inverse_linear(raw["float_shares"], 10_000_000, 50_000_000) == expected_norm["float_shares"]
    assert linear(raw["current_percentage_change"], 0, 20) == expected_norm["current_percentage_change"]
    assert linear(raw["relative_volume"], 1, 10) == expected_norm["relative_volume"]
    assert linear(raw["completed_bar_acceleration"], 0, 5) == expected_norm["completed_bar_acceleration"]

    independent_pressure = _independent_score(PRESSURE, raw)
    independent_ignition = _independent_score(IGNITION, raw)
    assert independent_pressure == payload["expected_pressure"]
    assert independent_ignition == payload["expected_ignition"]

    inputs = {key: _item(key, value) for key, value in raw.items()}
    result = evaluate_adam(inputs)
    assert result.pressure == payload["expected_pressure"]
    assert result.ignition == payload["expected_ignition"]
    assert result.classification == payload["expected_classification"]
    assert result.pressure == independent_pressure
    assert result.ignition == independent_ignition
