"""AUD-001 / AUD-039: browser-origin policy and fail-closed route policy.

Every HTTP case drives the real ``UiApiHandler`` / ``ControlHandler`` on an ephemeral loopback port with the
route callbacks replaced by recording no-ops, so a refused request is proven to stop before any callback.
"""

from __future__ import annotations

import ast
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from market_platform_foundation.platform.security import origin_policy
from market_platform_foundation.platform.security.access_control import (
    AuthorizationFailure,
    AuthorizedPrincipal,
    authorize_capability,
)
from market_platform_foundation.platform.security.origin_policy import (
    CONTENT_TYPE_NOT_JSON,
    CROSS_SITE_REQUEST,
    ORIGIN_NOT_ALLOWED,
    allowed_request_origin,
    browser_request_refusal,
)
from market_platform_foundation.platform.security.roles import OperatorRole
from market_platform_foundation.platform.security.route_policy import (
    PAPER_AUTOMATION_BASE,
    PAPER_AUTOMATION_CAPABILITIES,
    policy_for_route,
)
from market_platform_foundation.ui_api import server as server_module
from market_platform_foundation.ui_api.request_auth import authorize_http_request

UI = "http://127.0.0.1:5173"
FOREIGN = "https://attacker.invalid"
SERVER_SOURCE = Path(server_module.__file__)

# One concrete probe per mutating dispatch branch of do_POST/do_PUT (prefix/suffix branches need an id).
POST_PROBES = (
    "/evaluation/paper-performance/runs/RUN-1/refresh-benchmark", "/evaluation/paper-performance/runs",
    "/evaluation/prospective/runs", "/evaluation/prospective/rerun",
    "/screener/window", "/screener/window/release", "/screener/panels", "/screener/panels/release",
    "/screener/config", "/screener/providers/moomoo/connect", "/screener/news/synthesis/engine",
    "/screener/news/synthesis", "/screener/action-decision/preview", "/screener/action-decision/run",
    "/screener/action-decision/handoff", "/screener/next-session/draft", "/screener/next-session/lock",
    "/screener/next-session/observe", "/screener/next-session/evaluate", "/paper/risk-control/sma-stop/configure",
    "/paper/risk-control/sma-stop/evaluate", "/screener/reevaluation/configure", "/screener/reevaluation/start",
    "/screener/reevaluation/stop", "/screener/reevaluation/run-once", "/screener/ai-screener/runs/RUN-1/stop",
    "/screener/ai-screener", "/opportunities/ROW-1/watch", "/opportunities/ROW-1/dismiss",
    "/opportunities/ROW-1/review", "/controlled-replay/advance-clock", "/operator/lifecycle/actions",
    "/intelligence/ingest/news", "/intelligence/ingest/research-artifact-attachment",
    "/intelligence/ingest/enrichment", "/intelligence/ingest/enrichment/REC-1", "/discover/mixed/refresh",
    "/discover/mixed/release", "/canary/command", "/paper/orders/preview", "/paper/orders",
    "/paper/broker/orders/poll", "/paper/broker/reconciliation", "/paper/sessions", "/paper/experiments",
    "/paper/experiments/EXP-1/close", "/paper/sessions/close", "/paper/forward-tests/sessions",
    "/paper/forward-tests/decisions", "/paper/forward-tests/lock", "/paper/forward-tests/submit",
    "/paper/forward-tests/observe", "/paper/forward-tests/evaluate", "/operator/watchlist",
    "/operator/config/provider", "/operator/providers/moomoo/refresh", "/operator/recent", "/operator/workspace",
    "/operator/investigations", "/operator/investigations/WS-1/note", "/operator/preferences", "/captures/replay",
    "/paper/orders/cancel", "/paper/orders/replace", "/discover/promote-to-live-analysis", "/subscriptions",
    "/subscriptions/release", "/replay/scrub", "/assistant/conversations", "/assistant/conversations/CONV-1/prompt",
) + tuple(PAPER_AUTOMATION_BASE + op for op, (verb, _cap) in PAPER_AUTOMATION_CAPABILITIES.items() if verb == "POST")
PUT_PROBES = ("/intelligence/trade-reviews/REV-1/operator", "/intelligence/ingest/enrichment/REC-1")
# Explicit, documented reads reached by POST (a preview never mutates). Anything else that mutates needs write.
# /evaluation/prospective/rerun only reproduces a stored run (pre-existing explicit audit.read policy).
# Screener window/panel demand is explicitly read-scoped viewing demand (test_screener_s4.test_routes_are_read_scoped).
EXPLICIT_READ_POSTS = frozenset({"/screener/action-decision/preview", "/evaluation/prospective/rerun",
                                 "/screener/window", "/screener/window/release", "/screener/panels",
                                 "/screener/panels/release"})
