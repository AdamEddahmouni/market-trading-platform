"""Tests for the Phase 4 item 1.3 fit-report skeleton.

The skeleton implements the preregistered feasibility-gate ladder
(preregistration §8.1) and the honest NOT_CALIBRATED reporting contract (§8.2,
sprint item 1.3): failing gates are named, ``RESEARCH_ONLY`` slots are retained,
and nothing is force-flipped to ``CALIBRATED``. Structure only — no fitting, no
probabilities.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from squeeze_core.calibration.fit_report import (
    MINIMUM_NEGATIVE_EVENTS,
    MINIMUM_NON_EMPTY_EVALUATION_FOLDS,
    MINIMUM_POSITIVE_EVENTS,
    EvaluationStatus,
    FeasibilityGateId,
    FitReportSkeleton,
    HorizonSlotStatus,
    OutcomeCounts,
    Phase4Verdict,
    _counts_from_dataset,
    _counts_from_rows,
    build_fit_report_skeleton,
    evaluate_feasibility_gates,
    render_fit_report_markdown,
)
from squeeze_core.calibration.walkforward import (
    WalkForwardDiagnostics,
    WalkForwardFoldDiagnostics,
    boundary_observations_from_bytes,
    plan_walk_forward_folds,
    walk_forward_diagnostics,
)
from squeeze_core.research.models import CandidateCaseType, OutcomeLabel
from squeeze_core.research.serialization import deserialize_research_dataset


class _Row:
    """Lightweight stand-in for ``ResearchDatasetRow`` (only 3 fields read)."""

    def __init__(
        self,
        case_type: CandidateCaseType,
        outcome_label: OutcomeLabel,
        symbol: str = "TEST",
    ) -> None:
        self.case_type = case_type
        self.outcome_label = outcome_label
        self.symbol = symbol


def _diag(
    non_empty_evaluation_folds: int = 2,
    folds_with_empty_training: int = 2,
) -> WalkForwardDiagnostics:
    return WalkForwardDiagnostics(
        boundary_count=35,
        symbol_count=33,
        fold_count=non_empty_evaluation_folds,
        non_empty_evaluation_fold_count=non_empty_evaluation_folds,
        folds_with_empty_training=folds_with_empty_training,
        degenerate=False,
        degeneracy_reason=None,
        folds=(
            WalkForwardFoldDiagnostics(
                fold_index=0,
                train_boundary_count=0,
                evaluation_boundary_count=20,
                train_symbol_count=0,
                evaluation_symbol_count=19,
            ),
        ),
    )


def _real_report() -> FitReportSkeleton:
    """Build the skeleton from the committed fixtures (the runner's path)."""
    dataset = deserialize_research_dataset(
        (ROOT / "tests" / "fixtures" / "research" / "phase_3b_research_dataset.json")
        .read_bytes()
    )
    observations = []
    for path in sorted(
        (ROOT / "tests" / "fixtures" / "research").glob("*_outcome_observation.json")
    ):
        observations.extend(
            boundary_observations_from_bytes(path.read_bytes(), str(path))
        )
    diagnostics = walk_forward_diagnostics(plan_walk_forward_folds(observations))
    return build_fit_report_skeleton(_counts_from_dataset(dataset), diagnostics)


class OutcomeCountsTests(unittest.TestCase):
    def test_label_mapping_to_y1(self) -> None:
        counts = _counts_from_rows(
            [
                _Row(CandidateCaseType.ORIGINAL_PLATFORM_SURFACED, OutcomeLabel.SUBSTANTIAL_UPWARD_MOVE, "AAA"),
                _Row(CandidateCaseType.ORIGINAL_PLATFORM_SURFACED, OutcomeLabel.SUBSTANTIAL_UPWARD_MOVE, "BBB"),
                _Row(CandidateCaseType.ORIGINAL_PLATFORM_SURFACED, OutcomeLabel.NO_SUBSTANTIAL_UPWARD_MOVE, "CCC"),
                _Row(CandidateCaseType.ORIGINAL_PLATFORM_NOT_SURFACED, OutcomeLabel.SUBSTANTIAL_DOWNWARD_MOVE, "DDD"),
                _Row(CandidateCaseType.ORIGINAL_PLATFORM_NOT_SURFACED, OutcomeLabel.MIXED_OR_VOLATILE, "EEE"),
            ]
        )
        self.assertEqual(counts.positive_y1, 2)
        self.assertEqual(counts.negative_y1, 1)
        self.assertEqual(counts.downward_mirror, 1)
        self.assertEqual(counts.unevaluable, 1)
        self.assertEqual(counts.total_evaluable, 3)
        self.assertEqual(counts.unique_symbols, 5)

    def test_synthetic_rows_excluded(self) -> None:
        counts = _counts_from_rows(
            [
                _Row(CandidateCaseType.SYNTHETIC_EDGE_CASE, OutcomeLabel.SUBSTANTIAL_UPWARD_MOVE, "SYN_A"),
                _Row(CandidateCaseType.ORIGINAL_PLATFORM_SURFACED, OutcomeLabel.NO_SUBSTANTIAL_UPWARD_MOVE, "HIST"),
            ]
        )
        self.assertEqual(counts.positive_y1, 0)
        self.assertEqual(counts.negative_y1, 1)
        self.assertEqual(counts.unique_symbols, 1)

    def test_base_rate(self) -> None:
        self.assertAlmostEqual(
            OutcomeCounts(
                positive_y1=3, negative_y1=27, downward_mirror=5,
                unevaluable=0, total_evaluable=30, unique_symbols=33,
            ).positive_base_rate,
            0.1,
        )
        self.assertIsNone(
            OutcomeCounts(
                positive_y1=0, negative_y1=0, downward_mirror=0,
                unevaluable=2, total_evaluable=0, unique_symbols=2,
            ).positive_base_rate
        )

    def test_committed_fixture_counts(self) -> None:
        dataset = deserialize_research_dataset(
            (ROOT / "tests" / "fixtures" / "research" / "phase_3b_research_dataset.json")
            .read_bytes()
        )
        counts = _counts_from_dataset(dataset)
        self.assertEqual(counts.positive_y1, 3)
        self.assertEqual(counts.negative_y1, 27)
        self.assertEqual(counts.downward_mirror, 5)
        self.assertEqual(counts.total_evaluable, 30)
        self.assertEqual(counts.unique_symbols, 33)


class GateTests(unittest.TestCase):
    def test_thresholds_match_prereg(self) -> None:
        self.assertEqual(MINIMUM_POSITIVE_EVENTS, 10)
        self.assertEqual(MINIMUM_NEGATIVE_EVENTS, 10)
        self.assertEqual(MINIMUM_NON_EMPTY_EVALUATION_FOLDS, 2)

    def test_f1_fails_below_minimum(self) -> None:
        counts = OutcomeCounts(
            positive_y1=3, negative_y1=27, downward_mirror=5,
            unevaluable=0, total_evaluable=30, unique_symbols=33,
        )
        gate = evaluate_feasibility_gates(counts, _diag())[0][0]
        self.assertIs(gate.gate_id, FeasibilityGateId.F1_EVALUABLE_POSITIVES)
        self.assertFalse(gate.passed)
        self.assertIs(gate.status, EvaluationStatus.EVALUATED)
        self.assertIn("3 positives", gate.observed)

    def test_f2_passes_at_minimum(self) -> None:
        counts = OutcomeCounts(
            positive_y1=10, negative_y1=10, downward_mirror=0,
            unevaluable=0, total_evaluable=20, unique_symbols=20,
        )
        gates, _ = evaluate_feasibility_gates(counts, _diag(folds_with_empty_training=0))
        self.assertTrue(gates[0].passed)
        self.assertTrue(gates[1].passed)

    def test_f3_passes_at_two_folds_fails_at_one(self) -> None:
        counts = OutcomeCounts(
            positive_y1=10, negative_y1=10, downward_mirror=0,
            unevaluable=0, total_evaluable=20, unique_symbols=20,
        )
        gates, _ = evaluate_feasibility_gates(counts, _diag(non_empty_evaluation_folds=2))
        self.assertTrue(gates[2].passed)
        gates, _ = evaluate_feasibility_gates(counts, _diag(non_empty_evaluation_folds=1))
        self.assertFalse(gates[2].passed)

    def test_f4_not_structurally_decidable(self) -> None:
        counts = OutcomeCounts(
            positive_y1=10, negative_y1=10, downward_mirror=0,
            unevaluable=0, total_evaluable=20, unique_symbols=20,
        )
        gates, _ = evaluate_feasibility_gates(counts, _diag())
        f4 = gates[3]
        self.assertIs(f4.gate_id, FeasibilityGateId.F4_HORIZON_DATA)
        self.assertIsNone(f4.passed)
        self.assertIs(f4.status, EvaluationStatus.EVALUATED)
        self.assertIn("RESEARCH_ONLY", f4.observed)

    def test_f4_records_owned_multi_day_horizons(self) -> None:
        counts = OutcomeCounts(
            positive_y1=10, negative_y1=10, downward_mirror=0,
            unevaluable=0, total_evaluable=20, unique_symbols=20,
        )
        gates, coverage = evaluate_feasibility_gates(
            counts, _diag(), owned_multi_day_horizons=frozenset({3})
        )
        self.assertIn("owned multi-day horizons: [3]", gates[3].observed)
        owned = {c.horizon_days for c in coverage if c.owned_forward_path_data}
        self.assertEqual(owned, {1, 3})

    def test_ladder_order_matches_prereg_section_8_1(self) -> None:
        counts = OutcomeCounts(
            positive_y1=0, negative_y1=0, downward_mirror=0,
            unevaluable=0, total_evaluable=0, unique_symbols=0,
        )
        gates, _ = evaluate_feasibility_gates(counts, _diag())
        self.assertEqual(
            [gate.gate_id for gate in gates],
            [
                FeasibilityGateId.F1_EVALUABLE_POSITIVES,
                FeasibilityGateId.F2_EVALUABLE_NEGATIVES,
                FeasibilityGateId.F3_FOLD_STRUCTURE,
                FeasibilityGateId.F4_HORIZON_DATA,
            ],
        )


class SkeletonTests(unittest.TestCase):
    def test_real_cohort_fails_f1_only(self) -> None:
        report = _real_report()
        self.assertIs(report.verdict, Phase4Verdict.NOT_CALIBRATED)
        self.assertEqual(report.failing_gates, (FeasibilityGateId.F1_EVALUABLE_POSITIVES,))
        self.assertEqual(report.unevaluated_gates, (FeasibilityGateId.F4_HORIZON_DATA,))
        self.assertFalse(report.all_feasibility_gates_passed)
        self.assertIn("F-1", report.notes[0])

    def test_research_only_retained_and_no_fit(self) -> None:
        report = _real_report()
        self.assertTrue(report.research_only_retained)
        self.assertFalse(report.fit_attempted)
        self.assertTrue(
            all(
                c.slot_status is HorizonSlotStatus.RESEARCH_ONLY
                for c in report.horizon_coverage
            )
        )
        self.assertEqual(len(report.horizon_coverage), 5)

    def test_no_probability_or_metric_fields(self) -> None:
        report = _real_report()
        dump = json.loads(report.model_dump_json())
        forbidden = ("probab", "hazard", "brier", "slope", "intercept")
        for key in dump:
            self.assertFalse(
                any(word in key.lower() for word in forbidden),
                f"forbidden fitted-metric field: {key}",
            )

    def test_all_pass_still_blocks_on_section_10(self) -> None:
        counts = OutcomeCounts(
            positive_y1=10, negative_y1=10, downward_mirror=0,
            unevaluable=0, total_evaluable=20, unique_symbols=20,
        )
        report = build_fit_report_skeleton(
            counts, _diag(folds_with_empty_training=0)
        )
        self.assertTrue(report.all_feasibility_gates_passed)
        self.assertEqual(report.failing_gates, ())
        self.assertTrue(
            any("O-2" in blocker for blocker in report.fit_blocked_by)
        )
        self.assertFalse(any("feasibility:" in blocker for blocker in report.fit_blocked_by))

    def test_blocked_by_lists_owner_gates_and_failure(self) -> None:
        report = _real_report()
        self.assertEqual(len(report.fit_blocked_by), 5)
        self.assertIn("O-2", report.fit_blocked_by[0])
        self.assertIn("O-3", report.fit_blocked_by[1])
        self.assertIn("O-4", report.fit_blocked_by[2])
        self.assertIn("O-6", report.fit_blocked_by[3])
        self.assertIn("F-1", report.fit_blocked_by[4])

    def test_slot_status_uses_snapshot_contract_vocabulary(self) -> None:
        statuses = {status.value for status in HorizonSlotStatus}
        self.assertEqual(statuses, {"RESEARCH_ONLY", "CALIBRATED"})


class CommittedReportTests(unittest.TestCase):
    def test_committed_report_matches_regenerated(self) -> None:
        committed = (
            ROOT / "reports" / "calibration" / "phase_4_fit_report_skeleton.json"
        ).read_text(encoding="utf-8")
        parsed = FitReportSkeleton.model_validate_json(committed)
        self.assertEqual(parsed, _real_report())

    def test_committed_markdown_matches_regenerated(self) -> None:
        committed = (
            ROOT / "reports" / "calibration" / "phase_4_fit_report_skeleton.md"
        ).read_text(encoding="utf-8")
        self.assertEqual(committed, render_fit_report_markdown(_real_report()))


class MarkdownTests(unittest.TestCase):
    def test_names_failing_gate_and_retention(self) -> None:
        text = render_fit_report_markdown(_real_report())
        self.assertIn("Verdict: **NOT_CALIBRATED**", text)
        self.assertIn("RESEARCH_ONLY retained: **yes**", text)
        self.assertIn("Fit attempted: **no**", text)
        self.assertIn("**FAIL**", text)
        self.assertIn("| F-1 |", text)
        self.assertIn("| F-2 |", text)
        self.assertIn("| F-3 |", text)
        self.assertIn("NOT_EVALUABLE (owner data feasibility, O-1)", text)
        self.assertIn("`RESEARCH_ONLY`", text)

    def test_all_pass_markdown_has_no_fail_rows(self) -> None:
        counts = OutcomeCounts(
            positive_y1=10, negative_y1=10, downward_mirror=0,
            unevaluable=0, total_evaluable=20, unique_symbols=20,
        )
        report = build_fit_report_skeleton(counts, _diag(folds_with_empty_training=0))
        text = render_fit_report_markdown(report)
        self.assertNotIn("**FAIL**", text)
        self.assertIn("NOT_CALIBRATED", text)


if __name__ == "__main__":
    unittest.main()
