"""CONTROLLED REPLAY → Paper preview continuation acceptance.

Evidence class: SOFTWARE_CONTROLLED / FIXTURE_REPLAY only.
Never EMPIRICAL_ACTIVE, never prospective market evidence, never Live
authority, never broker order submission, never a fabricated filled order.

Extends the Controlled Replay golden path with the Radar → Paper preview
continuation that 36b3ad08 landed:

    controlled source
    → durable opportunity on Radar
    → Watch (lifecycle_state=WATCHED)
    → Paper authority + portfolio account required
    → workspace handoff provenance opportunity:{id}
    → server Paper preview (authority) + risk/account checks
    → submit remains operator-controlled (PREVIEW_REQUIRED)

Controlled-replay Watch/Dismiss alone must NOT unlock Paper preview.
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
sys.path.insert(0, str(ROOT))

from market_platform_foundation.news.timestamps import epoch_ns_from_iso  # noqa: E402
from market_platform_foundation.paper.decision_source import (  # noqa: E402
    parse_decision_source_snapshot,
    validate_snapshot_against_correlation,
)
from market_platform_foundation.paper.eligibility import (  # noqa: E402
    ensure_operator_fixture_registered,
)
from market_platform_foundation.paper.execution import (  # noqa: E402
    preview_interactive_order,
)
from market_platform_foundation.rt01.execution_decision_trace import (  # noqa: E402
    ExecutionDecisionKind,
    execution_decision_trace_repository,
    reset_execution_decision_trace_runtime_for_tests,
)
from market_platform_foundation.intelligence.trade_review import (  # noqa: E402
    reset_trade_review_repository_for_tests,
)
from market_platform_foundation.ui_api.live_intelligence import bind_ui_api_intelligence  # noqa: E402
from market_platform_foundation.ui_api.news_ingest import NEWS_INGEST_ROUTE  # noqa: E402
from market_platform_foundation.ui_api.operator_opportunity_state import (  # noqa: E402
    list_operator_acks,
    reset_operator_acks,
)
from market_platform_foundation.ui_api.paper_projections import (  # noqa: E402
    build_paper_portfolio_payload,
    open_paper_session,
    preview_paper_order,
    submit_paper_order,
)
from market_platform_foundation.ui_api.server import UiApiHandler  # noqa: E402
from market_platform_foundation.ui_api.store import ReplayStore  # noqa: E402
from tools.controlled_replay.env import build_controlled_replay_environment  # noqa: E402
from tools.controlled_replay.scenarios import (  # noqa: E402
    T_FRESH_RETRIEVED,
    build_news_ingest_body,
)

EVIDENCE_CLASS = "SOFTWARE_CONTROLLED"
EVIDENCE_DATA_MODE = "FIXTURE_REPLAY"

_SERVER_NS = int(epoch_ns_from_iso(T_FRESH_RETRIEVED) or 0)
_LIVE_KEYS = (
    "IMP_LIVE_OBSERVATIONAL",
    "IMP_LIVE_EXECUTION",
    "IMP_BROKER_LIVE_EXECUTION",
    "IMP_MOOMOO_LIVE",
    "IMP_FINVIZ_LIVE",
    "IMP_LIVE_INTERNAL_SIMULATION",
)

_FORBIDDEN_EVIDENCE = {
    "EMPIRICAL_ACTIVE",
    "PROSPECTIVE_FORWARD",
    "PROSPECTIVE_MARKET",
    "LIVE_MARKET_DATA",
    "LIVE_OBSERVATIONAL",
}


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


def _can_preview_opportunity_in_paper(row: dict) -> bool:
    """Mirror UI `canPreviewOpportunityInPaper` for acceptance assertions."""

    lifecycle = str(row.get("lifecycle_state") or "").upper()
    if lifecycle != "WATCHED":
        return False
    instrument = str(row.get("instrument_id") or "").strip()
    if not instrument:
        return False
    eligibility = str(row.get("eligibility_state") or "").upper()
    if eligibility in {"INELIGIBLE", "UNAVAILABLE"}:
        return False
    next_action = str(row.get("next_safe_action") or "")
    if next_action == "STOP":
        return False
    return next_action == "OPEN_WORKSPACE"


def _assert_software_controlled_context(testcase: unittest.TestCase, as_of: dict) -> None:
    testcase.assertEqual(as_of.get("data_mode"), EVIDENCE_DATA_MODE)
    testcase.assertEqual(as_of.get("execution_authority"), "BLOCKED")
    testcase.assertNotEqual(as_of.get("data_mode"), "LIVE_OBSERVATIONAL")
    testcase.assertNotIn(str(as_of.get("data_mode") or "").upper(), _FORBIDDEN_EVIDENCE)
    testcase.assertNotIn(str(as_of.get("evidence_class") or "").upper(), _FORBIDDEN_EVIDENCE)
    testcase.assertNotEqual(str(as_of.get("evidence_class") or "").upper(), "EMPIRICAL_ACTIVE")


def _move_cursor_to_fillable(store: ReplayStore) -> None:
    for index in range(len(store.bars) - 2, -1, -1):
        store.set_cursor_index(index)
        preview = preview_interactive_order(
            ledger=store.paper_ledger,
            bars=store.bars_for_execution(),
            symbol=store.symbol,
            instrument_id=store.instrument_id,
            side="BUY",
            quantity=1,
            observation_time=store.prediction_cutoff(),
            client_order_id="cursor-probe-cr-preview",
            idempotency_key="cursor-probe-cr-preview",
        )
        if preview.get("fill_preview") is not None and preview.get("risk_status") == "PASS":
            return
    raise AssertionError("no fillable cursor on fixture for Paper preview")


def _handoff_preview_body(*, opportunity_id: str, instrument_id: str, headline: str | None) -> dict:
    """Placeholder BUY×1 handoff matching UI `createWatchedOpportunityPaperOrderDraft`."""

    correlation = f"opportunity:{opportunity_id}"
    snapshot = {
        "source_type": "watched_opportunity",
        "source_id": opportunity_id,
        "reasons": [
            {"code": "WATCHED_OPPORTUNITY", "label": "Watched Radar opportunity handoff"}
        ],
    }
    if headline:
        snapshot["headline"] = headline
    return {
        "side": "BUY",
        "quantity": 1,
        "order_type": "MARKET",
        "instrument_id": instrument_id,
        "symbol": instrument_id,
        "client_order_id": f"workspace-ticket-cr-{opportunity_id[:12]}",
        "idempotency_key": f"workspace-ticket-cr-{opportunity_id[:12]}",
        "correlation_id": correlation,
        "decision_source_snapshot": snapshot,
    }


class ControlledReplayPaperPreviewAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        for key in _LIVE_KEYS:
            os.environ.pop(key, None)
        env = build_controlled_replay_environment({}, root=ROOT)
        state = Path(self._tmp.name) / "controlled-replay"
        state.mkdir(parents=True, exist_ok=True)
        env["IMP_STATE_DIR"] = str(state)
        for key, value in env.items():
            os.environ[key] = value
        self.assertEqual(os.environ.get("IMP_CONTROLLED_REPLAY"), "1")
        self.assertEqual(os.environ.get("IMP_PAPER_EXECUTION"), "0")
        self._state_dir = state
        reset_operator_acks()
        reset_trade_review_repository_for_tests()
        reset_execution_decision_trace_runtime_for_tests()
        ensure_operator_fixture_registered()

    def tearDown(self) -> None:
        for key in list(os.environ):
            if key.startswith("IMP_") or key in _LIVE_KEYS:
                os.environ.pop(key, None)
        reset_operator_acks()
        reset_trade_review_repository_for_tests()
        reset_execution_decision_trace_runtime_for_tests()
        self._tmp.cleanup()

    def test_evidence_class_label_is_software_controlled_fixture_replay(self) -> None:
        self.assertEqual(EVIDENCE_CLASS, "SOFTWARE_CONTROLLED")
        self.assertEqual(EVIDENCE_DATA_MODE, "FIXTURE_REPLAY")
        env = build_controlled_replay_environment({"IMP_LIVE_OBSERVATIONAL": "1"}, root=ROOT)
        self.assertEqual(env["IMP_PAPER_EXECUTION"], "0")
        self.assertNotIn("IMP_LIVE_OBSERVATIONAL", env)
        self.assertNotIn("IMP_LIVE_EXECUTION", env)

    def test_gate_refuses_unwatched_ineligible_and_stale_alone_does_not_block(self) -> None:
        watched_eligible = {
            "lifecycle_state": "WATCHED",
            "instrument_id": "AAPL",
            "eligibility_state": "ELIGIBLE",
            "next_safe_action": "OPEN_WORKSPACE",
            "data_quality": {"freshness": "STALE"},
        }
        self.assertTrue(_can_preview_opportunity_in_paper(watched_eligible))

        unwatched = dict(watched_eligible, lifecycle_state="ACTIVE")
        self.assertFalse(_can_preview_opportunity_in_paper(unwatched))

        dismissed = dict(watched_eligible, lifecycle_state="DISMISSED")
        self.assertFalse(_can_preview_opportunity_in_paper(dismissed))

        ineligible = dict(watched_eligible, eligibility_state="INELIGIBLE")
        self.assertFalse(_can_preview_opportunity_in_paper(ineligible))

        stop = dict(watched_eligible, next_safe_action="STOP")
        self.assertFalse(_can_preview_opportunity_in_paper(stop))

        no_instrument = dict(watched_eligible, instrument_id=None)
        self.assertFalse(_can_preview_opportunity_in_paper(no_instrument))

    def test_watched_opportunity_paper_preview_handoff_server_authority(self) -> None:
        collection_root = ROOT.parent
        store = ReplayStore(collection_root=collection_root)
        store.load()
        bind_ui_api_intelligence(store)
        self.assertEqual(store.data_mode, EVIDENCE_DATA_MODE)
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
                as_of = ctx["as_of_context"]
                self.assertTrue(ctx.get("controlled_replay") or as_of.get("controlled_replay"))
                _assert_software_controlled_context(self, as_of)
                self.assertTrue(as_of.get("not_live_market_data") or ctx.get("not_live_market_data"))

                body = json.dumps(build_news_ingest_body()).encode("utf-8")
                status, ingest = _http_json(conn, "POST", NEWS_INGEST_ROUTE, body=body)
                self.assertEqual(status, 200, ingest)
                self.assertGreaterEqual(int(ingest.get("opportunity_count") or 0), 1, ingest)
                self.assertFalse(ingest.get("live_authority", True))

                clock_body = json.dumps({"as_of_time": T_FRESH_RETRIEVED}).encode("utf-8")
                cstatus, cpayload = _http_json(
                    conn, "POST", "/controlled-replay/advance-clock", body=clock_body
                )
                self.assertEqual(cstatus, 200, cpayload)
                self.assertEqual(cpayload.get("execution_authority"), "BLOCKED")

                summary_status, summary = _http_json(conn, "GET", "/opportunities/summary", body=b"")
                self.assertEqual(summary_status, 200, summary)
                items = list(summary.get("items") or [])
                self.assertGreaterEqual(len(items), 1, summary)

                # Prefer AAPL so Paper fixture bars match the handoff instrument.
                aapl_row = None
                for item in items:
                    symbol = str(item.get("instrument_id") or item.get("symbol") or "").upper()
                    if symbol == "AAPL":
                        aapl_row = item
                        break
                self.assertIsNotNone(aapl_row, "expected AAPL controlled-replay opportunity")
                watch_id = str(aapl_row.get("opportunity_id") or aapl_row.get("summary_id"))
                instrument_id = str(aapl_row.get("instrument_id") or "").strip().upper()
                self.assertEqual(instrument_id, "AAPL")

                # Unwatched rows must not enter Paper preview.
                self.assertFalse(_can_preview_opportunity_in_paper(aapl_row))

                watch_status, watch_ack = _http_json(
                    conn, "POST", f"/opportunities/{watch_id}/watch", body=b"{}"
                )
                self.assertEqual(watch_status, 200, watch_ack)
                self.assertEqual(watch_ack["action"], "WATCHED")

                acks = list_operator_acks()
                self.assertIn((watch_id, "WATCHED"), {(r["opportunity_id"], r["action"]) for r in acks})

                detail_status, detail = _http_json(
                    conn, "GET", f"/opportunities/{watch_id}", body=b""
                )
                self.assertEqual(detail_status, 200, detail)
                self.assertEqual(str(detail.get("lifecycle_state") or "").upper(), "WATCHED")
                self.assertEqual(str(detail.get("opportunity_id") or watch_id), watch_id)
                self.assertTrue(detail.get("instrument_id"))
                # Freshness STALE alone must not block when still eligible for workspace.
                freshness = str(
                    ((detail.get("data_quality") or {}).get("freshness_evaluation") or {}).get(
                        "status"
                    )
                    or (detail.get("data_quality") or {}).get("freshness")
                    or ""
                ).upper()
                if freshness == "STALE":
                    self.assertNotEqual(detail.get("next_safe_action"), "STOP")

                self.assertTrue(
                    _can_preview_opportunity_in_paper(detail),
                    {
                        "lifecycle": detail.get("lifecycle_state"),
                        "eligibility": detail.get("eligibility_state"),
                        "next_safe_action": detail.get("next_safe_action"),
                        "instrument": detail.get("instrument_id"),
                    },
                )
                self.assertEqual(
                    str(detail.get("preview_href") or ""),
                    f"/workspace/{instrument_id}",
                )

                # Watch alone must not unlock Paper preview / execution.
                self.assertEqual(os.environ.get("IMP_PAPER_EXECUTION"), "0")
                blocked_session = open_paper_session(store, {"execution_mode": "INTERNAL_SIMULATION", "preferred_instrument": store.instrument_id})
                self.assertEqual(
                    blocked_session["session"]["execution_authority"],
                    "BLOCKED",
                    blocked_session,
                )
                self.assertNotEqual(blocked_session["session"]["execution_authority"], "AUTHORIZED")
                self.assertNotEqual(blocked_session["session"]["execution_authority"], "PAPER_ONLY")

                watch_traces = execution_decision_trace_repository().list_execution_decision_traces_by_opportunity(
                    watch_id
                )
                self.assertTrue(
                    any(row.decision_kind == ExecutionDecisionKind.WATCH for row in watch_traces)
                )
                self.assertFalse(
                    any(
                        row.decision_kind == ExecutionDecisionKind.PAPER_REQUESTED
                        for row in watch_traces
                    )
                )
                self.assertFalse(
                    any(
                        row.decision_kind == ExecutionDecisionKind.BROKER_ACCEPTED
                        for row in watch_traces
                    )
                )

                # No fake filled order from Watch / handoff alone.
                orders_before = store.paper_ledger.project_orders()
                filled_before = [
                    order
                    for order in orders_before
                    if str(order.get("status") or "").upper() in {"FILLED", "PARTIALLY_FILLED"}
                ]
                self.assertEqual(filled_before, [])

                # Explicit Paper authority is required for the preview continuation.
                os.environ["IMP_PAPER_EXECUTION"] = "1"
                session = open_paper_session(store, {"execution_mode": "INTERNAL_SIMULATION", "preferred_instrument": store.instrument_id})
                self.assertEqual(session["session"]["execution_mode"], "INTERNAL_SIMULATION")
                self.assertIn(
                    session["session"]["execution_authority"],
                    {"AUTHORIZED", "PAPER_ONLY"},
                )
                self.assertNotEqual(session["session"]["execution_authority"], "AUTHORIZED_LIVE")
                paper_account_id = str(session["session"]["paper_account_id"] or "")
                self.assertTrue(paper_account_id)

                portfolio = build_paper_portfolio_payload(store)
                self.assertEqual(portfolio["authority_boundary"], "PAPER_OBSERVABILITY")
                self.assertEqual(
                    portfolio["account"]["paper_account_id"],
                    paper_account_id,
                )
                self.assertIn("risk", portfolio)
                self.assertEqual(
                    portfolio["as_of_context"]["data_mode"],
                    EVIDENCE_DATA_MODE,
                )
                self.assertNotEqual(
                    portfolio["as_of_context"]["data_mode"],
                    "LIVE_OBSERVATIONAL",
                )

                _move_cursor_to_fillable(store)

                handoff = _handoff_preview_body(
                    opportunity_id=watch_id,
                    instrument_id=instrument_id,
                    headline=str(detail.get("headline") or "") or None,
                )
                # Canonical provenance identity.
                self.assertEqual(handoff["correlation_id"], f"opportunity:{watch_id}")
                snapshot = parse_decision_source_snapshot(handoff["decision_source_snapshot"])
                self.assertEqual(snapshot["source_type"], "watched_opportunity")
                self.assertEqual(snapshot["source_id"], watch_id)
                validate_snapshot_against_correlation(
                    snapshot=snapshot,
                    correlation_id=handoff["correlation_id"],
                )
                with self.assertRaises(ValueError):
                    validate_snapshot_against_correlation(
                        snapshot=snapshot,
                        correlation_id=watch_id,
                    )

                # Direct submit refused — server preview remains authority.
                with self.assertRaises(ValueError) as submit_ctx:
                    submit_paper_order(store, handoff)
                self.assertIn("PREVIEW_REQUIRED", str(submit_ctx.exception))

                preview = preview_paper_order(store, handoff)
                preview_block = preview["preview"]
                binding = preview_block["preview_binding"]
                self.assertTrue(preview_block.get("preview_id"))
                self.assertTrue(binding.get("intent_digest"))
                self.assertTrue(binding.get("portfolio_revision"))
                self.assertTrue(binding.get("risk_policy_revision"))
                self.assertEqual(binding.get("mode"), "PAPER")
                self.assertEqual(binding.get("account_id"), paper_account_id)
                self.assertEqual(
                    preview.get("as_of_context", {}).get("data_mode")
                    or portfolio["as_of_context"]["data_mode"],
                    EVIDENCE_DATA_MODE,
                )
                # Preview is not a fill and must not invent Live authority.
                self.assertNotIn(
                    str(preview.get("as_of_context", {}).get("execution_authority") or "").upper(),
                    {"LIVE", "AUTHORIZED_LIVE", "BROKER_LIVE"},
                )
                orders_after_preview = store.paper_ledger.project_orders()
                filled_after_preview = [
                    order
                    for order in orders_after_preview
                    if str(order.get("status") or "").upper() in {"FILLED", "PARTIALLY_FILLED"}
                ]
                self.assertEqual(filled_after_preview, [])

                # Provenance mismatch must fail closed (not silently rewrite).
                bad = dict(handoff)
                bad["correlation_id"] = f"attention:{watch_id}"
                with self.assertRaises(ValueError) as mismatch_ctx:
                    preview_paper_order(store, bad)
                self.assertIn(
                    "DECISION_SOURCE_SNAPSHOT_CORRELATION_MISMATCH",
                    str(mismatch_ctx.exception),
                )

                # Ineligible / unwatched synthetic rows still refuse the gate.
                self.assertFalse(
                    _can_preview_opportunity_in_paper(
                        {
                            **detail,
                            "lifecycle_state": "ACTIVE",
                        }
                    )
                )
                self.assertFalse(
                    _can_preview_opportunity_in_paper(
                        {
                            **detail,
                            "eligibility_state": "INELIGIBLE",
                            "next_safe_action": "OPEN_WORKSPACE",
                        }
                    )
                )
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)
            conn.close()


if __name__ == "__main__":
    unittest.main()
