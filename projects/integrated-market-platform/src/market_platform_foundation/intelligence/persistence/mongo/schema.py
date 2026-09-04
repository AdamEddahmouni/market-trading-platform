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


def _strategy_match_validator() -> dict[str, Any]:
    return {
        "bsonType": "object",
        "required": [
            "schema_version",
            "match_id",
            "strategy_id",
            "strategy_identity_hash",
            "match_identity_hash",
            "scope",
            "decision_time_ns",
            "disposition",
            "capability_state",
            "quality",
            "condition_results",
        ],
        "properties": {
            "schema_version": _STRING,
            "match_id": _STRING,
            "strategy_id": _STRING,
            "strategy_identity_hash": _STRING,
            "match_identity_hash": _STRING,
            "scope": {"bsonType": "object"},
            "decision_time_ns": _INT_OR_LONG,
            "disposition": _STRING,
            "capability_state": _STRING,
            "quality": {"bsonType": "object"},
            "source_snapshot_ref": {"bsonType": "object"},
            "source_evidence_refs": {"bsonType": "array"},
            "source_signal_refs": {"bsonType": "array"},
            "condition_results": {"bsonType": "array"},
            "rejection_reasons": {"bsonType": "array"},
            "abstention_reasons": {"bsonType": "array"},
            "unavailability_reasons": {"bsonType": "array"},
            "regime": _STRING,
            "context": {"bsonType": "object"},
            "source_forecast_refs": {"bsonType": "array"},
            "valid_from_ns": _INT_OR_LONG,
            "expires_at_ns": _INT_OR_LONG,
            "lineage_refs": {"bsonType": "array"},
            "correlation_id": _STRING,
        },
    }


def _strategy_attribution_validator() -> dict[str, Any]:
    return {
        "bsonType": "object",
        "required": [
            "schema_version",
            "attribution_id",
            "account_id",
            "mode",
            "instrument_id",
            "allocation_ref",
            "strategy_match_ref",
            "strategy_id",
            "strategy_identity_hash",
            "allocation_quantity",
            "allocation_direction",
            "allocation_time_ns",
            "point_in_time_ns",
            "fills",
            "execution_refs",
            "fill_refs",
            "forecast_refs",
            "prediction_outcome_refs",
            "materialization_semantics",
            "coverage_algorithm_version",
            "prediction_outcome_kind",
            "trading_outcome_kind",
            "initial_position_quantity",
            "initial_cost_basis_minor",
            "created_at_ns",
        ],
        "properties": {
            "schema_version": _STRING,
            "attribution_id": _STRING,
            "account_id": _STRING,
            "mode": _STRING,
            "instrument_id": _STRING,
            "allocation_ref": {"bsonType": "object"},
            "intent_ref": {"bsonType": "object"},
            "opportunity_ref": {"bsonType": "object"},
            "cluster_thesis_ref": {"bsonType": "object"},
            "strategy_match_ref": {"bsonType": "object"},
            "strategy_id": _STRING,
            "strategy_identity_hash": _STRING,
            "allocation_quantity": _INT_OR_LONG,
            "allocation_direction": _STRING,
            "allocation_time_ns": _INT_OR_LONG,
            "point_in_time_ns": _INT_OR_LONG,
            "fills": {"bsonType": "array"},
            "execution_refs": {"bsonType": "array"},
            "fill_refs": {"bsonType": "array"},
            "forecast_refs": {"bsonType": "array"},
            "prediction_outcome_refs": {"bsonType": "array"},
            "materialization_semantics": _STRING,
            "coverage_algorithm_version": _STRING,
            "prediction_outcome_kind": _STRING,
            "trading_outcome_kind": _STRING,
            "initial_position_quantity": _INT_OR_LONG,
            "initial_cost_basis_minor": _INT_OR_LONG,
            "created_at_ns": _INT_OR_LONG,
            "identity_hash": _STRING,
        },
    }


