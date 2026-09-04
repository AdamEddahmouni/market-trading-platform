"""Deterministic OF-03 canonicalization profiles."""

from __future__ import annotations

from typing import Any, Mapping

from market_platform_foundation.canonical import canonical_bytes, sha256_bytes

from .errors import OF03Error, OF03ErrorCode

DEFINITION_PROFILE = "imp-of03-definition-canonical-json-v1"
SNAPSHOT_PROFILE = "imp-of03-registry-snapshot-canonical-json-v1"
HASH_PROFILE = "imp-sha256-uppercase-hex-v1"
SCHEMA_VERSION = 1

_EXCLUDED_FROM_DEFINITION_HASH = frozenset({"definition_hash", "document_section_hash"})


def sha256_upper(data: bytes) -> str:
    return sha256_bytes(data)


def canonicalize_value(value: Any, *, context: str) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if not (-(2**63) <= value < 2**63):
            raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, f"integer out of range in {context}", {"context": context})
        return value
    if isinstance(value, float):
        raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, f"float prohibited in {context}", {"context": context})
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return [canonicalize_value(item, context=f"{context}[]") for item in value]
    if isinstance(value, dict):
        return {k: canonicalize_value(v, context=f"{context}.{k}") for k, v in sorted(value.items())}
    raise OF03Error(
        OF03ErrorCode.REGISTRY_INVALID,
        f"unsupported type in {context}",
        {"context": context, "type": type(value).__name__},
    )


def definition_canonical_obj(mapping: Mapping[str, Any]) -> dict[str, Any]:
    payload = {k: v for k, v in mapping.items() if k not in _EXCLUDED_FROM_DEFINITION_HASH}
    payload["definition_canonicalization_profile"] = DEFINITION_PROFILE
    payload["schema_version"] = int(payload.get("schema_version", SCHEMA_VERSION))
    return canonicalize_value(payload, context="definition")


def definition_hash_from_obj(mapping: Mapping[str, Any]) -> str:
    return sha256_upper(canonical_bytes(definition_canonical_obj(mapping)))


def snapshot_hash_from_obj(mapping: Mapping[str, Any]) -> str:
    obj = canonicalize_value(dict(mapping), context="snapshot")
    obj["snapshot_canonicalization_profile"] = SNAPSHOT_PROFILE
    return sha256_upper(canonical_bytes(canonicalize_value(obj, context="snapshot")))
