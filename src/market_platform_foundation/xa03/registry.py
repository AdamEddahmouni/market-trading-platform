"""In-memory XA-03 positioning admission and cross-asset reference registry."""

from __future__ import annotations

from threading import RLock

from market_platform_foundation.xa01.registry import InstrumentRegistry, get_registry as get_xa01_registry
from market_platform_foundation.xa02.contracts import AdmissionEnvelope, CrossAssetReferenceRelationship
from market_platform_foundation.xa02.enums import CrossAssetReferenceType
from market_platform_foundation.xa02.envelope import envelopes_equivalent_for_identity
from market_platform_foundation.xa02.registry import get_registry as get_xa02_registry

from .catalog import (
    ADMITTED_POSITIONING_MARKETS,
    bootstrap_xa_targets,
    build_catalog_relationships,
    is_admitted_market,
    validate_catalog_relationships,
)
from .errors import Xa03Error, Xa03ErrorCode


class PositioningAdmissionRegistry:
    def __init__(self, *, xa_registry: InstrumentRegistry | None = None) -> None:
        self._lock = RLock()
        self._xa_registry = xa_registry or get_xa01_registry()
        self._observations: dict[str, AdmissionEnvelope] = {}
        self._market_index: dict[str, list[str]] = {}
        self._relationships: dict[str, CrossAssetReferenceRelationship] = {}
        self._market_relationship_index: dict[str, list[str]] = {}
        self._target_relationship_index: dict[str, list[str]] = {}
        self._catalog_bootstrapped = False

    def clear(self) -> None:
        with self._lock:
            self._observations.clear()
            self._market_index.clear()
            self._relationships.clear()
            self._market_relationship_index.clear()
            self._target_relationship_index.clear()
            self._catalog_bootstrapped = False

    def bootstrap_catalog(self) -> dict[str, str]:
        with self._lock:
            targets = bootstrap_xa_targets(self._xa_registry)
            for relationship in build_catalog_relationships(xa_targets=targets):
                self._register_relationship(relationship, validate_target=True)
            self._catalog_bootstrapped = True
            return targets

    def admit_observation(self, envelope: AdmissionEnvelope) -> str:
        with self._lock:
            existing = self._observations.get(envelope.observation_id)
            if existing is not None:
                if envelopes_equivalent_for_identity(existing, envelope):
                    return envelope.observation_id
                raise Xa03Error(
                    Xa03ErrorCode.OBSERVATION_CONFLICT,
                    "observation identity conflict",
                    {"observation_id": envelope.observation_id},
                )
            self._observations[envelope.observation_id] = envelope
            self._market_index.setdefault(envelope.source_subject_id, []).append(envelope.observation_id)
            return envelope.observation_id

    def register_relationship(self, relationship: CrossAssetReferenceRelationship) -> str:
        with self._lock:
            return self._register_relationship(relationship, validate_target=True)

    def _register_relationship(
        self,
        relationship: CrossAssetReferenceRelationship,
        *,
        validate_target: bool,
    ) -> str:
        if relationship.relationship_type.value not in {item.value for item in CrossAssetReferenceType}:
            raise Xa03Error(
                Xa03ErrorCode.UNSUPPORTED_RELATIONSHIP,
                "unsupported relationship type",
                {"relationship_type": relationship.relationship_type.value},
            )
        if not is_admitted_market(relationship.subject_id):
            raise Xa03Error(
                Xa03ErrorCode.NOT_ADMITTED_MARKET,
                "relationship subject is not in admitted catalog",
                {"subject_id": relationship.subject_id},
            )
        if validate_target:
            try:
                self._xa_registry.get(relationship.target_xa_canonical_id)
            except Exception as exc:
                raise Xa03Error(
                    Xa03ErrorCode.UNKNOWN_XA_TARGET,
                    "unknown XA target identity",
                    {"target_xa_canonical_id": relationship.target_xa_canonical_id},
                ) from exc
        existing = self._relationships.get(relationship.relationship_id)
        if existing is not None:
            if existing == relationship:
                return relationship.relationship_id
            raise Xa03Error(
                Xa03ErrorCode.RELATIONSHIP_CONFLICT,
                "relationship identity conflict",
                {"relationship_id": relationship.relationship_id},
            )
        self._relationships[relationship.relationship_id] = relationship
        self._market_relationship_index.setdefault(relationship.subject_id, []).append(relationship.relationship_id)
        self._target_relationship_index.setdefault(relationship.target_xa_canonical_id, []).append(
            relationship.relationship_id
        )
        return relationship.relationship_id

    def get_observation(self, observation_id: str) -> AdmissionEnvelope:
        with self._lock:
            observation = self._observations.get(observation_id)
        if observation is None:
            raise Xa03Error(
                Xa03ErrorCode.UNKNOWN_OBSERVATION,
                "unknown admitted observation",
                {"observation_id": observation_id},
            )
        return observation

    def list_observations_for_market(self, market_report_id: str) -> tuple[AdmissionEnvelope, ...]:
        with self._lock:
            ids = tuple(self._market_index.get(market_report_id, ()))
            return tuple(self._observations[item] for item in ids)

    def list_relationships_for_market(self, market_report_id: str) -> tuple[CrossAssetReferenceRelationship, ...]:
        with self._lock:
            ids = tuple(self._market_relationship_index.get(market_report_id, ()))
            return tuple(self._relationships[item] for item in ids)

    def list_relationships_for_target(self, target_xa_canonical_id: str) -> tuple[CrossAssetReferenceRelationship, ...]:
        with self._lock:
            ids = tuple(self._target_relationship_index.get(target_xa_canonical_id, ()))
            return tuple(self._relationships[item] for item in ids)

    def list_all_relationships(self) -> tuple[CrossAssetReferenceRelationship, ...]:
        with self._lock:
            return tuple(self._relationships[item] for item in sorted(self._relationships))

    def validate_registry(self) -> list[dict[str, str]]:
        findings: list[dict[str, str]] = []
        with self._lock:
            if not self._catalog_bootstrapped:
                findings.append({"code": "CATALOG_NOT_BOOTSTRAPPED"})
            findings.extend(validate_catalog_relationships(tuple(self._relationships.values())))
        return findings

    def status(self) -> dict[str, int | bool]:
        with self._lock:
            return {
                "observation_count": len(self._observations),
                "relationship_count": len(self._relationships),
                "admitted_market_count": len(ADMITTED_POSITIONING_MARKETS),
                "catalog_bootstrapped": self._catalog_bootstrapped,
            }


_DEFAULT_REGISTRY = PositioningAdmissionRegistry()


def get_registry() -> PositioningAdmissionRegistry:
    return _DEFAULT_REGISTRY


def configure_registry(registry: PositioningAdmissionRegistry) -> None:
    global _DEFAULT_REGISTRY
    _DEFAULT_REGISTRY = registry


def reset_registry_for_tests() -> None:
    _DEFAULT_REGISTRY.clear()


def unified_admission_status() -> dict[str, object]:
    xa02 = get_xa02_registry().status()
    xa03 = get_registry().status()
    return {
        "schema_version": 1,
        "verticals": {
            "fred_rates": {
                "provider": "FRED",
                "source_classification": "FIXTURE_OR_ADMITTED",
                **xa02,
            },
            "cftc_positioning": {
                "provider": "CFTC",
                "source_classification": "FIXTURE",
                **xa03,
            },
        },
        "total_observation_count": int(xa02["observation_count"]) + int(xa03["observation_count"]),
        "total_relationship_count": int(xa02["relationship_count"]) + int(xa03["relationship_count"]),
    }
