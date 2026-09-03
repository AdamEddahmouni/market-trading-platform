"""Strictly read-only, stdlib HTTP client for the loopback IBKR gateway."""

from __future__ import annotations

import json
import re
import ssl
from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .capture import JsonlJournal, ObservationCapture
from .config import IbkrConfig, validate_gateway_url
from .pacing import RequestPacer


_GET_EXACT = frozenset(
    {
        "/iserver/auth/status",
        "/iserver/secdef/search",
        "/iserver/marketdata/snapshot",
        "/hmds/history",
        "/trsrv/secdef",
        "/trsrv/secdef/info",
        "/iserver/scanner/params",
        "/portfolio/accounts",
    }
)
_POST_EXACT = frozenset(
    {
        "/tickle",
        "/iserver/auth/ssodh/init",
        "/iserver/scanner/run",
    }
)
_GET_PATTERNS = (
    re.compile(r"^/portfolio/[A-Za-z0-9._-]+/positions/[0-9]+$"),
    re.compile(r"^/portfolio/[A-Za-z0-9._-]+/(?:summary|ledger)$"),
)


class LiveGateDisabled(RuntimeError):
    """Raised before I/O when explicit live observation is not enabled."""


class EndpointNotAllowed(ValueError):
    """Raised before I/O for anything outside the read-only allowlist."""


class HttpResponseError(RuntimeError):
    """Sanitized non-success response."""

    def __init__(self, status: int, method: str, path: str) -> None:
        self.status = status
        self.method = method
        self.path = path
        super().__init__(f"IBKR observational request failed: {method} {path} HTTP {status}")


class RateLimitError(HttpResponseError):
    """HTTP 429 response that has already activated the shared penalty box."""


@dataclass(frozen=True, slots=True)
class TransportResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


Transport = Callable[..., TransportResponse]


def _ssl_context() -> ssl.SSLContext:
    """Trust the gateway's self-signed certificate only after loopback validation."""

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def urllib_transport(
    request: Request, *, ssl_context: ssl.SSLContext, timeout: float
) -> TransportResponse:
    """Perform one bounded stdlib request and preserve HTTP status responses."""

    try:
        with urlopen(request, context=ssl_context, timeout=timeout) as response:  # noqa: S310
            return TransportResponse(
                int(response.status),
                {str(key).lower(): str(value) for key, value in response.headers.items()},
                response.read(),
            )
    except HTTPError as exc:
        return TransportResponse(
            int(exc.code),
            {str(key).lower(): str(value) for key, value in (exc.headers or {}).items()},
            exc.read(),
        )


def _endpoint_allowed(method: str, path: str) -> bool:
    if not path.startswith("/") or path.startswith("//") or any(marker in path for marker in ("?", "#", "%")):
        return False
    if method == "GET":
        return path in _GET_EXACT or any(pattern.fullmatch(path) for pattern in _GET_PATTERNS)
    if method == "POST":
        return path in _POST_EXACT
    return False


class IbkrClient:
    """A fail-closed client exposing only observational Gateway operations."""

    def __init__(
        self,
        config: IbkrConfig,
        *,
        transport: Transport = urllib_transport,
        pacer: RequestPacer | None = None,
        capture: ObservationCapture | None = None,
        penalty_journal: JsonlJournal | None = None,
    ) -> None:
        validate_gateway_url(config.gateway_url)
        self.config = config
        self._transport = transport
        self._context = _ssl_context()
        self._capture = capture or ObservationCapture(config.capture_root / "observations.jsonl")
        self._penalty_journal = penalty_journal or JsonlJournal(
            config.capture_root / "penalty-box.jsonl"
        )
        self._pacer = pacer or RequestPacer(
            requests_per_second=config.requests_per_second,
            history_min_spacing_seconds=config.history_min_spacing_seconds,
            history_window_max=config.history_window_max,
            history_window_seconds=config.history_window_seconds,
            penalty_box_seconds=config.penalty_box_seconds,
            journal=self._penalty_journal.append,
        )

    def request_json(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, object] | None = None,
        body: Mapping[str, object] | None = None,
    ) -> Any:
        if not self.config.live_enabled:
            raise LiveGateDisabled("IMP_IBKR_LIVE is not enabled")
        normalized_method = method.upper().strip()
        if not _endpoint_allowed(normalized_method, path):
            raise EndpointNotAllowed("endpoint is outside the ADR-LIVE-002 observational allowlist")
        query_items = sorted((params or {}).items(), key=lambda item: item[0])
        query = urlencode(query_items, doseq=True)
        url = f"{self.config.gateway_url}{path}"
        if query:
            url = f"{url}?{query}"
        data = None
        headers = {"Accept": "application/json"}
        if body is not None:
            data = json.dumps(dict(body), separators=(",", ":"), sort_keys=True).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(url, data=data, headers=headers, method=normalized_method)
        query_key = f"{path}?{query}" if query else path
        with self._pacer.slot(path, query_key):
            response = self._transport(
                request,
                ssl_context=self._context,
                timeout=self.config.timeout_seconds,
            )
            try:
                capture_payload: object = json.loads(response.body) if response.body else None
            except (UnicodeDecodeError, json.JSONDecodeError):
                capture_payload = response.body.decode("utf-8", errors="replace")
            self._capture.record(
                method=normalized_method,
                path=path,
                params=params,
                request_body=body,
                status=response.status,
                headers=response.headers,
                response_payload=capture_payload,
            )
            if response.status == 429:
                self._pacer.penalize(status=429, method=normalized_method, path=path)
                raise RateLimitError(response.status, normalized_method, path)
        if not 200 <= response.status < 300:
            raise HttpResponseError(response.status, normalized_method, path)
        if not response.body:
            return None
        try:
            return json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HttpResponseError(response.status, normalized_method, path) from exc


__all__ = [
    "EndpointNotAllowed",
    "HttpResponseError",
    "IbkrClient",
    "LiveGateDisabled",
    "RateLimitError",
    "TransportResponse",
    "urllib_transport",
]
