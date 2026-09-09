"""Tests for the Phase 4 walk-forward scaffold (sprint item 1.2).

The scaffold is structural machinery only: chronological ordering, symbol
grouping (ADR-0054), purge/embargo windows (O-2 addendum), regime slices, and
the degeneracy gate (preregistration §7). No fitting, no probabilities.
"""

from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from squeeze_core.calibration.walkforward import (
    EMBARGO_CALENDAR_DAYS,
    PURGE_CALENDAR_DAYS,
    BoundaryObservation,
    RegimeSlice,
    WalkForwardInputError,
    boundary_observations_from_bytes,
    plan_walk_forward_folds,
    regime_slice_for_boundary,
    walk_forward_diagnostics,
)

FIXTURES = ROOT / "tests" / "fixtures"


def observation(
    case_id: str,
    symbol: str,
    boundary_time: datetime,
) -> BoundaryObservation:
    return BoundaryObservation(case_id=case_id, symbol=symbol, boundary_time=boundary_time)


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


class RegimeSliceUnitTests(unittest.TestCase):
    def test_pre_registered_cutpoints_match_the_o2_addendum(self) -> None:
        self.assertEqual(PURGE_CALENDAR_DAYS, 30)
        self.assertEqual(EMBARGO_CALENDAR_DAYS, 15)
        # Half-open [start, end): a boundary exactly at a cutpoint belongs to
        # the later slice (O-2 addendum §3 membership rule).
        self.assertIs(
            regime_slice_for_boundary(utc(2019, 12, 31, 23, 59)),
            RegimeSlice.PRE_2020,
        )
        self.assertIs(
            regime_slice_for_boundary(utc(2020, 1, 1)), RegimeSlice.MEME_REGIME
        )
        self.assertIs(
            regime_slice_for_boundary(utc(2022, 3, 16)), RegimeSlice.HIGH_RATE
        )
        self.assertIs(
            regime_slice_for_boundary(utc(2024, 9, 18)), RegimeSlice.POST_NORMALIZATION
        )

    def test_partition_is_exhaustive(self) -> None:
        probes = [
            utc(1999, 6, 1),
            utc(2020, 7, 1),
            utc(2023, 1, 1),
            utc(2025, 12, 31),
            utc(2026, 7, 18, 13, 37, 55),
        ]
        assigned = [regime_slice_for_boundary(probe) for probe in probes]
        self.assertNotIn(RegimeSlice.UNASSIGNED, assigned)

    def test_naive_boundary_time_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            regime_slice_for_boundary(datetime(2024, 9, 18))


