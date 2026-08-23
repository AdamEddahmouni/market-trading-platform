"""Operator-surface remediation batch (E4/E5/E6/E7/E8/E12/E13) regression tests."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))

from market_platform_foundation.local_state.startup import (
    open_local_state,
    persist_ledger,
    reset_local_state_for_tests,
    restore_open_ledger,
    startup_report,
)
from market_platform_foundation.market_data.internal_simulation_gate import (
    evaluate_internal_simulation_gates,
    external_execution_path_active,
)
from market_platform_foundation.paper.ledger import PaperExecutionLedger
from market_platform_foundation.ui_api.operator_projections import replay_capture, save_preferences
from market_platform_foundation.ui_api.paper_projections import cancel_paper_order, open_paper_session
from market_platform_foundation.ui_api.server import LEDGER_ROUTE_LOCK, UiApiHandler
from market_platform_foundation.ui_api.store import ReplayStore

COLLECTION_ROOT = ROOT.parent


class IsolatedStateTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ["IMP_STATE_DIR"] = self._tmp.name
        os.environ["IMP_PERSIST_STATE"] = "1"
        os.environ.pop("IMP_LIVE_EXECUTION", None)
        os.environ.pop("IMP_PAPER_EXECUTION", None)
        os.environ.pop("IMP_BROKER_PAPER_EXECUTION", None)
        reset_local_state_for_tests()

    def tearDown(self) -> None:
        reset_local_state_for_tests()
        os.environ.pop("IMP_STATE_DIR", None)
        os.environ.pop("IMP_PERSIST_STATE", None)
        os.environ.pop("IMP_PAPER_EXECUTION", None)
        os.environ.pop("IMP_BROKER_PAPER_EXECUTION", None)
        self._tmp.cleanup()


def _open_broker_paper_ledger() -> PaperExecutionLedger:
    ledger = PaperExecutionLedger.open_session(
        replay_session_id="replay-restore",
        instrument_id="AAPL",
        symbol="AAPL",
        execution_mode="BROKER_PAPER",
        execution_authority="PAPER_ONLY",
    )
    persist_ledger(ledger)
    return ledger


class RestoreAuthorityTests(IsolatedStateTest):
    """E4: restore derives authority from the stored execution mode's own gate."""

    def _restore_broker_paper_session(self) -> tuple[PaperExecutionLedger | None, dict]:
        ledger = _open_broker_paper_ledger()
        session_id = ledger.session_id
        reset_local_state_for_tests()
        repo = open_local_state(force=True)
        assert repo is not None
        stored = repo.load_session(session_id)
        assert stored is not None
        current = {
            "data_mode": stored["data_mode"],
            "data_provider": stored["data_provider"],
            "execution_provider": stored["execution_provider"],
            "starting_cash_minor": int(stored["starting_cash_minor"]),
        }
        return restore_open_ledger(current_config=current)

    def test_broker_paper_resumes_under_its_own_gate_alone(self) -> None:
        os.environ["IMP_BROKER_PAPER_EXECUTION"] = "1"
        restored, details = self._restore_broker_paper_session()
        assert restored is not None
        self.assertEqual(restored.execution_mode, "BROKER_PAPER")
        self.assertEqual(restored.execution_authority, "PAPER_ONLY")
        self.assertNotIn("env_override", details)

    def test_broker_paper_blocked_without_gate(self) -> None:
        restored, details = self._restore_broker_paper_session()
        assert restored is not None
        self.assertEqual(restored.execution_authority, "BLOCKED")
        self.assertEqual(details.get("env_override"), "IMP_BROKER_PAPER_EXECUTION")

    def test_internal_simulation_restore_unchanged(self) -> None:
        # Regression guard: INTERNAL_SIMULATION still gated by IMP_PAPER_EXECUTION.
        ledger = PaperExecutionLedger.open_session(
            replay_session_id="replay-restore",
            instrument_id="AAPL",
            symbol="AAPL",
            execution_mode="INTERNAL_SIMULATION",
            execution_authority="AUTHORIZED",
        )
        persist_ledger(ledger)
        session_id = ledger.session_id
        reset_local_state_for_tests()
        repo = open_local_state(force=True)
        assert repo is not None
        stored = repo.load_session(session_id)
        assert stored is not None
        current = {
            "data_mode": stored["data_mode"],
            "data_provider": stored["data_provider"],
            "execution_provider": stored["execution_provider"],
            "starting_cash_minor": int(stored["starting_cash_minor"]),
        }
        restored, details = restore_open_ledger(current_config=current)
        assert restored is not None
        self.assertEqual(restored.execution_authority, "BLOCKED")
        self.assertEqual(details.get("env_override"), "IMP_PAPER_EXECUTION")

    def test_startup_report_deferred_follows_stored_mode(self) -> None:
        os.environ["IMP_BROKER_PAPER_EXECUTION"] = "1"
        _open_broker_paper_ledger()
        report = startup_report(live_healthy=True)
        self.assertFalse(report["execution_deferred"])


