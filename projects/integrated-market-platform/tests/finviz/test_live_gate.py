"""The Finviz live gate is enforced at the transport: credentials alone never cause a request."""

from __future__ import annotations

import os
import sys
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.finviz import http_client
from market_platform_foundation.finviz.config import finviz_feed_disabled
from market_platform_foundation.finviz.http_client import FinvizLiveDisabled, ReplayNetworkBlocked, UrllibSession, urllib_get
from market_platform_foundation.finviz.login_recovery import recover_token_via_login
from market_platform_foundation.finviz.news import FinvizNewsClient
from market_platform_foundation.finviz.options import FinvizOptionsClient
from market_platform_foundation.finviz.request_manager import FinvizRequestManager
from market_platform_foundation.finviz.screener import FinvizScreenerClient

FAKE = "FAKE-TOKEN-FOR-GATE-TEST-0000"


class _RecordingManager:
    def __init__(self) -> None:
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(url)
        return 200, "No.,Ticker\n1,AAPL\n", {"cached": False}

    def clear_cache(self) -> None:
        pass


class FinvizLiveGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.opened = []

        def refuse(*args, **kwargs):
            self.opened.append(args)
            raise AssertionError("NETWORK_ATTEMPTED")

        patches = [mock.patch.object(urllib.request, "urlopen", refuse),
                   mock.patch.object(urllib.request.OpenerDirector, "open", refuse),
                   mock.patch.dict(os.environ, {"FINVIZ_API_KEY": FAKE, "IMP_CONTROLLED_REPLAY": "0"})]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        os.environ.pop("IMP_FINVIZ_LIVE", None)
        for feed in ("SCREENER", "NEWS", "OPTIONS"):
            os.environ.pop(f"IMP_FINVIZ_{feed}_LIVE", None)

    def test_transports_refuse_without_live_gate(self) -> None:
        for value in (None, "0", "false", ""):
            if value is None:
                os.environ.pop("IMP_FINVIZ_LIVE", None)
            else:
                os.environ["IMP_FINVIZ_LIVE"] = value
            with self.assertRaises(FinvizLiveDisabled):
                urllib_get("https://elite.finviz.com/export/screener", params={"auth": FAKE})
            with self.assertRaises(FinvizLiveDisabled):
                UrllibSession().get("https://finviz.com/login.ashx")
            with self.assertRaises(FinvizLiveDisabled):
                UrllibSession().post("https://finviz.com/login_submit.ashx", data={"email": "x"})
        self.assertEqual(self.opened, [])
        self.assertTrue(issubclass(FinvizLiveDisabled, ReplayNetworkBlocked))

    def test_clients_with_credentials_report_live_disabled_and_make_no_request(self) -> None:
        os.environ["IMP_FINVIZ_LIVE"] = "0"
        manager = FinvizRequestManager(min_interval_s=0.0)
        screener = FinvizScreenerClient(api_key=FAKE, request_manager=manager)
        self.assertTrue(screener.configured)  # a stored credential is present ...
        self.assertEqual(screener.fetch_export(filter_expr="", force=True)["error"], "LIVE_DISABLED")  # ... but not authorization
        self.assertEqual(screener.fetch_symbol("AAPL", force=True)["error"], "LIVE_DISABLED")
        self.assertEqual(FinvizNewsClient(api_key=FAKE, request_manager=manager).fetch_news(force=True)["error"], "LIVE_DISABLED")
        self.assertEqual(FinvizOptionsClient(api_key=FAKE, request_manager=manager).fetch_chain("AAPL", force=True)["error"],
                         "LIVE_DISABLED")
        self.assertEqual(manager.metrics.request_count, 0)
        self.assertEqual(self.opened, [])

    def test_login_recovery_and_token_validation_make_no_request(self) -> None:
        os.environ["IMP_FINVIZ_LIVE"] = "0"
        with self.assertRaises(FinvizLiveDisabled):
            recover_token_via_login(username="user@example.com", password="not-a-password")
        manager = FinvizRequestManager(min_interval_s=0.0)
        self.assertFalse(manager._credential_manager.validate_token(FAKE, http_get=http_client.urllib_get))
        self.assertEqual(self.opened, [])

    def test_one_feed_can_be_withheld_while_others_stay_enabled(self) -> None:
        os.environ["IMP_FINVIZ_LIVE"] = "1"
        os.environ["IMP_FINVIZ_OPTIONS_LIVE"] = "0"
        self.assertTrue(finviz_feed_disabled("OPTIONS"))
        self.assertFalse(finviz_feed_disabled("SCREENER"))
        recording = _RecordingManager()
        options = FinvizOptionsClient(api_key=FAKE, request_manager=recording).fetch_chain("AAPL")
        self.assertEqual(options["error"], "LIVE_DISABLED")
        self.assertEqual(recording.calls, [])
        screener = FinvizScreenerClient(api_key=FAKE, request_manager=recording).fetch_export(filter_expr="")
        self.assertTrue(screener["success"])
        self.assertEqual(len(recording.calls), 1)
        with self.assertRaises(ValueError):
            finviz_feed_disabled("PORTFOLIO")

    def test_live_gate_on_reaches_the_transport(self) -> None:
        os.environ["IMP_FINVIZ_LIVE"] = "1"
        with self.assertRaises(AssertionError):  # the patched transport is reached only when authorized
            urllib_get("https://elite.finviz.com/export/screener", params={"auth": FAKE})
        self.assertEqual(len(self.opened), 1)


class FinvizDiagnosticsGateTests(unittest.TestCase):
    def test_diagnostics_distinguish_disabled_from_missing_credentials(self) -> None:
        from market_platform_foundation.ui_api import discovery_projections

        class _Health:
            credential_present = True
            source = mock.Mock(value="PRIVATE_FILE")
            state = mock.Mock(value="LOADED")
            finviz_credential_generation = 0
            last_validated = last_rotation = last_auth_error = None
            recovery_mode = mock.Mock(value="AUTO")
            automatic_recovery = "AUTOMATIC"

        credential = mock.Mock(health=mock.Mock(return_value=_Health()))
        manager = mock.Mock(metrics=mock.Mock(request_count=0, cache_hits=0, cache_misses=0, auth_recoveries=0))
        with mock.patch.object(discovery_projections, "get_finviz_credential_manager", return_value=credential), \
                mock.patch.object(discovery_projections, "get_finviz_request_manager", return_value=manager):
            with mock.patch.dict(os.environ, {"IMP_FINVIZ_LIVE": "0"}):
                off = discovery_projections.build_finviz_diagnostics_payload()
            with mock.patch.dict(os.environ, {"IMP_FINVIZ_LIVE": "1", "IMP_FINVIZ_OPTIONS_LIVE": "0"}):
                on = discovery_projections.build_finviz_diagnostics_payload()
        self.assertEqual((off["connection"], off["screener"], off["news"], off["options"], off["live_enabled"]),
                         ("LIVE_DISABLED", "LIVE_DISABLED", "LIVE_DISABLED", "LIVE_DISABLED", False))
        self.assertTrue(off["configured"])
        self.assertEqual(on["feeds"], {"screener": "ENABLED", "news": "ENABLED", "options": "LIVE_DISABLED"})
        self.assertEqual(on["options"], "LIVE_DISABLED")
        self.assertNotEqual(on["connection"], "LIVE_DISABLED")


if __name__ == "__main__":
    unittest.main()
