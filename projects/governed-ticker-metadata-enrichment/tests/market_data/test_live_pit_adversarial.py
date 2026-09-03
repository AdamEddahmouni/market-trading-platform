from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.market_data.live_admission import ADMISSION_BLOCKED, LiveAdmissionEngine
from market_platform_foundation.market_data.live_runtime import LiveObservationalRuntime, reset_live_runtime
from market_platform_foundation.market_data.observational_state import ObservationalStateStore
from market_platform_foundation.replay.lifecycle import check_tc001


class LivePitAdversarialTests(unittest.TestCase):
    def test_available_time_never_wall_clock_without_received(self) -> None:
        from market_platform_foundation.market_data.normalization import live_envelope_from_capture

        record = {
            "capability": "US_EQUITY_L1",
            "clocks": {"event_time_ns": 100, "provider_time_ns": 100, "received_time_ns": 200},
            "instrument_id": "AAPL",
            "provider": "moomoo",
            "provider_symbol": "US.AAPL",
            "raw_payload": {"bid_price": 1, "ask_price": 2, "bid_vol": 1, "ask_vol": 1, "last_price": 1.5},
            "sequence": 1,
        }
        envelope = live_envelope_from_capture(record)
        self.assertEqual(envelope["available_time"], 200)
        self.assertNotEqual(envelope["available_time"], time.time_ns())

    def test_late_event_excluded_by_tc001(self) -> None:
        early = {"available_time": 100, "normalized_event_id": "a"}
        late = {"available_time": 500, "normalized_event_id": "b"}
        visible = [early, late]
        decision_time = 300
        self.assertEqual(check_tc001(visible, decision_time)[0], "FAIL")

    def test_reconnect_cached_event_not_execution_admitted(self) -> None:
        engine = LiveAdmissionEngine()
        record = {
            "capability": "US_EQUITY_L1",
            "clocks": {"event_time_ns": 100, "provider_time_ns": 100, "received_time_ns": 900},
            "instrument_id": "NVDA",
            "provider": "moomoo",
            "provider_symbol": "US.NVDA",
            "raw_payload": {"bid_price": 100, "ask_price": 100.1, "bid_vol": 1, "ask_vol": 1, "last_price": 100.05},
            "sequence": 1,
        }
        engine.on_reconnect()
        result = engine.evaluate_record(record, wall_now_ns=900, is_cached=True)
        self.assertEqual(result["admission"]["execution"], ADMISSION_BLOCKED)

    def test_capture_replay_equivalence(self) -> None:
        fixture = ROOT / "tests/fixtures/market_data/moomoo/captured-aapl.jsonl"
        runtime_a = LiveObservationalRuntime()
        runtime_b = LiveObservationalRuntime()
        runtime_a.feed_fixture_path(fixture)
        runtime_b.feed_fixture_path(fixture)
        self.assertEqual(runtime_a.state.metrics["events_admitted"], runtime_b.state.metrics["events_admitted"])
        self.assertEqual(
            runtime_a.state.quote_for("AAPL").last_price if runtime_a.state.quote_for("AAPL") else None,
            runtime_b.state.quote_for("AAPL").last_price if runtime_b.state.quote_for("AAPL") else None,
        )

    def test_out_of_order_availability_preserved(self) -> None:
        store = ObservationalStateStore()
        engine = LiveAdmissionEngine()
        trade_b = {
            "capability": "US_EQUITY_TICKS",
            "clocks": {"event_time_ns": 200, "provider_time_ns": 200, "received_time_ns": 300},
            "instrument_id": "AAPL",
            "provider": "moomoo",
            "provider_symbol": "US.AAPL",
            "raw_payload": {"price": 1, "volume": 1, "ticker_direction": "BUY", "sequence": 10},
            "sequence": 10,
        }
        trade_a = {
            "capability": "US_EQUITY_TICKS",
            "clocks": {"event_time_ns": 100, "provider_time_ns": 100, "received_time_ns": 500},
            "instrument_id": "AAPL",
            "provider": "moomoo",
            "provider_symbol": "US.AAPL",
            "raw_payload": {"price": 1, "volume": 1, "ticker_direction": "SELL", "sequence": 11},
            "sequence": 11,
        }
        store.apply_admitted(engine.evaluate_record(trade_b, wall_now_ns=300))
        store.apply_admitted(engine.evaluate_record(trade_a, wall_now_ns=500))
        trades = store.trades_for("AAPL")
        self.assertEqual(len(trades), 2)
        self.assertLess(trades[0]["available_time_ns"], trades[1]["available_time_ns"])

    def tearDown(self) -> None:
        reset_live_runtime()


if __name__ == "__main__":
    unittest.main()
