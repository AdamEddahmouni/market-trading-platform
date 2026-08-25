"""Narrow Finviz login-based token recovery — authentication maintenance only."""

from __future__ import annotations

import csv
import io
import re
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Protocol
from urllib.parse import urlparse

LOGIN_PAGE_URL = "https://finviz.com/login-email?remember=true"
LOGIN_SUBMIT_URL = "https://finviz.com/login_submit"
TOKEN_PAGE_URL = "https://elite.finviz.com/api_explanation"
EXPORT_URL = "https://elite.finviz.com/export/screener"
EXPORT_VERSION = "152"
EXPORT_FILTER = "sh_float_u20,sh_price_u20"
EXPORT_COLUMNS = "1,25,26,30,31,84,42,43,49,50,52,53,55,59,56,60,61,64,65,66,57,81,86,87"

ALLOWED_HOSTS = frozenset(
    {
        "finviz.com",
        "www.finviz.com",
        "elite.finviz.com",
    },
)

TOKEN_PATTERN = re.compile(
    r"[?&]auth=([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-"
    r"[a-f0-9]{4}-[a-f0-9]{12})",
    re.IGNORECASE,
)
USER_TOKEN_PATTERN = re.compile(
    r"userToken.{0,256}?([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-"
    r"[a-f0-9]{4}-[a-f0-9]{12})",
    re.IGNORECASE | re.DOTALL,
)
TOKEN_VALUE_PATTERN = re.compile(
    r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-"
    r"[a-f0-9]{4}-[a-f0-9]{12}$",
    re.IGNORECASE,
)

MANUAL_AUTH_MARKERS = (
    "captcha",
    "two-factor",
    "two factor",
    "multi-factor",
    "multifactor",
    "verification code",
    "security challenge",
)

_SESSION_FACTORY: Callable[[], Any] | None = None
_SESSION_FACTORY_LOCK = threading.Lock()


class StrEnum(str, Enum):
    """Python 3.10-compatible StrEnum."""


class LoginRecoveryStatus(StrEnum):
    REFRESHED = "REFRESHED"
    MANUAL_AUTH_REQUIRED = "MANUAL_AUTH_REQUIRED"
    INVALID_EXPORT = "INVALID_EXPORT"
    CONFIG_MISSING = "CONFIG_MISSING"
    AUTH_FAILED = "AUTH_FAILED"
    TOKEN_NOT_FOUND = "TOKEN_NOT_FOUND"
    NETWORK_ERROR = "NETWORK_ERROR"
    DEPENDENCY_MISSING = "DEPENDENCY_MISSING"
    REDIRECT_REJECTED = "REDIRECT_REJECTED"


@dataclass(frozen=True, slots=True)
class LoginRecoveryResult:
    status: LoginRecoveryStatus
    token: str | None = None
    http_status: int | None = None
    detail: str = ""


class ResponseLike(Protocol):
    text: str
    status_code: int
    url: object
    headers: dict[str, str]


def validate_host(url: str) -> bool:
    try:
        host = urlparse(str(url)).hostname or ""
        return host.lower() in ALLOWED_HOSTS
    except (ValueError, TypeError):
        return False


def _requires_manual_auth(text: str) -> bool:
    lowered = text[:10_000].lower()
    return any(marker in lowered for marker in MANUAL_AUTH_MARKERS)


def _looks_like_login(text: str) -> bool:
    lowered = text[:10_000].lower()
    return any(marker in lowered for marker in ("login", "log in", "sign in", "password"))


def validate_export_response(response: ResponseLike) -> tuple[bool, str | None]:
    status = int(response.status_code)
    content_type = str(response.headers.get("content-type", "")).split(";", 1)[0].strip()
    text = response.text or ""
    lowered = text[:10_000].lower()
    if _requires_manual_auth(lowered):
        return False, "MANUAL_AUTH_REQUIRED"
    if "text/html" in content_type or "<html" in lowered:
        return False, "LOGIN_PAGE" if _looks_like_login(lowered) else "HTML_RESPONSE"
    if status != 200:
        return False, "HTTP_ERROR"
    try:
        reader = csv.DictReader(io.StringIO(text))
        columns = tuple(reader.fieldnames or ())
        if "Ticker" not in columns:
            return False, "NOT_CSV"
        rows = sum(1 for row in reader if (row.get("Ticker") or "").strip())
    except (csv.Error, TypeError):
        return False, "NOT_CSV"
    if rows < 1:
        return False, "EMPTY_EXPORT"
    return True, None


def set_login_session_factory(factory: Callable[[], Any]) -> None:
    """Register an optional tool-layer session for login recovery only."""
    global _SESSION_FACTORY
    with _SESSION_FACTORY_LOCK:
        _SESSION_FACTORY = factory


