"""DECISION-RESEARCH-001 — DEC-* assertion + adversarial suite (spec §9/§11).

Consolidates the milestone's hard invariants end-to-end over the committed
fixtures: cards -> examples -> harness -> OOS evaluation -> synthesis -> gate
report shape. Each ``DEC-*`` id is asserted directly and an end-to-end run
reproduces the empirically verified expected gate report.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.canonical import load_json_strict
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns
from market_platform_foundation.research.decision_research.examples import (
    DECLARED_ONLY_FAMILIES,
    build_ss_family_examples,
    load_donor_rows,
    validate_examples,
)
from market_platform_foundation.research.decision_research.experiments import (
    PROSPECTIVE_CAPTURE_FAMILIES,
)
from market_platform_foundation.research.decision_research.harness import (
    run_harness,
    verify_harness_folds,
)
from market_platform_foundation.research.decision_research.pit_gate import (
    reject_historical_finviz_screen_without_capture,
    validate_temporal_example,
)
from market_platform_foundation.research.decision_research.registry import (
    ExperimentCardRegistry,
)
from market_platform_foundation.research.decision_research.ss_cards import build_ss_family_cards
from market_platform_foundation.research.decision_research.synthesis import build_decision_candidate

CARDS_FIXTURE = ROOT / "tests" / "fixtures" / "research" / "experiment_cards.json"
EXAMPLES_FIXTURE = ROOT / "tests" / "fixtures" / "research" / "ss_family_examples.json"


def _make_registry() -> tuple[ExperimentCardRegistry, tempfile.TemporaryDirectory]:
    cards = build_ss_family_cards()
    tmp = tempfile.TemporaryDirectory()
    registry = ExperimentCardRegistry(Path(tmp.name))
    for card in cards.values():
        registry.register(card)
    return registry, tmp


def _pit_invalid_leak() -> dict:
    """An example whose feature becomes available after the decision (leak)."""
    return {
        "example_id": "leak-adv",
        "instrument_id": "BIYA",
        "decision_time_ns": 500_000_000,
        "features": [
            {
                "evidence_family": "SQUEEZE_STATE",
                "available_time_ns": 500_000_001,
                "quality_flags": ["FIXTURE_SQUEEZE_PROXY"],
                "freshness_ms": 1,
                "authority": "IMP_DERIVED",
                "value": {},
            }
        ],
        "outcome_time_ns": 600_000_000,
        "outcome": {"positive": True},
    }


class DECPIT001Tests(unittest.TestCase):
    def test_every_run_example_passes_pit_gate(self) -> None:
        examples = build_ss_family_examples()
        self.assertEqual(len(examples), 2808)
        # Every produced example is PIT-valid.
        self.assertEqual(validate_examples(examples), [])

    def test_harness_fold_pit_is_pass_for_all_cards(self) -> None:
        registry, tmp = _make_registry()
        try:
            run = run_harness(build_ss_family_cards(), build_ss_family_examples(), registry=registry)
            self.assertEqual(set(run["fold_pit_status"].values()), {"PASS"})
        finally:
            tmp.cleanup()

    def test_feature_after_decision_rejected(self) -> None:
        bad = _pit_invalid_leak()
        ok, reasons = validate_temporal_example(bad)
        self.assertFalse(ok)
        self.assertTrue(any("FEATURE_AFTER_DECISION" in r for r in reasons))


class DECPRE001Tests(unittest.TestCase):
    def test_no_result_without_registry_bound_card_hash(self) -> None:
        registry, tmp = _make_registry()
        try:
            run = run_harness(build_ss_family_cards(), build_ss_family_examples(), registry=registry)
            bound = set(run["bound_card_hashes"].values())
            for result in run["results"].values():
                self.assertIn(result["card_hash"], bound)
        finally:
            tmp.cleanup()

    def test_unregistered_card_run_fails_closed(self) -> None:
        cards = build_ss_family_cards()
        tmp = tempfile.TemporaryDirectory()
        registry = ExperimentCardRegistry(Path(tmp.name))
        registry.register(cards["SS-BASE"])  # only the baseline is registered
        try:
            with self.assertRaises(ValueError):
                run_harness(cards, build_ss_family_examples(), registry=registry)
        finally:
            tmp.cleanup()


class DECOOS001Tests(unittest.TestCase):
    def test_primary_metrics_come_only_from_oos_folds(self) -> None:
        registry, tmp = _make_registry()
        try:
            run = run_harness(build_ss_family_cards(), build_ss_family_examples(), registry=registry)
            # SS-BASE: pool 2808, evaluated OOS = 1688 = sum of fold test counts.
            base_result = run["results"]["SS-BASE"]
            self.assertEqual(base_result["metrics"]["pool_count"], 2808)
            self.assertEqual(base_result["metrics"]["oos_count"], 1688)
            plan = run["fold_plan"]["SS-BASE"]
            self.assertEqual(sum(f["test_count"] for f in plan), 1688)
            # The reported OOS count is never the full in-sample pool.
            self.assertLess(base_result["metrics"]["oos_count"], 2808)
        finally:
            tmp.cleanup()

    def test_tiny_pools_report_evaluated_oos_not_pool(self) -> None:
        # DEC-OOS-001: augmentation pools are not inflated to their (impossible)
        # full size; metrics reflect what is actually held out.
        registry, tmp = _make_registry()
        try:
            run = run_harness(build_ss_family_cards(), build_ss_family_examples(), registry=registry)
            cat = run["results"]["SS-CAT"]
            self.assertEqual(cat["metrics"]["pool_count"], 2)
            self.assertLessEqual(cat["metrics"]["oos_count"], cat["metrics"]["pool_count"])
        finally:
            tmp.cleanup()


class DECDET001Tests(unittest.TestCase):
    def test_repeat_runs_identical_hashes(self) -> None:
        registry, tmp = _make_registry()
        try:
            cards = build_ss_family_cards()
            examples = build_ss_family_examples()
            first = run_harness(cards, examples, registry=registry)
            second = run_harness(cards, examples, registry=registry)
            self.assertEqual(first["run_id"], second["run_id"])
            self.assertEqual(first["run_root_hash"], second["run_root_hash"])
        finally:
            tmp.cleanup()

    def test_oos_fold_boundary_leak_rejected(self) -> None:
        # Craft a fold whose train straddles the test start boundary.
        from market_platform_foundation.research.decision_research.harness import order_examples

        ordered = order_examples(build_ss_family_examples()[:100])
        bad = {
            "fold_id": 0,
            "train_start_cutoff": int(ordered[20]["decision_time_ns"]),
            "train_end_cutoff": int(ordered[99]["decision_time_ns"]),
            "test_start_cutoff": int(ordered[0]["decision_time_ns"]),
            "test_end_cutoff": int(ordered[9]["decision_time_ns"]),
            "train_count": 80,
            "test_count": 10,
            "train_start_index": 20,
            "train_end_index": 100,
            "test_start_index": 0,
            "test_end_index": 10,
        }
        status, reasons = verify_harness_folds([bad], ordered)
        self.assertEqual(status, "FAIL")
        self.assertTrue(any("FOLD_TRAIN_AFTER_TEST_START" in r for r in reasons))


class DECSYN001Tests(unittest.TestCase):
    CUTOFF = iso_to_epoch_ns("2026-07-21T00:00:00Z")

    def test_no_composite_score_in_synthesis(self) -> None:
        # DEC-SYN-001: no aggregate/adjudication score anywhere. MC16's
        # `theme_agreement_score` is a declared input feature (allowed); what is
        # forbidden is a computed composite/decision score field.
        lane = {
            "instrument": "BIYA", "lane": "SHORT_SQUEEZE", "evidence_type": "SQUEEZE_STATE",
            "quality": "PASS", "relevance": "HIGH", "direction": "POSITIVE",
            "confidence": "MEDIUM", "probability": None, "expected_value": None,
            "summary": "active squeeze", "freshness_label": "REPLAY",
            "available_time": "2026-07-20T13:00:00Z", "reason_codes": [], "sources": [],
            "details": {}, "explain_ref": "", "missing_evidence": [], "research_only": True,
        }
        candidate = build_decision_candidate("BIYA", self.CUTOFF, [lane])
        body = candidate.to_dict()
        forbidden_score_keys = {
            "composite_score", "decision_score", "signal_score", "score", "score_pct",
            "aggregate_score",
        }
        self.assertIsNone(body.get(next(iter(forbidden_score_keys & set(body)), None)))
        for container in ("supporting_evidence", "contradicting_evidence"):
            for piece in body[container]:
                overlap = forbidden_score_keys & set(piece)
                self.assertEqual(overlap, set(), container)
        self.assertEqual(body.get("evidence_mix"), "ALIGNED")
        self.assertEqual(body.get("direction_hypothesis"), "LONG")

    def test_contradiction_resolves_mixed_no_hypothesis(self) -> None:
        from market_platform_foundation.research.decision_research.synthesis import build_decision_candidate as b

        bull = {"lane": "SHORT_SQUEEZE", "direction": "POSITIVE", "quality": "PASS", "relevance": "HIGH", "summary": "bull", "freshness_label": "R", "available_time": "2026-07-20T13:00:00Z"}
        bear = {"lane": "ORDER_FLOW", "direction": "NEGATIVE", "quality": "PASS", "relevance": "HIGH", "summary": "bear", "freshness_label": "R", "available_time": "2026-07-20T13:00:00Z"}
        candidate = b("BIYA", self.CUTOFF, [bull, bear])
        self.assertEqual(candidate.evidence_mix, "MIXED")
        self.assertEqual(candidate.direction_hypothesis, "NO_HYPOTHESIS")


class DECMAN001Tests(unittest.TestCase):
    def test_execution_authority_is_none_everywhere(self) -> None:
        registry, tmp = _make_registry()
        try:
            run = run_harness(build_ss_family_cards(), build_ss_family_examples(), registry=registry)
            self.assertEqual(run["execution_authority"], "NONE")
            self.assertFalse(run["auto_strategy_promotion"])
            for result in run["results"].values():
                self.assertEqual(result["strategy_promotion"], "NONE")
        finally:
            tmp.cleanup()

    def test_no_automatic_order_path(self) -> None:
        # DEC-MAN-001 hard invariant: research/ never imports the order path.
        import os
        import subprocess
        import sys as sys_module

        code = (
            "import sys; import market_platform_foundation.research.decision_research as m; "
            "loaded=set(sys.modules); "
            "print(any(n.startswith('market_platform_foundation.paper.execution') for n in loaded))"
        )
        env = dict(os.environ, PYTHONPATH=str(SRC))
        proc = subprocess.run([sys_module.executable, "-c", code], capture_output=True, text=True, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "False")


class DECFV001Tests(unittest.TestCase):
    def test_finviz_rejected_without_prospective_capture(self) -> None:
        ok, reason = reject_historical_finviz_screen_without_capture(
            feature_source="FINVIZ_SCREEN", capture_present=False
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "NO_RETROACTIVE_FINVIZ_SCREEN_RECONSTRUCTION")

    def test_declared_only_and_finviz_never_built(self) -> None:
        self.assertIn("FINVIZ_DISCOVERY", DECLARED_ONLY_FAMILIES)
        self.assertIn("FINVIZ_DISCOVERY", PROSPECTIVE_CAPTURE_FAMILIES)
        attached = {
            f["evidence_family"]
            for e in build_ss_family_examples()
            for f in e["features"]
        }
        self.assertNotIn("FINVIZ_DISCOVERY", attached)
        with self.assertRaises(ValueError):
            load_donor_rows("FINVIZ_DISCOVERY")


class DECINC001Tests(unittest.TestCase):
    def test_empty_pool_fails_closed_insufficient(self) -> None:
        from market_platform_foundation.research.decision_research.experiments import evaluate_experiment

        result = evaluate_experiment(build_ss_family_cards()["SS-OF"], [], pool_count=0)
        self.assertEqual(result["status"], "INSUFFICIENT_DATA")

    def test_small_pool_fails_closed_prospective(self) -> None:
        from market_platform_foundation.research.decision_research.experiments import evaluate_experiment

        result = evaluate_experiment(build_ss_family_cards()["SS-CAT"], [], pool_count=2)
        self.assertEqual(result["status"], "NEEDS_PROSPECTIVE_VALIDATION")


class EndToEndGateReportTests(unittest.TestCase):
    def test_pipeline_reproduces_expected_gate_report(self) -> None:
        # Committed fixtures drive the run end-to-end.
        cards = build_ss_family_cards()
        self.assertEqual(len(cards), 6)
        tmp = tempfile.TemporaryDirectory()
        registry = ExperimentCardRegistry(Path(tmp.name))
        try:
            # register from the committed card fixture (byte-hash identity)
            for payload in load_json_strict(CARDS_FIXTURE):
                from market_platform_foundation.research.decision_research.cards import ExperimentCard

                registry.register(ExperimentCard.from_dict(payload))
            examples = build_ss_family_examples()
            run = run_harness(cards, examples, registry=registry)
            expected = {
                "SS-BASE": "INCONCLUSIVE",
                "SS-OF": "INSUFFICIENT_DATA",
                "SS-CAT": "NEEDS_PROSPECTIVE_VALIDATION",
                "SS-MKT": "NEEDS_PROSPECTIVE_VALIDATION",
                "SS-OF-CAT": "INSUFFICIENT_DATA",
                "SS-FV-DISC": "NEEDS_PROSPECTIVE_VALIDATION",
            }
            for eid, status in expected.items():
                self.assertEqual(run["results"][eid]["status"], status, eid)
            # no card adjudicated SUPPORTED on the current fixture scope
            self.assertTrue(all(v["status"] != "SUPPORTED" for v in run["results"].values()))
            # run record carries OOS-only + authority metadata
            self.assertEqual(run["execution_authority"], "NONE")
        finally:
            tmp.cleanup()

    def test_fixture_files_present_and_consistent(self) -> None:
        self.assertTrue(CARDS_FIXTURE.is_file())
        self.assertTrue(EXAMPLES_FIXTURE.is_file())
        # The committed examples fixture must match the deterministic builder.
        from market_platform_foundation.canonical import canonical_bytes

        expected = canonical_bytes(build_ss_family_examples())
        self.assertEqual(EXAMPLES_FIXTURE.read_bytes(), expected)


if __name__ == "__main__":
    unittest.main()
