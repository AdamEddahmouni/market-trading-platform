from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.market_data.bounded_queue import BoundedIngestQueue
from market_platform_foundation.market_data.capability_registry import VerifiedCapabilityRegistry
from market_platform_foundation.market_data.execution_event_buffer import LiveExecutionEventBuffer
from market_platform_foundation.market_data.internal_simulation_gate import evaluate_internal_simulation_gates
from market_platform_foundation.market_data.live_admission import ADMISSION_EXECUTION, LiveAdmissionEngine
from market_platform_foundation.market_data.live_runtime import LiveObservationalRuntime, reset_live_runtime

FIXTURE = ROOT / "tests/fixtures/market_data/moomoo/captured-aapl.jsonl"
LIVE_CAPTURE = ROOT / "evidence/market_data/moomoo/captured-aapl-live.jsonl"
PROBE = ROOT / "evidence/market_data/moomoo/capability-report.json"


class CapabilityRegistryTests(unittest.TestCase):
    def test_probe_report_loads_without_inferring_from_config(self) -> None:
        registry = VerifiedCapabilityRegistry.from_probe_file(PROBE, moomoo_configured=True)
        self.assertTrue(registry.capabilities)
        self.assertIsNotNone(registry.verified_at)
        l1 = registry.get("US_EQUITY_L1")
        self.assertIsNotNone(l1)

    def test_stale_probe_zeroes_entitlement(self) -> None:
        registry = VerifiedCapabilityRegistry.from_probe_file(PROBE, max_staleness_seconds=0)
        self.assertTrue(registry.is_stale)
        l1 = registry.get("US_EQUITY_L1")
        assert l1 is not None
        self.assertFalse(l1.account_entitled)


class BoundedQueueTests(unittest.TestCase):
    def test_overflow_is_explicit(self) -> None:
        queue: BoundedIngestQueue[dict[str, str]] = BoundedIngestQueue(max_size=2)
        self.assertTrue(queue.enqueue({"id": "1"}))
        self.assertTrue(queue.enqueue({"id": "2"}))
        self.assertFalse(queue.enqueue({"id": "3"}))
        metrics = queue.metrics()
        self.assertEqual(metrics["events_dropped"], 1)
        self.assertEqual(metrics["queue_overflows"], 1)


class ExecutionBufferTests(unittest.TestCase):
    def test_execution_buffer_uses_available_time(self) -> None:
        buffer = LiveExecutionEventBuffer()
        engine = LiveAdmissionEngine()
        record = {
            "capability": "US_EQUITY_L1",
            "clocks": {"event_time_ns": 100, "provider_time_ns": 100, "received_time_ns": 200},
            "instrument_id": "AAPL",
            "provider": "moomoo",
            "provider_symbol": "US.AAPL",
            "raw_payload": {"bid_price": 1, "ask_price": 2, "bid_vol": 1, "ask_vol": 1, "last_price": 1.5},
            "sequence": 1,
        }
        result = engine.evaluate_record(record, wall_now_ns=250)
        self.assertEqual(result["admission"]["execution"], ADMISSION_EXECUTION)
        buffer.append_admitted(result, provider_generation=1)
        bars = buffer.bars_for_execution(observation_time_ns=200, price_scale=4, instrument_id="AAPL")
        self.assertEqual(len(bars), 1)
        self.assertIn("bar_payload", bars[0])
        late = buffer.bars_for_execution(observation_time_ns=150, price_scale=4, instrument_id="AAPL")
        self.assertEqual(len(late), 0)


class InternalSimulationGateTests(unittest.TestCase):
    def test_gate_deferred_without_env(self) -> None:
        runtime = LiveObservationalRuntime()
        runtime.feed_fixture_path(FIXTURE)
        with mock.patch.dict(os.environ, {"IMP_PAPER_EXECUTION": "0", "IMP_LIVE_INTERNAL_SIMULATION": "0"}):
            gate = evaluate_internal_simulation_gates(runtime=runtime, probe_stale=False)
        self.assertEqual(gate.status, "DEFERRED_FOR_SAFETY")
        self.assertIn("PAPER_EXECUTION_GATE", gate.blocking)


class LiveCaptureReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_live_runtime()

    def tearDown(self) -> None:
        reset_live_runtime()

    @unittest.skipUnless(LIVE_CAPTURE.is_file(), "live capture fixture missing")
    def test_real_capture_replay_equivalence(self) -> None:
        runtime_a = LiveObservationalRuntime()
        runtime_b = LiveObservationalRuntime()
        count_a = runtime_a.feed_fixture_path(LIVE_CAPTURE)
        count_b = runtime_b.feed_fixture_path(LIVE_CAPTURE)
        self.assertEqual(count_a, count_b)
        self.assertGreater(count_a, 0)
        self.assertEqual(
            runtime_a.state.metrics["events_admitted"],
            runtime_b.state.metrics["events_admitted"],
        )


class LiveMarkTests(unittest.TestCase):
    def test_fixture_quote_produces_moomoo_mark(self) -> None:
        runtime = LiveObservationalRuntime()
        runtime.feed_fixture_path(FIXTURE)
        mark = runtime.live_mark_for("AAPL")
        self.assertIsNotNone(mark)
        assert mark is not None
        self.assertEqual(mark["mark_provider"], "MOOMOO")
        runtime.simulate_disconnect()
        stale = runtime.live_mark_for("AAPL")
        assert stale is not None
        self.assertEqual(stale["mark_quality"], "DISCONNECTED")

    def test_paper_unrealized_inherits_mark_quality(self) -> None:
        from market_platform_foundation.paper.ledger import PaperExecutionLedger

        ledger = PaperExecutionLedger.open_session(
            replay_session_id="live-mark",
            instrument_id="AAPL",
            symbol="AAPL",
            data_mode="LIVE_OBSERVATIONAL",
            data_provider="MOOMOO",
            execution_mode="INTERNAL_SIMULATION",
            execution_authority="PAPER_ONLY",
        )
        ledger._append = ledger._append  # keep type checkers quiet
        fill = {
            "fill_id": "f1",
            "order_id": "o1",
            "fill_quantity": 1,
            "fill_price_minor": 1901000,
            "direction": "long",
            "instrument_id": "AAPL",
        }
        ledger.append_fill(fill, order={"order_id": "o1"})
        ledger.apply_live_mark(
            mark_minor=1910000,
            mark_provider="MOOMOO",
            mark_as_of_ns=250,
            mark_quality="STALE",
        )
        positions = ledger.project_positions()
        self.assertEqual(positions[0]["mark_quality"], "STALE")
        self.assertEqual(positions[0]["average_fill_minor"], 1901000)
        self.assertNotEqual(positions[0]["mark_minor"], positions[0]["average_fill_minor"])


class MoomooSafetyRegressionTests(unittest.TestCase):
    def test_moomoo_modules_have_no_trade_context(self) -> None:
        from tools.moomoo.probe import FORBIDDEN_TRADE_NAMES

        modules = [
            ROOT / "src/market_platform_foundation/market_data/live_runtime.py",
            ROOT / "tools/moomoo/push_feed.py",
        ]
        for path in modules:
            source = path.read_text(encoding="utf-8")
            for name in FORBIDDEN_TRADE_NAMES:
                if name.startswith("Open") and "Trade" in name:
                    self.assertNotIn(name, source)

    def test_check_live_environment_reports_unreachable_opend(self) -> None:
        from tools.moomoo.check_live_environment import run_check

        report = run_check(host="127.0.0.1", port=59999)
        self.assertFalse(report["ready_for_live_observational"])
        self.assertIn(
            report.get("status"),
            {"PORT_UNREACHABLE", "OPEN_D_NOT_RUNNING", "OPEN_D_NOT_INSTALLED"},
        )


class ProviderNeutralityTests(unittest.TestCase):
    def test_live_state_payload_has_no_vendor_classes(self) -> None:
        runtime = LiveObservationalRuntime()
        runtime.feed_fixture_path(FIXTURE)
        quote = runtime.state.quote_for("AAPL")
        payload = quote.to_dict() if quote else {}
        forbidden = ("US.AAPL", "OpenQuoteContext", "StockQuoteHandlerBase")
        for token in forbidden:
            self.assertNotIn(token, str(payload))


if __name__ == "__main__":
    unittest.main()
