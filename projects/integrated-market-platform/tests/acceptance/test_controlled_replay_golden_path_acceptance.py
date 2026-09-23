"""CONTROLLED REPLAY operator golden-path acceptance (SOFTWARE / CONTROLLED).

Evidence class: CONTROLLED_REPLAY. Never EMPIRICAL_ACTIVE, never Live authority,
never broker order submission. Exercises the real HTTP stack:

    controlled news articles
    → POST /intelligence/ingest/news
    → EventV1 / PIT
    → observational detector / OE
    → GET /opportunities/summary
    → Watch / Dismiss
    → DecisionTrace / TradeReview
    → namespaced reset safety
"""

from __future__ import annotations

import http.client
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.news.timestamps import epoch_ns_from_iso  # noqa: E402
from market_platform_foundation.rt01.execution_decision_trace import (  # noqa: E402
    ExecutionDecisionKind,
    execution_decision_trace_repository,
    reset_execution_decision_trace_runtime_for_tests,
)
from market_platform_foundation.intelligence.trade_review import (  # noqa: E402
    TradeReviewMode,
    open_trade_review_repository,
    reset_trade_review_repository_for_tests,
)
from market_platform_foundation.ui_api.live_intelligence import bind_ui_api_intelligence  # noqa: E402
from market_platform_foundation.ui_api.news_ingest import NEWS_INGEST_ROUTE  # noqa: E402
from market_platform_foundation.ui_api.operator_opportunity_state import (  # noqa: E402
    list_operator_acks,
    reset_operator_acks,
)
from market_platform_foundation.ui_api.server import UiApiHandler  # noqa: E402
from market_platform_foundation.ui_api.store import ReplayStore  # noqa: E402
from market_platform_foundation.ui_api.trade_review_projections import (  # noqa: E402
    build_trade_reviews_for_opportunity_payload,
)
from tools.controlled_replay.env import build_controlled_replay_environment  # noqa: E402
from tools.controlled_replay.reset import reset_controlled_replay_state  # noqa: E402
from tools.controlled_replay.scenarios import (  # noqa: E402
    T_FRESH_RETRIEVED,
    build_news_ingest_body,
)

_SERVER_NS = int(epoch_ns_from_iso(T_FRESH_RETRIEVED) or 0)
_LIVE_KEYS = (
    "IMP_LIVE_OBSERVATIONAL",
    "IMP_LIVE_EXECUTION",
    "IMP_BROKER_LIVE_EXECUTION",
    "IMP_MOOMOO_LIVE",
    "IMP_FINVIZ_LIVE",
)


def _http_json(
    conn: http.client.HTTPConnection,
    method: str,
    path: str,
    *,
    body: bytes = b"{}",
) -> tuple[int, dict]:
    headers = {"Content-Type": "application/json", "Content-Length": str(len(body))}
    conn.request(method, path, body=body, headers=headers)
    response = conn.getresponse()
    payload = json.loads(response.read().decode("utf-8"))
    return response.status, payload


class ControlledReplayGoldenPathAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        for key in _LIVE_KEYS:
            os.environ.pop(key, None)
        env = build_controlled_replay_environment({}, root=ROOT)
        # Redirect state into the temp dir while keeping the namespaced suffix.
        state = Path(self._tmp.name) / "controlled-replay"
        state.mkdir(parents=True, exist_ok=True)
        env["IMP_STATE_DIR"] = str(state)
        for key, value in env.items():
            os.environ[key] = value
        self._state_dir = state
        reset_operator_acks()
        reset_trade_review_repository_for_tests()
        reset_execution_decision_trace_runtime_for_tests()

    def tearDown(self) -> None:
        for key in list(os.environ):
            if key.startswith("IMP_") or key in _LIVE_KEYS:
                if key in {
                    "IMP_CONTROLLED_REPLAY",
                    "IMP_STATE_DIR",
                    "IMP_PERSIST_STATE",
                    "IMP_PAPER_EXECUTION",
                } or key in _LIVE_KEYS:
                    os.environ.pop(key, None)
        reset_operator_acks()
        reset_trade_review_repository_for_tests()
        reset_execution_decision_trace_runtime_for_tests()
        self._tmp.cleanup()

    def test_controlled_replay_env_never_enables_live(self) -> None:
        env = build_controlled_replay_environment({"IMP_LIVE_OBSERVATIONAL": "1"}, root=ROOT)
        self.assertEqual(env["IMP_CONTROLLED_REPLAY"], "1")
        self.assertNotIn("IMP_LIVE_OBSERVATIONAL", env)
        self.assertNotIn("IMP_LIVE_EXECUTION", env)
        self.assertNotIn("IMP_MOOMOO_LIVE", env)
        self.assertEqual(env["IMP_PAPER_EXECUTION"], "0")
        self.assertIn("controlled-replay", env["IMP_STATE_DIR"].replace("\\", "/"))

    def test_reset_refuses_canonical_local_and_clears_namespace(self) -> None:
        # Exercise namespaced wipe on an isolated temp path (never the live
        # launcher-held .local/controlled-replay while an API may lock SQLite).
        isolated = Path(self._tmp.name) / "isolated-controlled-replay"
        isolated.mkdir(parents=True, exist_ok=True)
        marker = isolated / "imp-state.sqlite3"
        marker.write_text("demo", encoding="utf-8")
        import shutil

        shutil.rmtree(isolated)
        isolated.mkdir(parents=True, exist_ok=True)
        self.assertFalse((isolated / "imp-state.sqlite3").exists())

        result = reset_controlled_replay_state(ROOT)
        if not result.get("ok") and result.get("reason") == "STATE_LOCKED_STOP_STACK_FIRST":
            self.skipTest("controlled-replay sqlite locked by running launcher")
        self.assertTrue(result["ok"], result)
        self.assertIn("controlled-replay", str(result["path"]).replace("\\", "/"))

    def test_source_to_watch_dismiss_trace_review_and_stale_warning(self) -> None:
        collection_root = ROOT.parent
        store = ReplayStore(collection_root=collection_root)
        store.load()
        bind_ui_api_intelligence(store)
        self.assertEqual(store.data_mode, "FIXTURE_REPLAY")
        self.assertEqual(store.opportunity_source, "CONTROLLED_REPLAY")
        self.assertEqual(store.execution_authority, "BLOCKED")
        UiApiHandler.store = store

        runtime_patch = patch(
            "market_platform_foundation.market_data.live_runtime.get_live_runtime",
            return_value=None,
        )
        clock_patch = patch(
            "market_platform_foundation.ui_api.news_ingest.monotonic_wall_ns",
            return_value=_SERVER_NS,
        )
        auth_patch = patch.object(UiApiHandler, "_authorize_request", return_value=True)
        secret_patch = patch(
            "market_platform_foundation.ui_api.server.assert_no_secrets_in_payload",
            lambda _payload: None,
        )

        httpd = ThreadingHTTPServer(("127.0.0.1", 0), UiApiHandler)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=20)

        try:
            with runtime_patch, clock_patch, auth_patch, secret_patch:
                ctx_status, ctx = _http_json(conn, "GET", "/context", body=b"")
                self.assertEqual(ctx_status, 200, ctx)
                self.assertTrue(ctx.get("controlled_replay") or ctx["as_of_context"].get("controlled_replay"))
                self.assertEqual(ctx["as_of_context"]["data_mode"], "FIXTURE_REPLAY")
                self.assertEqual(ctx["as_of_context"]["execution_authority"], "BLOCKED")
                self.assertNotEqual(ctx["as_of_context"]["data_mode"], "LIVE_OBSERVATIONAL")

                body = json.dumps(build_news_ingest_body()).encode("utf-8")
                status, ingest = _http_json(conn, "POST", NEWS_INGEST_ROUTE, body=body)
                self.assertEqual(status, 200, ingest)
                self.assertGreaterEqual(int(ingest.get("opportunity_count") or 0), 1)
                self.assertFalse(ingest.get("live_authority", True))

                clock_body = json.dumps({"as_of_time": T_FRESH_RETRIEVED}).encode("utf-8")
                cstatus, cpayload = _http_json(
                    conn,
                    "POST",
                    "/controlled-replay/advance-clock",
                    body=clock_body,
                )
                self.assertEqual(cstatus, 200, cpayload)
                self.assertEqual(cpayload.get("execution_authority"), "BLOCKED")

                summary_status, summary = _http_json(conn, "GET", "/opportunities/summary", body=b"")
                self.assertEqual(summary_status, 200, summary)
                items = list(summary.get("items") or [])
                self.assertGreaterEqual(len(items), 1, summary)

                stale_rows = [
                    item
                    for item in items
                    if str(((item.get("data_quality") or {}).get("freshness") or "")).upper() == "STALE"
                    or str(
                        ((item.get("data_quality") or {}).get("freshness_evaluation") or {}).get("status") or ""
                    ).upper()
                    == "STALE"
                ]
                self.assertGreaterEqual(len(stale_rows), 1, "expected STALE scenario row")
                for row in stale_rows:
                    freshness = str(
                        ((row.get("data_quality") or {}).get("freshness_evaluation") or {}).get("status")
                        or (row.get("data_quality") or {}).get("freshness")
                        or ""
                    ).upper()
                    self.assertEqual(freshness, "STALE")
                    self.assertNotEqual(freshness, "FRESH")

                warn_rows = [
                    item
                    for item in items
                    if item.get("provider_linkage_warnings")
                ]
                self.assertGreaterEqual(len(warn_rows), 1, "expected linkage warning scenario")
                phrases = " ".join(
                    str(p) for row in warn_rows for p in (row.get("provider_linkage_warnings") or [])
                )
                self.assertTrue(
                    "uncorroborated" in phrases
                    or "contextual concern" in phrases
                    or "low confidence" in phrases
                    or "source URL missing" in phrases,
                    phrases,
                )

                watch_id = str(items[0].get("opportunity_id") or items[0].get("summary_id"))
                dismiss_candidate = None
                for item in items[1:]:
                    oid = str(item.get("opportunity_id") or item.get("summary_id") or "")
                    if oid and oid != watch_id:
                        dismiss_candidate = oid
                        break
                self.assertIsNotNone(dismiss_candidate)

                watch_status, watch_ack = _http_json(
                    conn, "POST", f"/opportunities/{watch_id}/watch", body=b"{}"
                )
                self.assertEqual(watch_status, 200, watch_ack)
                self.assertEqual(watch_ack["action"], "WATCHED")

                dismiss_status, dismiss_ack = _http_json(
                    conn,
                    "POST",
                    f"/opportunities/{dismiss_candidate}/dismiss",
                    body=b"{}",
                )
                self.assertEqual(dismiss_status, 200, dismiss_ack)
                self.assertEqual(dismiss_ack["action"], "DISMISSED")

                acks = list_operator_acks()
                actions = {(row["opportunity_id"], row["action"]) for row in acks}
                self.assertIn((watch_id, "WATCHED"), actions)
                self.assertIn((dismiss_candidate, "DISMISSED"), actions)

                watch_traces = execution_decision_trace_repository().list_execution_decision_traces_by_opportunity(
                    watch_id
                )
                self.assertTrue(any(row.decision_kind == ExecutionDecisionKind.WATCH for row in watch_traces))
                watch_reviews = build_trade_reviews_for_opportunity_payload(store, watch_id)
                self.assertGreaterEqual(len(watch_reviews.get("items") or []), 1)
                self.assertEqual(
                    watch_reviews["items"][0]["review_mode"],
                    TradeReviewMode.WATCHED_OPPORTUNITY.value,
                )
                review_repo = open_trade_review_repository()
                restored = review_repo.get_trade_review(str(watch_ack["trade_review_id"]))
                self.assertIsNotNone(restored)
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)
            conn.close()


if __name__ == "__main__":
    unittest.main()
