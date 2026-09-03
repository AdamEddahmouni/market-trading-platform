"""Task 5 — walk-forward OOS harness tests.

Uses a stub evaluator so fold/determinism/leak contracts are tested
independently of Task 6's metric logic. The real evaluator is integrated via
``tests/research/test_decision_research_001.py`` (Task 9).
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.research.decision_research.examples import build_ss_family_examples
from market_platform_foundation.research.decision_research.harness import (
    build_folds,
    evidence_bearing_subset,
    fold_test_examples,
    fold_train_examples,
    order_examples,
    run_harness,
    verify_harness_folds,
)
from market_platform_foundation.research.decision_research.registry import ExperimentCardRegistry
from market_platform_foundation.research.decision_research.ss_cards import build_ss_family_cards


def _examples(n: int, *, decision_step: int = 1000, offset: int = 0) -> list[dict]:
    families = [{"evidence_family": "SQUEEZE_STATE", "available_time_ns": -1}]
    return [
        {
            "example_id": f"ex-{i:04d}",
            "instrument_id": "BIYA",
            "decision_time_ns": (i + 1) * decision_step + offset,
            "features": [dict(f) for f in families],
            "outcome_time_ns": (i + 1) * decision_step + 5000,
            "outcome": {"positive": i % 2 == 0},
        }
        for i in range(n)
    ]


def _stub_evaluator(card, oos_examples, baseline_rate=None, pool_count=None):
    del baseline_rate
    return {
        "experiment_id": card.experiment_id,
        "baseline_id": card.baseline_id,
        "sample_count": len(oos_examples),
        "status": "PENDING",
        "metrics": {"oos_count": len(oos_examples), "pool_count": pool_count},
        "card_hash": card.card_hash,
    }


def _registered_registry(experiment_ids=None):
    cards = build_ss_family_cards()
    tmp = tempfile.TemporaryDirectory()
    registry = ExperimentCardRegistry(Path(tmp.name))
    for cid, card in cards.items():
        if experiment_ids is None or cid in experiment_ids:
            registry.register(card)
    return cards, registry, tmp


class FoldConstructionTests(unittest.TestCase):
    def test_order_by_decision_then_example_id(self) -> None:
        rows = [
            {"decision_time_ns": 5, "example_id": "b", "features": []},
            {"decision_time_ns": 2, "example_id": "b", "features": []},
            {"decision_time_ns": 2, "example_id": "a", "features": []},
            {"decision_time_ns": 5, "example_id": "a", "features": []},
        ]
        ordered = order_examples(rows)
        self.assertEqual(
            [r["example_id"] for r in ordered], ["a", "b", "a", "b"]
        )

    def test_ss_base_expanding_fold_math(self) -> None:
        # Full fixture: 2808 base examples -> block = max(50, ceil(0.15*2808)) =
        # 422; 4 blocks fit (2808 > 1688) -> expanding folds with growing train.
        examples = build_ss_family_examples()
        subset = evidence_bearing_subset(examples, ["SQUEEZE_STATE"])
        self.assertEqual(len(subset), 2808)
        folds = build_folds(subset)
        self.assertEqual(len(folds), 4)
        total_oos = sum(f["test_count"] for f in folds)
        self.assertEqual(total_oos, 1688)
        self.assertEqual(folds[0]["test_count"], 422)
        self.assertEqual(folds[0]["train_end_index"], 2808 - 1688)
        # expanding: each subsequent fold's train end advances by one block
        self.assertEqual(folds[1]["train_end_index"] - folds[0]["train_end_index"], 422)
        self.assertEqual(folds[3]["train_end_index"], 2808 - 422)

    def test_single_split_fallback_delegates_to_chronological(self) -> None:
        # n=12 -> block = max(50, ceil(0.15*12)=2) = 50; n <= 4*50 -> single
        # split using chronological_split (train int(12*0.6)=7, test 5).
        folds = build_folds(_examples(12))
        self.assertEqual(len(folds), 1)
        self.assertEqual(folds[0]["train_count"], 7)
        self.assertEqual(folds[0]["test_count"], 5)
        self.assertLess(folds[0]["train_end_cutoff"], folds[0]["test_start_cutoff"])

    def test_rolling_folds_use_fixed_window(self) -> None:
        subset = _examples(700)
        expanding = build_folds(subset)
        rolling = build_folds(
            subset, evaluation_window={"schema": "rolling_window", "folds": 4, "oos_block_frac": 0.15, "min_oos_block": 50, "window": 60}
        )
        self.assertEqual(len(expanding), 4)
        self.assertEqual(len(rolling), 4)
        ordered = order_examples(subset)
        # rolling train window stays 60 wide; expanding train keeps growing
        self.assertEqual(rolling[0]["test_count"], expanding[0]["test_count"])
        self.assertEqual(rolling[0]["train_count"], 60)
        self.assertGreater(expanding[0]["train_count"], rolling[0]["train_count"])

    def test_invalid_schema_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_folds(_examples(10), evaluation_window={"schema": "bogus"})

    def test_fold_membership_pit_integrity(self) -> None:
        subset = _examples(300)
        folds = build_folds(subset)
        ordered = order_examples(subset)
        status, reasons = verify_harness_folds(folds, ordered)
        self.assertEqual(status, "PASS", reasons)
        for fold in folds:
            self.assertEqual(fold["test_count"], len(fold_test_examples(fold, ordered)))
            self.assertEqual(fold["train_count"], len(fold_train_examples(fold, ordered)))


class AdversarialFoldTests(unittest.TestCase):
    def test_train_after_test_start_rejected(self) -> None:
        ordered = order_examples(_examples(100))
        leaked = ordered[20:40]  # pretend a chunk past the boundary is "train"
        test = ordered[15:25]
        bad_fold = {
            "fold_id": 0,
            "train_start_cutoff": int(ordered[20]["decision_time_ns"]),
            "train_end_cutoff": int(ordered[-1]["decision_time_ns"]),
            "test_start_cutoff": int(test[0]["decision_time_ns"]),
            "test_end_cutoff": int(test[-1]["decision_time_ns"]),
            "train_count": len(leaked := leaked) if False else len(ordered[20:40]),
            "test_count": len(test),
            "train_start_index": 20,
            "train_end_index": 40,
            "test_start_index": 15,
            "test_end_index": 25,
        }
        status, reasons = verify_harness_folds([bad_fold], ordered)
        self.assertEqual(status, "FAIL")
        self.assertIn("FOLD_TRAIN_AFTER_TEST_START:ex-0020", reasons)

    def test_pit_invalid_member_rejected(self) -> None:
        ordered = order_examples(_examples(100))
        ordered[10]["features"][0]["available_time_ns"] = ordered[10]["decision_time_ns"] + 1
        folds = build_folds(ordered)
        status, reasons = verify_harness_folds(folds, ordered)
        self.assertEqual(status, "FAIL")
        self.assertTrue(any("FOLD_PIT_VIOLATION:ex-0010" in r for r in reasons))


class RunRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cards, self.registry, self.tmp = _registered_registry()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_run_record_determinism(self) -> None:
        examples = _examples(300)
        first = run_harness(
            self.cards, examples, registry=self.registry, evaluate=_stub_evaluator
        )
        second = run_harness(
            self.cards, examples, registry=self.registry, evaluate=_stub_evaluator
        )
        self.assertEqual(first["run_id"], second["run_id"])
        self.assertEqual(first["run_root_hash"], second["run_root_hash"])
        self.assertEqual(first["results"], second["results"])

    def test_run_record_contract_fields(self) -> None:
        result = run_harness(
            self.cards, _examples(300), registry=self.registry, evaluate=_stub_evaluator
        )
        self.assertEqual(result["execution_authority"], "NONE")
        self.assertFalse(result["auto_strategy_promotion"])
        self.assertTrue(result["registry_bound"])
        self.assertEqual(len(result["bound_card_hashes"]), 6)
        for cid, card in self.cards.items():
            self.assertEqual(result["bound_card_hashes"][cid], card.card_hash)

    def test_oos_counts_reflect_evidence_bearing_subset(self) -> None:
        examples = build_ss_family_examples()
        result = run_harness(
            self.cards, examples, registry=self.registry, evaluate=_stub_evaluator
        )
        # SS-BASE subset = all 2808 -> expanding folds, OOS 1688
        self.assertEqual(result["oos_counts"]["SS-BASE"]["evidence_bearing"], 2808)
        self.assertEqual(result["oos_counts"]["SS-BASE"]["oos"], 1688)
        # SS-OF / SS-OF-CAT evidence-bearing subset is empty on current fixtures
        self.assertEqual(result["oos_counts"]["SS-OF"]["evidence_bearing"], 0)
        self.assertEqual(result["oos_counts"]["SS-OF"]["oos"], 0)
        self.assertEqual(result["oos_counts"]["SS-OF-CAT"]["evidence_bearing"], 0)
        self.assertEqual(result["oos_counts"]["SS-OF-CAT"]["oos"], 0)
        # SS-CAT / SS-MKT small pools resolve to the single-split fallback (≤4 blocks)
        self.assertEqual(result["oos_counts"]["SS-CAT"]["evidence_bearing"], 2)
        self.assertEqual(result["oos_counts"]["SS-MKT"]["evidence_bearing"], 1)

    def test_fail_closed_unregistered_card_raises(self) -> None:
        cards, registry, tmp = _registered_registry(experiment_ids={"SS-BASE", "SS-OF"})
        try:
            with self.assertRaises(ValueError):
                run_harness(cards, _examples(100), registry=registry, evaluate=_stub_evaluator)
        finally:
            tmp.cleanup()

    def test_no_cards_raises(self) -> None:
        with self.assertRaises(ValueError):
            run_harness({}, _examples(10), registry=self.registry, evaluate=_stub_evaluator)


if __name__ == "__main__":
    unittest.main()
