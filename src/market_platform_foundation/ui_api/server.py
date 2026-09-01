"""Stdlib HTTP handler for UI-001 read-only API."""

from __future__ import annotations

import json
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from typing import Any
from urllib.parse import parse_qs, urlparse

from ..canonical import canonical_bytes, write_canonical_json
from ..platform.security.access_control import AuthorizationFailure, authenticate_session_token
from ..platform.security.leak_audit import assert_no_secrets_in_payload
from . import broker_projections
from . import canary_projections
from . import live_projections
from . import operator_projections
from . import paper_projections
from . import projections
from .account_registry import build_accounts_payload
from ..operational_identity import OperationalIdentityError
from .auth_projections import (
    build_auth_status_payload,
    build_auth_session_payload,
    build_security_readiness_payload,
    handle_auth_login,
    handle_auth_logout,
    unauthenticated_session_payload,
)
from .assistant_projections import (
    build_assistant_conversations,
    build_assistant_messages,
    build_assistant_status,
    create_assistant_conversation,
    submit_assistant_prompt,
)
from .lane_provenance import attach_lane_provenance
from .request_auth import (
    authorization_http_status,
    authorize_http_request,
    extract_session_token,
    log_server_event,
)
from .store import ReplayStore


def _enrich_lane_payload(payload: dict[str, Any], *, lane_id: str) -> dict[str, Any]:
    return attach_lane_provenance(payload, lane_id=lane_id, retrieved_at_ns=time.time_ns())

# ThreadingHTTPServer dispatches every request on its own thread against ONE
# shared ReplayStore. Ledger mutation is not individually thread-safe (the
# next-event-sequence max+1 and the idempotency lookup->record are
# read-modify-write pairs), so all ledger-mutating POST route bodies below
# serialize on this single lock. Deliberately coarse: no server restructure,
# no per-store locking; responses are sent after releasing the lock.
LEDGER_ROUTE_LOCK = threading.Lock()


