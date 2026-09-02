"""In-memory XA catalog repository (IMP-XA-04)."""

from __future__ import annotations

import copy
import threading
from typing import Any

from market_platform_foundation.xa01.contracts import InstrumentRecord
from market_platform_foundation.xa01.enums import ExternalIdentifierType
from market_platform_foundation.xa02.contracts import (
    AdmittedObservation,
    AdmissionEnvelope,
    CrossAssetReferenceRelationship,
)

from .codec import (
    CATALOG_RECORD_CODECS,
    CatalogRecordT,
    canonical_semantic_equal,
    codec_for_record,
    encode_document,
)
from .errors import RepositoryConflictError
from .queries import filter_admission_envelopes_as_of, filter_scalar_observations_as_of
from .repository import RepositoryPutResult

_CODEC_BY_COLLECTION = {codec.collection_name: codec for codec in CATALOG_RECORD_CODECS}
_RECORD_TYPE_TO_COLLECTION = {
    InstrumentRecord: "xa_instruments",
    AdmittedObservation: "xa_scalar_observations",
    AdmissionEnvelope: "xa_admission_envelopes",
    CrossAssetReferenceRelationship: "xa_cross_asset_relationships",
}


class InMemoryCrossAssetCatalogRepository:
    """Thread-safe reference backend with Mongo-equivalent semantics."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._stores: dict[str, dict[str, dict[str, Any]]] = {
            codec.collection_name: {} for codec in CATALOG_RECORD_CODECS
        }
        self._alias_index: dict[tuple[str, str, str], str] = {}
        self._indicator_index: dict[str, set[str]] = {}
        self._subject_index: dict[str, set[str]] = {}
        self._relationship_subject_index: dict[str, set[str]] = {}
        self._relationship_target_index: dict[str, set[str]] = {}

    def put_instrument(self, record: InstrumentRecord) -> RepositoryPutResult:
        result = self._put(record)
        self._rebuild_alias_index_for_instrument(record)
        return result

    def get_instrument(self, canonical_id: str) -> InstrumentRecord | None:
        return self._get(InstrumentRecord, canonical_id)

    def list_instrument_ids(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._stores["xa_instruments"]))

    def put_scalar_observation(self, observation: AdmittedObservation) -> RepositoryPutResult:
        result = self._put(observation)
        with self._lock:
            self._indicator_index.setdefault(observation.canonical_indicator_id, set()).add(
                observation.observation_id
            )
        return result

    def get_scalar_observation(self, observation_id: str) -> AdmittedObservation | None:
        return self._get(AdmittedObservation, observation_id)

    def list_scalar_observations_for_indicator(
        self, canonical_indicator_id: str
    ) -> tuple[AdmittedObservation, ...]:
        with self._lock:
            ids = sorted(self._indicator_index.get(canonical_indicator_id, set()))
            rows = [
                self._decode(AdmittedObservation, self._stores["xa_scalar_observations"][item])
                for item in ids
                if item in self._stores["xa_scalar_observations"]
            ]
        return tuple(rows)

    def query_scalar_observations_as_of(
        self,
        decision_time: str,
        *,
        canonical_indicator_id: str | None = None,
        limit: int = 1000,
    ) -> tuple[AdmittedObservation, ...]:
        with self._lock:
            rows = [
                self._decode(AdmittedObservation, body)
                for body in self._stores["xa_scalar_observations"].values()
            ]
        return filter_scalar_observations_as_of(
            rows,
            decision_time,
            canonical_indicator_id=canonical_indicator_id,
            limit=limit,
        )

    def put_admission_envelope(self, envelope: AdmissionEnvelope) -> RepositoryPutResult:
        result = self._put(envelope)
        with self._lock:
            self._subject_index.setdefault(envelope.source_subject_id, set()).add(envelope.observation_id)
        return result

    def get_admission_envelope(self, observation_id: str) -> AdmissionEnvelope | None:
        return self._get(AdmissionEnvelope, observation_id)

    def list_admission_envelopes_for_subject(
        self, source_subject_id: str
    ) -> tuple[AdmissionEnvelope, ...]:
        with self._lock:
            ids = sorted(self._subject_index.get(source_subject_id, set()))
            rows = [
                self._decode(AdmissionEnvelope, self._stores["xa_admission_envelopes"][item])
                for item in ids
                if item in self._stores["xa_admission_envelopes"]
            ]
        return tuple(rows)

    def query_admission_envelopes_as_of(
        self,
        decision_time: str,
        *,
        source_subject_id: str | None = None,
        limit: int = 1000,
    ) -> tuple[AdmissionEnvelope, ...]:
        with self._lock:
            rows = [
                self._decode(AdmissionEnvelope, body)
                for body in self._stores["xa_admission_envelopes"].values()
            ]
        return filter_admission_envelopes_as_of(
            rows,
            decision_time,
            source_subject_id=source_subject_id,
            limit=limit,
        )

    def put_cross_asset_relationship(
        self, relationship: CrossAssetReferenceRelationship
    ) -> RepositoryPutResult:
        result = self._put(relationship)
        with self._lock:
            self._relationship_subject_index.setdefault(relationship.subject_id, set()).add(
                relationship.relationship_id
            )
            self._relationship_target_index.setdefault(relationship.target_xa_canonical_id, set()).add(
                relationship.relationship_id
            )
        return result

    def get_cross_asset_relationship(self, relationship_id: str) -> CrossAssetReferenceRelationship | None:
        return self._get(CrossAssetReferenceRelationship, relationship_id)

    def list_cross_asset_relationships_for_subject(
        self, subject_id: str
    ) -> tuple[CrossAssetReferenceRelationship, ...]:
        with self._lock:
            ids = sorted(self._relationship_subject_index.get(subject_id, set()))
            rows = [
                self._decode(
                    CrossAssetReferenceRelationship,
                    self._stores["xa_cross_asset_relationships"][item],
                )
                for item in ids
                if item in self._stores["xa_cross_asset_relationships"]
            ]
        return tuple(rows)

    def list_cross_asset_relationships_for_target(
        self, target_xa_canonical_id: str
    ) -> tuple[CrossAssetReferenceRelationship, ...]:
        with self._lock:
            ids = sorted(self._relationship_target_index.get(target_xa_canonical_id, set()))
            rows = [
                self._decode(
                    CrossAssetReferenceRelationship,
                    self._stores["xa_cross_asset_relationships"][item],
                )
                for item in ids
                if item in self._stores["xa_cross_asset_relationships"]
            ]
        return tuple(rows)

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

    def check_health(self) -> dict[str, object]:
        with self._lock:
            counts = {name: len(store) for name, store in self._stores.items()}
        return {
            "available": True,
            "backend": "in_memory",
            "database": None,
            "collection_counts": counts,
        }

    def _put(self, record: CatalogRecordT) -> RepositoryPutResult:
        codec = codec_for_record(record)
        document = encode_document(record)
        record_id = document[codec.id_field]
        with self._lock:
            store = self._stores[codec.collection_name]
            existing = store.get(record_id)
            if existing is None:
                store[record_id] = copy.deepcopy(document)
                return RepositoryPutResult.INSERTED
            if canonical_semantic_equal(existing, document):
                return RepositoryPutResult.ALREADY_PRESENT
            raise RepositoryConflictError(
                f"IMMUTABLE_CONFLICT:{codec.kind.value}:{record_id}",
                details={"kind": codec.kind.value, "id": record_id},
            )

    def _get(self, record_type: type, record_id: str) -> Any | None:
        collection_name = _RECORD_TYPE_TO_COLLECTION[record_type]
        with self._lock:
            body = self._stores[collection_name].get(record_id)
            if body is None:
                return None
            return self._decode(record_type, body)

    def _decode(self, record_type: type, body: dict[str, Any]) -> Any:
        collection_name = _RECORD_TYPE_TO_COLLECTION[record_type]
        codec = _CODEC_BY_COLLECTION[collection_name]
        return codec.from_dict(copy.deepcopy({k: v for k, v in body.items() if k != "_id"}))

    def _rebuild_alias_index_for_instrument(self, record: InstrumentRecord) -> None:
        canonical_id = record.descriptor.identity.canonical_id
        with self._lock:
            for alias in record.aliases:
                scope = (
                    alias.provider_id.upper(),
                    alias.identifier_type.value,
                    alias.alias_value.upper(),
                )
                self._alias_index[scope] = canonical_id


__all__ = ["InMemoryCrossAssetCatalogRepository"]
