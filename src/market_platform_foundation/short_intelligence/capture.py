"""Bounded hashed capture of official short-intelligence payloads."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..canonical import sha256_bytes
from ..market_data.lifecycle import ObservationLifecycle

CAPTURE_SCHEMA = "short_intelligence.provider_envelope/1.0.0"


def build_envelope(
    *,
    provider: str,
    dataset: str,
    query_identity: str,
    retrieved_time: str,
    raw_payload: bytes,
    schema_version: str = CAPTURE_SCHEMA,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    envelope = {
        "dataset": dataset,
        "lifecycle": ObservationLifecycle.CAPTURED.value,
        "provider": provider,
        "provider_observation_time": retrieved_time,
        "query_identity": query_identity,
        "raw_payload_hash": sha256_bytes(raw_payload),
        "received_time": retrieved_time,
        "schema_version": schema_version,
    }
    if extra:
        envelope.update(extra)
    return envelope


def append_jsonl(path: Path, envelope: dict[str, Any], *, max_records: int = 500) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
        if existing >= max_records:
            raise ValueError("CAPTURE_BOUND_EXCEEDED")
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(envelope, sort_keys=True, separators=(",", ":")) + "\n")
