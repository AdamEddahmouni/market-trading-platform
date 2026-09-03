"""Stdlib-only HTTP client for Finviz live probes.

Phase 0 source invariants prohibit third-party HTTP clients (requests)
and native-OS access inside ``src/market_platform_foundation``; the
live probe boundary must use the standard library (see
``sec_edgar/transport.py`` for the same pattern). This module provides
a minimal urllib-based response wrapper, a GET helper, and a cookie
session for the Finviz login-recovery flow. Responses intentionally
expose the same surface used by the injected mocks in tests:
``status_code``, ``text``, ``headers``, and ``url``.
"""

from __future__ import annotations

import http.client
import http.cookiejar
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass
class HttpResponse:
    """Minimal response surface mirroring the requests objects we replaced."""

    status_code: int
    text: str
    headers: dict[str, str] = field(default_factory=dict)
    url: str = ""

    def get(self, key: str, default: str = "") -> str:
        return self.headers.get(key, default)


_DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (IMP integrated-market-platform)",
    "Accept": "text/csv,application/csv,text/plain,*/*",
}


def urllib_get(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: float = 15.0,
    headers: dict[str, str] | None = None,
) -> HttpResponse:
    """Perform a GET with query parameters and return an HttpResponse.

    Raises :class:`urllib.error.URLError`, :class:`http.client.HTTPException`,
    or :class:`OSError` (timeouts) on failure.
    """
    target = url
    if params:
        query = urllib.parse.urlencode(params)
        separator = "&" if urllib.parse.urlsplit(url).query else "?"
        target = f"{url}{separator}{query}"
    request = urllib.request.Request(
        target,
        headers={**_DEFAULT_HEADERS, **(headers or {})},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        status = int(getattr(response, "status", 200))
        body = response.read().decode("utf-8", errors="replace")
        response_headers = {
            str(key).lower(): str(value) for key, value in response.headers.items()
        }
        return HttpResponse(
            status_code=status,
            text=body,
            headers=response_headers,
            url=target,
        )


def is_network_error(exc: BaseException) -> bool:
    return isinstance(exc, (urllib.error.URLError, http.client.HTTPException, OSError, socket.timeout))


class UrllibSession:
    """Minimal cookie-preserving session for the Finviz login flow.

    Implements just the surface used by ``recover_token_via_login``:
    ``post(url, data=..., timeout=..., allow_redirects=...)`` and
    ``get(url, timeout=..., params=...)``, each returning
    :class:`HttpResponse`. Redirects are followed for GET; for POST the
    login redirect (301/302/303/307/308) is followed while preserving
    cookies, converting to GET as the browser does for login forms.
    """

    def __init__(self) -> None:
        self._cookies = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._cookies)
        )

    @staticmethod
    def _finalize(response: Any, url: str) -> HttpResponse:
        body = response.read().decode("utf-8", errors="replace")
        headers = {str(key).lower(): str(value) for key, value in response.headers.items()}
        geturl = getattr(response, "geturl", None)
        final_url = geturl() if callable(geturl) else url
        return HttpResponse(
            status_code=int(getattr(response, "status", 200)),
            text=body,
            headers=headers,
            url=str(final_url),
        )

    def get(
        self,
        url: str,
        *,
        timeout: float = 15.0,
        params: dict[str, Any] | None = None,
    ) -> HttpResponse:
        target = url
        if params:
            query = urllib.parse.urlencode(params)
            separator = "&" if urllib.parse.urlsplit(url).query else "?"
            target = f"{url}{separator}{query}"
        request = urllib.request.Request(target, headers=dict(_DEFAULT_HEADERS))
        response = self._opener.open(request, timeout=timeout)
        return self._finalize(response, target)

    def post(
        self,
        url: str,
        *,
        data: dict[str, Any] | None = None,
        timeout: float = 15.0,
        allow_redirects: bool = True,
    ) -> HttpResponse:
        del allow_redirects  # urllib follows redirects; cookies are preserved by the jar
        payload = urllib.parse.urlencode(data or {}).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=payload,
            headers={**_DEFAULT_HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
        )
        response = self._opener.open(request, timeout=timeout)
        return self._finalize(response, url)

    def close(self) -> None:  # pragma: no cover - compatibility no-op
        return None