class CancelDispatchTests(IsolatedStateTest):
    """E6: /paper/orders/cancel dispatches on execution_mode, fail-closed."""

    @staticmethod
    def _broker_ledger_with_working_order() -> PaperExecutionLedger:
        ledger = PaperExecutionLedger.open_session(
            replay_session_id="replay-cancel",
            instrument_id="AAPL",
            symbol="AAPL",
            execution_mode="BROKER_PAPER",
            execution_authority="PAPER_ONLY",
        )
        intent = {
            "client_order_id": "c-e6",
            "idempotency_key": "c-e6",
            "intent_id": "int-e6",
            "quantity": 1,
            "side": "BUY",
        }
        ledger.append_intent(intent)
        ledger.append_order({"order_id": "ord-e6", "state": "CREATED"}, intent=intent)
        ledger.append_order_state(
            order_id="ord-e6",
            state="ACTIVATED",
            prior_state="CREATED",
            broker_order_id="BRK-E6",
        )
        return ledger

    class _FakeBrokerProvider:
        provider_id = "fake.broker.paper"
        capability = "paper_execution"

        def __init__(self) -> None:
            self.calls: list[dict] = []

        def cancel_order(self, *, client_order_id=None, broker_order_id=None):
            self.calls.append({"broker_order_id": broker_order_id, "client_order_id": client_order_id})
            return mock.Mock(reason_code="", status="ok")

    def _store_with_broker_ledger(self) -> ReplayStore:
        store = ReplayStore(collection_root=COLLECTION_ROOT)
        store.load()
        store.paper_ledger = self._broker_ledger_with_working_order()
        return store

    def test_broker_cancel_routed_through_composed_provider(self) -> None:
        store = self._store_with_broker_ledger()
        provider = self._FakeBrokerProvider()
        with mock.patch(
            "market_platform_foundation.providers.composition.get_provider_composition"
        ) as factory:
            factory.return_value.paper_execution = provider
            payload = cancel_paper_order(store, {"order_id": "ord-e6"})
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(provider.calls[0]["broker_order_id"], "BRK-E6")
        self.assertEqual(payload["cancellation"]["state"], "CANCELLED")

    def test_broker_cancel_fail_closed_without_composed_adapter(self) -> None:
        from market_platform_foundation.providers.composition import configure_provider_composition

        configure_provider_composition(None)  # disabled stub occupies the slot
        store = self._store_with_broker_ledger()
        ledger = store.paper_ledger
        events_before = len(ledger.events)
        with self.assertRaises(ValueError) as raised:
            cancel_paper_order(store, {"order_id": "ord-e6"})
        self.assertIn("PROVIDER_NOT_CONFIGURED", str(raised.exception))
        # No local-only CANCEL event may be appended while the broker order lives.
        cancelled = [
            event
            for event in ledger.events
            if event["event_type"] == "OrderStateChanged" and event["payload"].get("state") == "CANCELLED"
        ]
        self.assertEqual(cancelled, [])
        self.assertEqual(len(ledger.events), events_before)


class LiveSessionRefusalTests(IsolatedStateTest):
    """E8: LIVE sessions are refused at open (no live execution capability)."""

    def test_live_mode_refused(self) -> None:
        os.environ["IMP_LIVE_EXECUTION"] = "1"  # even the env flag cannot conjure capability
        store = ReplayStore(collection_root=COLLECTION_ROOT)
        store.load()
        existing_session = store.paper_ledger.session_id
        with self.assertRaises(ValueError) as raised:
            open_paper_session(store, {"execution_mode": "LIVE"})
        self.assertIn("OPERATING_MODE_UNSUPPORTED", str(raised.exception))
        self.assertEqual(store.paper_ledger.session_id, existing_session)


class PreferenceGuardTests(IsolatedStateTest):
    """E12: preference writer blocks safety-relevant env-shaped keys."""

    def test_safety_keys_blocked(self) -> None:
        repo = open_local_state(force=True)
        assert repo is not None
        for key in ("EXECUTION_ENABLE", "my_live_theme", "tradier_token", "MOOMOO_ENDPOINT", "IMP_ANYTHING"):
            with self.assertRaises(ValueError, msg=key):
                save_preferences({"preferences": {key: "x"}})

    def test_benign_keys_accepted(self) -> None:
        open_local_state(force=True)
        payload = save_preferences({"preferences": {"theme": "dark", "default_quantity": 10}})
        self.assertEqual(payload["preferences"].get("theme"), "dark")


