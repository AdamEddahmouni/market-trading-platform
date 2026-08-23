"""Platformization P3 durable local state tests. Isolated temp IMP_STATE_DIR."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))

from market_platform_foundation.local_state.connection import CorruptStateError, LocalStateConnection
from market_platform_foundation.local_state.migrations import SchemaVersionError
from market_platform_foundation.local_state.repository import reject_secret_key
from market_platform_foundation.local_state.schema import SCHEMA_VERSION
from market_platform_foundation.local_state.startup import (
    ledger_from_session,
    open_local_state,
    persist_ledger,
    reset_local_state_for_tests,
    restore_open_ledger,
    session_record_from_ledger,
)
from market_platform_foundation.paper.execution import submit_interactive_order
from market_platform_foundation.paper.ledger import PaperExecutionLedger
from market_platform_foundation.ui_api.paper_projections import open_paper_session
from market_platform_foundation.ui_api.store import ReplayStore

COLLECTION_ROOT = ROOT.parent


class IsolatedStateTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ["IMP_STATE_DIR"] = self._tmp.name
        os.environ["IMP_PERSIST_STATE"] = "1"
        os.environ.pop("IMP_LIVE_EXECUTION", None)
        reset_local_state_for_tests()

    def tearDown(self) -> None:
        reset_local_state_for_tests()
        os.environ.pop("IMP_STATE_DIR", None)
        os.environ.pop("IMP_PERSIST_STATE", None)
        os.environ.pop("IMP_PAPER_EXECUTION", None)
        self._tmp.cleanup()


class SchemaMigrationTests(IsolatedStateTest):
    def test_create_migrate_verify(self) -> None:
        repo = open_local_state(force=True)
        assert repo is not None
        self.assertEqual(repo.connection.schema_version(), SCHEMA_VERSION)
        self.assertTrue(repo.connection.integrity_ok())

    def test_unknown_newer_schema_fail_closed(self) -> None:
        repo = open_local_state(force=True)
        assert repo is not None
        path = repo.connection.path
        repo.connection.execute("INSERT INTO schema_meta(schema_version, applied_at) VALUES (99, 'future')")
        reset_local_state_for_tests()
        with self.assertRaises(SchemaVersionError):
            LocalStateConnection(path)

    def test_corrupt_db_fail_closed_preserves_file(self) -> None:
        repo = open_local_state(force=True)
        assert repo is not None
        path = repo.connection.path
        reset_local_state_for_tests()
        path.write_bytes(b"not a sqlite database")
        with self.assertRaises((CorruptStateError, sqlite3.DatabaseError)):
            LocalStateConnection(path)
        self.assertEqual(path.read_bytes(), b"not a sqlite database")


class PaperPersistenceTests(IsolatedStateTest):
    def _open_authorized(self) -> tuple[ReplayStore, list[dict]]:
        os.environ["IMP_PAPER_EXECUTION"] = "1"
        store = ReplayStore(collection_root=COLLECTION_ROOT)
        store.load()
        open_paper_session(store, {"execution_mode": "INTERNAL_SIMULATION"})
        for index in range(len(store.bars) - 2, -1, -1):
            store.set_cursor_index(index)
            bars = store.bars_for_execution()
            if not bars:
                continue
            from market_platform_foundation.paper.execution import preview_interactive_order

            probe = preview_interactive_order(
                ledger=store.paper_ledger,
                bars=bars,
                symbol=store.symbol,
                instrument_id=store.instrument_id,
                side="BUY",
                quantity=1,
                observation_time=store.prediction_cutoff(),
                client_order_id="p3-probe",
                idempotency_key="p3-probe",
            )
            if probe.get("fill_preview") is not None and probe.get("risk_status") == "PASS":
                return store, bars
        self.fail("no fillable bars")
        raise AssertionError

    def test_persisted_ledger_replay_equivalence(self) -> None:
        store, bars = self._open_authorized()
        result = submit_interactive_order(
            ledger=store.paper_ledger,
            bars=bars,
            symbol=store.symbol,
            instrument_id=store.instrument_id,
            side="BUY",
            quantity=1,
            observation_time=store.prediction_cutoff(),
            client_order_id="p3-eq-1",
            idempotency_key="p3-eq-1",
        )
        self.assertFalse(result["duplicate"])
        live_account = store.paper_ledger.project_account()
        live_positions = store.paper_ledger.project_positions()
        live_orders = store.paper_ledger.project_orders()
        live_fills = store.paper_ledger.project_fills()
        session_id = store.paper_ledger.session_id
        reset_local_state_for_tests()
        repo = open_local_state(force=True)
        assert repo is not None
        row = repo.load_session(session_id)
        assert row is not None
        rebuilt = ledger_from_session(row, repo.load_events(session_id), repo.load_idempotency(session_id))
        self.assertEqual(rebuilt.project_account()["cash_minor"], live_account["cash_minor"])
        self.assertEqual(rebuilt.project_positions()[0]["quantity"], live_positions[0]["quantity"])
        self.assertEqual(len(rebuilt.project_orders()), len(live_orders))
        self.assertEqual(len(rebuilt.project_fills()), len(live_fills))
        self.assertNotEqual(rebuilt.project_positions()[0].get("mark_quality"), "HEALTHY")

    def test_idempotency_survives_restart(self) -> None:
        store, bars = self._open_authorized()
        first = submit_interactive_order(
            ledger=store.paper_ledger,
            bars=bars,
            symbol=store.symbol,
            instrument_id=store.instrument_id,
            side="BUY",
            quantity=1,
            observation_time=store.prediction_cutoff(),
            client_order_id="p3-idem",
            idempotency_key="p3-idem",
        )
        session_id = store.paper_ledger.session_id
        fill_count = len(store.paper_ledger.project_fills())
        reset_local_state_for_tests()
        repo = open_local_state(force=True)
        assert repo is not None
        restored = ledger_from_session(
            repo.load_session(session_id),
            repo.load_events(session_id),
            repo.load_idempotency(session_id),
        )
        restored.execution_authority = "AUTHORIZED"
        restored.execution_mode = "INTERNAL_SIMULATION"
        second = submit_interactive_order(
            ledger=restored,
            bars=bars,
            symbol=store.symbol,
            instrument_id=store.instrument_id,
            side="BUY",
            quantity=1,
            observation_time=store.prediction_cutoff(),
            client_order_id="p3-idem",
            idempotency_key="p3-idem",
        )
        self.assertTrue(second["duplicate"])
        self.assertEqual(second["order_id"], first["order_id"])
        self.assertEqual(len(restored.project_fills()), fill_count)

    def test_trace_survives_restart(self) -> None:
        store, bars = self._open_authorized()
        result = submit_interactive_order(
            ledger=store.paper_ledger,
            bars=bars,
            symbol=store.symbol,
            instrument_id=store.instrument_id,
            side="BUY",
            quantity=1,
            observation_time=store.prediction_cutoff(),
            client_order_id="p3-trace",
            idempotency_key="p3-trace",
            correlation_id="corr-p3-trace",
        )
        session_id = store.paper_ledger.session_id
        reset_local_state_for_tests()
        repo = open_local_state(force=True)
        assert repo is not None
        restored = ledger_from_session(
            repo.load_session(session_id),
            repo.load_events(session_id),
            repo.load_idempotency(session_id),
        )
        trace = restored.project_execution_trace(intent_id=result["intent_id"])
        self.assertGreaterEqual(len(trace["steps"]), 4)
        self.assertEqual(trace["broker_order_submitted"], False)
        self.assertIsNone(trace["broker_order_id"])
        matching = [event for event in restored.events if event.get("correlation_id") == "corr-p3-trace"]
        self.assertGreaterEqual(len(matching), 1)

    def test_open_session_ids_unique_under_frozen_clock(self) -> None:
        """Regression: two opens in the same (coarse/frozen) clock tick differ.

        session ids are content hashes of the session body, which includes
        ``opened_at_ns``; on environments where ``time.time_ns()`` is frozen
        for whole ticks, a uniqueness nonce keeps ids distinct.
        """
        from unittest import mock

        frozen = 1787000000000000000
        with mock.patch(
            "market_platform_foundation.paper.ledger.time.time_ns", return_value=frozen
        ):
            first = PaperExecutionLedger.open_session(
                replay_session_id="frozen-clock-1",
                instrument_id="BIYA",
                symbol="BIYA",
                execution_mode="BROKER_PAPER",
                execution_authority="PAPER_ONLY",
            )
            second = PaperExecutionLedger.open_session(
                replay_session_id="frozen-clock-1",
                instrument_id="BIYA",
                symbol="BIYA",
                execution_mode="BROKER_PAPER",
                execution_authority="PAPER_ONLY",
            )
        self.assertNotEqual(first.session_id, second.session_id)

    def test_sessions_isolated_and_archive(self) -> None:
        store, bars = self._open_authorized()
        submit_interactive_order(
            ledger=store.paper_ledger,
            bars=bars,
            symbol=store.symbol,
            instrument_id=store.instrument_id,
            side="BUY",
            quantity=1,
            observation_time=store.prediction_cutoff(),
            client_order_id="p3-old",
            idempotency_key="p3-old",
        )
        old_id = store.paper_ledger.session_id
        open_paper_session(store, {"execution_mode": "INTERNAL_SIMULATION"})
        self.assertNotEqual(store.paper_ledger.session_id, old_id)
        self.assertEqual(store.paper_ledger.project_positions(), [])
        repo = open_local_state(force=True)
        assert repo is not None
        old = repo.load_session(old_id)
        assert old is not None
        self.assertEqual(old["status"], "CLOSED")
        self.assertEqual(repo.latest_open_session()["session_id"], store.paper_ledger.session_id)

    def test_safety_env_not_overridden_by_restore(self) -> None:
        store, bars = self._open_authorized()
        submit_interactive_order(
            ledger=store.paper_ledger,
            bars=bars,
            symbol=store.symbol,
            instrument_id=store.instrument_id,
            side="BUY",
            quantity=1,
            observation_time=store.prediction_cutoff(),
            client_order_id="p3-safe",
            idempotency_key="p3-safe",
        )
        os.environ.pop("IMP_PAPER_EXECUTION", None)
        reset_local_state_for_tests()
        current = session_record_from_ledger(store.paper_ledger)
        restored, details = restore_open_ledger(current_config=current)
        assert restored is not None
        self.assertEqual(restored.execution_authority, "BLOCKED")
        self.assertEqual(details.get("env_override"), "IMP_PAPER_EXECUTION")
        with self.assertRaises(ValueError):
            submit_interactive_order(
                ledger=restored,
                bars=bars,
                symbol=store.symbol,
                instrument_id=store.instrument_id,
                side="BUY",
                quantity=1,
                observation_time=store.prediction_cutoff(),
                client_order_id="p3-blocked",
                idempotency_key="p3-blocked",
            )


class OperatorStateTests(IsolatedStateTest):
    def test_watchlist_recent_workspace_prefs(self) -> None:
        repo = open_local_state(force=True)
        assert repo is not None
        default = repo.ensure_default_watchlist()
        repo.replace_watchlist_items(default["watchlist_id"], ["AAPL", "MSFT"])
        lists = repo.list_watchlists()
        self.assertEqual(len(lists), 1)
        self.assertEqual([item["instrument_id"] for item in lists[0]["items"]], ["AAPL", "MSFT"])
        repo.record_recent_instrument("AAPL")
        repo.record_recent_instrument("NVDA")
        recents = repo.list_recent_instruments()
        self.assertEqual([row["instrument_id"] for row in recents[:2]], ["NVDA", "AAPL"])
        saved = repo.save_workspace(
            {
                "selected_instrument": "AAPL",
                "open_panels": ["quote", "dom"],
                "panel_order": ["quote", "dom"],
                "hover": "should-ignore",
            }
        )
        self.assertNotIn("hover", saved["layout"])
        repo.set_preference("data_provider", "MOOMOO")
        with self.assertRaises(ValueError):
            reject_secret_key("api_key")
        with self.assertRaises(ValueError):
            repo.set_preference("moomoo_unlock_password", "x")

    def test_capture_missing_status(self) -> None:
        repo = open_local_state(force=True)
        assert repo is not None
        repo.upsert_capture(
            {
                "capture_id": "missing-1",
                "manifest_path": str(Path(self._tmp.name) / "nope.manifest.json"),
                "status": "MISSING",
            }
        )
        rows = repo.list_captures()
        by_id = {row["capture_id"]: row for row in rows}
        self.assertEqual(by_id["missing-1"]["status"], "MISSING")


class CrashConsistencyTests(IsolatedStateTest):
    def test_transaction_rollback_does_not_fabricate(self) -> None:
        repo = open_local_state(force=True)
        assert repo is not None
        store = ReplayStore(collection_root=COLLECTION_ROOT)
        store.load()
        os.environ["IMP_PAPER_EXECUTION"] = "1"
        open_paper_session(store, {"execution_mode": "INTERNAL_SIMULATION"})
        session = session_record_from_ledger(store.paper_ledger)
        with self.assertRaises(sqlite3.OperationalError):
            with repo.connection.transaction():
                repo.connection.execute(
                    "INSERT INTO paper_events(event_id, session_id, event_type, event_time, available_time, correlation_id, payload_json, schema_version, sequence) VALUES (?,?,?,?,?,?,?,?,?)",
                    ("dead", session["session_id"], "FillRecorded", 1, 1, None, "{}", 1, 99),
                )
                repo.connection.execute("INSERT INTO paper_events_nope VALUES (1)")
        leftover = repo.connection.execute(
            "SELECT COUNT(*) AS n FROM paper_events WHERE event_id='dead'"
        ).fetchone()
        self.assertEqual(int(leftover["n"]), 0)

    def test_duplicate_event_insert_is_idempotent(self) -> None:
        os.environ["IMP_PAPER_EXECUTION"] = "1"
        store = ReplayStore(collection_root=COLLECTION_ROOT)
        store.load()
        open_paper_session(store, {"execution_mode": "INTERNAL_SIMULATION"})
        persist_ledger(store.paper_ledger)
        persist_ledger(store.paper_ledger)
        repo = open_local_state(force=True)
        assert repo is not None
        events = repo.load_events(store.paper_ledger.session_id)
        sequences = [event["sequence"] for event in events]
        self.assertEqual(sequences, sorted(set(sequences)))


if __name__ == "__main__":
    unittest.main()
