"""In-memory XA-02 admission and cross-asset reference registry."""

from __future__ import annotations

from dataclasses import replace
from threading import RLock

from market_platform_foundation.xa01.registry import InstrumentRegistry, get_registry as get_xa01_registry

from .admission import admit_macro_observation, observations_equivalent_for_identity
from .catalog import (
    ADMITTED_RATES_SERIES,
    bootstrap_xa_targets,
    build_catalog_relationships,
    is_admitted_indicator,
)
from .contracts import (
    AdmittedObservation,
    CrossAssetReferenceRelationship,
    IndicatorAdmissionSummary,
)
from .enums import CrossAssetReferenceType
from .errors import Xa02Error, Xa02ErrorCode


class AdmissionRegistry:
    def __init__(self, *, xa_registry: InstrumentRegistry | None = None) -> None:
        self._lock = RLock()
        self._xa_registry = xa_registry or get_xa01_registry()
        self._observations: dict[str, AdmittedObservation] = {}
        self._indicator_index: dict[str, list[str]] = {}
        self._relationships: dict[str, CrossAssetReferenceRelationship] = {}
        self._indicator_relationship_index: dict[str, list[str]] = {}
        self._target_relationship_index: dict[str, list[str]] = {}
        self._catalog_bootstrapped = False

    def clear(self) -> None:
        with self._lock:
            self._observations.clear()
            self._indicator_index.clear()
            self._relationships.clear()
            self._indicator_relationship_index.clear()
            self._target_relationship_index.clear()
            self._catalog_bootstrapped = False

    def bootstrap_catalog(self) -> dict[str, str]:
        with self._lock:
            targets = bootstrap_xa_targets(self._xa_registry)
            for relationship in build_catalog_relationships(xa_targets=targets):
                self._register_relationship(relationship, validate_target=True)
            self._catalog_bootstrapped = True
            return targets

    def admit_observation(self, observation: AdmittedObservation) -> str:
        with self._lock:
            existing = self._observations.get(observation.observation_id)
            if existing is not None:
                if observations_equivalent_for_identity(existing, observation):
                    return observation.observation_id
                raise Xa02Error(
                    Xa02ErrorCode.OBSERVATION_CONFLICT,
                    "observation identity conflict",
                    {"observation_id": observation.observation_id},
                )
            self._observations[observation.observation_id] = observation
            self._indicator_index.setdefault(observation.canonical_indicator_id, []).append(
                observation.observation_id
            )
            return observation.observation_id

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
            raise Xa02Error(
                Xa02ErrorCode.UNSUPPORTED_RELATIONSHIP,
                "unsupported relationship type",
                {"relationship_type": relationship.relationship_type.value},
            )
        if not is_admitted_indicator(relationship.subject_id):
            raise Xa02Error(
                Xa02ErrorCode.NOT_ADMITTED_SERIES,
                "relationship subject is not in admitted catalog",
                {"subject_id": relationship.subject_id},
            )
        if validate_target:
            try:
                self._xa_registry.get(relationship.target_xa_canonical_id)
            except Exception as exc:
                raise Xa02Error(
                    Xa02ErrorCode.UNKNOWN_XA_TARGET,
                    "unknown XA target identity",
                    {"target_xa_canonical_id": relationship.target_xa_canonical_id},
                ) from exc
        existing = self._relationships.get(relationship.relationship_id)
        if existing is not None:
            if existing == relationship:
                return relationship.relationship_id
            raise Xa02Error(
                Xa02ErrorCode.RELATIONSHIP_CONFLICT,
                "relationship identity conflict",
                {"relationship_id": relationship.relationship_id},
            )
        self._relationships[relationship.relationship_id] = relationship
        self._indicator_relationship_index.setdefault(relationship.subject_id, []).append(
            relationship.relationship_id
        )
        self._target_relationship_index.setdefault(relationship.target_xa_canonical_id, []).append(
            relationship.relationship_id
        )
        return relationship.relationship_id

    def get_observation(self, observation_id: str) -> AdmittedObservation:
        with self._lock:
            observation = self._observations.get(observation_id)
        if observation is None:
            raise Xa02Error(
                Xa02ErrorCode.UNKNOWN_OBSERVATION,
                "unknown admitted observation",
                {"observation_id": observation_id},
            )
        return observation

    def list_observations_for_indicator(self, canonical_indicator_id: str) -> tuple[AdmittedObservation, ...]:
        with self._lock:
            ids = tuple(self._indicator_index.get(canonical_indicator_id, ()))
            return tuple(self._observations[item] for item in ids)

    def list_relationships_for_indicator(self, canonical_indicator_id: str) -> tuple[CrossAssetReferenceRelationship, ...]:
        with self._lock:
            ids = tuple(self._indicator_relationship_index.get(canonical_indicator_id, ()))
            return tuple(self._relationships[item] for item in ids)

    def list_relationships_for_target(self, target_xa_canonical_id: str) -> tuple[CrossAssetReferenceRelationship, ...]:
        with self._lock:
            ids = tuple(self._target_relationship_index.get(target_xa_canonical_id, ()))
            return tuple(self._relationships[item] for item in ids)

    def list_all_relationships(self) -> tuple[CrossAssetReferenceRelationship, ...]:
        with self._lock:
            return tuple(self._relationships[item] for item in sorted(self._relationships))

    def indicator_summary(self, canonical_indicator_id: str) -> IndicatorAdmissionSummary:
        from market_platform_foundation.fred.registry import lookup_canonical

        entry = lookup_canonical(canonical_indicator_id)
        if entry is None:
            raise Xa02Error(
                Xa02ErrorCode.UNKNOWN_INDICATOR,
                "unknown canonical indicator",
                {"canonical_indicator_id": canonical_indicator_id},
            )
        observations = self.list_observations_for_indicator(canonical_indicator_id)
        relationships = self.list_relationships_for_indicator(canonical_indicator_id)
        revisions = tuple(dict.fromkeys(item.revision_classification for item in observations))
        return IndicatorAdmissionSummary(
            canonical_indicator_id=canonical_indicator_id,
            provider_series_id=entry.fred_series_id,
            title=entry.title,
            units=entry.units,
            observation_count=len(observations),
            relationship_count=len(relationships),
            revision_classifications=revisions,
        )

    def validate_registry(self) -> list[dict[str, str]]:
        findings: list[dict[str, str]] = []
        with self._lock:
            if not self._catalog_bootstrapped:
                findings.append({"code": "CATALOG_NOT_BOOTSTRAPPED"})
            expected = {item.canonical_indicator_id for item in ADMITTED_RATES_SERIES}
            registered = set(self._indicator_relationship_index)
            for indicator in sorted(expected - registered):
                findings.append({"code": "MISSING_CATALOG_RELATIONSHIP", "canonical_indicator_id": indicator})
            for relationship in self._relationships.values():
                if relationship.subject_id not in expected:
                    findings.append(
                        {
                            "code": "UNADMITTED_RELATIONSHIP_SUBJECT",
                            "subject_id": relationship.subject_id,
                        }
                    )
        return findings

    def status(self) -> dict[str, int | bool]:
        with self._lock:
            return {
                "observation_count": len(self._observations),
                "relationship_count": len(self._relationships),
                "admitted_indicator_count": len(ADMITTED_RATES_SERIES),
                "catalog_bootstrapped": self._catalog_bootstrapped,
            }


_DEFAULT_REGISTRY = AdmissionRegistry()


def get_registry() -> AdmissionRegistry:
    return _DEFAULT_REGISTRY


def configure_registry(registry: AdmissionRegistry) -> None:
    global _DEFAULT_REGISTRY
    _DEFAULT_REGISTRY = registry


def reset_registry_for_tests() -> None:
    _DEFAULT_REGISTRY.clear()


def admit_macro_observations(observations: list) -> tuple[str, ...]:
    registry = get_registry()
    if not registry.status()["catalog_bootstrapped"]:
        registry.bootstrap_catalog()
    admitted_ids: list[str] = []
    for macro_obs in observations:
        admitted = admit_macro_observation(macro_obs)
        admitted_ids.append(registry.admit_observation(admitted))
    return tuple(admitted_ids)
