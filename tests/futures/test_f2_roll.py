"""F2 roll and continuous-series integration tests."""

from __future__ import annotations

import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.execution.simulator import simulate_futures_roll  # noqa: E402
from market_platform_foundation.futures.continuous import (  # noqa: E402
    additive_back_adjusted_series,
    ratio_adjusted_series,
    roll_gaps_from_prices,
)
from market_platform_foundation.futures.roll import select_lead_contract, ContractLiquidity  # noqa: E402
from market_platform_foundation.providers.adapters.fixture_futures_chain import (  # noqa: E402
    FixtureFuturesChainProvider,
)


class FuturesF2RollTests(unittest.TestCase):
    def test_lead_contract_selection_prefers_oi(self) -> None:
        contracts = [
            ContractLiquidity("ES202506", "2025-06-20", 120000, 200000, 18),
            ContractLiquidity("ES202509", "2025-09-20", 95000, 520000, 110),
        ]
        selection = select_lead_contract(contracts, today=date(2025, 6, 2))
        self.assertIsNotNone(selection)
        assert selection is not None
        self.assertEqual(selection.lead_contract_id, "ES202509")

    def test_fixture_chain_has_roll_metadata(self) -> None:
        provider = FixtureFuturesChainProvider()
        result = provider.fetch_chain("ES")
        self.assertEqual(result.status, "available")
        lead_rows = [row for row in result.events if row.get("lead_contract")]
        self.assertTrue(lead_rows)

    def test_roll_gap_continuous_pipeline(self) -> None:
        prices = [
            ("2025-06-02T14:41:07Z", Decimal("6001.75"), "ES202506"),
            ("2025-06-02T14:41:08Z", Decimal("6008.0"), "ES202509"),
        ]
        additive_gaps = [Decimal("6.25")]
        additive = additive_back_adjusted_series(prices, roll_gaps=additive_gaps)
        ratio_gaps = roll_gaps_from_prices(prices)
        ratio = ratio_adjusted_series(prices, roll_gaps=ratio_gaps)
        self.assertEqual(additive[-1].methodology, "additive_back_adjusted")
        self.assertEqual(ratio[-1].methodology, "ratio_adjusted")

    def test_simulate_futures_roll(self) -> None:
        roll = simulate_futures_roll(
            from_contract_id="ES202506",
            to_contract_id="ES202509",
            quantity=10,
            roll_gap=1.01,
        )
        self.assertTrue(roll["available"])
        self.assertIn("roll_id", roll)


if __name__ == "__main__":
    unittest.main()
