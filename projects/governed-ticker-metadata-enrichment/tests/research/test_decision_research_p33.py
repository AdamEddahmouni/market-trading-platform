"""P3.3 decision research tests.

Contains the P3.3 structural tests and, since DECISION-RESEARCH-001 Task 6,
:class:`EvaluateExperimentCardContractP33` — the card-driven, OOS-only contract
that replaced the legacy hard-coded 5/20 thresholds. The OOS-only runner
semantics (no in-sample TRAIN evaluation) are pinned here too.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.research.decision_research import (
    SHORT_SQUEEZE_EXPERIMENTS,
    reject_historical_finviz_screen_without_capture,
    run_short_squeeze_family,
    validate_temporal_example,
)
from market_platform_foundation.research.decision_research.examples import build_ss_family_examples
from market_platform_foundation.research.decision_research.experiments import evaluate_experiment
from market_platform_foundation.research.decision_research.pit_gate import chronological_split
from market_platform_foundation.research.decision_research.ss_cards import build_ss_family_cards


def _valid_example(*, decision_time_ns: int, positive: bool) -> dict:
    """Build a PIT-valid example: features before decision, outcome after."""
    return {
        "decision_time_ns": decision_time_ns,
        "features": [
            {
                "available_time_ns": decision_time_ns - 100,
                "evidence_family": "SQUEEZE_STATE",
            }
        ],
        "outcome_time_ns": decision_time_ns + 5000,
        "outcome": {"positive": positive},
    }


def _make_examples(n: int, *, positive_from: int = 0) -> list[dict]:
    """``n`` PIT-valid examples; examples[i] is positive when ``i >= positive_from``."""
    return [
        _valid_example(decision_time_ns=(i + 1) * 1000, positive=i >= positive_from)
        for i in range(n)
    ]


class DecisionResearchP33Tests(unittest.TestCase):
    def test_feature_after_decision_rejected(self) -> None:
        example = {
            "decision_time_ns": 1000,
            "features": [{"available_time_ns": 2000, "evidence_family": "CVD"}],
            "outcome_time_ns": 5000,
        }
        ok, reasons = validate_temporal_example(example)
        self.assertFalse(ok)
        self.assertTrue(any("FEATURE_AFTER_DECISION" in r for r in reasons))

    def test_outcome_must_be_after_decision(self) -> None:
        example = {
            "decision_time_ns": 5000,
            "features": [{"available_time_ns": 1000}],
            "outcome_time_ns": 1000,
        }
        ok, reasons = validate_temporal_example(example)
        self.assertFalse(ok)
        self.assertIn("OUTCOME_BEFORE_DECISION", reasons)

    def test_current_finviz_screen_cannot_be_historical(self) -> None:
        ok, reason = reject_historical_finviz_screen_without_capture(
            feature_source="FINVIZ_SCREEN",
            capture_present=False,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "NO_RETROACTIVE_FINVIZ_SCREEN_RECONSTRUCTION")

    def test_baseline_required_in_family(self) -> None:
        examples = [
            {
                "decision_time_ns": i * 1000,
                "features": [{"available_time_ns": i * 1000 - 100, "evidence_family": "SQUEEZE_STATE"}],
                "outcome_time_ns": i * 1000 + 5000,
                "outcome": {"positive": i % 2 == 0},
            }
            for i in range(1, 25)
        ]
        result = run_short_squeeze_family(examples)
        self.assertEqual(result["execution_authority"], "NONE")
        self.assertFalse(result["auto_strategy_promotion"])
        self.assertTrue(any(ex["experiment_id"] == "SS-BASE" for ex in result["experiments"]))

    def test_temporal_split(self) -> None:
        examples = [{"decision_time_ns": i} for i in range(10)]
        splits = chronological_split(examples)
        self.assertGreater(len(splits["train"]), 0)

    def test_tiny_nonempty_pool_is_prospective(self) -> None:
        # One evidence-bearing example: non-empty pool below min_sample_oos =>
        # NEEDS_PROSPECTIVE_VALIDATION (Task 6 semantics; there is evidence to
        # gather more of, unlike a truly empty pool).
        examples = [
            {
                "decision_time_ns": 1000,
                "features": [{"available_time_ns": 900, "evidence_family": "SQUEEZE_STATE"}],
                "outcome_time_ns": 2000,
                "outcome": {"positive": True},
            }
        ]
        result = run_short_squeeze_family(examples)
        ss_base = next(r for r in result["experiments"] if r["experiment_id"] == "SS-BASE")
        self.assertEqual(ss_base["status"], "NEEDS_PROSPECTIVE_VALIDATION")
        self.assertEqual(ss_base["metrics"]["pool_count"], 1)

    def test_no_auto_strategy_promotion(self) -> None:
        result = run_short_squeeze_family([])
        for row in result["experiments"]:
            self.assertEqual(row.get("strategy_promotion"), "NONE")


class EvaluateExperimentCardContractP33(unittest.TestCase):
    """Task 6 card-driven, OOS-only evaluation contract.

    Replaces the pre-milestone legacy lock (hard-coded 5/20 thresholds and the
    in-sample TRAIN-split runner). Status now derives from each card's
    ``min_sample_oos`` / ``primary_metric`` / ``primary_metric_threshold`` on
    the OOS subset only.
    """

    CARDS = build_ss_family_cards()

    # -- fail-closed card requirement ----------------------------------------
    def test_requires_experiment_card_fail_closed(self) -> None:
        # Passing a legacy ResearchHypothesis (not a card) must be rejected.
        with self.assertRaises(ValueError):
            evaluate_experiment(SHORT_SQUEEZE_EXPERIMENTS["SS-BASE"], _make_examples(5))

    def test_registered_card_enforced_when_registry_given(self) -> None:
        import tempfile

        from market_platform_foundation.research.decision_research.registry import (
            ExperimentCardRegistry,
        )

        with tempfile.TemporaryDirectory() as tmp:
            registry = ExperimentCardRegistry(Path(tmp))
            card = self.CARDS["SS-BASE"]
            with self.assertRaises(ValueError):
                evaluate_experiment(card, _make_examples(10), registry=registry)
            registry.register(card)
            result = evaluate_experiment(card, _make_examples(10), registry=registry)
            self.assertEqual(result["experiment_id"], "SS-BASE")

    # -- status boundaries from min_sample_oos --------------------------------
    def test_empty_subset_insufficient_data(self) -> None:
        result = evaluate_experiment(self.CARDS["SS-BASE"], [])
        self.assertEqual(result["status"], "INSUFFICIENT_DATA")
        self.assertEqual(result["sample_count"], 0)

    def test_below_min_sample_is_prospective(self) -> None:
        # SS-BASE min_sample_oos = 150; 5 positive PIT-valid OOS examples.
        result = evaluate_experiment(self.CARDS["SS-BASE"], _make_examples(5, positive_from=0))
        self.assertEqual(result["status"], "NEEDS_PROSPECTIVE_VALIDATION")
        self.assertEqual(result["sample_count"], 5)

    def test_base_anchor_inconclusive_never_supported(self) -> None:
        # SS-BASE anchor (absolute metric) is INCONCLUSIVE at/above min_sample_oos
        # and must NEVER report SUPPORTED — no tuning can change that.
        many = _make_examples(200, positive_from=0)
        result = evaluate_experiment(self.CARDS["SS-BASE"], many)
        self.assertEqual(result["status"], "INCONCLUSIVE")
        self.assertNotEqual(result["status"], "SUPPORTED")
        self.assertAlmostEqual(result["metrics"]["oos_precision"], 1.0)

    def test_supported_requires_edge_confirmatory(self) -> None:
        # SS-OF: all-positive OOS subset, baseline 0.5 -> delta +0.5, CONFIRMATORY.
        result = evaluate_experiment(
            self.CARDS["SS-OF"], _make_examples(30, positive_from=0), baseline_rate=0.5
        )
        self.assertEqual(result["status"], "SUPPORTED")
        self.assertEqual(result["metrics"]["oos_count"], 30)
        self.assertTrue(result["incremental_vs_baseline"]["delta_vs_baseline"] >= 0.05)

    def test_exploratory_edge_resolves_not_supported(self) -> None:
        # SS-OF-CAT is EXPLORATORY: even with an edge it resolves NOT_SUPPORTED.
        result = evaluate_experiment(
            self.CARDS["SS-OF-CAT"], _make_examples(30, positive_from=0), baseline_rate=0.5
        )
        self.assertEqual(result["status"], "NOT_SUPPORTED")

    def test_below_threshold_not_supported(self) -> None:
        # Precision 0.4 vs baseline 0.5 -> delta -0.1, no edge.
        result = evaluate_experiment(
            self.CARDS["SS-OF"], _make_examples(30, positive_from=18), baseline_rate=0.5
        )
        self.assertEqual(result["status"], "NOT_SUPPORTED")

    def test_metrics_are_oos_only(self) -> None:
        result = evaluate_experiment(
            self.CARDS["SS-CAT"], _make_examples(6, positive_from=4), baseline_rate=None
        )
        self.assertEqual(result["metrics"]["oos_count"], 6)
        self.assertAlmostEqual(result["metrics"]["oos_precision"], 2.0 / 6.0, places=6)
        self.assertAlmostEqual(
            result["metrics"]["oos_positive_base_rate"], 2.0 / 6.0, places=6
        )
        self.assertEqual(result["card_hash"], self.CARDS["SS-CAT"].card_hash)

    # -- runner is OOS-only on the real fixture -------------------------------
    def test_runner_oos_only_expected_gate_report(self) -> None:
        # Empirical gate report on current fixtures (pinned 2026-08-22):
        # SS-BASE INCONCLUSIVE (anchor), SS-OF/SS-OF-CAT INSUFFICIENT_DATA,
        # SS-CAT/SS-MKT/SS-FV-DISC NEEDS_PROSPECTIVE_VALIDATION. No SUPPORTED.
        result = run_short_squeeze_family(build_ss_family_examples())
        by_id = {row["experiment_id"]: row for row in result["experiments"]}
        expected = {
            "SS-BASE": "INCONCLUSIVE",
            "SS-OF": "INSUFFICIENT_DATA",
            "SS-CAT": "NEEDS_PROSPECTIVE_VALIDATION",
            "SS-MKT": "NEEDS_PROSPECTIVE_VALIDATION",
            "SS-OF-CAT": "INSUFFICIENT_DATA",
            "SS-FV-DISC": "NEEDS_PROSPECTIVE_VALIDATION",
        }
        for eid, status in expected.items():
            self.assertEqual(by_id[eid]["status"], status, eid)
            self.assertNotEqual(by_id[eid]["status"], "SUPPORTED", eid)
        # Pool sizes (evidence-bearing) vs evaluated-OOS counts on current fixtures:
        # SS-BASE pool 2808 -> 1688 held-out evaluated (expanding folds); the tiny
        # augmentation pools can't form folds, so evaluated-OOS is 0 but the pool
        # gates the NEEDS_PROSPECTIVE_VALIDATION status.
        self.assertEqual(by_id["SS-BASE"]["metrics"]["oos_count"], 1688)
        self.assertEqual(by_id["SS-BASE"]["metrics"]["pool_count"], 2808)
        self.assertEqual(by_id["SS-CAT"]["metrics"]["pool_count"], 2)
        self.assertEqual(by_id["SS-MKT"]["metrics"]["pool_count"], 1)
        self.assertEqual(by_id["SS-OF"]["metrics"]["pool_count"], 0)
        self.assertEqual(by_id["SS-OF"]["metrics"]["oos_count"], 0)


if __name__ == "__main__":
    unittest.main()
