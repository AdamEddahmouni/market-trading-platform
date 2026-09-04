"""Append-only, bounded, versioned provider envelopes (stdlib JSONL)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

CAPTURE_SCHEMA_VERSION = "market_data.provider_envelope/1.0.0"
DEFAULT_MAX_RECORDS = 5000


@dataclass(frozen=True, slots=True)
class ProviderEnvelope:
    provider: str
    instrument_id: str
    capability: str
    provider_symbol: str
    sequence: int | None
    clocks: dict[str, int | None]
    raw_payload: dict[str, Any]
    schema_version: str = CAPTURE_SCHEMA_VERSION
    lifecycle: str = "CAPTURED"
    quality_flags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "clocks": self.clocks,
            "instrument_id": self.instrument_id,
            "lifecycle": self.lifecycle,
            "provider": self.provider,
            "provider_symbol": self.provider_symbol,
            "quality_flags": list(self.quality_flags),
            "raw_payload": self.raw_payload,
            "schema_version": self.schema_version,
            "sequence": self.sequence,
        }


def append_envelope(
    path: Path,
    envelope: ProviderEnvelope,
    *,
    max_records: int = DEFAULT_MAX_RECORDS,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = sum(1 for _ in path.open("r", encoding="utf-8") if _.strip())
        if existing >= max_records:
            raise ValueError("CAPTURE_BOUND_EXCEEDED")
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(envelope.to_dict(), sort_keys=True, separators=(",", ":")) + "\n")


def read_envelopes(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            payload = json.loads(text)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def iter_envelopes(path: Path) -> Iterable[dict[str, Any]]:
    return read_envelopes(path)
