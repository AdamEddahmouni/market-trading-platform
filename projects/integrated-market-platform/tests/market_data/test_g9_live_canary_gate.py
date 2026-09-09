"""G9 live canary gate — no network when offline."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "providers"))

from market_platform_foundation.providers.ibkr_observational.adapter import IbkrOfflineError
from market_platform_foundation.providers.runtime_capability import (
    IBKR_PROVIDER_ID,
    RuntimeCapabilityRegistry,
    RuntimeCapabilityState,
)

from ibkr_observational_support import FakeLookup, FakeTransport, make_adapter, make_record


AAPL = make_record("AAPL")


class G9LiveCanaryGateTests(unittest.TestCase):
    def test_offline_blocks_connect_and_subscriptions(self) -> None:
        adapter, transport = make_adapter(live=False, lookup=FakeLookup(AAPL))
        with self.assertRaises(IbkrOfflineError):
            adapter.connect()
        with self.assertRaises(IbkrOfflineError):
            adapter.subscribe_trades(instrument_id="AAPL")
        self.assertEqual(transport.connect_calls, [])
        self.assertEqual(transport.tick_by_tick_requests, [])

    def test_runtime_registry_live_unverified(self) -> None:
        registry = RuntimeCapabilityRegistry()
        state = registry.runtime_state_for(IBKR_PROVIDER_ID)
        self.assertFalse(state.live_verified)
        view = registry.view_capability(IBKR_PROVIDER_ID, "IBKR_TRADES")
        self.assertEqual(view.runtime_state, RuntimeCapabilityState.LIVE_PROVIDER_UNVERIFIED)


if __name__ == "__main__":
    unittest.main()
