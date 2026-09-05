"""Tests for live-screener Adam weight-floor calibration."""

from __future__ import annotations

from pathlib import Path

import pytest

from apps.research_screener.methodologies.adam_calibration import (
    load_experiment,
    run_weight_floor_sweep,
)
from apps.research_screener.methodologies.adam_v1 import MIN_DIMENSION_WEIGHT, evaluate_adam
from apps.research_screener.methodologies.evidence import EvidenceInput

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "calibration" / "adam_live_evidence_profiles.json"


def test_finviz_core_profile_evaluable_at_baseline_floor():
    experiment = load_experiment(FIXTURE)
    report = run_weight_floor_sweep(experiment)
    baseline = next(
        v for v in report.variant_results
        if v.min_dimension_weight == MIN_DIMENSION_WEIGHT
    )
    finviz = next(
        row for row in baseline.profile_results
        if row.profile_id == "finviz_pressure_ignition_core"
    )
    assert finviz.evaluable
    assert finviz.pressure is not None
    assert finviz.ignition is not None
    assert finviz.pressure_supported_weight == 65
    assert finviz.ignition_supported_weight == 65


def test_pressure_si_dtc_only_unevaluable_at_baseline():
    experiment = load_experiment(FIXTURE)
    report = run_weight_floor_sweep(experiment)
    baseline = next(
        v for v in report.variant_results
        if v.min_dimension_weight == MIN_DIMENSION_WEIGHT
    )
    partial = next(
        row for row in baseline.profile_results
        if row.profile_id == "pressure_si_dtc_only"
    )
    assert partial.pressure_supported_weight == 55
    assert not partial.evaluable
    assert partial.classification == "UNEVALUABLE"


def test_lowering_floor_flips_partial_pressure_profile():
    experiment = load_experiment(FIXTURE)
    report = run_weight_floor_sweep(experiment)
    lowered = next(v for v in report.variant_results if v.min_dimension_weight == 55)
    assert any(
        flip["profile_id"] == "pressure_si_dtc_only"
        for flip in lowered.flips_from_baseline
    )


def test_calibration_recommends_retain_baseline():
    experiment = load_experiment(FIXTURE)
    report = run_weight_floor_sweep(experiment)
    assert report.recommendation["action"] == "RETAIN_BASELINE"
    assert report.recommendation["baseline_min_dimension_weight"] == 65


def test_evaluate_adam_marks_weights_validated_at_default_floor():
    item = EvidenceInput(
        key="published_short_interest_pct",
        value=30,
        unit="PERCENT",
        provider="Synthetic",
        provider_field="published_short_interest_pct",
        event_time="2026-08-17T12:00:00Z",
        received_time="2026-08-17T12:00:01Z",
        display_available=True,
        research_admissible=True,
        point_in_time_eligible=True,
        fresh=True,
        evidence_id="synthetic:si",
        selection_reason="ONLY_AVAILABLE",
    )
    result = evaluate_adam({"published_short_interest_pct": item})
    assert result.metadata["weights_validated"] is True
    assert result.metadata["min_dimension_weight"] == MIN_DIMENSION_WEIGHT


def test_evaluate_adam_custom_floor_not_marked_validated():
    item = EvidenceInput(
        key="published_short_interest_pct",
        value=30,
        unit="PERCENT",
        provider="Synthetic",
        provider_field="published_short_interest_pct",
        event_time="2026-08-17T12:00:00Z",
        received_time="2026-08-17T12:00:01Z",
        display_available=True,
        research_admissible=True,
        point_in_time_eligible=True,
        fresh=True,
        evidence_id="synthetic:si",
        selection_reason="ONLY_AVAILABLE",
    )
    result = evaluate_adam(
        {"published_short_interest_pct": item},
        min_dimension_weight=50,
    )
    assert result.metadata["weights_validated"] is False
