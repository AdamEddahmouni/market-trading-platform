"""Neutral security foundations for a future hosted platform (Platformization P5).

Locally-executable, stdlib-only prerequisites: fail-closed hosting config
schema, log/payload redaction, secret-leak audit, deterministic readiness
payloads, and the operator roles model. Nothing here is enforced on the
current localhost surface — see docs/superpowers/specs/
2026-08-22-platform-p5-hosted-security-foundations-design.md.
"""

from .config import (
    DEFAULT_BIND_HOST,
    DEFAULT_BIND_PORT,
    DEFAULT_MAX_REQUEST_BODY_BYTES,
    LOOPBACK_BIND_HOSTS,
    SECURITY_CONFIG_SCHEMA,
    TLS_TERMINATION_EXTERNAL,
    TLS_TERMINATION_MODES,
    TLS_TERMINATION_NONE,
    HostingSecurityConfig,
    RateLimitParameters,
    SecurityConfigError,
    load_security_config,
    parse_security_config,
    with_overrides,
)
from .readiness import (
    READINESS_SCHEMA,
    READYNESS_STATUSES,
    STATUS_NOT_READY,
    STATUS_READY,
    build_readiness_payload,
    collect_default_gates,
    render_readiness_json,
)
from .redaction import (
    REDACTED,
    SECRET_KEY_MARKERS,
    build_log_line,
    is_secret_key,
    normalize_key,
    redact_log_line,
    redact_mapping,
)
from .roles import (
    CAPABILITIES,
    ROLE_ENFORCEMENT_STATUS,
    ROLE_MODEL_SCHEMA,
    OPERATOR_ROLES,
    OperatorRole,
    RoleModelError,
    ROLE_CAPABILITY_MATRIX,
    assert_matrix_invariants,
    capabilities_for_role,
    role_allows,
)
from .leak_audit import (
    PLACEHOLDER_VALUES,
    SECRET_AUDIT_SCHEMA,
    SecretFinding,
    SecretLeakError,
    assert_no_secrets_in_payload,
    audit_text,
    scan_snapshot,
)

__all__ = [
    "CAPABILITIES",
    "DEFAULT_BIND_HOST",
    "DEFAULT_BIND_PORT",
    "DEFAULT_MAX_REQUEST_BODY_BYTES",
    "LOOPBACK_BIND_HOSTS",
    "OPERATOR_ROLES",
    "PLACEHOLDER_VALUES",
    "READINESS_SCHEMA",
    "READYNESS_STATUSES",
    "REDACTED",
    "ROLE_CAPABILITY_MATRIX",
    "ROLE_ENFORCEMENT_STATUS",
    "ROLE_MODEL_SCHEMA",
    "SECURITY_CONFIG_SCHEMA",
    "SECRET_AUDIT_SCHEMA",
    "SECRET_KEY_MARKERS",
    "STATUS_NOT_READY",
    "STATUS_READY",
    "TLS_TERMINATION_EXTERNAL",
    "TLS_TERMINATION_MODES",
    "TLS_TERMINATION_NONE",
    "HostingSecurityConfig",
    "OperatorRole",
    "RateLimitParameters",
    "RoleModelError",
    "SecretFinding",
    "SecretLeakError",
    "SecurityConfigError",
    "assert_matrix_invariants",
    "assert_no_secrets_in_payload",
    "audit_text",
    "build_log_line",
    "build_readiness_payload",
    "capabilities_for_role",
    "collect_default_gates",
    "is_secret_key",
    "load_security_config",
    "normalize_key",
    "parse_security_config",
    "redact_log_line",
    "redact_mapping",
    "render_readiness_json",
    "role_allows",
    "scan_snapshot",
    "with_overrides",
]
