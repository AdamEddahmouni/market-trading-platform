"""Provisional security identity helpers."""

from __future__ import annotations

import unittest

from market_platform_foundation.research.security_identity import (
    resolve_us_equity_ticker,
)


class SecurityIdentityTests(unittest.TestCase):
    def test_resolve_us_equity_ticker_normalizes(self) -> None:
        row = resolve_us_equity_ticker("aapl", venue_id="XNYS")
        self.assertEqual(row.ticker, "AAPL")
        self.assertEqual(row.instrument.instrument_id, "AAPL")
        self.assertEqual(row.instrument.venue_id, "XNYS")
        self.assertTrue(row.to_dict()["provisional"])

    def test_invalid_ticker_rejected(self) -> None:
        with self.assertRaises(ValueError):
            resolve_us_equity_ticker("")


if __name__ == "__main__":
    unittest.main()
