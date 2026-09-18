"""Lane B: synthetic grounded-fact fixtures (no evaluator gold, no owner fixture values)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.benchmark_protocol.admitted_factual_gold.fact_normalization import (  # noqa: E402
    normalize_scalar,
    values_equivalent,
)
from market_platform_foundation.intelligence.benchmark_protocol.facts_sut import run_ibp_facts_sut  # noqa: E402
from market_platform_foundation.intelligence.benchmark_protocol.grounded_fact_extraction import (  # noqa: E402
    FactualAnswerDisposition,
    answer_admitted_factual_question,
)
from market_platform_foundation.intelligence.benchmark_protocol.grounded_fact_extraction.evidence_projection import (  # noqa: E402
    artifact_support_hash,
)
from market_platform_foundation.intelligence.benchmark_protocol.grounded_fact_extraction.pipeline import (  # noqa: E402
    _detect_conflicts,
    _facts_have_provenance,
)
from market_platform_foundation.intelligence.benchmark_protocol.grounded_fact_extraction.question_handlers import (  # noqa: E402
    QUESTION_CLASS_HANDLERS,
)

_FIXTURE_PREFIX = "tests/fixtures/intelligence_benchmark/grounded_fact_independent"
_BARS = f"{_FIXTURE_PREFIX}/lane_b_synthetic_bars.json"
_GOV = f"{_FIXTURE_PREFIX}/lane_b_governance.json"
_PROVIDER = f"{_FIXTURE_PREFIX}/lane_b_provider_state.json"
_POST_CUTOFF = f"{_FIXTURE_PREFIX}/lane_b_post_cutoff_bars.json"
_CUTOFF = {"cutoff_instant": "2024-12-15T00:00:00Z"}


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


class GroundedFactIndependentNormalizationTests(unittest.TestCase):
    def test_boolean_normalization_case_folding(self) -> None:
        norm = {"case_folding": True}
        self.assertTrue(values_equivalent("TRUE", "true", normalization=norm))
        self.assertEqual(normalize_scalar(True, normalization=norm), "true")

    def test_integer_normalization_numeric_tolerance(self) -> None:
        norm = {"numeric_tolerance": {"relative": 0.02}}
        self.assertTrue(values_equivalent(501, 500, normalization=norm))
        self.assertFalse(values_equivalent(530, 500, normalization=norm))


class GroundedFactIndependentDispositionTests(unittest.TestCase):
    def test_supported_integer_row_count(self) -> None:
        outcome = answer_admitted_factual_question(
            question={
                "text": "How many raw bar rows are under session 2024-11-07?",
                "question_class": "ROW_COUNT",
            },
            temporal_cutoff=_CUTOFF,
            evidence_set=_evidence_set(_BARS, "HISTORICAL_DEVELOPMENT_ARTIFACT"),
            repository_root=ROOT,
        )
        self.assertEqual(outcome.disposition, FactualAnswerDisposition.SUPPORTED_ANSWER)
        self.assertEqual(outcome.structured_facts[0]["value"], 5)

    def test_supported_instrument_identity(self) -> None:
        outcome = answer_admitted_factual_question(
            question={"text": "primary instrument on sample", "question_class": "MARKET_INSTRUMENT"},
            temporal_cutoff=_CUTOFF,
            evidence_set=_evidence_set(_BARS, "HISTORICAL_DEVELOPMENT_ARTIFACT"),
            repository_root=ROOT,
        )
        self.assertEqual(outcome.disposition, FactualAnswerDisposition.SUPPORTED_ANSWER)
        self.assertEqual(outcome.structured_facts[0]["value"], "US.LANE_B")

    def test_supported_session_identity(self) -> None:
        outcome = answer_admitted_factual_question(
            question={"text": "session keys present", "question_class": "SESSION_IDENTITY"},
            temporal_cutoff=_CUTOFF,
            evidence_set=_evidence_set(_BARS, "HISTORICAL_DEVELOPMENT_ARTIFACT"),
            repository_root=ROOT,
        )
        self.assertEqual(outcome.disposition, FactualAnswerDisposition.SUPPORTED_ANSWER)
        self.assertEqual(outcome.structured_facts[0]["value"], 2)

    def test_supported_enum_authority_class(self) -> None:
        outcome = answer_admitted_factual_question(
            question={
                "text": "What corpus_evidence_authority value is declared?",
                "question_class": "AUTHORITY_CLASS",
            },
            temporal_cutoff=_CUTOFF,
            evidence_set=_evidence_set(_GOV),
            repository_root=ROOT,
        )
        self.assertEqual(outcome.disposition, FactualAnswerDisposition.SUPPORTED_ANSWER)
        self.assertEqual(outcome.structured_facts[0]["value"], "MANIFEST_ONLY")

    def test_supported_governed_dataset_id(self) -> None:
        outcome = answer_admitted_factual_question(
            question={
                "text": "What dataset_id is declared in the manifest?",
                "question_class": "GOVERNED_MANIFEST",
            },
            temporal_cutoff=_CUTOFF,
            evidence_set=_evidence_set(_GOV),
            repository_root=ROOT,
        )
        self.assertEqual(outcome.disposition, FactualAnswerDisposition.SUPPORTED_ANSWER)
        self.assertEqual(outcome.structured_facts[0]["value"], "lane.b.independent.v9")

    def test_supported_provider_state_row_count(self) -> None:
        outcome = answer_admitted_factual_question(
            question={
                "text": "How many moomoo rows are reported?",
                "question_class": "PROVIDER_VERIFICATION",
            },
            temporal_cutoff=_CUTOFF,
            evidence_set=_evidence_set(_PROVIDER),
            repository_root=ROOT,
        )
        self.assertEqual(outcome.disposition, FactualAnswerDisposition.SUPPORTED_ANSWER)
        self.assertEqual(outcome.structured_facts[0]["value"], 777)

    def test_artifact_support_hash_is_sha256_prefixed(self) -> None:
        digest = artifact_support_hash(ROOT, _BARS)
        self.assertTrue(digest.startswith("sha256:"))
        outcome = answer_admitted_factual_question(
            question={"text": "rows on 2024-11-07", "question_class": "ROW_COUNT"},
            temporal_cutoff=_CUTOFF,
            evidence_set=_evidence_set(_BARS, "HISTORICAL_DEVELOPMENT_ARTIFACT"),
            repository_root=ROOT,
        )
        self.assertEqual(outcome.structured_facts[0]["support_hash"], digest)

    def test_missing_evidence_file_correct_unknown_path(self) -> None:
        outcome = answer_admitted_factual_question(
            question={"text": "count rows", "question_class": "ROW_COUNT"},
            temporal_cutoff=_CUTOFF,
            evidence_set=_evidence_set(f"{_FIXTURE_PREFIX}/does_not_exist_lane_b.json"),
            repository_root=ROOT,
        )
        self.assertEqual(outcome.answer, "UNKNOWN")
        self.assertEqual(outcome.disposition, FactualAnswerDisposition.EVIDENCE_NOT_PROJECTABLE)

    def test_missing_requested_field_not_projectable(self) -> None:
        outcome = answer_admitted_factual_question(
            question={"text": "What is the launch_code in manifest?", "question_class": "GOVERNED_MANIFEST"},
            temporal_cutoff=_CUTOFF,
            evidence_set=_evidence_set(_GOV),
            repository_root=ROOT,
        )
        self.assertEqual(outcome.answer, "UNKNOWN")
        self.assertEqual(outcome.disposition, FactualAnswerDisposition.EVIDENCE_NOT_PROJECTABLE)

    def test_conflicting_evidence_disposition(self) -> None:
        facts = [
            {"field": "lane_b_metric", "value": 10, "source_artifact": "a", "source_path": "p", "support_hash": "sha256:aa"},
            {"field": "lane_b_metric", "value": 11, "source_artifact": "a", "source_path": "p", "support_hash": "sha256:aa"},
        ]
        self.assertTrue(_detect_conflicts(facts))

        def _conflicting_handler(artifact, question_text):  # noqa: ANN001
            return facts

        with patch.dict(QUESTION_CLASS_HANDLERS, {"ROW_COUNT": _conflicting_handler}, clear=False):
            outcome = answer_admitted_factual_question(
                question={"text": "rows on 2024-11-07", "question_class": "ROW_COUNT"},
                temporal_cutoff=_CUTOFF,
                evidence_set=_evidence_set(_BARS, "HISTORICAL_DEVELOPMENT_ARTIFACT"),
                repository_root=ROOT,
            )
        self.assertEqual(outcome.disposition, FactualAnswerDisposition.CONFLICTING_EVIDENCE)

    def test_insufficient_provenance_disposition(self) -> None:
        bad_facts = [
            {"field": "lane_b_metric", "value": 10, "source_artifact": "", "source_path": "p", "support_hash": ""},
        ]
        self.assertFalse(_facts_have_provenance(bad_facts))

        def _bad_provenance_handler(artifact, question_text):  # noqa: ANN001
            return bad_facts

        with patch.dict(QUESTION_CLASS_HANDLERS, {"ROW_COUNT": _bad_provenance_handler}, clear=False):
            outcome = answer_admitted_factual_question(
                question={"text": "rows on 2024-11-07", "question_class": "ROW_COUNT"},
                temporal_cutoff=_CUTOFF,
                evidence_set=_evidence_set(_BARS, "HISTORICAL_DEVELOPMENT_ARTIFACT"),
                repository_root=ROOT,
            )
        self.assertEqual(outcome.disposition, FactualAnswerDisposition.INSUFFICIENT_PROVENANCE)

    def test_temporal_cutoff_refusal_post_cutoff_bar(self) -> None:
        outcome = answer_admitted_factual_question(
            question={"text": "rows on 2024-12-01", "question_class": "ROW_COUNT"},
            temporal_cutoff={"cutoff_instant": "2024-12-01T12:00:00Z"},
            evidence_set=_evidence_set(_POST_CUTOFF, "HISTORICAL_DEVELOPMENT_ARTIFACT"),
            repository_root=ROOT,
        )
        self.assertEqual(outcome.disposition, FactualAnswerDisposition.TEMPORAL_CUTOFF_REFUSED)
        self.assertEqual(outcome.answer, "UNKNOWN")

    def test_abstention_correct_unknown(self) -> None:
        outcome = answer_admitted_factual_question(
            question={
                "text": "What is the closing price for WXYZ on 2024-11-07?",
                "question_class": "ABSTENTION",
            },
            temporal_cutoff=_CUTOFF,
            evidence_set=_evidence_set(_BARS, "HISTORICAL_DEVELOPMENT_ARTIFACT"),
            repository_root=ROOT,
        )
        self.assertEqual(outcome.disposition, FactualAnswerDisposition.CORRECT_UNKNOWN)
        self.assertEqual(outcome.answer, "UNKNOWN")

    def test_unanswerable_metric_correct_unknown(self) -> None:
        outcome = answer_admitted_factual_question(
            question={
                "text": "What is directional_accuracy for lane b?",
                "question_class": "UNANSWERABLE_METRIC",
            },
            temporal_cutoff=_CUTOFF,
            evidence_set=_evidence_set(_GOV),
            repository_root=ROOT,
        )
        self.assertEqual(outcome.disposition, FactualAnswerDisposition.CORRECT_UNKNOWN)


class GroundedFactIndependentSutImportTests(unittest.TestCase):
    def test_facts_sut_imports_without_evaluator_gold(self) -> None:
        blind = {
            "case_id": "LANE-B-INDEP-001",
            "protocol_version": "IBP_FACTUAL_SMOKE_V1",
            "blind_mode": "A",
            "context_reset_token": "lane-b-independent",
            "question": {
                "text": "How many raw bar rows are under session 2024-11-07?",
                "question_class": "ROW_COUNT",
            },
            "evidence_set": _evidence_set(_BARS, "HISTORICAL_DEVELOPMENT_ARTIFACT"),
            "temporal_cutoff": _CUTOFF,
            "routing_expectation": {"template": "HISTORICAL_FACTUAL"},
        }
        response = run_ibp_facts_sut(blind, repository_root=ROOT)
        self.assertNotEqual(response.get("answer"), "UNKNOWN")
        self.assertTrue(response.get("structured_facts"))


if __name__ == "__main__":
    unittest.main()
