"""P3.1 live internal execution: PIT-eligible LIVE_L1_SNAPSHOT bars only."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))

from market_platform_foundation.market_data.execution_event_buffer import LIVE_L1_TIMEFRAME, LiveExecutionEventBuffer
from market_platform_foundation.market_data.live_admission import ADMISSION_BLOCKED, ADMISSION_EXECUTION, LiveAdmissionEngine
from market_platform_foundation.market_data.live_runtime import LiveObservationalRuntime
from market_platform_foundation.paper.contracts import build_instrument_ref, build_user_order_intent
from market_platform_foundation.paper.execution import execute_order_intent, preview_interactive_order
from market_platform_foundation.paper.ledger import PaperExecutionLedger

LIVE_CAPTURE = ROOT / "evidence/market_data/moomoo/captured-aapl-live.jsonl"
LIVE_CAPTURE_FALLBACK = ROOT / "evidence/live-captures/p21-5164f0d08b.jsonl"


def _quote_record(
    *,
    instrument_id: str = "AAPL",
    available_ns: int = 200,
    event_ns: int = 100,
    last_price: float = 190.1,
    sequence: int = 1,
    extra_payload: dict | None = None,
) -> dict:
    payload = {
        "ask_price": last_price + 0.1,
        "ask_vol": 1,
        "bid_price": last_price - 0.1,
        "bid_vol": 1,
        "code": f"US.{instrument_id}",
        "last_price": last_price,
    }
    if extra_payload:
        payload.update(extra_payload)
    return {
        "capability": "US_EQUITY_L1",
        "clocks": {
            "event_time_ns": event_ns,
            "provider_time_ns": event_ns,
            "received_time_ns": available_ns,
        },
        "instrument_id": instrument_id,
        "provider": "moomoo",
        "provider_symbol": f"US.{instrument_id}",
        "raw_payload": payload,
        "sequence": sequence,
    }


def _admit(record: dict, *, wall_now_ns: int | None = None, **kwargs) -> dict:
    engine = LiveAdmissionEngine()
    received = int(record["clocks"]["received_time_ns"])
    return engine.evaluate_record(record, wall_now_ns=wall_now_ns if wall_now_ns is not None else received + 1_000_000, **kwargs)


def _authorized_ledger(instrument_id: str = "AAPL") -> PaperExecutionLedger:
    return PaperExecutionLedger.open_session(
        replay_session_id="p31",
        instrument_id=instrument_id,
        symbol=instrument_id,
        data_mode="LIVE_OBSERVATIONAL",
        data_provider="MOOMOO",
        execution_mode="INTERNAL_SIMULATION",
        execution_authority="PAPER_ONLY",
        execution_provider="INTERNAL",
    )


def _execute(ledger: PaperExecutionLedger, bars: list[dict], *, created_time: int, instrument_id: str = "AAPL"):
    intent = build_user_order_intent(
        instrument=build_instrument_ref(instrument_id=instrument_id, symbol=instrument_id),
        side="BUY",
        quantity=1,
        observation_time=created_time,
        client_order_id="p31",
        idempotency_key="p31",
    )
    return execute_order_intent(intent=intent, ledger=ledger, bars=bars)


class LiveExecutableBarTests(unittest.TestCase):
    def test_live_admitted_event_becomes_executable_bar(self) -> None:
        buffer = LiveExecutionEventBuffer()
        result = _admit(_quote_record(available_ns=200, sequence=1))
        self.assertEqual(result["admission"]["execution"], ADMISSION_EXECUTION)
        self.assertTrue(buffer.append_admitted(result, provider_generation=1))
        bars = buffer.bars_for_execution(observation_time_ns=200, price_scale=100, instrument_id="AAPL")
        self.assertEqual(len(bars), 1)
        bar = bars[0]
        self.assertEqual(bar["bar_payload"]["timeframe"], LIVE_L1_TIMEFRAME)
        self.assertEqual(bar["source"], "LIVE_L1_SNAPSHOT")
        self.assertEqual(bar["volume_basis"], "SIMULATION_POLICY")
        self.assertEqual(bar["available_time"], 200)
        self.assertEqual(bar["event_time"], 100)
        self.assertIn("open", bar["bar_payload"])
        self.assertIn("high", bar["bar_payload"])
        self.assertIn("low", bar["bar_payload"])
        self.assertIn("close", bar["bar_payload"])
        self.assertEqual(bar["volume"], 100)

    def test_pre_intent_event_not_executable(self) -> None:
        buffer = LiveExecutionEventBuffer()
        buffer.append_admitted(_admit(_quote_record(available_ns=100, sequence=1)), provider_generation=1)
        buffer.append_admitted(
            _admit(_quote_record(available_ns=200, sequence=2, last_price=190.2)),
            provider_generation=1,
        )
        created = 250
        bars = buffer.bars_for_execution(observation_time_ns=created, price_scale=100, instrument_id="AAPL")
        self.assertTrue(bars)
        self.assertFalse(buffer.bars_after_intent(created_time_ns=created, observation_time_ns=created, instrument_id="AAPL"))
        ledger = _authorized_ledger()
        decision, order, fill = _execute(ledger, bars, created_time=created)
        self.assertEqual(decision["decision"], "APPROVE")
        self.assertIsNone(fill)
        self.assertEqual(order["state"], "REJECTED")
        self.assertIn("SIM_NO_POST_SIGNAL_BAR", order["reason_codes"])
        preview = preview_interactive_order(
            ledger=ledger,
            bars=bars,
            symbol="AAPL",
            instrument_id="AAPL",
            side="BUY",
            quantity=1,
            observation_time=created,
            client_order_id="pre",
            idempotency_key="pre",
        )
        self.assertEqual(preview["quality_state"], "WAITING_FOR_ELIGIBLE_LIVE_EVENT")

    def test_post_intent_event_executable(self) -> None:
        buffer = LiveExecutionEventBuffer()
        buffer.append_admitted(_admit(_quote_record(available_ns=100, sequence=1)), provider_generation=1)
        buffer.append_admitted(
            _admit(_quote_record(available_ns=300, sequence=2, last_price=191.0)),
            provider_generation=1,
        )
        created = 200
        bars = buffer.bars_for_execution(observation_time_ns=400, price_scale=100, instrument_id="AAPL")
        post = buffer.bars_after_intent(
            created_time_ns=created,
            observation_time_ns=400,
            price_scale=100,
            instrument_id="AAPL",
        )
        self.assertEqual(len(post), 1)
        self.assertEqual(post[0]["available_time"], 300)
        ledger = _authorized_ledger()
        decision, order, fill = _execute(ledger, bars, created_time=created)
        self.assertEqual(decision["decision"], "APPROVE")
        self.assertIsNotNone(fill)
        self.assertEqual(order["state"], "FILLED")
        self.assertEqual(fill["fill_time"], 300)

    def test_wrong_symbol_not_executable(self) -> None:
        buffer = LiveExecutionEventBuffer()
        buffer.append_admitted(_admit(_quote_record(instrument_id="AAPL", available_ns=200)), provider_generation=1)
        biya = buffer.bars_for_execution(observation_time_ns=500, price_scale=100, instrument_id="BIYA")
        self.assertEqual(biya, [])
        ledger = _authorized_ledger("BIYA")
        decision, order, fill = _execute(ledger, biya, created_time=100, instrument_id="BIYA")
        self.assertEqual(decision["decision"], "APPROVE")
        self.assertIsNone(fill)
        self.assertEqual(order["state"], "REJECTED")

    def test_stale_event_not_executable(self) -> None:
        buffer = LiveExecutionEventBuffer()
        record = _quote_record(available_ns=200, sequence=1)
        stale = _admit(record, wall_now_ns=200 + 30_000_000_000)
        self.assertEqual(stale["admission"]["execution"], ADMISSION_BLOCKED)
        self.assertFalse(buffer.append_admitted(stale, provider_generation=1))
        bars = buffer.bars_for_execution(observation_time_ns=200 + 30_000_000_000, price_scale=100, instrument_id="AAPL")
        self.assertEqual(bars, [])

    def test_previous_generation_not_executable(self) -> None:
        buffer = LiveExecutionEventBuffer()
        result = _admit(_quote_record(available_ns=200, sequence=1))
        self.assertTrue(buffer.append_admitted(result, provider_generation=1))
        self.assertTrue(buffer.bars_for_execution(observation_time_ns=200, instrument_id="AAPL"))
        buffer.provider_generation = 2
        bars = buffer.bars_for_execution(observation_time_ns=200, instrument_id="AAPL")
        self.assertEqual(bars, [])
        ledger = _authorized_ledger()
        _decision, order, fill = _execute(ledger, bars, created_time=100)
        self.assertIsNone(fill)
        self.assertEqual(order["state"], "REJECTED")


class CaptureReplayAvailabilityTests(unittest.TestCase):
    def _capture_path(self) -> Path:
        if LIVE_CAPTURE.is_file():
            return LIVE_CAPTURE
        return LIVE_CAPTURE_FALLBACK

    @unittest.skipUnless(LIVE_CAPTURE.is_file() or LIVE_CAPTURE_FALLBACK.is_file(), "live capture missing")
    def test_capture_replay_intent_uses_post_intent_l1_only(self) -> None:
        path = self._capture_path()
        runtime = LiveObservationalRuntime()
        first_push_seen: set[str] = set()
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            clocks = record.get("clocks") if isinstance(record.get("clocks"), dict) else {}
            received = int(clocks.get("received_time_ns") or 0)
            channel = f"{record.get('instrument_id')}:{record.get('capability')}"
            is_first = channel not in first_push_seen
            if is_first:
                first_push_seen.add(channel)
            runtime.ingest_record(
                record,
                is_first_push=is_first,
                is_cached=bool(record.get("raw_payload", {}).get("push_data_type") == "CACHE"),
                wall_now_ns=received + 1_000_000,
            )
        times = [
            row.available_time_ns
            for row in runtime.execution_buffer.events_by_instrument.get("AAPL", ())
            if "L1" in row.capability
        ]
        self.assertGreaterEqual(len(times), 2, "need pre and post intent L1 evidence")
        times = sorted(times)
        created = times[len(times) // 2]
        horizon = times[-1]
        self.assertTrue(any(t <= created for t in times))
        self.assertTrue(any(t > created for t in times))
        bars = runtime.execution_buffer.bars_for_execution(
            observation_time_ns=horizon,
            price_scale=100,
            instrument_id="AAPL",
        )
        pre_only = [bar for bar in bars if int(bar["available_time"]) <= created]
        self.assertTrue(pre_only)
        ledger = _authorized_ledger()
        _decision, order_pre, fill_pre = _execute(ledger, pre_only, created_time=created)
        self.assertIsNone(fill_pre)
        self.assertEqual(order_pre["state"], "REJECTED")
        decision, order, fill = _execute(ledger, bars, created_time=created)
        self.assertEqual(decision["decision"], "APPROVE")
        self.assertIsNotNone(fill)
        self.assertEqual(order["state"], "FILLED")
        self.assertGreater(int(fill["fill_time"]), created)


class ActiveOperatorInstrumentTests(unittest.TestCase):
    def setUp(self) -> None:
        import os
        import tempfile

        from market_platform_foundation.local_state.startup import reset_local_state_for_tests

        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ["IMP_STATE_DIR"] = self._tmp.name
        os.environ["IMP_PERSIST_STATE"] = "1"
        os.environ.pop("IMP_LIVE_OBSERVATIONAL", None)
        os.environ.pop("IMP_MOOMOO_LIVE", None)
        os.environ.pop("IMP_PAPER_EXECUTION", None)
        reset_local_state_for_tests()

    def tearDown(self) -> None:
        import os

        from market_platform_foundation.local_state.startup import reset_local_state_for_tests

        reset_local_state_for_tests()
        os.environ.pop("IMP_STATE_DIR", None)
        os.environ.pop("IMP_PERSIST_STATE", None)
        os.environ.pop("IMP_LIVE_OBSERVATIONAL", None)
        os.environ.pop("IMP_MOOMOO_LIVE", None)
        os.environ.pop("IMP_PAPER_EXECUTION", None)
        os.environ.pop("IMP_LIVE_INTERNAL_SIMULATION", None)
        self._tmp.cleanup()

    def _store(self):
        from market_platform_foundation.ui_api.store import ReplayStore

        store = ReplayStore(collection_root=ROOT.parent)
        store.load()
        return store

    def test_workspace_symbol_becomes_ticket_symbol(self) -> None:
        from market_platform_foundation.local_state.startup import open_local_state
        from market_platform_foundation.ui_api.operator_instrument import (
            SOURCE_WORKSPACE,
            resolve_active_operator_instrument,
        )
        from market_platform_foundation.ui_api.paper_projections import preview_paper_order

        repo = open_local_state(force=True)
        assert repo is not None
        repo.save_workspace({"selected_instrument": "AAPL", "open_panels": ["live-market"]})
        store = self._store()
        instrument, source = resolve_active_operator_instrument(store)
        self.assertEqual(instrument, "AAPL")
        self.assertEqual(source, SOURCE_WORKSPACE)
        preview = preview_paper_order(
            store,
            {"side": "BUY", "quantity": 1, "client_order_id": "p31-ws", "idempotency_key": "p31-ws"},
        )
        self.assertEqual(preview["preview"]["instrument"]["instrument_id"], "AAPL")
        self.assertEqual(preview["preview"]["intent"]["instrument_id"], "AAPL")

    def test_live_mode_does_not_fallback_to_biya(self) -> None:
        import os

        from market_platform_foundation.ui_api.operator_instrument import (
            SOURCE_NONE,
            resolve_active_operator_instrument,
        )
        from market_platform_foundation.ui_api.paper_projections import preview_paper_order

        os.environ["IMP_LIVE_OBSERVATIONAL"] = "1"
        store = self._store()
        instrument, source = resolve_active_operator_instrument(store)
        self.assertIsNone(instrument)
        self.assertEqual(source, SOURCE_NONE)
        self.assertNotEqual(instrument, store.instrument_id)
        with self.assertRaises(ValueError) as raised:
            preview_paper_order(
                store,
                {"side": "BUY", "quantity": 1, "client_order_id": "p31-live", "idempotency_key": "p31-live"},
            )
        self.assertEqual(str(raised.exception), "OPERATOR_INSTRUMENT_REQUIRED")

    def test_explicit_ticket_symbol_wins(self) -> None:
        from market_platform_foundation.local_state.startup import open_local_state
        from market_platform_foundation.ui_api.operator_instrument import (
            SOURCE_ORDER_TICKET,
            resolve_active_operator_instrument,
        )
        from market_platform_foundation.ui_api.paper_projections import (
            open_paper_session,
            preview_paper_order,
            submit_paper_order,
        )

        repo = open_local_state(force=True)
        assert repo is not None
        repo.save_workspace({"selected_instrument": "NVDA"})
        store = self._store()
        instrument, source = resolve_active_operator_instrument(store, explicit="AAPL")
        self.assertEqual(instrument, "AAPL")
        self.assertEqual(source, SOURCE_ORDER_TICKET)
        preview = preview_paper_order(
            store,
            {
                "side": "BUY",
                "quantity": 1,
                "instrument_id": "AAPL",
                "client_order_id": "p31-explicit",
                "idempotency_key": "p31-explicit",
            },
        )
        self.assertEqual(preview["preview"]["intent"]["instrument_id"], "AAPL")
        repo.save_workspace({"selected_instrument": "NVDA", "open_panels": ["live-market"]})
        import os

        os.environ["IMP_PAPER_EXECUTION"] = "1"
        open_paper_session(store, {"execution_mode": "INTERNAL_SIMULATION"})
        submitted = submit_paper_order(
            store,
            {
                "side": "BUY",
                "quantity": 1,
                "instrument_id": preview["preview"]["intent"]["instrument_id"],
                "client_order_id": "p31-explicit-sub",
                "idempotency_key": "p31-explicit-sub",
            },
        )
        self.assertEqual(submitted["submission"]["order"]["instrument_id"], "AAPL")
        self.assertNotEqual(submitted["submission"]["order"]["instrument_id"], "NVDA")

    def test_active_symbol_survives_restart(self) -> None:
        import os

        from market_platform_foundation.local_state.startup import open_local_state, reset_local_state_for_tests
        from market_platform_foundation.ui_api.operator_instrument import (
            SOURCE_WORKSPACE,
            resolve_active_operator_instrument,
        )

        repo = open_local_state(force=True)
        assert repo is not None
        saved = repo.save_workspace(
            {
                "selected_instrument": "AAPL",
                "open_panels": ["live-market"],
                "execution_authority": "should-not-persist",
                "eligible": True,
            }
        )
        self.assertEqual(saved["layout"]["selected_instrument"], "AAPL")
        self.assertNotIn("execution_authority", saved["layout"])
        self.assertNotIn("eligible", saved["layout"])
        state_dir = os.environ["IMP_STATE_DIR"]
        reset_local_state_for_tests()
        os.environ["IMP_STATE_DIR"] = state_dir
        os.environ["IMP_PERSIST_STATE"] = "1"
        restored = open_local_state(force=True)
        assert restored is not None
        store = self._store()
        instrument, source = resolve_active_operator_instrument(store)
        self.assertEqual(instrument, "AAPL")
        self.assertEqual(source, SOURCE_WORKSPACE)
        layout = restored.load_active_workspace()["layout"]
        self.assertEqual(layout["selected_instrument"], "AAPL")
        self.assertNotIn("eligible", layout)

    def test_live_internal_paper_reachable_from_env_flags(self) -> None:
        import os

        from market_platform_foundation.ui_api.live_projections import resolve_live_operating_modes

        os.environ["IMP_LIVE_OBSERVATIONAL"] = "1"
        os.environ["IMP_MOOMOO_LIVE"] = "1"
        os.environ["IMP_PAPER_EXECUTION"] = "1"
        os.environ["IMP_LIVE_INTERNAL_SIMULATION"] = "1"
        store = self._store()
        store.execution_deferred = False
        data_mode, execution_mode, data_provider, authority = resolve_live_operating_modes(store)
        self.assertEqual(data_mode, "LIVE_OBSERVATIONAL")
        self.assertEqual(execution_mode, "INTERNAL_SIMULATION")
        self.assertEqual(data_provider, "MOOMOO")
        self.assertEqual(authority, "PAPER_ONLY")
        store.execution_deferred = True
        store.paper_ledger.execution_mode = "INTERNAL_SIMULATION"
        _mode, _exec, _provider, deferred_authority = resolve_live_operating_modes(store)
        self.assertEqual(deferred_authority, "BLOCKED")


class LivePaperRestartTests(unittest.TestCase):
    def setUp(self) -> None:
        import os
        import tempfile

        from market_platform_foundation.local_state.startup import reset_local_state_for_tests

        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ["IMP_STATE_DIR"] = self._tmp.name
        os.environ["IMP_PERSIST_STATE"] = "1"
        os.environ["IMP_PAPER_EXECUTION"] = "1"
        os.environ.pop("IMP_LIVE_OBSERVATIONAL", None)
        reset_local_state_for_tests()

    def tearDown(self) -> None:
        import os

        from market_platform_foundation.local_state.startup import reset_local_state_for_tests
        from market_platform_foundation.market_data.live_runtime import reset_live_runtime

        reset_live_runtime()
        reset_local_state_for_tests()
        os.environ.pop("IMP_STATE_DIR", None)
        os.environ.pop("IMP_PERSIST_STATE", None)
        os.environ.pop("IMP_PAPER_EXECUTION", None)
        os.environ.pop("IMP_LIVE_OBSERVATIONAL", None)
        os.environ.pop("IMP_MOOMOO_LIVE", None)
        os.environ.pop("IMP_LIVE_INTERNAL_SIMULATION", None)
        self._tmp.cleanup()

    def _filled_live_ledger(self):
        from market_platform_foundation.local_state.startup import persist_ledger
        from market_platform_foundation.paper.execution import submit_interactive_order

        buffer = LiveExecutionEventBuffer()
        buffer.append_admitted(_admit(_quote_record(available_ns=100, sequence=1)), provider_generation=1)
        buffer.append_admitted(
            _admit(_quote_record(available_ns=300, sequence=2, last_price=191.0)),
            provider_generation=1,
        )
        created = 200
        bars = buffer.bars_for_execution(observation_time_ns=400, price_scale=100, instrument_id="AAPL")
        ledger = _authorized_ledger()
        ledger.apply_live_mark(mark_minor=19100, mark_provider="MOOMOO", mark_as_of_ns=300, mark_quality="PASS")
        result = submit_interactive_order(
            ledger=ledger,
            bars=bars,
            symbol="AAPL",
            instrument_id="AAPL",
            side="BUY",
            quantity=1,
            observation_time=created,
            client_order_id="p31",
            idempotency_key="p31",
        )
        persist_ledger(ledger)
        return ledger, result["order"], result["fill"], result["decision"]

    def test_live_fill_survives_restart(self) -> None:
        import os

        from market_platform_foundation.local_state.startup import (
            ledger_from_session,
            open_local_state,
            reset_local_state_for_tests,
        )

        ledger, order, fill, _decision = self._filled_live_ledger()
        self.assertEqual(order["state"], "FILLED")
        self.assertIsNotNone(fill)
        session_id = ledger.session_id
        fill_count = len(ledger.project_fills())
        state_dir = os.environ["IMP_STATE_DIR"]
        reset_local_state_for_tests()
        os.environ["IMP_STATE_DIR"] = state_dir
        os.environ["IMP_PERSIST_STATE"] = "1"
        repo = open_local_state(force=True)
        assert repo is not None
        restored = ledger_from_session(
            repo.load_session(session_id),
            repo.load_events(session_id),
            repo.load_idempotency(session_id),
        )
        self.assertEqual(len(restored.project_fills()), fill_count)
        self.assertEqual(restored.project_orders()[0]["order_id"], order["order_id"])
        self.assertEqual(restored.project_fills()[0]["fill_id"], fill["fill_id"])
        self.assertEqual(restored.execution_provider, "INTERNAL")
        self.assertEqual(restored.data_provider, "MOOMOO")

    def test_live_fill_idempotency_survives_restart(self) -> None:
        import os

        from market_platform_foundation.local_state.startup import (
            ledger_from_session,
            open_local_state,
            reset_local_state_for_tests,
        )
        from market_platform_foundation.paper.execution import submit_interactive_order

        ledger, order, _fill, _decision = self._filled_live_ledger()
        session_id = ledger.session_id
        fill_count = len(ledger.project_fills())
        state_dir = os.environ["IMP_STATE_DIR"]
        reset_local_state_for_tests()
        os.environ["IMP_STATE_DIR"] = state_dir
        os.environ["IMP_PERSIST_STATE"] = "1"
        repo = open_local_state(force=True)
        assert repo is not None
        restored = ledger_from_session(
            repo.load_session(session_id),
            repo.load_events(session_id),
            repo.load_idempotency(session_id),
        )
        restored.execution_authority = "PAPER_ONLY"
        restored.execution_mode = "INTERNAL_SIMULATION"
        second = submit_interactive_order(
            ledger=restored,
            bars=[],
            symbol="AAPL",
            instrument_id="AAPL",
            side="BUY",
            quantity=1,
            observation_time=200,
            client_order_id="p31",
            idempotency_key="p31",
        )
        self.assertTrue(second["duplicate"])
        self.assertEqual(second["order_id"], order["order_id"])
        self.assertEqual(len(restored.project_fills()), fill_count)

    def test_restored_mark_not_fresh(self) -> None:
        import os

        from market_platform_foundation.local_state.startup import (
            ledger_from_session,
            open_local_state,
            reset_local_state_for_tests,
        )

        ledger, _order, _fill, _decision = self._filled_live_ledger()
        session_id = ledger.session_id
        state_dir = os.environ["IMP_STATE_DIR"]
        reset_local_state_for_tests()
        os.environ["IMP_STATE_DIR"] = state_dir
        os.environ["IMP_PERSIST_STATE"] = "1"
        repo = open_local_state(force=True)
        assert repo is not None
        restored = ledger_from_session(
            repo.load_session(session_id),
            repo.load_events(session_id),
            repo.load_idempotency(session_id),
        )
        positions = restored.project_positions()
        self.assertTrue(positions)
        self.assertEqual(positions[0]["mark_quality"], "RESTORED")
        self.assertNotEqual(positions[0]["mark_quality"], "PASS")
        self.assertEqual(positions[0]["mark_provider"], "MOOMOO")

    def test_restored_session_requires_fresh_live_health(self) -> None:
        import os
        from unittest import mock

        from market_platform_foundation.market_data.live_runtime import LiveObservationalRuntime, reset_live_runtime
        from market_platform_foundation.market_data.provider_lifecycle import ProviderConnectionState
        from market_platform_foundation.ui_api.paper_projections import submit_paper_order
        from market_platform_foundation.ui_api.store import ReplayStore

        os.environ["IMP_LIVE_OBSERVATIONAL"] = "1"
        os.environ["IMP_MOOMOO_LIVE"] = "1"
        os.environ["IMP_LIVE_INTERNAL_SIMULATION"] = "1"
        reset_live_runtime()
        runtime = LiveObservationalRuntime()
        runtime.lifecycle.connection_state = ProviderConnectionState.CONNECTED
        store = ReplayStore(collection_root=ROOT.parent)
        store.load()
        store.data_mode = "LIVE_OBSERVATIONAL"
        store.paper_ledger.data_mode = "LIVE_OBSERVATIONAL"
        store.paper_ledger.execution_mode = "INTERNAL_SIMULATION"
        store.paper_ledger.execution_authority = "BLOCKED"
        store.execution_deferred = True
        with mock.patch(
            "market_platform_foundation.market_data.live_runtime.get_live_runtime",
            return_value=runtime,
        ):
            with self.assertRaises(ValueError) as raised:
                submit_paper_order(
                    store,
                    {
                        "side": "BUY",
                        "quantity": 1,
                        "instrument_id": "AAPL",
                        "client_order_id": "p31-restored",
                        "idempotency_key": "p31-restored",
                    },
                )
        self.assertEqual(str(raised.exception), "RESTORED_SESSION_AWAITING_FRESH_LIVE_HEALTH")


class LiveAdversarialAndSafetyTests(unittest.TestCase):
    def test_empty_buffer_not_executable(self) -> None:
        buffer = LiveExecutionEventBuffer()
        bars = buffer.bars_for_execution(observation_time_ns=500, instrument_id="AAPL")
        self.assertEqual(bars, [])
        ledger = _authorized_ledger()
        _decision, order, fill = _execute(ledger, bars, created_time=100)
        self.assertIsNone(fill)
        self.assertEqual(order["state"], "REJECTED")

    def test_reconnect_cached_not_executable(self) -> None:
        buffer = LiveExecutionEventBuffer()
        result = _admit(_quote_record(available_ns=200, sequence=1), is_cached=True, is_first_push=True)
        self.assertNotEqual(result["admission"]["execution"], "EXECUTION_ADMITTED")
        self.assertFalse(buffer.append_admitted(result, provider_generation=1))

    def test_buffer_rollover_drops_oldest(self) -> None:
        buffer = LiveExecutionEventBuffer(max_events=2)
        buffer.append_admitted(_admit(_quote_record(available_ns=100, sequence=1)), provider_generation=1)
        buffer.append_admitted(_admit(_quote_record(available_ns=200, sequence=2, last_price=190.2)), provider_generation=1)
        buffer.append_admitted(_admit(_quote_record(available_ns=300, sequence=3, last_price=190.3)), provider_generation=1)
        bars = buffer.bars_for_execution(observation_time_ns=400, instrument_id="AAPL")
        times = [int(bar["available_time"]) for bar in bars]
        self.assertNotIn(100, times)
        self.assertEqual(times, [200, 300])

    def test_intent_on_boundary_not_filled(self) -> None:
        buffer = LiveExecutionEventBuffer()
        buffer.append_admitted(_admit(_quote_record(available_ns=200, sequence=1)), provider_generation=1)
        created = 200
        bars = buffer.bars_for_execution(observation_time_ns=200, instrument_id="AAPL")
        ledger = _authorized_ledger()
        _decision, order, fill = _execute(ledger, bars, created_time=created)
        self.assertIsNone(fill)
        self.assertEqual(order["state"], "REJECTED")

    def test_preview_cannot_create_fill(self) -> None:
        buffer = LiveExecutionEventBuffer()
        buffer.append_admitted(_admit(_quote_record(available_ns=100, sequence=1)), provider_generation=1)
        buffer.append_admitted(_admit(_quote_record(available_ns=300, sequence=2, last_price=191.0)), provider_generation=1)
        ledger = _authorized_ledger()
        preview = preview_interactive_order(
            ledger=ledger,
            bars=buffer.bars_for_execution(observation_time_ns=400, instrument_id="AAPL"),
            symbol="AAPL",
            instrument_id="AAPL",
            side="BUY",
            quantity=1,
            observation_time=200,
            client_order_id="preview-only",
            idempotency_key="preview-only",
        )
        self.assertIsNotNone(preview.get("fill_preview"))
        self.assertEqual(ledger.project_fills(), [])
        self.assertEqual(ledger.project_orders(), [])

    def test_submit_after_workspace_symbol_change_uses_ticket(self) -> None:
        import os
        import tempfile

        from market_platform_foundation.local_state.startup import open_local_state, reset_local_state_for_tests
        from market_platform_foundation.ui_api.paper_projections import preview_paper_order
        from market_platform_foundation.ui_api.store import ReplayStore

        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ["IMP_STATE_DIR"] = tmp.name
        os.environ["IMP_PERSIST_STATE"] = "1"
        os.environ.pop("IMP_LIVE_OBSERVATIONAL", None)
        reset_local_state_for_tests()
        try:
            repo = open_local_state(force=True)
            assert repo is not None
            repo.save_workspace({"selected_instrument": "NVDA"})
            store = ReplayStore(collection_root=ROOT.parent)
            store.load()
            preview = preview_paper_order(
                store,
                {
                    "side": "BUY",
                    "quantity": 1,
                    "instrument_id": "AAPL",
                    "client_order_id": "p31-switch",
                    "idempotency_key": "p31-switch",
                },
            )
            self.assertEqual(preview["preview"]["intent"]["instrument_id"], "AAPL")
            repo.save_workspace({"selected_instrument": "MSFT"})
            self.assertEqual(preview["preview"]["intent"]["instrument_id"], "AAPL")
        finally:
            reset_local_state_for_tests()
            os.environ.pop("IMP_STATE_DIR", None)
            os.environ.pop("IMP_PERSIST_STATE", None)
            tmp.cleanup()

    def test_live_internal_execution_never_calls_moomoo_trade_api(self) -> None:
        import ast

        forbidden = (
            "OpenTradeContext",
            "OpenUSTradeContext",
            "OpenHKTradeContext",
            "OpenSecTradeContext",
            "OpenCryptoTradeContext",
            "unlock_trade",
            "place_order",
            "modify_order",
        )
        paths = [
            ROOT / "src/market_platform_foundation/paper/execution.py",
            ROOT / "src/market_platform_foundation/ui_api/paper_projections.py",
            ROOT / "src/market_platform_foundation/ui_api/live_projections.py",
            ROOT / "src/market_platform_foundation/market_data/live_runtime.py",
        ]
        for path in paths:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
            imported = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        if alias.name in forbidden:
                            imported.append(alias.name)
                if isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Attribute) and func.attr in forbidden:
                        imported.append(func.attr)
                    if isinstance(func, ast.Name) and func.id in forbidden:
                        imported.append(func.id)
            self.assertEqual(imported, [], msg=str(path))
            self.assertNotIn("OpenTradeContext", source)

    def test_moomoo_live_does_not_authorize_broker_execution(self) -> None:
        import os

        from market_platform_foundation.operating_modes import resolve_execution_authority

        os.environ["IMP_MOOMOO_LIVE"] = "1"
        os.environ.pop("IMP_LIVE_EXECUTION", None)
        os.environ.pop("IMP_PAPER_EXECUTION", None)
        try:
            self.assertEqual(resolve_execution_authority(requested_mode="LIVE"), "BLOCKED")
            self.assertEqual(resolve_execution_authority(requested_mode="INTERNAL_SIMULATION"), "BLOCKED")
        finally:
            os.environ.pop("IMP_MOOMOO_LIVE", None)


class P31LiveOperatorVerticalSliceTests(unittest.TestCase):
    @unittest.skipUnless(LIVE_CAPTURE.is_file() or LIVE_CAPTURE_FALLBACK.is_file(), "live capture missing")
    def test_p31_live_operator_vertical_slice(self) -> None:
        path = LIVE_CAPTURE if LIVE_CAPTURE.is_file() else LIVE_CAPTURE_FALLBACK
        runtime = LiveObservationalRuntime()
        first_push_seen: set[str] = set()
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            clocks = record.get("clocks") if isinstance(record.get("clocks"), dict) else {}
            received = int(clocks.get("received_time_ns") or 0)
            channel = f"{record.get('instrument_id')}:{record.get('capability')}"
            is_first = channel not in first_push_seen
            if is_first:
                first_push_seen.add(channel)
            runtime.ingest_record(
                record,
                is_first_push=is_first,
                is_cached=bool(record.get("raw_payload", {}).get("push_data_type") == "CACHE"),
                wall_now_ns=received + 1_000_000,
            )
        times = sorted(
            row.available_time_ns
            for row in runtime.execution_buffer.events_by_instrument.get("AAPL", ())
            if "L1" in row.capability
        )
        self.assertGreaterEqual(len(times), 2)
        created = times[len(times) // 2]
        horizon = times[-1]
        bars = runtime.execution_buffer.bars_for_execution(
            observation_time_ns=horizon,
            price_scale=100,
            instrument_id="AAPL",
        )
        ledger = _authorized_ledger()
        preview = preview_interactive_order(
            ledger=ledger,
            bars=bars,
            symbol="AAPL",
            instrument_id="AAPL",
            side="BUY",
            quantity=1,
            observation_time=created,
            client_order_id="p31-slice-pre",
            idempotency_key="p31-slice-pre",
        )
        self.assertEqual(ledger.project_fills(), [])
        self.assertIn(preview["data_provider"], {"MOOMOO", "moomoo"})
        self.assertEqual(preview["execution_provider"], "INTERNAL")
        decision, order, fill = _execute(ledger, bars, created_time=created)
        self.assertEqual(decision["decision"], "APPROVE")
        self.assertEqual(order["state"], "FILLED")
        self.assertIsNotNone(fill)
        self.assertGreater(int(fill["fill_time"]), created)
        self.assertEqual(ledger.data_provider, "MOOMOO")
        self.assertEqual(ledger.execution_provider, "INTERNAL")
        trace = ledger.project_execution_trace(order_id=order["order_id"])
        self.assertFalse(trace["broker_order_submitted"])
        self.assertEqual(trace["execution_provider"], "INTERNAL")
        self.assertEqual(trace["market_data_provider"], "MOOMOO")


if __name__ == "__main__":
    unittest.main()
