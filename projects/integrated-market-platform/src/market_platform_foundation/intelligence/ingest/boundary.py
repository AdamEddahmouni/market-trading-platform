"""Ingest boundary guards shared by HTTP adapters and tests."""

from __future__ import annotations

import os
import re
from typing import Any

from ..contracts.agent_ingest import (
    AgentBotRole,
    AgentClaimType,
    AgentEnrichmentEvidenceV1,
)
from ...platform.security.auth_config import AuthEnforcementMode, load_auth_config

AGENT_ENRICHMENT_INGEST_MAX_BODY_BYTES = 65_536
AGENT_ENRICHMENT_MAX_SOURCE_REFS = 32
AGENT_ENRICHMENT_MAX_SOURCE_URL_LENGTH = 2_048
AGENT_ENRICHMENT_MAX_CLAIM_BODY_TEXT_CHARS = 16_384
AGENT_ENRICHMENT_MAX_CONTRADICTION_REFS = 64
AGENT_ENRICHMENT_MAX_METADATA_DEPTH = 8
AGENT_ENRICHMENT_MAX_METADATA_ENTRIES = 64
AGENT_ENRICHMENT_MAX_PROVENANCE_DEPTH = 6
AGENT_ENRICHMENT_MAX_PROVENANCE_ENTRIES = 32

_AGENT_ENRICHMENT_PERSISTENCE_METHODS = (
    "put_agent_enrichment_evidence",
    "get_agent_enrichment_evidence",
    "list_agent_enrichment_by_opportunity",
)

_AGENT_ID_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9._-]{0,127}$")

_PROVENANCE_FORBIDDEN_KEYS = frozenset(
    {
        "secret",
        "password",
        "api_key",
        "apikey",
        "token",
        "credential",
        "credentials",
        "authorization",
        "private_key",
    }
)

_CLAIM_TYPE_ALLOWED_ROLES: dict[AgentClaimType, frozenset[AgentBotRole]] = {
    AgentClaimType.SUPPORTING_EVIDENCE: frozenset({AgentBotRole.SENTINEL, AgentBotRole.AUDITOR}),
    AgentClaimType.VERIFICATION: frozenset({AgentBotRole.SENTINEL, AgentBotRole.AUDITOR}),
    AgentClaimType.SOURCE_ATTRIBUTION: frozenset({AgentBotRole.RESEARCH_SCOUT}),
    AgentClaimType.CONTRADICTION: frozenset({AgentBotRole.SKEPTIC, AgentBotRole.SENTINEL}),
    AgentClaimType.CHALLENGE: frozenset({AgentBotRole.SKEPTIC}),
    AgentClaimType.CROWD_CONTEXT: frozenset({AgentBotRole.CROWD_WATCH}),
    AgentClaimType.HYPOTHESIS_SUGGESTION: frozenset(
        {AgentBotRole.RESEARCH_SCOUT, AgentBotRole.COORDINATOR}
    ),
}

_ALLOWED_URL_SCHEMES = frozenset({"http", "https"})


def enforce_agent_enrichment_body_limit(content_length: int) -> None:
    if content_length < 0:
        raise ValueError("AGENT_ENRICHMENT_CONTENT_LENGTH_INVALID")
    if content_length > AGENT_ENRICHMENT_INGEST_MAX_BODY_BYTES:
        raise ValueError("AGENT_ENRICHMENT_BODY_TOO_LARGE")


def resolve_agent_enrichment_persistence(strategy_repository: Any) -> Any:
    if strategy_repository is None:
        raise ValueError("AGENT_ENRICHMENT_REPOSITORY_UNAVAILABLE")
    for method_name in _AGENT_ENRICHMENT_PERSISTENCE_METHODS:
        if not callable(getattr(strategy_repository, method_name, None)):
            raise ValueError("AGENT_ENRICHMENT_REPOSITORY_UNSUPPORTED")
    return strategy_repository


