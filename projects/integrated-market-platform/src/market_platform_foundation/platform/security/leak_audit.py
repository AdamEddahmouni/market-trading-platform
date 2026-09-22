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


def _structural_secret_key_is_benign(path: str, key: str, value: Any) -> bool:
    normalized = normalize_key(str(key))
    if normalized in BENIGN_SECRET_SHAPED_KEYS:
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
) -> tuple[SecretFinding, ...]:
    """Scan a config dict / env snapshot recursively for live secrets.

    A finding is recorded when a secret-shaped key holds a non-empty string
    that is not a documented placeholder. Values are fingerprinted, never
    returned. Env-style flat mappings (``IMP_TRADIER_TOKEN=...``) are just
    dicts and scan identically to nested config.
    """

    findings: list[SecretFinding] = []
    if isinstance(snapshot, Mapping):
        for key, value in snapshot.items():
            child_path = f"{path}.{key}" if path else str(key)
            if is_secret_key(str(key)) and not _structural_secret_key_is_benign(
                child_path, str(key), value
            ):
                if isinstance(value, str) and value.strip().upper() not in PLACEHOLDER_VALUES:
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
            findings.extend(scan_snapshot(value, path=child_path))
    elif isinstance(snapshot, (list, tuple)):
        for index, item in enumerate(snapshot):
            findings.extend(scan_snapshot(item, path=f"{path}[{index}]"))
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
        rendered = json.dumps(payload, sort_keys=True, default=str)
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
