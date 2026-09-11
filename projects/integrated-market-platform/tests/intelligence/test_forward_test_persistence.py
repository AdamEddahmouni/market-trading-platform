"""Durable forward-test persistence tests (PD-09-PERSISTENCE)."""

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

from market_platform_foundation.intelligence.paper_forward_bridge import (  # noqa: E402
    ForwardTestMode,
    ForwardTestRepositoryError,
    ForwardTestService,
    ForwardTestServiceError,
    ForwardTestState,
    create_forward_test_repository,
)
from market_platform_foundation.intelligence.paper_forward_bridge.types import (  # noqa: E402
    ForwardTestObservation,
)
from market_platform_foundation.local_state.schema import SCHEMA_VERSION  # noqa: E402
from market_platform_foundation.local_state.startup import (  # noqa: E402
    forward_test_restore_summary,
    open_local_state,
    reset_local_state_for_tests,
)
from forward_test_activation_support import (  # noqa: E402
    BASELINE_POLICY,
    POLICY_VERSION,
    create_activated_session,
    enable_test_campaigns_root,
    seed_baseline_campaign,
)

T0 = 1_700_000_000_000_000_000
HOUR = 3_600_000_000_000


class IsolatedForwardTestPersistenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ["IMP_STATE_DIR"] = self._tmp.name
        os.environ["IMP_PERSIST_STATE"] = "1"
        self.campaigns_root = enable_test_campaigns_root(Path(self._tmp.name))
        seed_baseline_campaign(self.campaigns_root)
        reset_local_state_for_tests()

    def tearDown(self) -> None:
        reset_local_state_for_tests()
        os.environ.pop("IMP_STATE_DIR", None)
        os.environ.pop("IMP_PERSIST_STATE", None)
        os.environ.pop("IMP_FORWARD_TEST_CAMPAIGNS_DIR", None)
        self._tmp.cleanup()

    def _repo(self):
        local = open_local_state(force=True)
        assert local is not None
        return create_forward_test_repository(connection=local.connection)

    def _service(self, repo=None) -> ForwardTestService:
        return ForwardTestService(repo or self._repo())

    def _restart(self):
        reset_local_state_for_tests()
        return self._repo(), self._service()

    def _seed_locked_decision(self, service: ForwardTestService):
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
        locked = service.lock_decision(
            forward_test_id=decision.forward_test_id,
            account_id="paper-a",
            locked_at_ns=T0,
        )
        return session, locked

    def test_schema_migration_includes_forward_test_tables(self) -> None:
        local = open_local_state(force=True)
        assert local is not None
        self.assertEqual(local.connection.schema_version(), SCHEMA_VERSION)
        tables = {
            str(row[0])
            for row in local.connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        self.assertIn("forward_test_sessions", tables)
        self.assertIn("forward_test_decisions", tables)
        self.assertIn("forward_test_observations", tables)
        self.assertIn("forward_test_claims", tables)
        self.assertIn("forward_test_campaign_bindings", tables)

    def test_campaign_binding_survives_restart(self) -> None:
        service = self._service()
        session = create_activated_session(
            service,
            self.campaigns_root,
            evaluation_horizon_ns=HOUR,
            created_at_ns=T0,
        )
        binding = service._store.get_active_binding(account_id="paper-a")
        self.assertIsNotNone(binding)
        assert binding is not None
        self.assertEqual(binding.forward_test_session_id, session.session_id)
        _, restarted = self._restart()
        recovered = restarted._store.get_active_binding(account_id="paper-a")
        self.assertIsNotNone(recovered)
        assert recovered is not None
        self.assertEqual(recovered.campaign_id, binding.campaign_id)
        self.assertEqual(recovered.forward_test_session_id, session.session_id)

    def test_first_lock_timestamp_persisted_after_restart(self) -> None:
        service = self._service()
        _session, locked = self._seed_locked_decision(service)
        binding = service._store.get_active_binding(account_id="paper-a")
        self.assertIsNotNone(binding)
        assert binding is not None
        self.assertEqual(binding.first_lock_at_ns, T0)
        _, restarted = self._restart()
        recovered_binding = restarted._store.get_active_binding(account_id="paper-a")
        self.assertIsNotNone(recovered_binding)
        assert recovered_binding is not None
        self.assertEqual(recovered_binding.first_lock_at_ns, T0)
        recovered_decision = restarted.get_decision(
            forward_test_id=locked.forward_test_id,
            account_id="paper-a",
        )
        self.assertEqual(recovered_decision.state, ForwardTestState.LOCKED)

    def test_create_session_restart_recover(self) -> None:
        service = self._service()
        session = create_activated_session(
            service,
            self.campaigns_root,
            evaluation_horizon_ns=HOUR,
            created_at_ns=T0,
        )
        repo, restarted = self._restart()
        recovered = restarted._store.list_sessions(account_id="paper-a")
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0].session_id, session.session_id)
        summary = forward_test_restore_summary()
        self.assertEqual(summary["restore"], "AVAILABLE")
        self.assertEqual(summary["session_count"], 1)

    def test_lock_restart_immutable(self) -> None:
        service = self._service()
        _session, locked = self._seed_locked_decision(service)
        _, restarted = self._restart()
        recovered = restarted.get_decision(
            forward_test_id=locked.forward_test_id,
            account_id="paper-a",
        )
        self.assertEqual(recovered.state, ForwardTestState.LOCKED)
        self.assertEqual(recovered.locked_at_ns, T0)
        tampered = replace(recovered, direction="SELL")
        with self.assertRaises(ForwardTestRepositoryError):
            restarted._store.put_decision(tampered)

    def test_append_observation_restart_preserved(self) -> None:
        service = self._service()
        _session, locked = self._seed_locked_decision(service)
        service.submit_to_paper(
            forward_test_id=locked.forward_test_id,
            account_id="paper-a",
            submitted_at_ns=T0 + 1,
        )
        service.attach_observation(
            forward_test_id=locked.forward_test_id,
            account_id="paper-a",
            observed_at_ns=T0 + HOUR,
            source_time_ns=T0 + HOUR,
            payload={"reference_price": 100.0, "close_price": 105.0},
        )
        _, restarted = self._restart()
        recovered = restarted.get_decision(
            forward_test_id=locked.forward_test_id,
            account_id="paper-a",
        )
        self.assertEqual(len(recovered.observations), 1)
        self.assertEqual(recovered.observations[0].payload["close_price"], 105.0)

    def test_observations_append_only_blocked_after_restart(self) -> None:
        service = self._service()
        _session, locked = self._seed_locked_decision(service)
        service.submit_to_paper(
            forward_test_id=locked.forward_test_id,
            account_id="paper-a",
            submitted_at_ns=T0 + 1,
        )
        service.attach_observation(
            forward_test_id=locked.forward_test_id,
            account_id="paper-a",
            observed_at_ns=T0 + HOUR,
            source_time_ns=T0 + HOUR,
            payload={"reference_price": 100.0, "close_price": 105.0},
        )
        service.attach_observation(
            forward_test_id=locked.forward_test_id,
            account_id="paper-a",
            observed_at_ns=T0 + HOUR + 1,
            source_time_ns=T0 + HOUR + 1,
            payload={"reference_price": 105.0, "close_price": 110.0},
        )
        _, restarted = self._restart()
        recovered = restarted.get_decision(
            forward_test_id=locked.forward_test_id,
            account_id="paper-a",
        )
        self.assertEqual(len(recovered.observations), 2)

        scenarios = (
            ("delete", replace(recovered, observations=recovered.observations[:-1])),
            (
                "reorder",
                replace(
                    recovered,
                    observations=(
                        recovered.observations[1],
                        recovered.observations[0],
                    ),
                ),
            ),
            (
                "replace",
                replace(
                    recovered,
                    observations=(
                        ForwardTestObservation(
                            observation_id="tampered-observation-id",
                            observed_at_ns=recovered.observations[0].observed_at_ns,
                            source_time_ns=recovered.observations[0].source_time_ns,
                            payload=dict(recovered.observations[0].payload),
                        ),
                        *recovered.observations[1:],
                    ),
                ),
            ),
        )
        for label, tampered in scenarios:
            with self.subTest(scenario=label):
                with self.assertRaises(ForwardTestRepositoryError) as ctx:
                    restarted._store.put_decision(tampered)
                self.assertEqual(str(ctx.exception), "FORWARD_TEST_OBSERVATIONS_APPEND_ONLY")

    def test_evaluate_restart_preserved(self) -> None:
        service = self._service()
        _session, locked = self._seed_locked_decision(service)
        service.submit_to_paper(
            forward_test_id=locked.forward_test_id,
            account_id="paper-a",
            submitted_at_ns=T0 + 1,
        )
        service.attach_observation(
            forward_test_id=locked.forward_test_id,
            account_id="paper-a",
            observed_at_ns=T0 + HOUR,
            source_time_ns=T0 + HOUR,
            payload={"reference_price": 100.0, "close_price": 105.0},
        )
        current = service.get_decision(
            forward_test_id=locked.forward_test_id,
            account_id="paper-a",
        )
        service._store.put_decision(replace(current, state=ForwardTestState.EVALUABLE))
        evaluated = service.evaluate(
            forward_test_id=locked.forward_test_id,
            account_id="paper-a",
            now_ns=T0 + HOUR + 1,
            force=True,
        )
        self.assertEqual(evaluated.state, ForwardTestState.EVALUATED)
        _, restarted = self._restart()
        recovered = restarted.get_decision(
            forward_test_id=locked.forward_test_id,
            account_id="paper-a",
        )
        self.assertEqual(recovered.state, ForwardTestState.EVALUATED)
        self.assertIsNotNone(recovered.signal_outcome)

    def test_evaluation_claim_durable_after_restart(self) -> None:
        service = self._service()
        _session, locked = self._seed_locked_decision(service)
        service.submit_to_paper(
            forward_test_id=locked.forward_test_id,
            account_id="paper-a",
            submitted_at_ns=T0 + 1,
        )
        service.attach_observation(
            forward_test_id=locked.forward_test_id,
            account_id="paper-a",
            observed_at_ns=T0 + HOUR,
            source_time_ns=T0 + HOUR,
            payload={"reference_price": 100.0, "close_price": 105.0},
        )
        current = service.get_decision(
            forward_test_id=locked.forward_test_id,
            account_id="paper-a",
        )
        service._store.put_decision(replace(current, state=ForwardTestState.EVALUABLE))
        evaluated = service.evaluate(
            forward_test_id=locked.forward_test_id,
            account_id="paper-a",
            now_ns=T0 + HOUR + 1,
            force=False,
        )
        self.assertEqual(evaluated.state, ForwardTestState.EVALUATED)
        _, restarted = self._restart()
        recovered = restarted.get_decision(
            forward_test_id=locked.forward_test_id,
            account_id="paper-a",
        )
        self.assertEqual(recovered.state, ForwardTestState.EVALUATED)
        tampered = replace(
            recovered,
            state=ForwardTestState.EVALUABLE,
            signal_outcome=None,
        )
        restarted._store.put_decision(tampered)
        blocked = restarted.evaluate(
            forward_test_id=locked.forward_test_id,
            account_id="paper-a",
            now_ns=T0 + HOUR + 2,
            force=False,
        )
        self.assertEqual(blocked.state, ForwardTestState.EVALUABLE)
        self.assertIsNone(blocked.signal_outcome)

    def test_cross_account_isolation(self) -> None:
        service = self._service()
        _session, locked = self._seed_locked_decision(service)
        _, restarted = self._restart()
        with self.assertRaises(ForwardTestServiceError):
            restarted.get_decision(
                forward_test_id=locked.forward_test_id,
                account_id="paper-b",
            )
        self.assertEqual(restarted._store.list_decisions(account_id="paper-b"), [])

    def test_duplicate_paper_submit_blocked_after_restart(self) -> None:
        service = self._service()
        _session, locked = self._seed_locked_decision(service)
        service.submit_to_paper(
            forward_test_id=locked.forward_test_id,
            account_id="paper-a",
            submitted_at_ns=T0 + 1,
        )
        _, restarted = self._restart()
        with self.assertRaises(ForwardTestServiceError):
            restarted.submit_to_paper(
                forward_test_id=locked.forward_test_id,
                account_id="paper-a",
                submitted_at_ns=T0 + 2,
            )

    def test_locked_decision_cannot_be_overwritten(self) -> None:
        service = self._service()
        _session, locked = self._seed_locked_decision(service)
        tampered = replace(
            locked,
            decision_payload={**locked.decision_payload, "tampered": True},
        )
        with self.assertRaises(ForwardTestRepositoryError):
            service._store.put_decision(tampered)

    def test_persistence_disabled_uses_memory_store(self) -> None:
        os.environ.pop("IMP_PERSIST_STATE", None)
        os.environ.pop("IMP_STATE_DIR", None)
        reset_local_state_for_tests()
        repo = create_forward_test_repository(connection=None)
        service = ForwardTestService(repo)
        session = create_activated_session(
            service,
            self.campaigns_root,
            evaluation_horizon_ns=HOUR,
            created_at_ns=T0,
        )
        self.assertEqual(len(service._store.list_sessions(account_id="paper-a")), 1)
        reset_local_state_for_tests()
        os.environ["IMP_STATE_DIR"] = self._tmp.name
        os.environ["IMP_PERSIST_STATE"] = "1"
        restarted = self._service()
        self.assertEqual(len(restarted._store.list_sessions(account_id="paper-a")), 0)
        self.assertNotEqual(
            restarted._store.list_sessions(account_id="paper-a"),
            [session],
        )


if __name__ == "__main__":
    unittest.main()
