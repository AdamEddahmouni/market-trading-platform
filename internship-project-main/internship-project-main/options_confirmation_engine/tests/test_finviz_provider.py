"""Offline unit tests for the Finviz options provider (no network)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from datetime import date

from options_engine.finviz_provider import (
    _as_of_date,
    _expiry_sort_key,
    _parse_expiry_date,
    estimate_spot_from_contracts,
    parse_options_csv,
)


# Matches the real Finviz Elite options export column layout.
SAMPLE_CSV = (
    "Contract Name,Last Trade,Expiry,Strike,Last Close,Bid,Ask,Change $,Change %,"
    "Volume,Open Int.,Type,IV,Delta,Gamma,Theta,Vega,Rho\n"
    '"AAPL260619C00190000",6/9/2026 3:55:56 PM,6/19/2026,190.0,10.2,10.1,10.4,0,0%,'
    "1200,5400,call,0.31,0.62,0.01,-0.02,0.05,0.03\n"
    '"AAPL260619C00200000",6/9/2026 3:55:56 PM,6/19/2026,200.0,2.2,2.1,2.3,0,0%,'
    "800,3300,call,0.29,0.38,0.01,-0.02,0.05,0.03\n"
    '"AAPL260619P00190000",6/9/2026 3:55:56 PM,6/19/2026,190.0,1.1,1.0,1.2,0,0%,'
    "640,2100,put,0.33,-0.38,0.01,-0.02,0.05,0.03\n"
)


class FinvizParserTests(unittest.TestCase):
    def test_parses_rows_and_fields(self) -> None:
        rows = parse_options_csv(SAMPLE_CSV)
        self.assertEqual(len(rows), 3)
        call = rows[0]
        self.assertEqual(call.contract_symbol, "AAPL260619C00190000")
        self.assertEqual(call.side, "call")
        self.assertEqual(call.strike, 190.0)
        self.assertEqual(call.expiration, "6/19/2026")
        self.assertEqual(call.volume, 1200.0)
        self.assertEqual(call.open_interest, 5400.0)
        self.assertAlmostEqual(call.implied_volatility, 0.31)
        self.assertAlmostEqual(call.last_price, 10.2)
        self.assertEqual(rows[2].side, "put")

    def test_in_the_money_derived_from_delta(self) -> None:
        rows = parse_options_csv(SAMPLE_CSV)
        # 190 call delta 0.62 -> ITM; 200 call delta 0.38 -> OTM; 190 put delta -0.38 -> OTM
        self.assertTrue(rows[0].in_the_money)
        self.assertFalse(rows[1].in_the_money)
        self.assertFalse(rows[2].in_the_money)

    def test_expiry_sort_key_is_chronological(self) -> None:
        raw = ["1/15/2027", "10/16/2026", "6/19/2026", "11/20/2026"]
        ordered = sorted(raw, key=_expiry_sort_key)
        self.assertEqual(ordered, ["6/19/2026", "10/16/2026", "11/20/2026", "1/15/2027"])

    def test_parse_expiry_date(self) -> None:
        self.assertEqual(_parse_expiry_date("6/15/2026"), date(2026, 6, 15))
        self.assertEqual(_parse_expiry_date("2026-06-15"), date(2026, 6, 15))
        self.assertIsNone(_parse_expiry_date("not-a-date"))

    def test_as_of_date_from_iso_timestamp(self) -> None:
        self.assertEqual(_as_of_date("2026-06-14T20:00:00+00:00"), date(2026, 6, 14))

    def test_handles_empty_input(self) -> None:
        self.assertEqual(parse_options_csv(""), [])
        self.assertEqual(parse_options_csv("   \n"), [])

    def test_tolerates_messy_numbers(self) -> None:
        csv_text = (
            "Type,Strike,Expiration,IV,Volume,Open Interest\n"
            'Call,"1,050.0",2026-07-17,45%,-,"1,200"\n'
        )
        rows = parse_options_csv(csv_text)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].strike, 1050.0)
        self.assertEqual(rows[0].volume, 0.0)
        self.assertEqual(rows[0].open_interest, 1200.0)
        self.assertAlmostEqual(rows[0].implied_volatility, 45.0)

    def test_spot_estimation_from_itm_boundary(self) -> None:
        rows = parse_options_csv(SAMPLE_CSV)
        spot = estimate_spot_from_contracts(rows)
        self.assertAlmostEqual(spot, 195.0)

    def test_spot_estimation_returns_zero_without_boundary(self) -> None:
        csv_text = (
            "Type,Strike,Expiration,In The Money\n"
            "Call,200.0,2026-06-19,false\n"
        )
        rows = parse_options_csv(csv_text)
        self.assertEqual(estimate_spot_from_contracts(rows), 0.0)


if __name__ == "__main__":
    unittest.main()
