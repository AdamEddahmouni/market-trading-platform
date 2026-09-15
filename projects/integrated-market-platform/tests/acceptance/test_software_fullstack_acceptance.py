"""Software-only full-stack acceptance (not empirical).

Evidence class: SOFTWARE / CONTROLLED. This module never claims live empirical
evidence, FTEP EMPIRICAL_ACTIVE, Item 9 calibration, or Grok automation.

Required production chain:

    controlled lawful-like provider event
    → UiApiHandler EventV1 admit (P1 request path)
    → PIT clocks
    → detector
    → Opportunity Engine
    → ranked
    → API
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
- Live, broker orders, and Grok must stay off. Accidental enablement is FAIL,
  not skip.
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
from datetime import datetime, timedelta, timezone
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
from market_platform_foundation.market_data.live_config import (  # noqa: E402
    live_observational_enabled,
)
from market_platform_foundation.ui_api.live_intelligence import (  # noqa: E402
    bind_ui_api_intelligence,
)
from market_platform_foundation.ui_api.news_ingest import (  # noqa: E402
    NEWS_INGEST_ROUTE,
)
from market_platform_foundation.ui_api.opportunity_projections import (  # noqa: E402
    build_opportunities_summary_payload,
)
from market_platform_foundation.ui_api.operator_opportunity_state import (  # noqa: E402
    reset_operator_acks,
)
from market_platform_foundation.ui_api.server import UiApiHandler  # noqa: E402
from market_platform_foundation.ui_api.store import ReplayStore  # noqa: E402

P1_HANDLER_ADMIT_MISSING = "P1_HANDLER_ADMIT_MISSING"
P1_HANDLER_ADMIT_PRESENT = "P1_HANDLER_ADMIT_PRESENT"
P2_EVENTV1_ADMIT_FAILED = "P2_EVENTV1_ADMIT_FAILED"
P2_PIT_CLOCKS_INVALID = "P2_PIT_CLOCKS_INVALID"
P3_DETECTOR_OPPORTUNITY_MISSING = "P3_DETECTOR_OPPORTUNITY_MISSING"
P4_RANKED_SUMMARY_MISSING = "P4_RANKED_SUMMARY_MISSING"
P4_RANKED_SUMMARY_BLOCKED = "P4_RANKED_SUMMARY_BLOCKED"
P5_WATCH_DISMISS_BLOCKED = "P5_WATCH_DISMISS_BLOCKED"
P6_DECISION_TRACE_UNREACHABLE = "P6_DECISION_TRACE_UNREACHABLE"
P7_TRADE_REVIEW_UNREACHABLE = "P7_TRADE_REVIEW_UNREACHABLE"
SOFTWARE_FULLSTACK_ACCEPTANCE = "SOFTWARE_FULLSTACK_ACCEPTANCE"
LIVE_OE_NO_MUTATION = "LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE"
LIVE_OE_NO_TRADE_REVIEW = "LIVE_OBSERVATIONAL_NO_TRADE_REVIEW"

_ADMIT_METHOD_NAMES = (
    "admit_event",
    "admit_provider_event",
    "admit_observation",
    "admit_event_v1",
    "dispatch_eventv1",
    "handle_event_admit",
    "handle_observation_ingress",
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
    "/intelligence/ingest/news",
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


def _current_news_clocks() -> tuple[str, str]:
    """Publication then retrieval. Current UTC, never 2026-07-21 fixture time."""

    retrieved_dt = datetime.now(timezone.utc).replace(microsecond=0)
    published_dt = retrieved_dt - timedelta(seconds=8)
    published = published_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    retrieved = retrieved_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    if "2026-07-21" in published or "2026-07-21" in retrieved:
        raise AssertionError("controlled news clocks must not use 2026-07-21 fixture time")
    return published, retrieved


def _controlled_lawful_like_news_ingest_body(*, published_time: str, retrieved_time: str) -> dict:
    """Known POST /intelligence/ingest/news body. Not a new HTTP shape."""

    return {
        "retrieved_time": retrieved_time,
        "articles": [
            {
                "headline": "Example Corp reports quarterly earnings",
                "published_time": published_time,
                "url": "https://example.com/software-fullstack-news",
                "tickers": ["AAPL"],
                "publisher_source": "Wire",
                "provider_native_id": "software-fullstack-news-1",
            }
        ],
    }


def _http_json(
    port: int,
    method: str,
    path: str,
    *,
    body: dict | None = None,
) -> tuple[int, dict | str]:
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
        """Full production chain. Fails honestly at the first unwired step."""

        self.assertFalse(live_observational_enabled())
        require_ui_handler_eventv1_admit()

        published_time, retrieved_time = _current_news_clocks()
        ingest_body = _controlled_lawful_like_news_ingest_body(
            published_time=published_time,
            retrieved_time=retrieved_time,
        )
        self.assertNotEqual(ingest_body.get("live_claim"), "CLAIMED")
        self.assertNotIn("collection_root", ingest_body)
        self.assertEqual(NEWS_INGEST_ROUTE, "/intelligence/ingest/news")

        reset_operator_acks()
        store = ReplayStore(collection_root=self._tmp.name)
        store.data_mode = "LIVE_OBSERVATIONAL"
        store.mode = "LIVE"
        bind_ui_api_intelligence(store)
        previous_store = getattr(UiApiHandler, "store", None)
        UiApiHandler.store = store
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), UiApiHandler)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        runtime_patch = patch(
            "market_platform_foundation.market_data.live_runtime.get_live_runtime",
            return_value=None,
        )
        auth_patch = patch.object(UiApiHandler, "_authorize_request", return_value=True)
        runtime_patch.start()
        auth_patch.start()
        try:
            status, ingest = _http_json(port, "POST", NEWS_INGEST_ROUTE, body=ingest_body)
            if status != 200 or not isinstance(ingest, dict) or int(ingest.get("admitted_count") or 0) < 1:
                raise AssertionError(
                    f"{P2_EVENTV1_ADMIT_FAILED}: POST {NEWS_INGEST_ROUTE} did not admit "
                    f"EventV1. status={status} body={ingest!r}. This is a FAIL, not a skip."
                )
            events = ingest.get("events") or []
            if not events or not isinstance(events[0], dict) or not events[0].get("event_id"):
                raise AssertionError(
                    f"{P2_EVENTV1_ADMIT_FAILED}: ingest response has no event_id. body={ingest!r}"
                )
            row = events[0]
            event_time_ns = row.get("event_time_ns")
            available_time_ns = row.get("available_time_ns")
            received_time_ns = row.get("received_time_ns")
            if event_time_ns is None or available_time_ns is None or event_time_ns == available_time_ns:
                raise AssertionError(
                    f"{P2_PIT_CLOCKS_INVALID}: EventV1 publication and retrieval clocks "
                    f"must stay distinct. event={row!r}"
                )
            if received_time_ns is not None and event_time_ns >= received_time_ns:
                raise AssertionError(
                    f"{P2_PIT_CLOCKS_INVALID}: event_time_ns must precede received_time_ns. "
                    f"event={row!r}"
                )
            stored = store.strategy_repository.get_event(row["event_id"])
            if stored is None:
                raise AssertionError(
                    f"{P2_EVENTV1_ADMIT_FAILED}: admitted event_id={row['event_id']!r} "
                    "did not persist/read back from the handler repository."
                )
            self.assertEqual(stored.event_type, "NEWS_ARTICLE")
            self.assertNotIn("2026-07-21", str(ingest))

            opportunity_ids = ingest.get("opportunity_ids") or []
            if (
                int(ingest.get("opportunity_count") or 0) < 1
                or not opportunity_ids
                or row.get("detector_detail") != "NEWS_ARTICLE_OPPORTUNITY_MINTED"
            ):
                raise AssertionError(
                    f"{P3_DETECTOR_OPPORTUNITY_MISSING}: EventV1 admitted but detector "
                    f"did not mint OpportunityV1. ingest={ingest!r}. This is a FAIL, not a skip."
                )
            opportunity_id = str(opportunity_ids[0])
            persisted_opportunity = store.strategy_repository.get_opportunity(opportunity_id)
            if persisted_opportunity is None:
                raise AssertionError(
                    f"{P3_DETECTOR_OPPORTUNITY_MISSING}: opportunity_id={opportunity_id!r} "
                    "did not persist/read back."
                )

            summary_status, summary = _http_json(port, "GET", "/opportunities/summary")
            summary_text = str(summary)
            assembled = build_opportunities_summary_payload(store)
            if summary_status == 403 and LIVE_OE_NO_MUTATION in summary_text:
                raise AssertionError(
                    f"{P4_RANKED_SUMMARY_BLOCKED}: {LIVE_OE_NO_MUTATION} on "
                    "GET /opportunities/summary. Ranked observational read is fail-closed. "
                    "This is a FAIL, not a skip."
                )
            if summary_status != 200 or not isinstance(summary, dict):
                reason = ""
                if isinstance(summary, dict):
                    reason = str(summary.get("reason_code") or summary.get("error") or "")
                raise AssertionError(
                    f"{P4_RANKED_SUMMARY_BLOCKED}: GET /opportunities/summary is not "
                    f"reachable on the request path. status={summary_status} "
                    f"reason={reason or summary!r}. In-process ranked assembly "
                    f"feed_status={assembled.get('feed_status')!r} "
                    f"items={len(assembled.get('items') or [])} "
                    f"(not a substitute for the HTTP read). This is a FAIL, not a skip."
                )
            items = summary.get("items") or []
            if summary.get("feed_status") != "READY" or not items:
                raise AssertionError(
                    f"{P4_RANKED_SUMMARY_MISSING}: ranked observational summary is not READY "
                    f"with OpportunityV1 items. summary={summary!r}"
                )
            if "2026-07-21" in str(summary.get("as_of_context", {})):
                raise AssertionError(
                    f"{P4_RANKED_SUMMARY_MISSING}: ranked as_of used 2026-07-21 fixture time. "
                    f"as_of_context={summary.get('as_of_context')!r}"
                )
            self.assertEqual(items[0].get("identity_kind"), "OPPORTUNITY_V1")
            self.assertEqual(items[0].get("opportunity_id"), opportunity_id)

            watch_status, watch_body = _http_json(
                port,
                "POST",
                f"/opportunities/{opportunity_id}/watch",
                body={},
            )
            if watch_status == 200:
                detail_status, detail = _http_json(port, "GET", f"/opportunities/{opportunity_id}")
                if detail_status != 200 or not isinstance(detail, dict):
                    raise AssertionError(
                        f"{P6_DECISION_TRACE_UNREACHABLE}: WATCH succeeded but opportunity "
                        f"detail/DecisionTrace readback failed. status={detail_status} body={detail!r}"
                    )
                review_status, review = _http_json(
                    port,
                    "GET",
                    f"/intelligence/trade-reviews?opportunity_id={opportunity_id}",
                )
                if (
                    review_status != 200
                    or not isinstance(review, dict)
                    or not review.get("items")
                    or LIVE_OE_NO_TRADE_REVIEW in str(review)
                ):
                    raise AssertionError(
                        f"{P7_TRADE_REVIEW_UNREACHABLE}: WATCH succeeded but TradeReview "
                        f"persist/readback is not wired. status={review_status} body={review!r}"
                    )
                raise AssertionError(
                    f"{P6_DECISION_TRACE_UNREACHABLE}: WATCH/TradeReview reads succeeded "
                    "but DecisionTrace request-path readback is not a known UiApiHandler route."
                )
            raise AssertionError(
                f"{P5_WATCH_DISMISS_BLOCKED}: {LIVE_OE_NO_MUTATION}. EventV1 admit, PIT "
                "clocks, detector OpportunityV1, and GET /opportunities/summary are wired. "
                "WATCH/DISMISS are not reachable without mutation authority. "
                f"status={watch_status} body={watch_body!r}. This is a FAIL, not a skip."
            )
        finally:
            auth_patch.stop()
            runtime_patch.stop()
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)
            if previous_store is not None:
                UiApiHandler.store = previous_store
            elif hasattr(UiApiHandler, "store"):
                delattr(UiApiHandler, "store")


if __name__ == "__main__":
    unittest.main()
