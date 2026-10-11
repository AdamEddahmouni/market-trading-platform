"""Regression tests for safe ReplayStore base-payload reuse."""

from __future__ import annotations

import tempfile
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.canonical import canonical_bytes
from market_platform_foundation.ui_api import store as store_module


class ReplayStoreLoadingTests(unittest.TestCase):
    def test_verified_payload_is_reused_but_mutable_state_is_not_shared(self) -> None:
        self.assertTrue(hasattr(store_module, "_cached_replay_payload"))
        store_module._cached_replay_payload.cache_clear()
        store_module._cached_decoded_replay_snapshot.cache_clear()
        payload = canonical_bytes(
            {
                "evaluation": {"risk_decisions": []},
                "events": [
                    {
                        "available_time": 1,
                        "event_type": "BAR_OHLCV_1M",
                        "instrument_id": "TEST",
                        "normalized_event_id": "event-1",
                    }
                ],
                "instrument_id": "TEST",
                "session_id": "session-1",
                "strategy": {"interpretations": []},
            }
        )
        with tempfile.TemporaryDirectory() as first_audit, tempfile.TemporaryDirectory() as second_audit:
            with patch.object(store_module, "_replay_source_digest", return_value="verified"), patch.object(
                store_module, "_build_replay_payload", return_value=payload
            ) as build:
                first = store_module.ReplayStore(
                    collection_root=Path("collection"),
                    assistant_audit_root=Path(first_audit),
                )
                second = store_module.ReplayStore(
                    collection_root=Path("collection"),
                    assistant_audit_root=Path(second_audit),
                )
                first.load()
                second.load()
        self.assertEqual(build.call_count, 1)
        self.assertEqual(first.bars, second.bars)
        self.assertIsNot(first.bars, second.bars)
        self.assertIsNot(first.bars[0], second.bars[0])
        first.bars[0]["instrument_id"] = "MUTATED"
        self.assertEqual(second.bars[0]["instrument_id"], "TEST")

    def test_load_decoded_snapshot_keeps_fixture_replay_under_live_gate(self) -> None:
        snapshot = {
            "evaluation": {"risk_decisions": []},
            "events": [
                {
                    "available_time": 1,
                    "event_type": "BAR_OHLCV_1M",
                    "instrument_id": "HIST",
                    "normalized_event_id": "hist-event-1",
                    "bar_payload": {"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1},
                }
            ],
            "instrument_id": "HIST",
            "session_id": "hist-session",
            "strategy": {"interpretations": []},
        }
        with tempfile.TemporaryDirectory() as audit_dir:
            store = store_module.ReplayStore(
                collection_root=Path("collection"),
                data_mode="FIXTURE_REPLAY",
                mode="REPLAY",
                assistant_audit_root=Path(audit_dir),
            )
            with patch(
                "market_platform_foundation.market_data.live_config.live_observational_enabled",
                return_value=True,
            ):
                store.load_decoded_snapshot(snapshot)
        self.assertEqual(store.data_mode, "FIXTURE_REPLAY")


class LiveStartupIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        import os
        from market_platform_foundation.local_state.startup import reset_local_state_for_tests
        from market_platform_foundation.local_state.paper_experiments import reset_paper_experiment_repository_for_tests
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {
            "IMP_STATE_DIR": self.temp.name, "IMP_PERSIST_STATE": "1",
            "IMP_LIVE_OBSERVATIONAL": "1", "IMP_MOOMOO_LIVE": "1",
            "IMP_PAPER_EXECUTION": "1", "IMP_LIVE_INTERNAL_SIMULATION": "1",
            "IMP_CONTROLLED_REPLAY": "0", "IMP_LIVE_EXECUTION": "0",
            "IMP_BROKER_PAPER_EXECUTION": "0",
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        reset_local_state_for_tests()
        reset_paper_experiment_repository_for_tests()
        self.addCleanup(reset_local_state_for_tests)
        self.addCleanup(reset_paper_experiment_repository_for_tests)

    def boot(self, *, live=True):
        store = store_module.ReplayStore(
            collection_root=Path(self.temp.name),
            data_mode="LIVE_OBSERVATIONAL" if live else "FIXTURE_REPLAY",
            data_provider="MOOMOO" if live else "INTERNAL",
        )
        store.load_decoded_snapshot({
            "evaluation": {}, "strategy": {}, "instrument_id": "TEST", "session_id": "startup-fixture",
            "events": [{"available_time": 1, "event_type": "BAR_OHLCV_1M",
                        "instrument_id": "TEST", "normalized_event_id": "startup-bar"}],
        })
        return store

    def sessions(self):
        from market_platform_foundation.local_state.startup import open_local_state
        return [tuple(r) for r in open_local_state().connection.execute(
            "SELECT session_id,status,data_mode,execution_mode,starting_cash_minor FROM paper_sessions ORDER BY session_id")]

    def test_live_without_admitted_session_does_not_persist_default_account(self):
        store = self.boot()
        self.assertEqual(self.sessions(), [])
        self.assertTrue(store.execution_deferred)
        self.assertEqual(store.execution_authority, "BLOCKED")
        self.assertEqual(store.restore_details["reason"], "PAPER_SESSION_ACTIVATION_REQUIRED")

    def test_live_preserves_incompatible_replay_session(self):
        replay = self.boot(live=False)
        before = self.sessions()
        live = self.boot()
        self.assertEqual(self.sessions(), before)
        self.assertEqual(live.data_mode, "LIVE_OBSERVATIONAL")
        self.assertNotEqual(live.paper_ledger.session_id, replay.paper_ledger.session_id)
        self.assertTrue(live.execution_deferred)

    def test_live_preserves_closed_session_and_balance(self):
        from market_platform_foundation.local_state.startup import persist_ledger
        from market_platform_foundation.paper.ledger import PaperExecutionLedger
        from market_platform_foundation.risk.policy import DEFAULT_RISK_POLICY
        ledger = PaperExecutionLedger.open_session(
            replay_session_id="closed-owner", instrument_id="TEST", symbol="TEST",
            data_mode="LIVE_OBSERVATIONAL", data_provider="MOOMOO",
            execution_mode="INTERNAL_SIMULATION", execution_authority="PAPER_ONLY",
            policy={**DEFAULT_RISK_POLICY, "initial_cash_minor": 10_000_000})
        ledger.close_session()
        persist_ledger(ledger)
        before = self.sessions()
        store = self.boot()
        self.assertEqual(self.sessions(), before)
        self.assertEqual(store.execution_authority, "BLOCKED")
        self.assertEqual(store.restore_details["reason"], "PAPER_SESSION_ACTIVATION_REQUIRED")

    def test_entrypoint_selects_live_identity_before_load(self):
        from tools.ui1 import run_ui_api
        seen = []
        with patch.object(run_ui_api.ReplayStore, "load", lambda s: seen.append((s.data_mode,s.data_provider))), patch(
            "market_platform_foundation.ui_api.live_intelligence.bind_ui_api_intelligence"), patch(
            "tools.ibkr.runtime_bootstrap.install_ibkr_observational_provider"), patch(
            "market_platform_foundation.market_data.live_runtime.get_live_runtime"):
            run_ui_api._load_store()
        self.assertEqual(seen, [("LIVE_OBSERVATIONAL", "MOOMOO")])

    def test_controlled_replay_entrypoint_keeps_replay_identity(self):
        import os
        from tools.ui1 import run_ui_api
        seen = []
        with patch.dict(os.environ, {"IMP_CONTROLLED_REPLAY":"1"}), patch.object(
            run_ui_api.ReplayStore, "load", lambda s: seen.append((s.data_mode,s.data_provider))), patch(
            "market_platform_foundation.ui_api.live_intelligence.bind_ui_api_intelligence"):
            run_ui_api._load_store()
        self.assertEqual(seen, [("FIXTURE_REPLAY", "INTERNAL")])


    def test_live_marks_cannot_persist_unadmitted_startup_projection(self):
        from market_platform_foundation.ui_api.live_projections import apply_live_marks_to_ledger
        from unittest.mock import Mock
        store = self.boot()
        runtime = Mock()
        runtime.live_mark_for.return_value = {"mark_minor":10000,"mark_provider":"MOOMOO",
            "mark_as_of_ns":1,"mark_quality":"STALE"}
        with patch("market_platform_foundation.ui_api.live_projections._runtime_or_none", return_value=runtime), patch(
            "market_platform_foundation.ui_api.paper_projections._live_focus_instrument_id",return_value="TEST"):
            apply_live_marks_to_ledger(store)
        self.assertEqual(self.sessions(), [])

    def test_explicit_experiment_creation_does_not_persist_placeholder(self):
        from market_platform_foundation.ui_api.paper_experiment import create_experiment
        store = self.boot()
        experiment = create_experiment(store,{})["experiment"]
        sessions = self.sessions()
        self.assertEqual(len(sessions),1)
        self.assertEqual(sessions[0][0],experiment["paper_session_id"])
        self.assertEqual(sessions[0][4],10_000_000)

    def test_compatible_live_experiment_restores_without_reseeding(self):
        from market_platform_foundation.ui_api.paper_experiment import create_experiment
        store = self.boot()
        experiment = create_experiment(store,{})["experiment"]
        before = self.sessions()
        restored = self.boot()
        self.assertEqual(self.sessions(),before)
        self.assertEqual(restored.paper_ledger.session_id,experiment["paper_session_id"])
        self.assertEqual(restored.paper_ledger.policy["initial_cash_minor"],10_000_000)
        self.assertTrue(restored.execution_deferred)


if __name__ == "__main__":
    unittest.main()
