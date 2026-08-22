"""Opt-in live OpenD tests. Never fail ordinary CI when Moomoo is offline."""

from __future__ import annotations

import os
import socket
import sys
import time
import unittest
from pathlib import Path

LIVE_ENABLED = os.environ.get("IMP_MOOMOO_LIVE") == "1"
HOST = os.environ.get("IMP_MOOMOO_HOST", "127.0.0.1")
PORT = int(os.environ.get("IMP_MOOMOO_PORT", "11111"))
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools" / "moomoo"))


def _opend_available() -> bool:
    if HOST not in {"127.0.0.1", "localhost", "::1"}:
        return False
    try:
        sock = socket.create_connection((HOST, PORT), timeout=1)
        sock.close()
        return True
    except OSError:
        return False


@unittest.skipUnless(LIVE_ENABLED and _opend_available(), "IMP_MOOMOO_LIVE=1 and localhost OpenD required")
class LiveMoomooOptInTests(unittest.TestCase):
    def test_quote_context_snapshot_two_symbols(self) -> None:
        import moomoo as ft

        self.assertTrue(hasattr(ft, "OpenQuoteContext"))
        self.assertFalse(hasattr(ft, "OpenQuoteContext") and "OpenTradeContext" in sys.modules)
        ctx = ft.OpenQuoteContext(host=HOST, port=PORT)
        try:
            self.assertNotEqual(type(ctx).__name__, "OpenUSTradeContext")
            ret, data = ctx.get_market_snapshot(["US.AAPL", "US.NVDA"])
            self.assertEqual(ret, ft.RET_OK)
            codes = set(data["code"].tolist()) if hasattr(data, "__getitem__") else set()
            self.assertIn("US.AAPL", codes)
            self.assertIn("US.NVDA", codes)
        finally:
            ctx.close()
        self.assertNotIn("OpenTradeContext", sys.modules)

    def test_runtime_ingest_from_live_push(self) -> None:
        import moomoo as ft
        from market_platform_foundation.market_data.live_runtime import LiveObservationalRuntime
        from push_feed import payload_rows

        runtime = LiveObservationalRuntime()
        ctx = ft.OpenQuoteContext(host=HOST, port=PORT)
        quotes: list = []
        tickers: list = []

        class QuoteHandler(ft.StockQuoteHandlerBase):
            def on_recv_rsp(self, rsp_pb):  # type: ignore[no-untyped-def]
                ret, data = super().on_recv_rsp(rsp_pb)
                if ret == ft.RET_OK:
                    quotes.extend(payload_rows(data))
                return ret, data

        class TickerHandler(ft.TickerHandlerBase):
            def on_recv_rsp(self, rsp_pb):  # type: ignore[no-untyped-def]
                ret, data = super().on_recv_rsp(rsp_pb)
                if ret == ft.RET_OK:
                    tickers.extend(payload_rows(data))
                return ret, data

        ctx.set_handler(QuoteHandler())
        ctx.set_handler(TickerHandler())
        try:
            ctx.subscribe(
                ["US.AAPL", "US.NVDA"],
                [ft.SubType.QUOTE, ft.SubType.TICKER],
                is_first_push=True,
                subscribe_push=True,
                session=ft.Session.ALL,
            )
            time.sleep(5)
            ctx.unsubscribe(["US.AAPL", "US.NVDA"], [ft.SubType.QUOTE, ft.SubType.TICKER])
        finally:
            ctx.close()
        self.assertGreater(len(quotes), 0)
        received = time.time_ns()
        for row in quotes:
            code = str(row.get("code") or "")
            runtime.ingest_record(
                {
                    "capability": "US_EQUITY_L1",
                    "clocks": {
                        "event_time_ns": received,
                        "provider_time_ns": received,
                        "received_time_ns": received,
                    },
                    "instrument_id": code.split(".")[-1],
                    "provider": "moomoo",
                    "provider_symbol": code,
                    "raw_payload": row,
                    "sequence": received,
                },
                wall_now_ns=received + 1_000_000,
            )
        aapl = runtime.state.quote_for("AAPL")
        nvda = runtime.state.quote_for("NVDA")
        self.assertIsNotNone(aapl)
        self.assertIsNotNone(nvda)
        assert aapl is not None and nvda is not None
        self.assertNotEqual(aapl.last_price, nvda.last_price)
        self.assertNotIn("OpenTradeContext", sys.modules)


if __name__ == "__main__":
    unittest.main()
