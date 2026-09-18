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
from market_platform_foundation.providers.ibkr_observational.historical_trades_pagination import (  # noqa: E402
    paginate_historical_trades,
    sort_trades_deterministic,
)
from market_platform_foundation.providers.ibkr_observational.query_provider import (  # noqa: E402
    IbkrObservationalQueryService,
)

from ibkr_observational_support import FakeLookup, FakeQueryProvider, make_record  # noqa: E402


AAPL = make_record("AAPL")


class PagingHistoricalTradesProvider(FakeQueryProvider):
    """Returns slices of a fixed tick tape keyed by start_time_ns cursor."""

    def __init__(self, *, tape_rows: list[dict[str, object]], con_id: int = 265598) -> None:
        super().__init__(
            secdef_rows={
                "AAPL": [
                    {
                        "symbol": "AAPL",
                        "conid": con_id,
                        "secType": "STK",
                        "exchange": "SMART",
                        "currency": "USD",
                    }
                ]
            }
        )
        self._tape_rows = list(tape_rows)
        self._con_id = con_id

    def fetch_historical_trades(
        self,
        *,
        con_id: int,
        start_time_ns: int,
        end_time_ns: int,
        number_of_ticks: int = 1000,
    ) -> dict[str, object]:
        self.requests.append(
            (
                "historical_trades",
                {
                    "con_id": con_id,
                    "start_time_ns": start_time_ns,
                    "end_time_ns": end_time_ns,
                    "number_of_ticks": number_of_ticks,
                },
            )
        )
        eligible = [
            row
            for row in self._tape_rows
            if start_time_ns <= int(row["t"]) * 1_000_000_000 <= end_time_ns
        ]
        eligible = sorted(eligible, key=lambda row: (int(row["t"]), float(row["price"])))
        page = eligible[:number_of_ticks]
        return {"data": page}


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

    def test_pagination_merges_multiple_pages_without_boundary_duplicates(self) -> None:
        tape = [
            {"t": 1_700_000_000 + index, "price": 100.0 + index, "size": 1.0}
            for index in range(5)
        ]
        provider = PagingHistoricalTradesProvider(tape_rows=tape)
        service = IbkrObservationalQueryService(provider=provider, lookup=FakeLookup(AAPL))
        terminal_end = 1_700_000_010_000_000_000
        result = service.fetch_historical_trades(
            "AAPL",
            start_time_ns=1_700_000_000_000_000_000,
            end_time_ns=terminal_end,
            con_id=265598,
            request_time_ns=terminal_end,
            terminal_window_end_ns=terminal_end,
            ticks_per_page=2,
            max_pages=10,
            min_inter_page_interval_ns=0,
        )
        self.assertTrue(result.accepted)
        self.assertTrue(result.complete)
        self.assertEqual(len(result.trades), 5)
        self.assertIsNotNone(result.provenance)
        self.assertEqual(result.provenance.page_count, 3)
        event_times = [trade.event_time_ns for trade in result.trades]
        self.assertEqual(event_times, sorted(event_times))
        self.assertEqual(len(set(event_times)), 5)

    def test_pagination_reports_incomplete_when_max_pages_exceeded(self) -> None:
        tape = [
            {"t": 1_700_000_000 + index, "price": 100.0 + index, "size": 1.0}
            for index in range(6)
        ]
        provider = PagingHistoricalTradesProvider(tape_rows=tape)
        service = IbkrObservationalQueryService(provider=provider, lookup=FakeLookup(AAPL))
        terminal_end = 1_700_000_020_000_000_000
        result = service.fetch_historical_trades(
            "AAPL",
            start_time_ns=1_700_000_000_000_000_000,
            end_time_ns=terminal_end,
            con_id=265598,
            request_time_ns=terminal_end,
            terminal_window_end_ns=terminal_end,
            ticks_per_page=2,
            max_pages=2,
            min_inter_page_interval_ns=0,
        )
        self.assertTrue(result.accepted)
        self.assertFalse(result.complete)
        self.assertEqual(result.provenance.incomplete_reason, "MAX_PAGES_REACHED")
        self.assertEqual(len(result.trades), 4)

    def test_pagination_unit_orders_and_hashes(self) -> None:
        rows = [
            {"t": 3, "price": 1.0, "size": 1.0},
            {"t": 1, "price": 2.0, "size": 1.0},
            {"t": 2, "price": 3.0, "size": 1.0},
        ]

        def fetch_page(start_ns: int, end_ns: int, number_of_ticks: int) -> dict[str, object]:
            return {"data": rows}

        trades, provenance = paginate_historical_trades(
            fetch_page,
            instrument_id="AAPL",
            window_start_time_ns=1_000_000_000,
            window_end_time_ns=4_000_000_000,
            ticks_per_page=1000,
            max_pages=1,
            min_inter_page_interval_ns=0,
        )
        ordered = sort_trades_deterministic(trades)
        self.assertEqual([trade.event_time_ns for trade in ordered], sorted(t.event_time_ns for t in trades))
        self.assertTrue(provenance.aggregate_content_sha256)
        self.assertEqual(provenance.page_count, 1)
        self.assertEqual(provenance.pages[0].trade_count, 3)


if __name__ == "__main__":
    unittest.main()
