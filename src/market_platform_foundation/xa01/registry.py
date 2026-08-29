"""In-memory XA-01 instrument registry."""

from __future__ import annotations

from dataclasses import replace
from threading import RLock
from typing import Iterable

from .contracts import (
    DomainParticipation,
    ExternalIdentifier,
    InstrumentDescriptor,
    InstrumentRecord,
    InstrumentRelationship,
)
from .enums import AnalyticalDomain, ExternalIdentifierType, RelationshipType
from .errors import Xa01Error, Xa01ErrorCode
from .identity import derive_canonical_id


class InstrumentRegistry:
    def __init__(self) -> None:
        self._lock = RLock()
        self._records: dict[str, InstrumentRecord] = {}
        self._identity_index: dict[tuple[str, str, tuple[tuple[str, str], ...]], str] = {}
        self._alias_index: dict[tuple[str, str, str], str] = {}

    def clear(self) -> None:
        with self._lock:
            self._records.clear()
            self._identity_index.clear()
            self._alias_index.clear()

    def register_descriptor(self, descriptor: InstrumentDescriptor) -> str:
        identity = descriptor.identity
        canonical_id = identity.canonical_id or derive_canonical_id(
            instrument_kind=identity.instrument_kind,
            asset_class=identity.asset_class,
            identity_key=identity.identity_key,
        )
        identity_material = (
            identity.identity_profile,
            identity.instrument_kind.value,
            tuple(sorted((k, v) for k, v in identity.identity_key.items())),
        )
        with self._lock:
            existing_id = self._identity_index.get(identity_material)
            if existing_id is not None and existing_id != canonical_id:
                raise Xa01Error(
                    Xa01ErrorCode.DUPLICATE_IDENTITY,
                    "conflicting canonical identity material",
                    {"existing_id": existing_id, "requested_id": canonical_id},
                )
            if canonical_id in self._records:
                current = self._records[canonical_id]
                if current.descriptor != descriptor:
                    raise Xa01Error(
                        Xa01ErrorCode.DUPLICATE_IDENTITY,
                        "descriptor mismatch for canonical_id",
                        {"canonical_id": canonical_id},
                    )
                return canonical_id
            final_descriptor = replace(
                descriptor,
                identity=replace(identity, canonical_id=canonical_id),
            )
            record = InstrumentRecord(descriptor=final_descriptor)
            self._records[canonical_id] = record
            self._identity_index[identity_material] = canonical_id
            return canonical_id

    def get(self, canonical_id: str) -> InstrumentRecord:
        with self._lock:
            record = self._records.get(canonical_id)
        if record is None:
            raise Xa01Error(
                Xa01ErrorCode.UNKNOWN_INSTRUMENT,
                "unknown canonical instrument",
                {"canonical_id": canonical_id},
            )
        return record

    def list_ids(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._records))

    def add_domains(self, canonical_id: str, domains: Iterable[AnalyticalDomain | DomainParticipation]) -> None:
        normalized: list[DomainParticipation] = []
        for item in domains:
            if isinstance(item, AnalyticalDomain):
                normalized.append(DomainParticipation(domain=item))
            else:
                normalized.append(item)
        with self._lock:
            record = self.get(canonical_id)
            merged = {item.domain: item for item in record.analytical_domains}
            for item in normalized:
                merged[item.domain] = item
            self._records[canonical_id] = replace(
                record,
                analytical_domains=tuple(sorted(merged.values(), key=lambda row: row.domain.value)),
            )

    def add_alias(self, canonical_id: str, alias: ExternalIdentifier) -> None:
        if not alias.alias_value.strip():
            raise Xa01Error(Xa01ErrorCode.INVALID_ALIAS, "alias_value required", {})
        scope = (
            alias.provider_id.upper(),
            alias.identifier_type.value,
            alias.alias_value.upper(),
        )
        with self._lock:
            self.get(canonical_id)
            existing = self._alias_index.get(scope)
            if existing is not None and existing != canonical_id:
                raise Xa01Error(
                    Xa01ErrorCode.ALIAS_CONFLICT,
                    "alias already bound to different instrument",
                    {"scope": scope, "existing_id": existing, "requested_id": canonical_id},
                )
            record = self._records[canonical_id]
            aliases = {(
                item.provider_id.upper(),
                item.identifier_type.value,
                item.alias_value.upper(),
            ): item for item in record.aliases}
            aliases[scope] = alias
            self._records[canonical_id] = replace(record, aliases=tuple(aliases.values()))
            self._alias_index[scope] = canonical_id

    def add_relationship(self, relationship: InstrumentRelationship) -> None:
        if relationship.from_canonical_id == relationship.to_canonical_id:
            raise Xa01Error(
                Xa01ErrorCode.SELF_RELATIONSHIP,
                "self-relationship forbidden",
                {"relationship_type": relationship.relationship_type.value},
            )
        with self._lock:
            self.get(relationship.from_canonical_id)
            self.get(relationship.to_canonical_id)
            if relationship.relationship_type == RelationshipType.UNDERLYING:
                self._assert_acyclic(relationship.from_canonical_id, relationship.to_canonical_id)
            record = self._records[relationship.from_canonical_id]
            rels = tuple(
                item
                for item in record.relationships
                if not (
                    item.relationship_type == relationship.relationship_type
                    and item.to_canonical_id == relationship.to_canonical_id
                )
            ) + (relationship,)
            self._records[relationship.from_canonical_id] = replace(record, relationships=rels)

    def _assert_acyclic(self, start: str, target: str) -> None:
        visited = {start}
        stack = [target]
        while stack:
            node = stack.pop()
            if node in visited:
                raise Xa01Error(
                    Xa01ErrorCode.CYCLIC_RELATIONSHIP,
                    "underlying relationship cycle forbidden",
                    {"from_canonical_id": start, "to_canonical_id": target},
                )
            visited.add(node)
            record = self._records.get(node)
            if record is None:
                continue
            for rel in record.relationships:
                if rel.relationship_type == RelationshipType.UNDERLYING:
                    stack.append(rel.to_canonical_id)

    def resolve_alias_scope(
        self,
        *,
        provider_id: str,
        identifier_type: ExternalIdentifierType,
        alias_value: str,
    ) -> str | None:
        scope = (provider_id.upper(), identifier_type.value, alias_value.upper())
        with self._lock:
            return self._alias_index.get(scope)

    def validate_registry(self) -> list[dict[str, str]]:
        findings: list[dict[str, str]] = []
        with self._lock:
            for canonical_id, record in self._records.items():
                if record.descriptor.identity.canonical_id != canonical_id:
                    findings.append(
                        {
                            "code": "IDENTITY_ID_MISMATCH",
                            "canonical_id": canonical_id,
                        }
                    )
                for rel in record.relationships:
                    if rel.from_canonical_id != canonical_id:
                        findings.append({"code": "RELATIONSHIP_FROM_MISMATCH", "canonical_id": canonical_id})
                    if rel.to_canonical_id not in self._records:
                        findings.append({"code": "RELATIONSHIP_TARGET_MISSING", "canonical_id": canonical_id})
        return findings


_DEFAULT_REGISTRY = InstrumentRegistry()


def get_registry() -> InstrumentRegistry:
    return _DEFAULT_REGISTRY


def configure_registry(registry: InstrumentRegistry) -> None:
    global _DEFAULT_REGISTRY
    _DEFAULT_REGISTRY = registry


def reset_registry_for_tests() -> None:
    _DEFAULT_REGISTRY.clear()
