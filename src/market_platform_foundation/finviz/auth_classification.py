"""Classify Finviz HTTP responses — auth vs rate limit vs network vs provider."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class StrEnum(str, Enum):
    """Python 3.10-compatible StrEnum."""

class FinvizFailureKind(StrEnum):
    AUTH_OK = "AUTH_OK"
    AUTH_INVALID = "AUTH_INVALID"
    AUTH_EXPIRED = "AUTH_EXPIRED"
    AUTH_REVOKED = "AUTH_REVOKED"
    SUBSCRIPTION_NOT_ELITE = "SUBSCRIPTION_NOT_ELITE"
    RATE_LIMITED = "RATE_LIMITED"
    NETWORK_ERROR = "NETWORK_ERROR"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    UNKNOWN = "UNKNOWN"


_MANUAL_AUTH_MARKERS = (
    "captcha",
    "two-factor",
    "two factor",
    "multi-factor",
    "multifactor",
    "verification code",
    "security challenge",
)

_LOGIN_MARKERS = ("login", "log in", "sign in", "password", "unauthorized")


@dataclass(frozen=True, slots=True)
class FinvizResponseClassification:
    kind: FinvizFailureKind
    http_status: int | None
    triggers_recovery: bool
    detail: str = ""


def _body_snippet(body: str, limit: int = 5000) -> str:
    return (body or "")[:limit].lower()


def _looks_like_login_page(body: str, content_type: str) -> bool:
    lowered = _body_snippet(body)
    if "text/html" in (content_type or "").lower():
        return True
    if "<html" in lowered:
        return True
    return any(marker in lowered for marker in _LOGIN_MARKERS)


def _requires_manual_auth(body: str) -> bool:
    lowered = _body_snippet(body, 10_000)
    return any(marker in lowered for marker in _MANUAL_AUTH_MARKERS)


def classify_http_response(
    *,
    status_code: int | None,
    body: str = "",
    content_type: str = "",
    network_error: bool = False,
) -> FinvizResponseClassification:
    if network_error:
        return FinvizResponseClassification(
            FinvizFailureKind.NETWORK_ERROR,
            status_code,
            triggers_recovery=False,
            detail="network_error",
        )
    if status_code is None:
        return FinvizResponseClassification(
            FinvizFailureKind.UNKNOWN,
            None,
            triggers_recovery=False,
        )
    if status_code == 429:
        return FinvizResponseClassification(
            FinvizFailureKind.RATE_LIMITED,
            status_code,
            triggers_recovery=False,
        )
    if status_code >= 500:
        return FinvizResponseClassification(
            FinvizFailureKind.PROVIDER_ERROR,
            status_code,
            triggers_recovery=False,
        )
    if _requires_manual_auth(body):
        return FinvizResponseClassification(
            FinvizFailureKind.AUTH_INVALID,
            status_code,
            triggers_recovery=False,
            detail="manual_auth_required",
        )
    if status_code in (401, 403):
        lowered = _body_snippet(body)
        if "expired" in lowered or "token expired" in lowered:
            return FinvizResponseClassification(
                FinvizFailureKind.AUTH_EXPIRED,
                status_code,
                triggers_recovery=True,
            )
        if "revoked" in lowered:
            return FinvizResponseClassification(
                FinvizFailureKind.AUTH_REVOKED,
                status_code,
                triggers_recovery=True,
            )
        if "elite" in lowered and ("subscription" in lowered or "upgrade" in lowered):
            return FinvizResponseClassification(
                FinvizFailureKind.SUBSCRIPTION_NOT_ELITE,
                status_code,
                triggers_recovery=False,
            )
        return FinvizResponseClassification(
            FinvizFailureKind.AUTH_INVALID,
            status_code,
            triggers_recovery=True,
        )
    if status_code == 200 and _looks_like_login_page(body, content_type):
        return FinvizResponseClassification(
            FinvizFailureKind.AUTH_INVALID,
            status_code,
            triggers_recovery=True,
            detail="html_login_response",
        )
    if status_code == 200:
        return FinvizResponseClassification(
            FinvizFailureKind.AUTH_OK,
            status_code,
            triggers_recovery=False,
        )
    return FinvizResponseClassification(
        FinvizFailureKind.UNKNOWN,
        status_code,
        triggers_recovery=False,
    )
