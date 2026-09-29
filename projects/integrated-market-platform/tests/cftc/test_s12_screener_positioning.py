"""S12 Screener positioning: CFTC Commitments of Traders per futures root, publication-gated.

Fixtures are real CFTC Public Reporting rows (futures-only TFF for E-mini S&P 500,
futures-only Disaggregated for WTI crude) for the reports of 2026-09-08/15/22.
"""

from __future__ import annotations

import json
import sys
import unittest
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.cftc.contracts import CotReportFamily  # noqa: E402
from market_platform_foundation.cftc.screener_positioning import (  # noqa: E402
    POSITIONING_MARKETS, build_positioning, publication_for, where_clause,
)

FIXTURES = ROOT / "tests" / "fixtures" / "cftc"
TFF_ES = json.loads((FIXTURES / "s12_tff_futures_only_es.json").read_text(encoding="utf-8"))
DIS_CL = json.loads((FIXTURES / "s12_disaggregated_futures_only_cl.json").read_text(encoding="utf-8"))


class MappingTests(unittest.TestCase):
    def test_codes_are_unique_and_micros_are_separate_markets(self):
        codes = Counter(market.code for market in POSITIONING_MARKETS.values())
        self.assertEqual(max(codes.values()), 1)
        self.assertNotEqual(POSITIONING_MARKETS["ES"].code, POSITIONING_MARKETS["MES"].code)
        self.assertNotEqual(POSITIONING_MARKETS["GC"].code, POSITIONING_MARKETS["MGC"].code)

    def test_report_family_by_asset(self):
        for root in ("ES", "ZN", "6E", "VX", "BTC", "SR3"):
            self.assertEqual(POSITIONING_MARKETS[root].report, CotReportFamily.TFF)
        for root in ("CL", "NG", "GC", "ZC", "LE"):
            self.assertEqual(POSITIONING_MARKETS[root].report, CotReportFamily.DISAGGREGATED)

    def test_where_clause_quotes_only_codes(self):
        clause = where_clause(["13874A", "067651", "x'; drop"], date(2026, 8, 24))
        self.assertIn("('067651', '13874A')", clause)
        self.assertNotIn("drop", clause)
        self.assertIn("'2026-08-24T00:00:00.000'", clause)


class PositioningTests(unittest.TestCase):
    def test_tff_categories_net_and_published_changes(self):
        report = build_positioning(TFF_ES, POSITIONING_MARKETS["ES"], now=datetime(2026, 9, 28, tzinfo=UTC))
        self.assertEqual((report["report_date"], report["publication_time"]), ("2026-09-22", "2026-09-25T19:30:00Z"))
        self.assertEqual(report["report"], "TFF")
        ids = [item["id"] for item in report["categories"]]
        self.assertIn("ASSET_MANAGER_INSTITUTIONAL", ids)
        self.assertNotIn("MANAGED_MONEY", ids)  # Disaggregated categories never appear on a TFF market
        for item in report["categories"]:
            if item["long"] is not None and item["short"] is not None:
                self.assertEqual(item["net"], item["long"] - item["short"])
        dealer = next(item for item in report["categories"] if item["id"] == "DEALER_INTERMEDIARY")
        row = next(row for row in TFF_ES if row["report_date_as_yyyy_mm_dd"].startswith("2026-09-22"))
        self.assertEqual(dealer["change_long"], int(float(row["change_in_dealer_long_all"])))
        self.assertIn("not a price forecast", report["net_method"])

    def test_disaggregated_categories(self):
        report = build_positioning(DIS_CL, POSITIONING_MARKETS["CL"], now=datetime(2026, 9, 28, tzinfo=UTC))
        ids = {item["id"] for item in report["categories"]}
        self.assertTrue({"PRODUCER_MERCHANT", "SWAP_DEALER", "MANAGED_MONEY"} <= ids)
        self.assertNotIn("LEVERAGED_FUNDS", ids)
        self.assertEqual(report["report"], "DISAGGREGATED")

    def test_report_is_invisible_before_its_publication(self):
        before = build_positioning(TFF_ES, POSITIONING_MARKETS["ES"], now=datetime(2026, 9, 25, 19, 29, tzinfo=UTC))
        self.assertEqual(before["report_date"], "2026-09-15")
        after = build_positioning(TFF_ES, POSITIONING_MARKETS["ES"], now=datetime(2026, 9, 25, 19, 30, tzinfo=UTC))
        self.assertEqual(after["report_date"], "2026-09-22")
        self.assertIsNone(build_positioning(TFF_ES, POSITIONING_MARKETS["ES"], now=datetime(2026, 9, 1, tzinfo=UTC)))

    def test_rows_for_other_markets_are_ignored(self):
        self.assertIsNone(build_positioning(TFF_ES, POSITIONING_MARKETS["NQ"], now=datetime(2026, 9, 28, tzinfo=UTC)))

    def test_publication_basis(self):
        published, basis = publication_for(date(2026, 9, 22))
        self.assertEqual(published, datetime(2026, 9, 25, 19, 30, tzinfo=UTC))
        self.assertIn(basis, ("CFTC_OFFICIAL_SCHEDULE", "CFTC_OFFICIAL_SCHEDULE_DELAYED"))
        _, inferred = publication_for(date(2031, 1, 7))
        self.assertEqual(inferred, "PUBLICATION_TIME_INFERRED_TUESDAY_PLUS_3")


if __name__ == "__main__":
    unittest.main()