class PlanningUnitTests(unittest.TestCase):
    def test_empty_input_is_rejected(self) -> None:
        with self.assertRaises(WalkForwardInputError):
            plan_walk_forward_folds([])

    def test_negative_windows_are_rejected(self) -> None:
        with self.assertRaises(WalkForwardInputError):
            plan_walk_forward_folds(
                [observation("A1", "AAA", utc(2026, 1, 1))], purge_calendar_days=-1
            )

    def test_symbol_cluster_never_straddles_a_fold(self) -> None:
        # AAA has three dependent boundaries (ADR-0054); all must land in the
        # same evaluation fold even though other symbols separate them.
        boundaries = [
            observation("AAA_EARLIEST", "AAA", utc(2026, 1, 5, 12)),
            observation("BBB_ONLY", "BBB", utc(2026, 1, 5, 13)),
            observation("AAA_LATEST", "AAA", utc(2026, 1, 5, 14)),
            observation("CCC_ONLY", "CCC", utc(2026, 2, 10)),
        ]
        plan = plan_walk_forward_folds(boundaries)
        aaa_folds = {
            fold.fold_index
            for fold in plan.folds
            if "AAA" in fold.evaluation_symbols
        }
        self.assertEqual(len(aaa_folds), 1)
        self.assertEqual(len(plan.symbol_groups), 3)
        self.assertIn(("AAA_EARLIEST", "AAA_LATEST"), plan.symbol_groups)

    def test_purge_and_embargo_exclude_training_boundaries(self) -> None:
        # Evaluation at Mar 20: a boundary on Feb 15 sits inside the 30-day
        # purge window (excluded), a boundary on Feb 3 sits inside the 15-day
        # embargo window beyond it (excluded), a boundary on Jan 10 is beyond
        # both windows (admissible training data).
        boundaries = [
            observation("IN_PURGE", "BBB", utc(2026, 2, 15)),
            observation("IN_EMBARGO", "CCC", utc(2026, 2, 3, 12)),
            observation("ADMISSIBLE", "AAA", utc(2026, 1, 10)),
            observation("EVAL", "DDD", utc(2026, 3, 20)),
        ]
        plan = plan_walk_forward_folds(boundaries)
        final_fold = plan.folds[-1]
        self.assertEqual(final_fold.evaluation_symbols, ("DDD",))
        self.assertEqual(final_fold.train_symbols, ("AAA",))
        self.assertEqual(len(final_fold.train_boundary_indices), 1)
        # Window arithmetic: purge [E-30, E), embargo [E-45, E-30).
        self.assertEqual(final_fold.purge_window_start, utc(2026, 2, 18))
        self.assertEqual(final_fold.purge_window_end, utc(2026, 3, 20))
        self.assertEqual(final_fold.embargo_window_start, utc(2026, 2, 3))
        self.assertEqual(final_fold.embargo_window_end, utc(2026, 2, 18))

    def test_expanding_window_releases_cleared_clusters_to_training(self) -> None:
        # An earlier evaluation cluster re-enters training once its label
        # window clears the w + e gap — necessary at this sample size.
        boundaries = [
            observation("EARLY_A", "AAA", utc(2026, 1, 1)),
            observation("EARLY_B", "BBB", utc(2026, 1, 2)),
            observation("LATE", "CCC", utc(2026, 3, 20)),
        ]
        plan = plan_walk_forward_folds(boundaries)
        final_fold = plan.folds[-1]
        self.assertEqual(final_fold.evaluation_symbols, ("CCC",))
        self.assertIn("AAA", final_fold.train_symbols)
        self.assertIn("BBB", final_fold.train_symbols)

    def test_training_symbols_never_overlap_evaluation_symbols(self) -> None:
        boundaries = [
            observation("A1", "AAA", utc(2026, 1, 1)),
            observation("A2", "AAA", utc(2026, 1, 2)),
            observation("B1", "BBB", utc(2026, 2, 15)),
            observation("C1", "CCC", utc(2026, 3, 20)),
            observation("D1", "DDD", utc(2026, 4, 25)),
        ]
        plan = plan_walk_forward_folds(boundaries)
        for fold in plan.folds:
            self.assertEqual(
                set(fold.train_symbols) & set(fold.evaluation_symbols), set()
            )

    def test_degeneracy_gate_flags_single_boundary_instant(self) -> None:
        # All boundaries at one instant: the chronological partition yields a
        # single evaluation fold — degenerate, and never re-shuffled.
        instant = utc(2026, 7, 18, 13, 37, 55)
        boundaries = [
            observation("A1", "AAA", instant),
            observation("B1", "BBB", instant),
            observation("C1", "CCC", instant),
        ]
        plan = plan_walk_forward_folds(boundaries)
        self.assertTrue(plan.degenerate)
        self.assertIsNotNone(plan.degeneracy_reason)
        self.assertIn("minimum is 2", plan.degeneracy_reason)

    def test_two_disjoint_instant_clusters_are_not_degenerate(self) -> None:
        boundaries = [
            observation("A1", "AAA", utc(2026, 1, 1)),
            observation("B1", "BBB", utc(2026, 3, 1)),
        ]
        plan = plan_walk_forward_folds(boundaries)
        self.assertFalse(plan.degenerate)
        self.assertEqual(len(plan.folds), 2)

    def test_plan_is_serializable(self) -> None:
        boundaries = [
            observation("A1", "AAA", utc(2026, 1, 1)),
            observation("B1", "BBB", utc(2026, 3, 1)),
        ]
        plan = plan_walk_forward_folds(boundaries)
        payload = json.loads(json.dumps(plan.model_dump(mode="json")))
        self.assertEqual(payload["harness_version"], "phase_4_walkforward_harness.v1")
        self.assertEqual(payload["purge_calendar_days"], 30)
        self.assertEqual(payload["embargo_calendar_days"], 15)


