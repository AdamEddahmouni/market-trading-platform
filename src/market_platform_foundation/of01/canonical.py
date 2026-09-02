"""Deterministic canonicalization profiles for OF-01."""

from __future__ import annotations

from typing import Any, Mapping

from market_platform_foundation.canonical import canonical_bytes, sha256_bytes

from .errors import OF01Error, OF01ErrorCode

COMMAND_PROFILE = "imp-of01-command-canonical-json-v1"
RECORD_PROFILE = "imp-of01-record-canonical-json-v1"
COMMIT_PROFILE = "imp-of01-commit-canonical-json-v1"
HASH_PROFILE = "imp-sha256-uppercase-hex-v1"
CAS_LOCATOR_PROFILE = "imp-of01-local-cas-v1"

_PROFILES = frozenset({COMMAND_PROFILE, RECORD_PROFILE, COMMIT_PROFILE})


def sha256_upper(data: bytes) -> str:
    return sha256_bytes(data)


def _reject_unknown_keys(obj: Mapping[str, Any], allowed: frozenset[str], *, context: str) -> None:
    unknown = set(obj.keys()) - allowed
    if unknown:
        raise OF01Error(
            OF01ErrorCode.INVALID_COMMAND,
            f"unknown keys in {context}",
            {"unknown_keys": sorted(unknown), "context": context},
        )


def _canonicalize_value(value: Any, *, context: str) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if not (-(2**63) <= value < 2**63):
            raise OF01Error(
                OF01ErrorCode.INVALID_COMMAND,
                f"integer out of range in {context}",
                {"context": context},
            )
        return value
    if isinstance(value, float):
        raise OF01Error(
            OF01ErrorCode.INVALID_COMMAND,
            f"float prohibited in {context}",
            {"context": context},
        )
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return [_canonicalize_value(item, context=f"{context}[]") for item in value]
    if isinstance(value, dict):
        _reject_unknown_keys(value, frozenset(value.keys()), context=context)
        return {k: _canonicalize_value(v, context=f"{context}.{k}") for k, v in sorted(value.items())}
    raise OF01Error(
        OF01ErrorCode.INVALID_COMMAND,
        f"unsupported type in {context}",
        {"context": context, "type": type(value).__name__},
    )


def _build_canonical(mapping: Mapping[str, Any], *, profile: str, context: str) -> bytes:
    if profile not in _PROFILES and profile != HASH_PROFILE:
        raise OF01Error(
            OF01ErrorCode.INVALID_COMMAND,
            "unsupported canonicalization profile",
            {"profile": profile},
        )
    canonical_obj = _canonicalize_value(dict(mapping), context=context)
    return canonical_bytes(canonical_obj)


def canonical_command_bytes(command_obj: Mapping[str, Any]) -> bytes:
    return _build_canonical(command_obj, profile=COMMAND_PROFILE, context="command")


def canonical_record_bytes(record_obj: Mapping[str, Any]) -> bytes:
    return _build_canonical(record_obj, profile=RECORD_PROFILE, context="record")


def canonical_commit_bytes(commit_obj: Mapping[str, Any]) -> bytes:
    return _build_canonical(commit_obj, profile=COMMIT_PROFILE, context="commit")


def command_hash_from_obj(command_obj: Mapping[str, Any]) -> str:
    return sha256_upper(canonical_command_bytes(command_obj))


def record_hash_from_obj(record_obj: Mapping[str, Any]) -> str:
    return sha256_upper(canonical_record_bytes(record_obj))


def commit_hash_from_obj(commit_obj: Mapping[str, Any]) -> str:
    return sha256_upper(canonical_commit_bytes(commit_obj))
