"""Request authorization against roles and operational account ACLs (TD-005)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from ...operational_identity import OperationalIdentity
from .auth_config import AuthConfig, AuthEnforcementMode, load_auth_config
from .principals import ALL_ACCOUNTS, PrincipalRecord, load_principal_registry, verify_principal_secret
from .roles import OperatorRole, role_allows
from .sessions import OperatorSession, SessionStore, get_session_store

ROLE_ENFORCEMENT_LOOPBACK_TRUST = "LOOPBACK_TRUST"
ROLE_ENFORCEMENT_ENFORCED = "ENFORCED"


class AuthorizationErrorCode(str, Enum):
    AUTH_REQUIRED = "AUTH_REQUIRED"
    AUTH_INVALID = "AUTH_INVALID"
    CAPABILITY_DENIED = "CAPABILITY_DENIED"
    ACCOUNT_ACCESS_DENIED = "ACCOUNT_ACCESS_DENIED"


@dataclass(frozen=True)
class AuthorizationFailure:
    code: AuthorizationErrorCode
    message: str

    def to_error_payload(self) -> dict[str, str]:
        return {"error": self.message, "reason_code": self.code.value}


@dataclass(frozen=True)
class AuthorizedPrincipal:
    principal_id: str
    display_name: str
    role: OperatorRole
    permitted_accounts: frozenset[str]
    session_token: str | None = None
    enforcement_mode: AuthEnforcementMode = AuthEnforcementMode.LOOPBACK_TRUST

    def permits_capability(self, capability: str) -> bool:
        return role_allows(self.role, capability)

    def permits_account(self, account_id: str) -> bool:
        if ALL_ACCOUNTS in self.permitted_accounts:
            return True
        return account_id in self.permitted_accounts

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "principal_id": self.principal_id,
            "display_name": self.display_name,
            "role": self.role.value,
            "permitted_accounts": sorted(self.permitted_accounts),
            "enforcement_mode": self.enforcement_mode.value,
            "role_enforcement_status": role_enforcement_status(),
        }


_LOOPBACK_TRUST_PRINCIPAL = AuthorizedPrincipal(
    principal_id="loopback-trust",
    display_name="Loopback trust operator",
    role=OperatorRole.ADMIN,
    permitted_accounts=frozenset({ALL_ACCOUNTS}),
    enforcement_mode=AuthEnforcementMode.LOOPBACK_TRUST,
)

_principal_registry_cache: dict[str, dict[str, PrincipalRecord]] = {}


def role_enforcement_status() -> str:
    config = load_auth_config()
    if config.enforcement_mode == AuthEnforcementMode.ENFORCED:
        return ROLE_ENFORCEMENT_ENFORCED
    return ROLE_ENFORCEMENT_LOOPBACK_TRUST


def reset_principal_registry_for_tests() -> None:
    _principal_registry_cache.clear()
    get_session_store().reset_for_tests()


def _principal_registry(config: AuthConfig) -> dict[str, PrincipalRecord]:
    path = config.principals_path or ""
    if path not in _principal_registry_cache:
        _principal_registry_cache[path] = load_principal_registry(path)
    return _principal_registry_cache[path]


def loopback_trust_principal() -> AuthorizedPrincipal:
    return _LOOPBACK_TRUST_PRINCIPAL


def authenticate_session_token(
    token: str | None,
    *,
    config: AuthConfig | None = None,
    store: SessionStore | None = None,
) -> AuthorizedPrincipal | AuthorizationFailure:
    cfg = config or load_auth_config()
    if cfg.enforcement_mode == AuthEnforcementMode.LOOPBACK_TRUST:
        return loopback_trust_principal()
    if not token:
        return AuthorizationFailure(
            AuthorizationErrorCode.AUTH_REQUIRED,
            "Authenticated session required",
        )
    session_store = store or get_session_store()
    session = session_store.get(token)
    if session is None:
        return AuthorizationFailure(
            AuthorizationErrorCode.AUTH_INVALID,
            "Session expired or invalid",
        )
    return AuthorizedPrincipal(
        principal_id=session.principal_id,
        display_name=session.display_name,
        role=OperatorRole(session.role),
        permitted_accounts=session.permitted_accounts,
        session_token=session.token,
        enforcement_mode=cfg.enforcement_mode,
    )


def authorize_capability(
    principal: AuthorizedPrincipal,
    capability: str,
) -> AuthorizationFailure | None:
    if principal.permits_capability(capability):
        return None
    return AuthorizationFailure(
        AuthorizationErrorCode.CAPABILITY_DENIED,
        f"Capability denied: {capability}",
    )


def authorize_account_access(
    principal: AuthorizedPrincipal,
    account_id: str,
) -> AuthorizationFailure | None:
    if principal.permits_account(account_id):
        return None
    return AuthorizationFailure(
        AuthorizationErrorCode.ACCOUNT_ACCESS_DENIED,
        f"Account access denied: {account_id}",
    )


def authorize_operational_identity(
    principal: AuthorizedPrincipal,
    identity: OperationalIdentity,
) -> AuthorizationFailure | None:
    return authorize_account_access(principal, identity.account_id)


def login_principal(
    *,
    principal_id: str,
    secret: str,
    config: AuthConfig | None = None,
    store: SessionStore | None = None,
) -> tuple[OperatorSession, AuthorizedPrincipal] | AuthorizationFailure:
    cfg = config or load_auth_config()
    if cfg.enforcement_mode != AuthEnforcementMode.ENFORCED:
        return AuthorizationFailure(
            AuthorizationErrorCode.AUTH_INVALID,
            "Login only required when auth enforcement is ENFORCED",
        )
    registry = _principal_registry(cfg)
    record = registry.get(principal_id)
    if record is None or not verify_principal_secret(record, secret):
        return AuthorizationFailure(
            AuthorizationErrorCode.AUTH_INVALID,
            "Invalid credentials",
        )
    session_store = store or get_session_store()
    session = session_store.create_session(record, ttl_seconds=cfg.session_ttl_seconds)
    principal = AuthorizedPrincipal(
        principal_id=record.principal_id,
        display_name=record.display_name,
        role=record.role,
        permitted_accounts=record.permitted_accounts,
        session_token=session.token,
        enforcement_mode=cfg.enforcement_mode,
    )
    return session, principal


def logout_session(token: str | None, *, store: SessionStore | None = None) -> None:
    if not token:
        return
    session_store = store or get_session_store()
    session_store.revoke(token)
