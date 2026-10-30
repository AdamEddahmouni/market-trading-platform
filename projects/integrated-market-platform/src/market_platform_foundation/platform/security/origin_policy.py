"""Browser-origin policy shared by the UI API (:8766) and the lifecycle control service (:8767) (AUD-001).

Both services bind loopback and, under LOOPBACK_TRUST, treat every caller as the local ADMIN. A browser on
this PC is the one client that can be steered by a page from another site, so browser requests are held to
an exact allowlist of the IMP UI origins:

* a request whose ``Origin`` header is present and not allowlisted is refused for every route and method,
  including preflight, before any handler runs;
* ``Sec-Fetch-Site: cross-site`` is refused even without ``Origin`` (no-cors loads, navigations from another
  site);
* a browser mutation must carry ``Content-Type: application/json``, which a cross-site page cannot send without
  a preflight that the first rule already refuses (closes the text/plain / form "simple request" path);
* CORS headers reflect an allowlisted origin only; there is no wildcard.

A request with no browser markers (no ``Origin``, no ``Sec-Fetch-*``: the keeper, launcher, CLI, tests, curl)
is not a page and keeps its existing treatment; the capability check still applies to it. This is not
authentication: any local process can still call the API (see the ENFORCED auth mode for that).
"""

from __future__ import annotations

import os
from typing import Mapping
from urllib.parse import urlparse

DEFAULT_UI_ORIGINS: frozenset[str] = frozenset({"http://127.0.0.1:5173", "http://localhost:5173"})
# Comma-separated extra origins (e.g. an e2e UI on another port). Exact matches only; no wildcards.
ALLOWED_ORIGINS_ENV = "IMP_UI_ALLOWED_ORIGINS"
MUTATING_METHODS: frozenset[str] = frozenset({"POST", "PUT", "PATCH", "DELETE"})

ORIGIN_NOT_ALLOWED = "ORIGIN_NOT_ALLOWED"
CROSS_SITE_REQUEST = "CROSS_SITE_REQUEST"
CONTENT_TYPE_NOT_JSON = "CONTENT_TYPE_NOT_JSON"


def normalize_origin(origin: str | None) -> str | None:
    """``scheme://host[:port]`` in lower case, or None when the value is not an http(s) origin."""
    if origin is None:
        return None
    text = str(origin).strip()
    if not text:
        return None
    try:
        parsed = urlparse(text)
    except ValueError:
        return None
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname or parsed.path not in {"", "/"} \
            or parsed.query or parsed.fragment or parsed.username or parsed.password:
        return None
    host = parsed.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    try:
        port = parsed.port
    except ValueError:
        return None
    return f"{parsed.scheme.lower()}://{host}" + (f":{port}" if port is not None else "")


def allowed_origins(environ: Mapping[str, str] | None = None) -> frozenset[str]:
    env = os.environ if environ is None else environ
    extra = {normalize_origin(item) for item in str(env.get(ALLOWED_ORIGINS_ENV, "")).split(",")}
    return DEFAULT_UI_ORIGINS | frozenset(item for item in extra if item)


def _lowered(headers: Mapping[str, str]) -> dict[str, str]:
    return {str(key).lower(): str(value) for key, value in headers.items()}


def is_browser_request(headers: Mapping[str, str]) -> bool:
    lowered = _lowered(headers)
    return "origin" in lowered or any(key.startswith("sec-fetch-") for key in lowered)


def allowed_request_origin(headers: Mapping[str, str], environ: Mapping[str, str] | None = None) -> str | None:
    """The request's Origin when it is allowlisted (the value to reflect in CORS headers), else None."""
    raw = _lowered(headers).get("origin")
    origin = normalize_origin(raw)
    return raw.strip() if origin is not None and origin in allowed_origins(environ) else None


def browser_request_refusal(method: str, headers: Mapping[str, str],
                            environ: Mapping[str, str] | None = None) -> str | None:
    """A refusal code for a browser request this service must not serve, or None to continue."""
    lowered = _lowered(headers)
    if lowered.get("sec-fetch-site", "").strip().lower() == "cross-site":
        return CROSS_SITE_REQUEST
    if "origin" in lowered and allowed_request_origin(headers, environ) is None:
        return ORIGIN_NOT_ALLOWED  # includes "null" (sandboxed frames, file:// pages)
    if method.upper() in MUTATING_METHODS and is_browser_request(headers):
        content_type = lowered.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            return CONTENT_TYPE_NOT_JSON
    return None
