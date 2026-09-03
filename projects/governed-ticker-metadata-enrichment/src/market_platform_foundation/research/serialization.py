"""Canonical JSON artifact serialization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..canonical import canonical_bytes, load_json_strict, sha256_bytes, write_canonical_json


def serialize_artifact(path: Path, artifact: dict[str, Any]) -> str:
    return write_canonical_json(path, artifact)


def load_artifact(path: Path) -> dict[str, Any]:
    doc = load_json_strict(path)
    if not isinstance(doc, dict):
        raise ValueError("artifact must be an object")
    return doc


def artifacts_equal(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return sha256_bytes(canonical_bytes(left)) == sha256_bytes(canonical_bytes(right))
