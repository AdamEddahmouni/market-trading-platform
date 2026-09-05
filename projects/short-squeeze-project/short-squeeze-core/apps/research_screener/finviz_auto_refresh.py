"""Automatic Finviz Elite export-token recovery for unattended operation."""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

_log = logging.getLogger(__name__)
_LOCK = threading.Lock()
_LAST_ATTEMPT = 0.0


def auto_refresh_enabled() -> bool:
    return os.environ.get("FINVIZ_AUTO_REFRESH", "true").strip().lower() in {
        "1", "true", "yes", "on",
    }


def refresh_cooldown_seconds() -> int:
    raw = os.environ.get("FINVIZ_AUTO_REFRESH_COOLDOWN_S", "300").strip()
    try:
        return max(60, int(raw))
    except ValueError:
        return 300


def is_token_expired_error(error: str | None) -> bool:
    text = str(error or "").lower()
    return any(
        marker in text
        for marker in (
            "401",
            "invalid",
            "login",
            "expired",
            "finviz_export_login",
            "token expired",
        )
    )


@dataclass(frozen=True, slots=True)
class AutoRefreshResult:
    attempted: bool
    refreshed: bool
    status: str | None = None
    detail: str | None = None


def _curl_session_factory() -> object:
    from curl_cffi import requests as curl_requests

    return curl_requests.Session()


def refresh_finviz_token_if_configured(
    path: Path,
    *,
    emit: Callable[[str], None] | None = None,
) -> AutoRefreshResult:
    if not auto_refresh_enabled():
        return AutoRefreshResult(attempted=False, refreshed=False, status="DISABLED")

    global _LAST_ATTEMPT
    with _LOCK:
        now = time.time()
        if now - _LAST_ATTEMPT < refresh_cooldown_seconds():
            return AutoRefreshResult(attempted=False, refreshed=False, status="COOLDOWN")
        _LAST_ATTEMPT = now

    try:
        import curl_cffi  # noqa: F401
    except ImportError:
        return AutoRefreshResult(
            attempted=True,
            refreshed=False,
            status="DEPENDENCY_MISSING",
            detail="curl_cffi required for Finviz auto-refresh",
        )

    from tools.provider_auth.finviz_token_refresh import RefreshStatus, refresh_finviz_token

    messages: list[str] = []
    writer = emit or messages.append
    result = refresh_finviz_token(path, _curl_session_factory, emit=writer)
    if result.status == RefreshStatus.REFRESHED:
        from .credentials import load_private_env

        load_private_env(path, verbose=False)
        return AutoRefreshResult(attempted=True, refreshed=True, status="REFRESHED")
    return AutoRefreshResult(
        attempted=True,
        refreshed=False,
        status=str(result.status),
        detail=messages[-1] if messages else None,
    )


def apply_refreshed_key_to_runtime(runtime: Any, path: Path) -> bool:
    from .credentials import load_private_env
    from .private_config import load_provider_credentials

    load_private_env(path, verbose=False)
    token = load_provider_credentials(path).values.get("FINVIZ_API_KEY")
    if not token:
        return False
    finviz = runtime.finviz
    if hasattr(finviz, "set_api_key"):
        finviz.set_api_key(token)
    return True


def ensure_finviz_operational(
    runtime: Any,
    *,
    providers_path: Path,
    force: bool = False,
) -> AutoRefreshResult:
    """Probe Finviz export; refresh token automatically when expired."""
    finviz = runtime.finviz
    if not finviz.configured:
        return AutoRefreshResult(attempted=False, refreshed=False, status="NOT_CONFIGURED")

    probe = finviz.fetch_screener(force=True)
    if probe.get("success") and not force:
        return AutoRefreshResult(attempted=False, refreshed=False, status="VALID")

    error = str(probe.get("error") or "")
    if not force and not is_token_expired_error(error):
        return AutoRefreshResult(
            attempted=False,
            refreshed=False,
            status="PROBE_FAILED",
            detail=error or None,
        )

    refresh = refresh_finviz_token_if_configured(providers_path)
    if refresh.refreshed:
        apply_refreshed_key_to_runtime(runtime, providers_path)
        retry = finviz.fetch_screener(force=True)
        if retry.get("success"):
            print(
                f"  Finviz auto-refresh: token renewed "
                f"({int(retry.get('rows', 0))} screener rows)"
            )
        else:
            print(
                "  Finviz auto-refresh: token updated but export still failing: "
                f"{retry.get('error')}"
            )
    else:
        detail = refresh.detail or refresh.status or "unknown"
        print(f"  Finviz auto-refresh: {detail}")
    return refresh


def maybe_recover_finviz(
    runtime: Any,
    error: str | None,
    providers_path: Path | None,
) -> bool:
    if providers_path is None or not is_token_expired_error(error):
        return False
    refresh = refresh_finviz_token_if_configured(providers_path)
    if not refresh.refreshed:
        _log.info("Finviz auto-refresh skipped or failed: %s", refresh.status)
        return False
    apply_refreshed_key_to_runtime(runtime, providers_path)
    return True
