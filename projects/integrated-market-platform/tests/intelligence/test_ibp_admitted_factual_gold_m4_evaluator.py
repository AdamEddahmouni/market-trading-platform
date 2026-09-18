"""Lane M4 — IBP admitted factual gold evaluator + harness (no scored run execution)."""

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
    FactualFactVerdict,
    FactualUnknownVerdict,
    admitted_artifacts_accessible,
    audit_factual_smoke_run_contamination,
    build_admitted_evidence_context,
    build_factual_blind_case_input,
    compute_caseset_hash,
    compute_goldset_hash,
    freeze_factual_smoke_run_configuration,
    load_candidate_factual_gold_protocol,
    load_factual_evaluator_gold,
    project_factual_case_for_sut,
    score_factual_case_dimensions,
    validate_factual_gold_protocol,
)
from market_platform_foundation.intelligence.benchmark_protocol.contamination import (  # noqa: E402
    EVALUATOR_ONLY_MANIFEST_KEYS,
)
from market_platform_foundation.intelligence.benchmark_protocol.facts_sut import run_ibp_facts_sut  # noqa: E402
from market_platform_foundation.intelligence.benchmark_protocol.admitted_factual_gold.fact_normalization import (  # noqa: E402
    values_equivalent,
)
from market_platform_foundation.intelligence.benchmark_protocol.sut_profiles import (  # noqa: E402
    IBP_FACTS_SUT_PROFILE_ID,
)

_CANDIDATE_PROTOCOL = (
    ROOT
    / "tests/fixtures/intelligence_benchmark/admitted_factual_gold/protocol_ibp_factual_smoke_v1_candidate.json"
)


