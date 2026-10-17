"""Secret-leak audit for config snapshots, payloads, and log text (P5).

Extends the value-blind patterns of :mod:`market_platform_foundation.credential_audit`
to runtime objects: given a config dict or env snapshot, find secret-shaped
keys holding non-placeholder values; given a rendered payload/log line, run
the governed ``SECRET_SCAN_RULES`` regexes and fail loudly on a match.

Structural matching is primarily **name-based** (``is_secret_key`` markers such
as ``token`` / ``key`` / ``auth``). A narrow name+value-shape allowlist treats
public operator metadata as benign when values are uppercase policy enums
(``credential_state``, ``status_token``, ``boundary_token``, …) or documented
non-secret shapes (config ``fields[n].key`` env identifiers, ``backend_authority``
module paths). Live secret-bearing values remain blocked.

Findings never carry the secret value — only the path/rule id and a short
SHA-256 fingerprint prefix so two findings can be correlated without
disclosing material.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping

from ...credential_audit import SECRET_SCAN_RULES
from .redaction import is_secret_key, normalize_key

SECRET_AUDIT_SCHEMA = "platform/secret-audit/1.0.0"

# Operational field names that contain secret-shaped substrings but are not credentials.
# Name-only allowlist for stable public authority / idempotency metadata (not secret values).
BENIGN_SECRET_SHAPED_KEYS: frozenset[str] = frozenset(
    normalize_key(name)
    for name in (
        "idempotency_key",
        "execution_authority",
        "execution_authority_after_arm",
        "authority_boundary",
        "analytics_authority",
        "research_context_execution_authority",
    )
)

# Public policy / resilience status fields whose *names* contain ``token`` but whose
# values are uppercase enum constants (OPEND_UNAVAILABLE, FALLBACK_BLOCKED, …).
# Name match alone is not enough — values must also look like policy enums.
_PUBLIC_POLICY_TOKEN_KEYS: frozenset[str] = frozenset(
    normalize_key(name)
    for name in (
        "status_token",
        "boundary_token",
        "provider_status_token",
        "token_status",
    )
)

# Uppercase status / policy enums (credential_state, status_token, …).
_PUBLIC_POLICY_ENUM_VALUE_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,127}$")
# Backward-compatible alias used by older call sites / docs.
_CREDENTIAL_STATE_VALUE_RE = _PUBLIC_POLICY_ENUM_VALUE_RE

# Stable canary / control-plane ``backend_authority`` module paths, not credentials.
_BACKEND_AUTHORITY_VALUE_RE = re.compile(
    r"^[a-z][a-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+$"
)

# Operator config field descriptors use ``key`` for env-var identifiers only.
_CONFIG_FIELD_DESCRIPTOR_KEY_PATH_RE = re.compile(r"fields\[\d+\]\.key$")
_ENV_VAR_IDENTIFIER_RE = re.compile(r"^[A-Z][A-Z0-9]*(_[A-Z0-9]+)+$")

PLACEHOLDER_VALUES: frozenset[str] = frozenset(
    {"", "CHANGEME", "EXAMPLE", "PLACEHOLDER", "NOT_A_SECRET"}
)

# Language-model usage counters (synthesis budget, per-call usage). Their names contain
# ``token`` but they count tokens; only whole-number values are benign, so a string
# (a live credential) under the same name is still blocked.
_MODEL_TOKEN_COUNT_KEYS: frozenset[str] = frozenset(
    normalize_key(name)
    for name in (
        "tokens",
        "max_tokens",
        "input_tokens",
        "output_tokens",
        "prompt_tokens",
        "reserved_tokens",
        "tokens_input",
        "tokens_output",
        "total_tokens_input",
        "worst_case_tokens",
        # Full-universe AI Screener plan and shared-budget hold counters.
        "required_tokens",
        "available_tokens",
        "held_tokens",
        "planned_tokens",
        "batch_tokens",
        "batch_tokens_max",
        "largest_batch_tokens",
        "reduction_tokens",
        "reserved_output_tokens",
        "estimated_input_tokens",
        "actual_input_tokens",
        "actual_output_tokens",
        "actual_tokens",
        "estimated_total_tokens",
        "expected_input_tokens",
        "reserved_batch_output_tokens",
        "reserved_output_tokens_total",
        "reserved_reasoning_tokens",
        "reserved_reasoning_tokens_total",
        "available_token_budget",
        # Exact local send-time counts: refused-before-generation input and the task's configured output maximum.
        "counted_not_sent_tokens",
        "configured_max_tokens",
        # AUTO-01 owner policy: the daily paid-inference allowance, a whole-number count.
        "max_paid_tokens_per_day",
    )
)

# Finviz diagnostics publish finite status enums and integer counters, never tokens.
_PUBLIC_FINVIZ_ENUMS = {
    "authentication": frozenset({"UNCONFIGURED", "LOADED", "VALIDATING", "HEALTHY", "AUTH_INVALID",
        "AUTH_EXPIRED", "AUTH_REVOKED", "AUTH_OPERATOR_ACTION_REQUIRED", "REFRESHING", "RATE_LIMITED",
        "PROVIDER_UNAVAILABLE", "ERROR"}),
    "credentialsource": frozenset({"ENVIRONMENT", "PRIVATE_FILE", "WINDOWS_CREDENTIAL_MANAGER", "PROVIDER_ENV_FILE", "NONE"}),
    "lastautherror": frozenset({"AUTH_OK", "AUTH_INVALID", "AUTH_EXPIRED", "AUTH_REVOKED", "SUBSCRIPTION_NOT_ELITE",
        "RATE_LIMITED", "NETWORK_ERROR", "PROVIDER_ERROR", "UNKNOWN", "REFRESHED", "MANUAL_AUTH_REQUIRED",
        "INVALID_EXPORT", "CONFIG_MISSING", "AUTH_FAILED", "TOKEN_NOT_FOUND", "DEPENDENCY_MISSING",
        "REDIRECT_REJECTED", "LOGIN_CREDENTIALS_MISSING", "MFA_OR_CAPTCHA"}),
}
_PUBLIC_FINVIZ_COUNTERS = frozenset({"finvizcredentialgeneration", "authrecoveries"})

# Exact public source assignments from the Finviz health authority matrix.
# Both the full response path and its field/value pair must match; generic
# authority fields and unknown assignments continue to fail closed.
_PUBLIC_FINVIZ_SOURCE_AUTHORITIES = {
    "broad_screening": "FINVIZ_ELITE",
    "candidate_discovery": "FINVIZ_ELITE",
    "fundamental_snapshot": "FINVIZ_ELITE",
    "technical_screening": "FINVIZ_ELITE",
    "relative_volume": "FINVIZ_ELITE",
    "short_float_discovery": "FINVIZ_ELITE",
    "official_short_interest": "FINRA",
    "threshold_status": "OFFICIAL_REGSHO",
    "fail_to_deliver": "SEC",
    "sec_filings": "SEC_EDGAR",
    "filing_discovery_alert": "FINVIZ_ELITE",
    "news_discovery": "FINVIZ_ELITE",
    "original_news": "ORIGINAL_PUBLISHER",
    "insider_discovery": "FINVIZ_ELITE",
    "insider_filing_truth": "SEC",
    "analyst_events": "FINVIZ_ELITE",
    "sector_industry_breadth": "FINVIZ_ELITE",
    "etf_holdings": "FINVIZ_ELITE",
    "live_bbo": "MOOMOO",
    "live_trades": "MOOMOO",
    "l2_depth": "MOOMOO",
    "cvd": "IMP_DERIVED",
    "internal_fill": "EXECUTION_ADMITTED",
    "execution": "INTERNAL",
}

_FINGERPRINT_HEX_CHARS = 12


class SecretLeakError(AssertionError):
    """Raised when a secret-shaped value reaches a log/response surface."""


@dataclass(frozen=True)
class SecretFinding:
    """A secret-shaped key with non-placeholder content. Never holds the value."""

    path: str
    reason: str
    fingerprint: str


def _fingerprint(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return digest[:_FINGERPRINT_HEX_CHARS].upper()


def _is_public_credential_state_field(key: str, value: Any) -> bool:
    return (
        normalize_key(key) == "credentialstate"
        and isinstance(value, str)
        and bool(_PUBLIC_POLICY_ENUM_VALUE_RE.fullmatch(value.strip()))
    )


def _is_public_policy_token_field(key: str, value: Any) -> bool:
    """True for resilience/safety token *names* holding uppercase policy enums only.

    Matches NAMES that contain ``token`` (via :func:`is_secret_key`) only when the
    VALUE is a documented public constant shape — never a live credential.
    """

    if normalize_key(key) not in _PUBLIC_POLICY_TOKEN_KEYS:
        return False
    if not isinstance(value, str):
        return False
    return bool(_PUBLIC_POLICY_ENUM_VALUE_RE.fullmatch(value.strip()))


def _is_backend_authority_module_path(key: str, value: Any) -> bool:
    """``backend_authority`` holds dotted public module paths, not bearer secrets."""

    if normalize_key(key) != "backendauthority":
        return False
    if not isinstance(value, str):
        return False
    return bool(_BACKEND_AUTHORITY_VALUE_RE.fullmatch(value.strip()))


def _is_operator_config_field_descriptor_key(path: str, key: str, value: Any) -> bool:
    """``fields[n].key`` holds env-var names in operator config, not secret values."""

    if normalize_key(key) != "key":
        return False
    if not _CONFIG_FIELD_DESCRIPTOR_KEY_PATH_RE.search(path):
        return False
    if not isinstance(value, str):
        return False
    return bool(_ENV_VAR_IDENTIFIER_RE.fullmatch(value.strip()))


def _is_model_token_count(key: str, value: Any) -> bool:
    """LLM token counters hold whole numbers; never strings, floats or booleans."""

    return (
        normalize_key(key) in _MODEL_TOKEN_COUNT_KEYS
        and isinstance(value, int)
        and not isinstance(value, bool)
    )


def _is_finviz_matrix_authority_path(segments: tuple[str | int, ...]) -> bool:
    """Only the standalone and aggregate provider-health response structures."""
    if len(segments) == 5 and segments[0] == "finviz":
        segments = segments[1:]
    return (
        len(segments) == 4 and segments[:2] == ("authority", "matrix")
        and segments[-1] == "authority"
    )


def _structural_secret_key_is_benign(
    path: str, key: str, value: Any, *, segments: tuple[str | int, ...] = (),
) -> bool:
    normalized = normalize_key(str(key))
    if (
        _is_finviz_matrix_authority_path(segments) and isinstance(value, str)
        and _PUBLIC_FINVIZ_SOURCE_AUTHORITIES.get(segments[-2]) == value
    ):
        return True
    if normalized in _PUBLIC_FINVIZ_ENUMS and isinstance(value, str) and value in _PUBLIC_FINVIZ_ENUMS[normalized]:
        return True
    if normalized in _PUBLIC_FINVIZ_COUNTERS and type(value) is int and value >= 0:
        return True
    if normalized in BENIGN_SECRET_SHAPED_KEYS:
        return True
    if _is_model_token_count(str(key), value):
        return True
    if _is_public_credential_state_field(str(key), value):
        return True
    if _is_public_policy_token_field(str(key), value):
        return True
    if _is_backend_authority_module_path(str(key), value):
        return True
    if _is_operator_config_field_descriptor_key(path, str(key), value):
        return True
    return False


def scan_snapshot(
    snapshot: Any,
    *,
    path: str = "",
    _segments: tuple[str | int, ...] | None = None,
) -> tuple[SecretFinding, ...]:
    """Scan a config dict / env snapshot recursively for live secrets.

    A finding is recorded when a secret-shaped key holds a non-empty string
    that is not a documented placeholder. Values are fingerprinted, never
    returned. Env-style flat mappings (``IMP_TRADIER_TOKEN=...``) are just
    dicts and scan identically to nested config.
    """

    findings: list[SecretFinding] = []
    segments = (() if not path else (path,)) if _segments is None else _segments
    if isinstance(snapshot, Mapping):
        for key, value in snapshot.items():
            name = key if type(key) is str else str(key)
            if not isinstance(value, (Mapping, list, tuple)):
                # A scalar has no children, so its path is built only to report a finding.
                if not is_secret_key(name):
                    continue
                child_segments = (*segments, name)
                child_path = f"{path}.{key}" if path else str(key)
                if _structural_secret_key_is_benign(child_path, name, value, segments=child_segments):
                    continue
                if _is_finviz_matrix_authority_path(child_segments):
                    findings.append(SecretFinding(
                        path=child_path, reason="UNSUPPORTED_PUBLIC_AUTHORITY_ASSIGNMENT",
                        fingerprint=_fingerprint(str(value))))
                elif isinstance(value, str) and value.strip().upper() not in PLACEHOLDER_VALUES:
                    findings.append(SecretFinding(
                        path=child_path,
                        reason="SECRET_SHAPED_KEY_WITH_LIVE_VALUE",
                        fingerprint=_fingerprint(value),
                    ))
                elif isinstance(value, (int, float)) and not isinstance(value, bool):
                    findings.append(SecretFinding(
                        path=child_path,
                        reason="SECRET_SHAPED_KEY_WITH_NON_STRING_VALUE",
                        fingerprint=_fingerprint(str(value)),
                    ))
                continue
            child_path = f"{path}.{key}" if path else str(key)
            child_segments = (*segments, name)
            if is_secret_key(name) and not _structural_secret_key_is_benign(
                child_path, name, value, segments=child_segments
            ):
                if _is_finviz_matrix_authority_path(child_segments):
                    findings.append(SecretFinding(
                        path=child_path, reason="UNSUPPORTED_PUBLIC_AUTHORITY_ASSIGNMENT",
                        fingerprint=_fingerprint(str(value)),
                    ))
                elif isinstance(value, str) and value.strip().upper() not in PLACEHOLDER_VALUES:
                    findings.append(
                        SecretFinding(
                            path=child_path,
                            reason="SECRET_SHAPED_KEY_WITH_LIVE_VALUE",
                            fingerprint=_fingerprint(value),
                        )
                    )
                elif isinstance(value, (int, float)) and not isinstance(value, bool):
                    findings.append(
                        SecretFinding(
                            path=child_path,
                            reason="SECRET_SHAPED_KEY_WITH_NON_STRING_VALUE",
                            fingerprint=_fingerprint(str(value)),
                        )
                    )
            findings.extend(scan_snapshot(value, path=child_path, _segments=child_segments))
    elif isinstance(snapshot, (list, tuple)):
        for index, item in enumerate(snapshot):
            findings.extend(scan_snapshot(item, path=f"{path}[{index}]", _segments=(*segments, index)))
    return tuple(findings)


def audit_text(text: str) -> tuple[str, ...]:
    """Run governed ``credential_audit.SECRET_SCAN_RULES`` against text.

    Returns sorted rule ids that matched; empty means clean.
    """

    matched = []
    for rule_id, pattern in SECRET_SCAN_RULES.items():
        if re.search(pattern, text):
            matched.append(rule_id)
    return tuple(sorted(matched))


def assert_no_secrets_in_payload(payload: Any, *, context: str = "payload") -> None:
    """Fail closed if a payload would leak secrets to logs/responses.

    Checks both structural (secret-shaped keys with live values in dict
    payloads) and textual shapes (rendered JSON scanned by the governed
    rules). Raises :class:`SecretLeakError` naming paths/rule ids only.
    """

    findings = scan_snapshot(payload)
    textual_rules: tuple[str, ...] = ()
    try:
        rendered = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        rendered = ""
    if rendered:
        textual_rules = audit_text(rendered)
    problems: list[str] = [
        f"{finding.path}:{finding.reason}" for finding in findings
    ] + [f"RULE:{rule_id}" for rule_id in textual_rules]
    if problems:
        raise SecretLeakError(
            f"{context} would disclose secrets: {', '.join(sorted(problems))}"
        )
