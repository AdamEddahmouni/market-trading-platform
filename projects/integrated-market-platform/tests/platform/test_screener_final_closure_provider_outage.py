"""Final Main Screener closure — a stopped OpenD fails fast and recovers.

The vendor quote-context constructor retries a refused connection without
returning, and every transport call is serialized, so one preview could hold
every Screener provider read. The transport now probes the loopback port first;
an outage is reported as ``OPEND_UNAVAILABLE`` and is not cached as a resolved
futures contract, so the first read after OpenD returns works again.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_screener_s3 as s3  # noqa: E402
from tools.moomoo.opend_quote_transport import OPEND_UNAVAILABLE, OpendCurrentKlineSession  # noqa: E402


class FakeContext:
    def __init__(self) -> None:
        self.closed = False

    def get_global_state(self):
        return 0, {"qot_logined": True}

    def get_market_snapshot(self, codes):
        return 0, []

    def close(self) -> None:
        self.closed = True


class FakeSdk:
    RET_OK = 0

    def __init__(self) -> None:
        self.contexts: list[FakeContext] = []

    def OpenQuoteContext(self, host, port):  # noqa: N802 — vendor SDK name
        context = FakeContext()
        self.contexts.append(context)
        return context


class TransportOutageTests(unittest.TestCase):
    def test_unreachable_opend_never_constructs_a_vendor_context(self) -> None:
        sdk = FakeSdk()
        session = OpendCurrentKlineSession(host="127.0.0.1", port=11111, sdk=sdk, reachable=lambda: False)
        self.assertEqual(session.fetch_future_quotes(["US.ESZ26"])["reason_code"], OPEND_UNAVAILABLE)
        self.assertEqual(session.fetch_future_contracts(["US.ESmain"])["reason_code"], OPEND_UNAVAILABLE)
        self.assertEqual(sdk.contexts, [])

    def test_outage_drops_the_stale_context_and_reconnect_opens_a_new_one(self) -> None:
        sdk, up = FakeSdk(), [True]
        session = OpendCurrentKlineSession(host="127.0.0.1", port=11111, sdk=sdk, reachable=lambda: up[0])
        self.assertIsNone(session.fetch_future_quotes(["US.ESZ26"])["reason_code"])
        up[0] = False
        self.assertEqual(session.fetch_future_quotes(["US.ESZ26"])["reason_code"], OPEND_UNAVAILABLE)
        self.assertTrue(sdk.contexts[0].closed)
        up[0] = True
        self.assertIsNone(session.fetch_future_quotes(["US.ESZ26"])["reason_code"])
        self.assertEqual(len(sdk.contexts), 2)

    def test_default_probe_reports_a_closed_port(self) -> None:
        import socket

        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        session = OpendCurrentKlineSession(host="127.0.0.1", port=port)
        self.assertEqual(session.fetch_future_quotes(["US.ESZ26"])["reason_code"], OPEND_UNAVAILABLE)


class FuturesContextOutageTests(unittest.TestCase):
    def test_provider_outage_is_not_cached_as_a_resolution(self) -> None:
        transport = s3.FuturesTransport(fail=OPEND_UNAVAILABLE)
        service = s3.futures_service(transport)
        down = service.read(sector="Healthcare", industry="Biotechnology", market_cap=5e10)["items"][0]
        self.assertEqual((down["contract"]["state"], down["contract"]["provider_reason"]), ("UNRESOLVED", OPEND_UNAVAILABLE))
        transport.fail = None
        up = service.read(sector="Healthcare", industry="Biotechnology", market_cap=5e10)["items"][0]
        self.assertEqual(up["contract"]["state"], "CURRENT")


if __name__ == "__main__":
    unittest.main()
