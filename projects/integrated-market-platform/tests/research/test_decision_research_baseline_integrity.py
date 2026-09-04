"""E10 regression — fail-closed baseline semantics in the decision-research harness.

Research-integrity contract: a baseline-relative metric may only be adjudicated
against the baseline card's OWN measured OOS slice. A missing baseline must
raise ``HARNESS_BASELINE_MISSING`` — never a 0.0 substitution (which would let
raw precision masquerade as delta and reach SUPPORTED) and never a slice
borrowed from the current card.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))

from market_platform_foundation.research.decision_research.cards import ExperimentCard
from market_platform_foundation.research.decision_research.experiments import (
    evaluate_experiment,
)
from market_platform_foundation.research.decision_research.harness import (
    build_folds,
    evidence_bearing_subset,
    fold_test_examples,
    order_examples,
    run_harness,
)

PREREG = 1_784_678_400_000_000_000  # fixed preregistration constant


def build_card(
    *,
    experiment_id: str,
    baseline_id: str,
    required: tuple[str, ...],
    primary_metric: str = "oos_precision_delta_vs_baseline",
    min_sample_oos: int = 10,
) -> ExperimentCard:
    return ExperimentCard(
        experiment_id=experiment_id,
        family="SHORT_SQUEEZE",
        hypothesis_label="CONFIRMATORY",
        baseline_id=baseline_id,
        added_evidence=(),
        feature_spec={
            "required": list(required),
            "min_quality": {},
            "min_freshness_ms": {},
        },
        outcome_spec={
            "horizon_ns": 1_800_000_000_000,
            "return_basis": "MARK_TO_MARK",
            "cost_model_version": "execution_book_aware_v1",
        },
        inclusion_criteria=("admitted_fixture",),
        exclusion_criteria=("no_retroactive_finviz",),
        primary_metric=primary_metric,
        min_sample_oos=min_sample_oos,
        primary_metric_threshold=0.05,
        preregistered_at_ns=PREREG,
    )


def _valid_example(*, decision_time_ns: int, families: tuple[str, ...], positive: bool) -> dict:
    return {
        "decision_time_ns": decision_time_ns,
        "features": [
            {"available_time_ns": decision_time_ns - 100, "evidence_family": f}
            for f in families
        ],
        "outcome_time_ns": decision_time_ns + 5000,
        "outcome": {"positive": positive},
    }


def _split_examples() -> list[dict[str, Any]]:
    """60 PIT-valid examples whose FAM_A-only and FAM_A+FAM_B slices disagree.

    ``i % 4 == 0`` drives positivity while ``i % 2 == 0`` gates the FAM_B
    feature, so positives are distributed differently across the two slices.
    """
    return [
        _valid_example(
            decision_time_ns=(i + 1) * 1_000_000,
            families=("FAM_A", "FAM_B") if i % 2 == 0 else ("FAM_A",),
            positive=i % 4 == 0,
        )
        for i in range(60)
    ]


def _oos_rate(examples: list[dict[str, Any]], required: tuple[str, ...]) -> float:
    subset = evidence_bearing_subset(order_examples(examples), list(required))
    folds = build_folds(subset)
    oos = [ex for fold in folds for ex in fold_test_examples(fold, order_examples(subset))]
    positives = sum(1 for ex in oos if ex.get("outcome", {}).get("positive"))
    return positives / len(oos)


def _capturing_evaluator(sink: dict[str, Any]):
    def evaluate(card, oos_examples, *, baseline_rate=None, pool_count=None):
        sink[card.experiment_id] = {
            "baseline_rate": baseline_rate,
            "oos_count": len(oos_examples),
            "pool_count": pool_count,
        }
        return {
            "experiment_id": card.experiment_id,
            "baseline_id": card.baseline_id,
            "sample_count": len(oos_examples),
            "status": "PENDING",
            "metrics": {"oos_count": len(oos_examples), "pool_count": pool_count},
        }

    return evaluate


class HarnessBaselineIntegrityTests(unittest.TestCase):
    def test_baseline_computed_from_baseline_card_slice(self) -> None:
        examples = _split_examples()
        cards = {
            "SS-BASE": build_card(
                experiment_id="SS-BASE",
                baseline_id="SS-BASE",
                required=("FAM_A",),
                primary_metric="oos_positive_base_rate",
            ),
            "SS-AUG": build_card(
                experiment_id="SS-AUG",
                baseline_id="SS-BASE",
                required=("FAM_A", "FAM_B"),
            ),
        }
        sink: dict[str, Any] = {}
        run_harness(cards, examples, evaluate=_capturing_evaluator(sink))

        expected = _oos_rate(examples, ("FAM_A",))
        misattributed = _oos_rate(examples, ("FAM_A", "FAM_B"))
        # The premise: current-card slice and baseline-card slice genuinely
        # disagree, so a correct test can tell them apart.
        self.assertNotEqual(expected, misattributed)
        self.assertAlmostEqual(sink["SS-AUG"]["baseline_rate"], expected)

    def test_absent_baseline_raises_sentinel(self) -> None:
        examples = _split_examples()
        cards = {
            "SS-AUG": build_card(
                experiment_id="SS-AUG",
                baseline_id="SS-NOTHING",
                required=("FAM_A", "FAM_B"),
            ),
        }
        with self.assertRaises(ValueError) as ctx:
            run_harness(cards, examples, evaluate=_capturing_evaluator({}))
        self.assertIn("HARNESS_BASELINE_MISSING", str(ctx.exception))


class EvaluateExperimentBaselineFailClosedTests(unittest.TestCase):
    def test_missing_baseline_never_substitutes_zero(self) -> None:
        card = build_card(
            experiment_id="SS-AUG",
            baseline_id="SS-BASE",
            required=("FAM_A",),
            min_sample_oos=5,
        )
        oos = [
            _valid_example(decision_time_ns=(i + 1) * 1_000, families=("FAM_A",), positive=True)
            for i in range(10)
        ]
        with self.assertRaises(ValueError) as ctx:
            evaluate_experiment(card, oos, baseline_rate=None)
        self.assertIn("HARNESS_BASELINE_MISSING", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