class UiApiHandler(BaseHTTPRequestHandler):
    store: ReplayStore

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send_json(self, payload: dict[str, Any], *, status: HTTPStatus = HTTPStatus.OK) -> None:
        try:
            assert_no_secrets_in_payload(payload)
        except Exception as exc:
            log_server_event("ui_api.secret_leak_blocked", error=str(exc))
            self._send_error_json(
                "UI_SECRET_LEAK_BLOCKED",
                "Response blocked by secret-leak audit",
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, code: str, message: str, *, status: HTTPStatus) -> None:
        self._send_json({"error": message, "reason_code": code}, status=status)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-IMP-Session")
        self.end_headers()

    def _authorize_request(
        self,
        method: str,
        path: str,
        query: dict[str, list[str]],
        body: dict[str, Any] | None = None,
    ) -> bool:
        auth = authorize_http_request(
            self.store,
            method=method,
            path=path,
            headers=dict(self.headers.items()),
            query=query,
            body=body,
        )
        if isinstance(auth, AuthorizationFailure):
            self._send_error_json(
                auth.code.value,
                auth.message,
                status=authorization_http_status(auth),
            )
            return False
        return True

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)
        if path == "/auth/status":
            self._send_json(build_auth_status_payload())
            return
        if path == "/auth/session":
            token = extract_session_token(dict(self.headers.items()))
            principal = authenticate_session_token(token)
            if isinstance(principal, AuthorizationFailure):
                self._send_json(unauthenticated_session_payload())
                return
            self._send_json(build_auth_session_payload(principal, token=token))
            return
        if path == "/security/readiness":
            if not self._authorize_request("GET", path, query):
                return
            self._send_json(build_security_readiness_payload())
            return
        if not self._authorize_request("GET", path, query):
            return
        try:
            if path == "/provider/health":
                self._send_json(live_projections.build_provider_health_payload(self.store))
                return
            if path == "/provider/finviz/health":
                from .discovery_projections import build_finviz_diagnostics_payload

                self._send_json(build_finviz_diagnostics_payload())
                return
            if path == "/discover/screens":
                from .discovery_projections import build_discover_screens_payload

                self._send_json(build_discover_screens_payload())
                return
            if path == "/discover/run":
                from .discovery_projections import build_discover_run_payload

                screen_id = (query.get("screen") or ["SHORT_SQUEEZE_DISCOVERY"])[0]
                force = (query.get("force") or ["0"])[0] in ("1", "true", "yes")
                self._send_json(build_discover_run_payload(str(screen_id), force=force))
                return
            if path == "/discover/mixed":
                from .mixed_discovery_projections import build_mixed_discover_payload

                self._send_json(build_mixed_discover_payload())
                return
            if path == "/state/startup":
                self._send_json(operator_projections.build_startup_payload(self.store))
                return
            if path == "/operator/state":
                self._send_json(operator_projections.build_operator_state_payload(self.store))
                return
            if path == "/captures":
                try:
                    self._send_json(operator_projections.refresh_captures())
                except ValueError:
                    self._send_json({"captures": [], "indexed": 0, "persistence_enabled": False})
                return
            if path == "/paper/sessions":
                self._send_json(paper_projections.list_paper_sessions(self.store))
                return
            if path == "/symbols/search":
                query_text = (query.get("q") or [""])[0]
                self._send_json(live_projections.build_symbol_search_payload(str(query_text)))
                return
            if path.startswith("/instruments/") and path.endswith("/capabilities"):
                instrument_id = path.removeprefix("/instruments/").removesuffix("/capabilities")
                try:
                    self._send_json(live_projections.build_instrument_capabilities_payload(instrument_id))
                except Exception as exc:
                    print(f"CAPABILITIES_ERROR {instrument_id}: {exc!r}", flush=True)
                    self._send_json(
                        {
                            "capabilities": [],
                            "instrument_id": instrument_id.upper(),
                            "reason": f"CAPABILITIES_ERROR:{exc}",
                        }
                    )
                return
            if path.startswith("/market-state/"):
                instrument_id = path.removeprefix("/market-state/").strip("/")
                self._send_json(live_projections.build_market_state_payload(instrument_id))
                return
            if path == "/context":
                self._send_json(projections.build_context_payload(self.store))
                return
            if path == "/capabilities":
                self._send_json(
                    {
                        "as_of_context": projections.build_as_of_context(self.store),
                        "capability_states": projections.build_capabilities(self.store),
                    }
                )
                return
            if path == "/attention":
                cursor = query.get("cursor", [None])[0]
                limit_raw = query.get("limit", [None])[0]
                limit = int(limit_raw) if limit_raw else None
                self._send_json(projections.build_attention_page(self.store, cursor=cursor, limit=limit))
                return
            if path.startswith("/instruments/") and path.endswith("/overview"):
                instrument_id = path.removeprefix("/instruments/").removesuffix("/overview")
                self._send_json(projections.build_instrument_overview(self.store, instrument_id))
                return
            if path.startswith("/explain/"):
                ref = path.removeprefix("/explain/")
                self._send_json(projections.build_explain_payload(self.store, ref))
                return
            if path.startswith("/inspect/"):
                ref = path.removeprefix("/inspect/")
                self._send_json(projections.build_inspect_payload(self.store, ref))
                return
            if path == "/replay/session":
                self._send_json(projections.build_replay_session(self.store))
                return
            if path == "/research/analytics":
                self._send_json(projections.build_research_analytics_payload(self.store))
                return
            if path == "/research/models":
                self._send_json(projections.build_research_models_payload(self.store))
                return
            if path == "/research/simulation":
                self._send_json(projections.build_research_simulation_payload(self.store))
                return
            if path.startswith("/workspace/") and path.endswith("/institutional-flow"):
                symbol = path.removeprefix("/workspace/").removesuffix("/institutional-flow").strip("/")
                if not symbol:
                    self._send_error_json(
                        "UI_REQUEST_INVALID",
                        "workspace institutional-flow symbol is required",
                        status=HTTPStatus.BAD_REQUEST,
                    )
                    return
                self._send_json(
                    _enrich_lane_payload(
                        projections.build_workspace_institutional_flow_payload(self.store, symbol),
                        lane_id="institutional-flow",
                    )
                )
                return
            if path == "/explore/futures":
                as_of = projections.build_as_of_context(self.store)
                from ..donor_bridge.futures_projections import build_explore_futures_payload

                self._send_json(build_explore_futures_payload(as_of_context=as_of))
                return
            if path == "/explore/squeeze/scanner":
                as_of = projections.build_as_of_context(self.store)
                from ..donor_bridge.projections import build_explore_squeeze_scanner_payload

                self._send_json(build_explore_squeeze_scanner_payload(as_of_context=as_of))
                return
            if path == "/explore/squeeze":
                as_of = projections.build_as_of_context(self.store)
                from ..donor_bridge.projections import build_explore_squeeze_payload

                self._send_json(build_explore_squeeze_payload(as_of_context=as_of))
                return
            if path == "/explore/catalyst":
                as_of = projections.build_as_of_context(self.store)
                from ..donor_bridge.projections import build_explore_catalyst_payload

                self._send_json(build_explore_catalyst_payload(as_of_context=as_of))
                return
            if path.startswith("/workspace/") and path.endswith("/evidence"):
                symbol = path.removeprefix("/workspace/").removesuffix("/evidence").strip("/")
                if not symbol:
                    self._send_error_json(
                        "UI_REQUEST_INVALID",
                        "workspace evidence symbol is required",
                        status=HTTPStatus.BAD_REQUEST,
                    )
                    return
                from . import workspace_evidence

                data_mode = query.get("data_mode", ["frozen"])[0]
                self._send_json(
                    _enrich_lane_payload(
                        workspace_evidence.build_workspace_evidence_payload(
                            self.store,
                            symbol,
                            data_mode=str(data_mode),
                        ),
                        lane_id="evidence",
                    )
                )
                return
            if path.startswith("/workspace/") and path.endswith("/squeeze"):
                symbol = path.removeprefix("/workspace/").removesuffix("/squeeze").strip("/")
                if not symbol:
                    self._send_error_json(
                        "UI_REQUEST_INVALID",
                        "workspace squeeze symbol is required",
                        status=HTTPStatus.BAD_REQUEST,
                    )
                    return
                as_of = projections.build_as_of_context(self.store)
                from ..donor_bridge.projections import build_workspace_squeeze_payload

                data_mode = (query.get("data_mode") or ["frozen"])[0].strip().lower()
                self._send_json(
                    _enrich_lane_payload(
                        build_workspace_squeeze_payload(
                            symbol,
                            as_of_context=as_of,
                            prediction_cutoff=self.store.prediction_cutoff(),
                            data_mode=data_mode,
                        ),
                        lane_id="squeeze",
                    )
                )
                return
            if path.startswith("/workspace/") and path.endswith("/catalyst"):
                symbol = path.removeprefix("/workspace/").removesuffix("/catalyst").strip("/")
                if not symbol:
                    self._send_error_json(
                        "UI_REQUEST_INVALID",
                        "workspace catalyst symbol is required",
                        status=HTTPStatus.BAD_REQUEST,
                    )
                    return
                as_of = projections.build_as_of_context(self.store)
                from ..providers.projections import build_workspace_catalyst_payload as build_fixture_catalyst
                from ..donor_bridge.projections import build_workspace_catalyst_payload as build_bridge_catalyst

                payload = build_fixture_catalyst(
                    symbol,
                    as_of_context=as_of,
                    prediction_cutoff=self.store.prediction_cutoff(),
                )
                if not payload.get("available"):
                    payload = build_bridge_catalyst(symbol, as_of_context=as_of)
                self._send_json(_enrich_lane_payload(payload, lane_id="catalyst"))
                return
            if path.startswith("/workspace/") and path.endswith("/market-context"):
                symbol = path.removeprefix("/workspace/").removesuffix("/market-context").strip("/")
                if not symbol:
                    self._send_error_json(
                        "UI_REQUEST_INVALID",
                        "workspace market-context symbol is required",
                        status=HTTPStatus.BAD_REQUEST,
                    )
                    return
                as_of = projections.build_as_of_context(self.store)
                from ..providers.projections import build_workspace_market_context_payload

                self._send_json(
                    _enrich_lane_payload(
                        build_workspace_market_context_payload(
                            symbol,
                            as_of_context=as_of,
                            prediction_cutoff=self.store.prediction_cutoff(),
                        ),
                        lane_id="market-context",
                    )
                )
                return
            if path.startswith("/workspace/") and path.endswith("/disclosure"):
                symbol = path.removeprefix("/workspace/").removesuffix("/disclosure").strip("/")
                if not symbol:
                    self._send_error_json(
                        "UI_REQUEST_INVALID",
                        "workspace disclosure symbol is required",
                        status=HTTPStatus.BAD_REQUEST,
                    )
                    return
                as_of = projections.build_as_of_context(self.store)
                from ..providers.projections import build_workspace_disclosure_payload

                self._send_json(
                    _enrich_lane_payload(
                        build_workspace_disclosure_payload(
                            symbol,
                            as_of_context=as_of,
                            prediction_cutoff=self.store.prediction_cutoff(),
                        ),
                        lane_id="disclosure",
                    )
                )
                return
            if path.startswith("/workspace/") and path.endswith("/order-flow"):
                symbol = path.removeprefix("/workspace/").removesuffix("/order-flow").strip("/")
                if not symbol:
                    self._send_error_json(
                        "UI_REQUEST_INVALID",
                        "workspace order-flow symbol is required",
                        status=HTTPStatus.BAD_REQUEST,
                    )
                    return
                as_of = projections.build_as_of_context(self.store)
                live_payload = live_projections.build_live_order_flow_payload(symbol)
                if live_payload is not None and live_payload.get("available"):
                    self._send_json(_enrich_lane_payload(live_payload, lane_id="order-flow"))
                    return
                from ..providers.projections import build_workspace_order_flow_payload

                self._send_json(
                    _enrich_lane_payload(
                        build_workspace_order_flow_payload(
                            symbol,
                            as_of_context=as_of,
                            prediction_cutoff=self.store.prediction_cutoff(),
                        ),
                        lane_id="order-flow",
                    )
                )
                return
            if path.startswith("/workspace/") and path.endswith("/options"):
                symbol = path.removeprefix("/workspace/").removesuffix("/options").strip("/")
                if not symbol:
                    self._send_error_json(
                        "UI_REQUEST_INVALID",
                        "workspace options symbol is required",
                        status=HTTPStatus.BAD_REQUEST,
                    )
                    return
                as_of = projections.build_as_of_context(self.store)
                from ..providers.projections import build_workspace_options_payload

                self._send_json(
                    _enrich_lane_payload(
                        build_workspace_options_payload(
                            symbol,
                            as_of_context=as_of,
                            prediction_cutoff=self.store.prediction_cutoff(),
                        ),
                        lane_id="options",
                    )
                )
                return
            if path.startswith("/workspace/") and path.endswith("/large-transactions"):
                symbol = path.removeprefix("/workspace/").removesuffix("/large-transactions").strip("/")
                if not symbol:
                    self._send_error_json(
                        "UI_REQUEST_INVALID",
                        "workspace large-transactions symbol is required",
                        status=HTTPStatus.BAD_REQUEST,
                    )
                    return
                as_of = projections.build_as_of_context(self.store)
                from ..providers.projections import build_workspace_large_transactions_payload

                self._send_json(
                    _enrich_lane_payload(
                        build_workspace_large_transactions_payload(
                            symbol,
                            as_of_context=as_of,
                            prediction_cutoff=self.store.prediction_cutoff(),
                        ),
                        lane_id="large-transactions",
                    )
                )
                return
            if path.startswith("/workspace/") and path.endswith("/futures"):
                symbol = path.removeprefix("/workspace/").removesuffix("/futures").strip("/")
                if not symbol:
                    self._send_error_json(
                        "UI_REQUEST_INVALID",
                        "workspace futures symbol is required",
                        status=HTTPStatus.BAD_REQUEST,
                    )
                    return
                as_of = projections.build_as_of_context(self.store)
                from ..providers.projections import build_workspace_futures_payload

                self._send_json(
                    _enrich_lane_payload(
                        build_workspace_futures_payload(
                            symbol,
                            as_of_context=as_of,
                            prediction_cutoff=self.store.prediction_cutoff(),
                        ),
                        lane_id="futures",
                    )
                )
                return
            if path.startswith("/workspace/") and path.endswith("/fund-etf"):
                symbol = path.removeprefix("/workspace/").removesuffix("/fund-etf").strip("/")
                if not symbol:
                    self._send_error_json(
                        "UI_REQUEST_INVALID",
                        "workspace fund-etf symbol is required",
                        status=HTTPStatus.BAD_REQUEST,
                    )
                    return
                as_of = projections.build_as_of_context(self.store)
                from ..providers.projections import build_workspace_fund_etf_payload

                self._send_json(
                    _enrich_lane_payload(
                        build_workspace_fund_etf_payload(
                            symbol,
                            as_of_context=as_of,
                            prediction_cutoff=self.store.prediction_cutoff(),
                        ),
                        lane_id="fund-etf",
                    )
                )
                return
            if path.startswith("/workspace/") and path.endswith("/order-book"):
                symbol = path.removeprefix("/workspace/").removesuffix("/order-book").strip("/")
                if not symbol:
                    self._send_error_json(
                        "UI_REQUEST_INVALID",
                        "workspace order-book symbol is required",
                        status=HTTPStatus.BAD_REQUEST,
                    )
                    return
                as_of = projections.build_as_of_context(self.store)
                live_book = live_projections.build_live_order_book_payload(symbol)
                if live_book is not None and live_book.get("available"):
                    self._send_json(_enrich_lane_payload(live_book, lane_id="order-book"))
                    return
                from ..providers.projections import build_workspace_order_book_payload

                self._send_json(
                    _enrich_lane_payload(
                        build_workspace_order_book_payload(
                            symbol,
                            as_of_context=as_of,
                            prediction_cutoff=self.store.prediction_cutoff(),
                        ),
                        lane_id="order-book",
                    )
                )
                return
            if path == "/assistant/status":
                self._send_json(build_assistant_status(self.store))
                return
            if path == "/accounts":
                self._send_json(build_accounts_payload(self.store))
                return
            if path == "/canary/snapshot":
                query = parse_qs(parsed.query)
                account_id = query.get("account_id", [None])[0]
                try:
                    self._send_json(canary_projections.build_canary_snapshot_payload(account_id=account_id))
                except ValueError as exc:
                    self._send_error_json("OPERATIONAL_ACCOUNT_UNKNOWN", str(exc), status=HTTPStatus.BAD_REQUEST)
                return
            if path == "/canary/authorization/preview":
                self._send_json(canary_projections.build_canary_authorization_preview_payload())
                return
            if path == "/canary/timeline":
                self._send_json(canary_projections.build_canary_timeline_payload())
                return
            if path == "/canary/reconciliation":
                query = parse_qs(parsed.query)
                account_id = query.get("account_id", [None])[0]
                try:
                    self._send_json(
                        canary_projections.build_canary_reconciliation_payload(account_id=account_id)
                    )
                except ValueError as exc:
                    self._send_error_json("OPERATIONAL_ACCOUNT_UNKNOWN", str(exc), status=HTTPStatus.BAD_REQUEST)
                return
            if path == "/canary/incidents":
                self._send_json(canary_projections.build_canary_incidents_payload())
                return
            if path == "/canary/action-inventory":
                self._send_json(canary_projections.build_canary_action_inventory())
                return
            if path == "/canary/reliability":
                self._send_json(canary_projections.build_canary_reliability_payload())
                return
            if path == "/canary/pilot":
                self._send_json(canary_projections.build_canary_pilot_payload())
                return
            if path == "/canary/deployment":
                self._send_json(canary_projections.build_canary_deployment_payload())
                return
            if path == "/paper/account":
                self._send_json(paper_projections.build_paper_account_payload(self.store))
                return
            if path == "/paper/positions":
                self._send_json(paper_projections.build_paper_positions_payload(self.store))
                return
            if path == "/paper/orders":
                self._send_json(paper_projections.build_paper_orders_payload(self.store))
                return
            if path == "/paper/order-history":
                query = parse_qs(parsed.query)
                cursor = query.get("cursor", [None])[0]
                limit_raw = query.get("limit", [None])[0]
                limit = int(limit_raw) if limit_raw else None
                self._send_json(
                    paper_projections.build_paper_order_history_page(
                        self.store,
                        cursor=str(cursor) if cursor else None,
                        limit=limit,
                    )
                )
                return
            if path == "/paper/fills":
                self._send_json(paper_projections.build_paper_fills_payload(self.store))
                return
            if path == "/paper/risk":
                self._send_json(paper_projections.build_paper_risk_payload(self.store))
                return
            if path == "/paper/portfolio":
                query = parse_qs(parsed.query)
                view_mode = query.get("view_mode", [None])[0]
                try:
                    self._send_json(
                        paper_projections.build_paper_portfolio_payload(self.store, view_mode=view_mode)
                    )
                except OperationalIdentityError as exc:
                    self._send_error_json("OPERATIONAL_IDENTITY_INVALID", str(exc), status=HTTPStatus.BAD_REQUEST)
                return
            if path == "/paper/trace":
                query = parse_qs(parsed.query)
                intent_id = query.get("intent_id", [None])[0]
                order_id = query.get("order_id", [None])[0]
                fill_id = query.get("fill_id", [None])[0]
                try:
                    self._send_json(
                        paper_projections.build_paper_trace_payload(
                            self.store,
                            intent_id=str(intent_id) if intent_id else None,
                            order_id=str(order_id) if order_id else None,
                            fill_id=str(fill_id) if fill_id else None,
                        )
                    )
                except ValueError as exc:
                    self._send_error_json("PAPER_TRACE_NOT_FOUND", str(exc), status=HTTPStatus.BAD_REQUEST)
                return
            if path == "/paper/broker/orders":
                self._send_json(broker_projections.build_broker_orders_payload(self.store))
                return
            if path == "/paper/broker/account":
                self._send_json(broker_projections.build_broker_account_payload(self.store))
                return
            if path == "/paper/broker/positions":
                self._send_json(broker_projections.build_broker_positions_payload(self.store))
                return
            if path == "/paper/broker/reconciliation":
                self._send_json(broker_projections.build_broker_reconciliation_payload(self.store))
                return
            if path == "/paper/broker/health":
                self._send_json(broker_projections.build_broker_health_payload(self.store))
                return
            if path == "/assistant/conversations":
                principal = query.get("principal_id", [None])[0]
                self._send_json(build_assistant_conversations(self.store, principal))
                return
            if path.startswith("/assistant/conversations/") and path.endswith("/messages"):
                conversation_id = path.removeprefix("/assistant/conversations/").removesuffix("/messages")
                if not conversation_id:
                    self._send_error_json(
                        "UI_REQUEST_INVALID",
                        "conversation id required",
                        status=HTTPStatus.BAD_REQUEST,
                    )
                    return
                self._send_json(build_assistant_messages(self.store, conversation_id))
                return
            self._send_error_json("UI_ROUTE_NOT_FOUND", f"Unknown path: {path}", status=HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self._send_error_json("UI_REQUEST_INVALID", str(exc), status=HTTPStatus.BAD_REQUEST)
        except KeyError:
            self._send_error_json("UI_ASSISTANT_NOT_FOUND", "conversation not found", status=HTTPStatus.NOT_FOUND)
        except Exception as exc:
            log_server_event("ui_api.internal_error", path=path, error=repr(exc))
            self._send_error_json("UI_INTERNAL_ERROR", str(exc), status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_error_json("UI_JSON_INVALID", "Invalid JSON body", status=HTTPStatus.BAD_REQUEST)
            return
        if not isinstance(body, dict):
            self._send_error_json("UI_JSON_INVALID", "Body must be an object", status=HTTPStatus.BAD_REQUEST)
            return
        if path == "/auth/login":
            result = handle_auth_login(body)
            if isinstance(result, AuthorizationFailure):
                self._send_error_json(
                    result.code.value,
                    result.message,
                    status=HTTPStatus.UNAUTHORIZED,
                )
                return
            self._send_json(result)
            return
        if path == "/auth/logout":
            token = extract_session_token(dict(self.headers.items()))
            self._send_json(handle_auth_logout(token))
            return
        if not self._authorize_request("POST", path, parse_qs(parsed.query), body):
            return
        if path == "/discover/mixed/refresh":
            from .mixed_discovery_projections import refresh_mixed_discovery

            screen_ids = body.get("screen_ids")
            if screen_ids is not None and (
                not isinstance(screen_ids, list)
                or any(not isinstance(screen_id, str) for screen_id in screen_ids)
            ):
                self._send_error_json(
                    "UI_REQUEST_INVALID",
                    "screen_ids must be a list of screen id strings",
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            try:
                self._send_json(refresh_mixed_discovery(screen_ids))
            except ValueError as exc:
                self._send_error_json(
                    "UI_REQUEST_INVALID",
                    str(exc),
                    status=HTTPStatus.BAD_REQUEST,
                )
            return
        if path == "/discover/mixed/release":
            from .mixed_discovery_projections import release_mixed_live_subscriptions

            self._send_json(release_mixed_live_subscriptions())
            return
        if path == "/canary/command":
            try:
                with LEDGER_ROUTE_LOCK:
                    payload = canary_projections.handle_canary_command(body)
                self._send_json(payload)
            except (KeyError, TypeError, ValueError) as exc:
                self._send_error_json("CANARY_COMMAND_FAILED", str(exc), status=HTTPStatus.BAD_REQUEST)
            return

        if path == "/paper/orders/preview":
            try:
                self._send_json(paper_projections.preview_paper_order(self.store, body))
            except ValueError as exc:
                self._send_error_json("PAPER_ORDER_PREVIEW_FAILED", str(exc), status=HTTPStatus.BAD_REQUEST)
            return

        if path == "/paper/orders":
            try:
                with LEDGER_ROUTE_LOCK:
                    payload = paper_projections.submit_paper_order(self.store, body)
                self._send_json(payload)
            except ValueError as exc:
                code = "PAPER_EXECUTION_NOT_AUTHORIZED" if "NOT_AUTHORIZED" in str(exc) else "PAPER_ORDER_SUBMIT_FAILED"
                self._send_error_json(code, str(exc), status=HTTPStatus.BAD_REQUEST)
            return

        if path == "/paper/sessions":
            try:
                with LEDGER_ROUTE_LOCK:
                    payload = paper_projections.open_paper_session(self.store, body)
                self._send_json(payload)
            except ValueError as exc:
                self._send_error_json("PAPER_SESSION_OPEN_FAILED", str(exc), status=HTTPStatus.BAD_REQUEST)
            return

        if path == "/paper/sessions/close":
            try:
                with LEDGER_ROUTE_LOCK:
                    payload = paper_projections.close_paper_session(self.store)
                self._send_json(payload)
            except ValueError as exc:
                self._send_error_json("PAPER_SESSION_CLOSE_FAILED", str(exc), status=HTTPStatus.BAD_REQUEST)
            return

        if path == "/operator/watchlist":
            try:
                self._send_json(operator_projections.update_watchlist(body))
            except ValueError as exc:
                self._send_error_json("OPERATOR_WATCHLIST_FAILED", str(exc), status=HTTPStatus.BAD_REQUEST)
            return
        if path == "/operator/recent":
            try:
                self._send_json(operator_projections.record_recent(body))
            except ValueError as exc:
                self._send_error_json("OPERATOR_RECENT_FAILED", str(exc), status=HTTPStatus.BAD_REQUEST)
            return
        if path == "/operator/workspace":
            try:
                self._send_json(operator_projections.save_workspace(body))
            except ValueError as exc:
                self._send_error_json("OPERATOR_WORKSPACE_FAILED", str(exc), status=HTTPStatus.BAD_REQUEST)
            return
        if path == "/operator/preferences":
            try:
                self._send_json(operator_projections.save_preferences(body))
            except ValueError as exc:
                self._send_error_json("OPERATOR_PREFERENCES_FAILED", str(exc), status=HTTPStatus.BAD_REQUEST)
            return
        if path == "/captures/replay":
            try:
                with LEDGER_ROUTE_LOCK:
                    payload = operator_projections.replay_capture(body)
                self._send_json(payload)
            except ValueError as exc:
                self._send_error_json("CAPTURE_REPLAY_FAILED", str(exc), status=HTTPStatus.BAD_REQUEST)
            return

        if path == "/paper/orders/cancel":
            try:
                with LEDGER_ROUTE_LOCK:
                    payload = paper_projections.cancel_paper_order(self.store, body)
                self._send_json(payload)
            except ValueError as exc:
                code = "PAPER_ORDER_CANCEL_FAILED"
                if "NOT_AUTHORIZED" in str(exc):
                    code = "PAPER_EXECUTION_NOT_AUTHORIZED"
                elif "NOT_SUPPORTED" in str(exc):
                    code = "PAPER_ORDER_CANCEL_NOT_SUPPORTED"
                elif "NOT_FOUND" in str(exc):
                    code = "PAPER_ORDER_NOT_FOUND"
                self._send_error_json(code, str(exc), status=HTTPStatus.BAD_REQUEST)
            return

        if path == "/discover/promote-to-live-analysis":
            from .discovery_projections import promote_to_live_analysis

            instrument_id = str(body.get("instrument_id", "")).strip()
            if not instrument_id:
                self._send_error_json(
                    "UI_REQUEST_INVALID",
                    "instrument_id required",
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            self._send_json(promote_to_live_analysis(instrument_id))
            return

        if path == "/subscriptions":
            from ..market_data.live_runtime import get_live_runtime

            runtime = get_live_runtime(create=False)
            if runtime is None:
                self._send_error_json(
                    "LIVE_OBSERVATIONAL_DISABLED",
                    "IMP_LIVE_OBSERVATIONAL not enabled",
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            instrument_id = str(body.get("instrument_id", "")).strip()
            capabilities = body.get("capabilities") or ["BASIC_QUOTE", "TRADES"]
            consumer_id = str(body.get("consumer_id") or "ui-default")
            priority = int(body.get("priority") or 1)
            if not instrument_id:
                self._send_error_json("UI_REQUEST_INVALID", "instrument_id required", status=HTTPStatus.BAD_REQUEST)
                return
            if not isinstance(capabilities, list):
                self._send_error_json("UI_REQUEST_INVALID", "capabilities must be a list", status=HTTPStatus.BAD_REQUEST)
                return
            results = runtime.subscribe(
                instrument_id=instrument_id,
                capabilities=[str(item) for item in capabilities],
                consumer_id=consumer_id,
                priority=priority,
            )
            self._send_json({"instrument_id": instrument_id.upper(), "subscriptions": results})
            return

        if path == "/subscriptions/release":
            from ..market_data.live_runtime import get_live_runtime

            runtime = get_live_runtime(create=False)
            if runtime is None:
                self._send_error_json(
                    "LIVE_OBSERVATIONAL_DISABLED",
                    "IMP_LIVE_OBSERVATIONAL not enabled",
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            instrument_id = str(body.get("instrument_id", "")).strip()
            capabilities = body.get("capabilities") or ["BASIC_QUOTE", "TRADES", "ORDER_BOOK"]
            consumer_id = str(body.get("consumer_id") or "ui-default")
            if not instrument_id:
                self._send_error_json("UI_REQUEST_INVALID", "instrument_id required", status=HTTPStatus.BAD_REQUEST)
                return
            results = runtime.unsubscribe(
                instrument_id=instrument_id,
                capabilities=[str(item) for item in capabilities],
                consumer_id=consumer_id,
            )
            self._send_json({"instrument_id": instrument_id.upper(), "subscriptions": results})
            return

        if path == "/replay/scrub":
            try:
                cursor_index = body.get("cursor_index")
                available_time = body.get("available_time")
                payload = projections.scrub_replay(
                    self.store,
                    cursor_index=int(cursor_index) if cursor_index is not None else None,
                    available_time=int(available_time) if available_time is not None else None,
                )
                self._send_json(payload)
            except ValueError as exc:
                self._send_error_json("UI_REPLAY_SCRUB_FAILED", str(exc), status=HTTPStatus.BAD_REQUEST)
            return

        if path == "/assistant/conversations":
            title = str(body.get("title", "Research session")).strip() or "Research session"
            principal_id = body.get("principal_id")
            principal = str(principal_id) if principal_id else None
            self._send_json(create_assistant_conversation(self.store, title=title, principal_id=principal))
            return

        if path.startswith("/assistant/conversations/") and path.endswith("/prompt"):
            conversation_id = path.removeprefix("/assistant/conversations/").removesuffix("/prompt")
            if not conversation_id:
                self._send_error_json(
                    "UI_REQUEST_INVALID",
                    "conversation id required",
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            prompt = str(body.get("prompt", ""))
            selection_ref = body.get("selection_ref")
            selection = str(selection_ref) if selection_ref else None
            try:
                self._send_json(
                    submit_assistant_prompt(
                        self.store,
                        conversation_id,
                        prompt,
                        selection_ref=selection,
                    )
                )
            except KeyError:
                self._send_error_json(
                    "UI_ASSISTANT_NOT_FOUND",
                    "conversation not found",
                    status=HTTPStatus.NOT_FOUND,
                )
            except ValueError as exc:
                self._send_error_json("UI_ASSISTANT_PROMPT_INVALID", str(exc), status=HTTPStatus.BAD_REQUEST)
            return

        self._send_error_json("UI_ROUTE_NOT_FOUND", f"Unknown path: {path}", status=HTTPStatus.NOT_FOUND)


def canonical_response_bytes(payload: dict[str, Any]) -> bytes:
    return canonical_bytes(payload)
