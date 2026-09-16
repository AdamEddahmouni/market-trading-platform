"""Software-only full-stack acceptance (not empirical).

Evidence class: SOFTWARE / CONTROLLED. This module never claims live empirical
evidence, FTEP EMPIRICAL_ACTIVE, Item 9 calibration, or Grok automation.

Required production chain (post-#205 honesty):

    controlled lawful-like Finviz/news provider row (already-fetched JSON)
    → UiApiHandler POST ``/intelligence/ingest/news`` (EventV1 admit)
    → PIT clocks on EventV1
    → ``ingress.observational_news_detector``
    → Opportunity Engine (in-memory ranked book)
    → API summary
    → WATCH / DISMISS
    → DecisionTrace
    → TradeReview
    → persist / readback

Skip / xfail policy (NOT a silent pass):

- Missing P1 UiApiHandler EventV1 admit is a FAIL with
  ``P1_HANDLER_ADMIT_MISSING``. Never ``skip``, never ``expectedFailure``.
- ReplayStore / COLLECTION_ROOT load cannot substitute for handler admit.
- In-process ``ObservationIngressRouter`` / ``dispatch_sec_insider_row``
  cannot substitute for the UI-process request path.
- Live env gates, broker orders, and Grok must stay off. Accidental enablement
  is FAIL, not skip.
- This file must not use ``@unittest.skip`` or ``@unittest.expectedFailure``.

This suite owns new test modules under ``tests/acceptance/`` only. It does not
edit ``opportunity_projections.py``, ``run_ui_api.py``, news EventV1, vite,
launcher, or Item 9.
"""

from __future__ import annotations

