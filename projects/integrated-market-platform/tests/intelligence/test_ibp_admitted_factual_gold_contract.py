"""IBP admitted factual gold M1 — contract, SUT boundary, UNKNOWN, hashing."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.benchmark_protocol.admitted_factual_gold import (  # noqa: E402
    AdmittedFactualGoldContractError,
    FACTUAL_GOLD_EVALUATOR_ONLY_CASE_KEYS,
    FactualUnknownVerdict,
    IBP_ADMITTED_FACTUAL_GOLD_SCHEMA_VERSION,
    IBP_FACTUAL_SMOKE_PROTOCOL_VERSION,
    compute_case_gold_hash,
    compute_caseset_hash,
    compute_goldset_hash,
    empty_protocol_template,
    factual_gold_hash_algorithm,
    load_factual_gold_protocol,
    project_factual_case_for_sut,
    validate_factual_gold_case,
    validate_factual_gold_protocol,
)
from market_platform_foundation.intelligence.benchmark_protocol.contamination import (  # noqa: E402
    BenchmarkContaminationError,
)


def _sample_answerable_case() -> dict:
    unknown_policy = {
        "correct_unknown_verdict": FactualUnknownVerdict.CORRECT_UNKNOWN.value,
        "encoded_in_evaluator_contract": True,
    }
    expected_facts = [
        {
            "expected_fact": {"field": "session_date", "value": "2026-09-15"},
            "source_artifact": "tests/fixtures/historical_development/aapl_2026-09-15_rth_sample.json",
            "source_record": "row:0",
            "source_hash": "sha256:0000000000000000000000000000000000000000000000000000000000000001",
        }
    ]
    case_id = "IBP-FACTUAL-SAMPLE-001"
    gold_hash = compute_case_gold_hash(
        case_id=case_id,
        expected_facts=expected_facts,
        unknown_policy=unknown_policy,
    )
    return {
        "CASE_ID": case_id,
        "MODE": "A",
        "QUESTION": {
            "text": "What is the session date in the admitted AAPL RTH sample?",
            "constructed_from_admitted_evidence_only": True,
        },
        "EVIDENCE_ACCESS_MODE": "ADMITTED_EVIDENCE_FIXED",
        "EVIDENCE_SET": {
            "evidence_access_mode": "ADMITTED_EVIDENCE_FIXED",
            "sources": [
                {
                    "source_type": "HISTORICAL_DEVELOPMENT_ARTIFACT",
                    "evidence_access_mode": "ADMITTED_EVIDENCE_FIXED",
                    "artifact_ref": "tests/fixtures/historical_development/aapl_2026-09-15_rth_sample.json",
                }
            ],
        },
        "EVIDENCE_FINGERPRINT": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "TEMPORAL_CUTOFF": {
            "kind": "SESSION_END",
            "cutoff_instant": "2026-09-15T20:00:00Z",
            "contamination_control": True,
        },
        "EXPECTED_FACTS": expected_facts,
        "ANSWER_NORMALIZATION": {
            "structured_facts_preferred": True,
            "case_folding": True,
            "trim_whitespace": True,
            "iso_timestamp_normalization": True,
            "numeric_tolerance": {"relative": 1e-9},
        },
        "ACCEPTABLE_EQUIVALENTS": [],
        "UNKNOWN_POLICY": unknown_policy,
        "PROVENANCE_REQUIREMENTS": {
            "gold_source_independent": True,
            "chain": ["expected_fact", "source_artifact", "source_record", "source_hash"],
        },
        "ROUTING_EXPECTATION": {"template": "HISTORICAL_FACTUAL"},
        "GOLD_HASH": gold_hash,
        "SCORING_GATE": "ANSWERABLE_FROM_ADMITTED_EVIDENCE",
        "evaluator_gold_ref": "evaluator_only/admitted_factual_gold/IBP-FACTUAL-SAMPLE-001.json",
        "evaluator_notes": "M1 contract test only — not a scored case",
    }


class IbpAdmittedFactualGoldContractTests(unittest.TestCase):
    def test_empty_protocol_fixture_loads(self) -> None:
        protocol = load_factual_gold_protocol(ROOT)
        self.assertEqual(protocol["schema_version"], IBP_ADMITTED_FACTUAL_GOLD_SCHEMA_VERSION)
        self.assertEqual(protocol["protocol_version"], IBP_FACTUAL_SMOKE_PROTOCOL_VERSION)
        self.assertEqual(protocol["cases"], [])
        self.assertFalse(protocol["freeze"]["cases_constructed"])

    def test_empty_protocol_matches_template(self) -> None:
        loaded = load_factual_gold_protocol(ROOT)
        template = empty_protocol_template()
        self.assertEqual(loaded["caseset_hash"], template["caseset_hash"])
        self.assertEqual(loaded["goldset_hash"], template["goldset_hash"])

    def test_hash_algorithm_documented_for_empty_caseset(self) -> None:
        self.assertEqual(factual_gold_hash_algorithm(), "sha256-canonical-json-v1")
        empty_hash = compute_caseset_hash([])
        self.assertEqual(len(empty_hash), 64)
        self.assertEqual(compute_goldset_hash([]), compute_goldset_hash([]))

    def test_sample_case_validates(self) -> None:
        validate_factual_gold_case(_sample_answerable_case())

    def test_sut_projection_strips_evaluator_fields(self) -> None:
        case = _sample_answerable_case()
        self.assertIn("evaluator_gold_ref", case)
        sut = project_factual_case_for_sut(case)
        self.assertNotIn("evaluator_gold_ref", sut)
        for key in FACTUAL_GOLD_EVALUATOR_ONLY_CASE_KEYS:
            self.assertNotIn(key, sut)
        self.assertIn("QUESTION", sut)
        self.assertIn("TEMPORAL_CUTOFF", sut)

    def test_evaluator_leak_detected(self) -> None:
        from market_platform_foundation.intelligence.benchmark_protocol.admitted_factual_gold import (
            assert_factual_case_safe_for_sut,
        )

        bundle = project_factual_case_for_sut(_sample_answerable_case())
        bundle["GOLD_HASH"] = "tamper"
        with self.assertRaises(BenchmarkContaminationError) as ctx:
            assert_factual_case_safe_for_sut(bundle)
        self.assertEqual(str(ctx.exception), "FACTUAL_EVALUATOR_GOLD_LEAK:GOLD_HASH")

        bundle = project_factual_case_for_sut(_sample_answerable_case())
        bundle["evaluator_gold_ref"] = "evaluator_only/admitted_factual_gold/leak.json"
        with self.assertRaises(BenchmarkContaminationError) as ctx:
            assert_factual_case_safe_for_sut(bundle)
        self.assertEqual(str(ctx.exception), "FACTUAL_EVALUATOR_GOLD_LEAK:evaluator_gold_ref")

    def test_temporal_cutoff_requires_contamination_control(self) -> None:
        case = copy.deepcopy(_sample_answerable_case())
        case["TEMPORAL_CUTOFF"] = {
            "kind": "SESSION_END",
            "cutoff_instant": "2026-09-15T20:00:00Z",
            "contamination_control": False,
        }
        with self.assertRaises(AdmittedFactualGoldContractError) as ctx:
            validate_factual_gold_case(case)
        self.assertEqual(str(ctx.exception), "FACTUAL_TEMPORAL_CONTAMINATION_CONTROL_REQUIRED")

    def test_unknown_verdict_enum_required(self) -> None:
        case = _sample_answerable_case()
        case = copy.deepcopy(case)
        case["UNKNOWN_POLICY"] = {
            "correct_unknown_verdict": "POST_HOC_UNKNOWN",
            "encoded_in_evaluator_contract": True,
        }
        with self.assertRaises(AdmittedFactualGoldContractError) as ctx:
            validate_factual_gold_case(case)
        self.assertEqual(str(ctx.exception), "FACTUAL_UNKNOWN_VERDICT_INVALID")

    def test_synthetic_gold_string_forbidden(self) -> None:
        case = _sample_answerable_case()
        case = copy.deepcopy(case)
        case["EXPECTED_FACTS"][0]["expected_fact"] = "synthetic-gold-001"
        with self.assertRaises(AdmittedFactualGoldContractError) as ctx:
            validate_factual_gold_case(case)
        self.assertEqual(str(ctx.exception), "FACTUAL_SYNTHETIC_GOLD_STRING_FORBIDDEN")

    def test_mixed_evidence_modes_forbidden(self) -> None:
        case = _sample_answerable_case()
        case = copy.deepcopy(case)
        case["EVIDENCE_SET"]["sources"].append(
            {
                "source_type": "ADMITTED_FIXTURE_RECORD",
                "evidence_access_mode": "CURRENT_WEB_LOOKUP",
                "artifact_ref": "https://example.invalid",
            }
        )
        with self.assertRaises(AdmittedFactualGoldContractError) as ctx:
            validate_factual_gold_case(case)
        self.assertEqual(str(ctx.exception), "FACTUAL_MIXED_EVIDENCE_ACCESS_MODE_FORBIDDEN")

    def test_protocol_with_inline_case_hashes(self) -> None:
        case = _sample_answerable_case()
        protocol = empty_protocol_template()
        protocol["cases"] = [case]
        protocol["caseset_hash"] = compute_caseset_hash([case])
        protocol["goldset_hash"] = compute_goldset_hash([case["evaluator_gold_ref"]])
        validate_factual_gold_protocol(protocol)


if __name__ == "__main__":
    unittest.main()
