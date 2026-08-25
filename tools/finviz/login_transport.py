"""Optional browser-impersonating transport for Finviz login recovery.

The governed Finviz export client remains standard-library-only. This tool-layer
module registers ``curl_cffi`` only for the exceptional login/key-recovery flow
when the optional package is already available in the launcher environment.
"""

from __future__ import annotations

import os
from typing import Any

from market_platform_foundation.finviz.login_recovery import (
    reset_login_session_factory,
    set_login_session_factory,
)

_UNSET = object()
_ALLOWED_MODES = frozenset({"auto", "urllib", "curl_cffi"})


def _optional_curl_requests() -> Any | None:
    try:
        from curl_cffi import requests as curl_requests
    except ImportError:
        return None
    return curl_requests


def configure_login_transport(
    mode: str | None = None,
    *,
    requests_module: Any = _UNSET,
) -> str:
    """Register the requested login-only session and return its public label."""
    selected = (mode or os.environ.get("IMP_FINVIZ_LOGIN_TRANSPORT", "auto")).strip().lower()
    if selected not in _ALLOWED_MODES:
        raise RuntimeError("Finviz login transport must be auto, urllib, or curl_cffi")
    if selected == "urllib":
        reset_login_session_factory()
        return "URLLIB"

    curl_requests = (
        _optional_curl_requests()
        if requests_module is _UNSET
        else requests_module
    )
    if curl_requests is None:
        reset_login_session_factory()
        if selected == "curl_cffi":
            raise RuntimeError("curl_cffi login transport is unavailable")
        return "URLLIB"

    set_login_session_factory(
        lambda: curl_requests.Session(impersonate="chrome")
    )
    return "CURL_CFFI"
