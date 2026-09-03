"""Namespaced canonical entity and provider identifier identities."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def _required(value: str, code: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(code)
    if not _TOKEN.fullmatch(text):
        raise ValueError(f"{code}_INVALID")
    return text


@dataclass(frozen=True, slots=True)
class EntityIdentity:
    namespace: str
    entity_id: str
    asset_class: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "namespace", _required(self.namespace, "ENTITY_NAMESPACE_REQUIRED"))
        object.__setattr__(self, "entity_id", _required(self.entity_id, "ENTITY_ID_REQUIRED"))
        object.__setattr__(self, "asset_class", _required(self.asset_class, "ENTITY_ASSET_CLASS_REQUIRED"))

    def qualified_id(self) -> str:
        return f"{self.namespace}:{self.asset_class}:{self.entity_id}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_class": self.asset_class,
            "entity_id": self.entity_id,
            "namespace": self.namespace,
            "qualified_id": self.qualified_id(),
        }


@dataclass(frozen=True, slots=True)
class InstrumentIdentity:
    namespace: str
    instrument_id: str
    asset_class: str
    venue_id: str
    currency: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "namespace", _required(self.namespace, "INSTRUMENT_NAMESPACE_REQUIRED"))
        object.__setattr__(self, "instrument_id", _required(self.instrument_id, "INSTRUMENT_ID_REQUIRED"))
        object.__setattr__(self, "asset_class", _required(self.asset_class, "INSTRUMENT_ASSET_CLASS_REQUIRED"))
        object.__setattr__(self, "venue_id", _required(self.venue_id, "INSTRUMENT_VENUE_REQUIRED"))
        object.__setattr__(self, "currency", _required(self.currency, "INSTRUMENT_CURRENCY_REQUIRED"))

    def qualified_id(self) -> str:
        return f"{self.namespace}:{self.asset_class}:{self.venue_id}:{self.instrument_id}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_class": self.asset_class,
            "currency": self.currency,
            "instrument_id": self.instrument_id,
            "namespace": self.namespace,
            "qualified_id": self.qualified_id(),
            "venue_id": self.venue_id,
        }


@dataclass(frozen=True, slots=True)
class ProviderIdentifierMapping:
    provider_id: str
    source_instance_id: str
    provider_identifier: str
    canonical_instrument: InstrumentIdentity
    mapping_version: str
    conflict_state: str = "NONE"

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider_id", _required(self.provider_id, "PROVIDER_ID_REQUIRED"))
        object.__setattr__(self, "source_instance_id", _required(self.source_instance_id, "SOURCE_INSTANCE_ID_REQUIRED"))
        object.__setattr__(self, "provider_identifier", _required(self.provider_identifier, "PROVIDER_IDENTIFIER_REQUIRED"))
        object.__setattr__(self, "mapping_version", _required(self.mapping_version, "MAPPING_VERSION_REQUIRED"))
        conflict_state = str(self.conflict_state).strip().upper() or "NONE"
        if conflict_state not in {"NONE", "RESOLVED"}:
            raise ValueError("MAPPING_CONFLICT_STATE_INVALID")
        object.__setattr__(self, "conflict_state", conflict_state)

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_instrument": self.canonical_instrument.to_dict(),
            "conflict_state": self.conflict_state,
            "mapping_version": self.mapping_version,
            "provider_id": self.provider_id,
            "provider_identifier": self.provider_identifier,
            "source_instance_id": self.source_instance_id,
        }


@dataclass(frozen=True, slots=True)
class MappingConflictResolution:
    """Deterministic, auditable outcome for a provider-symbol mapping set."""

    provider_id: str
    source_instance_id: str
    provider_identifier: str
    candidates: tuple[InstrumentIdentity, ...]
    selected: InstrumentIdentity | None
    decision: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidates": [item.to_dict() for item in self.candidates],
            "decision": self.decision,
            "provider_id": self.provider_id,
            "provider_identifier": self.provider_identifier,
            "reason": self.reason,
            "selected": self.selected.to_dict() if self.selected else None,
            "source_instance_id": self.source_instance_id,
        }


def resolve_mapping_conflict(
    mappings: tuple[ProviderIdentifierMapping, ...],
) -> MappingConflictResolution:
    if not mappings:
        raise ValueError("MAPPING_CANDIDATES_REQUIRED")
    ordered = tuple(sorted(mappings, key=lambda item: item.canonical_instrument.qualified_id()))
    identity = (ordered[0].provider_id, ordered[0].source_instance_id, ordered[0].provider_identifier)
    if any(
        (item.provider_id, item.source_instance_id, item.provider_identifier) != identity
        for item in ordered
    ):
        raise ValueError("MAPPING_SCOPE_MISMATCH")
    candidates = tuple(
        sorted(
            {item.canonical_instrument for item in ordered},
            key=lambda item: item.qualified_id(),
        )
    )
    if len(candidates) == 1:
        return MappingConflictResolution(
            *identity,
            candidates,
            candidates[0],
            "CONSISTENT",
            "all provider mappings resolve to one canonical instrument",
        )
    return MappingConflictResolution(
        *identity,
        candidates,
        None,
        "FAIL_CLOSED_CONFLICT",
        "provider identifier maps to multiple canonical instruments",
    )


__all__ = [
    "EntityIdentity",
    "InstrumentIdentity",
    "MappingConflictResolution",
    "ProviderIdentifierMapping",
    "resolve_mapping_conflict",
]
