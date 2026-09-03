"""HTTP transport for official EIA Open Data API v2."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .redaction import redact_text, sanitize_error, sanitize_response_payload

EIA_API_BASE = "https://api.eia.gov"
DEFAULT_USER_AGENT = "integrated-market-platform-eia/1.0 (+https://www.eia.gov/opendata/)"
MAX_JSON_ROWS = 5000


class EiaTransportError(Exception):
    """EIA source unavailable, auth failure, or malformed response."""


class EiaTransport:
    """Bounded EIA API v2 client with conservative pacing and pagination."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = EIA_API_BASE,
        user_agent: str = DEFAULT_USER_AGENT,
        min_interval_seconds: float = 0.35,
        timeout_seconds: float = 45.0,
        max_retries: int = 3,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent
        self.min_interval_seconds = min_interval_seconds
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._last_request_at = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_interval_seconds:
            time.sleep(self.min_interval_seconds - elapsed)

    def _request_json_once(self, url: str) -> dict[str, Any]:
        self._throttle()
        request = urllib.request.Request(
            url,
            headers={"User-Agent": self.user_agent, "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                raise EiaTransportError("SOURCE_UNAVAILABLE: HTTP 429 rate limited") from exc
            if exc.code in {401, 403}:
                raise EiaTransportError("AUTH_UNAVAILABLE: invalid or missing EIA API key") from exc
            if exc.code >= 500:
                raise EiaTransportError(f"SOURCE_UNAVAILABLE: HTTP {exc.code}") from exc
            raise EiaTransportError(f"SOURCE_UNAVAILABLE: HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise EiaTransportError(f"SOURCE_UNAVAILABLE: {sanitize_error(exc)}") from exc
        except json.JSONDecodeError as exc:
            raise EiaTransportError("SOURCE_UNAVAILABLE: invalid JSON") from exc
        finally:
            self._last_request_at = time.monotonic()

        if not isinstance(payload, dict):
            raise EiaTransportError("SOURCE_UNAVAILABLE: unexpected payload shape")
        return payload

    def _request_json(self, url: str) -> dict[str, Any]:
        attempt = 0
        while True:
            try:
                return self._request_json_once(url)
            except EiaTransportError as exc:
                attempt += 1
                if attempt > self.max_retries or "429" not in str(exc):
                    raise
                time.sleep(min(2.0 * attempt, 8.0))

    @staticmethod
    def _encode_params(params: dict[str, Any]) -> str:
        pairs: list[tuple[str, str]] = []
        for key, value in params.items():
            if isinstance(value, list):
                for item in value:
                    pairs.append((key, str(item)))
            else:
                pairs.append((key, str(value)))
        return urllib.parse.urlencode(pairs, quote_via=urllib.parse.quote)

    def build_url(self, route: str, params: dict[str, Any]) -> str:
        safe_params = dict(params)
        safe_params["api_key"] = self.api_key
        query = self._encode_params(safe_params)
        route = route if route.startswith("/") else f"/{route}"
        return f"{self.base_url}{route}?{query}"

    def diagnostic_label(self, route: str, params: dict[str, Any], status: int = 200) -> str:
        safe = {key: value for key, value in params.items() if key != "api_key"}
        return f"GET {route} {self._encode_params(safe)} status={status}"

    def get_route_metadata(self, route: str) -> dict[str, Any]:
        payload = self._request_json(self.build_url(route, {}))
        return sanitize_response_payload(payload)

    def request_json_raw(self, route: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return unsanitized JSON for credential-echo auditing only — never persist/log."""
        return self._request_json(self.build_url(route, dict(params or {})))

    def query_data(
        self,
        route: str,
        *,
        params: dict[str, Any] | None = None,
        length: int = 5000,
        offset: int = 0,
    ) -> dict[str, Any]:
        query_params = dict(params or {})
        query_params.setdefault("length", min(length, MAX_JSON_ROWS))
        query_params.setdefault("offset", offset)
        payload = self._request_json(self.build_url(route, query_params))
        return sanitize_response_payload(payload)

    def query_data_paginated(
        self,
        route: str,
        *,
        params: dict[str, Any] | None = None,
        length: int = 5000,
        max_pages: int = 20,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        page_length = min(length, MAX_JSON_ROWS)
        offset = 0
        rows: list[dict[str, Any]] = []
        last_meta: dict[str, Any] = {}
        for _ in range(max_pages):
            payload = self.query_data(route, params=params, length=page_length, offset=offset)
            response = payload.get("response", {})
            if not isinstance(response, dict):
                break
            last_meta = response
            page_rows = response.get("data", [])
            if not isinstance(page_rows, list):
                break
            page_dicts = [row for row in page_rows if isinstance(row, dict)]
            rows.extend(page_dicts)
            total = int(response.get("total", len(rows)))
            offset += len(page_dicts)
            if offset >= total or not page_dicts:
                break
        return rows, last_meta

    def reachable(self) -> bool:
        try:
            payload = self.get_route_metadata("/v2/petroleum/sum/sndw")
            response = payload.get("response")
            return isinstance(response, dict)
        except EiaTransportError:
            return False


__all__ = [
    "DEFAULT_USER_AGENT",
    "EIA_API_BASE",
    "EiaTransport",
    "EiaTransportError",
    "MAX_JSON_ROWS",
]
