"""CONTROLLED REPLAY → Paper submit acknowledgement acceptance.

Evidence class: SOFTWARE_CONTROLLED / FIXTURE_REPLAY only.
Never EMPIRICAL_ACTIVE, never prospective market evidence, never Live
authority, never broker network submission, never a fabricated fill.

Continues past PR #400 confirmation/gates with the post-submit question:

    WATCHED opportunity
    → Paper authority + session
    → preview (server binding)
    → explicit preview_id submit
    → durable Paper order acknowledgement fields
    → order-history readback with opportunity:{id} provenance

Fill → position is asserted only when canonical internal simulation already
produced them; this suite never invents fills.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
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
    reset_execution_decision_trace_runtime_for_tests,
)
from market_platform_foundation.intelligence.trade_review import (  # noqa: E402
    reset_trade_review_repository_for_tests,
)
from market_platform_foundation.ui_api.live_intelligence import bind_ui_api_intelligence  # noqa: E402
from market_platform_foundation.ui_api.news_ingest import NEWS_INGEST_ROUTE  # noqa: E402
from market_platform_foundation.ui_api.operator_opportunity_state import (  # noqa: E402
    reset_operator_acks,
)
from market_platform_foundation.ui_api.paper_projections import (  # noqa: E402
    build_paper_order_history_page,
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
            client_order_id="cursor-probe-cr-submit-ack",
            idempotency_key="cursor-probe-cr-submit-ack",
        )
        if preview.get("fill_preview") is not None and preview.get("risk_status") == "PASS":
            return
    raise AssertionError("no fillable cursor on fixture for Paper submit acknowledgement")


def _handoff_body(*, opportunity_id: str, instrument_id: str, headline: str | None) -> dict:
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
        "client_order_id": f"workspace-ticket-ack-{opportunity_id[:12]}",
        "idempotency_key": f"workspace-ticket-ack-{opportunity_id[:12]}",
        "correlation_id": correlation,
        "decision_source_snapshot": snapshot,
    }


class ControlledReplayPaperSubmitAckAcceptanceTests(unittest.TestCase):
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

    def test_evidence_class_is_software_controlled_fixture_replay(self) -> None:
        self.assertEqual(EVIDENCE_CLASS, "SOFTWARE_CONTROLLED")
        self.assertEqual(EVIDENCE_DATA_MODE, "FIXTURE_REPLAY")

    def test_submit_yields_durable_order_and_order_history_readback(self) -> None:
        collection_root = ROOT.parent
        store = ReplayStore(collection_root=collection_root)
        store.load()
        bind_ui_api_intelligence(store)
        self.assertEqual(store.data_mode, EVIDENCE_DATA_MODE)
        self.assertEqual(store.opportunity_source, "CONTROLLED_REPLAY")
        UiApiHandler.store = store

        runtime_patch = patch(
            "market_platform_foundation.market_data.live_runtime.get_live_runtime",
            return_value=None,
        )
        clock_patch = patch(
            "market_platform_foundation.ui_api.news_ingest.monotonic_wall_ns",
            return_value=_SERVER_NS,
        )

        with runtime_patch, clock_patch:
            # Ingest + Watch on AAPL (fixture bars match Paper session).
            from http.client import HTTPConnection
            from http.server import ThreadingHTTPServer
            import threading

            httpd = ThreadingHTTPServer(("127.0.0.1", 0), UiApiHandler)
            port = httpd.server_address[1]
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            conn = HTTPConnection("127.0.0.1", port, timeout=20)
            try:
                auth_patch = patch.object(UiApiHandler, "_authorize_request", return_value=True)
                secret_patch = patch(
                    "market_platform_foundation.ui_api.server.assert_no_secrets_in_payload",
                    lambda _payload: None,
                )
                with auth_patch, secret_patch:
                    body = json.dumps(build_news_ingest_body()).encode("utf-8")
                    conn.request(
                        "POST",
                        NEWS_INGEST_ROUTE,
                        body=body,
                        headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
                    )
                    ingest_resp = conn.getresponse()
                    ingest = json.loads(ingest_resp.read().decode("utf-8"))
                    self.assertEqual(ingest_resp.status, 200, ingest)

                    clock_body = json.dumps({"as_of_time": T_FRESH_RETRIEVED}).encode("utf-8")
                    conn.request(
                        "POST",
                        "/controlled-replay/advance-clock",
                        body=clock_body,
                        headers={
                            "Content-Type": "application/json",
                            "Content-Length": str(len(clock_body)),
                        },
                    )
                    clock_resp = conn.getresponse()
                    self.assertEqual(clock_resp.status, 200, clock_resp.read())

                    conn.request("GET", "/opportunities/summary")
                    summary_resp = conn.getresponse()
                    summary = json.loads(summary_resp.read().decode("utf-8"))
                    self.assertEqual(summary_resp.status, 200, summary)
                    aapl_row = None
                    for item in summary.get("items") or []:
                        if str(item.get("instrument_id") or "").upper() == "AAPL":
                            aapl_row = item
                            break
                    self.assertIsNotNone(aapl_row, "expected AAPL controlled-replay opportunity")
                    watch_id = str(aapl_row.get("opportunity_id") or aapl_row.get("summary_id"))
                    instrument_id = "AAPL"

                    conn.request("POST", f"/opportunities/{watch_id}/watch", body=b"{}")
                    watch_resp = conn.getresponse()
                    watch_ack = json.loads(watch_resp.read().decode("utf-8"))
                    self.assertEqual(watch_resp.status, 200, watch_ack)
                    self.assertEqual(watch_ack["action"], "WATCHED")
            finally:
                httpd.shutdown()
                httpd.server_close()
                thread.join(timeout=5)
                conn.close()

            os.environ["IMP_PAPER_EXECUTION"] = "1"
            session = open_paper_session(store, {"execution_mode": "INTERNAL_SIMULATION"})
            self.assertIn(session["session"]["execution_authority"], {"AUTHORIZED", "PAPER_ONLY"})
            self.assertNotEqual(session["session"]["execution_authority"], "AUTHORIZED_LIVE")
            paper_account_id = str(session["session"]["paper_account_id"] or "")
            self.assertTrue(paper_account_id)

            portfolio = build_paper_portfolio_payload(store)
            self.assertEqual(portfolio["as_of_context"]["data_mode"], EVIDENCE_DATA_MODE)
            self.assertNotEqual(portfolio["as_of_context"]["data_mode"], "LIVE_OBSERVATIONAL")

            _move_cursor_to_fillable(store)
            handoff = _handoff_body(
                opportunity_id=watch_id,
                instrument_id=instrument_id,
                headline=None,
            )
            self.assertEqual(handoff["correlation_id"], f"opportunity:{watch_id}")
            snapshot = parse_decision_source_snapshot(handoff["decision_source_snapshot"])
            validate_snapshot_against_correlation(
                snapshot=snapshot,
                correlation_id=handoff["correlation_id"],
            )

            # Preview remains authority — direct submit without preview_id fails.
            with self.assertRaises(ValueError) as bare_submit:
                submit_paper_order(store, handoff)
            self.assertIn("PREVIEW_REQUIRED", str(bare_submit.exception))

            preview = preview_paper_order(store, handoff)
            preview_id = preview["preview"]["preview_id"]
            self.assertTrue(preview_id)
            self.assertEqual(preview["preview"]["risk_status"], "PASS", preview)

            submit_body = dict(handoff, preview_id=preview_id)
            submission_envelope = submit_paper_order(store, submit_body)
            submission = submission_envelope["submission"]

            # Durable acknowledgement fields the UI surfaces after submit.
            order_id = str(submission.get("order_id") or "")
            intent_id = str(submission.get("intent_id") or "")
            self.assertTrue(order_id, submission)
            self.assertTrue(intent_id, submission)
            self.assertFalse(submission.get("duplicate", True), submission)
            order = submission.get("order") or {}
            self.assertEqual(str(order.get("order_id") or order_id), order_id)
            self.assertTrue(str(order.get("state") or order.get("status") or ""))
            self.assertEqual(
                str(order.get("correlation_id") or submission.get("correlation_id") or ""),
                f"opportunity:{watch_id}",
            )

            # Immediate order-history / portfolio readback.
            history = build_paper_order_history_page(store)
            history_orders = list(history.get("orders") or [])
            portfolio_after = build_paper_portfolio_payload(store)
            portfolio_orders = list(portfolio_after.get("orders") or [])
            visible = history_orders + portfolio_orders
            matched = [
                row
                for row in visible
                if str(row.get("order_id") or "") == order_id
            ]
            self.assertTrue(
                matched,
                {
                    "order_id": order_id,
                    "history_count": len(history_orders),
                    "portfolio_order_count": len(portfolio_orders),
                    "history_states": [row.get("state") for row in history_orders],
                    "portfolio_states": [row.get("state") for row in portfolio_orders],
                },
            )
            matched_order = matched[0]
            self.assertEqual(
                str(matched_order.get("correlation_id") or ""),
                f"opportunity:{watch_id}",
            )

            # Fill is only asserted when canonical simulation already produced one.
            # Do not invent fills; do not fail this acknowledgement gate on a later
            # Portfolio position-projection gap.
            fill = submission.get("fill")
            if fill is not None:
                self.assertEqual(str(fill.get("order_id") or ""), order_id)
                history_fills = list(history.get("fills") or [])
                portfolio_fills = list(portfolio_after.get("fills") or [])
                fill_ids = {
                    str(row.get("fill_id") or "")
                    for row in history_fills + portfolio_fills
                    if str(row.get("order_id") or "") == order_id
                }
                submitted_fill_id = str(fill.get("fill_id") or submission.get("fill_id") or "")
                if submitted_fill_id:
                    self.assertIn(
                        submitted_fill_id,
                        fill_ids,
                        {
                            "fill_id": submitted_fill_id,
                            "history_fill_count": len(history_fills),
                            "portfolio_fill_count": len(portfolio_fills),
                        },
                    )
            else:
                self.assertIsNone(submission.get("fill_id"))

            # Live / broker authority remains closed.
            self.assertNotIn(
                str(submission_envelope.get("as_of_context", {}).get("execution_authority") or "").upper(),
                {"LIVE", "AUTHORIZED_LIVE", "BROKER_LIVE"},
            )


if __name__ == "__main__":
    unittest.main()
