"""G9 CVD integration for IBKR classified trade tape."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "providers"))

from market_platform_foundation.market_data.runtime_composition import build_replay_composition
from market_platform_foundation.providers.ibkr_observational.constants import TICK_ASK, TICK_BID
from market_platform_foundation.order_flow.contracts import AggressorSide, AggressorSource, ClassifiedTrade

from ibkr_observational_support import FakeLookup, FakeTransport, connected_adapter, make_record


AAPL = make_record("AAPL")


def _classified(
    *,
    side: AggressorSide,
    signed: float,
    source: AggressorSource,
    trade_id: str = "t1",
) -> ClassifiedTrade:
    return ClassifiedTrade(
        trade_id=trade_id,
        price=100.0,
        quantity=abs(signed),
        aggressor_side=side,
        signed_volume=signed,
        aggressor_source=source,
        classification_method="test",
        classification_confidence=1.0 if side is not AggressorSide.UNKNOWN else 0.0,
        trade_timestamp="1000",
        provider="IBKR",
    )


class G9IbkrCvdTests(unittest.TestCase):
    def setUp(self) -> None:
        self.composition = build_replay_composition(
            transport=FakeTransport(), lookup=FakeLookup(AAPL)
        )
        self.store = self.composition.store

    def test_native_buy_increments_cvd(self) -> None:
        self.store.apply_classified_trade(
            _classified(side=AggressorSide.BUY, signed=10.0, source=AggressorSource.EXCHANGE_NATIVE),
            instrument_id="AAPL",
        )
        cvd = self.composition.lanes.build_cvd_payload("AAPL")
        self.assertTrue(cvd.get("available"))
        self.assertGreater(float(cvd["cvd"]["session_cvd"]), 0)

    def test_native_sell_decrements_cvd(self) -> None:
        self.store.apply_classified_trade(
            _classified(side=AggressorSide.SELL, signed=-8.0, source=AggressorSource.EXCHANGE_NATIVE),
            instrument_id="AAPL",
        )
        cvd = self.composition.lanes.build_cvd_payload("AAPL")
        self.assertTrue(cvd.get("available"))
        self.assertLess(float(cvd["cvd"]["session_cvd"]), 0)

    def test_inferred_buy_increments(self) -> None:
        self.store.apply_classified_trade(
            _classified(side=AggressorSide.BUY, signed=3.0, source=AggressorSource.LEE_READY),
            instrument_id="AAPL",
        )
        cvd = self.composition.lanes.build_cvd_payload("AAPL")
        self.assertTrue(cvd.get("available"))

    def test_unknown_does_not_fabricate(self) -> None:
        self.store.apply_classified_trade(
            _classified(side=AggressorSide.UNKNOWN, signed=0.0, source=AggressorSource.UNKNOWN),
            instrument_id="AAPL",
        )
        cvd = self.composition.lanes.build_cvd_payload("AAPL")
        self.assertFalse(cvd.get("available"))

    def test_ibkr_adapter_inferred_path_end_to_end(self) -> None:
        adapter, transport = connected_adapter(store=self.store, lookup=FakeLookup(AAPL))
        l1 = adapter.subscribe_l1(instrument_id="AAPL")
        adapter.on_tick_price(l1.req_id, TICK_BID, 100.0)
        adapter.on_tick_price(l1.req_id, TICK_ASK, 101.0)
        trades = adapter.subscribe_trades(instrument_id="AAPL")
        adapter.on_tick_by_tick_all_last(trades.req_id, 2, 101.0, 5.0, source_time_ns=100)
        cvd = self.composition.lanes.build_cvd_payload("AAPL")
        self.assertTrue(cvd.get("available"))
        self.assertGreater(float(cvd["cvd"]["session_cvd"]), 0)

    def test_l1_only_does_not_move_cvd(self) -> None:
        adapter, transport = connected_adapter(store=self.store, lookup=FakeLookup(AAPL))
        l1 = adapter.subscribe_l1(instrument_id="AAPL")
        adapter.on_tick_price(l1.req_id, TICK_BID, 100.0)
        adapter.on_tick_price(l1.req_id, TICK_ASK, 101.0)
        cvd = self.composition.lanes.build_cvd_payload("AAPL")
        self.assertFalse(cvd.get("available"))

    def test_session_reset_semantics(self) -> None:
        self.store.apply_classified_trade(
            _classified(side=AggressorSide.BUY, signed=2.0, source=AggressorSource.LEE_READY, trade_id="a"),
            instrument_id="AAPL",
        )
        first = self.composition.lanes.build_cvd_payload("AAPL")
        second = self.composition.lanes.build_cvd_payload("AAPL", previous_anchor=first.get("anchor"))
        self.assertIsNotNone(second)

    def test_replay_same_trades_same_cvd(self) -> None:
        self.store.apply_classified_trade(
            _classified(side=AggressorSide.SELL, signed=-4.0, source=AggressorSource.LEE_READY),
            instrument_id="AAPL",
        )
        a = self.composition.lanes.build_cvd_payload("AAPL")
        b = self.composition.lanes.build_cvd_payload("AAPL")
        self.assertEqual(a.get("cvd"), b.get("cvd"))


if __name__ == "__main__":
    unittest.main()
