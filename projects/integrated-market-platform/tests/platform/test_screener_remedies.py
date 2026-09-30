"""Screener setup: actionable remedies, the provider connect allowlist, and the setup checklist.

No process is started and nothing touches the network: OpenD diagnosis, catalog
invalidation, and every news provider are injected fakes.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.news.finbert_sentiment import FinbertSentiment  # noqa: E402
from market_platform_foundation.platform.security.route_policy import policy_for_route  # noqa: E402
from market_platform_foundation.ui_api import screener_remedies  # noqa: E402
from market_platform_foundation.ui_api.errors import CanonicalErrorCategory, canonical_error_category  # noqa: E402
from market_platform_foundation.ui_api.screener_config import validate_panel_layout  # noqa: E402
from market_platform_foundation.ui_api.screener_multi import MultiUniverseScreener  # noqa: E402
from market_platform_foundation.ui_api.screener_remedies import (  # noqa: E402
    connect_provider, opend_status, remedy_for, setup_checklist, with_remedy)
from tests.platform.test_screener_s11 import service  # noqa: E402


class RemedyTextTests(unittest.TestCase):
    def test_opend_down_says_what_is_wrong_and_offers_start(self):
        remedy = remedy_for("OPEND_UNAVAILABLE", scope="ETFs")
        self.assertEqual(remedy["title"], "moomoo OpenD isn't running")
        self.assertIn("load ETFs", remedy["step"])
        self.assertEqual(remedy["action"]["kind"], "CONNECT")
        self.assertEqual(remedy["action"]["provider"], "opend")
        self.assertEqual(remedy["reason"], "OPEND_UNAVAILABLE")

    def test_sec_user_agent_and_live_gates_have_one_step(self):
        sec = remedy_for("SEC_USER_AGENT_NOT_SET")
        self.assertIn("SEC_USER_AGENT", sec["step"])
        for code, flag in (("IMP_EDGAR_LIVE_NOT_SET", "IMP_EDGAR_LIVE=1"), ("IMP_NEWS_RSS_LIVE_NOT_SET", "IMP_NEWS_RSS_LIVE=1"),
                           ("FINVIZ_LIVE_DISABLED", "IMP_FINVIZ_LIVE=1"),
                           ("IMP_PUBLIC_RECORDS_LIVE_NOT_SET", "IMP_PUBLIC_RECORDS_LIVE=1")):
            self.assertIn(flag, remedy_for(code)["step"], code)
        self.assertEqual(remedy_for("IMP_NEWSAPI_LIVE_NOT_SET")["action"],
                         {"kind": "COMMAND", "command": "python tools/news/auth.py configure"})

    def test_unknown_or_empty_reason_has_no_remedy(self):
        self.assertIsNone(remedy_for(None))
        self.assertIsNone(remedy_for("HTTP_500"))
        # Generic codes are not guessed to be OpenD outside an OpenD-backed catalog.
        self.assertIsNone(remedy_for("PROVIDER_UNAVAILABLE"))

    def test_working_provider_gets_no_remedy_but_loading_model_does(self):
        self.assertNotIn("remedy", with_remedy({"state": "CURRENT", "reason": None}))
        self.assertNotIn("remedy", with_remedy({"state": "CURRENT", "reason": "PARTIAL_FEEDS:x"}))
        self.assertEqual(with_remedy({"state": "CURRENT", "reason": "MODEL_LOADING"})["remedy"]["reason"], "MODEL_LOADING")
        self.assertEqual(with_remedy({"state": "LIVE_DISABLED", "reason": "IMP_EDGAR_LIVE_NOT_SET"})["remedy"]["reason"],
                         "IMP_EDGAR_LIVE_NOT_SET")


class FeedRemedyTests(unittest.TestCase):
    def feed_with_catalog_error(self, universe: str, error: str):
        svc = service()
        svc._catalog = lambda _universe: ([], error)
        return svc.feed(universe=universe)

    def test_etf_and_futures_catalog_outage_points_at_opend(self):
        for universe, label in (("US_ETFS", "ETFs"), ("FUTURES", "Futures")):
            payload = self.feed_with_catalog_error(universe, "PROVIDER_UNAVAILABLE")
            self.assertEqual(payload["result_count"], 0)
            self.assertEqual(payload["remedy"]["reason"], "OPEND_UNAVAILABLE")
            self.assertIn(f"load {label}", payload["remedy"]["step"])
            self.assertEqual(payload["remedy"]["action"]["provider"], "opend")

    def test_healthy_feed_has_no_remedy(self):
        payload = service().feed(universe="US_EQUITIES")
        self.assertIsNone(payload["remedy"])

    def test_disabled_provider_rows_carry_their_step(self):
        payload = service(rss_env={}).feed(universe="US_ETFS")
        rss = next(item for item in payload["providers"] if item["id"] == "rss")
        self.assertEqual(rss["state"], "LIVE_DISABLED")
        self.assertIn("IMP_NEWS_RSS_LIVE=1", rss["remedy"]["step"])

    def test_sentiment_model_status_carries_remedy(self):
        payload = service(sentiment=FinbertSentiment(model_path="")).feed(universe="US_EQUITIES")
        self.assertEqual(payload["sentiment_model"]["remedy"]["reason"], "IMP_FINBERT_MODEL_PATH_NOT_SET")


class ConnectTests(unittest.TestCase):
    def setUp(self):
        screener_remedies._opend_cache = None
        self.invalidated = 0

    def invalidate(self):
        self.invalidated += 1

    def test_unknown_provider_is_refused(self):
        for provider in ("newsapi", "../../etc", "", "OPEND"):
            with self.assertRaises(ValueError):
                connect_provider(provider, diagnose=lambda start: self.fail("must not diagnose"), invalidate=self.invalidate)
        self.assertEqual(self.invalidated, 0)
        self.assertEqual(canonical_error_category("PROVIDER_NOT_CONNECTABLE"), CanonicalErrorCategory.VALIDATION_ERROR)

    def test_opend_ready_after_start_invalidates_cached_catalogs(self):
        calls = []

        def diagnose(start):
            calls.append(start)
            return {"status": "READY", "opend": {"running": True}}

        result = connect_provider("opend", diagnose=diagnose, invalidate=self.invalidate)
        self.assertEqual(calls, [True])
        self.assertEqual(result["state"], "CONNECTED")
        self.assertEqual(self.invalidated, 1)

    def test_opend_launched_but_not_logged_in_is_starting(self):
        result = connect_provider("opend", diagnose=lambda start: {"status": "PORT_UNREACHABLE", "opend": {"running": True}},
                                  invalidate=self.invalidate)
        self.assertEqual(result["state"], "STARTING")
        self.assertEqual(result["reason"], "PORT_UNREACHABLE")

    def test_opend_not_installed_returns_install_step(self):
        result = connect_provider("opend", diagnose=lambda start: {"status": "OPEN_D_NOT_INSTALLED", "opend": {"running": False}},
                                  invalidate=self.invalidate)
        self.assertEqual(result["state"], "FAILED")
        self.assertIn("Install moomoo OpenD", result["remedy"]["step"])
        self.assertIsNone(result["remedy"]["action"])

    def test_opend_status_is_cached_between_checks(self):
        calls = []
        now = [0.0]

        def diagnose(start):
            calls.append(start)
            return {"status": "OPEN_D_NOT_RUNNING"}

        first = opend_status(diagnose=diagnose, clock=lambda: now[0])
        opend_status(diagnose=diagnose, clock=lambda: now[0])
        self.assertEqual(calls, [False])
        self.assertEqual(first, {"state": "UNAVAILABLE", "reason": "OPEN_D_NOT_RUNNING"})
        now[0] = 60.0
        opend_status(diagnose=diagnose, clock=lambda: now[0])
        self.assertEqual(calls, [False, False])


def checklist(env, opend):
    return setup_checklist(env=env.get, opend=lambda: opend, service=service(),
                           key_gates=lambda: {"newsapi": (False, None), "finnhub": (True, None)})


class CatalogRecoveryTests(unittest.TestCase):
    """OpenD coming back is picked up within a poll, not after the 15-minute catalog TTL."""

    def screener(self):
        self.now = [0.0]
        self.calls = 0
        self.up = False

        test = self

        class Transport:
            def fetch_future_contracts(self, _roots):
                test.calls += 1
                return {"rows": []} if test.up else {"reason_code": "OPEND_UNAVAILABLE"}

        return MultiUniverseScreener(transport_getter=lambda: Transport(), clock=lambda: self.now[0])

    def test_failed_catalog_is_retried_after_a_short_ttl(self):
        screener = self.screener()
        self.assertEqual(screener._catalog("FUTURES")[2], "OPEND_UNAVAILABLE")
        self.now[0] = 10.0
        screener._catalog("FUTURES")
        self.assertEqual(self.calls, 1)
        self.up = True
        self.now[0] = 31.0
        self.assertIsNone(screener._catalog("FUTURES")[2])
        self.assertEqual(self.calls, 2)
        self.now[0] = 600.0
        screener._catalog("FUTURES")
        self.assertEqual(self.calls, 2)   # a good catalog keeps the long TTL

    def test_invalidate_retries_at_once(self):
        screener = self.screener()
        screener._catalog("FUTURES")
        self.up = True
        screener.invalidate_catalogs()
        self.assertIsNone(screener._catalog("FUTURES")[2])
        self.assertEqual(self.calls, 2)


class SetupChecklistTests(unittest.TestCase):
    def test_rows_cover_each_free_capability_with_state_and_step(self):
        payload = checklist({}, {"state": "UNAVAILABLE", "reason": "OPEN_D_NOT_RUNNING"})
        rows = {row["id"]: row for row in payload["rows"]}
        self.assertEqual(set(rows), {"opend", "newsapi", "finnhub", "rss", "sec_filings", "public_records", "senate_efd",
                                     "finbert", "ai"})
        self.assertTrue(rows["opend"]["connectable"])
        self.assertEqual(rows["opend"]["remedy"]["action"]["kind"], "CONNECT")
        self.assertEqual(rows["sec_filings"]["reason"], "IMP_EDGAR_LIVE_NOT_SET")
        self.assertEqual(rows["senate_efd"]["reason"], "SENATE_EFD_REQUIRES_INTERACTIVE_TERMS_ACCEPTANCE")
        self.assertIsNotNone(rows["senate_efd"]["remedy"])
        self.assertFalse(rows["rss"]["connectable"])
        self.assertEqual(rows["newsapi"]["reason"], "IMP_NEWSAPI_LIVE_NOT_SET")
        self.assertEqual(rows["finnhub"]["reason"], "FINNHUB_API_KEY_NOT_SET")
        for row in payload["rows"]:
            if row["state"] != "CURRENT":
                self.assertIsNotNone(row["remedy"], row["id"])
        self.assertEqual(payload["total"], len(payload["rows"]))

    def test_sec_user_agent_step_once_edgar_is_enabled(self):
        payload = checklist({"IMP_EDGAR_LIVE": "1"}, {"state": "CURRENT", "reason": None})
        rows = {row["id"]: row for row in payload["rows"]}
        self.assertEqual(rows["sec_filings"]["reason"], "SEC_USER_AGENT_NOT_SET")
        self.assertIsNone(rows["opend"]["remedy"])
        self.assertFalse(rows["opend"]["connectable"])

    def test_routes_and_panel(self):
        self.assertEqual(policy_for_route("GET", "/screener/setup").capability, "state.read")
        self.assertEqual(policy_for_route("POST", "/screener/providers/opend/connect").capability, "state.write")
        layout = validate_panel_layout({"version": 1, "open_panels": ["setup"], "active_panel": "setup", "dock_height": 300,
                                        "dockview_layout": None})
        self.assertEqual(layout["open_panels"], ["setup"])


if __name__ == "__main__":
    unittest.main()
