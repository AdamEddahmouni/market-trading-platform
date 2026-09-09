"""G9 performance smoke — adapter overhead on fake/replay path."""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "providers"))

from market_platform_foundation.providers.ibkr_observational.constants import TICK_ASK, TICK_BID
from market_platform_foundation.providers.ibkr_observational.trades import (
    QuoteContext,
    classify_trade_print,
    facts_from_tick_by_tick_all_last,
)

from ibkr_observational_support import FakeLookup, connected_adapter, make_record


AAPL = make_record("AAPL")
ITERATIONS = 2000


class G9PerformanceTests(unittest.TestCase):
    def test_trade_normalization_overhead(self) -> None:
        facts = facts_from_tick_by_tick_all_last(
            instrument_id="AAPL",
            subscription_id="s",
            req_id=1,
            generation=1,
            price=101.0,
            size=1.0,
            source_time_ns=1,
            received_time_ns=2,
        )
        quote = QuoteContext(bid=100.0, ask=101.0, provider="IBKR", received_ns=1, quality="PASS")
        start = time.perf_counter()
        for _ in range(ITERATIONS):
            classify_trade_print(facts, quote=quote, provider="IBKR")
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.assertLess(elapsed_ms, 5000.0, "G9 classification smoke exceeded budget")

    def test_adapter_trade_callback_overhead(self) -> None:
        adapter, transport = connected_adapter(lookup=FakeLookup(AAPL))
        adapter.connect()
        l1 = adapter.subscribe_l1(instrument_id="AAPL")
        adapter.on_tick_price(l1.req_id, TICK_BID, 100.0)
        adapter.on_tick_price(l1.req_id, TICK_ASK, 101.0)
        sub = adapter.subscribe_trades(instrument_id="AAPL")
        start = time.perf_counter()
        for i in range(500):
            adapter.on_tick_by_tick_all_last(sub.req_id, 2, 101.0, 1.0, source_time_ns=i + 100)
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.assertLess(elapsed_ms, 5000.0, "G9 adapter trade callback smoke exceeded budget")


if __name__ == "__main__":
    unittest.main()
