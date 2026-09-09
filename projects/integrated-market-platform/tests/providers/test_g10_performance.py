"""G10 runtime performance smoke (development machine, not provider latency)."""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.market_data.depth_admission import evaluate_depth_admissibility
from market_platform_foundation.market_data.live_config import depth_freshness_policy
from market_platform_foundation.order_flow.order_book.contracts import DepthOperation, DepthSide, build_depth_update
from market_platform_foundation.order_flow.order_book.engine import IncrementalOrderBook
from market_platform_foundation.providers.ibkr_observational.historical_bars import normalize_ibkr_history_row
from market_platform_foundation.providers.runtime_capability import RuntimeCapabilityRegistry

ITERATIONS = 5000
G10_RUNTIME_PERFORMANCE_MEASURED: dict[str, float] = {}


class G10PerformanceTests(unittest.TestCase):
    def test_depth_freshness_evaluation_overhead(self) -> None:
        book = IncrementalOrderBook("AAPL")
        book.apply(
            build_depth_update(
                instrument_id="AAPL",
                operation=DepthOperation.RESET,
                received_time_ns=0,
            )
        )
        book.apply(
            build_depth_update(
                instrument_id="AAPL",
                operation=DepthOperation.INSERT,
                side=DepthSide.BID,
                price="100",
                size="1",
                received_time_ns=0,
            )
        )
        policy = depth_freshness_policy("ibkr.observational")
        start = time.perf_counter()
        for i in range(ITERATIONS):
            evaluate_depth_admissibility(book, as_of_time_ns=i + 1_000, policy=policy)
        elapsed_ms = (time.perf_counter() - start) * 1000
        G10_RUNTIME_PERFORMANCE_MEASURED["depth_freshness_ms"] = elapsed_ms
        self.assertLess(elapsed_ms, 5000.0)

    def test_capability_resolution_overhead(self) -> None:
        registry = RuntimeCapabilityRegistry()
        start = time.perf_counter()
        for _ in range(ITERATIONS):
            registry.view_capability("ibkr.observational", "IBKR_L2", instrument_id="AAPL")
        elapsed_ms = (time.perf_counter() - start) * 1000
        G10_RUNTIME_PERFORMANCE_MEASURED["capability_resolution_ms"] = elapsed_ms
        self.assertLess(elapsed_ms, 5000.0)

    def test_historical_bar_normalization_overhead(self) -> None:
        row = {"t": 1_700_000_000, "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 100}
        start = time.perf_counter()
        for _ in range(ITERATIONS):
            normalize_ibkr_history_row(row, instrument_id="AAPL", interval="1h")
        elapsed_ms = (time.perf_counter() - start) * 1000
        G10_RUNTIME_PERFORMANCE_MEASURED["historical_bar_normalization_ms"] = elapsed_ms
        self.assertLess(elapsed_ms, 5000.0)


if __name__ == "__main__":
    unittest.main()
