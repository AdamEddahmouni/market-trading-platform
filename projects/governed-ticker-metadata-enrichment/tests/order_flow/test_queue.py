"""Tests for OF10 MBO queue module."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.order_flow.queue import (
    QUEUE_METHOD,
    build_queue_snapshot,
    compute_queue_imbalance_mbo,
    estimate_queue_position,
    parse_mbo_orders,
)
from market_platform_foundation.order_flow.execution_forecast import (
    MBO_QUEUE_MODEL_VERSION,
    compute_execution_forecast,
)
from market_platform_foundation.providers.adapters.fixture_mbo import FixtureMboProvider
from market_platform_foundation.providers.adapters.fixture_futures import FixtureFuturesProvider

MBO_FIXTURE = ROOT / "tests" / "fixtures" / "providers" / "order_flow" / "es_mbo_slice.json"


class TestQueueModule(unittest.TestCase):
    def test_parse_and_reconstruct_fifo_queue(self) -> None:
        payload = json.loads(MBO_FIXTURE.read_text(encoding="utf-8"))
        orders = payload["snapshots"][0]["orders"]
        parsed = parse_mbo_orders(orders)
        self.assertEqual(len(parsed), 7)
        snapshot = build_queue_snapshot(parsed, event_time=payload["snapshots"][0]["event_time"])
        assert snapshot is not None
        self.assertEqual(snapshot.queue_method, QUEUE_METHOD)
        self.assertAlmostEqual(snapshot.bid_queues[0].total_size, 50.0)

    def test_queue_imbalance_mbo(self) -> None:
        provider = FixtureMboProvider(fixture_path=MBO_FIXTURE)
        snapshot = provider.queue_snapshot_for_event_time("2025-06-02T14:41:00.000000000Z")
        assert snapshot is not None
        imbalance = compute_queue_imbalance_mbo(snapshot)
        self.assertGreater(imbalance, 0.0)

    def test_estimate_queue_position(self) -> None:
        provider = FixtureMboProvider(fixture_path=MBO_FIXTURE)
        snapshot = provider.queue_snapshot_for_event_time("2025-06-02T14:41:00.000000000Z")
        assert snapshot is not None
        estimate = estimate_queue_position(snapshot, price=6000.0, side="bid", hypothetical_size=10.0)
        self.assertEqual(estimate.size_at_level, 50.0)


class TestExecutionForecastQueueUpgrade(unittest.TestCase):
    def test_mbo_upgrades_queue_model_version(self) -> None:
        provider = FixtureMboProvider(fixture_path=MBO_FIXTURE)
        mbo_snapshot = provider.queue_snapshot_for_event_time("2025-06-02T14:41:00.000000000Z")
        futures_fixture = json.loads(
            (ROOT / "tests" / "fixtures" / "providers" / "futures" / "es_depth_slice.json").read_text(
                encoding="utf-8"
            )
        )
        l2_snapshot = futures_fixture["snapshots"][0]
        without_mbo = compute_execution_forecast(l2_snapshot)
        with_mbo = compute_execution_forecast(l2_snapshot, mbo_queue_snapshot=mbo_snapshot)
        self.assertEqual(without_mbo.queue_model_version, "none")
        self.assertEqual(with_mbo.queue_model_version, MBO_QUEUE_MODEL_VERSION)
        self.assertIn("MBO_UNAVAILABLE", without_mbo.quality_flags)

    def test_futures_fixture_ingest_has_mbo_fields(self) -> None:
        provider = FixtureFuturesProvider()
        events = provider.build_envelopes()
        self.assertTrue(events)
        payload = events[0]["whale_event"]
        self.assertTrue(payload.get("mbo_capability_available"))
        self.assertEqual(payload.get("queue_method"), QUEUE_METHOD)


if __name__ == "__main__":
    unittest.main()