# /canary/command takes its capability per command (route_policy.capability_for_canary_command).
PER_COMMAND_POSTS = frozenset({"/canary/command"})
# The routes AUD-039 found authorized as reads; each now needs an explicit write/order/ingest capability.
AUD039_ROUTES = (
    ("POST", "/paper/orders/replace"), ("POST", "/paper/forward-tests/submit"),
    ("POST", "/paper/forward-tests/decisions"), ("POST", "/paper/forward-tests/lock"),
    ("POST", "/paper/broker/orders/poll"), ("POST", "/paper/broker/reconciliation"),
    ("PUT", "/intelligence/trade-reviews/REV-1/operator"),
    ("POST", "/intelligence/ingest/research-artifact-attachment"),
)


def _route_literals(method_name: str) -> tuple[set[str], set[str]]:
    """Exact and prefix route literals compared against ``path`` inside one ``do_*`` method (AST)."""
    tree = ast.parse(SERVER_SOURCE.read_text(encoding="utf-8"))
    exact, prefixes = set(), set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef) and node.name == method_name):
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Compare) and isinstance(sub.left, ast.Name) and sub.left.id == "path":
                for comp in sub.comparators:
                    values = comp.elts if isinstance(comp, (ast.Tuple, ast.Set, ast.List)) else [comp]
                    exact |= {v.value for v in values if isinstance(v, ast.Constant) and str(v.value).startswith("/")}
            if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and sub.func.attr == "startswith"
                    and isinstance(sub.func.value, ast.Name) and sub.func.value.id == "path" and sub.args
                    and isinstance(sub.args[0], ast.Constant)):
                prefixes.add(sub.args[0].value)
    return exact, prefixes


class OriginPolicyUnitTests(unittest.TestCase):
    def test_only_the_ui_origins_are_allowed_and_reflected(self) -> None:
        for origin in (UI, "http://localhost:5173", "HTTP://LOCALHOST:5173"):
            self.assertIsNone(browser_request_refusal("POST", {"Origin": origin, "Content-Type": "application/json"}))
        self.assertEqual(allowed_request_origin({"Origin": UI}), UI)
        for origin in (FOREIGN, "null", "http://127.0.0.1:8080", "http://[::1]:5173", "http://imp.localhost:5173",
                       "http://127.0.0.1.evil.example:5173", "http://127.0.0.1:5173/path", "file://", "http://[", "http://127.0.0.1:bad"):
            with self.subTest(origin=origin):
                self.assertEqual(browser_request_refusal("GET", {"Origin": origin}), ORIGIN_NOT_ALLOWED)
                self.assertIsNone(allowed_request_origin({"Origin": origin}))

    def test_cross_site_fetch_metadata_is_refused_even_without_origin(self) -> None:
        self.assertEqual(browser_request_refusal("GET", {"Sec-Fetch-Site": "cross-site"}), CROSS_SITE_REQUEST)
        self.assertEqual(browser_request_refusal("GET", {"Origin": UI, "Sec-Fetch-Site": "cross-site"}),
                         CROSS_SITE_REQUEST)
        self.assertIsNone(browser_request_refusal("GET", {"Sec-Fetch-Site": "none"}))  # typed in the address bar

    def test_a_browser_mutation_needs_a_json_body_type(self) -> None:
        for content_type in ("text/plain;charset=UTF-8", "application/x-www-form-urlencoded", "multipart/form-data",
                             ""):
            with self.subTest(content_type=content_type):
                self.assertEqual(browser_request_refusal("POST", {"Origin": UI, "Content-Type": content_type}),
                                 CONTENT_TYPE_NOT_JSON)
        self.assertIsNone(browser_request_refusal("POST", {"Origin": UI,
                                                           "Content-Type": "application/json; charset=utf-8"}))

    def test_non_browser_callers_are_unaffected(self) -> None:
        # The keeper, launcher, CLI and tests send no browser markers; urllib's default form type is fine for them.
        for headers in ({}, {"User-Agent": "imp-keeper/1.0"},
                        {"Content-Type": "application/x-www-form-urlencoded"}):
            self.assertIsNone(browser_request_refusal("POST", headers))

    def test_extra_origins_are_exact_and_explicit(self) -> None:
        env = {origin_policy.ALLOWED_ORIGINS_ENV: "http://127.0.0.1:51730, bogus"}
        self.assertIsNone(browser_request_refusal("GET", {"Origin": "http://127.0.0.1:51730"}, env))
        self.assertEqual(browser_request_refusal("GET", {"Origin": "http://127.0.0.1:51731"}, env),
                         ORIGIN_NOT_ALLOWED)


