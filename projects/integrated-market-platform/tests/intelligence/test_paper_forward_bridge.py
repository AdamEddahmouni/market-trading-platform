"""Tests for governed Paper forward-testing bridge."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "intelligence"))

from market_platform_foundation.intelligence.news_strategy_evaluation.contracts import (  # noqa: E402
    EvaluationDecision,
    PolicyClassification,
    StrategyEvaluationDecision,
)
from market_platform_foundation.intelligence.paper_forward_bridge import (  # noqa: E402
    ForwardTestMode,
    ForwardTestRunKind,
    ForwardTestService,
    ForwardTestServiceError,
    ForwardTestState,
    ForwardTestStore,
)
from market_platform_foundation.intelligence.paper_forward_bridge.evaluation import (  # noqa: E402
    evaluate_forward_test,
)
from market_platform_foundation.intelligence.paper_forward_bridge.paper_handoff import (  # noqa: E402
    build_decision_source_snapshot,
    build_paper_preview_body,
)
from market_platform_foundation.intelligence.paper_forward_bridge.temporal import (  # noqa: E402
    ForwardTestTemporalError,
    assert_decision_payload_immutable,
    assert_input_observable_at_decision,
    assert_run_kind_forward,
)
from market_platform_foundation.paper.decision_source import (  # noqa: E402
    parse_decision_source_snapshot,
    validate_snapshot_against_correlation,
)
from market_platform_foundation.ui_api.forward_test_projections import (  # noqa: E402
    create_forward_test_decision,
    create_forward_test_session,
    evaluate_forward_test_decision,
    lock_forward_test_decision,
    submit_forward_test_to_paper,
)
from market_platform_foundation.ui_api.paper_projections import open_paper_session  # noqa: E402
from market_platform_foundation.ui_api.store import ReplayStore  # noqa: E402
from forward_test_activation_support import (  # noqa: E402
    BASELINE_POLICY,
    CAMPAIGN_SLUG,
    POLICY_VERSION,
    ActivatedForwardTestCase,
    create_activated_session,
    enable_test_campaigns_root,
    seed_baseline_campaign,
)


T0 = 1_700_000_000_000_000_000
HOUR = 3_600_000_000_000


def _strategy_decision(*, instrument_id: str = "ACME") -> StrategyEvaluationDecision:
    return StrategyEvaluationDecision(
        decision_id="sed-1",
        evaluation_run_id="run-1",
        sample_id="sample-1",
        policy_id="news_deterministic_baseline",
        policy_version="1.0.0",
        policy_classification=PolicyClassification.BASELINE_DETERMINISTIC,
        config_hash="cfg-1",
        as_of="2026-09-09T12:00:00Z",
        instrument_id=instrument_id,
        asset_class="EQUITY",
        decision=EvaluationDecision.POSITIVE_DIRECTIONAL_BIAS,
        normalized_directional_units=1,
        simulation_only=True,
        execution_authority=False,
        news_event_ids=("evt-1",),
        inference_record_ids=("inf-1",),
        feature_snapshot_id="snap-1",
        market_snapshot_ref="mkt-1",
    )


class ForwardTestDomainTests(ActivatedForwardTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.store = ForwardTestStore()
        self.service = ForwardTestService(self.store)

    def test_create_lock_and_observe_lifecycle(self) -> None:
        session = create_activated_session(
            self.service,
            self.campaigns_root,
            evaluation_horizon_ns=HOUR,
            created_at_ns=T0,
        )
        decision = self.service.create_decision(
            account_id="paper-a",
            mode="PAPER",
            session_id=session.session_id,
            symbol="ACME",
            direction="POSITIVE_DIRECTIONAL_BIAS",
            decision_time_ns=T0,
            source_time_ns=T0 - 1,
            strategy_id=BASELINE_POLICY,
            strategy_version=POLICY_VERSION,
            test_mode=ForwardTestMode.SIGNAL_ONLY,
        )
        self.assertEqual(decision.run_kind, ForwardTestRunKind.FORWARD_TEST)
        locked = self.service.lock_decision(
            forward_test_id=decision.forward_test_id,
            account_id="paper-a",
            locked_at_ns=T0,
        )
        self.assertEqual(locked.state, ForwardTestState.LOCKED)
        observed = self.service.submit_to_paper(
            forward_test_id=decision.forward_test_id,
            account_id="paper-a",
            submitted_at_ns=T0 + 1,
        )
        self.assertEqual(observed.state, ForwardTestState.OBSERVING)
        with_obs = self.service.attach_observation(
            forward_test_id=decision.forward_test_id,
            account_id="paper-a",
            observed_at_ns=T0 + HOUR,
            source_time_ns=T0 + HOUR,
            payload={"reference_price": 100.0},
        )
        self.assertGreaterEqual(len(with_obs.observations), 1)

    def test_strategy_evaluation_handoff(self) -> None:
        session = create_activated_session(
            self.service,
            self.campaigns_root,
            evaluation_horizon_ns=HOUR,
            created_at_ns=T0,
        )
        decision = self.service.create_decision_from_strategy_evaluation(
            account_id="paper-a",
            mode="PAPER",
            session_id=session.session_id,
            strategy_decision=_strategy_decision(),
            decision_time_ns=T0,
            source_time_ns=T0 - 1,
            test_mode=ForwardTestMode.EXECUTION,
            quantity=10,
            evaluation_horizon_ns=HOUR,
        )
        self.assertFalse(_strategy_decision().execution_authority)
        locked = self.service.lock_decision(
            forward_test_id=decision.forward_test_id,
            account_id="paper-a",
            locked_at_ns=T0,
        )
        body = build_paper_preview_body(locked)
        self.assertEqual(body["side"], "BUY")
        self.assertEqual(body["quantity"], 10)

    def test_duplicate_paper_submission_blocked(self) -> None:
        session = create_activated_session(
            self.service,
            self.campaigns_root,
            evaluation_horizon_ns=HOUR,
            created_at_ns=T0,
        )
        decision = self.service.create_decision(
            account_id="paper-a",
            mode="PAPER",
            session_id=session.session_id,
            symbol="ACME",
            direction="BUY",
            decision_time_ns=T0,
            source_time_ns=T0 - 1,
            strategy_id=BASELINE_POLICY,
            strategy_version=POLICY_VERSION,
            test_mode=ForwardTestMode.SIGNAL_ONLY,
        )
        self.service.lock_decision(
            forward_test_id=decision.forward_test_id,
            account_id="paper-a",
            locked_at_ns=T0,
        )
        self.service.submit_to_paper(
            forward_test_id=decision.forward_test_id,
            account_id="paper-a",
            submitted_at_ns=T0 + 1,
        )
        with self.assertRaises(ForwardTestServiceError):
            self.service.submit_to_paper(
                forward_test_id=decision.forward_test_id,
                account_id="paper-a",
                submitted_at_ns=T0 + 2,
            )


class ForwardTestTemporalTests(unittest.TestCase):
    def test_future_input_rejected(self) -> None:
        with self.assertRaises(ForwardTestTemporalError):
            assert_input_observable_at_decision(
                effective_time_ns=T0 + 10,
                decision_time_ns=T0,
            )

    def test_decision_payload_immutable(self) -> None:
        with self.assertRaises(ForwardTestTemporalError):
            assert_decision_payload_immutable(original={"a": 1}, proposed={"a": 2})

    def test_backtest_boundary(self) -> None:
        with self.assertRaises(ForwardTestTemporalError):
            assert_run_kind_forward(run_kind="BACKTEST")


class ForwardTestEvaluationTests(ActivatedForwardTestCase):
    def test_evaluation_after_horizon(self) -> None:
        store = ForwardTestStore()
        service = ForwardTestService(store)
        session = create_activated_session(
            service,
            self.campaigns_root,
            evaluation_horizon_ns=HOUR,
            created_at_ns=T0,
        )
        decision = service.create_decision(
            account_id="paper-a",
            mode="PAPER",
            session_id=session.session_id,
            symbol="ACME",
            direction="BUY",
            decision_time_ns=T0,
            source_time_ns=T0 - 1,
            strategy_id=BASELINE_POLICY,
            strategy_version=POLICY_VERSION,
            test_mode=ForwardTestMode.SIGNAL_ONLY,
        )
        service.lock_decision(
            forward_test_id=decision.forward_test_id,
            account_id="paper-a",
            locked_at_ns=T0,
        )
        service.submit_to_paper(
            forward_test_id=decision.forward_test_id,
            account_id="paper-a",
            submitted_at_ns=T0 + 1,
        )
        service.attach_observation(
            forward_test_id=decision.forward_test_id,
            account_id="paper-a",
            observed_at_ns=T0 + HOUR,
            source_time_ns=T0 + HOUR,
            payload={"reference_price": 100.0, "close_price": 105.0},
        )
        current = service.get_decision(
            forward_test_id=decision.forward_test_id,
            account_id="paper-a",
        )
        current = replace(current, state=ForwardTestState.EVALUABLE)
        store.put_decision(current)
        evaluated = service.evaluate(
            forward_test_id=decision.forward_test_id,
            account_id="paper-a",
            now_ns=T0 + HOUR + 1,
            force=True,
        )
        self.assertEqual(evaluated.state, ForwardTestState.EVALUATED)
        self.assertIsNotNone(evaluated.signal_outcome)
        self.assertEqual(evaluated.signal_outcome.directional_correct, True)


class ForwardTestAccountIsolationTests(ActivatedForwardTestCase):
    def test_cross_account_access_denied(self) -> None:
        store = ForwardTestStore()
        service = ForwardTestService(store)
        session = create_activated_session(
            service,
            self.campaigns_root,
            evaluation_horizon_ns=HOUR,
            created_at_ns=T0,
        )
        decision = service.create_decision(
            account_id="paper-a",
            mode="PAPER",
            session_id=session.session_id,
            symbol="ACME",
            direction="BUY",
            decision_time_ns=T0,
            source_time_ns=T0 - 1,
            strategy_id=BASELINE_POLICY,
            strategy_version=POLICY_VERSION,
            test_mode=ForwardTestMode.SIGNAL_ONLY,
        )
        with self.assertRaises(ForwardTestServiceError):
            service.get_decision(forward_test_id=decision.forward_test_id, account_id="paper-b")


class ForwardTestDecisionSourceTests(ActivatedForwardTestCase):
    def test_forward_test_snapshot_correlation(self) -> None:
        store = ForwardTestStore()
        service = ForwardTestService(store)
        session = create_activated_session(
            service,
            self.campaigns_root,
            evaluation_horizon_ns=HOUR,
            created_at_ns=T0,
        )
        decision = service.create_decision(
            account_id="paper-a",
            mode="PAPER",
            session_id=session.session_id,
            symbol="ACME",
            direction="BUY",
            decision_time_ns=T0,
            source_time_ns=T0 - 1,
            strategy_id=BASELINE_POLICY,
            strategy_version=POLICY_VERSION,
            test_mode=ForwardTestMode.EXECUTION,
            quantity=1,
        )
        locked = service.lock_decision(
            forward_test_id=decision.forward_test_id,
            account_id="paper-a",
            locked_at_ns=T0,
        )
        snapshot = build_decision_source_snapshot(locked)
        parsed = parse_decision_source_snapshot(snapshot)
        assert parsed is not None
        validated = validate_snapshot_against_correlation(
            snapshot=parsed,
            correlation_id=service.correlation_id(decision.forward_test_id),
        )
        self.assertEqual(validated["source_type"], "forward_test_decision")


class ForwardTestApiTests(unittest.TestCase):
    def setUp(self) -> None:
        from market_platform_foundation.local_state.startup import reset_local_state_for_tests

        os.environ["IMP_PAPER_EXECUTION"] = "1"
        os.environ["IMP_FORWARD_TEST_EVAL_FORCE"] = "1"
        self._activation_tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ["IMP_STATE_DIR"] = self._activation_tmp.name
        reset_local_state_for_tests()
        self.campaigns_root = enable_test_campaigns_root(Path(self._activation_tmp.name))
        fixture_root = ROOT.parent
        self.store = ReplayStore(collection_root=fixture_root)
        self.store.load()
        open_paper_session(self.store, {"execution_mode": "INTERNAL_SIMULATION"})
        self.store.paper_ledger.execution_authority = "AUTHORIZED"
        self.store.paper_ledger.execution_mode = "INTERNAL_SIMULATION"
        self.account_id = self.store.paper_ledger.paper_account_id
        seed_baseline_campaign(self.campaigns_root, paper_account_id=self.account_id)

    def tearDown(self) -> None:
        from market_platform_foundation.local_state.startup import reset_local_state_for_tests

        reset_local_state_for_tests()
        os.environ.pop("IMP_STATE_DIR", None)
        os.environ.pop("IMP_FORWARD_TEST_CAMPAIGNS_DIR", None)
        os.environ.pop("IMP_FORWARD_TEST_EVAL_FORCE", None)
        self._activation_tmp.cleanup()

    def test_api_end_to_end_signal_only(self) -> None:
        session_payload = create_forward_test_session(
            self.store,
            {
                "account_id": self.account_id,
                "campaign_id": CAMPAIGN_SLUG,
                "cohort_arm": "BASELINE",
                "strategy_id": BASELINE_POLICY,
                "strategy_version": POLICY_VERSION,
                "universe": ["ACME"],
                "evaluation_horizon_ns": HOUR,
                "created_at_ns": T0,
            },
        )
        session_id = session_payload["session"]["session_id"]
        decision_payload = create_forward_test_decision(
            self.store,
            {
                "account_id": self.account_id,
                "session_id": session_id,
                "symbol": "ACME",
                "direction": "POSITIVE_DIRECTIONAL_BIAS",
                "decision_time_ns": T0,
                "source_time_ns": T0 - 1,
                "strategy_id": BASELINE_POLICY,
                "strategy_version": POLICY_VERSION,
                "test_mode": "SIGNAL_ONLY",
            },
        )
        forward_test_id = decision_payload["forward_test"]["forward_test_id"]
        locked = lock_forward_test_decision(
            self.store,
            {
                "account_id": self.account_id,
                "forward_test_id": forward_test_id,
                "locked_at_ns": T0,
            },
        )
        self.assertEqual(locked["forward_test"]["state"], "LOCKED")
        submitted = submit_forward_test_to_paper(
            self.store,
            {
                "account_id": self.account_id,
                "forward_test_id": forward_test_id,
                "submitted_at_ns": T0 + 1,
            },
        )
        self.assertEqual(submitted["forward_test"]["state"], "OBSERVING")
        evaluated = evaluate_forward_test_decision(
            self.store,
            {
                "account_id": self.account_id,
                "forward_test_id": forward_test_id,
                "now_ns": T0 + HOUR + 1,
                "force": True,
            },
        )
        self.assertIn(
            evaluated["forward_test"]["state"],
            {"EVALUATED", "INSUFFICIENT_DATA", "OBSERVING", "EVALUABLE"},
        )


class ForwardTestBacktestBoundaryTests(ActivatedForwardTestCase):
    def test_run_kind_forward_test_only(self) -> None:
        store = ForwardTestStore()
        service = ForwardTestService(store)
        session = create_activated_session(
            service,
            self.campaigns_root,
            evaluation_horizon_ns=HOUR,
            created_at_ns=T0,
        )
        decision = service.create_decision(
            account_id="paper-a",
            mode="PAPER",
            session_id=session.session_id,
            symbol="ACME",
            direction="BUY",
            decision_time_ns=T0,
            source_time_ns=T0 - 1,
            strategy_id=BASELINE_POLICY,
            strategy_version=POLICY_VERSION,
            test_mode=ForwardTestMode.SIGNAL_ONLY,
        )
        self.assertEqual(decision.run_kind.value, "FORWARD_TEST")
        self.assertNotEqual(decision.run_kind.value, "BACKTEST")


if __name__ == "__main__":
    unittest.main()
