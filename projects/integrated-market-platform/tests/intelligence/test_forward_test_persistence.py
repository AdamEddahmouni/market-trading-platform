"""Durable forward-test persistence tests (PD-09-PERSISTENCE)."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

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
from market_platform_foundation.intelligence.paper_forward_bridge.sqlite_repository import (  # noqa: E402
    CLAIM_EVALUATION,
    CLAIM_PAPER_SUBMISSION,
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
    CAMPAIGN_SLUG,
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
        os.environ["IMP_FORWARD_TEST_EVAL_FORCE"] = "1"
        self.campaigns_root = enable_test_campaigns_root(Path(self._tmp.name))
        seed_baseline_campaign(self.campaigns_root)
        reset_local_state_for_tests()

    def tearDown(self) -> None:
        reset_local_state_for_tests()
        os.environ.pop("IMP_STATE_DIR", None)
        os.environ.pop("IMP_PERSIST_STATE", None)
        os.environ.pop("IMP_FORWARD_TEST_CAMPAIGNS_DIR", None)
        os.environ.pop("IMP_FORWARD_TEST_EVAL_FORCE", None)
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

    def test_dual_cohort_arm_sessions_share_campaign_binding(self) -> None:
        service = self._service()
        baseline = create_activated_session(
            service,
            self.campaigns_root,
            evaluation_horizon_ns=HOUR,
            created_at_ns=T0,
        )
        ai_session = service.create_session(
            account_id="paper-a",
            mode="PAPER",
            strategy_id="news_ai_enhanced",
            strategy_version=POLICY_VERSION,
            universe=("ACME",),
            evaluation_horizon_ns=HOUR,
            created_at_ns=T0 + 1,
            campaign_id=CAMPAIGN_SLUG,
            cohort_arm="AI_ENHANCED",
            campaigns_root_override=self.campaigns_root,
        )
        self.assertNotEqual(baseline.session_id, ai_session.session_id)
        binding = service._store.get_active_binding(account_id="paper-a")
        self.assertIsNotNone(binding)
        assert binding is not None
        self.assertEqual(binding.forward_test_session_id, baseline.session_id)
        sessions = service._store.list_sessions(account_id="paper-a")
        arms = {session.cohort_arm.value for session in sessions if session.cohort_arm}
        self.assertEqual(arms, {"BASELINE", "AI_ENHANCED"})

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


class DurableForwardTestPersistenceV6Tests(IsolatedForwardTestPersistenceTest):
    def test_schema_version_is_six(self) -> None:
        local = open_local_state(force=True)
        assert local is not None
        self.assertEqual(local.connection.schema_version(), 6)
        tables = {
            str(row[0])
            for row in local.connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        self.assertIn("forward_test_signal_links", tables)

    def test_populated_v2_migrates_to_v6(self) -> None:
        import sqlite3

        from market_platform_foundation.local_state.schema import (
            CREATE_STATEMENTS,
            FORWARD_TEST_CREATE_STATEMENTS,
        )

        reset_local_state_for_tests()
        db_path = Path(self._tmp.name) / "imp-state.sqlite3"
        for extra in (db_path, Path(f"{db_path}-wal"), Path(f"{db_path}-shm")):
            extra.unlink(missing_ok=True)
        conn = sqlite3.connect(str(db_path))
        for statement in (*CREATE_STATEMENTS, *FORWARD_TEST_CREATE_STATEMENTS):
            conn.execute(statement)
        conn.execute("INSERT INTO schema_meta(schema_version, applied_at) VALUES (1, 't')")
        conn.execute("INSERT INTO schema_meta(schema_version, applied_at) VALUES (2, 't')")
        conn.execute(
            """
            INSERT INTO forward_test_sessions(
                session_id, account_id, mode, strategy_id, strategy_version,
                universe_json, evaluation_horizon_ns, created_at_ns, status, config_json
            ) VALUES ('fts-legacy', 'paper-a', 'PAPER', 'news_deterministic_baseline',
                      '1.0.0', '["ACME"]', ?, ?, 'ACTIVE', '{}')
            """,
            (HOUR, T0),
        )
        conn.commit()
        conn.close()
        local = open_local_state(force=True)
        assert local is not None
        self.assertEqual(local.connection.schema_version(), 6)
        row = local.connection.execute(
            "SELECT session_id, git_sha FROM forward_test_sessions WHERE session_id='fts-legacy'"
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "fts-legacy")
        columns = {
            str(item[1])
            for item in local.connection.execute("PRAGMA table_info(forward_test_sessions)").fetchall()
        }
        self.assertIn("git_sha", columns)
        self.assertIn("persist_time_ns", columns)
        self.assertIn("simulator_version", columns)

    def test_v5_duplicate_acks_deduped_on_v6(self) -> None:
        import sqlite3

        from market_platform_foundation.local_state.schema import (
            CREATE_STATEMENTS,
            FORWARD_TEST_ACTIVATION_MIGRATION,
            FORWARD_TEST_CAMPAIGN_BINDINGS,
            FORWARD_TEST_CREATE_STATEMENTS,
            OPPORTUNITY_OPERATOR_ACKS,
        )

        reset_local_state_for_tests()
        db_path = Path(self._tmp.name) / "imp-state.sqlite3"
        for extra in (db_path, Path(f"{db_path}-wal"), Path(f"{db_path}-shm")):
            extra.unlink(missing_ok=True)
        conn = sqlite3.connect(str(db_path))
        statements = (
            *CREATE_STATEMENTS,
            *FORWARD_TEST_CREATE_STATEMENTS,
            *FORWARD_TEST_ACTIVATION_MIGRATION,
            *FORWARD_TEST_CAMPAIGN_BINDINGS,
            *OPPORTUNITY_OPERATOR_ACKS,
        )
        for statement in statements:
            conn.execute(statement)
        for version in range(1, 6):
            conn.execute(
                "INSERT INTO schema_meta(schema_version, applied_at) VALUES (?, 't')",
                (version,),
            )
        conn.execute(
            """
            INSERT INTO opportunity_operator_acks(
                summary_id, opportunity_id, paper_account_id, action, created_at_ns
            ) VALUES
                ('sum-1', 'opp-1', 'paper-a', 'WATCHED', 1),
                ('sum-1', 'opp-1', 'paper-a', 'WATCHED', 2)
            """
        )
        conn.commit()
        conn.close()
        local = open_local_state(force=True)
        assert local is not None
        self.assertEqual(local.connection.schema_version(), 6)
        count = local.connection.execute(
            "SELECT COUNT(*) FROM opportunity_operator_acks WHERE paper_account_id='paper-a'"
        ).fetchone()
        self.assertEqual(int(count[0]), 1)

    def test_live_mode_rejected_at_repository(self) -> None:
        repo = self._repo()
        session = create_activated_session(
            self._service(repo),
            self.campaigns_root,
            evaluation_horizon_ns=HOUR,
            created_at_ns=T0,
        )
        live = replace(session, mode="LIVE")
        with self.assertRaises(ForwardTestRepositoryError) as ctx:
            repo.put_session(live)
        self.assertEqual(str(ctx.exception), "FORWARD_TEST_LIVE_MODE_FORBIDDEN")

    def test_two_campaigns_isolated_after_restart(self) -> None:
        from market_platform_foundation.intelligence.paper_forward_bridge import (
            seed_test_frozen_manifest,
        )

        service = self._service()
        session_a = create_activated_session(
            service,
            self.campaigns_root,
            evaluation_horizon_ns=HOUR,
            created_at_ns=T0,
        )
        seed_test_frozen_manifest(
            self.campaigns_root,
            campaign_slug="FTEP-V1-TEST-B",
            paper_account_id="paper-b",
            universe_symbols=("BETA",),
            evaluation_horizon_ns=HOUR,
        )
        session_b = service.create_session(
            account_id="paper-b",
            mode="PAPER",
            strategy_id=BASELINE_POLICY,
            strategy_version=POLICY_VERSION,
            universe=("BETA",),
            evaluation_horizon_ns=HOUR,
            created_at_ns=T0 + 1,
            campaign_id="FTEP-V1-TEST-B",
            cohort_arm="BASELINE",
            campaigns_root_override=self.campaigns_root,
        )
        decision_a = service.create_decision(
            account_id="paper-a",
            mode="PAPER",
            session_id=session_a.session_id,
            symbol="ACME",
            direction="BUY",
            decision_time_ns=T0,
            source_time_ns=T0 - 1,
            strategy_id=BASELINE_POLICY,
            strategy_version=POLICY_VERSION,
            test_mode=ForwardTestMode.SIGNAL_ONLY,
        )
        decision_b = service.create_decision(
            account_id="paper-b",
            mode="PAPER",
            session_id=session_b.session_id,
            symbol="BETA",
            direction="BUY",
            decision_time_ns=T0,
            source_time_ns=T0 - 1,
            strategy_id=BASELINE_POLICY,
            strategy_version=POLICY_VERSION,
            test_mode=ForwardTestMode.SIGNAL_ONLY,
        )
        _, restarted = self._restart()
        recovered_a = restarted.list_decisions(
            account_id="paper-a",
            campaign_id=CAMPAIGN_SLUG,
        )
        recovered_b = restarted.list_decisions(
            account_id="paper-b",
            campaign_id="FTEP-V1-TEST-B",
        )
        self.assertEqual([item.forward_test_id for item in recovered_a], [decision_a.forward_test_id])
        self.assertEqual([item.forward_test_id for item in recovered_b], [decision_b.forward_test_id])
        self.assertEqual(
            restarted.list_decisions(account_id="paper-a", campaign_id="FTEP-V1-TEST-B"),
            [],
        )

    def test_instrument_and_strategy_isolation_after_restart(self) -> None:
        service = self._service()
        session = service.create_session(
            account_id="paper-a",
            mode="PAPER",
            strategy_id=BASELINE_POLICY,
            strategy_version=POLICY_VERSION,
            universe=("ACME", "ES"),
            evaluation_horizon_ns=HOUR,
            created_at_ns=T0,
            campaign_id=CAMPAIGN_SLUG,
            cohort_arm="BASELINE",
            campaigns_root_override=self.campaigns_root,
        )
        acme = service.create_decision(
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
        es = service.create_decision(
            account_id="paper-a",
            mode="PAPER",
            session_id=session.session_id,
            symbol="ES",
            direction="BUY",
            decision_time_ns=T0 + 1,
            source_time_ns=T0,
            strategy_id=BASELINE_POLICY,
            strategy_version=POLICY_VERSION,
            test_mode=ForwardTestMode.SIGNAL_ONLY,
        )
        ai_session = service.create_session(
            account_id="paper-a",
            mode="PAPER",
            strategy_id="news_ai_enhanced",
            strategy_version=POLICY_VERSION,
            universe=("ACME",),
            evaluation_horizon_ns=HOUR,
            created_at_ns=T0 + 2,
            campaign_id=CAMPAIGN_SLUG,
            cohort_arm="AI_ENHANCED",
            campaigns_root_override=self.campaigns_root,
        )
        ai = service.create_decision(
            account_id="paper-a",
            mode="PAPER",
            session_id=ai_session.session_id,
            symbol="ACME",
            direction="BUY",
            decision_time_ns=T0 + 2,
            source_time_ns=T0 + 1,
            strategy_id="news_ai_enhanced",
            strategy_version=POLICY_VERSION,
            test_mode=ForwardTestMode.SIGNAL_ONLY,
        )
        _, restarted = self._restart()
        only_es = restarted.list_decisions(account_id="paper-a", symbol="ES")
        self.assertEqual([item.forward_test_id for item in only_es], [es.forward_test_id])
        baseline_only = restarted.list_decisions(
            account_id="paper-a",
            strategy_id=BASELINE_POLICY,
        )
        self.assertEqual(
            {item.forward_test_id for item in baseline_only},
            {acme.forward_test_id, es.forward_test_id},
        )
        self.assertNotIn(ai.forward_test_id, {item.forward_test_id for item in baseline_only})

    def test_evaluation_claim_rolls_back_with_transaction(self) -> None:
        service = self._service()
        _session, locked = self._seed_locked_decision(service)
        local = open_local_state(force=True)
        assert local is not None
        repo = self._repo()
        with self.assertRaises(RuntimeError):
            with local.connection.transaction():
                self.assertTrue(repo.claim_evaluation(locked.forward_test_id))
                raise RuntimeError("boom")
        claimed = repo.claim_evaluation(locked.forward_test_id)
        self.assertTrue(claimed)

    def _claim_types(self, forward_test_id: str) -> set[str]:
        local = open_local_state(force=True)
        assert local is not None
        rows = local.connection.execute(
            "SELECT claim_type FROM forward_test_claims WHERE forward_test_id=?",
            (forward_test_id,),
        ).fetchall()
        return {str(row[0]) for row in rows}

    def test_commit_evaluation_rolls_back_claim_when_put_fails_and_survives_restart(
        self,
    ) -> None:
        """H2: claim_evaluation + put must share one transaction across restart."""
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

        with patch.object(
            service._store,
            "_put_decision_body",
            side_effect=RuntimeError("simulated put failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "simulated put failure"):
                service.evaluate(
                    forward_test_id=locked.forward_test_id,
                    account_id="paper-a",
                    now_ns=T0 + HOUR + 1,
                    force=False,
                )

        self.assertNotIn(CLAIM_EVALUATION, self._claim_types(locked.forward_test_id))
        stalled = service.get_decision(
            forward_test_id=locked.forward_test_id,
            account_id="paper-a",
        )
        self.assertEqual(stalled.state, ForwardTestState.EVALUABLE)
        self.assertIsNone(stalled.signal_outcome)

        _, restarted = self._restart()
        self.assertNotIn(CLAIM_EVALUATION, self._claim_types(locked.forward_test_id))
        evaluated = restarted.evaluate(
            forward_test_id=locked.forward_test_id,
            account_id="paper-a",
            now_ns=T0 + HOUR + 1,
            force=False,
        )
        self.assertEqual(evaluated.state, ForwardTestState.EVALUATED)
        self.assertIsNotNone(evaluated.signal_outcome)

        _, restarted_again = self._restart()
        recovered = restarted_again.get_decision(
            forward_test_id=locked.forward_test_id,
            account_id="paper-a",
        )
        self.assertEqual(recovered.state, ForwardTestState.EVALUATED)
        self.assertIn(CLAIM_EVALUATION, self._claim_types(locked.forward_test_id))
        self.assertFalse(restarted_again._store.claim_evaluation(locked.forward_test_id))

    def test_commit_paper_submission_rolls_back_claim_when_put_fails_and_survives_restart(
        self,
    ) -> None:
        """H3: claim_paper_submission + put must share one transaction across restart."""
        service = self._service()
        _session, locked = self._seed_locked_decision(service)

        with patch.object(
            service._store,
            "_put_decision_body",
            side_effect=RuntimeError("simulated put failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "simulated put failure"):
                service.submit_to_paper(
                    forward_test_id=locked.forward_test_id,
                    account_id="paper-a",
                    submitted_at_ns=T0 + 1,
                    paper_order_id="ord-rb-1",
                )

        self.assertNotIn(CLAIM_PAPER_SUBMISSION, self._claim_types(locked.forward_test_id))
        stalled = service.get_decision(
            forward_test_id=locked.forward_test_id,
            account_id="paper-a",
        )
        self.assertEqual(stalled.state, ForwardTestState.LOCKED)
        self.assertIsNone(stalled.paper_order_id)

        _, restarted = self._restart()
        self.assertNotIn(CLAIM_PAPER_SUBMISSION, self._claim_types(locked.forward_test_id))
        submitted = restarted.submit_to_paper(
            forward_test_id=locked.forward_test_id,
            account_id="paper-a",
            submitted_at_ns=T0 + 1,
            paper_order_id="ord-rb-1",
        )
        self.assertEqual(submitted.state, ForwardTestState.OBSERVING)
        self.assertEqual(submitted.paper_order_id, "ord-rb-1")

        _, restarted_again = self._restart()
        recovered = restarted_again.get_decision(
            forward_test_id=locked.forward_test_id,
            account_id="paper-a",
        )
        self.assertEqual(recovered.state, ForwardTestState.OBSERVING)
        self.assertEqual(recovered.paper_order_id, "ord-rb-1")
        self.assertIn(CLAIM_PAPER_SUBMISSION, self._claim_types(locked.forward_test_id))
        self.assertFalse(
            restarted_again._store.claim_paper_submission(locked.forward_test_id)
        )
        with self.assertRaises(ForwardTestServiceError):
            restarted_again.submit_to_paper(
                forward_test_id=locked.forward_test_id,
                account_id="paper-a",
                submitted_at_ns=T0 + 2,
                paper_order_id="ord-rb-2",
            )

    def test_reconstruct_metrics_from_paper_ledger_and_observations(self) -> None:
        from market_platform_foundation.intelligence.paper_forward_bridge.reconstruction import (
            reconstruct_campaign,
        )

        service = self._service()
        session, locked = self._seed_locked_decision(service)
        submitted = service.submit_to_paper(
            forward_test_id=locked.forward_test_id,
            account_id="paper-a",
            submitted_at_ns=T0 + 1,
            paper_order_id="ord-1",
        )
        service.attach_observation(
            forward_test_id=locked.forward_test_id,
            account_id="paper-a",
            observed_at_ns=T0 + HOUR,
            source_time_ns=T0 + HOUR,
            payload={
                "reference_price": 100.0,
                "close_price": 110.0,
                "realized_pnl_minor": 250,
                "fill_count": 2,
            },
        )
        local = open_local_state(force=True)
        assert local is not None
        local.connection.execute(
            """
            INSERT INTO paper_events(
                event_id, session_id, event_type, event_time, available_time,
                correlation_id, payload_json, schema_version, sequence
            ) VALUES ('ev-fill', 'ps-1', 'FillRecorded', ?, ?, 'c',
                      '{"order_id":"ord-1","fill":{"fill_id":"f1"}}', 1, 1)
            """,
            (T0 + 2, T0 + 2),
        )
        local.connection.execute(
            """
            INSERT INTO paper_events(
                event_id, session_id, event_type, event_time, available_time,
                correlation_id, payload_json, schema_version, sequence
            ) VALUES ('ev-pnl', 'ps-1', 'PositionChanged', ?, ?, 'c',
                      '{"realized_pnl_minor": 250}', 1, 2)
            """,
            (T0 + 3, T0 + 3),
        )
        reconstructed = reconstruct_campaign(
            local.connection,
            account_id="paper-a",
            campaign_id=CAMPAIGN_SLUG,
        )
        self.assertEqual(reconstructed["session_count"], 1)
        self.assertEqual(reconstructed["decision_count"], 1)
        row = reconstructed["decisions"][0]
        self.assertEqual(row["realized_pnl_minor"], 250)
        self.assertEqual(row["fill_count"], 1)
        self.assertEqual(row["signal_outcome"]["quality"], "COMPLETE")
        recovered = service.get_decision(
            forward_test_id=locked.forward_test_id,
            account_id="paper-a",
        )
        self.assertEqual(recovered.paper_order_id, "ord-1")
        self.assertEqual(
            recovered.provenance_snapshot.get("git_sha"),
            submitted.provenance_snapshot.get("git_sha"),
        )
        self.assertIsNotNone(recovered.provenance_snapshot.get("simulator_version"))

    def test_operator_ack_idempotent_and_account_scoped(self) -> None:
        from market_platform_foundation.ui_api.operator_opportunity_state import (
            list_operator_acks,
            record_operator_ack,
        )

        record_operator_ack(
            summary_id="sum-1",
            opportunity_id="opp-1",
            paper_account_id="paper-a",
            action="WATCHED",
            created_at_ns=T0,
        )
        record_operator_ack(
            summary_id="sum-1",
            opportunity_id="opp-1",
            paper_account_id="paper-a",
            action="WATCHED",
            created_at_ns=T0 + 1,
        )
        record_operator_ack(
            summary_id="sum-2",
            opportunity_id="opp-2",
            paper_account_id="paper-b",
            action="DISMISSED",
            created_at_ns=T0 + 2,
        )
        acks_a = list_operator_acks(paper_account_id="paper-a")
        acks_b = list_operator_acks(paper_account_id="paper-b")
        self.assertEqual(len(acks_a), 1)
        self.assertEqual(len(acks_b), 1)

    def test_identities_stable_after_restart(self) -> None:
        service = self._service()
        _session, locked = self._seed_locked_decision(service)
        original_id = locked.forward_test_id
        _, restarted = self._restart()
        recovered = restarted.get_decision(
            forward_test_id=original_id,
            account_id="paper-a",
        )
        self.assertEqual(recovered.forward_test_id, original_id)
        self.assertEqual(recovered.session_id, locked.session_id)
        self.assertIsNotNone(recovered.provenance_snapshot.get("git_sha"))
        self.assertIsNotNone(recovered.provenance_snapshot.get("simulator_version"))
        local = open_local_state(force=True)
        assert local is not None
        decision_row = local.connection.execute(
            """
            SELECT persist_time_ns, available_time_ns, receive_time_ns, git_sha
            FROM forward_test_decisions WHERE forward_test_id=?
            """,
            (original_id,),
        ).fetchone()
        self.assertIsNotNone(decision_row)
        self.assertIsNotNone(decision_row[0])
        self.assertIsNotNone(decision_row[3])
        session_row = local.connection.execute(
            """
            SELECT git_sha, simulator_version, persist_time_ns
            FROM forward_test_sessions WHERE session_id=?
            """,
            (locked.session_id,),
        ).fetchone()
        self.assertIsNotNone(session_row)
        self.assertIsNotNone(session_row[0])
        self.assertIsNotNone(session_row[1])
        self.assertIsNotNone(session_row[2])

    def test_observation_payload_conflict_rejected(self) -> None:
        service = self._service()
        _session, locked = self._seed_locked_decision(service)
        service.submit_to_paper(
            forward_test_id=locked.forward_test_id,
            account_id="paper-a",
            submitted_at_ns=T0 + 1,
        )
        observed = service.attach_observation(
            forward_test_id=locked.forward_test_id,
            account_id="paper-a",
            observed_at_ns=T0 + HOUR,
            source_time_ns=T0 + HOUR,
            payload={"reference_price": 100.0, "close_price": 105.0},
        )
        tampered = replace(
            observed,
            observations=(
                replace(observed.observations[0], payload={"reference_price": 1.0}),
            ),
        )
        with self.assertRaises(ForwardTestRepositoryError) as ctx:
            service._store.put_decision(tampered)
        self.assertEqual(str(ctx.exception), "FORWARD_TEST_OBSERVATION_PAYLOAD_CONFLICT")

    def test_operator_acks_survive_restart(self) -> None:
        from market_platform_foundation.ui_api.operator_opportunity_state import (
            OPERATOR_ACK_STORAGE_DURABLE,
            list_operator_acks,
            operator_ack_storage,
            record_operator_ack,
            reset_operator_acks,
        )

        self.assertEqual(operator_ack_storage(), OPERATOR_ACK_STORAGE_DURABLE)
        record_operator_ack(
            summary_id="sum-restart",
            opportunity_id="opp-restart",
            paper_account_id="paper-a",
            action="WATCHED",
            created_at_ns=T0,
        )
        reset_operator_acks()
        self._restart()
        acks = list_operator_acks(paper_account_id="paper-a")
        self.assertEqual(len(acks), 1)
        self.assertEqual(acks[0]["summary_id"], "sum-restart")
        self.assertEqual(acks[0]["opportunity_id"], "opp-restart")

    def test_signal_link_survives_restart_and_reconstructs(self) -> None:
        from market_platform_foundation.intelligence.paper_forward_bridge.reconstruction import (
            reconstruct_campaign,
        )

        service = self._service()
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
            decision_payload={"opportunity_id": "opp-link-1", "signal_id": "sig-1"},
        )
        locked = service.lock_decision(
            forward_test_id=decision.forward_test_id,
            account_id="paper-a",
            locked_at_ns=T0,
        )
        service.submit_to_paper(
            forward_test_id=locked.forward_test_id,
            account_id="paper-a",
            submitted_at_ns=T0 + 1,
            paper_order_id="ord-link-1",
        )
        local = open_local_state(force=True)
        assert local is not None
        local.connection.execute(
            """
            INSERT INTO paper_events(
                event_id, session_id, event_type, event_time, available_time,
                correlation_id, payload_json, schema_version, sequence
            ) VALUES ('ev-fill-link', 'ps-1', 'FillRecorded', ?, ?, 'c',
                      '{"order_id":"ord-link-1","fill":{"fill_id":"f-link"}}', 1, 1)
            """,
            (T0 + 2, T0 + 2),
        )
        local.connection.execute(
            """
            INSERT INTO paper_events(
                event_id, session_id, event_type, event_time, available_time,
                correlation_id, payload_json, schema_version, sequence
            ) VALUES ('ev-pnl-link', 'ps-1', 'PositionChanged', ?, ?, 'c',
                      '{"realized_pnl_minor": 250}', 1, 2)
            """,
            (T0 + 3, T0 + 3),
        )
        repo, restarted = self._restart()
        recovered = restarted.get_decision(
            forward_test_id=locked.forward_test_id,
            account_id="paper-a",
        )
        self.assertEqual(recovered.decision_payload["opportunity_id"], "opp-link-1")
        self.assertEqual(recovered.decision_payload["signal_id"], "sig-1")
        self.assertEqual(recovered.paper_order_id, "ord-link-1")
        local = open_local_state(force=True)
        assert local is not None
        links = local.connection.execute(
            """
            SELECT forward_test_id, opportunity_id, signal_id
            FROM forward_test_signal_links
            WHERE opportunity_id=?
            """,
            ("opp-link-1",),
        ).fetchall()
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0][0], locked.forward_test_id)
        self.assertEqual(links[0][2], "sig-1")
        repo.put_decision(recovered)
        count = local.connection.execute(
            "SELECT COUNT(*) FROM forward_test_signal_links WHERE opportunity_id=?",
            ("opp-link-1",),
        ).fetchone()
        self.assertEqual(int(count[0]), 1)
        reconstructed = reconstruct_campaign(
            local.connection,
            account_id="paper-a",
            campaign_id=CAMPAIGN_SLUG,
        )
        self.assertEqual(reconstructed["decision_count"], 1)
        row = reconstructed["decisions"][0]
        self.assertEqual(row["opportunity_id"], "opp-link-1")
        self.assertEqual(row["signal_id"], "sig-1")
        self.assertEqual(row["paper_order_id"], "ord-link-1")
        self.assertEqual(row["realized_pnl_minor"], 250)
        self.assertEqual(row["signal_link"]["opportunity_id"], "opp-link-1")
        self.assertEqual(row["signal_link"]["signal_id"], "sig-1")

    def test_decision_without_opportunity_id_has_no_signal_link(self) -> None:
        service = self._service()
        _session, locked = self._seed_locked_decision(service)
        local = open_local_state(force=True)
        assert local is not None
        count = local.connection.execute(
            "SELECT COUNT(*) FROM forward_test_signal_links WHERE forward_test_id=?",
            (locked.forward_test_id,),
        ).fetchone()
        self.assertEqual(int(count[0]), 0)


class PersistOffOperatorAckSemanticsTests(unittest.TestCase):
    def setUp(self) -> None:
        from market_platform_foundation.ui_api.operator_opportunity_state import (
            reset_operator_acks,
        )

        self._saved_persist = os.environ.pop("IMP_PERSIST_STATE", None)
        self._saved_dir = os.environ.pop("IMP_STATE_DIR", None)
        self._saved_campaigns = os.environ.pop("IMP_FORWARD_TEST_CAMPAIGNS_DIR", None)
        reset_operator_acks()
        reset_local_state_for_tests()
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)

    def tearDown(self) -> None:
        from market_platform_foundation.ui_api.operator_opportunity_state import (
            reset_operator_acks,
        )

        reset_operator_acks()
        reset_local_state_for_tests()
        os.environ.pop("IMP_PERSIST_STATE", None)
        os.environ.pop("IMP_STATE_DIR", None)
        os.environ.pop("IMP_FORWARD_TEST_CAMPAIGNS_DIR", None)
        if self._saved_persist is not None:
            os.environ["IMP_PERSIST_STATE"] = self._saved_persist
        if self._saved_dir is not None:
            os.environ["IMP_STATE_DIR"] = self._saved_dir
        if self._saved_campaigns is not None:
            os.environ["IMP_FORWARD_TEST_CAMPAIGNS_DIR"] = self._saved_campaigns
        self._tmp.cleanup()

    def test_operator_ack_storage_is_process_local(self) -> None:
        from market_platform_foundation.ui_api.operator_opportunity_state import (
            OPERATOR_ACK_STORAGE_PROCESS_LOCAL,
            operator_ack_storage,
        )

        self.assertEqual(operator_ack_storage(), OPERATOR_ACK_STORAGE_PROCESS_LOCAL)

    def test_persist_off_acks_vanish_after_process_reset(self) -> None:
        from market_platform_foundation.ui_api.operator_opportunity_state import (
            list_operator_acks,
            record_operator_ack,
            reset_operator_acks,
        )

        record_operator_ack(
            summary_id="sum-ephemeral",
            opportunity_id="opp-ephemeral",
            paper_account_id="paper-a",
            action="WATCHED",
            created_at_ns=T0,
        )
        self.assertEqual(len(list_operator_acks(paper_account_id="paper-a")), 1)
        reset_operator_acks()
        self.assertEqual(list_operator_acks(), ())

    def test_persist_off_acks_do_not_write_sqlite(self) -> None:
        from market_platform_foundation.ui_api.operator_opportunity_state import (
            record_operator_ack,
        )

        record_operator_ack(
            summary_id="sum-no-sqlite",
            opportunity_id="opp-no-sqlite",
            paper_account_id="paper-a",
            action="DISMISSED",
            created_at_ns=T0,
        )
        os.environ["IMP_STATE_DIR"] = self._tmp.name
        os.environ["IMP_PERSIST_STATE"] = "1"
        local = open_local_state(force=True)
        assert local is not None
        count = local.connection.execute(
            "SELECT COUNT(*) FROM opportunity_operator_acks"
        ).fetchone()
        self.assertEqual(int(count[0]), 0)

    def test_persistence_required_campaign_blocked_when_persist_off(self) -> None:
        from market_platform_foundation.intelligence.paper_forward_bridge.preflight import (
            PreflightDisposition,
            run_forward_test_preflight,
        )

        result = run_forward_test_preflight(campaign_slug="FTEP-V1-001", mode="PAPER")
        self.assertEqual(result.disposition, PreflightDisposition.NOT_READY)
        self.assertIn("PERSISTENCE_DISABLED", result.blockers)


if __name__ == "__main__":
    unittest.main()