def reset_login_session_factory() -> None:
    global _SESSION_FACTORY
    with _SESSION_FACTORY_LOCK:
        _SESSION_FACTORY = None


def _registered_session_factory() -> Callable[[], Any] | None:
    with _SESSION_FACTORY_LOCK:
        return _SESSION_FACTORY


def recover_token_via_login(
    *,
    username: str,
    password: str,
    session_factory: Callable[[], Any] | None = None,
) -> LoginRecoveryResult:
    if not username or not password:
        return LoginRecoveryResult(LoginRecoveryStatus.CONFIG_MISSING)
    factory = session_factory or _registered_session_factory() or _default_session_factory
    if factory is None:
        return LoginRecoveryResult(LoginRecoveryStatus.DEPENDENCY_MISSING)
    session: Any | None = None
    try:
        session = factory()
        login_page = session.get(LOGIN_PAGE_URL, timeout=15)
        if not validate_host(str(login_page.url)):
            return LoginRecoveryResult(
                LoginRecoveryStatus.REDIRECT_REJECTED,
                http_status=int(login_page.status_code),
                detail="login_page_redirect",
            )
        login_page_text = (login_page.text or "")[:10_000].lower()
        if _requires_manual_auth(login_page_text):
            return LoginRecoveryResult(LoginRecoveryStatus.MANUAL_AUTH_REQUIRED)
        if int(login_page.status_code) != 200:
            return LoginRecoveryResult(
                LoginRecoveryStatus.AUTH_FAILED,
                http_status=int(login_page.status_code),
            )

        login = session.post(
            LOGIN_SUBMIT_URL,
            data={"email": username, "password": password, "remember": "on"},
            timeout=15,
            allow_redirects=True,
        )
        if not validate_host(str(login.url)):
            return LoginRecoveryResult(
                LoginRecoveryStatus.REDIRECT_REJECTED,
                http_status=int(login.status_code),
                detail="login_redirect",
            )
        login_text = (login.text or "")[:10_000].lower()
        if _requires_manual_auth(login_text):
            return LoginRecoveryResult(LoginRecoveryStatus.MANUAL_AUTH_REQUIRED)
        if int(login.status_code) != 200:
            return LoginRecoveryResult(
                LoginRecoveryStatus.AUTH_FAILED,
                http_status=int(login.status_code),
            )

        token_page = session.get(TOKEN_PAGE_URL, timeout=15)
        if not validate_host(str(token_page.url)):
            return LoginRecoveryResult(
                LoginRecoveryStatus.REDIRECT_REJECTED,
                http_status=int(token_page.status_code),
                detail="token_page_redirect",
            )
        page_text = token_page.text or ""
        if _requires_manual_auth(page_text[:10_000].lower()):
            return LoginRecoveryResult(LoginRecoveryStatus.MANUAL_AUTH_REQUIRED)
        match = TOKEN_PATTERN.search(page_text) or USER_TOKEN_PATTERN.search(page_text)
        if int(token_page.status_code) != 200 or match is None:
            return LoginRecoveryResult(
                LoginRecoveryStatus.TOKEN_NOT_FOUND,
                http_status=int(token_page.status_code),
            )
        token = match.group(1)
        if not TOKEN_VALUE_PATTERN.fullmatch(token):
            return LoginRecoveryResult(LoginRecoveryStatus.TOKEN_NOT_FOUND)

        validation_response = session.get(
            EXPORT_URL,
            params={
                "v": EXPORT_VERSION,
                "f": EXPORT_FILTER,
                "c": EXPORT_COLUMNS,
                "auth": token,
            },
            timeout=15,
        )
        if not validate_host(str(validation_response.url)):
            return LoginRecoveryResult(
                LoginRecoveryStatus.REDIRECT_REJECTED,
                http_status=int(validation_response.status_code),
                detail="validation_redirect",
            )
        valid, error = validate_export_response(validation_response)
        if not valid:
            if error == "MANUAL_AUTH_REQUIRED":
                return LoginRecoveryResult(LoginRecoveryStatus.MANUAL_AUTH_REQUIRED)
            return LoginRecoveryResult(
                LoginRecoveryStatus.INVALID_EXPORT,
                http_status=int(validation_response.status_code),
                detail=error or "invalid_export",
            )
        return LoginRecoveryResult(
            LoginRecoveryStatus.REFRESHED,
            token=token,
            http_status=int(validation_response.status_code),
        )
    except Exception:
        return LoginRecoveryResult(LoginRecoveryStatus.NETWORK_ERROR)
    finally:
        if session is not None:
            dispose_session(session)


def _default_session_factory() -> Any | None:
    from .http_client import UrllibSession

    return UrllibSession()


def dispose_session(session: Any) -> None:
    try:
        close = getattr(session, "close", None)
        if callable(close):
            close()
    except Exception:
        pass
