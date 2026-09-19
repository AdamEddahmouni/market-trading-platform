"""Grounded fact extraction v1 — independent fixtures (no evaluator gold payloads)."""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.benchmark_protocol.admitted_factual_gold import (  # noqa: E402
    build_factual_blind_case_input,
    load_candidate_factual_gold_protocol,
)
from market_platform_foundation.intelligence.benchmark_protocol.admitted_factual_gold.fact_normalization import (  # noqa: E402
    values_equivalent,
)
from market_platform_foundation.intelligence.benchmark_protocol.contamination import (  # noqa: E402
    EVALUATOR_ONLY_MANIFEST_KEYS,
)
from market_platform_foundation.intelligence.benchmark_protocol.facts_sut import (  # noqa: E402
    run_ibp_facts_sut,
)
from market_platform_foundation.intelligence.benchmark_protocol.grounded_fact_extraction import (  # noqa: E402
    FactualAnswerDisposition,
    answer_admitted_factual_question,
)

_FIXTURE_ROOT = ROOT / "tests/fixtures/intelligence_benchmark/grounded_fact_extraction"
_CANDIDATE_PROTOCOL = (
    ROOT
    / "tests/fixtures/intelligence_benchmark/admitted_factual_gold/protocol_ibp_factual_smoke_v1_candidate.json"
)


def _evidence_set(artifact_rel: str, source_type: str = "ADMITTED_FIXTURE_RECORD") -> dict:
    return {
        "evidence_access_mode": "ADMITTED_EVIDENCE_FIXED",
        "sources": [
            {
                "source_type": source_type,
                "evidence_access_mode": "ADMITTED_EVIDENCE_FIXED",
                "artifact_ref": artifact_rel,
            }
        ],
    }