class CaptureProvenanceTests(IsolatedStateTest):
    """E13: canonical data mode, explicit provenance, no env mutation."""

    def test_replay_capture_is_canonical_and_env_clean(self) -> None:
        repo = open_local_state(force=True)
        assert repo is not None
        repo.upsert_capture(
            {
                "capture_id": "cap-e13",
                "manifest_path": "captures/cap-e13/manifest.json",
                "events_path": "captures/cap-e13/events.jsonl",
                "provider": "MOOMOO",
                "status": "AVAILABLE",
            }
        )
        sentinel = os.environ.pop("IMP_LIVE_FIXTURE_FEED", None)
        try:
            payload = replay_capture({"capture_id": "cap-e13"})
        finally:
            restored = os.environ.pop("IMP_LIVE_FIXTURE_FEED", None)
        self.assertIsNone(restored)
        if sentinel is not None:
            os.environ["IMP_LIVE_FIXTURE_FEED"] = sentinel
        self.assertEqual(payload["data_mode"], "HISTORICAL_CAPTURE")
        self.assertEqual(payload["status"], "READY")
        self.assertIn("HISTORICAL_CAPTURE", payload["provenance"])


class GateHonestyTests(unittest.TestCase):
    """E7: gates are labeled from checkable facts, never hardcoded PASS."""

    def test_pit_unverified_labeled_attested_not_pass(self) -> None:
        gate = evaluate_internal_simulation_gates(runtime=None, external_path_active=False)
        self.assertEqual(gate.gates["PIT_ADVERSARIAL"], "ATTESTED")
        self.assertNotIn("PIT_ADVERSARIAL", gate.blocking)

    def test_pit_verified_false_blocks(self) -> None:
        gate = evaluate_internal_simulation_gates(runtime=None, pit_tests_pass=False, external_path_active=False)
        self.assertEqual(gate.gates["PIT_ADVERSARIAL"], "FAIL")
        self.assertIn("PIT_ADVERSARIAL", gate.blocking)

    def test_pit_verified_true_passes(self) -> None:
        gate = evaluate_internal_simulation_gates(runtime=None, pit_tests_pass=True, external_path_active=False)
        self.assertEqual(gate.gates["PIT_ADVERSARIAL"], "PASS")

    def test_external_execution_path_fails_closed(self) -> None:
        gate = evaluate_internal_simulation_gates(runtime=None, external_path_active=True)
        self.assertEqual(gate.gates["NO_EXTERNAL_EXECUTION_PATH"], "FAIL")
        self.assertIn("NO_EXTERNAL_EXECUTION_PATH", gate.blocking)

    def test_default_fact_check_inspects_composition(self) -> None:
        from market_platform_foundation.providers.composition import (
            ProviderComposition,
            configure_provider_composition,
        )
        from market_platform_foundation.providers.stubs import DisabledPaperExecutionProvider

        try:
            configure_provider_composition(ProviderComposition())
            self.assertFalse(external_execution_path_active())
            gate = evaluate_internal_simulation_gates(runtime=None)
            self.assertEqual(gate.gates["NO_EXTERNAL_EXECUTION_PATH"], "PASS")
            composition = ProviderComposition()
            composition.paper_execution = self._FakeAdapter()
            configure_provider_composition(composition)
            self.assertTrue(external_execution_path_active())
            gate = evaluate_internal_simulation_gates(runtime=None)
            self.assertIn("NO_EXTERNAL_EXECUTION_PATH", gate.blocking)
        finally:
            configure_provider_composition(None)

    class _FakeAdapter:
        provider_id = "fake.broker.paper"
        capability = "paper_execution"


class LedgerRouteLockSmokeTests(IsolatedStateTest):
    """E5: parallel submits through the real threaded server keep sequences unique."""

    def test_parallel_submits_have_unique_event_sequences(self) -> None:
        os.environ["IMP_PAPER_EXECUTION"] = "1"
        store = ReplayStore(collection_root=COLLECTION_ROOT)
        store.load()
        open_paper_session(store, {"execution_mode": "INTERNAL_SIMULATION"})

        handler = type("BoundHandler", (UiApiHandler,), {"store": store})
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            workers = 8

            def post(index: int) -> int:
                body = json.dumps(
                    {
                        "side": "BUY",
                        "quantity": 1,
                        "client_order_id": f"e5-{index}",
                        "idempotency_key": f"e5-{index}",
                    }
                ).encode("utf-8")
                request = urllib.request.Request(
                    f"http://127.0.0.1:{port}/paper/orders",
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=30) as response:
                    return response.status

            results: list[int] = []
            errors: list[Exception] = []
            lock = threading.Lock()

            def worker(index: int) -> None:
                try:
                    status = post(index)
                except Exception as exc:  # noqa: BLE001 - surfaced below
                    with lock:
                        errors.append(exc)
                    return
                with lock:
                    results.append(status)

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(workers)]
            for item in threads:
                item.start()
            for item in threads:
                item.join()

            self.assertEqual(errors, [])
            self.assertEqual(sorted(results), [200] * workers)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=10)

        submitted = [
            int(event["sequence"])
            for event in store.paper_ledger.events
            if event["event_type"] == "OrderSubmitted"
        ]
        self.assertEqual(len(submitted), 8)
        self.assertEqual(len(set(submitted)), len(submitted))
        # The route bodies serialize on the module-level lock.
        self.assertIsInstance(LEDGER_ROUTE_LOCK, type(threading.Lock()))


if __name__ == "__main__":
    unittest.main()