def _allocation_decision_validator() -> dict[str, Any]:
    return {
        "bsonType": "object",
        "required": [
            "schema_version",
            "allocation_decision_id",
            "decision_set_id",
            "status",
            "account_id",
            "mode",
            "decision_time_ns",
            "currency",
            "scale",
            "opportunity_ref",
            "cluster_ref",
            "economic_assessment_ref",
            "portfolio_snapshot_ref",
            "comparison_id",
            "rank",
            "competing_opportunity_refs",
            "comparison_constraints",
            "allocation_constraints",
            "comparison_vector",
            "allocated_capital",
            "allocated_buying_power",
            "allocated_maximum_loss",
            "reason_codes",
        ],
        "properties": {
            "schema_version": _STRING,
            "allocation_decision_id": _STRING,
            "decision_set_id": _STRING,
            "status": _STRING,
            "account_id": _STRING,
            "mode": _STRING,
            "decision_time_ns": _INT_OR_LONG,
            "currency": _STRING,
            "scale": _INT_OR_LONG,
            "opportunity_ref": {"bsonType": "object"},
            "cluster_ref": {"bsonType": "object"},
            "economic_assessment_ref": {"bsonType": "object"},
            "strategy_match_ref": {"bsonType": ["object", "null"]},
            "forecast_refs": {"bsonType": "array"},
            "allocation_intent_ref": {"bsonType": ["object", "null"]},
            "portfolio_snapshot_ref": {"bsonType": "object"},
            "comparison_id": _STRING,
            "comparator_version": _STRING,
            "allocator_version": _STRING,
            "rank": _INT_OR_LONG,
            "competing_opportunity_refs": {"bsonType": "array"},
            "comparison_constraints": {"bsonType": "object"},
            "allocation_constraints": {"bsonType": "object"},
            "comparison_vector": {"bsonType": "object"},
            "requested_capital": {"bsonType": ["object", "null"]},
            "requested_buying_power": {"bsonType": ["object", "null"]},
            "requested_maximum_loss": {"bsonType": ["object", "null"]},
            "allocated_capital": {"bsonType": "object"},
            "allocated_buying_power": {"bsonType": "object"},
            "allocated_maximum_loss": {"bsonType": "object"},
            "reason_codes": {"bsonType": "array"},
            "lineage_refs": {"bsonType": "array"},
            "source_refs": {"bsonType": "array"},
            "implementation_version": _STRING,
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


def _order_ready_validator() -> dict[str, Any]:
    return {
        "bsonType": "object",
        "required": [
            "order_ready_id",
            "schema_version",
            "allocation_decision_id",
            "trade_proposal_id",
            "risk_decision_id",
            "account_id",
            "mode",
            "decision_time_ns",
            "instrument_id",
            "symbol",
            "approved_quantity",
            "approved_notional_minor",
            "status",
            "execution_authority",
            "execution_mode",
            "idempotency_key",
            "correlation_id",
            "reason_codes",
            "lineage_refs",
        ],
        "properties": {
            "order_ready_id": _STRING,
            "schema_version": _STRING,
            "allocation_decision_id": _STRING,
            "trade_proposal_id": _STRING,
            "risk_decision_id": _STRING,
            "account_id": _STRING,
            "mode": _STRING,
            "decision_time_ns": _INT_OR_LONG,
            "instrument_id": _STRING,
            "symbol": _STRING,
            "approved_quantity": _INT_OR_LONG,
            "approved_notional_minor": _INT_OR_LONG,
            "status": _STRING,
            "execution_authority": _STRING,
            "execution_mode": _STRING,
            "idempotency_key": _STRING,
            "correlation_id": _STRING,
            "reason_codes": {"bsonType": "array"},
            "lineage_refs": {"bsonType": "array"},
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
    "strategy_matches": _strategy_match_validator,
    "strategy_attributions": _strategy_attribution_validator,
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


ALLOCATION_DECISION_VALIDATOR = _allocation_decision_validator()
ALLOCATION_DECISION_INDEXES = (
    MongoIndexSpec(
        name="idx_allocation_decisions_decision_set",
        keys=[("decision_set_id", 1), ("rank", 1)],
    ),
    MongoIndexSpec(
        name="idx_allocation_decisions_account_mode",
        keys=[("account_id", 1), ("mode", 1), ("decision_time_ns", 1)],
    ),
)
ORDER_READY_VALIDATOR = _order_ready_validator()
ORDER_READY_INDEXES = (
    MongoIndexSpec(
        name="idx_order_ready_allocation",
        keys=[("allocation_decision_id", 1)],
    ),
    MongoIndexSpec(
        name="idx_order_ready_risk",
        keys=[("risk_decision_id", 1)],
    ),
)


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
    if codec.collection_name == "strategy_matches":
        return (
            MongoIndexSpec(
                name="idx_strategy_matches_strategy_decision",
                keys=[("strategy_id", 1), ("decision_time_ns", 1)],
            ),
            MongoIndexSpec(
                name="idx_strategy_matches_scope_decision",
                keys=[("scope.instrument_ids", 1), ("decision_time_ns", 1)],
            ),
            MongoIndexSpec(name="idx_strategy_matches_expires_at", keys=[("expires_at_ns", 1)]),
        )
    if codec.collection_name == "strategy_attributions":
        return (
            MongoIndexSpec(
                name="idx_strategy_attributions_allocation",
                keys=[("allocation_ref.kind", 1), ("allocation_ref.id", 1)],
            ),
            MongoIndexSpec(
                name="idx_strategy_attributions_account_mode",
                keys=[("account_id", 1), ("mode", 1), ("point_in_time_ns", 1)],
            ),
            MongoIndexSpec(
                name="idx_strategy_attributions_strategy",
                keys=[("strategy_id", 1), ("allocation_time_ns", 1)],
            ),
            MongoIndexSpec(
                name="idx_strategy_attributions_fill",
                keys=[("fill_refs.id", 1)],
            ),
        )
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
        self._ensure_named_collection(
            "allocation_decisions",
            ALLOCATION_DECISION_VALIDATOR,
        )
        self._ensure_named_indexes("allocation_decisions", ALLOCATION_DECISION_INDEXES)
        self._ensure_named_collection("order_ready", ORDER_READY_VALIDATOR)
        self._ensure_named_indexes("order_ready", ORDER_READY_INDEXES)

    def _ensure_collection(self, spec: MongoCollectionSpec) -> None:
        self._ensure_named_collection(spec.codec.collection_name, spec.validator)

    def _ensure_named_collection(self, name: str, validator: dict[str, Any]) -> None:
        existing = self._database.list_collection_names()
        validator_doc = {"$jsonSchema": validator}
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
        self._ensure_named_indexes(spec.codec.collection_name, spec.indexes)

    def _ensure_named_indexes(
        self,
        collection_name: str,
        indexes: tuple[MongoIndexSpec, ...],
    ) -> None:
        collection = self._database[collection_name]
        existing = {index["name"]: index for index in collection.list_indexes()}
        for index_spec in indexes:
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
                    f"INDEX_DRIFT:{collection_name}:{index_spec.name}",
                    details={
                        "collection": collection_name,
                        "index": index_spec.name,
                        "expected": expected_key,
                        "actual": current.get("key"),
                    },
                )
            if bool(current.get("unique")) != index_spec.unique:
                raise RepositorySchemaError(
                    f"INDEX_UNIQUE_DRIFT:{collection_name}:{index_spec.name}",
                    details={"collection": collection_name, "index": index_spec.name},
                )


__all__ = [
    "ALLOCATION_DECISION_INDEXES",
    "ALLOCATION_DECISION_VALIDATOR",
    "COLLECTION_SPECS",
    "MONGO_SCHEMA_PLAN_VERSION",
    "MongoCollectionSpec",
    "MongoIndexSpec",
    "MongoSchemaManager",
    "ORDER_READY_INDEXES",
    "ORDER_READY_VALIDATOR",
    "build_collection_specs",
]
