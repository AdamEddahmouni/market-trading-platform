"""Regression: answerability, claim linkage, absent vs negative, harness probes."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.benchmark_protocol.facts_sut import (  # noqa: E402
    run_ibp_facts_sut,
)
from market_platform_foundation.intelligence.benchmark_protocol.grounded_fact_extraction import (  # noqa: E402
    AnswerabilityClass,
    EvidencePolarity,
    FactualAnswerDisposition,
    answer_admitted_factual_question,
    answer_harness_factual_probe,
    classify_answerability,
    link_claim_to_evidence,
)
from market_platform_foundation.intelligence.benchmark_protocol.grounded_fact_extraction.evidence_projection import (  # noqa: E402
    ProjectedArtifact,
    artifact_support_hash,
)

_FIXTURE_PREFIX = "tests/fixtures/intelligence_benchmark/grounded_fact_independent"
_BARS = f"{_FIXTURE_PREFIX}/lane_b_synthetic_bars.json"
_POLARITY = f"{_FIXTURE_PREFIX}/lane_gi_polarity_bars.json"
_CUTOFF = {"cutoff_instant": "2024-12-15T00:00:00Z"}


def _evidence_set(artifact_rel: str) -> dict:
    return {
        "evidence_access_mode": "ADMITTED_EVIDENCE_FIXED",
        "sources": [
            {
                "source_type": "HISTORICAL_DEVELOPMENT_ARTIFACT",
                "evidence_access_mode": "ADMITTED_EVIDENCE_FIXED",
                "artifact_ref": artifact_rel,
            }
        ],
    }


class AnswerabilityClassificationTests(unittest.TestCase):
    def test_absent_evidence_when_no_payload(self) -> None:
        cls = classify_answerability(blind_mode="A", evidence_present=False)
        self.assertEqual(cls, AnswerabilityClass.ABSENT_EVIDENCE)

    def test_capability_absent_for_options_mode_on_bars(self) -> None:
        cls = classify_answerability(
            blind_mode="B",
            evidence_present=True,
            available_capabilities={"QUOTES", "TRADES"},
        )
        self.assertEqual(cls, AnswerabilityClass.CAPABILITY_ABSENT)

    def test_answerable_for_quotes_mode_on_bars(self) -> None:
        cls = classify_answerability(
            blind_mode="A",
            evidence_present=True,
            available_capabilities={"QUOTES", "TRADES"},
        )
        self.assertEqual(cls, AnswerabilityClass.ANSWERABLE)

    def test_contradiction_dominates(self) -> None:
        cls = classify_answerability(
            blind_mode="A",
            evidence_present=True,
            available_capabilities={"QUOTES", "TRADES"},
            conflicting=True,
        )
        self.assertEqual(cls, AnswerabilityClass.CONTRADICTING_EVIDENCE)


class ClaimLinkageAndPolarityTests(unittest.TestCase):
    def test_link_preserves_provenance_and_positive_polarity(self) -> None:
        artifact = ProjectedArtifact(
            artifact_ref=_BARS,
            source_type="HISTORICAL_DEVELOPMENT_ARTIFACT",
            payload={},
            support_hash=artifact_support_hash(ROOT, _BARS),
        )
        row = link_claim_to_evidence(
            field="raw_row_count",
            value=5,
            artifact=artifact,
            source_path="session:2024-11-07",
        )
        self.assertEqual(row["support_hash"], artifact.support_hash)
        self.assertEqual(row["evidence_polarity"], EvidencePolarity.POSITIVE.value)
        self.assertEqual(row["claim_link"]["source_path"], "session:2024-11-07")

    def test_zero_count_is_negative_not_absent(self) -> None:
        artifact = ProjectedArtifact(
            artifact_ref=_POLARITY,
            source_type="HISTORICAL_DEVELOPMENT_ARTIFACT",
            payload={},
            support_hash=artifact_support_hash(ROOT, _POLARITY),
        )
        row = link_claim_to_evidence(
            field="malformed_time_key_rows",
            value=0,
            artifact=artifact,
            source_path="session:2024-11-07;filter:time_key=missing",
        )
        self.assertEqual(row["evidence_polarity"], EvidencePolarity.NEGATIVE.value)

    def test_contamination_zero_is_negative_evidence_disposition(self) -> None:
        outcome = answer_admitted_factual_question(
            question={
                "text": "How many rows have literal time_key value 'never-present' on 2024-11-07?",
                "question_class": "CONTAMINATION_SIGNAL",
            },
            temporal_cutoff=_CUTOFF,
            evidence_set=_evidence_set(_POLARITY),
            repository_root=ROOT,
        )
        self.assertEqual(outcome.disposition, FactualAnswerDisposition.NEGATIVE_EVIDENCE)
        self.assertEqual(outcome.structured_facts[0]["value"], 0)
        self.assertEqual(
            outcome.structured_facts[0]["evidence_polarity"],
            EvidencePolarity.NEGATIVE.value,
        )
        self.assertIsNotNone(outcome.structured_facts[0].get("claim_link"))


class HarnessProbeRegressionTests(unittest.TestCase):
    def test_absent_harness_fixture_correct_unknown(self) -> None:
        outcome = answer_harness_factual_probe(
            repository_root=ROOT,
            fixture_rel=None,
            blind_mode="B",
            case_id="LANE-GI-ABSENT",
        )
        self.assertEqual(outcome.answer, "UNKNOWN")
        self.assertEqual(outcome.disposition, FactualAnswerDisposition.ABSENT_EVIDENCE)
        self.assertEqual(outcome.abstention_reason, "ABSENT_HARNESS_EVIDENCE")

    def test_options_mode_with_bars_capability_absent(self) -> None:
        outcome = answer_harness_factual_probe(
            repository_root=ROOT,
            fixture_rel=_BARS,
            blind_mode="B",
            case_id="LANE-GI-CAP",
        )
        self.assertEqual(outcome.answer, "UNKNOWN")
        self.assertEqual(outcome.disposition, FactualAnswerDisposition.CAPABILITY_ABSENT)
        self.assertEqual(outcome.abstention_reason, "CAPABILITY_EVIDENCE_ABSENT")

    def test_quotes_mode_extracts_structured_facts_with_provenance(self) -> None:
        outcome = answer_harness_factual_probe(
            repository_root=ROOT,
            fixture_rel=_BARS,
            blind_mode="A",
            case_id="LANE-GI-BARS",
        )
        self.assertEqual(outcome.disposition, FactualAnswerDisposition.SUPPORTED_ANSWER)
        self.assertNotEqual(outcome.answer, "UNKNOWN")
        self.assertTrue(outcome.structured_facts)
        for row in outcome.structured_facts:
            self.assertTrue(row.get("source_artifact"))
            self.assertTrue(row.get("support_hash"))
            self.assertIn("claim_link", row)

    def test_facts_sut_harness_path_no_quality_narrative(self) -> None:
        response = run_ibp_facts_sut(
            {
                "case_id": "LANE-GI-SUT-001",
                "blind_mode": "A",
                "context_reset_token": "gi-harness",
                "historical_harness_fixture": _BARS,
            },
            repository_root=ROOT,
        )
        self.assertNotIn("Quality state", response.get("answer") or "")
        self.assertNotEqual(response.get("inference_abstention_reason"), "EVIDENCE_RESOLVER_MISSING")
        self.assertEqual(response.get("factual_answer_disposition"), "SUPPORTED_ANSWER")
        self.assertTrue(response.get("structured_facts"))
        self.assertTrue(response.get("historical_fixture_loaded"))

    def test_facts_sut_absent_fixture_not_resolver_missing(self) -> None:
        response = run_ibp_facts_sut(
            {
                "case_id": "LANE-GI-SUT-002",
                "blind_mode": "C",
                "context_reset_token": "gi-absent",
            },
            repository_root=ROOT,
        )
        self.assertEqual(response.get("answer"), "UNKNOWN")
        self.assertEqual(response.get("inference_abstention_reason"), "ABSENT_HARNESS_EVIDENCE")
        self.assertEqual(response.get("factual_answer_disposition"), "ABSENT_EVIDENCE")
        self.assertFalse(response.get("historical_fixture_loaded"))


if __name__ == "__main__":
    unittest.main()
