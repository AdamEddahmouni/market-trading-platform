"""Mongo collection schema for XA catalog persistence (IMP-XA-04)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..codec import CATALOG_RECORD_CODECS, MONGO_SCHEMA_PLAN_VERSION, CatalogRecordCodec
from ..errors import RepositorySchemaError

_STRING = {"bsonType": "string"}


def _id_validator(id_field: str) -> dict[str, Any]:
    return {
        "bsonType": "object",
        "required": ["schema_version", id_field],
        "properties": {
            "schema_version": {"bsonType": ["int", "long"]},
            id_field: _STRING,
        },
    }


@dataclass(frozen=True, slots=True)
class CollectionPlan:
    name: str
    validator: dict[str, Any]
    indexes: tuple[dict[str, Any], ...]


def _plans() -> tuple[CollectionPlan, ...]:
    plans: list[CollectionPlan] = []
    for codec in CATALOG_RECORD_CODECS:
        indexes: list[dict[str, Any]] = []
        if codec.collection_name == "xa_instruments":
            indexes.append({"keys": [("canonical_id", 1)], "unique": True, "name": "canonical_id_unique"})
        elif codec.collection_name == "xa_scalar_observations":
            indexes.extend(
                [
                    {"keys": [("observation_id", 1)], "unique": True, "name": "observation_id_unique"},
                    {"keys": [("canonical_indicator_id", 1), ("available_time", 1)], "name": "indicator_available_time"},
                ]
            )
        elif codec.collection_name == "xa_admission_envelopes":
            indexes.extend(
                [
                    {"keys": [("observation_id", 1)], "unique": True, "name": "observation_id_unique"},
                    {"keys": [("source_subject_id", 1), ("available_time", 1)], "name": "subject_available_time"},
                    {"keys": [("payload_kind", 1)], "name": "payload_kind_lookup"},
                ]
            )
        elif codec.collection_name == "xa_cross_asset_relationships":
            indexes.extend(
                [
                    {"keys": [("relationship_id", 1)], "unique": True, "name": "relationship_id_unique"},
                    {"keys": [("subject_id", 1)], "name": "subject_lookup"},
                    {"keys": [("target_xa_canonical_id", 1)], "name": "target_lookup"},
                ]
            )
        plans.append(
            CollectionPlan(
                name=codec.collection_name,
                validator=_id_validator(codec.id_field),
                indexes=tuple(indexes),
            )
        )
    return tuple(plans)


COLLECTION_PLANS = _plans()


class MongoCatalogSchemaManager:
    def __init__(self, database: Any) -> None:
        self._database = database

    def ensure_schema(self) -> None:
        for plan in COLLECTION_PLANS:
            collection = self._database[plan.name]
            try:
                collection.create_index([("_id", 1)], unique=True, name="_id_unique")
                for index in plan.indexes:
                    keys = index["keys"]
                    collection.create_index(
                        keys,
                        unique=index.get("unique", False),
                        name=index["name"],
                    )
                self._database.command(
                    {
                        "collMod": plan.name,
                        "validator": {"$jsonSchema": plan.validator},
                        "validationLevel": "moderate",
                    }
                )
            except Exception as exc:
                try:
                    self._database.create_collection(
                        plan.name,
                        validator={"$jsonSchema": plan.validator},
                        validationLevel="moderate",
                    )
                    collection = self._database[plan.name]
                    collection.create_index([("_id", 1)], unique=True, name="_id_unique")
                    for index in plan.indexes:
                        collection.create_index(
                            index["keys"],
                            unique=index.get("unique", False),
                            name=index["name"],
                        )
                except Exception as inner_exc:
                    raise RepositorySchemaError(
                        "XA_CATALOG_SCHEMA_BOOTSTRAP_FAILED",
                        details={
                            "collection": plan.name,
                            "plan_version": MONGO_SCHEMA_PLAN_VERSION,
                            "reason": str(inner_exc or exc),
                        },
                    ) from inner_exc


__all__ = ["MongoCatalogSchemaManager", "COLLECTION_PLANS"]
