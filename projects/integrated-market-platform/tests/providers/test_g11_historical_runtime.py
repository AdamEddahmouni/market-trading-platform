"""G11 historical bar runtime wiring tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "providers"))

from market_platform_foundation.market_data.observational_state import ObservationalStateStore
from market_platform_foundation.market_data.runtime_composition import (
    ObservationalRuntimeComposition,
)
from market_platform_foundation.providers.ibkr_observational.historical_bars import (
    normalize_ibkr_history_row,
)

from ibkr_observational_support import FakeLookup, FakeQueryProvider, make_record


AAPL = make_record("AAPL")


class G11HistoricalRuntimeTests(unittest.TestCase):
    def test_exact_canonical_instrument_request(self) -> None:
        provider = FakeQueryProvider(
            secdef_rows={
                "AAPL": [
                    {
                        "symbol": "AAPL",
                        "conid": 265598,
                        "secType": "STK",
                        "exchange": "SMART",
                        "currency": "USD",
                    }
                ]
            }
        )
        composition = ObservationalRuntimeComposition()
        composition.attach_ibkr_query_service(provider, lookup=FakeLookup(AAPL))
        result = composition.fetch_historical_bars("AAPL", period="1d", bar="1h")
        self.assertTrue(result.accepted)
        self.assertEqual(len(result.bars), 1)
        self.assertEqual(result.bars[0].instrument_id, "AAPL")

    def test_timestamp_preservation(self) -> None:
        row = {"t": 1_700_000_000, "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 100}
        bar = normalize_ibkr_history_row(row, instrument_id="AAPL", interval="1h")
        self.assertEqual(bar.source_time_ns, 1_700_000_000_000_000_000)

    def test_missing_timestamp_fails(self) -> None:
        with self.assertRaises(ValueError):
            normalize_ibkr_history_row({"o": 1}, instrument_id="AAPL", interval="1h")

    def test_malformed_ohlc_still_normalizes_with_defaults(self) -> None:
        bar = normalize_ibkr_history_row(
            {"t": 1, "o": None, "h": None, "l": None, "c": None},
            instrument_id="AAPL",
            interval="1h",
        )
        self.assertEqual(bar.open, 0.0)

    def test_empty_result_distinct_from_unavailable(self) -> None:
        provider = FakeQueryProvider(
            secdef_rows={
                "AAPL": [
                    {
                        "symbol": "AAPL",
                        "conid": 265598,
                        "secType": "STK",
                        "exchange": "SMART",
                        "currency": "USD",
                    }
                ]
            },
            history_payloads={265598: {"data": []}},
        )
        composition = ObservationalRuntimeComposition()
        composition.attach_ibkr_query_service(provider, lookup=FakeLookup(AAPL))
        result = composition.fetch_historical_bars("AAPL")
        self.assertTrue(result.accepted)
        self.assertEqual(len(result.bars), 0)

    def test_pit_cutoff_behavior(self) -> None:
        provider = FakeQueryProvider(
            secdef_rows={
                "AAPL": [
                    {
                        "symbol": "AAPL",
                        "conid": 265598,
                        "secType": "STK",
                        "exchange": "SMART",
                        "currency": "USD",
                    }
                ]
            },
            history_payloads={
                265598: {
                    "data": [
                        {"t": 100, "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 1},
                        {"t": 200, "o": 2, "h": 3, "l": 1.5, "c": 2.5, "v": 2},
                    ]
                }
            },
        )
        composition = ObservationalRuntimeComposition()
        composition.attach_ibkr_query_service(provider, lookup=FakeLookup(AAPL))
        result = composition.fetch_historical_bars(
            "AAPL",
            pit_cutoff_ns=150 * 1_000_000_000,
        )
        self.assertTrue(result.accepted)
        self.assertEqual(len(result.bars), 1)

    def test_no_mutation_of_quote_state(self) -> None:
        store = ObservationalStateStore()
        provider = FakeQueryProvider(
            secdef_rows={
                "AAPL": [
                    {
                        "symbol": "AAPL",
                        "conid": 265598,
                        "secType": "STK",
                        "exchange": "SMART",
                        "currency": "USD",
                    }
                ]
            }
        )
        composition = ObservationalRuntimeComposition(store=store)
        composition.attach_ibkr_query_service(provider, lookup=FakeLookup(AAPL))
        before = store.metrics_report()
        composition.fetch_historical_bars("AAPL")
        after = store.metrics_report()
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