class RoutePolicyFailClosedTests(unittest.TestCase):
    def test_every_dispatched_mutation_has_an_explicit_policy(self) -> None:
        for method, probes in (("POST", POST_PROBES), ("PUT", PUT_PROBES)):
            for path in probes:
                with self.subTest(method=method, path=path):
                    policy = policy_for_route(method, path)
                    self.assertFalse(policy.refused)
                    if path not in EXPLICIT_READ_POSTS | PER_COMMAND_POSTS:
                        self.assertNotIn(policy.capability, (None, "state.read", "audit.read"))

    def test_the_probe_table_covers_every_route_literal_in_the_server(self) -> None:
        # Completeness: a new do_POST/do_PUT branch must be added to the probes (and so to route_policy).
        for method, probes in (("do_POST", POST_PROBES), ("do_PUT", PUT_PROBES)):
            exact, prefixes = _route_literals(method)
            exact -= {"/auth/login", "/auth/logout"}  # handled before authorization
            if method == "do_POST":
                exact.add("/intelligence/ingest/news")  # compared via news_ingest.NEWS_INGEST_ROUTE
            for literal in sorted(exact):
                self.assertIn(literal, probes, f"{method} {literal}")
            for prefix in sorted(prefixes):
                self.assertTrue(any(p.startswith(prefix) for p in probes), f"{method} prefix {prefix}")

    def test_unmapped_mutations_are_refused_in_loopback_trust(self) -> None:
        for method, path in (("POST", "/paper/automation/liquidate"), ("POST", "/paper/orders/mass-cancel"),
                             ("PUT", "/paper/orders"), ("POST", "/control/shutdown"), ("DELETE", "/paper/orders")):
            with self.subTest(method=method, path=path):
                self.assertTrue(policy_for_route(method, path).refused)
                result = authorize_http_request(mock.Mock(), method=method, path=path, headers={}, query={}, body={})
                self.assertIsInstance(result, AuthorizationFailure)
                self.assertIn("ROUTE_POLICY_UNMAPPED", result.message)
        self.assertFalse(policy_for_route("GET", "/some/unknown/read").refused)

    def test_unknown_evaluation_action_cannot_inherit_read_authority(self) -> None:
        policy = policy_for_route("POST", "/evaluation/prospective/unknown/rerun")
        self.assertTrue(policy.refused)

    def test_request_authorization_enforces_privileged_route_roles(self) -> None:
        from market_platform_foundation.ui_api import request_auth
        cases = (
            ("POST", "/operator/lifecycle/actions", OperatorRole.OPERATOR),
            ("POST", "/paper/automation/start", OperatorRole.OPERATOR),
            ("POST", "/paper/orders/replace", OperatorRole.OPERATOR),
            ("POST", "/operator/config/provider", OperatorRole.ADMIN),
            ("POST", "/screener/news/synthesis/engine", OperatorRole.OPERATOR),
            ("POST", "/evaluation/prospective/runs", OperatorRole.OPERATOR),
        )
        store = mock.Mock()
        store.paper_ledger.events = []
        for method, path, minimum_role in cases:
            for role in OperatorRole:
                principal = AuthorizedPrincipal("fixture", "fixture", role, frozenset({"*"}))
                with self.subTest(path=path, role=role), mock.patch.object(
                    request_auth, "authenticate_session_token", return_value=principal
                ):
                    result = authorize_http_request(store, method=method, path=path,
                                                    headers={}, query={}, body={})
                    permitted = role == OperatorRole.ADMIN or (
                        role == OperatorRole.OPERATOR and minimum_role == OperatorRole.OPERATOR)
                    self.assertEqual(isinstance(result, AuthorizedPrincipal), permitted)

    def test_enforced_roles_viewer_cannot_mutate_operator_can(self) -> None:
        viewer = AuthorizedPrincipal("v", "v", OperatorRole.VIEWER, frozenset({"*"}))
        operator = AuthorizedPrincipal("o", "o", OperatorRole.OPERATOR, frozenset({"*"}))
        for method, probes in (("POST", POST_PROBES), ("PUT", PUT_PROBES)):
            for path in probes:
                if path in EXPLICIT_READ_POSTS | PER_COMMAND_POSTS:
                    continue
                with self.subTest(method=method, path=path):
                    capability = policy_for_route(method, path).capability
                    self.assertIsNotNone(authorize_capability(viewer, capability))
        for method, path in AUD039_ROUTES:
            with self.subTest(method=method, path=path):
                self.assertIsNone(authorize_capability(operator, policy_for_route(method, path).capability))
        self.assertEqual(policy_for_route("POST", "/paper/orders/replace").capability, "paper.order.submit")
        from market_platform_foundation.platform.security.route_policy import capability_for_canary_command

        for command in ("confirm_order", "authorize_session", "anything_else"):
            self.assertIsNotNone(authorize_capability(viewer, capability_for_canary_command({"command": command})))


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, name: str):
        def record(*_args, **_kwargs):
            self.calls.append(name)
            return {"ok": True, "callback": name}
        return record


