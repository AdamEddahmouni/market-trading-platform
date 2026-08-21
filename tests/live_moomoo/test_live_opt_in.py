"""Opt-in live OpenD tests. Never fail ordinary CI when Moomoo is offline."""

from __future__ import annotations

import os
import socket
import unittest

LIVE_ENABLED = os.environ.get("IMP_MOOMOO_LIVE") == "1"
HOST = os.environ.get("IMP_MOOMOO_HOST", "127.0.0.1")
PORT = int(os.environ.get("IMP_MOOMOO_PORT", "11111"))


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
    def test_quote_context_snapshot_aapl(self) -> None:
        import moomoo as ft

        self.assertTrue(hasattr(ft, "OpenQuoteContext"))
        ctx = ft.OpenQuoteContext(host=HOST, port=PORT)
        try:
            self.assertNotEqual(type(ctx).__name__, "OpenUSTradeContext")
            ret, data = ctx.get_market_snapshot(["US.AAPL"])
            self.assertEqual(ret, ft.RET_OK)
            self.assertGreaterEqual(len(data.index), 1)
        finally:
            ctx.close()


if __name__ == "__main__":
    unittest.main()