class GroundedFactExtractionV1Tests(unittest.TestCase):
    def test_supported_integer_row_count(self) -> None:
        rel = "tests/fixtures/intelligence_benchmark/grounded_fact_extraction/mini_row_count.json"
        outcome = answer_admitted_factual_question(
            question={
                "text": "How many raw bar rows are under session 2025-06-01?",
                "question_class": "ROW_COUNT",
            },
            temporal_cutoff={"cutoff_instant": "2025-06-01T20:00:00Z"},
            evidence_set=_evidence_set(rel, "HISTORICAL_DEVELOPMENT_ARTIFACT"),
            repository_root=ROOT,
        )
        self.assertEqual(outcome.disposition, FactualAnswerDisposition.SUPPORTED_ANSWER)
        self.assertEqual(outcome.structured_facts[0]["value"], 2)

    def test_enum_state_authority_class(self) -> None:
        rel = "tests/fixtures/intelligence_benchmark/grounded_fact_extraction/authority_manifest.json"
        outcome = answer_admitted_factual_question(
            question={
                "text": "What corpus_evidence_authority value is declared?",
                "question_class": "AUTHORITY_CLASS",
            },
            temporal_cutoff={"cutoff_instant": "2025-06-01T20:00:00Z"},
            evidence_set=_evidence_set(rel),
            repository_root=ROOT,
        )
        self.assertEqual(outcome.disposition, FactualAnswerDisposition.SUPPORTED_ANSWER)
        self.assertEqual(outcome.structured_facts[0]["value"], "HISTORICAL_DEVELOPMENT")

    def test_identifier_dataset_id(self) -> None:
        rel = "tests/fixtures/intelligence_benchmark/grounded_fact_extraction/authority_manifest.json"
        outcome = answer_admitted_factual_question(
            question={
                "text": "What dataset_id is declared in the manifest?",
                "question_class": "GOVERNED_MANIFEST",
            },
            temporal_cutoff={"cutoff_instant": "2025-06-01T20:00:00Z"},
            evidence_set=_evidence_set(rel),
            repository_root=ROOT,
        )
        self.assertEqual(outcome.structured_facts[0]["value"], "fixture.dataset.v1")

    def test_artifact_support_hash_present(self) -> None:
        rel = "tests/fixtures/intelligence_benchmark/grounded_fact_extraction/mini_row_count.json"
        outcome = answer_admitted_factual_question(
            question={"text": "row count 2025-06-01", "question_class": "ROW_COUNT"},
            temporal_cutoff={"cutoff_instant": "2025-06-01T20:00:00Z"},
            evidence_set=_evidence_set(rel, "HISTORICAL_DEVELOPMENT_ARTIFACT"),
            repository_root=ROOT,
        )
        self.assertTrue(str(outcome.structured_facts[0]["support_hash"]).startswith("sha256:"))

    def test_missing_evidence_unknown(self) -> None:
        outcome = answer_admitted_factual_question(
            question={"text": "count rows", "question_class": "ROW_COUNT"},
            temporal_cutoff={"cutoff_instant": "2025-06-01T20:00:00Z"},
            evidence_set=_evidence_set("tests/fixtures/does_not_exist.json"),
            repository_root=ROOT,
        )
        self.assertEqual(outcome.answer, "UNKNOWN")

    def test_conflicting_evidence_unknown(self) -> None:
        facts = [
            {"field": "x", "value": 1, "source_artifact": "a", "source_path": "p", "support_hash": "sha256:1"},
            {"field": "x", "value": 2, "source_artifact": "a", "source_path": "p", "support_hash": "sha256:1"},
        ]
        from market_platform_foundation.intelligence.benchmark_protocol.grounded_fact_extraction.pipeline import (
            _detect_conflicts,
        )

        self.assertTrue(_detect_conflicts(facts))

    def test_temporal_cutoff_refuses_future_bar(self) -> None:
        rel = "tests/fixtures/intelligence_benchmark/grounded_fact_extraction/future_bar_session.json"
        outcome = answer_admitted_factual_question(
            question={"text": "rows on 2030-01-01", "question_class": "ROW_COUNT"},
            temporal_cutoff={"cutoff_instant": "2025-01-01T00:00:00Z"},
            evidence_set=_evidence_set(rel, "HISTORICAL_DEVELOPMENT_ARTIFACT"),
            repository_root=ROOT,
        )
        self.assertEqual(outcome.disposition, FactualAnswerDisposition.TEMPORAL_CUTOFF_REFUSED)

    def test_abstention_unknown_for_missing_instrument(self) -> None:
        rel = "tests/fixtures/intelligence_benchmark/grounded_fact_extraction/mini_row_count.json"
        outcome = answer_admitted_factual_question(
            question={
                "text": "What is the closing price for ZZZZ on 2025-06-01?",
                "question_class": "ABSTENTION",
            },
            temporal_cutoff={"cutoff_instant": "2025-06-01T20:00:00Z"},
            evidence_set=_evidence_set(rel, "HISTORICAL_DEVELOPMENT_ARTIFACT"),
            repository_root=ROOT,
        )
        self.assertEqual(outcome.disposition, FactualAnswerDisposition.CORRECT_UNKNOWN)
        self.assertEqual(outcome.answer, "UNKNOWN")

    def test_unsupported_question_class_unknown(self) -> None:
        outcome = answer_admitted_factual_question(
            question={"text": "random", "question_class": "NOT_A_REAL_CLASS"},
            temporal_cutoff={"cutoff_instant": "2025-06-01T20:00:00Z"},
            evidence_set=_evidence_set(
                "tests/fixtures/intelligence_benchmark/grounded_fact_extraction/mini_row_count.json",
                "HISTORICAL_DEVELOPMENT_ARTIFACT",
            ),
            repository_root=ROOT,
        )
        self.assertEqual(outcome.answer, "UNKNOWN")

    def test_fixture_cannot_promote_to_live_via_sut(self) -> None:
        blind = {
            "case_id": "FIXTURE-PROMO-TEST",
            "protocol_version": "IBP_FACTUAL_SMOKE_V1",
            "blind_mode": "A",
            "context_reset_token": "promo",
            "question": {
                "text": "How many raw bar rows are under session 2025-06-01?",
                "question_class": "ROW_COUNT",
            },
            "evidence_set": _evidence_set(
                "tests/fixtures/intelligence_benchmark/grounded_fact_extraction/mini_row_count.json",
                "HISTORICAL_DEVELOPMENT_ARTIFACT",
            ),
            "temporal_cutoff": {"cutoff_instant": "2025-06-01T20:00:00Z"},
            "routing_expectation": {"template": "HISTORICAL_FACTUAL"},
        }
        response = run_ibp_facts_sut(blind, repository_root=ROOT)
        self.assertFalse(response.get("live_promotion_allowed"))
        self.assertEqual(response.get("evidence_data_mode"), "FIXTURE_REPLAY")

    def test_normalization_equivalence_on_answer(self) -> None:
        norm = {
            "trim_whitespace": True,
            "case_folding": True,
            "instrument_symbol_canonicalization": True,
        }
        rel = "tests/fixtures/historical_development/aapl_2026-09-15_rth_sample.json"
        outcome = answer_admitted_factual_question(
            question={
                "text": "first instrument code on 2026-09-15 sample",
                "question_class": "MARKET_INSTRUMENT",
            },
            temporal_cutoff={"cutoff_instant": "2026-09-15T20:00:00Z"},
            evidence_set=_evidence_set(rel, "HISTORICAL_DEVELOPMENT_ARTIFACT"),
            repository_root=ROOT,
            answer_normalization=norm,
        )
        self.assertTrue(
            values_equivalent(
                outcome.structured_facts[0]["value"],
                "us.aapl",
                normalization=norm,
            )
        )