import ast
import http.client
import inspect
import json
import os
import sys
import tempfile
import textwrap
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.normalization.models import (  # noqa: E402
    IngestionMode,
)
from market_platform_foundation.intelligence.observation_ingress import (  # noqa: E402
    ObservationIngressRouter,
    build_production_observation_ingress_router,
    dispatch_normalization_result,
)
from market_platform_foundation.intelligence.opportunity.freshness import (  # noqa: E402
    FRESHNESS_FRESH,
    HONESTY_SOURCES,
    OpportunityFreshnessPolicy,
    evaluate_opportunity_freshness,
    fail_closed_for_actionable,
)
from market_platform_foundation.intelligence.persistence import (  # noqa: E402
    InMemoryIntelligenceRepository,
)
from market_platform_foundation.intelligence.trade_review import (  # noqa: E402
    TRADE_REVIEW_DURABLE_LOOP_READY,
    TradeReviewMode,
    open_trade_review_repository,
    reset_trade_review_repository_for_tests,
)
from market_platform_foundation.market_data.live_config import (  # noqa: E402
    live_observational_enabled,
)
from market_platform_foundation.news.timestamps import epoch_ns_from_iso  # noqa: E402
from market_platform_foundation.rt01.execution_decision_trace import (  # noqa: E402
    ExecutionDecisionKind,
    execution_decision_trace_repository,
    reset_execution_decision_trace_runtime_for_tests,
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

P1_HANDLER_ADMIT_MISSING = "P1_HANDLER_ADMIT_MISSING"
P1_HANDLER_ADMIT_PRESENT = "P1_HANDLER_ADMIT_PRESENT"
SOFTWARE_FULLSTACK_ACCEPTANCE = "SOFTWARE_FULLSTACK_ACCEPTANCE"

_PUBLISHED = "2026-09-15T14:05:00Z"
_RETRIEVED = "2026-09-15T14:05:08Z"
_SERVER = "2026-09-15T14:05:10Z"
_SERVER_NS = int(epoch_ns_from_iso(_SERVER) or 0)

_ADMIT_METHOD_NAMES = (
    "admit_event",
    "admit_provider_event",
    "admit_observation",
    "admit_event_v1",
    "dispatch_eventv1",
    "handle_event_admit",
    "handle_observation_ingress",
    "handle_news_ingest_post",
)

_ADMIT_SOURCE_TOKENS = (
    "dispatch_normalization_result",
    "dispatch_sec_insider_row",
    "dispatch_congressional_disclosure_row",
    "build_production_observation_ingress_router",
    "ObservationIngressRouter",
    "admit_event",
    "admit_provider_event",
    "put_event(",
    "EventV1(",
    "handle_news_ingest_post",
    "NEWS_INGEST_ROUTE",
    "/intelligence/ingest/news",
)

_GROK_EXCLUSION_TOKENS = (
    "agent_enrichment",
    "handle_agent_enrichment",
    "/intelligence/ingest/enrichment",
)

_CANDIDATE_ADMIT_PATHS = (
    NEWS_INGEST_ROUTE,
    "/intelligence/ingest/event",
    "/intelligence/ingest/events",
    "/intelligence/observations/admit",
    "/observation-ingress/dispatch",
    "/events/admit",
)

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

_THIS_FILE = Path(__file__).resolve()


def _clear_live_and_grok_env() -> None:
    for key in _LIVE_ENV_KEYS + _GROK_ENV_KEYS:
        os.environ.pop(key, None)


def _import_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
    return names


def _call_attr_names(fn_source: str) -> set[str]:
    tree = ast.parse(textwrap.dedent(fn_source))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            names.add(node.func.attr)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            names.add(node.func.id)
    return names


def _request_path_source() -> str:
    return "\n".join(
        (
            inspect.getsource(UiApiHandler.do_POST),
            inspect.getsource(UiApiHandler.do_PUT),
            inspect.getsource(UiApiHandler.do_GET),
        )
    )


def _strip_grok_ingest_blocks(source: str) -> str:
    kept: list[str] = []
    skipping = False
    for line in source.splitlines():
        if any(token in line for token in _GROK_EXCLUSION_TOKENS):
            skipping = True
        if skipping:
            stripped = line.strip()
            if stripped.startswith("if path") and not any(
                token in line for token in _GROK_EXCLUSION_TOKENS
            ):
                skipping = False
                kept.append(line)
            continue
        kept.append(line)
    return "\n".join(kept)


def probe_ui_handler_eventv1_admit() -> tuple[str, str]:
    """Return (status, detail) for UiApiHandler request-path EventV1 admit.

    Library ingress, ReplayStore.load, Grok enrichment ingest, and helper-only
    comments do not count. Missing admit is ``P1_HANDLER_ADMIT_MISSING``.
    """

    for name in _ADMIT_METHOD_NAMES:
        fn = getattr(UiApiHandler, name, None)
        if callable(fn):
            return (
                P1_HANDLER_ADMIT_PRESENT,
                f"UiApiHandler.{name} is callable",
            )

    request_source = _strip_grok_ingest_blocks(_request_path_source())
    hits = [token for token in _ADMIT_SOURCE_TOKENS if token in request_source]
    if hits:
        return (
            P1_HANDLER_ADMIT_PRESENT,
            "UiApiHandler request path references EventV1 admit tokens: " + ", ".join(hits),
        )

    launcher = ROOT / "tools" / "ui1" / "run_ui_api.py"
    launcher_hits: tuple[str, ...] = ()
    if launcher.is_file():
        launcher_text = launcher.read_text(encoding="utf-8")
        launcher_hits = tuple(token for token in _ADMIT_SOURCE_TOKENS if token in launcher_text)
    detail = (
        "UiApiHandler do_POST/do_PUT/do_GET has no EventV1 admit/ingress "
        "request path (Grok enrichment ingest excluded). "
        f"candidate_paths={_CANDIDATE_ADMIT_PATHS} "
        f"admit_methods={_ADMIT_METHOD_NAMES} "
        f"launcher_admit_tokens={launcher_hits or '()'}"
    )
    return P1_HANDLER_ADMIT_MISSING, detail


def require_ui_handler_eventv1_admit() -> None:
    status, detail = probe_ui_handler_eventv1_admit()
    if status != P1_HANDLER_ADMIT_PRESENT:
        raise AssertionError(
            f"{P1_HANDLER_ADMIT_MISSING}: production UI process does not admit "
            f"a controlled lawful-like provider event into EventV1. {detail}. "
            "ReplayStore.load, in-process ObservationIngressRouter, and Grok "
            "enrichment ingest cannot substitute. This is a FAIL, not a skip."
        )


def _raw_article(*, headline: str, tickers: list[str], provider_native_id: str) -> dict:
    return {
        "headline": headline,
        "published_time": _PUBLISHED,
        "url": f"https://example.com/{provider_native_id}",
        "tickers": tickers,
        "publisher_source": "Wire",
        "provider_native_id": provider_native_id,
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


def _exercise_controlled_news_http_chain(state_dir: str) -> None:
    """HTTP-only chain; ReplayStore.load stays outside the owning test method."""

    collection_root = ROOT.parent

    reset_operator_acks()
    reset_trade_review_repository_for_tests()
    reset_execution_decision_trace_runtime_for_tests()
    os.environ["IMP_STATE_DIR"] = state_dir
    os.environ["IMP_PERSIST_STATE"] = "1"

    store = ReplayStore(collection_root=collection_root)
    store.load()
    store.data_mode = "LIVE_OBSERVATIONAL"
    store.mode = "LIVE"
    store.last_source_time_ns = _SERVER_NS
    bind_ui_api_intelligence(store)
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
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=15)

    try:
        with runtime_patch, clock_patch, auth_patch, secret_patch:
            ingest_body = json.dumps(
                {
                    "retrieved_time": _RETRIEVED,
                    "articles": [
                        _raw_article(
                            headline="Example Corp reports quarterly earnings",
                            tickers=["AAPL"],
                            provider_native_id="fv-fullstack-watch",
                        ),
                        _raw_article(
                            headline="Contoso Ltd reports quarterly earnings",
                            tickers=["MSFT"],
                            provider_native_id="fv-fullstack-dismiss",
                        ),
                    ],
                }
            ).encode("utf-8")
            status, ingest = _http_json(conn, "POST", NEWS_INGEST_ROUTE, body=ingest_body)
            assert status == 200, ingest
            assert ingest["admitted_count"] == 2, ingest
            assert ingest["opportunity_count"] == 2, ingest
            assert ingest["zero_qualifying_count"] == 0, ingest
            assert ingest["live_authority"] is False
            assert ingest["events"][0]["detector_detail"] == "NEWS_ARTICLE_OPPORTUNITY_MINTED"

            repo = store.strategy_repository
            assert repo is not None
            event = repo.get_event(ingest["events"][0]["event_id"])
            assert event is not None
            assert event.event_type == "NEWS_ARTICLE"
            assert event.event_time_ns != event.available_time_ns
            assert event.received_time_ns == _SERVER_NS

            summary_status, summary = _http_json(conn, "GET", "/opportunities/summary")
            assert summary_status == 200, summary
            assert summary["feed_status"] == "READY", summary
            assert summary.get("reason") != "LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE"
            assert len(summary["items"]) == 2

            watch_id = ingest["opportunity_ids"][0]
            dismiss_id = ingest["opportunity_ids"][1]
            watch_status, watch_ack = _http_json(
                conn,
                "POST",
                f"/opportunities/{watch_id}/watch",
            )
            assert watch_status == 200, watch_ack
            assert watch_ack["action"] == "WATCHED"
            watch_review_id = str(watch_ack["trade_review_id"])

            dismiss_status, dismiss_ack = _http_json(
                conn,
                "POST",
                f"/opportunities/{dismiss_id}/dismiss",
            )
            assert dismiss_status == 200, dismiss_ack
            assert dismiss_ack["action"] == "DISMISSED"
            dismiss_review_id = str(dismiss_ack["trade_review_id"])

            post_status, post_summary = _http_json(conn, "GET", "/opportunities/summary")
            assert post_status == 200, post_summary
            remaining = {
                str(item.get("opportunity_id") or item.get("summary_id"))
                for item in (post_summary.get("items") or [])
            }
            assert watch_id in remaining
            assert dismiss_id not in remaining

            acks = list_operator_acks()
            actions = {(row["opportunity_id"], row["action"]) for row in acks}
            assert (watch_id, "WATCHED") in actions
            assert (dismiss_id, "DISMISSED") in actions

            watch_traces = execution_decision_trace_repository().list_execution_decision_traces_by_opportunity(
                watch_id
            )
            dismiss_traces = execution_decision_trace_repository().list_execution_decision_traces_by_opportunity(
                dismiss_id
            )
            watch_kinds = {row.decision_kind for row in watch_traces}
            dismiss_kinds = {row.decision_kind for row in dismiss_traces}
            assert ExecutionDecisionKind.WATCH in watch_kinds
            assert ExecutionDecisionKind.DISMISS in dismiss_kinds
            watch_trace = next(row for row in watch_traces if row.decision_kind == ExecutionDecisionKind.WATCH)
            dismiss_trace = next(
                row for row in dismiss_traces if row.decision_kind == ExecutionDecisionKind.DISMISS
            )

            watch_reviews = build_trade_reviews_for_opportunity_payload(store, watch_id)
            dismiss_reviews = build_trade_reviews_for_opportunity_payload(store, dismiss_id)
            assert watch_reviews["acceptance_label"] == TRADE_REVIEW_DURABLE_LOOP_READY
            assert dismiss_reviews["items"][0]["review_mode"] == TradeReviewMode.REJECTED_OPPORTUNITY.value

            watch_trace_id = watch_trace.decision_trace_id
            dismiss_trace_id = dismiss_trace.decision_trace_id

            reset_trade_review_repository_for_tests()
            reset_execution_decision_trace_runtime_for_tests()
            reset_operator_acks()
            os.environ["IMP_STATE_DIR"] = state_dir
            os.environ["IMP_PERSIST_STATE"] = "1"

            restored_actions = {(row["opportunity_id"], row["action"]) for row in list_operator_acks()}
            assert (watch_id, "WATCHED") in restored_actions
            assert (dismiss_id, "DISMISSED") in restored_actions

            review_repo = open_trade_review_repository()
            restored_watch = review_repo.get_trade_review(watch_review_id)
            restored_dismiss = review_repo.get_trade_review(dismiss_review_id)
            assert restored_watch is not None
            assert restored_dismiss is not None
            assert restored_watch.review_mode == TradeReviewMode.WATCHED_OPPORTUNITY
            assert restored_dismiss.review_mode == TradeReviewMode.REJECTED_OPPORTUNITY

            restored_watch_trace = execution_decision_trace_repository().get_execution_decision_trace(
                watch_trace_id
            )
            restored_dismiss_trace = execution_decision_trace_repository().get_execution_decision_trace(
                dismiss_trace_id
            )
            assert restored_watch_trace is not None
            assert restored_dismiss_trace is not None
            assert restored_watch_trace.decision_kind == ExecutionDecisionKind.WATCH
            assert restored_dismiss_trace.decision_kind == ExecutionDecisionKind.DISMISS
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)
        conn.close()


