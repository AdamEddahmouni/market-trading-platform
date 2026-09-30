"""Final Screener closure: the News BONDS index sees every outstanding Treasury.

News matches BONDS headlines on Treasury CUSIPs. Its catalog used to page the whole BONDS universe in
default (maturity-descending) order and stop at 20,000 rows; after S16 added ~318k fund-held rows, live
acceptance found 9 of 463 Treasury CUSIPs in that index. The index now reads the Treasury rows directly,
from the projection the Screener already holds.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.ui_api import screener_bonds, screener_news  # noqa: E402
from market_platform_foundation.ui_api.screener_query import parse_query  # noqa: E402
from market_platform_foundation.ui_api.screener_universes import BONDS  # noqa: E402
import tests.fixed_income.test_s16_fixed_income_expansion as s16  # noqa: E402


class TreasuryRowsTests(s16.FundRowScreenerTests):
    # Reuse the S16 fixture (8 Treasuries + fund-held rows); only the tests below run in this class.
    def test_treasury_rows_are_every_treasury_and_nothing_else(self):
        rows, error = self.svc.treasury_rows()
        self.assertIsNone(error)
        self.assertEqual(len(rows), 8)
        self.assertEqual({row["category"] for row in rows}, {"Treasury"})
        self.assertTrue(all(row["cusip"].startswith("912") and row["instrument"]["instrument_id"] for row in rows))

    def test_treasury_rows_reuse_the_screener_projection(self):
        self.svc.read(parse_query(universe=BONDS, limit=5))
        projected = dict(self.svc._projected)
        self.svc.treasury_rows()
        self.assertEqual(list(self.svc._projected), list(projected))          # no second projection is built
        self.assertTrue(all(self.svc._projected[key] is value for key, value in projected.items()))

    def test_news_bonds_catalog_uses_the_treasury_rows(self):
        with mock.patch.object(screener_bonds, "bond_screener_service", return_value=self.svc), \
                mock.patch("market_platform_foundation.ui_api.screener_projections.read_screener",
                           side_effect=AssertionError("BONDS must not be paged")):
            rows, error = screener_news._default_catalog(BONDS)
        self.assertIsNone(error)
        self.assertEqual(len(rows), 8)


for _name in [name for name in dir(s16.FundRowScreenerTests) if name.startswith("test_")]:
    setattr(TreasuryRowsTests, _name, None)   # inherited S16 tests run in their own module


if __name__ == "__main__":
    unittest.main()
