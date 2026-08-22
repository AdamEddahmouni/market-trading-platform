"""Finviz Elite authentication state machine."""

from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """Python 3.10-compatible StrEnum."""


class FinvizAuthState(StrEnum):
    UNCONFIGURED = "UNCONFIGURED"
    LOADED = "LOADED"
    VALIDATING = "VALIDATING"
    HEALTHY = "HEALTHY"
    AUTH_INVALID = "AUTH_INVALID"
    AUTH_EXPIRED = "AUTH_EXPIRED"
    AUTH_REVOKED = "AUTH_REVOKED"
    AUTH_OPERATOR_ACTION_REQUIRED = "AUTH_OPERATOR_ACTION_REQUIRED"
    REFRESHING = "REFRESHING"
    RATE_LIMITED = "RATE_LIMITED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    ERROR = "ERROR"


class FinvizCredentialSource(StrEnum):
    ENVIRONMENT = "ENVIRONMENT"
    WINDOWS_CREDENTIAL_MANAGER = "WINDOWS_CREDENTIAL_MANAGER"
    PROVIDER_ENV_FILE = "PROVIDER_ENV_FILE"
    NONE = "NONE"


class FinvizRecoveryMode(StrEnum):
    AUTO = "AUTO"
    MANUAL = "MANUAL"
    LOGIN_REQUIRED = "LOGIN_REQUIRED"
    UNAVAILABLE = "UNAVAILABLE"
