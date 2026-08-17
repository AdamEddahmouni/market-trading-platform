"""Stdlib HTTP handler for UI-001 read-only API."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from typing import Any
from urllib.parse import parse_qs, urlparse

from ..canonical import canonical_bytes, write_canonical_json
from . import projections
from .assistant_projections import (
    build_assistant_conversations,
    build_assistant_messages,
    build_assistant_status,
    create_assistant_conversation,
    submit_assistant_prompt,
)
from .store import ReplayStore


class UiApiHandler(BaseHTTPRequestHandler):
    store: ReplayStore

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send_json(self, payload: dict[str, Any], *, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
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
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)
        try:
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

                self._send_json(build_workspace_squeeze_payload(symbol, as_of_context=as_of))
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
                from ..donor_bridge.projections import build_workspace_catalyst_payload

                self._send_json(build_workspace_catalyst_payload(symbol, as_of_context=as_of))
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
                    build_workspace_disclosure_payload(
                        symbol,
                        as_of_context=as_of,
                        prediction_cutoff=self.store.prediction_cutoff(),
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
                from ..providers.projections import build_workspace_order_flow_payload

                self._send_json(
                    build_workspace_order_flow_payload(
                        symbol,
                        as_of_context=as_of,
                        prediction_cutoff=self.store.prediction_cutoff(),
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
                    build_workspace_options_payload(
                        symbol,
                        as_of_context=as_of,
                        prediction_cutoff=self.store.prediction_cutoff(),
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
                    build_workspace_large_transactions_payload(
                        symbol,
                        as_of_context=as_of,
                        prediction_cutoff=self.store.prediction_cutoff(),
                    )
                )
                return
            if path == "/assistant/status":
                self._send_json(build_assistant_status(self.store))
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
