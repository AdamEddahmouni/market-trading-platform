"""Fail-closed hosting security configuration schema (Platformization P5).

Neutral, locally-executable prerequisites for a future hosted deployment
(PLATFORMIZATION_ROADMAP.md P5). This module is pure validation logic: it is
wired nowhere destructive today — the UI API still binds ``127.0.0.1`` with no
auth exactly as before. The schema exists so that the day the bind surface or
deployment topology changes, the safety parameters are already validated,
fail-closed, and documented rather than invented under time pressure.

Fail-closed defaults:

- Bind address allowlist is loopback-only (``127.0.0.1``, ``::1``,
  ``localhost``). A non-loopback bind requires BOTH an explicit opt-in flag
  AND an explicit external TLS-termination mode; otherwise validation raises.
- TLS termination is assumed to happen at a reverse proxy in front of the
  process (``TERMINATED_AT_REVERSE_PROXY``). The platform serves plain HTTP
  on loopback today and MUST NOT be exposed directly; any hosted variant
  must document its proxy/TLS posture through this config.
- Request body size is bounded (default 1 MiB) so a future write surface
  cannot inherit an unbounded read handler's assumptions.
- Rate-limit parameters are present and on by default for non-loopback binds;
  disabling rate limiting on a remotely-bindable config fails validation.

No wall clock, no network I/O, stdlib only.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from typing import Any, Mapping

SECURITY_CONFIG_SCHEMA = "platform/security-config/1.0.0"

ENV_PREFIX = "IMP_SEC_"

DEFAULT_BIND_HOST = "127.0.0.1"
DEFAULT_BIND_PORT = 8766

LOOPBACK_BIND_HOSTS: frozenset[str] = frozenset(
    {"127.0.0.1", "::1", "localhost", "[::1]"}
)

TLS_TERMINATION_NONE = "NONE_LOCALHOST_PLAINTEXT"
TLS_TERMINATION_EXTERNAL = "TERMINATED_AT_REVERSE_PROXY"
TLS_TERMINATION_MODES: tuple[str, ...] = (
    TLS_TERMINATION_NONE,
    TLS_TERMINATION_EXTERNAL,
)

MIN_REQUEST_BODY_BYTES = 1024
MAX_REQUEST_BODY_BYTES_CEILING = 67_108_864  # 64 MiB hard ceiling
DEFAULT_MAX_REQUEST_BODY_BYTES = 1_048_576  # 1 MiB

_TRUTHY = frozenset({"1", "true", "yes", "on"})


class SecurityConfigError(ValueError):
    """Raised when hosting security configuration fails closed."""


@dataclass(frozen=True)
class RateLimitParameters:
    """Token-bucket-shaped rate-limit knobs (validation only, no enforcement)."""

    enabled: bool = True
    requests_per_window: int = 600
    window_seconds: int = 60
    burst_allowance: int = 60


@dataclass(frozen=True)
class HostingSecurityConfig:
    """Validated hosting-relevant security configuration."""

    bind_host: str = DEFAULT_BIND_HOST
    bind_port: int = DEFAULT_BIND_PORT
    tls_termination: str = TLS_TERMINATION_NONE
    allow_non_loopback_bind: bool = False
    max_request_body_bytes: int = DEFAULT_MAX_REQUEST_BODY_BYTES
    rate_limit: RateLimitParameters = RateLimitParameters()

    def validate(self) -> tuple[str, ...]:
        """Return sorted error codes; empty tuple means the config passes.

        Fail-closed rules (P5 spec §4):
        - bind host must be loopback unless explicitly allowed;
        - non-loopback bind requires external TLS termination AND rate limiting;
        - body-size bound must exist and sit inside sane bounds;
        - rate-limit integers must be positive where meaningful.
        """

        errors: list[str] = []
        if self.bind_port < 1 or self.bind_port > 65535:
            errors.append("BIND_PORT_OUT_OF_RANGE")
        loopback = self.bind_host.lower() in LOOPBACK_BIND_HOSTS
        if not loopback:
            if not self.allow_non_loopback_bind:
                errors.append("NON_LOOPBACK_BIND_NOT_ALLOWED")
            if self.tls_termination != TLS_TERMINATION_EXTERNAL:
                errors.append("NON_LOOPBACK_REQUIRES_TLS_TERMINATION")
            if not self.rate_limit.enabled:
                errors.append("NON_LOOPBACK_REQUIRES_RATE_LIMIT")
        if self.tls_termination not in TLS_TERMINATION_MODES:
            errors.append("UNKNOWN_TLS_TERMINATION_MODE")
        if (
            self.max_request_body_bytes < MIN_REQUEST_BODY_BYTES
            or self.max_request_body_bytes > MAX_REQUEST_BODY_BYTES_CEILING
        ):
            errors.append("MAX_REQUEST_BODY_BYTES_OUT_OF_RANGE")
        if self.rate_limit.requests_per_window <= 0:
            errors.append("RATE_LIMIT_REQUESTS_MUST_BE_POSITIVE")
        if self.rate_limit.window_seconds <= 0:
            errors.append("RATE_LIMIT_WINDOW_MUST_BE_POSITIVE")
        if self.rate_limit.burst_allowance < 0:
            errors.append("RATE_LIMIT_BURST_MUST_BE_NON_NEGATIVE")
        return tuple(sorted(errors))

    def validated(self) -> "HostingSecurityConfig":
        """Return self if valid, else raise :class:`SecurityConfigError`."""

        errors = self.validate()
        if errors:
            raise SecurityConfigError(
                f"{SECURITY_CONFIG_SCHEMA} rejected: {', '.join(errors)}"
            )
        return self


def _parse_bool(raw: str | None) -> bool:
    """Fail-closed boolean parse: only explicit truthy strings are True."""

    if raw is None:
        return False
    return raw.strip().lower() in _TRUTHY


def _parse_int(name: str, raw: str | None, default: int) -> int:
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError as exc:
        raise SecurityConfigError(f"{name} is not an integer: {raw!r}") from exc


def parse_security_config(values: Mapping[str, str]) -> HostingSecurityConfig:
    """Build a :class:`HostingSecurityConfig` from string key/values.

    Unknown keys are ignored (forward compatibility); malformed values raise
    :class:`SecurityConfigError` instead of being silently coerced.
    """

    def get(suffix: str) -> str | None:
        return values.get(ENV_PREFIX + suffix)

    tls_raw = get("TLS_TERMINATION")
    if tls_raw is not None and tls_raw.strip() != "":
        tls_mode = tls_raw.strip().upper()
        if tls_mode not in TLS_TERMINATION_MODES:
            raise SecurityConfigError(
                f"{ENV_PREFIX}TLS_TERMINATION must be one of "
                f"{', '.join(TLS_TERMINATION_MODES)}; got {tls_raw!r}"
            )
    else:
        tls_mode = TLS_TERMINATION_NONE

    rate_enabled_raw = get("RATE_LIMIT_ENABLED")
    rate_enabled = (
        _parse_bool(rate_enabled_raw) if rate_enabled_raw is not None else True
    )
    rate_limit = RateLimitParameters(
        enabled=rate_enabled,
        requests_per_window=_parse_int(
            f"{ENV_PREFIX}RATE_LIMIT_REQUESTS_PER_WINDOW",
            get("RATE_LIMIT_REQUESTS_PER_WINDOW"),
            RateLimitParameters.requests_per_window,
        ),
        window_seconds=_parse_int(
            f"{ENV_PREFIX}RATE_LIMIT_WINDOW_SECONDS",
            get("RATE_LIMIT_WINDOW_SECONDS"),
            RateLimitParameters.window_seconds,
        ),
        burst_allowance=_parse_int(
            f"{ENV_PREFIX}RATE_LIMIT_BURST_ALLOWANCE",
            get("RATE_LIMIT_BURST_ALLOWANCE"),
            RateLimitParameters.burst_allowance,
        ),
    )

    host_raw = get("BIND_HOST")
    bind_host = host_raw.strip() if host_raw else DEFAULT_BIND_HOST
    return HostingSecurityConfig(
        bind_host=bind_host,
        bind_port=_parse_int(
            f"{ENV_PREFIX}BIND_PORT", get("BIND_PORT"), DEFAULT_BIND_PORT
        ),
        tls_termination=tls_mode,
        allow_non_loopback_bind=_parse_bool(get("ALLOW_NON_LOOPBACK")),
        max_request_body_bytes=_parse_int(
            f"{ENV_PREFIX}MAX_BODY_BYTES",
            get("MAX_BODY_BYTES"),
            DEFAULT_MAX_REQUEST_BODY_BYTES,
        ),
        rate_limit=rate_limit,
    )


def load_security_config(env: Mapping[str, str] | None = None) -> HostingSecurityConfig:
    """Parse and validate from an env mapping (default ``os.environ``).

    Raises :class:`SecurityConfigError` on any invalid value — callers fail
    closed rather than starting with a weaker-than-defaults posture.
    """

    source = os.environ if env is None else env
    selected = {
        key: value
        for key, value in source.items()
        if isinstance(key, str) and key.startswith(ENV_PREFIX)
    }
    return parse_security_config(selected).validated()


def with_overrides(
    base: HostingSecurityConfig, **changes: Any
) -> HostingSecurityConfig:
    """Return a validated copy with dataclass ``replace`` overrides."""

    return replace(base, **changes).validated()
