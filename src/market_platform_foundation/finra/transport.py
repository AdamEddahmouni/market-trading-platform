"""Stdlib FINRA Query API transport. Conservative vs documented ceilings."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .auth import FinraAuthError, FinraTokenManager

API_BASE = "https://api.finra.org"
# Documented sync ceiling is 1200 req/min/IP. Operate far below it.
MAX_REQUESTS_PER_MINUTE = 60
DEFAULT_MIN_INTERVAL_S = 60.0 / MAX_REQUESTS_PER_MINUTE
DEFAULT_TIMEOUT_S = 20.0
MAX_RETRIES = 3
SYNC_RECORD_LIMIT = 1000

Requester = Callable[[str, str, dict[str, str], bytes | None, float], tuple[int, dict[str, str], bytes]]


@dataclass
class FinraResponse:
    status: int
    headers: dict[str, str]
    body: bytes
    request_id: str
    records: list[dict[str, Any]]

    @property
    def record_total(self) -> int | None:
        raw = self.headers.get("record-total") or self.headers.get("Record-Total")
        if raw is None:
            return None
        try:
            return int(raw)
        except ValueError:
            return None


class FinraTransport:
    _global_lock = threading.Lock()
    _last_request = 0.0

    def __init__(
        self,
        token_manager: FinraTokenManager,
        *,
        requester: Requester | None = None,
        min_interval_s: float = DEFAULT_MIN_INTERVAL_S,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        self._tokens = token_manager
        self._requester = requester or _stdlib_requester
        self.min_interval_s = min_interval_s
        self._sleeper = sleeper or time.sleep
        self.request_count = 0
        self.error_count = 0
        self.last_status = "idle"
        self.last_request_id = ""
        self.last_success_monotonic: float | None = None

    def get(self, path: str, *, timeout: float = DEFAULT_TIMEOUT_S) -> FinraResponse:
        return self._send("GET", path, None, timeout)

    def post(self, path: str, payload: dict[str, Any], *, timeout: float = DEFAULT_TIMEOUT_S) -> FinraResponse:
        return self._send("POST", path, payload, timeout)

    def _send(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None,
        timeout: float,
    ) -> FinraResponse:
        url = path if path.startswith("http") else API_BASE.rstrip("/") + "/" + path.lstrip("/")
        last_error: BaseException | None = None
        unauthorized_retried = False
        for attempt in range(MAX_RETRIES):
            token = self._tokens.get_token(force=unauthorized_retried and attempt > 0)
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
            body = None if payload is None else json.dumps(payload).encode("utf-8")
            self._throttle()
            try:
                status, raw_headers, raw_body = self._requester(method, url, headers, body, timeout)
                if status == 401 and not unauthorized_retried:
                    unauthorized_retried = True
                    self._tokens.invalidate()
                    continue
                if status >= 500 and attempt + 1 < MAX_RETRIES:
                    self.error_count += 1
                    self._sleeper(0.2 * (2 ** attempt))
                    continue
                if status in {401, 403}:
                    self.error_count += 1
                    self.last_status = f"http_{status}"
                    raise FinraAuthError("AUTH_FAILED")
                if status >= 400:
                    self.error_count += 1
                    self.last_status = f"http_{status}"
                    raise OSError(f"FINRA_HTTP_{status}")
                self.request_count += 1
                self.last_status = "ok"
                request_id = _header(raw_headers, "FINRA-api-request-id")
                self.last_request_id = request_id
                self.last_success_monotonic = time.monotonic()
                records = _parse_records(raw_body)
                return FinraResponse(status, raw_headers, raw_body, request_id, records)
            except FinraAuthError:
                raise
            except HTTPError as exc:
                last_error = exc
                self.error_count += 1
                self.last_status = f"http_{exc.code}"
                if exc.code == 401 and not unauthorized_retried:
                    unauthorized_retried = True
                    self._tokens.invalidate()
                    continue
                if exc.code in {401, 403}:
                    raise FinraAuthError("AUTH_FAILED") from exc
                if exc.code >= 500 and attempt + 1 < MAX_RETRIES:
                    self._sleeper(0.2 * (2 ** attempt))
                    continue
                raise OSError(f"FINRA_HTTP_{exc.code}") from exc
            except (URLError, TimeoutError, OSError) as exc:
                last_error = exc
                self.error_count += 1
                self.last_status = "network_error"
                if attempt + 1 < MAX_RETRIES:
                    self._sleeper(0.2 * (2 ** attempt))
                    continue
                raise OSError("SOURCE_UNAVAILABLE") from exc
        raise OSError("SOURCE_UNAVAILABLE") from last_error

    def _throttle(self) -> None:
        with self._global_lock:
            elapsed = time.monotonic() - FinraTransport._last_request
            wait = self.min_interval_s - elapsed
            if wait > 0:
                self._sleeper(wait)
            FinraTransport._last_request = time.monotonic()


def _header(headers: dict[str, str], name: str) -> str:
    lowered = {key.lower(): value for key, value in headers.items()}
    return str(lowered.get(name.lower(), ""))


def _parse_records(body: bytes) -> list[dict[str, Any]]:
    if not body:
        return []
    payload = json.loads(body.decode("utf-8"))
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("data", "records", "result"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
        return [payload]
    return []


def _stdlib_requester(
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes | None,
    timeout: float,
) -> tuple[int, dict[str, str], bytes]:
    request = Request(url, data=body, method=method, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        raw_headers = {str(key): str(value) for key, value in response.headers.items()}
        return int(getattr(response, "status", 200)), raw_headers, response.read()