def _controlled_lawful_like_provider_payload(*, event_time_ns: int, received_time_ns: int) -> dict:
    """Software-controlled provider-shaped quote. Not ReplayStore. Not live."""

    return {
        "provider": "moomoo.opend.observational",
        "capability": "QUOTE",
        "provider_symbol": "US.AAPL",
        "sequence": 1,
        "clocks": {
            "event_time_ns": event_time_ns,
            "provider_time_ns": event_time_ns + 5_000_000,
            "received_time_ns": received_time_ns,
        },
        "raw_payload": {
            "bid_price": 190.0,
            "ask_price": 190.05,
            "bid_vol": 200,
            "ask_vol": 180,
        },
        "admission_class": "SOFTWARE_CONTROLLED_LAWFUL_LIKE",
        "live_claim": "NOT_CLAIMED",
        "replay_substitute": False,
    }


class SoftwareFullstackAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        _clear_live_and_grok_env()
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ["IMP_STATE_DIR"] = self._tmp.name
        os.environ["IMP_PERSIST_STATE"] = "1"

    def tearDown(self) -> None:
        _clear_live_and_grok_env()
        os.environ.pop("IMP_STATE_DIR", None)
        os.environ.pop("IMP_PERSIST_STATE", None)
        os.environ.pop("IMP_PAPER_EXECUTION", None)
        reset_operator_acks()
        reset_trade_review_repository_for_tests()
        reset_execution_decision_trace_runtime_for_tests()
        self._tmp.cleanup()

    def test_acceptance_label_is_software_only(self) -> None:
        self.assertEqual(SOFTWARE_FULLSTACK_ACCEPTANCE, "SOFTWARE_FULLSTACK_ACCEPTANCE")
        self.assertNotEqual(SOFTWARE_FULLSTACK_ACCEPTANCE, "EMPIRICAL_ACTIVE")

    def test_skip_xfail_policy_is_not_a_silent_pass(self) -> None:
        source = _THIS_FILE.read_text(encoding="utf-8")
        tree = ast.parse(source)
        decorated: list[str] = []
        skip_calls: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.decorator_list:
                names = [ast.unparse(dec) for dec in node.decorator_list]
                if any("skip" in name or "expectedFailure" in name for name in names):
                    decorated.append(f"{node.name}: {names}")
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr == "skipTest":
                    skip_calls.append("skipTest")
                if isinstance(func, ast.Name) and func.id == "skipTest":
                    skip_calls.append("skipTest")
        self.assertEqual(decorated, [], msg=f"skip/xfail would be a silent pass: {decorated}")
        self.assertEqual(skip_calls, [], msg="skipTest would be a silent pass")
        self.assertIn("P1_HANDLER_ADMIT_MISSING", source)
        self.assertIn("require_ui_handler_eventv1_admit", source)
        method = inspect.getsource(self.test_controlled_event_through_api_watch_dismiss_trace_review_readback)
        self.assertIn("require_ui_handler_eventv1_admit", method)
        self.assertNotIn("skipTest", _call_attr_names(method))

    def test_live_off_no_broker_order_no_grok(self) -> None:
        self.assertFalse(live_observational_enabled())
        for key in _LIVE_ENV_KEYS + _GROK_ENV_KEYS:
            self.assertNotEqual(os.environ.get(key), "1", msg=f"{key} must stay off")
        fullstack = inspect.getsource(
            self.test_controlled_event_through_api_watch_dismiss_trace_review_readback
        )
        called = _call_attr_names(fullstack)
        self.assertNotIn("submit_paper_order", called)
        self.assertNotIn("submit_broker_order", called)
        self.assertNotIn("handle_agent_enrichment_ingest_post", called)
        self.assertNotIn("/intelligence/ingest/enrichment", "".join(_CANDIDATE_ADMIT_PATHS))
        self.assertNotIn("/paper/orders", "".join(_CANDIDATE_ADMIT_PATHS))

    def test_replay_fixture_cannot_substitute_for_handler_admit(self) -> None:
        tree = ast.parse(_THIS_FILE.read_text(encoding="utf-8"))
        self.assertNotIn("COLLECTION_ROOT", _import_names(tree))
        fullstack = inspect.getsource(
            self.test_controlled_event_through_api_watch_dismiss_trace_review_readback
        )
        self.assertNotIn("load", _call_attr_names(fullstack))
        self.assertNotIn("COLLECTION_ROOT", fullstack)

        repo = InMemoryIntelligenceRepository()
        router = build_production_observation_ingress_router(repo)
        self.assertIsInstance(router, ObservationIngressRouter)
        self.assertTrue(callable(dispatch_normalization_result))
        handler_status, handler_detail = probe_ui_handler_eventv1_admit()
        self.assertIn(
            handler_status,
            {P1_HANDLER_ADMIT_MISSING, P1_HANDLER_ADMIT_PRESENT},
            handler_detail,
        )
        if handler_status == P1_HANDLER_ADMIT_MISSING:
            self.assertNotIn("ObservationIngressRouter", _request_path_source())

    def test_stale_timestamp_cannot_appear_current(self) -> None:
        as_of_ns = 1_800_000_000_000_000_000
        stale_event_ns = as_of_ns - (10 * 60 * 1_000_000_000)
        stale = evaluate_opportunity_freshness(
            source="SOFTWARE_CONTROLLED",
            as_of_time_ns=as_of_ns,
            last_source_time_ns=stale_event_ns,
            policy=OpportunityFreshnessPolicy(stale_after_ns=5_000_000_000),
        )
        self.assertEqual(stale.status, "STALE")
        self.assertFalse(stale.actionable)
        self.assertTrue(fail_closed_for_actionable(stale))
        self.assertNotEqual(stale.status, FRESHNESS_FRESH)

        current_clock_ns = as_of_ns
        honesty_replay = evaluate_opportunity_freshness(
            source="REPLAY",
            as_of_time_ns=current_clock_ns,
            last_source_time_ns=current_clock_ns,
        )
        self.assertIn(honesty_replay.source, HONESTY_SOURCES)
        self.assertNotEqual(honesty_replay.status, FRESHNESS_FRESH)

        honesty_fixture = evaluate_opportunity_freshness(
            source="FIXTURE",
            as_of_time_ns=current_clock_ns,
            last_source_time_ns=current_clock_ns,
        )
        self.assertNotEqual(honesty_fixture.status, FRESHNESS_FRESH)

        payload = _controlled_lawful_like_provider_payload(
            event_time_ns=stale_event_ns,
            received_time_ns=as_of_ns,
        )
        self.assertLess(payload["clocks"]["event_time_ns"], payload["clocks"]["received_time_ns"])
        self.assertNotEqual(IngestionMode.REPLAY.value, "SOFTWARE_CONTROLLED_LAWFUL_LIKE")
        self.assertNotEqual(IngestionMode.LIVE_OBSERVED.value, payload["live_claim"])

    def test_controlled_event_through_api_watch_dismiss_trace_review_readback(self) -> None:
        """Full production chain over HTTP. SOFTWARE / HISTORICAL_RECONSTRUCTED only."""

        self.assertFalse(live_observational_enabled())
        require_ui_handler_eventv1_admit()
        _exercise_controlled_news_http_chain(self._tmp.name)


if __name__ == "__main__":
    unittest.main()
