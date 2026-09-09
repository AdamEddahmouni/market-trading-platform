"""G11 runtime composition startup/shutdown tests."""

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

from ibkr_observational_support import FakeLookup, FakeQueryProvider, FakeTransport, make_record


AAPL = make_record("AAPL")


class G11RuntimeCompositionTests(unittest.TestCase):
    def test_streaming_and_query_startup(self) -> None:
        composition = ObservationalRuntimeComposition()
        transport = FakeTransport()
        composition.attach_ibkr_adapter(
            transport,
            config=IbkrObservationalConfig(live_enabled=True),
            lookup=FakeLookup(AAPL),
        )
        composition.attach_ibkr_query_service(FakeQueryProvider(), lookup=FakeLookup(AAPL))
        self.assertIsNotNone(composition.ibkr_adapter)
        self.assertIsNotNone(composition.ibkr_query_service)

    def test_query_only_startup(self) -> None:
        composition = ObservationalRuntimeComposition()
        composition.attach_ibkr_query_service(FakeQueryProvider(), lookup=FakeLookup(AAPL))
        self.assertIsNone(composition.ibkr_adapter)
        self.assertIsNotNone(composition.ibkr_query_service)

    def test_repeated_shutdown_idempotent(self) -> None:
        composition = ObservationalRuntimeComposition()
        provider = FakeQueryProvider()
        composition.attach_ibkr_query_service(provider, lookup=FakeLookup(AAPL))
        composition.shutdown()
        composition.shutdown()
        self.assertIsNone(composition.ibkr_query_service)
        self.assertEqual(provider.shutdown_calls, 1)

    def test_no_queries_after_shutdown(self) -> None:
        composition = ObservationalRuntimeComposition()
        provider = FakeQueryProvider(
            secdef_rows={
                "AAPL": [
                    {
                        "symbol": "AAPL",
                        "conid": 1,
                        "secType": "STK",
                        "exchange": "SMART",
                        "currency": "USD",
                    }
                ]
            }
        )
        composition.attach_ibkr_query_service(provider, lookup=FakeLookup(AAPL))
        composition.shutdown()
        result = composition.fetch_historical_bars("AAPL")
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "NO_QUERY_SERVICE")

    def test_repeated_configure_safe(self) -> None:
        composition = ObservationalRuntimeComposition()
        provider_a = FakeQueryProvider()
        provider_b = FakeQueryProvider()
        composition.attach_ibkr_query_service(provider_a, lookup=FakeLookup(AAPL))
        composition.attach_ibkr_query_service(provider_b, lookup=FakeLookup(AAPL))
        self.assertEqual(provider_a.shutdown_calls, 0)
        result = composition.resolve_contract("AAPL")
        self.assertFalse(result.accepted or result.qualification is not None)


if __name__ == "__main__":
    unittest.main()