class IbpAdmittedFactualGoldM4EvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.protocol = json.loads(_CANDIDATE_PROTOCOL.read_text(encoding="utf-8"))
        validate_factual_gold_protocol(cls.protocol)
        cls.answerable = [
            row
            for row in cls.protocol["cases"]
            if row.get("SCORING_GATE") == "ANSWERABLE_FROM_ADMITTED_EVIDENCE"
        ]

    def test_frozen_protocol_hashes_unchanged(self) -> None:
        self.assertEqual(self.protocol["caseset_hash"], "B3459E4F9D658687B12A6F8ABA4C81F15EEF51FFC05126A8B76698329C920A5C")
        self.assertEqual(self.protocol["goldset_hash"], "9F5B9638470D92C5AA071F9190710CF0244839B414E538995883C7394A7A308F")
        self.assertEqual(self.protocol["caseset_hash"], compute_caseset_hash(self.protocol["cases"]))
        refs = [row["evaluator_gold_ref"] for row in self.protocol["cases"]]
        self.assertEqual(self.protocol["goldset_hash"], compute_goldset_hash(refs))

    def test_blind_input_hides_evaluator_gold(self) -> None:
        for case in self.answerable:
            blind = build_factual_blind_case_input(case, context_reset_token="ctx-m4")
            for key in FACTUAL_GOLD_EVALUATOR_ONLY_CASE_KEYS:
                self.assertNotIn(key, blind)
            for key in EVALUATOR_ONLY_MANIFEST_KEYS:
                self.assertNotIn(key, blind)
            self.assertIn("evidence_set", blind)
            self.assertTrue(blind["admitted_evidence_artifact_refs"])

    def test_admitted_evidence_accessible_for_all_answerable_cases(self) -> None:
        for case in self.answerable:
            ok, missing = admitted_artifacts_accessible(ROOT, case["EVIDENCE_SET"])
            self.assertTrue(ok, msg=f"{case['CASE_ID']} missing {missing}")

    def test_sut_can_access_required_evidence_after_wiring(self) -> None:
        for case in self.answerable:
            blind = build_factual_blind_case_input(case, context_reset_token=f"ctx-{case['CASE_ID']}")
            response = run_ibp_facts_sut(blind, repository_root=ROOT)
            refs = blind["admitted_evidence_artifact_refs"]
            loaded = response.get("admitted_evidence_artifacts_loaded") or []
            self.assertEqual(sorted(loaded), sorted(refs), case["CASE_ID"])
            self.assertEqual(response.get("evidence_data_mode"), "FIXTURE_REPLAY")
            self.assertFalse(response.get("live_promotion_allowed"))

    def test_unknown_semantics_correct_unknown(self) -> None:
        case = next(row for row in self.answerable if row["CASE_ID"] == "IBP-FACTUAL-011")
        gold = load_factual_evaluator_gold(ROOT, case["evaluator_gold_ref"])
        scoring = score_factual_case_dimensions(
            sut_response={"answer": "UNKNOWN", "inference_abstention_reason": "NO_MSFT"},
            gold=gold,
        )
        self.assertEqual(scoring["dimensions"]["unknown_handling"], "PASS")
        verdicts = {row["field"]: row["verdict"] for row in scoring["fact_verdicts"]}
        self.assertEqual(verdicts.get("_unknown"), FactualFactVerdict.CORRECT_UNKNOWN.value)

    def test_unknown_semantics_unnecessary_unknown(self) -> None:
        case = next(row for row in self.answerable if row["CASE_ID"] == "IBP-FACTUAL-001")
        gold = load_factual_evaluator_gold(ROOT, case["evaluator_gold_ref"])
        scoring = score_factual_case_dimensions(
            sut_response={"answer": "UNKNOWN"},
            gold=gold,
        )
        self.assertEqual(scoring["dimensions"]["unknown_handling"], "FAIL")
        self.assertIn(FactualFactVerdict.UNNECESSARY_UNKNOWN.value, [r["verdict"] for r in scoring["fact_verdicts"]])

    def test_fact_normalization_numeric_tolerance(self) -> None:
        norm = self.answerable[0]["ANSWER_NORMALIZATION"]
        self.assertTrue(values_equivalent(1950, 1950.0, normalization=norm))
        self.assertTrue(values_equivalent("US.AAPL", "us.aapl", normalization=norm))

    def test_supported_fact_scoring(self) -> None:
        case = next(row for row in self.answerable if row["CASE_ID"] == "IBP-FACTUAL-001")
        gold = load_factual_evaluator_gold(ROOT, case["evaluator_gold_ref"])
        scoring = score_factual_case_dimensions(
            sut_response={
                "answer": "instrument_code: US.AAPL",
                "structured_facts": [{"field": "instrument_code", "value": "US.AAPL"}],
                "freshness": "ADMITTED_EVIDENCE_FIXED",
                "authority": "ADMITTED_EVIDENCE_FIXED",
                "provenance_complete": True,
                "routing_template": case["ROUTING_EXPECTATION"]["template"],
                "final_state": "CLOSED",
                "operator_close": "OK",
                "catastrophic": False,
            },
            gold=gold,
        )
        self.assertEqual(scoring["dimensions"]["facts"], "PASS")
        self.assertIn(
            FactualFactVerdict.SUPPORTED_FACT.value,
            [row["verdict"] for row in scoring["fact_verdicts"]],
        )

    def test_context_reset_tokens_unique_per_case(self) -> None:
        frozen = freeze_factual_smoke_run_configuration(ROOT, sut_profile_id=IBP_FACTS_SUT_PROFILE_ID)
        tokens = {
            build_factual_blind_case_input(
                case,
                context_reset_token=f"reset-{case['CASE_ID']}-{frozen['frozen_config_fingerprint'][:8]}",
            )["context_reset_token"]
            for case in self.answerable[:3]
        }
        self.assertEqual(len(tokens), 3)

    def test_freeze_config_immutable_fields(self) -> None:
        from market_platform_foundation.canonical import canonical_bytes, sha256_bytes

        frozen = freeze_factual_smoke_run_configuration(ROOT, sut_profile_id=IBP_FACTS_SUT_PROFILE_ID)
        body = {key: value for key, value in frozen.items() if key not in {"frozen_config_fingerprint", "frozen_at_utc"}}
        reversed_body = {**body, "case_ids": list(reversed(body["case_ids"]))}
        reversed_fp = sha256_bytes(canonical_bytes(reversed_body))
        self.assertNotEqual(frozen["frozen_config_fingerprint"], reversed_fp)

    def test_contamination_audit_passes_for_wired_harness(self) -> None:
        case_results = []
        for case in self.answerable[:2]:
            blind = build_factual_blind_case_input(case, context_reset_token=f"audit-{case['CASE_ID']}")
            sut_response = run_ibp_facts_sut(blind, repository_root=ROOT)
            case_results.append(
                {
                    "case_id": case["CASE_ID"],
                    "context_reset_token": blind["context_reset_token"],
                    "prior_case_ids_visible_to_sut": False,
                    "evaluator_gold_loaded_for_sut": False,
                    "sut_response_includes_gold": False,
                    "evidence_set": case["EVIDENCE_SET"],
                    "sut_response": sut_response,
                }
            )
        audit = audit_factual_smoke_run_contamination(
            {"case_results": case_results, "frozen_config_fingerprint": "TEST_FP", "config_change_detected": False},
            repository_root=ROOT,
            frozen_config_fingerprint="TEST_FP",
        )
        self.assertEqual(audit["checks"]["SUT_CAN_ACCESS_REQUIRED_EVIDENCE"], "PASS")
        self.assertEqual(audit["checks"]["FIXTURE_REPLAY_NOT_PROMOTED_TO_LIVE"], "PASS")
        self.assertEqual(audit["checks"]["DID_SYSTEM_SEE_GOLD"], "PASS")

    def test_evaluator_loads_gold_after_sut_projection_only(self) -> None:
        case = self.answerable[0]
        sut_bundle = project_factual_case_for_sut(case)
        self.assertNotIn("EXPECTED_FACTS", sut_bundle)
        gold = load_factual_evaluator_gold(ROOT, case["evaluator_gold_ref"])
        self.assertEqual(gold["CASE_ID"], case["CASE_ID"])

    def test_temporal_cutoff_present_in_sut_bundle(self) -> None:
        for case in self.answerable:
            sut = project_factual_case_for_sut(case)
            cutoff = sut["TEMPORAL_CUTOFF"]
            self.assertTrue(cutoff.get("contamination_control"))

    def test_factual_smoke_baseline_not_executed_in_m4_tests(self) -> None:
        protocol = load_candidate_factual_gold_protocol(ROOT)
        self.assertFalse(protocol["freeze"]["smoke10_executed"])
        self.assertEqual(protocol["freeze"]["status"], "FROZEN")


if __name__ == "__main__":
    unittest.main()
