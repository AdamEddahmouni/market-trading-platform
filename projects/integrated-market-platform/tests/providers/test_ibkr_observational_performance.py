"""IBKR adapter normalization performance tests (G6 §32).

Measures adapter normalization separately from the G5 book engine and records
representative throughput. Classification: ``ADAPTER_PERFORMANCE_MEASURED`` —
never ``PRODUCTION_IBKR_PROVEN``. Bounds are deliberately loose so the tests
stay deterministic on shared CI; the recorded numbers go to evidence.
"""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from market_platform_foundation.market_data.observational_state import (  # noqa: E402
    ObservationalStateStore,
)
from market_platform_foundation.providers.ibkr_observational.constants import (  # noqa: E402
    IB_OP_INSERT,
    IB_OP_UPDATE,
    IB_SIDE_ASK,
    IB_SIDE_BID,
    TICK_ASK,
    TICK_BID,
)
from market_platform_foundation.providers.ibkr_observational.contracts import (  # noqa: E402
    CapabilityKind,
)

from ibkr_observational_support import (  # noqa: E402
    FakeLookup,
    make_adapter,
    make_record,
)

AAPL = make_record("AAPL")

#: Callback batches per measurement (kept small so the suite stays fast).
N_CALLBACKS = 20_000


class AdapterPerformanceTests(unittest.TestCase):
    """Throughput of adapter normalization (not the book engine)."""

    def _l1_adapter(self):
        store = ObservationalStateStore()
        adapter, _ = make_adapter(live=True, store=store, lookup=FakeLookup(AAPL))
        adapter.connect()
        sub = adapter.subscribe_l1(instrument_id="AAPL")
        return adapter, store, sub

    def test_l1_callback_aggregation_throughput(self) -> None:
        adapter, _, sub = self._l1_adapter()
        started = time.perf_counter()
        for i in range(N_CALLBACKS):
            adapter.on_tick_price(sub.req_id, TICK_BID, 100.0 + i % 10, received_ns=1000 + i)
            adapter.on_tick_size(sub.req_id, TICK_ASK, 101.0 + i % 10, received_ns=1000 + i)
        elapsed = time.perf_counter() - started
        rate = (N_CALLBACKS * 2) / elapsed
        # Loose floor: far below any real machine's capability.
        self.assertGreater(rate, 1_000, f"L1 aggregation too slow: {rate:.0f}/s")
        self.assertGreater(rate, 10_000)

    def test_l2_callback_to_depth_update_throughput(self) -> None:
        adapter, _, sub = self._l1_adapter()
        # Reuse the adapter without store application: measure normalization.
        depth_adapter = make_adapter(live=True, store=None, lookup=FakeLookup(AAPL))[0]
        depth_adapter.connect()
        depth_sub = depth_adapter.subscribe_l2(instrument_id="AAPL")
        started = time.perf_counter()
        for i in range(N_CALLBACKS):
            depth_adapter.on_mkt_depth(
                depth_sub.req_id,
                i % 20,
                IB_OP_INSERT if i % 3 else IB_OP_UPDATE,
                IB_SIDE_BID if i % 2 else IB_SIDE_ASK,
                100.0 + (i % 50) / 10,
                float(1 + i % 100),
                received_ns=1000 + i,
            )
        elapsed = time.perf_counter() - started
        rate = N_CALLBACKS / elapsed
        self.assertGreater(rate, 1_000, f"L2 normalization too slow: {rate:.0f}/s")

    def test_l2_callback_to_canonical_book_apply_throughput(self) -> None:
        store = ObservationalStateStore()
        adapter, _ = make_adapter(live=True, store=store, lookup=FakeLookup(AAPL))
        adapter.connect()
        sub = adapter.subscribe_l2(instrument_id="AAPL")
        started = time.perf_counter()
        for i in range(N_CALLBACKS):
            adapter.on_mkt_depth(
                sub.req_id,
                i % 20,
                IB_OP_INSERT if i % 3 else IB_OP_UPDATE,
                IB_SIDE_BID if i % 2 else IB_SIDE_ASK,
                100.0 + (i % 50) / 10,
                float(1 + i % 100),
                received_ns=1000 + i,
            )
        elapsed = time.perf_counter() - started
        rate = N_CALLBACKS / elapsed
        self.assertGreater(rate, 1_000, f"L2→book apply too slow: {rate:.0f}/s")

    def test_throughput_at_depth_levels(self) -> None:
        """Measure at representative depths 10/50/60 (60 is the local ceiling)."""
        results: dict[int, float] = {}
        for depth in (10, 50, 60):
            store = ObservationalStateStore()
            adapter, _ = make_adapter(
                live=True, store=store, lookup=FakeLookup(AAPL), default_depth_levels=depth
            )
            adapter.connect()
            sub = adapter.subscribe_l2(instrument_id="AAPL")
            started = time.perf_counter()
            for i in range(N_CALLBACKS // 4):
                adapter.on_mkt_depth(
                    sub.req_id,
                    i % depth,
                    IB_OP_INSERT if i % 3 else IB_OP_UPDATE,
                    IB_SIDE_BID if i % 2 else IB_SIDE_ASK,
                    100.0 + (i % depth) / 10,
                    float(1 + i % 100),
                    received_ns=1000 + i,
                )
            elapsed = time.perf_counter() - started
            results[depth] = (N_CALLBACKS // 4) / elapsed
        for depth, rate in results.items():
            self.assertGreater(rate, 1_000, f"depth {depth}: {rate:.0f}/s")


if __name__ == "__main__":
    unittest.main()