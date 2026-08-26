"""BUILD 27 prospective paper execution qualification tests."""

from __future__ import annotations

import os
import unittest

from market_platform_foundation.intelligence.paper_execution_qualification import (
    DEFAULT_HORIZON_NS,
    DEFAULT_INSTRUMENT_UNIVERSE,
    ExecutionIntegrityStatus,
    PaperEvidenceClass,
    PaperQualificationDisposition,
    REQUIRED_SCENARIOS,
    ScenarioStatus,
    build_initial_paper_portfolio_state,
    build_paper_execution_qualification_run,
    build_paper_execution_qualification_spec,
    derive_initial_portfolio_state_id,
    derive_qualification_spec_id,
    detect_run_freeze_violation,
    empty_funnel,
    execution_shortfall_bps,
    paper_execution_qualification_spec_v1_to_dict,
    reconcile_funnel,
    run_paper_execution_qualification,
    run_prospective_paper_fixture_lifecycle,
    run_scenarios,
    validate_forward_lineage,
    validate_no_future_quote,
    validate_opportunity_not_expired,
    validate_quote_fill_realism,
    verify_build26_integrity,
)
from tests.intelligence.outcome_fixtures import T


BUILD26_HEAD = "8812720989244d08a436a73cc0a27595538c7f21"
BUILD25_HEAD = "15e7a4f6fc88e5a1c90c6bc3b1b4f8c3a861d2f2"


class PaperExecutionQualificationSpecTests(unittest.TestCase):
    def test_spec_identity_deterministic(self) -> None:
        s1 = build_paper_execution_qualification_spec(
            source_build26_ref=BUILD26_HEAD,
            source_release_candidate_ref=BUILD25_HEAD,
            source_head=BUILD26_HEAD,
            qualification_start_ns=T,
        )
        s2 = build_paper_execution_qualification_spec(
            source_build26_ref=BUILD26_HEAD,
            source_release_candidate_ref=BUILD25_HEAD,
            source_head=BUILD26_HEAD,
            qualification_start_ns=T,
        )
        self.assertEqual(s1.qualification_spec_id, s2.qualification_spec_id)
        self.assertTrue(s1.qualification_spec_id.startswith("PEQSPEC-"))

    def test_spec_round_trip(self) -> None:
        spec = build_paper_execution_qualification_spec(
            source_build26_ref=BUILD26_HEAD,
            source_release_candidate_ref=BUILD25_HEAD,
            source_head=BUILD26_HEAD,
            qualification_start_ns=T,
        )
        payload = paper_execution_qualification_spec_v1_to_dict(spec)
        self.assertEqual(payload["required_execution_mode"], "PAPER")
        self.assertEqual(payload["required_execution_authority"], "PAPER_ONLY")
        self.assertEqual(payload["horizon_ns"], DEFAULT_HORIZON_NS)

    def test_live_execution_mode_rejected_in_run(self) -> None:
        spec = build_paper_execution_qualification_spec(
            source_build26_ref=BUILD26_HEAD,
            source_release_candidate_ref=BUILD25_HEAD,
            source_head=BUILD26_HEAD,
            qualification_start_ns=T,
        )
        with self.assertRaises(ValueError):
            build_paper_execution_qualification_run(
                spec=spec,
                source_head=BUILD26_HEAD,
                run_start_ns=T,
                execution_mode="LIVE",
            )


class InitialPortfolioTests(unittest.TestCase):
    def test_deterministic_identity(self) -> None:
        p1 = build_initial_paper_portfolio_state()
        p2 = build_initial_paper_portfolio_state()
        self.assertEqual(p1.state_id, p2.state_id)
        self.assertEqual(derive_initial_portfolio_state_id(p1), p1.state_id)

    def test_reset_changes_id(self) -> None:
        base = build_initial_paper_portfolio_state()
        changed = build_initial_paper_portfolio_state(initial_cash_minor=50_000_00)
        self.assertNotEqual(base.state_id, changed.state_id)


class ForwardLineageTests(unittest.TestCase):
    def test_replay_excluded(self) -> None:
        status, codes = validate_forward_lineage(
            evidence_class=PaperEvidenceClass.REPLAY_PAPER,
            forward_receipt_ref="ref",
            forecast_id="fc",
        )
        self.assertEqual(status, ExecutionIntegrityStatus.INVALID)

    def test_forward_lineage_valid(self) -> None:
        status, codes = validate_forward_lineage(
            evidence_class=PaperEvidenceClass.FORWARD_PAPER,
            forward_receipt_ref="FQPRCPT-test",
            forecast_id="fc-test",
        )
        self.assertEqual(status, ExecutionIntegrityStatus.VALID)


