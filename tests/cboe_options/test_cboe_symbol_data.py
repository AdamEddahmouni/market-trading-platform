"""Cboe exchange-specific symbol data snapshots."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.cboe_options.contracts import CboeExchangeCode, CoverageScope, contract_snapshot_to_dict  # noqa: E402
from market_platform_foundation.cboe_options.symbol_data import parse_symbol_data_csv  # noqa: E402

sys.path.insert(0, str(ROOT / "tests" / "cboe_options"))
from _helpers import INGESTED_TIME, RETRIEVED_TIME, load_text


class CboeSymbolDataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.capture = parse_symbol_data_csv(
            load_text("symbol_data_cone.csv"),
            exchange=CboeExchangeCode.C1,
            retrieved_time=RETRIEVED_TIME,
            ingested_time=INGESTED_TIME,
        )

    def test_exchange_identity_is_c1_not_bzx(self) -> None:
        self.assertEqual(self.capture.exchange, CboeExchangeCode.C1)
        self.assertEqual(len(self.capture.snapshots), 5)
        for snap in self.capture.snapshots:
            self.assertEqual(snap.exchange, CboeExchangeCode.C1)

    def test_quotes_are_exchange_specific_not_nbbo(self) -> None:
        first = self.capture.snapshots[0]
        self.assertIsNotNone(first.exchange_bid)
        self.assertIsNotNone(first.exchange_ask)
        serialized = json.dumps(contract_snapshot_to_dict(first)).upper()
        self.assertNotIn("NBBO", serialized)

    def test_exchange_specific_scope_not_consolidated_opra(self) -> None:
        for snap in self.capture.snapshots:
            self.assertEqual(snap.coverage_scope, CoverageScope.EXCHANGE_SPECIFIC)

    def test_contract_identity_distinguishes_call_put_and_expiry(self) -> None:
        keys = {
            (snap.underlying, snap.expiration_date, snap.strike, snap.option_type)
            for snap in self.capture.snapshots
        }
        self.assertEqual(len(keys), 5)
        self.assertEqual({snap.expiration_date for snap in self.capture.snapshots}, {"2025-09-19"})


if __name__ == "__main__":
    unittest.main()