def _request(base: str, method: str, path: str, *, headers: dict[str, str] | None = None,
             body: bytes | None = None) -> tuple[int, dict[str, str], dict]:
    request = urllib.request.Request(base + path, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            raw = response.read()
            return response.status, dict(response.headers.items()), json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return exc.code, dict(exc.headers.items()), json.loads(raw) if raw else {}


class UiApiHandlerOriginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.recorder = _Recorder()
        service = mock.Mock()
        for op in ("disarm", "pause", "stop", "start", "resume"):
            setattr(service, op, cls.recorder(f"automation.{op}"))
        for op in ("configure", "arm", "emergency_stop"):
            setattr(service, op, cls.recorder(f"automation.{op}"))
        cls.patches = [
            mock.patch.object(server_module.projections, "build_context_payload", cls.recorder("context")),
            mock.patch("market_platform_foundation.ui_api.paper_automation.paper_automation_service",
                       lambda _store: service),
            mock.patch.object(server_module.paper_projections, "replace_paper_order", cls.recorder("orders.replace")),
            mock.patch.object(server_module.forward_test_projections, "submit_forward_test_to_paper",
                              cls.recorder("forward.submit")),
            mock.patch("tools.platform.control_service._spawn_action", cls.recorder("lifecycle")),
        ]
        for patch in cls.patches:
            patch.start()
        store = mock.Mock()
        store.paper_ledger.events = []  # no Paper identity: account scope resolves to None
        store.controlled_replay = False
        cls.previous_store = getattr(server_module.UiApiHandler, "store", None)
        server_module.UiApiHandler.store = store
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), server_module.UiApiHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        for patch in cls.patches:
            patch.stop()
        server_module.UiApiHandler.store = cls.previous_store

    def setUp(self) -> None:
        self.recorder.calls.clear()

    def test_foreign_origin_read_is_refused_before_the_handler_and_gets_no_cors(self) -> None:
        status, headers, payload = _request(self.base, "GET", "/context", headers={"Origin": FOREIGN})
        self.assertEqual(status, 403)
        self.assertIn(ORIGIN_NOT_ALLOWED, json.dumps(payload))
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        self.assertEqual(self.recorder.calls, [])

    def test_ui_origin_read_is_served_with_its_exact_origin(self) -> None:
        status, headers, _payload = _request(self.base, "GET", "/context", headers={"Origin": UI})
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), UI)
        self.assertEqual(self.recorder.calls, ["context"])

    def test_non_browser_read_is_served_without_cors(self) -> None:
        status, headers, _payload = _request(self.base, "GET", "/context")
        self.assertEqual(status, 200)
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        self.assertNotEqual(headers.get("Access-Control-Allow-Origin"), "*")

    def test_preflight_is_refused_for_foreign_origins_and_exact_for_the_ui(self) -> None:
        status, headers, _ = _request(self.base, "OPTIONS", "/paper/automation/disarm",
                                      headers={"Origin": FOREIGN, "Access-Control-Request-Method": "POST"})
        self.assertEqual(status, 403)
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        status, headers, _ = _request(self.base, "OPTIONS", "/paper/automation/disarm",
                                      headers={"Origin": UI, "Access-Control-Request-Method": "POST"})
        self.assertEqual(status, 204)
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), UI)

    def test_foreign_origin_mutations_never_reach_a_callback(self) -> None:
        cases = [("POST", PAPER_AUTOMATION_BASE + op) for op in ("disarm", "stop", "emergency-stop", "arm",
                                                                 "configure", "start", "pause", "resume")]
        cases += [("POST", "/paper/orders/replace"), ("POST", "/paper/forward-tests/submit"),
                  ("POST", "/operator/lifecycle/actions"), ("POST", "/screener/ai-screener"),
                  ("POST", "/screener/reevaluation/run-once"), ("POST", "/screener/news/synthesis"),
                  ("PUT", "/intelligence/trade-reviews/REV-1/operator")]
        for method, path in cases:
            for content_type in ("text/plain;charset=UTF-8", "application/json"):
                with self.subTest(method=method, path=path, content_type=content_type):
                    body = b'{"action":"stop","reason":"x"}'
                    status, headers, payload = _request(self.base, method, path, body=body,
                                                        headers={"Origin": FOREIGN, "Content-Type": content_type})
                    self.assertEqual(status, 403)
                    self.assertIn(ORIGIN_NOT_ALLOWED, json.dumps(payload))
                    self.assertNotIn("Access-Control-Allow-Origin", headers)
        self.assertEqual(self.recorder.calls, [])

    def test_simple_request_text_plain_from_the_ui_origin_is_refused(self) -> None:
        status, _headers, payload = _request(self.base, "POST", "/paper/automation/disarm", body=b"{}",
                                             headers={"Origin": UI, "Content-Type": "text/plain;charset=UTF-8"})
        self.assertEqual(status, 403)
        self.assertIn(CONTENT_TYPE_NOT_JSON, json.dumps(payload))
        self.assertEqual(self.recorder.calls, [])

    def test_cross_site_fetch_metadata_without_origin_is_refused(self) -> None:
        status, _headers, _payload = _request(self.base, "GET", "/context", headers={"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(status, 403)
        self.assertEqual(self.recorder.calls, [])

    def test_the_ui_and_local_cli_keep_their_access(self) -> None:
        status, headers, _ = _request(self.base, "POST", "/paper/automation/disarm", body=b"{}",
                                      headers={"Origin": UI, "Content-Type": "application/json"})
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), UI)
        status, _headers, _ = _request(self.base, "POST", "/paper/automation/pause", body=b"{}")  # CLI, no Origin
        self.assertEqual(status, 200)
        self.assertEqual(self.recorder.calls, ["automation.disarm", "automation.pause"])

    def test_an_unmapped_mutation_is_refused_without_reaching_dispatch(self) -> None:
        status, _headers, payload = _request(self.base, "POST", "/paper/automation/liquidate", body=b"{}",
                                             headers={"Content-Type": "application/json"})
        self.assertEqual(status, 403)
        self.assertIn("ROUTE_POLICY_UNMAPPED", json.dumps(payload))
        self.assertEqual(self.recorder.calls, [])


class ControlServiceOriginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from tools.platform import control_service

        cls.module = control_service
        cls.tmp = tempfile.TemporaryDirectory()
        cls.recorder = _Recorder()
        cls.patch = mock.patch.object(control_service, "_spawn_action", cls.recorder("spawn"))
        cls.patch.start()
        control_service.ControlHandler.root = Path(cls.tmp.name)
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), control_service.ControlHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.patch.stop()
        cls.tmp.cleanup()

    def setUp(self) -> None:
        self.recorder.calls.clear()

    def test_foreign_or_simple_request_lifecycle_posts_are_refused(self) -> None:
        for headers in ({"Origin": FOREIGN, "Content-Type": "text/plain"},
                        {"Origin": FOREIGN, "Content-Type": "application/json"},
                        {"Origin": UI, "Content-Type": "text/plain"},
                        {"Sec-Fetch-Site": "cross-site", "Content-Type": "application/json"}):
            with self.subTest(headers=headers):
                status, _h, _p = _request(self.base, "POST", "/control/actions", body=b'{"action":"stop"}',
                                          headers=headers)
                self.assertEqual(status, 403)
        status, _h, payload = _request(self.base, "POST", "/control/actions", body=b"{}",
                                       headers={"Origin": FOREIGN, "Content-Type": "application/json"})
        self.assertEqual((payload["reason_code"], payload["error_category"]), (ORIGIN_NOT_ALLOWED, "AUTH_ERROR"))
        status, _h, _p = _request(self.base, "OPTIONS", "/control/actions", headers={"Origin": FOREIGN})
        self.assertEqual(status, 403)
        self.assertEqual(self.recorder.calls, [])

    def test_the_ui_and_launcher_still_reach_the_action(self) -> None:
        status, headers, _ = _request(self.base, "POST", "/control/actions", body=b'{"action":"stop"}',
                                      headers={"Origin": UI, "Content-Type": "application/json"})
        self.assertIn(status, (200, 202))
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), UI)
        status, _h, _ = _request(self.base, "POST", "/control/actions", body=b'{"action":"stop"}')
        self.assertIn(status, (200, 202))
        self.assertEqual(self.recorder.calls, ["spawn", "spawn"])


if __name__ == "__main__":
    unittest.main()
