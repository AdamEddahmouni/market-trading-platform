"""Mongo-backed XA catalog repository (IMP-XA-04)."""

from __future__ import annotations

from typing import Any

from market_platform_foundation.xa01.contracts import InstrumentRecord
from market_platform_foundation.xa01.enums import ExternalIdentifierType
from market_platform_foundation.xa02.contracts import (
    AdmittedObservation,
    AdmissionEnvelope,
    CrossAssetReferenceRelationship,
)

from ..codec import (
    CATALOG_RECORD_CODECS,
    CatalogRecordT,
    canonical_semantic_equal,
    codec_for_record,
    decode_document,
    encode_document,
)
from ..errors import RepositoryConflictError, RepositoryUnavailableError, RepositoryValidationError
from ..queries import filter_admission_envelopes_as_of, filter_scalar_observations_as_of, validate_limit
from ..repository import RepositoryPutResult
from .config import MongoCatalogRepositoryConfig, redact_mongo_uri
from .schema import MongoCatalogSchemaManager

_CODEC_BY_COLLECTION = {codec.collection_name: codec for codec in CATALOG_RECORD_CODECS}


def _import_pymongo() -> Any:
    try:
        from pymongo import MongoClient
        from pymongo.errors import DuplicateKeyError, PyMongoError, ServerSelectionTimeoutError
    except ImportError as exc:
        raise RepositoryUnavailableError(
            "PYMONGO_NOT_INSTALLED",
            details={"reason": str(exc)},
        ) from exc
    return MongoClient, DuplicateKeyError, PyMongoError, ServerSelectionTimeoutError


