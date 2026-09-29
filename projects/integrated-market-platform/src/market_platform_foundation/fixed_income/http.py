"""Bounded HTTP GET for public fixed-income publications.

Only allowlisted official hosts are reachable. Requests identify IMP with a
descriptive user agent: home.treasury.gov delays anonymous tool user agents by
~17 s per request (observed 2026-09-27) and answers a descriptive one in
~0.4 s. Errors surface as stable codes; URLs and bodies are never echoed.
"""

from __future__ import annotations

import json
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

USER_AGENT = "IMP-FixedIncome/1.0 (Integrated Market Platform research workstation)"
DEFAULT_TIMEOUT_S = 20.0
MAX_BODY_BYTES = 16 * 1024 * 1024
#: Treasury Fiscal Data, Treasury daily rates, the New York Fed Markets API (S16), and OpenFIGI (S16, opt-in).
ALLOWED_HOSTS = frozenset({"api.fiscaldata.treasury.gov", "home.treasury.gov", "markets.newyorkfed.org",
                           "api.openfigi.com"})

#: ``(url, timeout_s) -> body bytes``; tests inject a fake.
Getter = Callable[[str, float], bytes]


class FixedIncomeSourceError(OSError):
    """A source failure carrying only a stable code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def http_get(url: str, timeout_s: float = DEFAULT_TIMEOUT_S) -> bytes:
    host = urlsplit(url).hostname or ""
    if host not in ALLOWED_HOSTS:
        raise FixedIncomeSourceError("HOST_NOT_ALLOWED")
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json, application/xml"})
    try:
        with urlopen(request, timeout=timeout_s) as response:  # noqa: S310 — allowlisted https hosts
            body = response.read(MAX_BODY_BYTES + 1)
    except HTTPError as exc:
        raise FixedIncomeSourceError(f"HTTP_{exc.code}") from None
    except (URLError, TimeoutError, OSError):
        raise FixedIncomeSourceError("SOURCE_UNREACHABLE") from None
    if len(body) > MAX_BODY_BYTES:
        raise FixedIncomeSourceError("RESPONSE_TOO_LARGE")
    return body


def http_post_json(url: str, payload: Any, timeout_s: float = DEFAULT_TIMEOUT_S,
                   headers: dict[str, str] | None = None) -> Any:
    """POST a JSON body to an allowlisted host; same stable failure codes as ``http_get``."""

    host = urlsplit(url).hostname or ""
    if host not in ALLOWED_HOSTS:
        raise FixedIncomeSourceError("HOST_NOT_ALLOWED")
    request = Request(url, data=json.dumps(payload).encode("utf-8"), method="POST",
                      headers={"User-Agent": USER_AGENT, "Content-Type": "application/json", **(headers or {})})
    try:
        with urlopen(request, timeout=timeout_s) as response:  # noqa: S310 — allowlisted https hosts
            body = response.read(MAX_BODY_BYTES + 1)
    except HTTPError as exc:
        raise FixedIncomeSourceError(f"HTTP_{exc.code}") from None
    except (URLError, TimeoutError, OSError):
        raise FixedIncomeSourceError("SOURCE_UNREACHABLE") from None
    if len(body) > MAX_BODY_BYTES:
        raise FixedIncomeSourceError("RESPONSE_TOO_LARGE")
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise FixedIncomeSourceError("MALFORMED_RESPONSE") from None


def get_json(get: Getter, url: str, timeout_s: float = DEFAULT_TIMEOUT_S) -> Any:
    try:
        return json.loads(get(url, timeout_s).decode("utf-8"))
    except FixedIncomeSourceError:
        raise
    except (UnicodeDecodeError, ValueError):
        raise FixedIncomeSourceError("MALFORMED_RESPONSE") from None


def failure_code(exc: BaseException) -> str:
    return exc.code if isinstance(exc, FixedIncomeSourceError) else "SOURCE_UNAVAILABLE"
