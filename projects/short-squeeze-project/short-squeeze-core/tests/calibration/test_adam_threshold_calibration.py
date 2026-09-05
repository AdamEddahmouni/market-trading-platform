"""Tests for live-screener Adam classification-threshold calibration."""

from __future__ import annotations

from pathlib import Path

import pytest

from apps.research_screener.methodologies.adam_calibration import (
    load_experiment,
    run_classification_threshold_sweep,
)
from apps.research_screener.methodologies.adam_v1 import (
    DEFAULT_CLASSIFICATION_THRESHOLDS,
    evaluate_adam,
)
from apps.research_screener.methodologies.evidence import EvidenceInput

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = (
    ROOT / "tests" / "fixtures" / "calibration" / "adam_classification_threshold_profiles.json"
)


def test_full_provider_prime_at_baseline_thresholds():
    experiment = load_experiment(FIXTURE)
    report = run_classification_threshold_sweep(experiment)
    baseline = next(v for v in report.variant_results if v.variant_id == "baseline")
    prime = next(
        row for row in baseline.profile_results if row.profile_id == "full_provider_prime"
    )
    assert prime.classification == "PRIME"
    assert prime.pressure == 100
    assert prime.ignition == 100


def test_finviz_core_subprime_at_baseline_not_prime():
    experiment = load_experiment(FIXTURE)
    report = run_classification_threshold_sweep(experiment)
    baseline = next(v for v in report.variant_results if v.variant_id == "baseline")
    finviz = next(
        row for row in baseline.profile_results
        if row.profile_id == "finviz_pressure_ignition_core"
    )
    assert finviz.classification == "SUBPRIME"
    assert finviz.pressure == 100
    assert finviz.ignition == 100


def test_moderate_coverage_strong_stays_subprime_at_baseline():
    experiment = load_experiment(FIXTURE)
    report = run_classification_threshold_sweep(experiment)
    baseline = next(v for v in report.variant_results if v.variant_id == "baseline")
    row = next(
        row for row in baseline.profile_results
        if row.profile_id == "moderate_coverage_strong"
    )
    assert row.classification == "SUBPRIME"
    assert row.coverage_category == "MODERATE_COVERAGE"


def test_lower_high_coverage_promotes_finviz_to_prime():
    experiment = load_experiment(FIXTURE)
    report = run_classification_threshold_sweep(experiment)
    lowered = next(
        v for v in report.variant_results if v.variant_id == "lower_high_coverage_65"
    )
    assert any(
        flip["profile_id"] == "finviz_pressure_ignition_core"
        and flip["variant_classification"] == "PRIME"
        for flip in lowered.flips_from_baseline
    )


def test_raise_prime_demotes_boundary_prime_profile():
    experiment = load_experiment(FIXTURE)
    report = run_classification_threshold_sweep(experiment)
    raised = next(v for v in report.variant_results if v.variant_id == "raise_prime_75")
    assert any(
        flip["profile_id"] == "prime_boundary_72"
        and flip["baseline_classification"] == "PRIME"
        and flip["variant_classification"] == "SUBPRIME"
        for flip in raised.flips_from_baseline
    )


def test_threshold_calibration_recommends_retain_baseline():
    experiment = load_experiment(FIXTURE)
    report = run_classification_threshold_sweep(experiment)
    assert report.recommendation["action"] == "RETAIN_BASELINE"
    assert report.recommendation["baseline_variant_id"] == "baseline"


def test_evaluate_adam_marks_thresholds_optimal_at_defaults():
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
    assert result.metadata["thresholds_optimal"] is True


def test_evaluate_adam_custom_thresholds_not_marked_optimal():
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
    custom = DEFAULT_CLASSIFICATION_THRESHOLDS
    lowered = type(custom)(
        prime_pressure_min=65,
        prime_ignition_min=65,
        subprime_primary_min=custom.subprime_primary_min,
        subprime_secondary_min=custom.subprime_secondary_min,
        watch_min=custom.watch_min,
        high_coverage_min=custom.high_coverage_min,
        moderate_coverage_min=custom.moderate_coverage_min,
        low_coverage_min=custom.low_coverage_min,
    )
    result = evaluate_adam(
        {"published_short_interest_pct": item},
        classification_thresholds=lowered,
    )
    assert result.metadata["thresholds_optimal"] is False