class FillRealismTests(unittest.TestCase):
    def test_market_buy_respects_ask(self) -> None:
        ok, _ = validate_quote_fill_realism(side="BUY", fill_price_minor=10100, bid_minor=9900, ask_minor=10100)
        self.assertTrue(ok)
        bad, codes = validate_quote_fill_realism(side="BUY", fill_price_minor=10000, bid_minor=9900, ask_minor=10100)
        self.assertFalse(bad)
        self.assertTrue(codes)

    def test_market_sell_respects_bid(self) -> None:
        ok, _ = validate_quote_fill_realism(side="SELL", fill_price_minor=9900, bid_minor=9900, ask_minor=10100)
        self.assertTrue(ok)

    def test_no_future_quote(self) -> None:
        ok, codes = validate_no_future_quote(fill_time_ns=T, quote_available_time_ns=T + 1)
        self.assertFalse(ok)

    def test_shortfall_buy_positive_when_worse(self) -> None:
        sf = execution_shortfall_bps(side="BUY", fill_price_minor=10200, reference_price_minor=10000)
        self.assertIsNotNone(sf)
        self.assertGreater(sf, 0)


class OpportunityExpiryTests(unittest.TestCase):
    def test_exact_boundary_expired(self) -> None:
        ok, codes = validate_opportunity_not_expired(
            decision_time_ns=T + 5,
            valid_until_ns=T + 5,
        )
        self.assertFalse(ok)


class FunnelTests(unittest.TestCase):
    def test_reconcile_empty_ok(self) -> None:
        ok, issues = reconcile_funnel(empty_funnel())
        self.assertTrue(ok)
        self.assertEqual(issues, [])


class ScenarioTests(unittest.TestCase):
    def test_required_scenarios_pass(self) -> None:
        os.environ["IMP_PAPER_EXECUTION"] = "1"
        results = run_scenarios(REQUIRED_SCENARIOS)
        failures = [r for r in results if r.status == ScenarioStatus.FAIL]
        self.assertEqual(failures, [], msg=str(failures))


class FixtureLifecycleTests(unittest.TestCase):
    def test_prospective_fixture_lifecycle(self) -> None:
        os.environ["IMP_PAPER_EXECUTION"] = "1"
        result = run_prospective_paper_fixture_lifecycle(
            source_build26_ref=BUILD26_HEAD,
            source_release_candidate_ref=BUILD25_HEAD,
            source_head=BUILD26_HEAD,
            qualification_start_ns=T,
        )
        self.assertTrue(result.spec_id.startswith("PEQSPEC-"))
        self.assertTrue(result.run_id.startswith("PEQRUN-"))
        self.assertIsNotNone(result.forward_receipt_ref)


class RunnerTests(unittest.TestCase):
    def test_run_paper_execution_qualification(self) -> None:
        os.environ["IMP_PAPER_EXECUTION"] = "1"
        result = run_paper_execution_qualification(
            source_build26_ref=BUILD26_HEAD,
            source_release_candidate_ref=BUILD25_HEAD,
            source_head=BUILD26_HEAD,
            qualification_start_ns=T,
        )
        self.assertIn(
            result.disposition,
            {
                PaperQualificationDisposition.PAPER_EXECUTION_QUALIFIED_WITH_LIMITATIONS,
                PaperQualificationDisposition.INSUFFICIENT_PAPER_EXECUTION_EVIDENCE,
                PaperQualificationDisposition.INVALID_EXECUTION_INTEGRITY,
            },
        )


class ZeroLiveBrokerTests(unittest.TestCase):
    def test_paper_orchestrator_source_has_no_broker_submit(self) -> None:
        import inspect

        from market_platform_foundation.intelligence.execution import engine as engine_mod

        source = inspect.getsource(engine_mod.PaperExecutionOrchestrator.execute_paper)
        for token in ("ibkr", "moomoo", "tradier", "tastytrade", "submit_order"):
            self.assertNotIn(token.lower(), source.lower())


class FreezeViolationTests(unittest.TestCase):
    def test_policy_change_detected(self) -> None:
        code = detect_run_freeze_violation(
            initial_opportunity_policy_ref="opp-1",
            current_opportunity_policy_ref="opp-2",
            initial_execution_policy_ref="exec-1",
            current_execution_policy_ref="exec-1",
        )
        self.assertIsNotNone(code)


class Build26IntegrityTests(unittest.TestCase):
    def test_build26_manifest_present(self) -> None:
        result = verify_build26_integrity(expected_head=BUILD26_HEAD)
        self.assertEqual(result.status, "PASS")
        self.assertTrue(result.manifest_present)


if __name__ == "__main__":
    unittest.main()