def enforce_intelligence_ingest_auth_posture() -> None:
    """Fail closed when operators require ENFORCED auth for external agent ingest."""

    flag = os.environ.get("IMP_INTELLIGENCE_INGEST_REQUIRE_ENFORCED", "").strip().lower()
    if flag not in {"1", "true", "yes"}:
        return
    config = load_auth_config()
    if config.enforcement_mode != AuthEnforcementMode.ENFORCED:
        raise ValueError("INTELLIGENCE_INGEST_LOOPBACK_TRUST_FORBIDDEN")


def _dict_depth(value: Any, *, depth: int = 0, max_depth: int) -> int:
    if depth > max_depth:
        raise ValueError("INGEST_PAYLOAD_TOO_DEEP")
    if not isinstance(value, dict):
        return depth
    deepest = depth
    for child in value.values():
        if isinstance(child, dict):
            deepest = max(deepest, _dict_depth(child, depth=depth + 1, max_depth=max_depth))
        elif isinstance(child, list):
            for item in child:
                if isinstance(item, dict):
                    deepest = max(deepest, _dict_depth(item, depth=depth + 1, max_depth=max_depth))
    return deepest


def _validate_metadata_container(value: Any, *, field_name: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name}_INVALID")
    if len(value) > AGENT_ENRICHMENT_MAX_METADATA_ENTRIES:
        raise ValueError(f"{field_name}_TOO_LARGE")
    if _dict_depth(value, max_depth=AGENT_ENRICHMENT_MAX_METADATA_DEPTH) > AGENT_ENRICHMENT_MAX_METADATA_DEPTH:
        raise ValueError("INGEST_PAYLOAD_TOO_DEEP")


def _validate_provenance(provenance: Any) -> None:
    if not isinstance(provenance, dict) or not provenance:
        raise ValueError("INGEST_PROVENANCE_REQUIRED")
    if len(provenance) > AGENT_ENRICHMENT_MAX_PROVENANCE_ENTRIES:
        raise ValueError("INGEST_PROVENANCE_TOO_LARGE")
    if _dict_depth(provenance, max_depth=AGENT_ENRICHMENT_MAX_PROVENANCE_DEPTH) > AGENT_ENRICHMENT_MAX_PROVENANCE_DEPTH:
        raise ValueError("INGEST_PAYLOAD_TOO_DEEP")
    for key in provenance:
        lowered = str(key).lower()
        if lowered in _PROVENANCE_FORBIDDEN_KEYS:
            raise ValueError("INGEST_PROVENANCE_SECRET_FIELD_FORBIDDEN")
    if not any(provenance.get(field) for field in ("ingest_plane", "source", "worker_id")):
        raise ValueError("INGEST_PROVENANCE_SOURCE_REQUIRED")


def _validate_url_like_reference(value: str) -> None:
    text = str(value).strip()
    if not text:
        return
    if len(text) > AGENT_ENRICHMENT_MAX_SOURCE_URL_LENGTH:
        raise ValueError("INGEST_SOURCE_REF_URL_TOO_LONG")
    normalized = text.replace("\\", "/")
    if ".." in normalized:
        raise ValueError("INGEST_SOURCE_REF_PATH_TRAVERSAL")
    lower = text.lower()
    if lower.startswith("file:") or lower.startswith("data:"):
        raise ValueError("INGEST_SOURCE_REF_SCHEME_FORBIDDEN")
    if lower.startswith("\\\\") or (len(text) > 1 and text[1] == ":" and text[0].isalpha()):
        raise ValueError("INGEST_SOURCE_REF_LOCAL_PATH_FORBIDDEN")
    if "://" in text:
        scheme = text.split("://", 1)[0].lower()
        if scheme not in _ALLOWED_URL_SCHEMES:
            raise ValueError("INGEST_SOURCE_REF_URL_SCHEME_FORBIDDEN")


def _validate_source_ref_dict(ref: Any) -> None:
    if not isinstance(ref, dict):
        raise ValueError("INGEST_SOURCE_REF_INVALID")
    for field in ("raw_reference", "external_id"):
        raw = ref.get(field)
        if raw is not None:
            _validate_url_like_reference(str(raw))


