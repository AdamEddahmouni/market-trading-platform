"""In-memory FINRA OAuth2 client-credentials token manager."""

from __future__ import annotations

import base64
import json
import threading
import time
from dataclasses import dataclass
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .client_config import FinraCredentials

FIP_TOKEN_URL = (
    "https://ews.fip.finra.org/fip/rest/ews/oauth2/access_token?grant_type=client_credentials"
)
DEFAULT_SAFETY_MARGIN_S = 120.0
DEFAULT_TIMEOUT_S = 15.0

TokenRequester = Callable[[str, dict[str, str], float], tuple[int, bytes]]


class FinraAuthError(OSError):
    pass


@dataclass
class _TokenCache:
    access_token: str
    token_type: str
    expires_at_monotonic: float
    obtained_at_monotonic: float
    expires_in_s: float


class FinraTokenManager:
    """Single-flight in-memory cache. Tokens are never written to disk."""

    def __init__(
        self,
        credentials: FinraCredentials,
        *,
        requester: TokenRequester | None = None,
        safety_margin_s: float = DEFAULT_SAFETY_MARGIN_S,
        token_url: str = FIP_TOKEN_URL,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if not credentials.present():
            raise FinraAuthError("FINRA_CREDENTIALS_MISSING")
        self._credentials = credentials
        self._requester = requester or _stdlib_token_requester
        self._safety_margin_s = safety_margin_s
        self.token_url = token_url
        self._clock = clock or time.monotonic
        self._lock = threading.Lock()
        self._refreshing = threading.Condition(self._lock)
        self._in_flight = False
        self._cache: _TokenCache | None = None
        self.last_refresh_monotonic: float | None = None
        self.refresh_count = 0
        self.last_error = ""

    def get_token(self, *, force: bool = False) -> str:
        with self._lock:
            now = self._clock()
            if not force and self._cache_valid(now):
                assert self._cache is not None
                return self._cache.access_token
            while self._in_flight:
                self._refreshing.wait(timeout=30.0)
                now = self._clock()
                if not force and self._cache_valid(now):
                    assert self._cache is not None
                    return self._cache.access_token
            self._in_flight = True
        try:
            token = self._fetch_token()
            return token
        finally:
            with self._lock:
                self._in_flight = False
                self._refreshing.notify_all()

    def invalidate(self) -> None:
        with self._lock:
            self._cache = None

    def _cache_valid(self, now: float) -> bool:
        cache = self._cache
        if cache is None or not cache.access_token:
            return False
        return now < (cache.expires_at_monotonic - self._safety_margin_s)

    def _fetch_token(self) -> str:
        raw = f"{self._credentials.client_id}:{self._credentials.client_secret}".encode("utf-8")
        basic = base64.b64encode(raw).decode("ascii")
        headers = {
            "Authorization": f"Basic {basic}",
            "Accept": "application/json",
        }
        try:
            status, body = self._requester(self.token_url, headers, DEFAULT_TIMEOUT_S)
        except HTTPError as exc:
            self.last_error = f"FINRA_HTTP_{exc.code}"
            if exc.code in {401, 403}:
                raise FinraAuthError("AUTH_FAILED") from exc
            raise FinraAuthError("SOURCE_UNAVAILABLE") from exc
        except (URLError, TimeoutError, OSError) as exc:
            self.last_error = "TOKEN_ENDPOINT_UNAVAILABLE"
            raise FinraAuthError("SOURCE_UNAVAILABLE") from exc
        if status >= 400:
            self.last_error = f"FINRA_HTTP_{status}"
            if status in {401, 403}:
                raise FinraAuthError("AUTH_FAILED")
            raise FinraAuthError("SOURCE_UNAVAILABLE")
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self.last_error = "TOKEN_RESPONSE_INVALID"
            raise FinraAuthError("SOURCE_UNAVAILABLE") from exc
        token = str(payload.get("access_token") or "")
        if not token:
            self.last_error = "TOKEN_MISSING"
            raise FinraAuthError("AUTH_FAILED")
        expires_raw = payload.get("expires_in", 1800)
        try:
            expires_in = float(expires_raw)
        except (TypeError, ValueError):
            expires_in = 1800.0
        now = self._clock()
        cache = _TokenCache(
            access_token=token,
            token_type=str(payload.get("token_type") or "Bearer"),
            expires_at_monotonic=now + expires_in,
            obtained_at_monotonic=now,
            expires_in_s=expires_in,
        )
        with self._lock:
            self._cache = cache
            self.last_refresh_monotonic = now
            self.refresh_count += 1
            self.last_error = ""
        return token


def _stdlib_token_requester(url: str, headers: dict[str, str], timeout: float) -> tuple[int, bytes]:
    request = Request(url, data=b"", method="POST", headers=headers)
    with urlopen(request, timeout=timeout) as response:
        return int(getattr(response, "status", 200)), response.read()