class MongoCrossAssetCatalogRepository:
    """Synchronous PyMongo persistence backend for XA catalog records."""

    def __init__(
        self,
        *,
        client: Any | None = None,
        database_name: str | None = None,
        owns_client: bool = False,
        config: MongoCatalogRepositoryConfig | None = None,
    ) -> None:
        MongoClient, _, _, _ = _import_pymongo()
        if client is None:
            if config is None:
                raise ValueError("MONGO_CLIENT_OR_CONFIG_REQUIRED")
            client = MongoClient(
                config.uri,
                serverSelectionTimeoutMS=config.server_selection_timeout_ms,
                appname=config.application_name,
            )
            owns_client = True
            database_name = config.database_name
        if database_name is None:
            raise ValueError("MONGODB_DATABASE_REQUIRED")
        self._client = client
        self._database = client[database_name]
        self._owns_client = owns_client
        self._database_name = database_name
        self._schema_manager = MongoCatalogSchemaManager(self._database)

    @classmethod
    def from_config(cls, config: MongoCatalogRepositoryConfig) -> MongoCrossAssetCatalogRepository:
        return cls(config=config)

    def ensure_schema(self) -> None:
        self._schema_manager.ensure_schema()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def put_instrument(self, record: InstrumentRecord) -> RepositoryPutResult:
        return self._put(record)

    def get_instrument(self, canonical_id: str) -> InstrumentRecord | None:
        return self._get("xa_instruments", canonical_id, InstrumentRecord)

    def list_instrument_ids(self) -> tuple[str, ...]:
        ids = self._database["xa_instruments"].find({}, {"canonical_id": 1}).sort("canonical_id", 1)
        return tuple(str(row["canonical_id"]) for row in ids)

    def put_scalar_observation(self, observation: AdmittedObservation) -> RepositoryPutResult:
        return self._put(observation)

    def get_scalar_observation(self, observation_id: str) -> AdmittedObservation | None:
        return self._get("xa_scalar_observations", observation_id, AdmittedObservation)

    def list_scalar_observations_for_indicator(
        self, canonical_indicator_id: str
    ) -> tuple[AdmittedObservation, ...]:
        codec = _CODEC_BY_COLLECTION["xa_scalar_observations"]
        cursor = self._database["xa_scalar_observations"].find(
            {"canonical_indicator_id": canonical_indicator_id}
        ).sort("observation_id", 1)
        return tuple(decode_document(document, codec) for document in cursor)

    def query_scalar_observations_as_of(
        self,
        decision_time: str,
        *,
        canonical_indicator_id: str | None = None,
        limit: int = 1000,
    ) -> tuple[AdmittedObservation, ...]:
        active_limit = validate_limit(limit)
        query: dict[str, object] = {"available_time": {"$lte": decision_time}}
        if canonical_indicator_id is not None:
            query["canonical_indicator_id"] = canonical_indicator_id
        codec = _CODEC_BY_COLLECTION["xa_scalar_observations"]
        cursor = (
            self._database["xa_scalar_observations"]
            .find(query)
            .sort([("available_time", 1), ("observation_id", 1)])
            .limit(active_limit)
        )
        rows = [decode_document(document, codec) for document in cursor]
        return filter_scalar_observations_as_of(
            rows,
            decision_time,
            canonical_indicator_id=canonical_indicator_id,
            limit=active_limit,
        )

    def put_admission_envelope(self, envelope: AdmissionEnvelope) -> RepositoryPutResult:
        return self._put(envelope)

    def get_admission_envelope(self, observation_id: str) -> AdmissionEnvelope | None:
        return self._get("xa_admission_envelopes", observation_id, AdmissionEnvelope)

    def list_admission_envelopes_for_subject(
        self, source_subject_id: str
    ) -> tuple[AdmissionEnvelope, ...]:
        codec = _CODEC_BY_COLLECTION["xa_admission_envelopes"]
        cursor = self._database["xa_admission_envelopes"].find(
            {"source_subject_id": source_subject_id}
        ).sort("observation_id", 1)
        return tuple(decode_document(document, codec) for document in cursor)

    def query_admission_envelopes_as_of(
        self,
        decision_time: str,
        *,
        source_subject_id: str | None = None,
        limit: int = 1000,
    ) -> tuple[AdmissionEnvelope, ...]:
        active_limit = validate_limit(limit)
        query: dict[str, object] = {"available_time": {"$lte": decision_time}}
        if source_subject_id is not None:
            query["source_subject_id"] = source_subject_id
        codec = _CODEC_BY_COLLECTION["xa_admission_envelopes"]
        cursor = (
            self._database["xa_admission_envelopes"]
            .find(query)
            .sort([("available_time", 1), ("observation_id", 1)])
            .limit(active_limit)
        )
        rows = [decode_document(document, codec) for document in cursor]
        return filter_admission_envelopes_as_of(
            rows,
            decision_time,
            source_subject_id=source_subject_id,
            limit=active_limit,
        )

    def put_cross_asset_relationship(
        self, relationship: CrossAssetReferenceRelationship
    ) -> RepositoryPutResult:
        return self._put(relationship)

    def get_cross_asset_relationship(self, relationship_id: str) -> CrossAssetReferenceRelationship | None:
        return self._get("xa_cross_asset_relationships", relationship_id, CrossAssetReferenceRelationship)

    def list_cross_asset_relationships_for_subject(
        self, subject_id: str
    ) -> tuple[CrossAssetReferenceRelationship, ...]:
        codec = _CODEC_BY_COLLECTION["xa_cross_asset_relationships"]
        cursor = self._database["xa_cross_asset_relationships"].find({"subject_id": subject_id}).sort(
            "relationship_id", 1
        )
        return tuple(decode_document(document, codec) for document in cursor)

    def list_cross_asset_relationships_for_target(
        self, target_xa_canonical_id: str
    ) -> tuple[CrossAssetReferenceRelationship, ...]:
        codec = _CODEC_BY_COLLECTION["xa_cross_asset_relationships"]
        cursor = self._database["xa_cross_asset_relationships"].find(
            {"target_xa_canonical_id": target_xa_canonical_id}
        ).sort("relationship_id", 1)
        return tuple(decode_document(document, codec) for document in cursor)

    def resolve_alias_scope(
        self,
        *,
        provider_id: str,
        identifier_type: ExternalIdentifierType,
        alias_value: str,
    ) -> str | None:
        codec = _CODEC_BY_COLLECTION["xa_instruments"]
        provider = provider_id.upper()
        alias = alias_value.upper()
        cursor = self._database["xa_instruments"].find(
            {
                "aliases": {
                    "$elemMatch": {
                        "provider_id": {"$regex": f"^{provider}$", "$options": "i"},
                        "identifier_type": identifier_type.value,
                        "alias_value": {"$regex": f"^{alias}$", "$options": "i"},
                    }
                }
            }
        ).limit(2)
        matches = [decode_document(document, codec) for document in cursor]
        if not matches:
            return None
        return matches[0].descriptor.identity.canonical_id

    def check_health(self) -> dict[str, object]:
        try:
            self._client.admin.command("ping")
            return {
                "available": True,
                "backend": "mongo",
                "database": self._database_name,
            }
        except Exception as exc:
            raise RepositoryUnavailableError(
                "MONGO_HEALTH_CHECK_FAILED",
                details={"database": self._database_name, "reason": str(exc)},
            ) from exc

    def _put(self, record: CatalogRecordT) -> RepositoryPutResult:
        _, DuplicateKeyError, PyMongoError, ServerSelectionTimeoutError = _import_pymongo()
        codec = codec_for_record(record)
        document = encode_document(record)
        record_id = document[codec.id_field]
        collection = self._database[codec.collection_name]
        try:
            collection.insert_one(document)
            return RepositoryPutResult.INSERTED
        except DuplicateKeyError:
            existing = collection.find_one({"_id": document["_id"]})
            if existing is None:
                raise RepositoryConflictError(
                    f"IMMUTABLE_CONFLICT:{codec.kind.value}:{record_id}",
                    details={"kind": codec.kind.value, "id": record_id},
                )
            if canonical_semantic_equal(existing, document):
                return RepositoryPutResult.ALREADY_PRESENT
            raise RepositoryConflictError(
                f"IMMUTABLE_CONFLICT:{codec.kind.value}:{record_id}",
                details={"kind": codec.kind.value, "id": record_id},
            )
        except ServerSelectionTimeoutError as exc:
            raise RepositoryUnavailableError(
                "MONGO_UNAVAILABLE",
                details={"reason": str(exc)},
            ) from exc
        except PyMongoError as exc:
            raise RepositoryUnavailableError(
                "MONGO_WRITE_FAILED",
                details={"collection": codec.collection_name, "reason": str(exc)},
            ) from exc

    def _get(self, collection_name: str, record_id: str, record_type: type) -> Any | None:
        codec = _CODEC_BY_COLLECTION[collection_name]
        document = self._database[collection_name].find_one({"_id": record_id})
        if document is None:
            return None
        try:
            return decode_document(document, codec)
        except RepositoryValidationError:
            raise
        except Exception as exc:
            raise RepositoryValidationError(
                f"DOMAIN_DESERIALIZATION_FAILED:{codec.kind.value}",
                details={"id": record_id, "reason": str(exc)},
            ) from exc


__all__ = ["MongoCrossAssetCatalogRepository"]
