"""G8 CVD runtime tests — no L1 quote fabrication."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "providers"))

from market_platform_foundation.market_data.live_admission import LiveAdmissionEngine
from market_platform_foundation.market_data.runtime_composition import build_replay_composition
from market_platform_foundation.providers.ibkr_observational.constants import TICK_BID, TICK_ASK

from ibkr_observational_support import FakeLookup, FakeTransport, connected_adapter, make_record


AAPL = make_record("AAPL")


def _admit_trade(store, *, side: str = "BUY", quantity: float = 10) -> None:
    engine = LiveAdmissionEngine()
    record = {
        "capability": "US_EQUITY_TICKS",
        "clocks": {"event_time_ns": 1000, "provider_time_ns": 1000, "received_time_ns": 1100},
        "instrument_id": "AAPL",
        "provider": "IBKR",
        "provider_symbol": "US.AAPL",
        "raw_payload": {
            "price": 100.0,
            "volume": quantity,
            "ticker_direction": side,
            "sequence": 1,
        },
        "sequence": 1,
    }
    store.apply_admitted(engine.evaluate_record(record, wall_now_ns=1100))


class G8CvdRuntimeTests(unittest.TestCase):
    def test_l1_quote_does_not_create_fake_trade(self) -> None:
        composition = build_replay_composition(
            transport=FakeTransport(), lookup=FakeLookup(AAPL)
        )
        adapter, transport = connected_adapter(store=composition.store, lookup=FakeLookup(AAPL))
        adapter.subscribe_l1(instrument_id="AAPL")
        req_id = transport.mkt_data_requests[0][0]
        adapter.on_tick_price(req_id, TICK_BID, 100.0)
        adapter.on_tick_price(req_id, TICK_ASK, 101.0)
        trades = composition.store.trades_for("AAPL")
        self.assertEqual(trades, [])

    def test_quote_update_alone_does_not_move_cvd(self) -> None:
        composition = build_replay_composition(
            transport=FakeTransport(), lookup=FakeLookup(AAPL)
        )
        adapter, transport = connected_adapter(store=composition.store, lookup=FakeLookup(AAPL))
        adapter.subscribe_l1(instrument_id="AAPL")
        req_id = transport.mkt_data_requests[0][0]
        adapter.on_tick_price(req_id, TICK_BID, 100.0)
        cvd = composition.lanes.build_cvd_payload("AAPL")
        self.assertFalse(cvd.get("available"))
        self.assertEqual(cvd.get("reason"), "INSUFFICIENT_TRADE_CLASSIFICATION")

    def test_classified_trade_evidence_updates_cvd(self) -> None:
        composition = build_replay_composition(
            transport=FakeTransport(), lookup=FakeLookup(AAPL)
        )
        _admit_trade(composition.store)
        cvd = composition.lanes.build_cvd_payload("AAPL")
        self.assertTrue(cvd.get("available"))

    def test_session_reset_semantics_unchanged(self) -> None:
        composition = build_replay_composition(
            transport=FakeTransport(), lookup=FakeLookup(AAPL)
        )
        _admit_trade(composition.store)
        first = composition.lanes.build_cvd_payload("AAPL", previous_anchor=None)
        second = composition.lanes.build_cvd_payload("AAPL", previous_anchor=first.get("anchor"))
        self.assertIsNotNone(second)

    def test_replay_deterministic(self) -> None:
        composition = build_replay_composition(
            transport=FakeTransport(), lookup=FakeLookup(AAPL)
        )
        _admit_trade(composition.store, side="SELL", quantity=5)
        a = composition.lanes.build_cvd_payload("AAPL")
        b = composition.lanes.build_cvd_payload("AAPL")
        self.assertEqual(a.get("cvd_total"), b.get("cvd_total"))

    def test_provider_provenance_retained(self) -> None:
        composition = build_replay_composition(
            transport=FakeTransport(), lookup=FakeLookup(AAPL)
        )
        _admit_trade(composition.store, quantity=1)
        cvd = composition.lanes.build_cvd_payload("AAPL")
        self.assertEqual(cvd.get("provenance", {}).get("provider"), "IBKR")

    def test_missing_trade_capability_explicit(self) -> None:
        composition = build_replay_composition(
            transport=FakeTransport(), lookup=FakeLookup(AAPL)
        )
        cvd = composition.lanes.build_cvd_payload("AAPL")
        self.assertEqual(cvd.get("state"), "UNAVAILABLE")

    def test_bl_0304_trade_tape_closes_offline_path(self) -> None:
        """G9: IBKR tick-by-tick + L1 context produces classified CVD offline."""
        composition = build_replay_composition(
            transport=FakeTransport(), lookup=FakeLookup(AAPL)
        )
        adapter, transport = connected_adapter(store=composition.store, lookup=FakeLookup(AAPL))
        adapter.subscribe_l1(instrument_id="AAPL")
        l1_req = transport.mkt_data_requests[0][0]
        adapter.on_tick_price(l1_req, TICK_BID, 100.0)
        adapter.on_tick_price(l1_req, TICK_ASK, 101.0)
        adapter.subscribe_trades(instrument_id="AAPL")
        trade_req = transport.tick_by_tick_requests[0][0]
        adapter.on_tick_by_tick_all_last(trade_req, 2, 101.0, 10.0, source_time_ns=1000)
        cvd = composition.lanes.build_cvd_payload("AAPL")
        self.assertTrue(cvd.get("available"))


if __name__ == "__main__":
    unittest.main()
