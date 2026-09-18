"""IBP non-stub facts SUT protocol tests (no live Smoke10 or Full30 execution)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.benchmark_protocol.blind_input import (  # noqa: E402
    build_blind_case_input,
)
from market_platform_foundation.intelligence.benchmark_protocol.contamination import (  # noqa: E402
    EVALUATOR_ONLY_MANIFEST_KEYS,
)
from market_platform_foundation.intelligence.benchmark_protocol.facts_sut import (  # noqa: E402
    ibp_blind_mode_routing_plan,
    run_ibp_facts_sut,
)
from market_platform_foundation.intelligence.benchmark_protocol.historical_evidence_context import (  # noqa: E402
    build_historical_fixture_evidence_context,
)
from market_platform_foundation.intelligence.benchmark_protocol.smoke10_execution import (  # noqa: E402
    execute_smoke10_case,
    freeze_smoke10_run_configuration,
)
from market_platform_foundation.intelligence.benchmark_protocol.smoke10_evaluator import (  # noqa: E402
    load_evaluator_gold,
)
from market_platform_foundation.intelligence.benchmark_protocol.suite_catalog import (  # noqa: E402
    load_suite_catalog,
    smoke10_case_ids,
)
from market_platform_foundation.intelligence.benchmark_protocol.sut_dispatch import (  # noqa: E402
    resolve_sut_runner,
)
from market_platform_foundation.intelligence.benchmark_protocol.sut_profiles import (  # noqa: E402
    IBP_FACTS_SUT_MODEL_ID,
    IBP_FACTS_SUT_PROFILE_ID,
    IBP_HYPOTHESIS_FACTS_SUT_V1,
    IBP_SYNTHETIC_SUT_PROFILE_ID,
    resolve_sut_profile,
    sut_profile_documentation,
)
from market_platform_foundation.intelligence.contracts import SemanticEventType  # noqa: E402

STUB_BASELINE_FINGERPRINT_PREFIX = "76DDD188CD080365"
FREEZE_FIXTURE = (
    ROOT
    / "tests/fixtures/intelligence_benchmark/freeze/ibp_smoke10_nonstub_sut_freeze_v1.json"
)


class IntelligenceBenchmarkNonstubSutProtocolTests(unittest.TestCase):
    def test_sut_profile_documents_bounded_facts_responder(self) -> None:
        profile = resolve_sut_profile(IBP_FACTS_SUT_PROFILE_ID)
        doc = sut_profile_documentation(profile, code_sha="TEST_SHA")
        self.assertEqual(doc["SUT_NAME"], profile.name)
        self.assertEqual(doc["SUT_VERSION"], profile.version)
        self.assertEqual(doc["CODE_SHA"], "TEST_SHA")
        self.assertEqual(doc["HYPOTHESIS_ID"], IBP_HYPOTHESIS_FACTS_SUT_V1)
        self.assertEqual(doc["SUT_MODEL_ID"], IBP_FACTS_SUT_MODEL_ID)
        self.assertIsNotNone(doc["LIMITATION_CLASS"])

    def test_nonstub_freeze_differs_from_stub_baseline_fingerprint(self) -> None:
        stub = freeze_smoke10_run_configuration(ROOT, code_sha="CANONICAL_TEST_SHA")
        facts = freeze_smoke10_run_configuration(
            ROOT,
            code_sha="CANONICAL_TEST_SHA",
            sut_profile_id=IBP_FACTS_SUT_PROFILE_ID,
        )
        self.assertEqual(stub["sut_profile_id"], IBP_SYNTHETIC_SUT_PROFILE_ID)
        self.assertNotEqual(stub["frozen_config_fingerprint"], facts["frozen_config_fingerprint"])
        self.assertEqual(facts["sut_profile_id"], IBP_FACTS_SUT_PROFILE_ID)
        self.assertNotIn("full30_executed", facts)
        evidence_fp = json.loads(
            (
                ROOT
                / "evidence/intelligence-benchmark/imp-research-validation-04-lane-d-smoke10/frozen_config.json"
            ).read_text(encoding="utf-8")
        )["frozen_config_fingerprint"]
        self.assertTrue(evidence_fp.startswith(STUB_BASELINE_FINGERPRINT_PREFIX))
        self.assertNotEqual(facts["frozen_config_fingerprint"], evidence_fp)

    def test_checked_in_nonstub_freeze_artifact_matches_generator(self) -> None:
        self.assertTrue(FREEZE_FIXTURE.is_file(), "missing nonstub freeze fixture")
        expected = freeze_smoke10_run_configuration(
            ROOT,
            code_sha="109fd650df4998d953450eda267e8edfdad6de81",
            sut_profile_id=IBP_FACTS_SUT_PROFILE_ID,
        )
        pinned = json.loads(FREEZE_FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(pinned["frozen_config_fingerprint"], expected["frozen_config_fingerprint"])
        self.assertEqual(pinned["case_ids"], list(smoke10_case_ids(load_suite_catalog(ROOT))))

    def test_gold_inaccessible_to_sut_blind_input(self) -> None:
        catalog = load_suite_catalog(ROOT)
        case = catalog["cases"][0]
        blind = build_blind_case_input(case, context_reset_token="ctx-001")
        self.assertNotIn("evaluator_gold_ref", blind)
        for key in EVALUATOR_ONLY_MANIFEST_KEYS:
            self.assertNotIn(key, blind)

    def test_facts_sut_never_emits_gold_answer_field(self) -> None:
        catalog = load_suite_catalog(ROOT)
        case = catalog["cases"][0]
        response = run_ibp_facts_sut(
            build_blind_case_input(case, context_reset_token="ctx-facts-001"),
            repository_root=ROOT,
        )
        self.assertNotIn("gold_answer", response)
        self.assertEqual(response["sut_profile_id"], IBP_FACTS_SUT_PROFILE_ID)

    def test_facts_sut_without_fixture_resolver_missing_is_unknown(self) -> None:
        catalog = load_suite_catalog(ROOT)
        case = next(row for row in catalog["cases"] if not row.get("historical_harness_fixture"))
        response = run_ibp_facts_sut(
            build_blind_case_input(case, context_reset_token="ctx-no-fixture"),
            repository_root=ROOT,
        )
        self.assertEqual(response["answer"], "UNKNOWN")
        self.assertEqual(response["inference_abstention_reason"], "EVIDENCE_RESOLVER_MISSING")

    def test_historical_fixture_evidence_context_exposes_resolvers(self) -> None:
        fixture_rel = "tests/fixtures/historical_development/aapl_2026-09-15_rth_sample.json"
        context = build_historical_fixture_evidence_context(ROOT, fixture_rel)
        self.assertIsNotNone(context)
        assert context is not None
        self.assertTrue(callable(context.get("resolve_explain")))
        self.assertTrue(callable(context.get("resolve_inspect")))
        self.assertIn("explain:quality:system", context.get("available_explain_refs", ()))

    def test_facts_sut_with_fixture_can_emit_cited_non_unknown(self) -> None:
        catalog = load_suite_catalog(ROOT)
        case = next(row for row in catalog["cases"] if row.get("historical_harness_fixture"))
        response = run_ibp_facts_sut(
            build_blind_case_input(case, context_reset_token="ctx-fixture-cite"),
            repository_root=ROOT,
        )
        self.assertTrue(response["historical_fixture_loaded"])
        self.assertIsNone(response["inference_abstention_reason"])
        self.assertNotEqual(response["answer"], "UNKNOWN")
        self.assertTrue(response["answer"])

    def test_facts_sut_context_reset_is_per_case(self) -> None:
        catalog = load_suite_catalog(ROOT)
        case = catalog["cases"][0]
        first = run_ibp_facts_sut(
            build_blind_case_input(case, context_reset_token="ctx-reset-a"),
            repository_root=ROOT,
        )
        second = run_ibp_facts_sut(
            build_blind_case_input(case, context_reset_token="ctx-reset-b"),
            repository_root=ROOT,
        )
        self.assertEqual(first["context_reset_token"], "ctx-reset-a")
        self.assertEqual(second["context_reset_token"], "ctx-reset-b")
        self.assertEqual(first["case_id"], second["case_id"])
        self.assertEqual(second["final_state"], "CLOSED")

    def test_blind_modes_map_to_smart_router_event_types(self) -> None:
        expected = {
            "A": SemanticEventType.ORDER_FLOW_REVERSAL,
            "B": SemanticEventType.UNUSUAL_OPTIONS_ACTIVITY,
            "C": SemanticEventType.BORROW_CHANGE,
            "D": SemanticEventType.NEWS_EVENT,
            "E": SemanticEventType.REGIME_SHIFT,
        }
        for mode, event_type in expected.items():
            self.assertEqual(ibp_blind_mode_routing_plan(mode)[0], event_type)

    def test_evaluation_runs_only_after_sut_response(self) -> None:
        catalog = load_suite_catalog(ROOT)
        case = catalog["cases"][0]
        runner = resolve_sut_runner(IBP_FACTS_SUT_PROFILE_ID, repository_root=ROOT)
        call_order: list[str] = []

        def tracking_runner(blind_input: dict) -> dict:
            call_order.append("sut")
            return runner(blind_input)

        with mock.patch(
            "market_platform_foundation.intelligence.benchmark_protocol.smoke10_execution.load_evaluator_gold",
            side_effect=lambda *_args, **_kwargs: (
                call_order.append("gold")
                or {"gold_answer": "synthetic-gold-001", "do_not_expose_to_sut": True}
            ),
        ):
            execute_smoke10_case(
                repository_root=ROOT,
                case=case,
                frozen_config_fingerprint="TEST-FP",
                sut_runner=tracking_runner,
            )
        self.assertEqual(call_order, ["sut", "gold"])

    def test_single_case_protocol_does_not_execute_full_smoke10(self) -> None:
        with mock.patch(
            "market_platform_foundation.intelligence.benchmark_protocol.smoke10_execution.execute_smoke10_baseline",
            side_effect=AssertionError("FULL_SMOKE10_EXECUTED"),
        ):
            catalog = load_suite_catalog(ROOT)
            runner = resolve_sut_runner(IBP_FACTS_SUT_PROFILE_ID, repository_root=ROOT)
            row = execute_smoke10_case(
                repository_root=ROOT,
                case=catalog["cases"][0],
                frozen_config_fingerprint="PROTOCOL-FP",
                sut_runner=runner,
            )
        self.assertTrue(row["scores_executed"])
        self.assertFalse(row["evaluator_gold_loaded_for_sut"])

    def test_default_freeze_remains_stub_profile(self) -> None:
        frozen = freeze_smoke10_run_configuration(ROOT, code_sha="CANONICAL_TEST_SHA")
        self.assertEqual(frozen["sut_profile_id"], IBP_SYNTHETIC_SUT_PROFILE_ID)

    def test_load_evaluator_gold_is_evaluator_only_path(self) -> None:
        catalog = load_suite_catalog(ROOT)
        case = catalog["cases"][0]
        gold = load_evaluator_gold(ROOT, case["evaluator_gold_ref"])
        self.assertTrue(gold.get("do_not_expose_to_sut"))


if __name__ == "__main__":
    unittest.main()
