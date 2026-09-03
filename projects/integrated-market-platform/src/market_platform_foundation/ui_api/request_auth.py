"""Request authentication and authorization helpers for ui_api (TD-005)."""

from __future__ import annotations

from http import HTTPStatus
from typing import Any, Mapping

from ..operational_identity import OperationalIdentityError
from ..platform.security.access_control import (
    AuthorizationErrorCode,
    AuthorizationFailure,
    AuthorizedPrincipal,
    authenticate_session_token,
    authorize_account_access,
    authorize_capability,
    authorize_operational_identity,
)
from ..platform.security.redaction import build_log_line
from ..platform.security.route_policy import (
    AccountScopeKind,
    capability_for_canary_command,
    policy_for_route,
    resolve_account_scope,
)
from .store import ReplayStore


def extract_session_token(headers: Mapping[str, str]) -> str | None:
    auth_header = headers.get("Authorization") or headers.get("authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        return token or None
    session_header = headers.get("X-IMP-Session") or headers.get("x-imp-session")
    if session_header:
        return session_header.strip() or None
    return None


def authorize_http_request(
    store: ReplayStore,
    *,
    method: str,
    path: str,
    headers: Mapping[str, str],
    query: Mapping[str, list[str]],
    body: dict[str, Any] | None = None,
) -> AuthorizedPrincipal | AuthorizationFailure:
    policy = policy_for_route(method, path)
    if policy.public_in_enforced_mode:
        token = extract_session_token(headers)
        principal = authenticate_session_token(token)
        if isinstance(principal, AuthorizationFailure):
            return principal
        return principal

    token = extract_session_token(headers)
    principal = authenticate_session_token(token)
    if isinstance(principal, AuthorizationFailure):
        return principal

    capability = policy.capability
    if path == "/canary/command" and body is not None:
        capability = capability_for_canary_command(body)

    if capability:
        failure = authorize_capability(principal, capability)
        if failure is not None:
            return failure

    if policy.account_scope != AccountScopeKind.NONE:
        try:
            identity = resolve_account_scope(
                store,
                policy.account_scope,
                query=query,
                body=body,
            )
        except (OperationalIdentityError, ValueError) as exc:
            return AuthorizationFailure(
                AuthorizationErrorCode.ACCOUNT_ACCESS_DENIED,
                str(exc),
            )
        if identity is not None:
            failure = authorize_operational_identity(principal, identity)
            if failure is not None:
                return failure
        elif policy.account_scope == AccountScopeKind.QUERY_ACCOUNT_ID:
            account_id = (query.get("account_id") or [None])[0]
            if account_id:
                failure = authorize_account_access(principal, str(account_id))
                if failure is not None:
                    return failure

    return principal


def authorization_http_status(failure: AuthorizationFailure) -> HTTPStatus:
    if failure.code.value in {"AUTH_REQUIRED", "AUTH_INVALID"}:
        return HTTPStatus.UNAUTHORIZED
    return HTTPStatus.FORBIDDEN


def log_server_event(event: str, **fields: Any) -> None:
    line = build_log_line(event, level="INFO", fields=fields)
    print(line, flush=True)
