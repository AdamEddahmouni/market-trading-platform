"""Tests for recorded order-flow provider and factory."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.providers.adapters.fixture_order_flow import (  # noqa: E402
    DEFAULT_ORDER_FLOW_FIXTURE,
    FixtureOrderFlowProvider,
)
from market_platform_foundation.providers.adapters.order_flow_factory import (  # noqa: E402
    build_order_flow_provider,
)
from market_platform_foundation.providers.adapters.recorded_order_flow import (  # noqa: E402
    RecordedOrderFlowProvider,
)


class RecordedOrderFlowProviderTests(unittest.TestCase):
    def test_fixture_provider_uses_classify_bar_delta_provenance(self) -> None:
        provider = FixtureOrderFlowProvider()
        result = provider.fetch_order_flow("NVDA")
        self.assertEqual(result.status, "available")
        self.assertTrue(result.events)
        provenance = {
            event["whale_event"]["aggressor_provenance"]
            for event in result.events
            if isinstance(event.get("whale_event"), dict)
        }
        self.assertIn("known", provenance)

    def test_recorded_provider_pit_filters_bars(self) -> None:
        provider = RecordedOrderFlowProvider()
        cutoff = iso_to_epoch_ns("2026-07-21T20:30:01.000000000Z")
        result = provider.fetch_order_flow("NVDA", as_of_time_ns=cutoff)
        self.assertEqual(result.status, "available")
        self.assertEqual(len(result.events), 2)

    def test_factory_defaults_to_fixture_provider(self) -> None:
        env = os.environ.pop("IMP_ORDER_FLOW_LIVE", None)
        try:
            provider = build_order_flow_provider()
            self.assertIsInstance(provider, FixtureOrderFlowProvider)
            self.assertEqual(provider.provider_id, "cvd.fixture.order_flow")
        finally:
            if env is not None:
                os.environ["IMP_ORDER_FLOW_LIVE"] = env

    def test_factory_live_gate_selects_recorded_provider(self) -> None:
        previous = os.environ.get("IMP_ORDER_FLOW_LIVE")
        os.environ["IMP_ORDER_FLOW_LIVE"] = "1"
        try:
            provider = build_order_flow_provider(fixture_path=DEFAULT_ORDER_FLOW_FIXTURE)
            self.assertIsInstance(provider, RecordedOrderFlowProvider)
            self.assertEqual(provider.provider_id, "cvd.recorded.order_flow")
        finally:
            if previous is None:
                os.environ.pop("IMP_ORDER_FLOW_LIVE", None)
            else:
                os.environ["IMP_ORDER_FLOW_LIVE"] = previous

    def test_recorded_provider_unavailable_when_fixture_missing(self) -> None:
        provider = RecordedOrderFlowProvider(fixture_path=Path("/nonexistent/order_flow.json"))
        result = provider.fetch_order_flow("NVDA")
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.reason_code, "ORDER_FLOW_LIVE_NOT_CONFIGURED")


if __name__ == "__main__":
    unittest.main()
