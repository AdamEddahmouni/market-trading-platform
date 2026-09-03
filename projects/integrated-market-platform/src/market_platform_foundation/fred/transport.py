"""Shared HTTP transport for FRED API clients."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .redaction import sanitize_error


FRED_BASE_URL = "https://api.stlouisfed.org"
DEFAULT_USER_AGENT = "integrated-market-platform-fred/1.0 (+research; contact via repo)"


class FredTransportError(Exception):
    """FRED source unavailable, auth failure, or malformed response."""

    def __str__(self) -> str:
        return sanitize_error(super().__str__())


class FredHttpTransport:
    """Bounded HTTP client with throttling, retries, and credential-safe errors."""

    def __init__(
        self,
        *,
        base_url: str = FRED_BASE_URL,
        user_agent: str = DEFAULT_USER_AGENT,
        min_interval_seconds: float = 0.35,
        timeout_seconds: float = 45.0,
        max_retries: int = 3,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent
        self.min_interval_seconds = min_interval_seconds
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._last_request_at = 0.0
        self.last_status_code: int | None = None

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_interval_seconds:
            time.sleep(self.min_interval_seconds - elapsed)

    def request_json(
        self,
        *,
        path: str,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        query = urllib.parse.urlencode(params or {}, quote_via=urllib.parse.quote)
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{query}"
        request_headers = {"User-Agent": self.user_agent, "Accept": "application/json"}
        if headers:
            request_headers.update(headers)

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            self._throttle()
            request = urllib.request.Request(url, headers=request_headers)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    self.last_status_code = response.status
                    payload = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                self.last_status_code = exc.code
                if exc.code in {429, 500, 502, 503, 504} and attempt < self.max_retries:
                    time.sleep(min(2.0 ** attempt, 8.0))
                    last_error = exc
                    continue
                if exc.code in {401, 403}:
                    raise FredTransportError("AUTH_FAILED") from exc
                error_body = ""
                try:
                    error_body = exc.read().decode("utf-8", errors="replace")
                except OSError:
                    error_body = ""
                if error_body:
                    try:
                        parsed = json.loads(error_body)
                        if isinstance(parsed, dict):
                            code = parsed.get("error_code", parsed.get("error_code", ""))
                            message = parsed.get("error_message", parsed.get("message", ""))
                            raise FredTransportError(
                                f"SOURCE_UNAVAILABLE: HTTP {exc.code} error_code={code} error_message={message}"
                            ) from exc
                    except json.JSONDecodeError:
                        pass
                raise FredTransportError(f"SOURCE_UNAVAILABLE: HTTP {exc.code}") from exc
            except urllib.error.URLError as exc:
                if attempt < self.max_retries:
                    time.sleep(min(2.0 ** attempt, 8.0))
                    last_error = exc
                    continue
                raise FredTransportError(f"SOURCE_UNAVAILABLE: {exc.reason}") from exc
            except json.JSONDecodeError as exc:
                raise FredTransportError("SOURCE_UNAVAILABLE: invalid JSON") from exc
            finally:
                self._last_request_at = time.monotonic()

            if not isinstance(payload, dict):
                raise FredTransportError("SOURCE_UNAVAILABLE: unexpected payload shape")
            return payload

        raise FredTransportError("SOURCE_UNAVAILABLE: retries exhausted") from last_error


__all__ = ["FRED_BASE_URL", "FredHttpTransport", "FredTransportError"]
