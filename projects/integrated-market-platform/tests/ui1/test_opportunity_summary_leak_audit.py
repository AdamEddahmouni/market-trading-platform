"""Ranked HTTP summary vs UI leak audit.

Public observational cards must not 500 solely because canonical
``instrument_id`` companions (``instrument_key``) or
``decision_support.authority`` look secret-shaped. Real secrets must still
500. Live, Grok, and broker orders stay off. ACK/WATCH stay fail-closed.
"""

from __future__ import annotations

import http.client
import json
import os
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from market_platform_foundation.market_data.live_config import live_observational_enabled
from market_platform_foundation.platform.security.leak_audit import (
    SecretLeakError,
    assert_no_secrets_in_payload,
    scan_snapshot,
)
from market_platform_foundation.ui_api.live_intelligence import bind_ui_api_intelligence
from market_platform_foundation.ui_api.news_ingest import NEWS_INGEST_ROUTE
from market_platform_foundation.ui_api.opportunity_projections import (
    apply_opportunity_ack,
    build_opportunities_summary_payload,
)
from market_platform_foundation.ui_api.operator_opportunity_state import reset_operator_acks
from market_platform_foundation.ui_api.server import UiApiHandler
from market_platform_foundation.ui_api.store import ReplayStore

from tests.ui1.test_ui_api import COLLECTION_ROOT

_LIVE_ENV_KEYS = (
    "IMP_LIVE_OBSERVATIONAL",
    "IMP_LIVE_EXECUTION",
    "IMP_LIVE_INTERNAL_SIMULATION",
    "IMP_MOOMOO_LIVE",
    "IMP_IBKR_LIVE",
    "IMP_FINVIZ_LIVE",
    "IMP_LIVE_FIXTURE_FEED",
)

_GROK_ENV_KEYS = (
    "IMP_GROK",
    "IMP_GROK_LIVE",
    "GROK_API_KEY",
    "XAI_API_KEY",
    "IMP_XAI_API_KEY",
)

_PUBLISHED = "2026-09-15T14:05:00Z"
_RETRIEVED = "2026-09-15T14:05:08Z"
LIVE_OE_NO_MUTATION = "LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE"


def _clear_live_and_grok_env() -> None:
    for key in _LIVE_ENV_KEYS + _GROK_ENV_KEYS:
        os.environ.pop(key, None)


def _qualifying_news_body() -> dict:
    return {
        "retrieved_time": _RETRIEVED,
        "articles": [
            {
                "headline": "Example Corp reports quarterly earnings",
                "published_time": _PUBLISHED,
                "url": "https://example.com/ranked-summary-leak-audit",
                "tickers": ["AAPL"],
                "publisher_source": "Wire",
                "provider_native_id": "ranked-summary-leak-audit-1",
            }
        ],
    }


def _http_json(port: int, method: str, path: str, *, body: dict | None = None) -> tuple[int, dict | str]:
    payload = b"" if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json", "Content-Length": str(len(payload))}
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request(method, path, body=payload, headers=headers)
    response = conn.getresponse()
    raw = response.read().decode("utf-8")
    conn.close()
    try:
        parsed: dict | str = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        parsed = raw
    return response.status, parsed


class RankedSummaryLeakAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        _clear_live_and_grok_env()
        reset_operator_acks()
        self.store = ReplayStore(collection_root=COLLECTION_ROOT)
        self.store.load()
        self.store.data_mode = "LIVE_OBSERVATIONAL"
        self.store.mode = "LIVE"
        bind_ui_api_intelligence(self.store)
        previous_store = getattr(UiApiHandler, "store", None)
        self._previous_store = previous_store
        UiApiHandler.store = self.store
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), UiApiHandler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self._runtime_patch = patch(
            "market_platform_foundation.market_data.live_runtime.get_live_runtime",
            return_value=None,
        )
        self._auth_patch = patch.object(UiApiHandler, "_authorize_request", return_value=True)
        self._runtime_patch.start()
        self._auth_patch.start()

    def tearDown(self) -> None:
        self._auth_patch.stop()
        self._runtime_patch.stop()
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)
        if self._previous_store is not None:
            UiApiHandler.store = self._previous_store
        elif hasattr(UiApiHandler, "store"):
            delattr(UiApiHandler, "store")
        _clear_live_and_grok_env()

    def test_real_secret_still_blocked_by_leak_audit(self) -> None:
        with self.assertRaises(SecretLeakError) as ctx:
            assert_no_secrets_in_payload(
                {"config": {"FINVIZ_API_KEY": "live-finviz-token-value"}},
                context="ui_payload",
            )
        self.assertIn("SECRET_SHAPED_KEY_WITH_LIVE_VALUE", str(ctx.exception))
        findings = scan_snapshot(
            {
                "items": [
                    {
                        "instrument_key": "AAPL",
                        "decision_support": {"authority": "DOWNSTREAM_RISK_NOT_RANKING"},
                    }
                ]
            }
        )
        reasons = {finding.reason for finding in findings}
        paths = {finding.path for finding in findings}
        self.assertIn("SECRET_SHAPED_KEY_WITH_LIVE_VALUE", reasons)
        self.assertIn("items[0].instrument_key", paths)
        self.assertIn("items[0].decision_support.authority", paths)

    def test_http_get_summary_500s_when_payload_contains_real_secret(self) -> None:
        def _leaky(_store, **_kwargs):
            return {"feed_status": "READY", "items": [{"api_key": "sk-live-secret-value"}]}

        with patch(
            "market_platform_foundation.ui_api.opportunity_projections.build_opportunities_summary_payload",
            side_effect=_leaky,
        ):
            status, body = _http_json(self.port, "GET", "/opportunities/summary")
        self.assertEqual(status, 500)
        self.assertIsInstance(body, dict)
        self.assertEqual(body.get("reason_code"), "UI_SECRET_LEAK_BLOCKED")

    def test_ranked_summary_after_news_ingest_does_not_500(self) -> None:
        self.assertFalse(live_observational_enabled())
        for key in _LIVE_ENV_KEYS + _GROK_ENV_KEYS:
            self.assertNotEqual(os.environ.get(key), "1", msg=f"{key} must stay off")

        status, ingest = _http_json(self.port, "POST", NEWS_INGEST_ROUTE, body=_qualifying_news_body())
        self.assertEqual(status, 200)
        self.assertIsInstance(ingest, dict)
        self.assertGreaterEqual(int(ingest.get("admitted_count") or 0), 1)
        self.assertGreaterEqual(int(ingest.get("opportunity_count") or 0), 1)
        opportunity_id = str((ingest.get("opportunity_ids") or [None])[0])

        summary_status, summary = _http_json(self.port, "GET", "/opportunities/summary")
        self.assertNotEqual(summary_status, 500)
        if isinstance(summary, dict):
            self.assertNotEqual(summary.get("reason_code"), "UI_SECRET_LEAK_BLOCKED")
        self.assertEqual(summary_status, 200)
        self.assertIsInstance(summary, dict)
        self.assertEqual(summary.get("feed_status"), "READY")
        items = summary.get("items") or []
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.get("identity_kind"), "OPPORTUNITY_V1")
        self.assertEqual(item.get("opportunity_id"), opportunity_id)
        self.assertEqual(item.get("instrument_id"), "AAPL")
        self.assertNotIn("instrument_key", item)
        support = item.get("decision_support") or {}
        self.assertNotIn("authority", support)
        self.assertNotIn("order_id", item)
        self.assertNotIn("order_id", support)
        self.assertNotIn("2026-07-21", str(summary.get("as_of_context", {})))
        assert_no_secrets_in_payload(summary, context="opportunities_summary")

        assembled = build_opportunities_summary_payload(self.store)
        self.assertEqual(assembled.get("feed_status"), "READY")
        assert_no_secrets_in_payload(assembled, context="in_process_ranked_summary")

    def test_live_remains_off_and_no_broker_order(self) -> None:
        self.assertFalse(live_observational_enabled())
        for key in _LIVE_ENV_KEYS + _GROK_ENV_KEYS:
            self.assertNotEqual(os.environ.get(key), "1", msg=f"{key} must stay off")
        source = __import__("inspect").getsource(self.test_ranked_summary_after_news_ingest_does_not_500)
        self.assertNotIn("submit_paper_order", source)
        self.assertNotIn("submit_broker_order", source)
        self.assertNotIn("/paper/orders", source)
        self.assertNotIn("/intelligence/ingest/enrichment", source)
        status, body = _http_json(self.port, "POST", "/paper/orders", body={"symbol": "AAPL", "qty": 1})
        self.assertNotEqual(status, 200)
        self.assertNotIn("order_id", str(body))

    def test_watch_remains_fail_closed_without_mutation_authority(self) -> None:
        status, ingest = _http_json(self.port, "POST", NEWS_INGEST_ROUTE, body=_qualifying_news_body())
        self.assertEqual(status, 200)
        self.assertIsInstance(ingest, dict)
        opportunity_id = str((ingest.get("opportunity_ids") or [None])[0])
        watch_status, watch_body = _http_json(
            port=self.port,
            method="POST",
            path=f"/opportunities/{opportunity_id}/watch",
            body={},
        )
        self.assertEqual(watch_status, 403)
        self.assertIn(LIVE_OE_NO_MUTATION, str(watch_body))
        with self.assertRaises(PermissionError) as ack_ctx:
            apply_opportunity_ack(self.store, row_id=opportunity_id, action="WATCHED")
        self.assertEqual(str(ack_ctx.exception), LIVE_OE_NO_MUTATION)


if __name__ == "__main__":
    unittest.main()
