"""SEC Fair Access transport: declared User-Agent, global throttle, cache, fail-closed."""

from __future__ import annotations

import gzip
import threading
import time
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

FORBIDDEN_USER_AGENTS = (
    "python-urllib",
    "python-requests",
    "urllib",
    "unknown bot",
)

# Conservative vs SEC 10 req/s Fair Access ceiling.
MAX_REQUESTS_PER_SECOND = 5
DEFAULT_MIN_INTERVAL_S = 1.0 / MAX_REQUESTS_PER_SECOND
DEFAULT_TIMEOUT_S = 15.0
MAX_RETRIES = 3

Requester = Callable[[str, dict[str, str], float], bytes]


def require_user_agent(value: str) -> str:
    text = (value or "").strip()
    if not text:
        raise ValueError("SEC_USER_AGENT_REQUIRED")
    lowered = text.lower()
    if any(token in lowered for token in FORBIDDEN_USER_AGENTS):
        raise ValueError("SEC_USER_AGENT_GENERIC_FORBIDDEN")
    if "@" not in text or " " not in text:
        raise ValueError("SEC_USER_AGENT_MUST_IDENTIFY_CONTACT")
    return text


class SecTransport:
    """Process-wide serialized requester. Concurrent callers share one budget."""

    _global_lock = threading.Lock()
    _last_request = 0.0

    def __init__(
        self,
        *,
        user_agent: str,
        requester: Requester | None = None,
        min_interval_s: float = DEFAULT_MIN_INTERVAL_S,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        self.user_agent = require_user_agent(user_agent)
        self._requester = requester or _stdlib_requester
        self.min_interval_s = min_interval_s
        self._sleeper = sleeper or time.sleep
        self._cache: dict[str, bytes] = {}
        self.request_count = 0
        self.cache_hits = 0
        self.error_count = 0
        self.last_status = "idle"

    def get(self, url: str, *, immutable: bool = False, timeout: float = DEFAULT_TIMEOUT_S) -> bytes:
        if immutable and url in self._cache:
            self.cache_hits += 1
            return self._cache[url]
        last_error: BaseException | None = None
        for attempt in range(MAX_RETRIES):
            self._throttle()
            try:
                body = self._requester(
                    url,
                    {"User-Agent": self.user_agent, "Accept-Encoding": "gzip"},
                    timeout,
                )
                self.request_count += 1
                self.last_status = "ok"
                if immutable:
                    self._cache[url] = body
                return body
            except HTTPError as exc:
                last_error = exc
                self.error_count += 1
                self.last_status = f"http_{exc.code}"
                if exc.code == 429:
                    retry_after = 1.0
                    if exc.headers is not None:
                        raw = exc.headers.get("Retry-After")
                        if raw:
                            try:
                                retry_after = float(raw)
                            except ValueError:
                                retry_after = 1.0
                    self._sleeper(retry_after)
                    continue
                if exc.code >= 500 and attempt + 1 < MAX_RETRIES:
                    self._sleeper(0.2 * (2 ** attempt))
                    continue
                raise OSError(f"SEC_HTTP_{exc.code}") from exc
            except (URLError, TimeoutError, OSError) as exc:
                last_error = exc
                self.error_count += 1
                self.last_status = "network_error"
                if attempt + 1 < MAX_RETRIES:
                    self._sleeper(0.2 * (2 ** attempt))
                    continue
                raise OSError("SEC_UNREACHABLE") from exc
        raise OSError("SEC_UNREACHABLE") from last_error

    def _throttle(self) -> None:
        with self._global_lock:
            elapsed = time.monotonic() - SecTransport._last_request
            wait = self.min_interval_s - elapsed
            if wait > 0:
                self._sleeper(wait)
            SecTransport._last_request = time.monotonic()


def _stdlib_requester(url: str, headers: dict[str, str], timeout: float) -> bytes:
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        raw = response.read()
        encoding = response.headers.get("Content-Encoding", "")
    if encoding == "gzip":
        raw = gzip.decompress(raw)
    return raw
