"""Hot-path telemetry observer overhead on ingress dispatch."""

from __future__ import annotations

import time
import unittest

from market_platform_foundation.hot_path_telemetry.collector import HotPathClockCollector
from market_platform_foundation.intelligence.normalization import IngestionMode, NormalizationContext
from market_platform_foundation.intelligence.observation_ingress import (
    IngressDispatchContext,
    build_production_observation_ingress_router,
    dispatch_normalization_result,
)
from market_platform_foundation.intelligence.normalization.providers.moomoo import normalize_moomoo_capture
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository

T0 = 1_000_000_000_000
FIVE_SEC = 5 * 1_000_000_000


def _quote_fixture() -> dict:
    return {
        "provider": "moomoo.opend.observational",
        "capability": "QUOTE",
        "provider_symbol": "US.NVDA",
        "sequence": 42,
        "clocks": {
            "event_time_ns": T0,
            "provider_time_ns": T0 + 5_000_000,
            "received_time_ns": T0 + FIVE_SEC,
        },
        "raw_payload": {
            "bid_price": 100.0,
            "ask_price": 100.05,
            "bid_vol": 500,
            "ask_vol": 400,
        },
    }


class HotPathOverheadTests(unittest.TestCase):
    def test_dispatch_observer_overhead_bounded(self) -> None:
        ctx = NormalizationContext(
            received_time_ns=T0 + FIVE_SEC,
            ingestion_mode=IngestionMode.LIVE_OBSERVED,
        )
        normalized = normalize_moomoo_capture(_quote_fixture(), context=ctx)
        event = normalized.event
        assert event is not None
        dispatch_ctx = IngressDispatchContext(
            dispatch_time_ns=T0 + FIVE_SEC,
            ingestion_mode=IngestionMode.LIVE_OBSERVED,
            source_label="moomoo.capture",
        )
        iterations = 500

        def bench(observer: HotPathClockCollector | None) -> float:
            repo = InMemoryIntelligenceRepository()
            router = build_production_observation_ingress_router(repo, dispatch_observer=observer)
            dispatch_normalization_result(
                router,
                normalized,
                context=dispatch_ctx,
                clock_collector=observer,
            )
            start = time.perf_counter()
            for _ in range(iterations):
                router.dispatch(event, context=dispatch_ctx, allow_duplicate_replay=True)
            return time.perf_counter() - start

        with_observer = bench(HotPathClockCollector())
        without_observer = bench(None)
        ratio = with_observer / max(without_observer, 1e-9)
        self.assertLess(ratio, 3.0, f"observer overhead ratio {ratio:.2f} exceeds 3x")


if __name__ == "__main__":
    unittest.main()