def _claim_body_text_length(claim_body: Any) -> int:
    if not isinstance(claim_body, dict):
        return 0
    total = 0
    for key, value in claim_body.items():
        total += len(str(key))
        if isinstance(value, str):
            total += len(value)
        elif isinstance(value, (int, float, bool)):
            total += len(str(value))
        elif isinstance(value, dict):
            total += _claim_body_text_length(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    total += len(item)
                elif isinstance(item, dict):
                    total += _claim_body_text_length(item)
    return total


def validate_agent_id_for_ingest(agent_id: str) -> None:
    text = str(agent_id).strip()
    if not text or not _AGENT_ID_PATTERN.fullmatch(text):
        raise ValueError("INGEST_AGENT_ID_INVALID")


def validate_agent_enrichment_ingest_payload(payload: dict[str, Any]) -> None:
    """Structural limits on raw ingest JSON before contract deserialization."""

    if not isinstance(payload, dict):
        raise ValueError("INGEST_PAYLOAD_INVALID")
    validate_agent_id_for_ingest(str(payload.get("agent_id") or ""))
    _validate_provenance(payload.get("provenance"))
    _validate_metadata_container(payload.get("metadata") or {}, field_name="METADATA")
    _validate_metadata_container(payload.get("claim_body") or {}, field_name="CLAIM_BODY")
    _validate_metadata_container(payload.get("crowd_context") or {}, field_name="CROWD_CONTEXT")
    if _claim_body_text_length(payload.get("claim_body") or {}) > AGENT_ENRICHMENT_MAX_CLAIM_BODY_TEXT_CHARS:
        raise ValueError("INGEST_CLAIM_BODY_TOO_LARGE")
    source_refs = payload.get("source_refs") or []
    if not isinstance(source_refs, list):
        raise ValueError("INGEST_SOURCE_REFS_INVALID")
    if len(source_refs) > AGENT_ENRICHMENT_MAX_SOURCE_REFS:
        raise ValueError("INGEST_SOURCE_REFS_TOO_MANY")
    for ref in source_refs:
        _validate_source_ref_dict(ref)
    contradiction_refs = payload.get("contradiction_refs") or []
    if not isinstance(contradiction_refs, list):
        raise ValueError("INGEST_CONTRADICTION_REFS_INVALID")
    if len(contradiction_refs) > AGENT_ENRICHMENT_MAX_CONTRADICTION_REFS:
        raise ValueError("INGEST_CONTRADICTION_REFS_TOO_MANY")


def validate_agent_enrichment_record_policy(record: AgentEnrichmentEvidenceV1) -> None:
    """Agent identity and role alignment after typed deserialization."""

    validate_agent_id_for_ingest(record.agent_id)
    allowed_roles = _CLAIM_TYPE_ALLOWED_ROLES.get(record.claim_type)
    if allowed_roles is not None and record.bot_role not in allowed_roles:
        raise ValueError("INGEST_BOT_ROLE_CLAIM_MISMATCH")


__all__ = [
    "AGENT_ENRICHMENT_INGEST_MAX_BODY_BYTES",
    "AGENT_ENRICHMENT_MAX_CLAIM_BODY_TEXT_CHARS",
    "AGENT_ENRICHMENT_MAX_CONTRADICTION_REFS",
    "AGENT_ENRICHMENT_MAX_METADATA_DEPTH",
    "AGENT_ENRICHMENT_MAX_SOURCE_REFS",
    "AGENT_ENRICHMENT_MAX_SOURCE_URL_LENGTH",
    "enforce_agent_enrichment_body_limit",
    "enforce_intelligence_ingest_auth_posture",
    "resolve_agent_enrichment_persistence",
    "validate_agent_enrichment_ingest_payload",
    "validate_agent_enrichment_record_policy",
    "validate_agent_id_for_ingest",
]