class LoaderUnitTests(unittest.TestCase):
    def test_single_observation_fixture_parses(self) -> None:
        path = FIXTURES / "research" / "aacb_outcome_observation.json"
        observations = boundary_observations_from_bytes(
            path.read_bytes(), source_path=str(path)
        )
        self.assertEqual(len(observations), 1)
        item = observations[0]
        self.assertEqual(item.case_id, "AACB_ARTIFACT_DISCOVERY")
        self.assertEqual(item.symbol, "AACB")
        self.assertEqual(item.boundary_time.tzinfo, timezone.utc)
        self.assertEqual(item.source_path, str(path))

    def test_array_payload_parses(self) -> None:
        payload = json.dumps(
            [
                {
                    "case_id": "X1",
                    "symbol": "XXX",
                    "detection_boundary": "2026-01-01T12:00:00Z",
                    "reference_price_policy": "first_eligible_trade_bar_close_at_or_after_boundary.v1",
                    "horizon": "24_HOURS",
                    "completeness": "COMPLETE",
                },
                {
                    "case_id": "Y1",
                    "symbol": "YYY",
                    "detection_boundary": "2026-02-01T12:00:00Z",
                    "reference_price_policy": "first_eligible_trade_bar_close_at_or_after_boundary.v1",
                    "horizon": "24_HOURS",
                    "completeness": "PARTIAL",
                },
            ]
        ).encode("utf-8")
        observations = boundary_observations_from_bytes(payload)
        self.assertEqual([item.case_id for item in observations], ["X1", "Y1"])

    def test_incomplete_payload_is_rejected(self) -> None:
        with self.assertRaises(Exception):
            boundary_observations_from_bytes(b'{"case_id": "X1", "symbol": "XXX"}')


class CommittedCohortStructureTests(unittest.TestCase):
    """The committed 35-boundary historical set, split by the fixed rules."""

    def setUp(self) -> None:
        observations: list[BoundaryObservation] = []
        for path in sorted((FIXTURES / "research").glob("*_outcome_observation.json")):
            observations.extend(boundary_observations_from_bytes(path.read_bytes(), str(path)))
        self.observations = observations
        self.plan = plan_walk_forward_folds(observations)
        self.diagnostics = walk_forward_diagnostics(self.plan)

    def test_committed_historical_cohort_is_thirty_five_boundaries(self) -> None:
        self.assertEqual(self.diagnostics.boundary_count, 35)
        self.assertEqual(self.diagnostics.symbol_count, 33)

    def test_biya_cluster_is_grouped(self) -> None:
        biya_groups = [
            group for group in self.plan.symbol_groups if any(g.startswith("BIYA") for g in group)
        ]
        self.assertEqual(len(biya_groups), 1)
        self.assertEqual(len(biya_groups[0]), 3)

    def test_structure_is_reported_honestly(self) -> None:
        diag = self.diagnostics
        # Regime counts: every owned boundary is post-normalization (O-2
        # addendum slices; recorded, never padded).
        self.assertEqual(
            diag.regime_counts.get(RegimeSlice.POST_NORMALIZATION), 35
        )
        self.assertEqual(
            set(diag.empty_regimes),
            {RegimeSlice.PRE_2020, RegimeSlice.MEME_REGIME, RegimeSlice.HIGH_RATE},
        )
        # Two boundary instants ~30 days apart: two evaluation folds (exactly
        # the prereg §7 minimum) and no admissible training boundaries in
        # either fold — the fact item 1.3 must report honestly.
        self.assertEqual(diag.fold_count, 2)
        self.assertEqual(diag.non_empty_evaluation_fold_count, 2)
        self.assertFalse(diag.degenerate)
        self.assertEqual(diag.folds_with_empty_training, 2)
        self.assertTrue(
            all(fold.train_boundary_count == 0 for fold in diag.folds)
        )
        self.assertTrue(
            all(not fold.train_symbol_overlap for fold in diag.folds)
        )

    def test_limitations_are_carried_on_the_report(self) -> None:
        self.assertIn(
            "HISTORICAL_CASE_BOUNDARIES_NOT_INDEPENDENT", self.diagnostics.limitations
        )
        self.assertIn("STRUCTURE_ONLY_NO_FIT_NO_PROBABILITY", self.diagnostics.limitations)

    def test_diagnostics_carry_no_probability_fields(self) -> None:
        payload = self.diagnostics.model_dump(mode="json")
        forbidden = {"probability", "brier", "pr_auc", "log_loss", "label", "outcome"}
        for key in payload:
            self.assertNotIn(key, forbidden)
        for fold in payload["folds"]:
            for key in fold:
                self.assertNotIn(key, forbidden)


if __name__ == "__main__":
    unittest.main()
