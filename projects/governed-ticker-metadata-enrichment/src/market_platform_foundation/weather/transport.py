"""Bounded standard-library HTTP transport for official NOAA weather sources."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping

NWS_API_BASE = "https://api.weather.gov"
DEFAULT_NWS_USER_AGENT = (
    "integrated-market-platform-weather/1.0 "
    "(+https://www.weather.gov/documentation/services-web-api)"
)
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MIN_INTERVAL_SECONDS = 0.2
DEFAULT_MAX_RETRIES = 3


class WeatherTransportError(Exception):
    """Official weather source is unavailable or returned malformed content."""


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """Small response boundary that keeps cache/provenance metadata."""

    body: bytes
    status: int
    headers: Mapping[str, str]
    url: str


Requester = Callable[[str, dict[str, str], float], HttpResponse | bytes]


def require_nws_user_agent(value: str) -> str:
    text = (value or "").strip()
    if not text:
        raise ValueError("NWS_USER_AGENT_REQUIRED")
    if text.lower() in {"python-urllib", "python-requests", "urllib"}:
        raise ValueError("NWS_USER_AGENT_GENERIC_FORBIDDEN")
    return text


class WeatherTransport:
    """Paced NOAA client with bounded retries and no credential requirement."""

    def __init__(
        self,
        *,
        user_agent: str = DEFAULT_NWS_USER_AGENT,
        requester: Requester | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        min_interval_seconds: float = DEFAULT_MIN_INTERVAL_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        if max_retries < 0:
            raise ValueError("WEATHER_MAX_RETRIES_MUST_BE_NONNEGATIVE")
        self.user_agent = require_nws_user_agent(user_agent)
        self.timeout_seconds = timeout_seconds
        self.min_interval_seconds = min_interval_seconds
        self.max_retries = max_retries
        self._requester = requester or _stdlib_requester
        self._sleeper = sleeper or time.sleep
        self._last_request_at = 0.0
        self.request_count = 0
        self.last_status_code: int | None = None
        self.last_response_headers: dict[str, str] = {}
        self.last_response_url = ""

    def _throttle(self) -> None:
        wait = self.min_interval_seconds - (time.monotonic() - self._last_request_at)
        if wait > 0:
            self._sleeper(wait)

    def request_bytes(
        self,
        url: str,
        *,
        accept: str = "application/geo+json, application/json",
    ) -> bytes:
        headers = {"User-Agent": self.user_agent, "Accept": accept}
        for attempt in range(self.max_retries + 1):
            self._throttle()
            try:
                response = self._requester(url, headers, self.timeout_seconds)
                self.request_count += 1
                self._last_request_at = time.monotonic()
                if isinstance(response, bytes):
                    self.last_status_code = 200
                    self.last_response_headers = {}
                    self.last_response_url = url
                    return response
                self.last_status_code = response.status
                self.last_response_headers = {
                    str(key).lower(): str(value) for key, value in response.headers.items()
                }
                self.last_response_url = response.url
                return response.body
            except urllib.error.HTTPError as exc:
                self.request_count += 1
                self.last_status_code = exc.code
                self._last_request_at = time.monotonic()
                retryable = exc.code == 429 or exc.code in {500, 502, 503, 504}
                if retryable and attempt < self.max_retries:
                    self._sleeper(_retry_delay(exc, attempt))
                    continue
                prefix = "NWS" if "api.weather.gov" in url else "NOAA"
                raise WeatherTransportError(f"{prefix}_HTTP_{exc.code}") from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                self.request_count += 1
                self._last_request_at = time.monotonic()
                if attempt < self.max_retries:
                    self._sleeper(min(0.25 * (2**attempt), 4.0))
                    continue
                raise WeatherTransportError("NOAA_SOURCE_UNREACHABLE") from exc
        raise WeatherTransportError("NOAA_RETRIES_EXHAUSTED")

    def request_json(self, url: str) -> dict[str, Any]:
        raw = self.request_bytes(url)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WeatherTransportError("NOAA_INVALID_JSON") from exc
        if not isinstance(payload, dict):
            raise WeatherTransportError("NOAA_UNEXPECTED_PAYLOAD_SHAPE")
        return payload


def _retry_delay(exc: urllib.error.HTTPError, attempt: int) -> float:
    if exc.headers is not None:
        raw = exc.headers.get("Retry-After")
        if raw:
            try:
                return max(0.0, min(float(raw), 30.0))
            except ValueError:
                pass
    return min(0.25 * (2**attempt), 4.0)


def _stdlib_requester(url: str, headers: dict[str, str], timeout: float) -> HttpResponse:
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
        status = int(getattr(response, "status", 200))
        response_headers = {str(key): str(value) for key, value in response.headers.items()}
        final_url = str(response.geturl())
    return HttpResponse(body=body, status=status, headers=response_headers, url=final_url)


__all__ = [
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_MIN_INTERVAL_SECONDS",
    "DEFAULT_NWS_USER_AGENT",
    "DEFAULT_TIMEOUT_SECONDS",
    "HttpResponse",
    "NWS_API_BASE",
    "WeatherTransport",
    "WeatherTransportError",
    "require_nws_user_agent",
]
