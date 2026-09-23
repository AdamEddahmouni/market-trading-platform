"""CONTROLLED REPLAY operator golden-path acceptance.

Evidence class: SOFTWARE_CONTROLLED / FIXTURE_REPLAY only.
Never EMPIRICAL_ACTIVE, never prospective market evidence, never Live authority,
never broker order submission. Exercises the real HTTP stack in namespaced
resettable Controlled Replay state:

    controlled source
    → POST /intelligence/ingest/news
    → EventV1 / PIT
    → observational detector / OE
    → durable opportunity
    → Radar (/opportunities/summary)
    → Watch / Dismiss
    → DecisionTrace / TradeReview
    → namespaced reset safety

Paper preview is out of scope for this acceptance lane.
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

    def test_context_gate_refuses_live_observational(self) -> None:
        from tools.controlled_replay.cli import verify_controlled_replay_context

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps(
                    {
                        "as_of_context": {
                            "data_mode": "LIVE_OBSERVATIONAL",
                            "controlled_replay": False,
                            "execution_authority": "BLOCKED",
                        }
                    }
                ).encode("utf-8")

        with patch("urllib.request.urlopen", return_value=_Resp()):
            gate = verify_controlled_replay_context(api_base="http://127.0.0.1:8766")
        self.assertFalse(gate["ok"])
        self.assertEqual(gate["reason"], "LIVE_OBSERVATIONAL_REFUSED")

    def test_reset_refuses_non_namespaced_and_clears_namespace(self) -> None:
        # Refuse paths that are not the controlled-replay namespace.
        with patch(
            "tools.controlled_replay.reset.controlled_replay_state_dir",
            return_value=(ROOT / ".local").resolve(),
        ):
            refused_canonical = reset_controlled_replay_state(ROOT)
        self.assertFalse(refused_canonical.get("ok"))
        self.assertEqual(refused_canonical.get("reason"), "REFUSED_CANONICAL_LOCAL")

        with patch(
            "tools.controlled_replay.reset.controlled_replay_state_dir",
            return_value=(Path(self._tmp.name) / "other-state").resolve(),
        ):
            refused_marker = reset_controlled_replay_state(ROOT)
        self.assertFalse(refused_marker.get("ok"))
        self.assertEqual(refused_marker.get("reason"), "REFUSED_PATH_NOT_NAMESPACED")

        # Exercise namespaced wipe on an isolated temp path (never a running
        # launcher-held .local/controlled-replay while an API may lock SQLite).
        with patch(
            "tools.controlled_replay.reset.controlled_replay_state_dir",
            return_value=(Path(self._tmp.name) / "isolated-controlled-replay").resolve(),
        ):
            isolated = Path(self._tmp.name) / "isolated-controlled-replay"
            isolated.mkdir(parents=True, exist_ok=True)
            (isolated / "imp-state.sqlite3").write_text("demo", encoding="utf-8")
            result = reset_controlled_replay_state(ROOT)
        self.assertTrue(result["ok"], result)
        self.assertIn("controlled-replay", str(result["path"]).replace("\\", "/"))
        self.assertFalse((isolated / "imp-state.sqlite3").exists())
        self.assertTrue(isolated.exists())

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
                # Controlled Replay must never be labeled as prospective/empirical.
                as_of = ctx["as_of_context"]
                self.assertTrue(as_of.get("not_live_market_data") or ctx.get("not_live_market_data"))
                self.assertNotEqual(str(as_of.get("data_mode") or ""), "EMPIRICAL_ACTIVE")
                self.assertNotIn(
                    str(as_of.get("evidence_class") or "").upper(),
                    {
                        "EMPIRICAL_ACTIVE",
                        "PROSPECTIVE_FORWARD",
                        "PROSPECTIVE_MARKET",
                        "LIVE_MARKET_DATA",
                    },
                )
                self.assertNotIn(
                    str(as_of.get("data_mode") or "").upper(),
                    {
                        "EMPIRICAL_ACTIVE",
                        "PROSPECTIVE_FORWARD",
                        "PROSPECTIVE_MARKET",
                        "LIVE_OBSERVATIONAL",
                    },
                )

                body = json.dumps(build_news_ingest_body()).encode("utf-8")
                status, ingest = _http_json(conn, "POST", NEWS_INGEST_ROUTE, body=body)
                self.assertEqual(status, 200, ingest)
                self.assertGreaterEqual(int(ingest.get("admitted_count") or 0), 1, ingest)
                self.assertGreaterEqual(int(ingest.get("opportunity_count") or 0), 1, ingest)
                self.assertFalse(ingest.get("live_authority", True))
                # Zero-qualifying controlled source fails closed at admit (not minted).
                skipped = list(ingest.get("skipped") or [])
                self.assertGreaterEqual(int(ingest.get("skipped_count") or 0), 1, ingest)
                self.assertTrue(
                    any(
                        "CATALYST" in str(row.get("reason") or "").upper()
                        or "NO_MATCH" in str(row.get("reason") or "").upper()
                        for row in skipped
                    ),
                    skipped,
                )

                events = list(ingest.get("events") or [])
                self.assertGreaterEqual(len(events), 1, ingest)
                opportunity_ids = [
                    str(oid) for oid in (ingest.get("opportunity_ids") or []) if str(oid).strip()
                ]
                self.assertGreaterEqual(len(opportunity_ids), 1, ingest)

                # EventV1 / PIT: admitted rows carry identity + point-in-time stamps.
                repository = getattr(store, "strategy_repository", None)
                self.assertIsNotNone(repository)
                for event_row in events:
                    self.assertTrue(str(event_row.get("event_id") or "").strip(), event_row)
                    for pit_key in (
                        "event_time_ns",
                        "available_time_ns",
                        "received_time_ns",
                    ):
                        self.assertIsNotNone(event_row.get(pit_key), (pit_key, event_row))
                        self.assertGreater(int(event_row[pit_key]), 0, (pit_key, event_row))
                    # Live gates are off → fail closed to HISTORICAL_RECONSTRUCTED.
                    self.assertEqual(
                        str(event_row.get("ingestion_mode") or ""),
                        "HISTORICAL_RECONSTRUCTED",
                        event_row,
                    )
                    self.assertNotEqual(
                        str(event_row.get("ingestion_mode") or ""),
                        "LIVE_OBSERVED",
                        event_row,
                    )

                    oid = event_row.get("opportunity_id")
                    if oid:
                        # Detector / OE produced a durable opportunity.
                        self.assertIsNotNone(event_row.get("detector_detail"), event_row)
                        persisted = repository.get_opportunity(str(oid))
                        self.assertIsNotNone(persisted, oid)
                        self.assertEqual(str(persisted.opportunity_id), str(oid))

                clock_body = json.dumps({"as_of_time": T_FRESH_RETRIEVED}).encode("utf-8")
                cstatus, cpayload = _http_json(
                    conn,
                    "POST",
                    "/controlled-replay/advance-clock",
                    body=clock_body,
                )
                self.assertEqual(cstatus, 200, cpayload)
                self.assertEqual(cpayload.get("execution_authority"), "BLOCKED")
                self.assertTrue(cpayload.get("not_live_market_data"))
                self.assertEqual(store.data_mode, "FIXTURE_REPLAY")

                summary_status, summary = _http_json(conn, "GET", "/opportunities/summary", body=b"")
                self.assertEqual(summary_status, 200, summary)
                items = list(summary.get("items") or [])
                self.assertGreaterEqual(len(items), 1, summary)
                radar_ids = {
                    str(item.get("opportunity_id") or item.get("summary_id") or "")
                    for item in items
                }
                radar_ids.discard("")
                # Durable opportunity IDs from ingest are what Radar surfaces.
                self.assertTrue(
                    set(opportunity_ids).issubset(radar_ids) or bool(radar_ids & set(opportunity_ids)),
                    {"ingest": opportunity_ids, "radar": sorted(radar_ids)},
                )
                # Zero-qualifying controlled source must not invent a ZZZZ radar row.
                symbols = {
                    str(item.get("symbol") or item.get("instrument") or "").upper()
                    for item in items
                }
                self.assertNotIn("ZZZZ", symbols)

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
                pre_dismiss_count = len(items)

                watch_status, watch_ack = _http_json(
                    conn, "POST", f"/opportunities/{watch_id}/watch", body=b"{}"
                )
                self.assertEqual(watch_status, 200, watch_ack)
                self.assertEqual(watch_ack["action"], "WATCHED")
                self.assertIn("trade_review_id", watch_ack)

                dismiss_status, dismiss_ack = _http_json(
                    conn,
                    "POST",
                    f"/opportunities/{dismiss_candidate}/dismiss",
                    body=b"{}",
                )
                self.assertEqual(dismiss_status, 200, dismiss_ack)
                self.assertEqual(dismiss_ack["action"], "DISMISSED")
                self.assertIn("trade_review_id", dismiss_ack)

                acks = list_operator_acks()
                actions = {(row["opportunity_id"], row["action"]) for row in acks}
                self.assertIn((watch_id, "WATCHED"), actions)
                self.assertIn((dismiss_candidate, "DISMISSED"), actions)

                # Radar queue: dismissed durable opportunity leaves the active surface.
                after_status, after_summary = _http_json(
                    conn, "GET", "/opportunities/summary", body=b""
                )
                self.assertEqual(after_status, 200, after_summary)
                after_items = list(after_summary.get("items") or [])
                after_ids = {
                    str(item.get("opportunity_id") or item.get("summary_id") or "")
                    for item in after_items
                }
                after_ids.discard("")
                self.assertNotIn(dismiss_candidate, after_ids)
                self.assertLessEqual(len(after_items), pre_dismiss_count)

                watch_traces = execution_decision_trace_repository().list_execution_decision_traces_by_opportunity(
                    watch_id
                )
                dismiss_traces = execution_decision_trace_repository().list_execution_decision_traces_by_opportunity(
                    dismiss_candidate
                )
                self.assertTrue(
                    any(row.decision_kind == ExecutionDecisionKind.WATCH for row in watch_traces)
                )
                self.assertTrue(
                    any(row.decision_kind == ExecutionDecisionKind.DISMISS for row in dismiss_traces)
                )
                self.assertFalse(
                    any(row.decision_kind == ExecutionDecisionKind.PAPER_REQUESTED for row in watch_traces)
                )
                self.assertFalse(
                    any(
                        row.decision_kind == ExecutionDecisionKind.BROKER_ACCEPTED
                        for row in dismiss_traces
                    )
                )

                watch_reviews = build_trade_reviews_for_opportunity_payload(store, watch_id)
                dismiss_reviews = build_trade_reviews_for_opportunity_payload(
                    store, dismiss_candidate
                )
                self.assertGreaterEqual(len(watch_reviews.get("items") or []), 1)
                self.assertEqual(
                    watch_reviews["items"][0]["review_mode"],
                    TradeReviewMode.WATCHED_OPPORTUNITY.value,
                )
                self.assertGreaterEqual(len(dismiss_reviews.get("items") or []), 1)
                self.assertEqual(
                    dismiss_reviews["items"][0]["review_mode"],
                    TradeReviewMode.REJECTED_OPPORTUNITY.value,
                )
                review_repo = open_trade_review_repository()
                restored_watch = review_repo.get_trade_review(str(watch_ack["trade_review_id"]))
                restored_dismiss = review_repo.get_trade_review(
                    str(dismiss_ack["trade_review_id"])
                )
                self.assertIsNotNone(restored_watch)
                self.assertIsNotNone(restored_dismiss)
                self.assertEqual(str(restored_watch.opportunity_id), watch_id)
                self.assertEqual(str(restored_dismiss.opportunity_id), dismiss_candidate)
                self.assertEqual(
                    restored_watch.review_mode, TradeReviewMode.WATCHED_OPPORTUNITY
                )
                self.assertEqual(
                    restored_dismiss.review_mode, TradeReviewMode.REJECTED_OPPORTUNITY
                )
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)
            conn.close()


if __name__ == "__main__":
    unittest.main()
