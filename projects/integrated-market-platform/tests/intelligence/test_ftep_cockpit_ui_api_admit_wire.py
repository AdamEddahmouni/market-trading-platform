"""Two-process proof: FTEP prospective rows → HTTP → UiApiHandler store → ranked GET."""

from __future__ import annotations

import http.client
import json
import os
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from market_platform_foundation.intelligence.paper_forward_bridge.ftep_catalyst_watch import (
    collect_ftep_catalyst_watch,
)
from market_platform_foundation.intelligence.paper_forward_bridge.ftep_prospective_catalyst_ingress import (
    CLASS_SUCCESS,
    ProspectiveCatalystIngressResult,
)
from market_platform_foundation.local_state.paths import REPO_ROOT
from market_platform_foundation.news.timestamps import epoch_ns_from_iso
from market_platform_foundation.ui_api.cockpit_admit import (
    build_news_ingest_body_from_prospective_ingress,
    post_prospective_ingress_to_running_ui_api,
)
from market_platform_foundation.ui_api.live_intelligence import bind_ui_api_intelligence
from market_platform_foundation.ui_api.news_ingest import NEWS_INGEST_ROUTE
from market_platform_foundation.ui_api.server import UiApiHandler
from market_platform_foundation.ui_api.store import ReplayStore

from tests.ui1.test_ui_api import COLLECTION_ROOT

_PUBLISHED = "2026-09-15T14:00:05Z"
_RETRIEVED = "2026-09-15T14:00:08Z"
_SERVER = "2026-09-15T14:00:10Z"


def _sample_ingress() -> ProspectiveCatalystIngressResult:
    return ProspectiveCatalystIngressResult(
        attempted=True,
        ready=True,
        reason=None,
        source_label="live:finviz_elite_prospective",
        rows=(
            {
                "symbol": "AAPL",
                "headline": "Example Corp reports quarterly earnings",
                "published_time": _PUBLISHED,
                "retrieved_time": _RETRIEVED,
                "source_event_id": "evt-http-wire-1",
            },
        ),
        stats={"as_of_ns": 999_999_999_999_999_999},
        classification=CLASS_SUCCESS,
    )


class FtepCockpitUiApiAdmitWireTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ReplayStore(collection_root=COLLECTION_ROOT)
        self.store.load()
        self.store.data_mode = "LIVE_OBSERVATIONAL"
        self.store.mode = "LIVE"
        bind_ui_api_intelligence(self.store)
        UiApiHandler.store = self.store
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), UiApiHandler)
        self.port = self.httpd.server_address[1]
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self._runtime_patch = patch(
            "market_platform_foundation.market_data.live_runtime.get_live_runtime",
            return_value=None,
        )
        self._runtime_patch.start()
        self._server_ns = int(epoch_ns_from_iso(_SERVER) or 0)
        self._clock_patch = patch(
            "market_platform_foundation.ui_api.news_ingest.monotonic_wall_ns",
            return_value=self._server_ns,
        )
        self._clock_patch.start()
        self._auth_patch = patch.object(UiApiHandler, "_authorize_request", return_value=True)
        self._auth_patch.start()
        self._secret_patch = patch(
            "market_platform_foundation.ui_api.server.assert_no_secrets_in_payload",
            lambda _payload: None,
        )
        self._secret_patch.start()

    def tearDown(self) -> None:
        self._secret_patch.stop()
        self._auth_patch.stop()
        self._clock_patch.stop()
        self._runtime_patch.stop()
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)

    def test_news_ingest_body_never_includes_forged_server_receive(self) -> None:
        body = build_news_ingest_body_from_prospective_ingress(_sample_ingress())
        self.assertNotIn("server_received_time_ns", body)
        for article in body.get("articles") or []:
            self.assertNotIn("server_received_time_ns", article)

    def test_ui_api_down_fail_closed(self) -> None:
        dead_base = "http://127.0.0.1:1"
        receipt = post_prospective_ingress_to_running_ui_api(
            _sample_ingress(),
            base_url=dead_base,
            timeout_s=1.0,
        )
        self.assertFalse(receipt.get("ok"))
        self.assertEqual(receipt.get("reason"), "UI_API_COCKPIT_ADMIT_UNREACHABLE")
        self.assertEqual(receipt.get("opportunity_count"), 0)

    def test_ftep_ingress_http_post_then_summary_get_on_handler_store(self) -> None:
        receipt = post_prospective_ingress_to_running_ui_api(
            _sample_ingress(),
            base_url=self.base_url,
        )
        self.assertTrue(receipt.get("ok"))
        self.assertEqual(receipt.get("opportunity_count"), 1)
        opp_id = receipt["opportunity_ids"][0]
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", "/opportunities/summary")
        response = conn.getresponse()
        self.assertEqual(response.status, 200)
        summary = json.loads(response.read().decode("utf-8"))
        self.assertEqual(summary["feed_status"], "READY")
        ids = [row.get("opportunity_id") for row in summary.get("items") or []]
        self.assertIn(opp_id, ids)

    def test_forged_server_receive_rejected_on_post(self) -> None:
        body = build_news_ingest_body_from_prospective_ingress(_sample_ingress())
        body["server_received_time_ns"] = self._server_ns
        payload = json.dumps(body).encode("utf-8")
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request(
            "POST",
            NEWS_INGEST_ROUTE,
            body=payload,
            headers={"Content-Type": "application/json", "Content-Length": str(len(payload))},
        )
        response = conn.getresponse()
        self.assertNotEqual(response.status, 200)

    def test_collect_ftep_catalyst_watch_posts_to_serving_ui_api(self) -> None:
        ingress = _sample_ingress()
        status = {
            "us_equity_rth_open": True,
            "governed_session_count": 2,
            "empirical_lock_count": 0,
        }
        with (
            patch(
                "market_platform_foundation.intelligence.paper_forward_bridge."
                "ftep_catalyst_watch.collect_ftep_campaign_status",
                return_value=status,
            ),
            patch(
                "market_platform_foundation.intelligence.paper_forward_bridge."
                "ftep_catalyst_watch.load_governed_session_ids_from_evidence",
                return_value=(["fts-A"], "evidence.jsonl"),
            ),
            patch(
                "market_platform_foundation.intelligence.paper_forward_bridge."
                "ftep_prospective_catalyst_ingress.collect_finviz_prospective_attention_rows",
                return_value=ingress,
            ),
            patch(
                "market_platform_foundation.ui_api.cockpit_admit.resolve_ui_api_base_url",
                return_value=self.base_url,
            ),
        ):
            payload = collect_ftep_catalyst_watch(REPO_ROOT, "FTEP-V1-002", live_ingress=True)
        self.assertFalse(payload["dry_run"])
        self.assertEqual(payload["ingress_outcome"], "COCKPIT_ADMIT_HTTP_OK")
        self.assertEqual(payload["cockpit_admit_hop"], "HTTP_UI_API")
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", "/opportunities/summary")
        response = conn.getresponse()
        self.assertEqual(response.status, 200)
        summary = json.loads(response.read().decode("utf-8"))
        self.assertEqual(summary["feed_status"], "READY")
        self.assertGreaterEqual(len(summary.get("items") or []), 1)


if __name__ == "__main__":
    unittest.main()
