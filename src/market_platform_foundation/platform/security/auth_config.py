"""Authentication and authorization enforcement configuration (TD-005)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

AUTH_CONFIG_SCHEMA = "platform/auth-config/1.0.0"
ENV_PREFIX = "IMP_AUTH_"

_TRUTHY = frozenset({"1", "true", "yes", "on"})


class AuthEnforcementMode(str, Enum):
    """How the UI API authenticates and authorizes requests."""

    LOOPBACK_TRUST = "LOOPBACK_TRUST"
    ENFORCED = "ENFORCED"


class AuthConfigError(ValueError):
    """Raised when auth configuration is invalid."""


@dataclass(frozen=True)
class AuthConfig:
    enforcement_mode: AuthEnforcementMode = AuthEnforcementMode.LOOPBACK_TRUST
    principals_path: str | None = None
    session_ttl_seconds: int = 86_400

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if self.session_ttl_seconds < 60 or self.session_ttl_seconds > 604_800:
            errors.append("SESSION_TTL_OUT_OF_RANGE")
        if self.enforcement_mode == AuthEnforcementMode.ENFORCED and not self.principals_path:
            errors.append("ENFORCED_REQUIRES_PRINCIPALS_PATH")
        return tuple(sorted(errors))

    def validated(self) -> "AuthConfig":
        errors = self.validate()
        if errors:
            raise AuthConfigError("; ".join(errors))
        return self


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in _TRUTHY


def parse_auth_config(mapping: Mapping[str, Any]) -> AuthConfig:
    mode_raw = str(mapping.get("enforcement_mode", AuthEnforcementMode.LOOPBACK_TRUST.value)).upper()
    try:
        mode = AuthEnforcementMode(mode_raw)
    except ValueError:
        raise AuthConfigError(f"UNKNOWN_AUTH_ENFORCEMENT_MODE: {mode_raw}")
    principals_path = mapping.get("principals_path")
    path = str(principals_path).strip() if principals_path else None
    ttl_raw = mapping.get("session_ttl_seconds", 86_400)
    return AuthConfig(
        enforcement_mode=mode,
        principals_path=path,
        session_ttl_seconds=int(ttl_raw),
    )


def load_auth_config(env: Mapping[str, str] | None = None) -> AuthConfig:
    source = env if env is not None else os.environ
    mode = AuthEnforcementMode.LOOPBACK_TRUST
    if _truthy(source.get(f"{ENV_PREFIX}ENFORCEMENT")):
        mode = AuthEnforcementMode.ENFORCED
    mode_raw = source.get(f"{ENV_PREFIX}ENFORCEMENT_MODE")
    if mode_raw:
        try:
            mode = AuthEnforcementMode(str(mode_raw).strip().upper())
        except ValueError:
            raise AuthConfigError(f"UNKNOWN_AUTH_ENFORCEMENT_MODE: {mode_raw}")
    principals_path = source.get(f"{ENV_PREFIX}PRINCIPALS_PATH")
    ttl_raw = source.get(f"{ENV_PREFIX}SESSION_TTL_SECONDS", "86400")
    return AuthConfig(
        enforcement_mode=mode,
        principals_path=str(principals_path).strip() if principals_path else None,
        session_ttl_seconds=int(ttl_raw),
    ).validated()


def load_principals_document(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise AuthConfigError("PRINCIPALS_DOCUMENT_MUST_BE_OBJECT")
    return payload
