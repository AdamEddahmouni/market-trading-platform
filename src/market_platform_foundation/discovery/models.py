"""Discovery domain models — candidates are INVESTIGATE, never BUY/SELL."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CandidateTransition(str, Enum):
    NEW_ENTRY = "NEW_ENTRY"
    STILL_MATCHES = "STILL_MATCHES"
    DROPPED = "DROPPED"
    REENTERED = "REENTERED"


@dataclass(frozen=True, slots=True)
class ScreenDefinition:
    screen_id: str
    version: str
    description: str
    filters: str
    sort: str | None
    max_results: int
    required_fields: tuple[str, ...]
    reason: str
    columns: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "screen_id": self.screen_id,
            "version": self.version,
            "description": self.description,
            "filters": self.filters,
            "sort": self.sort,
            "max_results": self.max_results,
            "required_fields": list(self.required_fields),
            "reason": self.reason,
            "columns": self.columns,
        }


@dataclass(slots=True)
class DiscoveryCandidate:
    instrument_id: str
    provider_symbol: str
    screen_id: str
    screen_version: str
    discovered_at: str
    available_time_ns: int
    matched_reasons: list[str]
    metrics: dict[str, Any]
    inspection_priority: int
    quality: str
    provenance: dict[str, Any]
    rank: int | None = None
    transition: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrument_id": self.instrument_id,
            "provider_symbol": self.provider_symbol,
            "screen_id": self.screen_id,
            "screen_version": self.screen_version,
            "discovered_at": self.discovered_at,
            "available_time_ns": self.available_time_ns,
            "matched_reasons": list(self.matched_reasons),
            "metrics": dict(self.metrics),
            "inspection_priority": self.inspection_priority,
            "quality": self.quality,
            "provenance": dict(self.provenance),
            "rank": self.rank,
            "transition": self.transition,
            "candidate_role": "INVESTIGATE",
        }


@dataclass(slots=True)
class CandidateSet:
    run_id: str
    screen_id: str
    screen_version: str
    screen_definition: dict[str, Any]
    requested_at: str
    received_at: str
    available_time_ns: int
    provider: str
    schema_version: str
    candidate_count: int
    candidates: list[DiscoveryCandidate]
    quality: str
    raw_response_hash: str | None = None
    capture_artifact_path: str | None = None
    transitions: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "screen_id": self.screen_id,
            "screen_version": self.screen_version,
            "screen_definition": self.screen_definition,
            "requested_at": self.requested_at,
            "received_at": self.received_at,
            "available_time_ns": self.available_time_ns,
            "provider": self.provider,
            "schema_version": self.schema_version,
            "candidate_count": self.candidate_count,
            "candidates": [c.to_dict() for c in self.candidates],
            "quality": self.quality,
            "raw_response_hash": self.raw_response_hash,
            "capture_artifact_path": self.capture_artifact_path,
            "transitions": list(self.transitions),
        }

    def symbols(self) -> list[str]:
        return [c.instrument_id for c in self.candidates]
