"""G11 historical TRADE runtime wiring tests (Lane C)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "providers"))

from market_platform_foundation.providers.ibkr_observational.historical_trades import (  # noqa: E402
    normalize_ibkr_historical_trade_row,
)
from market_platform_foundation.providers.ibkr_observational.query_provider import (  # noqa: E402
    IbkrObservationalQueryService,
)

from ibkr_observational_support import FakeLookup, FakeQueryProvider, make_record  # noqa: E402


AAPL = make_record("AAPL")


class G11HistoricalTradesTests(unittest.TestCase):
    def test_normalize_trade_row(self) -> None:
        trade = normalize_ibkr_historical_trade_row(
            {"t": 1_700_000_000, "price": 150.0, "size": 25},
            instrument_id="AAPL",
        )
        self.assertEqual(trade.observation_kind, "TRADE")
        self.assertEqual(trade.event_time_ns, 1_700_000_000_000_000_000)

    def test_query_service_accepts_post_window_request(self) -> None:
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
            historical_trades_payloads={
                265598: {
                    "data": [
                        {
                            "t": 1_700_000_000,
                            "price": 101.0,
                            "size": 10,
                        }
                    ]
                }
            },
        )
        service = IbkrObservationalQueryService(provider=provider, lookup=FakeLookup(AAPL))
        terminal_end = 1_700_000_120_000_000_000
        result = service.fetch_historical_trades(
            "AAPL",
            start_time_ns=1_700_000_000_000_000_000,
            end_time_ns=terminal_end,
            con_id=265598,
            request_time_ns=terminal_end,
            terminal_window_end_ns=terminal_end,
        )
        self.assertTrue(result.accepted)
        self.assertEqual(len(result.trades), 1)

    def test_query_service_refuses_pre_terminal_retrieval(self) -> None:
        provider = FakeQueryProvider(secdef_rows={"AAPL": [{"symbol": "AAPL", "conid": 1}]})
        service = IbkrObservationalQueryService(provider=provider, lookup=FakeLookup(AAPL))
        terminal_end = 100
        result = service.fetch_historical_trades(
            "AAPL",
            start_time_ns=0,
            end_time_ns=terminal_end,
            con_id=1,
            request_time_ns=terminal_end - 1,
            terminal_window_end_ns=terminal_end,
        )
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "RETRIEVAL_BEFORE_TERMINAL_WINDOW_END")

    def test_query_service_refuses_when_post_horizon_timing_omitted(self) -> None:
        provider = FakeQueryProvider(secdef_rows={"AAPL": [{"symbol": "AAPL", "conid": 1}]})
        service = IbkrObservationalQueryService(provider=provider, lookup=FakeLookup(AAPL))
        terminal_end = 100
        for kwargs in (
            {"request_time_ns": None, "terminal_window_end_ns": terminal_end},
            {"request_time_ns": terminal_end, "terminal_window_end_ns": None},
            {},
        ):
            with self.subTest(kwargs=kwargs):
                result = service.fetch_historical_trades(
                    "AAPL",
                    start_time_ns=0,
                    end_time_ns=terminal_end,
                    con_id=1,
                    **kwargs,
                )
                self.assertFalse(result.accepted)
                self.assertEqual(result.reason, "POST_HORIZON_RETRIEVAL_TIMING_REQUIRED")


if __name__ == "__main__":
    unittest.main()
