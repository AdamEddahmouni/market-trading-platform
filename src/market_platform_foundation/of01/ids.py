"""UUID and hash identity validation for OF-01."""

from __future__ import annotations

import re
import uuid

from .errors import OF01Error, OF01ErrorCode

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
_HASH_RE = re.compile(r"^[0-9A-F]{64}$")
_NIL_UUID = "00000000-0000-0000-0000-000000000000"


def new_uuid() -> str:
    return str(uuid.uuid4())


def validate_hash(value: str, *, field: str) -> str:
    if not isinstance(value, str) or not _HASH_RE.fullmatch(value):
        raise OF01Error(
            OF01ErrorCode.INVALID_COMMAND,
            f"invalid hash for {field}",
            {"field": field},
        )
    return value


def validate_uuid(
    value: str,
    *,
    field: str,
    allowed_versions: frozenset[int] = frozenset({4}),
) -> str:
    if not isinstance(value, str):
        raise OF01Error(
            OF01ErrorCode.INVALID_COMMAND,
            f"invalid UUID for {field}",
            {"field": field},
        )
    if value != value.lower():
        raise OF01Error(
            OF01ErrorCode.INVALID_COMMAND,
            f"UUID must be lowercase for {field}",
            {"field": field},
        )
    if value == _NIL_UUID:
        raise OF01Error(
            OF01ErrorCode.INVALID_COMMAND,
            f"nil UUID prohibited for {field}",
            {"field": field},
        )
    if not _UUID_RE.fullmatch(value):
        raise OF01Error(
            OF01ErrorCode.INVALID_COMMAND,
            f"invalid UUID format for {field}",
            {"field": field},
        )
    try:
        parsed = uuid.UUID(value)
    except ValueError as exc:
        raise OF01Error(
            OF01ErrorCode.INVALID_COMMAND,
            f"invalid UUID for {field}",
            {"field": field},
        ) from exc
    if parsed.version not in allowed_versions:
        raise OF01Error(
            OF01ErrorCode.INVALID_COMMAND,
            f"UUID version {parsed.version} not allowed for {field}",
            {"field": field, "version": parsed.version},
        )
    if str(parsed) != value:
        raise OF01Error(
            OF01ErrorCode.INVALID_COMMAND,
            f"noncanonical UUID spelling for {field}",
            {"field": field},
        )
    return value


def validate_imported_uuid5(
    value: str,
    *,
    field: str,
    namespace_id: str,
    provenance_qualifier: str,
) -> str:
    validate_uuid(value, field=field, allowed_versions=frozenset({5}))
    if provenance_qualifier not in {"LEGACY_PARTIAL", "RETROSPECTIVE_INDEX"}:
        raise OF01Error(
            OF01ErrorCode.INVALID_COMMAND,
            "UUIDv5 requires declared import provenance qualifier",
            {"field": field, "provenance_qualifier": provenance_qualifier},
        )
    validate_uuid(namespace_id, field=f"{field}_namespace")
    return value
