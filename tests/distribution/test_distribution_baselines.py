"""Expanded SHARED P2 distribution forecast and fixture tests."""

from __future__ import annotations

import hashlib
import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.canonical import canonical_bytes  # noqa: E402
from market_platform_foundation.futures.continuous import (  # noqa: E402
    additive_back_adjusted_series,
    ratio_adjusted_series,
    roll_gaps_from_prices,
    unadjusted_continuous_series,
)
from market_platform_foundation.providers.adapters.fixture_distribution import (  # noqa: E402
    FixtureDistributionForecastProvider,
)
from market_platform_foundation.research.distribution import (  # noqa: E402
    ewma_volatility_forecast,
    garch11_forecast,
    har_rv_forecast,
    physical_distribution_forecast,
    realized_volatility_close_to_close,
    realized_volatility_parkinson,
)


class DistributionBaselineTests(unittest.TestCase):
    def test_realized_vol_positive_on_trend(self) -> None:
        closes = [100 + i for i in range(30)]
        rv = realized_volatility_close_to_close(closes)
        self.assertIsNotNone(rv)
        assert rv is not None
        self.assertGreater(rv, 0)

    def test_parkinson_vol(self) -> None:
        highs = [101 + i * 0.1 for i in range(20)]
        lows = [99 + i * 0.1 for i in range(20)]
        rv = realized_volatility_parkinson(highs, lows)
        self.assertIsNotNone(rv)

    def test_ewma_and_garch_forecasts(self) -> None:
        closes = [100 + (i % 5) for i in range(40)]
        ewma = ewma_volatility_forecast(closes)
        garch = garch11_forecast(closes)
        self.assertIsNotNone(ewma)
        self.assertIsNotNone(garch)

    def test_har_rv_requires_history(self) -> None:
        short = [100.0 + i * 0.1 for i in range(10)]
        self.assertIsNone(har_rv_forecast(short))
        long = [100.0 + (i % 3) * 0.2 for i in range(80)]
        self.assertIsNotNone(har_rv_forecast(long))


class PhysicalDistributionForecastTests(unittest.TestCase):
    def test_multi_horizon_forecast_contract(self) -> None:
        closes = [170.5 + i * 0.01 for i in range(40)]
        forecast = physical_distribution_forecast(
            closes,
            symbol="NVDA",
            as_of_time="2026-07-21T20:30:39.000000000Z",
            horizons=(1, 5, 10),
        )
        self.assertIsNotNone(forecast)
        assert forecast is not None
        self.assertEqual(len(forecast.horizons), 3)
        self.assertIsNotNone(forecast.vol_forecast_annualized)

    def test_fixture_provider_replay_hash(self) -> None:
        provider = FixtureDistributionForecastProvider()
        result = provider.fetch_distribution_forecast("NVDA")
        self.assertEqual(result.status, "available")
        payload = result.events[0]
        digest = hashlib.sha256(canonical_bytes(payload)).hexdigest()
        self.assertEqual(len(digest), 64)


class ContinuousSeriesTests(unittest.TestCase):
    def test_additive_back_adjusted_series(self) -> None:
        prices = [
            ("2025-01-01", Decimal("100"), "ESU25"),
            ("2025-01-02", Decimal("105"), "ESU25"),
            ("2025-01-03", Decimal("110"), "ESZ25"),
        ]
        points = additive_back_adjusted_series(prices, roll_gaps=[Decimal("2")])
        self.assertEqual(len(points), 3)
        self.assertEqual(points[-1].methodology, "additive_back_adjusted")
        self.assertEqual(points[-1].roll_adjustment, Decimal("2"))

    def test_ratio_adjusted_series(self) -> None:
        prices = [
            ("2025-01-01", Decimal("100"), "ESU25"),
            ("2025-01-02", Decimal("105"), "ESZ25"),
        ]
        gaps = roll_gaps_from_prices(prices)
        points = ratio_adjusted_series(prices, roll_gaps=gaps)
        self.assertEqual(points[-1].methodology, "ratio_adjusted")

    def test_unadjusted_continuous_series(self) -> None:
        prices = [("2025-01-01", Decimal("100"), "ESU25")]
        points = unadjusted_continuous_series(prices)
        self.assertEqual(points[0].price, Decimal("100"))


if __name__ == "__main__":
    unittest.main()
