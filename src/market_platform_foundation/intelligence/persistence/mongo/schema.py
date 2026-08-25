"""Mongo collection schema, validators, and index bootstrap (BUILD 04.5)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..codec import MONGO_SCHEMA_PLAN_VERSION, RECORD_CODECS, RecordCodec
from ..errors import RepositorySchemaError

_INT_OR_LONG = {"bsonType": ["int", "long"]}
_STRING = {"bsonType": "string"}


def _id_validator(id_field: str) -> dict[str, Any]:
    return {
        "bsonType": "object",
        "required": ["schema_version", id_field],
        "properties": {
            "schema_version": _STRING,
            id_field: _STRING,
        },
    }


def _event_validator() -> dict[str, Any]:
    return {
        "bsonType": "object",
        "required": [
            "schema_version",
            "event_id",
            "event_type",
            "event_time_ns",
            "available_time_ns",
            "payload",
            "quality",
            "source",
        ],
        "properties": {
            "schema_version": _STRING,
            "event_id": _STRING,
            "event_type": _STRING,
            "event_time_ns": _INT_OR_LONG,
            "available_time_ns": _INT_OR_LONG,
            "instrument_id": _STRING,
            "provider_time_ns": _INT_OR_LONG,
            "received_time_ns": _INT_OR_LONG,
            "payload": {"bsonType": "object"},
            "quality": {"bsonType": "object"},
            "source": {"bsonType": "object"},
        },
    }


def _snapshot_validator() -> dict[str, Any]:
    return {
        "bsonType": "object",
        "required": ["schema_version", "snapshot_id", "decision_time_ns", "scope", "quality"],
        "properties": {
            "schema_version": _STRING,
            "snapshot_id": _STRING,
            "decision_time_ns": _INT_OR_LONG,
            "scope": {"bsonType": "object"},
            "quality": {"bsonType": "object"},
            "created_at_ns": _INT_OR_LONG,
        },
    }


def _detection_validator() -> dict[str, Any]:
    return {
        "bsonType": "object",
        "required": [
            "schema_version",
            "detection_id",
            "semantic_event_type",
            "detected_at_ns",
            "source_snapshot_ref",
            "detector_lineage",
            "scope",
            "severity",
            "reason_codes",
            "quality",
        ],
        "properties": {
            "schema_version": _STRING,
            "detection_id": _STRING,
            "semantic_event_type": _STRING,
            "detected_at_ns": _INT_OR_LONG,
            "source_snapshot_ref": {"bsonType": "object"},
            "detector_lineage": {"bsonType": "object"},
            "scope": {"bsonType": "object"},
            "severity": _STRING,
            "reason_codes": {"bsonType": "array"},
            "quality": {"bsonType": "object"},
        },
    }


def _routing_decision_validator() -> dict[str, Any]:
    return {
        "bsonType": "object",
        "required": [
            "schema_version",
            "routing_decision_id",
            "detection_ref",
            "decision_time_ns",
            "expert_domain",
            "route_action",
            "priority",
            "reason_codes",
            "required_capabilities",
            "optional_capabilities",
            "quality",
            "router_lineage",
        ],
        "properties": {
            "schema_version": _STRING,
            "routing_decision_id": _STRING,
            "detection_ref": {"bsonType": "object"},
            "decision_time_ns": _INT_OR_LONG,
            "expert_domain": _STRING,
            "route_action": _STRING,
            "priority": _STRING,
            "reason_codes": {"bsonType": "array"},
            "required_capabilities": {"bsonType": "array"},
            "optional_capabilities": {"bsonType": "array"},
            "deadline_time_ns": _INT_OR_LONG,
            "expires_at_ns": _INT_OR_LONG,
            "ttl_ns": _INT_OR_LONG,
            "quality": {"bsonType": "object"},
            "router_lineage": {"bsonType": "object"},
        },
    }


def _signal_validator() -> dict[str, Any]:
    return {
        "bsonType": "object",
        "required": [
            "schema_version",
            "signal_id",
            "signal_type",
            "scope",
            "as_of_time_ns",
            "value",
            "quality",
        ],
        "properties": {
            "schema_version": _STRING,
            "signal_id": _STRING,
            "signal_type": _STRING,
            "scope": {"bsonType": "object"},
            "as_of_time_ns": _INT_OR_LONG,
            "value": {"bsonType": ["double", "int", "long", "decimal"]},
            "quality": {"bsonType": "object"},
        },
    }


def _evidence_validator() -> dict[str, Any]:
    return {
        "bsonType": "object",
        "required": [
            "schema_version",
            "evidence_id",
            "snapshot_id",
            "expert_id",
            "scope",
            "applicability",
            "quality",
        ],
        "properties": {
            "schema_version": _STRING,
            "evidence_id": _STRING,
            "snapshot_id": _STRING,
            "expert_id": _STRING,
            "scope": {"bsonType": "object"},
            "applicability": _STRING,
            "quality": {"bsonType": "object"},
        },
    }


def _hypothesis_validator() -> dict[str, Any]:
    return {
        "bsonType": "object",
        "required": [
            "schema_version",
            "hypothesis_id",
            "hypothesis_type",
            "scope",
            "generated_at_ns",
            "snapshot_id",
            "quality",
        ],
        "properties": {
            "schema_version": _STRING,
            "hypothesis_id": _STRING,
            "hypothesis_type": _STRING,
            "scope": {"bsonType": "object"},
            "generated_at_ns": _INT_OR_LONG,
            "snapshot_id": _STRING,
            "quality": {"bsonType": "object"},
        },
    }


def _forecast_validator() -> dict[str, Any]:
    return {
        "bsonType": "object",
        "required": [
            "schema_version",
            "forecast_id",
            "scope",
            "decision_time_ns",
            "snapshot_id",
            "target",
            "horizon",
            "estimate",
            "quality",
        ],
        "properties": {
            "schema_version": _STRING,
            "forecast_id": _STRING,
            "scope": {"bsonType": "object"},
            "decision_time_ns": _INT_OR_LONG,
            "snapshot_id": _STRING,
            "target": {"bsonType": "object"},
            "horizon": {"bsonType": "object"},
            "estimate": {"bsonType": "object"},
            "quality": {"bsonType": "object"},
            "resolve_time_ns": _INT_OR_LONG,
        },
    }


def _opportunity_validator() -> dict[str, Any]:
    return {
        "bsonType": "object",
        "required": ["schema_version", "opportunity_id", "scope", "created_at_ns", "quality"],
        "properties": {
            "schema_version": _STRING,
            "opportunity_id": _STRING,
            "scope": {"bsonType": "object"},
            "created_at_ns": _INT_OR_LONG,
            "quality": {"bsonType": "object"},
            "valid_until_ns": _INT_OR_LONG,
        },
    }


def _outcome_validator() -> dict[str, Any]:
    return {
        "bsonType": "object",
        "required": [
            "schema_version",
            "outcome_id",
            "forecast_id",
            "adjudicated_at_ns",
            "resolution_status",
            "quality",
        ],
        "properties": {
            "schema_version": _STRING,
            "outcome_id": _STRING,
            "forecast_id": _STRING,
            "adjudicated_at_ns": _INT_OR_LONG,
            "resolution_status": _STRING,
            "quality": {"bsonType": "object"},
        },
    }


def _prediction_ledger_validator() -> dict[str, Any]:
    return {
        "bsonType": "object",
        "required": [
            "schema_version",
            "ledger_entry_id",
            "forecast_id",
            "forecast_ref",
            "target",
            "horizon_ns",
            "scope",
            "instrument_id",
            "forecast_decision_time_ns",
            "anchor_observation",
            "target_time_ns",
            "target_window_start_ns",
            "target_window_end_ns",
            "availability_cutoff_ns",
            "settlement_policy_identity",
            "observation_source_policy",
            "mode",
            "registered_at_ns",
        ],
        "properties": {
            "schema_version": _STRING,
            "ledger_entry_id": _STRING,
            "forecast_id": _STRING,
            "forecast_ref": {"bsonType": "object"},
            "target": {"bsonType": "object"},
            "horizon_ns": _INT_OR_LONG,
            "scope": {"bsonType": "object"},
            "instrument_id": _STRING,
            "forecast_decision_time_ns": _INT_OR_LONG,
            "anchor_observation": {"bsonType": "object"},
            "target_time_ns": _INT_OR_LONG,
            "target_window_start_ns": _INT_OR_LONG,
            "target_window_end_ns": _INT_OR_LONG,
            "availability_cutoff_ns": _INT_OR_LONG,
            "settlement_policy_identity": _STRING,
            "observation_source_policy": {"bsonType": "object"},
            "mode": _STRING,
            "registered_at_ns": _INT_OR_LONG,
            "scenario_id": _STRING,
            "lineage_refs": {"bsonType": "array"},
            "metadata": {"bsonType": "object"},
        },
    }


def _run_manifest_validator() -> dict[str, Any]:
    return {
        "bsonType": "object",
        "required": ["schema_version", "run_id", "created_at_ns", "quality"],
        "properties": {
            "schema_version": _STRING,
            "run_id": _STRING,
            "created_at_ns": _INT_OR_LONG,
            "quality": {"bsonType": "object"},
            "run_window_start_ns": _INT_OR_LONG,
            "run_window_end_ns": _INT_OR_LONG,
        },
    }


def _inference_job_validator() -> dict[str, Any]:
    return {
        "bsonType": "object",
        "required": [
            "schema_version",
            "job_id",
            "routing_decision_ref",
            "detection_ref",
            "expert_domain",
            "priority",
            "decision_time_ns",
            "submitted_at_ns",
            "deadline_time_ns",
            "expires_at_ns",
            "execution_profile_id",
            "batch_key",
            "residency_key",
            "scheduler_policy_identity",
            "scheduler_lineage",
        ],
        "properties": {
            "schema_version": _STRING,
            "job_id": _STRING,
            "routing_decision_ref": {"bsonType": "object"},
            "detection_ref": {"bsonType": "object"},
            "source_snapshot_ref": {"bsonType": "object"},
            "expert_domain": _STRING,
            "priority": _STRING,
            "decision_time_ns": _INT_OR_LONG,
            "submitted_at_ns": _INT_OR_LONG,
            "deadline_time_ns": _INT_OR_LONG,
            "expires_at_ns": _INT_OR_LONG,
            "execution_profile_id": _STRING,
            "batch_key": _STRING,
            "residency_key": _STRING,
            "adapter_key": _STRING,
            "scheduler_policy_identity": _STRING,
            "scheduler_lineage": {"bsonType": "object"},
            "required_capabilities": {"bsonType": "array"},
            "metadata": {"bsonType": "object"},
        },
    }


_VALIDATOR_BUILDERS = {
    "events": _event_validator,
    "detections": _detection_validator,
    "routing_decisions": _routing_decision_validator,
    "inference_jobs": _inference_job_validator,
    "snapshots": _snapshot_validator,
    "signals": _signal_validator,
    "evidence": _evidence_validator,
    "hypotheses": _hypothesis_validator,
    "forecasts": _forecast_validator,
    "opportunities": _opportunity_validator,
    "outcomes": _outcome_validator,
    "prediction_ledger": _prediction_ledger_validator,
    "run_manifests": _run_manifest_validator,
}


@dataclass(frozen=True, slots=True)
class MongoIndexSpec:
    name: str
    keys: list[tuple[str, int]]
    unique: bool = False


@dataclass(frozen=True, slots=True)
class MongoCollectionSpec:
    codec: RecordCodec
    validator: dict[str, Any]
    indexes: tuple[MongoIndexSpec, ...]


def _indexes_for(codec: RecordCodec) -> tuple[MongoIndexSpec, ...]:
    if codec.collection_name == "events":
        return (
            MongoIndexSpec(
                name="idx_events_available_time",
                keys=[("available_time_ns", 1)],
            ),
            MongoIndexSpec(
                name="idx_events_instrument_available_time",
                keys=[("instrument_id", 1), ("available_time_ns", 1)],
            ),
            MongoIndexSpec(
                name="idx_events_event_type_available_time",
                keys=[("event_type", 1), ("available_time_ns", 1)],
            ),
            MongoIndexSpec(
                name="idx_events_point_in_time_sort",
                keys=[
                    ("available_time_ns", 1),
                    ("received_time_ns", 1),
                    ("event_time_ns", 1),
                    ("event_id", 1),
                ],
            ),
        )
    if codec.collection_name == "snapshots":
        return (
            MongoIndexSpec(name="idx_snapshots_decision_time", keys=[("decision_time_ns", 1)]),
        )
    if codec.collection_name == "detections":
        return (
            MongoIndexSpec(name="idx_detections_snapshot", keys=[("source_snapshot_ref.id", 1), ("detected_at_ns", 1)]),
            MongoIndexSpec(name="idx_detections_event_time", keys=[("semantic_event_type", 1), ("detected_at_ns", 1)]),
        )
    if codec.collection_name == "routing_decisions":
        return (
            MongoIndexSpec(name="idx_routes_detection", keys=[("detection_ref.id", 1)]),
            MongoIndexSpec(name="idx_routes_domain_time", keys=[("expert_domain", 1), ("decision_time_ns", 1)]),
            MongoIndexSpec(name="idx_routes_expires_at", keys=[("expires_at_ns", 1)]),
        )
    if codec.collection_name == "inference_jobs":
        return (
            MongoIndexSpec(name="idx_inference_jobs_route", keys=[("routing_decision_ref.id", 1)]),
            MongoIndexSpec(name="idx_inference_jobs_detection", keys=[("detection_ref.id", 1)]),
            MongoIndexSpec(name="idx_inference_jobs_expires_at", keys=[("expires_at_ns", 1)]),
        )
    if codec.collection_name == "signals":
        return (
            MongoIndexSpec(
                name="idx_signals_scope_instrument_as_of",
                keys=[("scope.instrument_ids", 1), ("as_of_time_ns", 1)],
            ),
            MongoIndexSpec(name="idx_signals_as_of_time", keys=[("as_of_time_ns", 1)]),
        )
    if codec.collection_name == "evidence":
        return (MongoIndexSpec(name="idx_evidence_snapshot_id", keys=[("snapshot_id", 1)]),)
    if codec.collection_name == "forecasts":
        return (
            MongoIndexSpec(
                name="idx_forecasts_scope_instrument_decision_time",
                keys=[("scope.instrument_ids", 1), ("decision_time_ns", 1)],
            ),
            MongoIndexSpec(name="idx_forecasts_decision_time", keys=[("decision_time_ns", 1)]),
        )
    if codec.collection_name == "outcomes":
        return (MongoIndexSpec(name="idx_outcomes_forecast_id", keys=[("forecast_id", 1)]),)
    if codec.collection_name == "prediction_ledger":
        return (
            MongoIndexSpec(name="idx_prediction_ledger_forecast_id", keys=[("forecast_id", 1)]),
            MongoIndexSpec(name="idx_prediction_ledger_cutoff", keys=[("availability_cutoff_ns", 1)]),
        )
    if codec.collection_name == "opportunities":
        return (
            MongoIndexSpec(
                name="idx_opportunities_scope_instrument_created",
                keys=[("scope.instrument_ids", 1), ("created_at_ns", 1)],
            ),
            MongoIndexSpec(name="idx_opportunities_valid_until", keys=[("valid_until_ns", 1)]),
        )
    if codec.collection_name == "run_manifests":
        return (MongoIndexSpec(name="idx_run_manifests_created_at", keys=[("created_at_ns", 1)]),)
    return ()


def build_collection_specs() -> tuple[MongoCollectionSpec, ...]:
    specs: list[MongoCollectionSpec] = []
    for codec in RECORD_CODECS:
        builder = _VALIDATOR_BUILDERS.get(codec.collection_name)
        if builder is None:
            validator = _id_validator(codec.id_field)
        else:
            validator = builder()
        specs.append(
            MongoCollectionSpec(
                codec=codec,
                validator=validator,
                indexes=_indexes_for(codec),
            )
        )
    return tuple(specs)


COLLECTION_SPECS = build_collection_specs()


class MongoSchemaManager:
    """Idempotent Mongo schema bootstrap and drift detection."""

    def __init__(self, database: Any) -> None:
        self._database = database

    def ensure_schema(self) -> None:
        for spec in COLLECTION_SPECS:
            self._ensure_collection(spec)
            self._ensure_indexes(spec)

    def _ensure_collection(self, spec: MongoCollectionSpec) -> None:
        name = spec.codec.collection_name
        existing = self._database.list_collection_names()
        validator_doc = {"$jsonSchema": spec.validator}
        options = {
            "validator": validator_doc,
            "validationLevel": "strict",
            "validationAction": "error",
        }
        if name not in existing:
            self._database.create_collection(name, **options)
            return
        info = self._database.command("listCollections", filter={"name": name})
        first = info.get("cursor", {}).get("firstBatch", [])
        current_options = first[0].get("options", {}) if first else {}
        current_validator = current_options.get("validator")
        if current_validator != validator_doc:
            raise RepositorySchemaError(
                f"VALIDATOR_DRIFT:{name}",
                details={"collection": name, "expected": validator_doc, "actual": current_validator},
            )

    def _ensure_indexes(self, spec: MongoCollectionSpec) -> None:
        collection = self._database[spec.codec.collection_name]
        existing = {index["name"]: index for index in collection.list_indexes()}
        for index_spec in spec.indexes:
            current = existing.get(index_spec.name)
            expected_key = [(field, direction) for field, direction in index_spec.keys]
            if current is None:
                collection.create_index(
                    index_spec.keys,
                    name=index_spec.name,
                    unique=index_spec.unique,
                )
                continue
            if list(current.get("key", {}).items()) != expected_key:
                raise RepositorySchemaError(
                    f"INDEX_DRIFT:{spec.codec.collection_name}:{index_spec.name}",
                    details={
                        "collection": spec.codec.collection_name,
                        "index": index_spec.name,
                        "expected": expected_key,
                        "actual": current.get("key"),
                    },
                )
            if bool(current.get("unique")) != index_spec.unique:
                raise RepositorySchemaError(
                    f"INDEX_UNIQUE_DRIFT:{spec.codec.collection_name}:{index_spec.name}",
                    details={"collection": spec.codec.collection_name, "index": index_spec.name},
                )


__all__ = [
    "COLLECTION_SPECS",
    "MONGO_SCHEMA_PLAN_VERSION",
    "MongoCollectionSpec",
    "MongoIndexSpec",
    "MongoSchemaManager",
    "build_collection_specs",
]
