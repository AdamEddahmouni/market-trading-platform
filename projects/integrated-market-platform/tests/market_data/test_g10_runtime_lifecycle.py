"""G10 runtime lifecycle hardening tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "providers"))

from market_platform_foundation.market_data.runtime_composition import (
    ObservationalRuntimeComposition,
)
from market_platform_foundation.providers.ibkr_observational.adapter import IbkrObservationalConfig

from ibkr_observational_support import FakeLookup, FakeTransport, connected_adapter, make_record


AAPL = make_record("AAPL")


class G10RuntimeLifecycleTests(unittest.TestCase):
    def test_composition_shutdown_idempotent(self) -> None:
        composition = ObservationalRuntimeComposition()
        transport = FakeTransport()
        composition.attach_ibkr_adapter(
            transport,
            config=IbkrObservationalConfig(live_enabled=True),
            lookup=FakeLookup(AAPL),
        )
        composition.ibkr_adapter.connect()
        composition.shutdown()
        composition.shutdown()
        self.assertIsNone(composition.ibkr_adapter)

    def test_adapter_shutdown_blocks_reconnect(self) -> None:
        adapter, _transport = connected_adapter(lookup=FakeLookup(AAPL))
        adapter.connect()
        adapter.subscribe_l1(instrument_id="AAPL")
        adapter.shutdown()
        adapter.handle_reconnect()
        self.assertEqual(adapter.subscription_status(), {})

    def test_repeated_cancel_safe(self) -> None:
        adapter, _transport = connected_adapter(lookup=FakeLookup(AAPL))
        adapter.connect()
        adapter.subscribe_l2(instrument_id="AAPL")
        first = adapter.cancel_l2("AAPL")
        second = adapter.cancel_l2("AAPL")
        self.assertTrue(first.accepted)
        self.assertFalse(second.accepted)


if __name__ == "__main__":
    unittest.main()
