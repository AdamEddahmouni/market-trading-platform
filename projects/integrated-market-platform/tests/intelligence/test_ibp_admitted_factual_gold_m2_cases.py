"""Lane M2 — admitted factual gold candidate cases (independent of SUT)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.benchmark_protocol.admitted_factual_gold import (  # noqa: E402
    FACTUAL_GOLD_EVALUATOR_ONLY_CASE_KEYS,
    compute_case_gold_hash,
    compute_caseset_hash,
    compute_goldset_hash,
    project_factual_case_for_sut,
    validate_factual_gold_case,
    validate_factual_gold_protocol,
)
from market_platform_foundation.intelligence.benchmark_protocol.admitted_factual_gold.sut_projection import (  # noqa: E402
    assert_factual_case_safe_for_sut,
)

_CANDIDATE_PROTOCOL = (
    ROOT
    / "tests/fixtures/intelligence_benchmark/admitted_factual_gold/protocol_ibp_factual_smoke_v1_candidate.json"
)


class IbpAdmittedFactualGoldM2CaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.protocol = json.loads(_CANDIDATE_PROTOCOL.read_text(encoding="utf-8"))
        validate_factual_gold_protocol(cls.protocol)

    def test_candidate_protocol_freeze_state(self) -> None:
        freeze = self.protocol["freeze"]
        self.assertTrue(freeze["cases_constructed"])
        self.assertEqual(freeze["status"], "FROZEN")
        self.assertFalse(freeze["smoke10_executed"])

    def test_caseset_and_goldset_hashes_match(self) -> None:
        cases = self.protocol["cases"]
        self.assertEqual(self.protocol["caseset_hash"], compute_caseset_hash(cases))
        refs = [c["evaluator_gold_ref"] for c in cases]
        self.assertEqual(self.protocol["goldset_hash"], compute_goldset_hash(refs))

    def test_each_case_validates_and_gold_files_match(self) -> None:
        for case in self.protocol["cases"]:
            validate_factual_gold_case(case)
            ref = case["evaluator_gold_ref"]
            gold_path = ROOT / "tests/fixtures/intelligence_benchmark" / ref
            self.assertTrue(gold_path.is_file(), ref)
            on_disk = json.loads(gold_path.read_text(encoding="utf-8"))
            self.assertEqual(on_disk["CASE_ID"], case["CASE_ID"])
            if case["SCORING_GATE"] == "ANSWERABLE_FROM_ADMITTED_EVIDENCE":
                self.assertEqual(
                    case["GOLD_HASH"],
                    compute_case_gold_hash(
                        case_id=case["CASE_ID"],
                        expected_facts=case["EXPECTED_FACTS"],
                        unknown_policy=case["UNKNOWN_POLICY"],
                    ),
                )

    def test_sut_projection_hides_evaluator_gold(self) -> None:
        for case in self.protocol["cases"]:
            if case["SCORING_GATE"] != "ANSWERABLE_FROM_ADMITTED_EVIDENCE":
                continue
            sut = project_factual_case_for_sut(case)
            for key in FACTUAL_GOLD_EVALUATOR_ONLY_CASE_KEYS:
                self.assertNotIn(key, sut)
            assert_factual_case_safe_for_sut(sut)

    def test_answerability_flags(self) -> None:
        answerable = [
            c for c in self.protocol["cases"] if c["SCORING_GATE"] == "ANSWERABLE_FROM_ADMITTED_EVIDENCE"
        ]
        excluded = [c for c in self.protocol["cases"] if c["SCORING_GATE"] == "EXCLUDED_UNANSWERABLE"]
        self.assertEqual(len(answerable), 11)
        self.assertEqual(len(excluded), 1)
        unknown_cases = [
            c
            for c in answerable
            if c["UNKNOWN_POLICY"]["correct_unknown_verdict"] == "CORRECT_UNKNOWN"
        ]
        self.assertEqual(len(unknown_cases), 1)
        self.assertEqual(unknown_cases[0]["CASE_ID"], "IBP-FACTUAL-011")

    def test_empty_protocol_fixture_unchanged(self) -> None:
        empty_path = (
            ROOT
            / "tests/fixtures/intelligence_benchmark/admitted_factual_gold/protocol_ibp_factual_smoke_v1_empty.json"
        )
        empty = json.loads(empty_path.read_text(encoding="utf-8"))
        self.assertEqual(empty["cases"], [])
        self.assertFalse(empty["freeze"]["cases_constructed"])


if __name__ == "__main__":
    unittest.main()