class GroundedFactExtractionAntiGamingTests(unittest.TestCase):
    def test_no_case_id_branching_in_facts_sut(self) -> None:
        source = (ROOT / "src/market_platform_foundation/intelligence/benchmark_protocol/facts_sut.py").read_text(
            encoding="utf-8"
        )
        self.assertIsNone(re.search(r"IBP-FACTUAL-\d{3}", source))
        self.assertNotIn("if case_id ==", source)

    def test_sut_works_without_evaluator_gold_keys_in_blind_input(self) -> None:
        blind = {
            "case_id": "INDEPENDENT-001",
            "protocol_version": "IBP_FACTUAL_SMOKE_V1",
            "blind_mode": "A",
            "context_reset_token": "x",
            "question": {"text": "rows 2025-06-01", "question_class": "ROW_COUNT"},
            "evidence_set": _evidence_set(
                "tests/fixtures/intelligence_benchmark/grounded_fact_extraction/mini_row_count.json",
                "HISTORICAL_DEVELOPMENT_ARTIFACT",
            ),
            "temporal_cutoff": {"cutoff_instant": "2025-06-01T20:00:00Z"},
            "routing_expectation": {"template": "HISTORICAL_FACTUAL"},
        }
        for key in EVALUATOR_ONLY_MANIFEST_KEYS:
            self.assertNotIn(key, blind)
        response = run_ibp_facts_sut(blind, repository_root=ROOT)
        self.assertNotEqual(response.get("answer"), "")
        self.assertIn("structured_facts", response)

    def test_public_protocol_blind_cases_produce_structured_facts(self) -> None:
        protocol = load_candidate_factual_gold_protocol(ROOT)
        answerable = [
            row
            for row in protocol["cases"]
            if row.get("SCORING_GATE") == "ANSWERABLE_FROM_ADMITTED_EVIDENCE"
        ]
        for case in answerable:
            blind = build_factual_blind_case_input(case, context_reset_token=f"gf-{case['CASE_ID']}")
            response = run_ibp_facts_sut(blind, repository_root=ROOT)
            q_class = case["QUESTION"]["question_class"]
            if q_class == "ABSTENTION":
                self.assertEqual(response.get("answer"), "UNKNOWN")
            else:
                self.assertNotEqual(response.get("answer"), "UNKNOWN", case["CASE_ID"])
                self.assertTrue(response.get("structured_facts"), case["CASE_ID"])


if __name__ == "__main__":
    unittest.main()
