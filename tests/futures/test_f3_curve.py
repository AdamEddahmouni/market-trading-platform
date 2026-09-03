"""F3 curve engine tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.futures.curve import curve_regime, curve_snapshot_payload  # noqa: E402
from market_platform_foundation.providers.adapters.fixture_futures_chain import (  # noqa: E402
    FixtureFuturesChainProvider,
)


class FuturesF3CurveTests(unittest.TestCase):
    def test_es_fixture_curve_contango(self) -> None:
        provider = FixtureFuturesChainProvider()
        chain = provider.fetch_chain("ES")
        self.assertEqual(chain.status, "available")
        curve = curve_snapshot_payload(chain)
        self.assertTrue(curve.get("available"))
        self.assertEqual(curve.get("regime"), "contango")
        from market_platform_foundation.contracts.futures import FuturesCurveSnapshot
        from decimal import Decimal

        snapshot = FuturesCurveSnapshot(
            instrument_family="ES",
            observation_time="2025-06-02T14:41:00.000000000Z",
            available_time="2025-06-02T14:41:00.000000000Z",
            contract_ids=("ES202506", "ES202509"),
            expirations=("2025-06-20", "2025-09-20"),
            prices=(Decimal("6001.75"), Decimal("6008.0")),
        )
        self.assertEqual(curve_regime(snapshot), "contango")


if __name__ == "__main__":
    unittest.main()
