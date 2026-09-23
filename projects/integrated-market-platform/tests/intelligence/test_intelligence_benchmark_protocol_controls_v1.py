"""RTH15-10 IBP protocol controls: lookahead, catastrophe, invalidation, vanity ban."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.benchmark_protocol import (  # noqa: E402
    apply_contamination_invalidation,
    assert_no_lookahead_in_blind_input,
    assert_no_vanity_aggregate_score,
    audit_smoke10_run_contamination,
    build_protocol_v1_freeze_certificate,
    execute_smoke10_baseline,
    freeze_smoke10_run_configuration,
    load_suite_catalog,
)
from market_platform_foundation.intelligence.benchmark_protocol.blind_input import (  # noqa: E402
    build_blind_case_input,
)
from market_platform_foundation.intelligence.benchmark_protocol.protocol_controls import (  # noqa: E402
    BLIND_MODE_DEFINITIONS,
    CATASTROPHIC_CRITERIA,
    CONTAMINATED_CASE_POLICY,
    LOOKAHEAD_POLICY,
    VANITY_AGGREGATE_SCORE_POLICY,
)
from market_platform_foundation.intelligence.benchmark_protocol.smoke10_evaluator import (  # noqa: E402
    score_case_dimensions,
)


class IntelligenceBenchmarkProtocolControlsV1Tests(unittest.TestCase):
    def test_protocol_freeze_certificate_marks_rth15_10_complete(self) -> None:
        freeze = build_protocol_v1_freeze_certificate(ROOT)
        self.assertEqual(freeze["RTH15_10_COMPLETE"], "YES")
        self.assertEqual(freeze["lookahead_policy"], LOOKAHEAD_POLICY)
        self.assertEqual(freeze["contaminated_case_policy"], CONTAMINATED_CASE_POLICY)
        self.assertEqual(freeze["vanity_aggregate_score_policy"], VANITY_AGGREGATE_SCORE_POLICY)
        self.assertEqual(set(BLIND_MODE_DEFINITIONS), {"A", "B", "C", "D", "E"})
        self.assertIn("GOLD_EXPOSED_TO_SUT", CATASTROPHIC_CRITERIA)
        for value in freeze["rth15_10_properties"].values():
            self.assertEqual(value, "PRESENT")

    def test_blind_input_rejects_lookahead_keys(self) -> None:
        with self.assertRaises(ValueError) as raised:
            assert_no_lookahead_in_blind_input({"case_id": "X", "gold_answer": "leak"})
        self.assertIn("IBP_LOOKAHEAD_FORBIDDEN", str(raised.exception))

    def test_catalog_blind_inputs_have_no_lookahead(self) -> None:
        catalog = load_suite_catalog(ROOT)
        for case in catalog["cases"]:
            blind = build_blind_case_input(case, context_reset_token=f"t-{case['case_id']}")
            assert_no_lookahead_in_blind_input(blind)
            self.assertEqual(blind["lookahead_policy"], "FORBIDDEN")
            self.assertNotIn("evaluator_gold_ref", blind)

    def test_vanity_aggregate_score_forbidden(self) -> None:
        with self.assertRaises(ValueError) as raised:
            assert_no_vanity_aggregate_score({"overall_score": 0.9})
        self.assertIn("IBP_VANITY_AGGREGATE_FORBIDDEN", str(raised.exception))

    def test_contaminated_case_is_invalidated_not_partial_credit(self) -> None:
        frozen = freeze_smoke10_run_configuration(ROOT)
        run = execute_smoke10_baseline(ROOT, frozen_config=frozen)
        run["case_results"][0]["sut_response_includes_gold"] = True
        run["case_results"][0]["sut_response"]["gold_answer"] = "leaked"
        run["contamination_audit"] = audit_smoke10_run_contamination(
            run,
            frozen_config_fingerprint=frozen["frozen_config_fingerprint"],
        )
        self.assertEqual(run["contamination_audit"]["checks"]["DID_SYSTEM_SEE_GOLD"], "FAIL")
        apply_contamination_invalidation(run)
        first = run["case_results"][0]
        self.assertEqual(first["case_validity"], "INVALID")
        self.assertFalse(first["partial_credit_applied"])
        self.assertFalse(first["scores_executed"])
        self.assertTrue(all(value == "INVALID" for value in first["dimension_scores"].values()))
        self.assertIn(first["case_id"], run["invalidated_case_ids"])

    def test_catastrophic_criteria_trigger_on_gold_exposure(self) -> None:
        scoring = score_case_dimensions(
            sut_response={
                "answer": "UNKNOWN",
                "freshness": "FIXTURE",
                "authority": "HISTORICAL_DEVELOPMENT",
                "provenance_complete": True,
                "routing": "A",
                "final_state": "CLOSED",
                "operator_close": "OK",
                "catastrophic": False,
            },
            gold={"gold_answer": "synthetic-gold-001"},
            blind_mode="A",
            blind_input={"case_id": "IBP-CASE-001"},
            case_row_flags={"sut_response_includes_gold": True},
        )
        self.assertEqual(scoring["dimensions"]["catastrophic"], "FAIL")
        self.assertIn("CATASTROPHIC_GOLD_EXPOSURE", scoring["failure_reasons"])

    def test_freeze_embeds_protocol_controls_and_clean_run_has_no_invalid_cases(self) -> None:
        frozen = freeze_smoke10_run_configuration(ROOT)
        self.assertEqual(frozen["lookahead_policy"], "FORBIDDEN")
        self.assertEqual(frozen["protocol_freeze_certificate"]["RTH15_10_COMPLETE"], "YES")
        with tempfile.TemporaryDirectory() as tmp:
            run = execute_smoke10_baseline(
                ROOT,
                frozen_config=frozen,
                artifact_root=Path(tmp),
            )
            cert_path = Path(tmp) / "protocol_freeze_certificate.json"
            self.assertTrue(cert_path.is_file())
        self.assertEqual(run["contamination_audit"]["overall"], "PASS")
        self.assertEqual(run.get("invalidated_case_ids"), [])
        self.assertEqual(run["summaries"]["vanity_aggregate_score"], "FORBIDDEN")
        self.assertNotIn("overall_score", run)
        self.assertNotIn("pass_rate", run["summaries"])
        for row in run["case_results"]:
            self.assertEqual(row["case_validity"], "VALID")
            self.assertIn("facts", row["dimension_scores"])
            self.assertTrue(isinstance(row["dimension_scores"]["facts"], str))


if __name__ == "__main__":
    unittest.main()
