"""Bounded HTTP for keyless official public-record APIs (House Clerk, USAspending, LDA, CFTC)."""

from __future__ import annotations

import gzip
import json
import os
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Callable

LIVE_ENV = "IMP_PUBLIC_RECORDS_LIVE"
USER_AGENT = "integrated-market-platform-public-records/1.0"
DEFAULT_TIMEOUT_S = 20.0
MAX_BYTES = 16 * 1024 * 1024

#: (url, body | None, headers, timeout) -> (status, bytes)
Requester = Callable[[str, bytes | None, dict[str, str], float], tuple[int, bytes]]


class PublicRecordsError(Exception):
    """A classified source failure; the message is a stable code, never a URL or body."""


def live_state(env: Callable[[str], str | None] = os.environ.get) -> tuple[str, str | None]:
    if (env(LIVE_ENV) or "") != "1":
        return "LIVE_DISABLED", f"{LIVE_ENV}_NOT_SET"
    return "CURRENT", None


def _stdlib_request(url: str, body: bytes | None, headers: dict[str, str], timeout: float) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(MAX_BYTES + 1)
            encoding = response.headers.get("Content-Encoding", "")
            status = int(getattr(response, "status", 200))
    except urllib.error.HTTPError as exc:
        return exc.code, b""
    if len(raw) > MAX_BYTES:
        raise PublicRecordsError("RESPONSE_TOO_LARGE")
    return status, gzip.decompress(raw) if encoding == "gzip" else raw


class PublicRecordsHttp:
    """Per-host serialized requests with a minimum interval; failures become stable codes."""

    def __init__(self, *, requester: Requester | None = None, min_interval_s: float = 0.5,
                 timeout_s: float = DEFAULT_TIMEOUT_S, sleeper: Callable[[float], None] = time.sleep) -> None:
        self._requester = requester or _stdlib_request
        self._min_interval_s = min_interval_s
        self._timeout_s = timeout_s
        self._sleeper = sleeper
        self._lock = threading.Lock()
        self._last: dict[str, float] = {}
        self.request_count = 0

    def _throttle(self, url: str) -> None:
        host = url.split("/")[2] if "://" in url else url
        # Reserve this host's next slot under the lock, then wait outside it: a paced host (e.g. the
        # House PTR loader) never holds up requests to other hosts.
        with self._lock:
            now = time.monotonic()
            slot = max(now, self._last.get(host, float("-inf")) + self._min_interval_s)
            self._last[host] = slot
        if slot > now:
            self._sleeper(slot - now)

    def get_bytes(self, url: str, *, accept: str = "*/*") -> bytes:
        return self._send(url, None, {"Accept": accept})

    def get_json(self, url: str) -> Any:
        return self._decode(self._send(url, None, {"Accept": "application/json"}))

    def post_json(self, url: str, payload: dict[str, Any]) -> Any:
        body = json.dumps(payload).encode("utf-8")
        return self._decode(self._send(url, body, {"Accept": "application/json", "Content-Type": "application/json"}))

    def _send(self, url: str, body: bytes | None, headers: dict[str, str]) -> bytes:
        self._throttle(url)
        try:
            status, raw = self._requester(url, body, {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip", **headers},
                                          self._timeout_s)
        except PublicRecordsError:
            raise
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise PublicRecordsError("NETWORK_ERROR") from exc
        self.request_count += 1
        if status == 429:
            raise PublicRecordsError("HTTP_429")
        if status in (401, 403):
            raise PublicRecordsError(f"HTTP_{status}")
        if status >= 400:
            raise PublicRecordsError(f"HTTP_{status}")
        return raw

    @staticmethod
    def _decode(raw: bytes) -> Any:
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PublicRecordsError("MALFORMED_JSON") from exc


__all__ = ["LIVE_ENV", "PublicRecordsError", "PublicRecordsHttp", "Requester", "USER_AGENT", "live_state"]
