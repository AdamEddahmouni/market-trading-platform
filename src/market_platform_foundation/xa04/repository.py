"""Backend-independent XA catalog repository contract (IMP-XA-04)."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol, runtime_checkable

from market_platform_foundation.xa01.contracts import InstrumentRecord
from market_platform_foundation.xa01.enums import ExternalIdentifierType
from market_platform_foundation.xa02.contracts import (
    AdmittedObservation,
    AdmissionEnvelope,
    CrossAssetReferenceRelationship,
)


class RepositoryPutResult(StrEnum):
    INSERTED = "INSERTED"
    ALREADY_PRESENT = "ALREADY_PRESENT"


@runtime_checkable
class CrossAssetCatalogRepository(Protocol):
    """Typed persistence boundary for canonical XA catalog records."""

    def put_instrument(self, record: InstrumentRecord) -> RepositoryPutResult: ...

    def get_instrument(self, canonical_id: str) -> InstrumentRecord | None: ...

    def list_instrument_ids(self) -> tuple[str, ...]: ...

    def put_scalar_observation(self, observation: AdmittedObservation) -> RepositoryPutResult: ...

    def get_scalar_observation(self, observation_id: str) -> AdmittedObservation | None: ...

    def list_scalar_observations_for_indicator(
        self, canonical_indicator_id: str
    ) -> tuple[AdmittedObservation, ...]: ...

    def query_scalar_observations_as_of(
        self,
        decision_time: str,
        *,
        canonical_indicator_id: str | None = None,
        limit: int = 1000,
    ) -> tuple[AdmittedObservation, ...]: ...

    def put_admission_envelope(self, envelope: AdmissionEnvelope) -> RepositoryPutResult: ...

    def get_admission_envelope(self, observation_id: str) -> AdmissionEnvelope | None: ...

    def list_admission_envelopes_for_subject(
        self, source_subject_id: str
    ) -> tuple[AdmissionEnvelope, ...]: ...

    def query_admission_envelopes_as_of(
        self,
        decision_time: str,
        *,
        source_subject_id: str | None = None,
        limit: int = 1000,
    ) -> tuple[AdmissionEnvelope, ...]: ...

    def put_cross_asset_relationship(
        self, relationship: CrossAssetReferenceRelationship
    ) -> RepositoryPutResult: ...

    def get_cross_asset_relationship(self, relationship_id: str) -> CrossAssetReferenceRelationship | None: ...

    def list_cross_asset_relationships_for_subject(
        self, subject_id: str
    ) -> tuple[CrossAssetReferenceRelationship, ...]: ...

    def list_cross_asset_relationships_for_target(
        self, target_xa_canonical_id: str
    ) -> tuple[CrossAssetReferenceRelationship, ...]: ...

    def resolve_alias_scope(
        self,
        *,
        provider_id: str,
        identifier_type: ExternalIdentifierType,
        alias_value: str,
    ) -> str | None: ...

    def check_health(self) -> dict[str, object]: ...
