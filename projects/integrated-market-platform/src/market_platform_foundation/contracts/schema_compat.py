"""Schema compatibility and round-trip helpers per ADR-SCH-001."""

from __future__ import annotations

from typing import Any

from ..canonical import canonical_bytes, load_json_strict, sha256_bytes, write_canonical_json
from pathlib import Path


def parse_major(schema_version: str) -> int:
    return int(schema_version.split(".", maxsplit=1)[0])


def compatible_reader(schema_version: str, reader_version: str) -> bool:
    return parse_major(schema_version) == parse_major(reader_version)


def round_trip_record(record: dict[str, Any]) -> dict[str, Any]:
    encoded = canonical_bytes(record)
    loaded = load_json_strict_from_bytes(encoded)
    if not isinstance(loaded, dict):
        raise ValueError("round trip must produce object")
    return loaded


def load_json_strict_from_bytes(data: bytes) -> object:
    import json

    from ..canonical import _pairs_no_duplicates

    return json.loads(data.decode("utf-8"), object_pairs_hook=_pairs_no_duplicates)


def round_trip_file(path: Path) -> tuple[dict[str, Any], str]:
    record = load_json_strict(path)
    if not isinstance(record, dict):
        raise ValueError("fixture must be object")
    restored = round_trip_record(record)
    return restored, sha256_bytes(canonical_bytes(restored))
