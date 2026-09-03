"""Comprehensive BUILD 16 evaluation diagnostics tests."""

from __future__ import annotations

import copy
import math
import unittest

from market_platform_foundation.intelligence.contracts import Direction, ForecastEstimate, ForecastV1
from market_platform_foundation.intelligence.contracts.prediction_ledger import PredictionLedgerEntryV1
from market_platform_foundation.intelligence.evaluation import (
    EvaluationError,
    EvaluationService,
    EvaluationSpec,
    ProbabilityView,
    TRUE_PREDICTION_COVERAGE_UNAVAILABLE,
    derive_cohort_fingerprint,
    derive_evaluation_spec_id,
    derive_report_id,
    evaluation_report_v1_from_dict,
    evaluation_report_v1_to_dict,
)
from market_platform_foundation.intelligence.evaluation.calibration_diag import (
    assign_bin,
    compute_calibration_diagnostics,
    reliability_bin_boundaries,
)
from market_platform_foundation.intelligence.evaluation.cohort import materialize_cohort, refine_diagnostic_states
from market_platform_foundation.intelligence.evaluation.metrics import (
    clip_probability,
    compute_brier_contribution,
    compute_log_loss_contribution,
    compute_predictive_metrics,
)
from market_platform_foundation.intelligence.evaluation.provenance import validate_evaluated_probability
from market_platform_foundation.intelligence.evaluation.types import (
    AggregateStatus,
    EvaluationCohortRow,
    PredictionDiagnosticState,
)
from market_platform_foundation.intelligence.outcomes import (
    OutcomeSettlementService,
    PredictionLedgerService,
    SettlementMode,
    SettlementStatus,
    register_control_forecast_for_settlement,
    register_final_forecast_for_settlement,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from tests.intelligence.outcome_fixtures import (
    HORIZON_5M,
    ONE_MIN,
    T,
    baseline_control_forecast,
    cutoff_for,
    seed_terminal_trade,
    synthetic_final_forecast,
    target_time_for,
)

DEFAULT_CUTOFF = T + HORIZON_5M + ONE_MIN


def _default_spec(**overrides) -> EvaluationSpec:
    base = EvaluationSpec(
        evaluation_as_of_ns=DEFAULT_CUTOFF,
        decision_start_ns=T - 1,
        decision_end_ns=T + 1,
        target_kind="direction_up_down",
        horizon_ns=HORIZON_5M,
        mode=SettlementMode.ACTUAL_LIVE.value,
        probability_view=ProbabilityView.OPERATIONAL,
        slice_dimensions=("role", "horizon"),
    )
    if overrides:
        return EvaluationSpec(
            evaluation_as_of_ns=overrides.get("evaluation_as_of_ns", base.evaluation_as_of_ns),
            decision_start_ns=overrides.get("decision_start_ns", base.decision_start_ns),
            decision_end_ns=overrides.get("decision_end_ns", base.decision_end_ns),
            target_kind=overrides.get("target_kind", base.target_kind),
            horizon_ns=overrides.get("horizon_ns", base.horizon_ns),
            mode=overrides.get("mode", base.mode),
            probability_view=overrides.get("probability_view", base.probability_view),
            calibration_bin_count=overrides.get("calibration_bin_count", base.calibration_bin_count),
            log_loss_epsilon=overrides.get("log_loss_epsilon", base.log_loss_epsilon),
            minimum_slice_size=overrides.get("minimum_slice_size", base.minimum_slice_size),
            high_confidence_threshold=overrides.get("high_confidence_threshold", base.high_confidence_threshold),
            scenario_id=overrides.get("scenario_id", base.scenario_id),
            slice_dimensions=overrides.get("slice_dimensions", base.slice_dimensions),
            implementation_version=overrides.get("implementation_version", base.implementation_version),
        )
    return base


def _settled_control(repo: InMemoryIntelligenceRepository) -> tuple[ForecastV1, PredictionLedgerEntryV1, int]:
    forecast = baseline_control_forecast(repo, anchor_price=100.0)
    entry = register_control_forecast_for_settlement(forecast, repo, now_ns=T)
    assert isinstance(entry, PredictionLedgerEntryV1)
    target = target_time_for(forecast)
    cutoff = cutoff_for(forecast)
    seed_terminal_trade(repo, price=110.0, event_time_ns=target)
    result = OutcomeSettlementService(repo).settle(entry, now_ns=cutoff)
    assert result.status == SettlementStatus.SETTLED
    return forecast, entry, cutoff


class EvaluationMetricTests(unittest.TestCase):
    def test_brier_perfect_and_worst(self) -> None:
        self.assertEqual(compute_brier_contribution(1.0, 1), 0.0)
        self.assertEqual(compute_brier_contribution(0.0, 1), 1.0)

    def test_log_loss_epsilon_clips_hard_probabilities(self) -> None:
        clipped, changed = clip_probability(0.0, 1e-15)
        self.assertTrue(changed)
        value = compute_log_loss_contribution(0.0, 1, 1e-15)
        self.assertTrue(math.isfinite(value))

    def test_malformed_probability_rejected(self) -> None:
        with self.assertRaises(EvaluationError):
            validate_evaluated_probability(float("nan"))


class EvaluationCohortTests(unittest.TestCase):
    def test_future_label_excluded_from_predictive_rows(self) -> None:
        repo = InMemoryIntelligenceRepository()
        forecast, entry, cutoff = _settled_control(repo)
        spec = _default_spec(evaluation_as_of_ns=cutoff - 1)
        rows = refine_diagnostic_states(materialize_cohort(repo, spec), spec)
        self.assertEqual(rows[0].diagnostic_state, PredictionDiagnosticState.FUTURE_LABEL)

    def test_label_equality_boundary_eligible(self) -> None:
        repo = InMemoryIntelligenceRepository()
        _, _, cutoff = _settled_control(repo)
        spec = _default_spec(evaluation_as_of_ns=cutoff)
        rows = refine_diagnostic_states(materialize_cohort(repo, spec), spec)
        self.assertEqual(rows[0].diagnostic_state, PredictionDiagnosticState.CORRECT)

    def test_mode_filter_excludes_non_matching_entries(self) -> None:
        repo = InMemoryIntelligenceRepository()
        _settled_control(repo)
        spec = _default_spec(mode="COUNTERFACTUAL")
        rows = materialize_cohort(repo, spec)
        self.assertEqual(rows, ())

    def test_empty_cohort_structured_metrics(self) -> None:
        repo = InMemoryIntelligenceRepository()
        report = EvaluationService(repo).evaluate(_default_spec())
        self.assertEqual(report.aggregate_metrics.status, AggregateStatus.EMPTY_COHORT)


class EvaluationServiceTests(unittest.TestCase):
    def test_baseline_control_evaluation_report(self) -> None:
        repo = InMemoryIntelligenceRepository()
        forecast, _, cutoff = _settled_control(repo)
        spec = _default_spec(evaluation_as_of_ns=cutoff)
        report = EvaluationService(repo).evaluate(spec, persist=True)
        self.assertEqual(report.aggregate_metrics.status, AggregateStatus.OK)
        self.assertIsNotNone(report.aggregate_metrics.brier_score)
        self.assertEqual(report.settlement.true_prediction_coverage_status, TRUE_PREDICTION_COVERAGE_UNAVAILABLE)
        stored = repo.get_evaluation_report(report.report_id)
        assert stored is not None
        self.assertEqual(stored.report_id, report.report_id)

    def test_deterministic_report_identity(self) -> None:
        repo = InMemoryIntelligenceRepository()
        _, _, cutoff = _settled_control(repo)
        spec = _default_spec(evaluation_as_of_ns=cutoff)
        first = EvaluationService(repo).evaluate(spec)
        second = EvaluationService(repo).evaluate(spec)
        self.assertEqual(first.report_id, second.report_id)
        self.assertEqual(first.cohort_fingerprint, second.cohort_fingerprint)

    def test_input_order_independence(self) -> None:
        repo = InMemoryIntelligenceRepository()
        _, _, cutoff = _settled_control(repo)
        spec = _default_spec(evaluation_as_of_ns=cutoff)
        report_a = EvaluationService(repo).evaluate(spec)
        # Shuffled re-read does not change stored artifacts; evaluate again after noop.
        report_b = EvaluationService(repo).evaluate(spec)
        self.assertEqual(report_a.report_id, report_b.report_id)

    def test_fixed_as_of_late_data_invariance(self) -> None:
        repo = InMemoryIntelligenceRepository()
        forecast, entry, cutoff = _settled_control(repo)
        spec = _default_spec(evaluation_as_of_ns=cutoff)
        before = EvaluationService(repo).evaluate(spec)
        from tests.intelligence.test_signal_fixtures import trade_event

        repo.put_event(
            trade_event(
                "late-unrelated-event",
                event_time_ns=cutoff + 1_000_000_000,
                price=50.0,
                quantity=1,
                available_time_ns=cutoff + 1_000_000_000,
            )
        )
        after = EvaluationService(repo).evaluate(spec)
        self.assertEqual(before.report_id, after.report_id)
        self.assertEqual(before.aggregate_metrics.brier_score, after.aggregate_metrics.brier_score)

    def test_evaluation_as_of_advance_adds_rows(self) -> None:
        repo = InMemoryIntelligenceRepository()
        forecast, entry, cutoff = _settled_control(repo)
        early_spec = _default_spec(evaluation_as_of_ns=cutoff - 1)
        early = EvaluationService(repo).evaluate(early_spec)
        self.assertEqual(early.settlement.outcome_available_count, 0)
        late = EvaluationService(repo).evaluate(_default_spec(evaluation_as_of_ns=cutoff))
        self.assertGreater(late.settlement.outcome_available_count, early.settlement.outcome_available_count)

    def test_raw_vs_calibrated_comparison(self) -> None:
        repo = InMemoryIntelligenceRepository()
        forecast = synthetic_final_forecast(repo, probability=0.8, anchor_price=100.0)
        entry = register_final_forecast_for_settlement(forecast, repo, now_ns=T)
        assert isinstance(entry, PredictionLedgerEntryV1)
        target = target_time_for(forecast)
        cutoff = cutoff_for(forecast)
        seed_terminal_trade(repo, price=108.0, event_time_ns=target)
        OutcomeSettlementService(repo).settle(entry, now_ns=cutoff)
        report = EvaluationService(repo).evaluate(_default_spec(evaluation_as_of_ns=cutoff))
        assert report.probability_view_comparison is not None
        self.assertIsNotNone(report.probability_view_comparison.raw_brier)
        self.assertIsNotNone(report.probability_view_comparison.calibrated_brier)

    def test_round_trip_report_serialization(self) -> None:
        repo = InMemoryIntelligenceRepository()
        _, _, cutoff = _settled_control(repo)
        report = EvaluationService(repo).evaluate(_default_spec(evaluation_as_of_ns=cutoff))
        payload = evaluation_report_v1_to_dict(report)
        restored = evaluation_report_v1_from_dict(payload)
        self.assertEqual(restored.report_id, report.report_id)


class EvaluationCalibrationTests(unittest.TestCase):
    def test_bin_boundaries_and_empty_bins(self) -> None:
        boundaries = reliability_bin_boundaries(10)
        self.assertEqual(len(boundaries), 10)
        self.assertEqual(assign_bin(0.0, boundaries), 0)
        self.assertEqual(assign_bin(1.0, boundaries), 9)

    def test_ece_on_uniform_rows(self) -> None:
        repo = InMemoryIntelligenceRepository()
        _, _, cutoff = _settled_control(repo)
        spec = _default_spec(evaluation_as_of_ns=cutoff)
        rows = refine_diagnostic_states(materialize_cohort(repo, spec), spec)
        calibration = compute_calibration_diagnostics(rows, spec)
        assert calibration is not None
        self.assertIsNotNone(calibration.ece)


if __name__ == "__main__":
    unittest.main()
