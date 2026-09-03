"""Auth API projections for UI-001 (TD-005)."""

from __future__ import annotations

from typing import Any

from ..platform.security.access_control import (
    AuthorizationErrorCode,
    AuthorizationFailure,
    AuthorizedPrincipal,
    login_principal,
    logout_session,
    loopback_trust_principal,
    role_enforcement_status,
)
from ..platform.security.auth_config import AuthEnforcementMode, load_auth_config
from ..platform.security.sessions import get_session_store


def build_auth_status_payload() -> dict[str, Any]:
    config = load_auth_config()
    return {
        "authority_boundary": "OPERATOR_AUTHENTICATION",
        "enforcement_mode": config.enforcement_mode.value,
        "role_enforcement_status": role_enforcement_status(),
        "session_required": config.enforcement_mode == AuthEnforcementMode.ENFORCED,
        "login_path": "/auth/login",
        "session_path": "/auth/session",
    }


def build_auth_session_payload(
    principal: AuthorizedPrincipal,
    *,
    token: str | None = None,
) -> dict[str, Any]:
    config = load_auth_config()
    body: dict[str, Any] = {
        "authority_boundary": "OPERATOR_AUTHENTICATION",
        "enforcement_mode": config.enforcement_mode.value,
        "role_enforcement_status": role_enforcement_status(),
        **principal.to_public_dict(),
    }
    if config.enforcement_mode == AuthEnforcementMode.LOOPBACK_TRUST:
        body["authenticated"] = True
        body["session_token"] = None
        return body
    body["authenticated"] = True
    if token:
        body["session_token"] = token
    session = get_session_store().get(token or "")
    if session is not None:
        body["expires_at_ns"] = session.expires_at_ns
    return body


def handle_auth_login(body: dict[str, Any]) -> dict[str, Any] | AuthorizationFailure:
    principal_id = str(body.get("principal_id", "")).strip()
    secret = str(body.get("secret", ""))
    if not principal_id or not secret:
        return AuthorizationFailure(
            AuthorizationErrorCode.AUTH_INVALID,
            "principal_id and secret required",
        )
    result = login_principal(principal_id=principal_id, secret=secret)
    if isinstance(result, AuthorizationFailure):
        return result
    session, principal = result
    payload = build_auth_session_payload(principal, token=session.token)
    payload["issued_at_ns"] = session.issued_at_ns
    return payload


def handle_auth_logout(token: str | None) -> dict[str, Any]:
    logout_session(token)
    return {
        "authority_boundary": "OPERATOR_AUTHENTICATION",
        "logged_out": True,
        "role_enforcement_status": role_enforcement_status(),
    }


def build_security_readiness_payload() -> dict[str, Any]:
    from ..platform.security.readiness import build_readiness_payload, collect_default_gates

    gates = collect_default_gates()
    checks = {
        "auth_enforcement_mode": load_auth_config().enforcement_mode.value,
        "role_enforcement_status": role_enforcement_status(),
    }
    return build_readiness_payload(
        gates=gates,
        mode_context={"surface": "ui_api"},
        checks=checks,
        schema="platform/readiness/auth/1.0.0",
    )


def unauthenticated_session_payload() -> dict[str, Any]:
    config = load_auth_config()
    if config.enforcement_mode == AuthEnforcementMode.LOOPBACK_TRUST:
        return build_auth_session_payload(loopback_trust_principal())
    return {
        "authority_boundary": "OPERATOR_AUTHENTICATION",
        "authenticated": False,
        "enforcement_mode": config.enforcement_mode.value,
        "role_enforcement_status": role_enforcement_status(),
    }
