"""Canonical record codec registry for intelligence persistence (BUILD 04.5)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from ..contracts.common import ContractKind
from ..contracts.detection import DetectionV1, detection_v1_from_dict, detection_v1_to_dict
from ..contracts.event import EventV1, event_v1_from_dict, event_v1_to_dict
from ..contracts.evidence import EvidenceV1, evidence_v1_from_dict, evidence_v1_to_dict
from ..contracts.forecast import ForecastV1, forecast_v1_from_dict, forecast_v1_to_dict
from ..contracts.hypothesis import HypothesisV1, hypothesis_v1_from_dict, hypothesis_v1_to_dict
from ..contracts.opportunity import OpportunityV1, opportunity_v1_from_dict, opportunity_v1_to_dict
from ..contracts.outcome import OutcomeV1, outcome_v1_from_dict, outcome_v1_to_dict
from ..contracts.run_manifest import RunManifestV1, run_manifest_v1_from_dict, run_manifest_v1_to_dict
from ..contracts.signal import SignalV1, signal_v1_from_dict, signal_v1_to_dict
from ..contracts.snapshot import SnapshotV1, snapshot_v1_from_dict, snapshot_v1_to_dict
from ..contracts.routing_decision import (
    RoutingDecisionV1,
    routing_decision_v1_from_dict,
    routing_decision_v1_to_dict,
)
from ..contracts.inference_job import (
    InferenceJobV1,
    inference_job_v1_from_dict,
    inference_job_v1_to_dict,
)
from .errors import RepositorySerializationError

BSON_MAX_INT64 = (1 << 63) - 1
BSON_MIN_INT64 = -(1 << 63)

PERSISTENCE_METADATA_FIELDS = frozenset({"_id"})

RecordT = (
    EventV1
    | DetectionV1
    | RoutingDecisionV1
    | InferenceJobV1
    | SnapshotV1
    | SignalV1
    | EvidenceV1
    | HypothesisV1
    | ForecastV1
    | OpportunityV1
    | OutcomeV1
    | RunManifestV1
)


@dataclass(frozen=True, slots=True)
class RecordCodec:
    """Maps a canonical contract type to persistence collection metadata."""

    kind: ContractKind
    collection_name: str
    id_field: str
    to_dict: Callable[[Any], dict[str, Any]]
    from_dict: Callable[[dict[str, Any]], Any]


def _validate_bson_integer(value: int, *, field_path: str) -> None:
    if not isinstance(value, int):
        raise RepositorySerializationError(
            f"BSON_INTEGER_REQUIRED:{field_path}",
            details={"field": field_path, "value_type": type(value).__name__},
        )
    if value < BSON_MIN_INT64 or value > BSON_MAX_INT64:
        raise RepositorySerializationError(
            f"BSON_INTEGER_OUT_OF_RANGE:{field_path}",
            details={"field": field_path, "value": value},
        )


def _walk_integers(payload: Any, *, path: str = "") -> None:
    if isinstance(payload, bool):
        return
    if isinstance(payload, int):
        _validate_bson_integer(payload, field_path=path or "root")
        return
    if isinstance(payload, dict):
        for key, value in payload.items():
            child = f"{path}.{key}" if path else str(key)
            _walk_integers(value, path=child)
        return
    if isinstance(payload, list):
        for index, item in enumerate(payload):
            _walk_integers(item, path=f"{path}[{index}]")


def canonical_body(record: RecordT) -> dict[str, Any]:
    """Return authoritative BUILD 01 serialized dict for a record."""
    codec = codec_for_record(record)
    return codec.to_dict(record)


def canonical_semantic_equal(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Compare canonical serialized bodies ignoring persistence metadata."""
    left_clean = {k: v for k, v in left.items() if k not in PERSISTENCE_METADATA_FIELDS}
    right_clean = {k: v for k, v in right.items() if k not in PERSISTENCE_METADATA_FIELDS}
    return json.dumps(left_clean, sort_keys=True, separators=(",", ":")) == json.dumps(
        right_clean, sort_keys=True, separators=(",", ":")
    )


def encode_document(record: RecordT) -> dict[str, Any]:
    """Encode a domain record for MongoDB insertion."""
    codec = codec_for_record(record)
    body = codec.to_dict(record)
    _walk_integers(body)
    document = dict(body)
    document["_id"] = body[codec.id_field]
    return document


def decode_document(document: dict[str, Any], codec: RecordCodec) -> RecordT:
    """Decode a Mongo document into a domain record."""
    payload = {k: v for k, v in document.items() if k not in PERSISTENCE_METADATA_FIELDS}
    try:
        return codec.from_dict(payload)
    except (KeyError, TypeError, ValueError) as exc:
        from .errors import RepositoryValidationError

        raise RepositoryValidationError(
            f"DOMAIN_DESERIALIZATION_FAILED:{codec.kind}",
            details={"kind": codec.kind.value, "reason": str(exc)},
        ) from exc


def codec_for_record(record: RecordT) -> RecordCodec:
    for codec in RECORD_CODECS:
        if isinstance(record, _KIND_TO_TYPE[codec.kind]):
            return codec
    raise TypeError(f"UNSUPPORTED_RECORD_TYPE:{type(record).__name__}")


def codec_for_kind(kind: ContractKind) -> RecordCodec:
    for codec in RECORD_CODECS:
        if codec.kind == kind:
            return codec
    raise KeyError(f"UNSUPPORTED_RECORD_KIND:{kind}")


_KIND_TO_TYPE: dict[ContractKind, type] = {
    ContractKind.EVENT: EventV1,
    ContractKind.DETECTION: DetectionV1,
    ContractKind.ROUTING_DECISION: RoutingDecisionV1,
    ContractKind.INFERENCE_JOB: InferenceJobV1,
    ContractKind.SNAPSHOT: SnapshotV1,
    ContractKind.SIGNAL: SignalV1,
    ContractKind.EVIDENCE: EvidenceV1,
    ContractKind.HYPOTHESIS: HypothesisV1,
    ContractKind.FORECAST: ForecastV1,
    ContractKind.OPPORTUNITY: OpportunityV1,
    ContractKind.OUTCOME: OutcomeV1,
    ContractKind.RUN_MANIFEST: RunManifestV1,
}

RECORD_CODECS: tuple[RecordCodec, ...] = (
    RecordCodec(
        kind=ContractKind.EVENT,
        collection_name="events",
        id_field="event_id",
        to_dict=event_v1_to_dict,
        from_dict=event_v1_from_dict,
    ),
    RecordCodec(
        kind=ContractKind.DETECTION,
        collection_name="detections",
        id_field="detection_id",
        to_dict=detection_v1_to_dict,
        from_dict=detection_v1_from_dict,
    ),
    RecordCodec(
        kind=ContractKind.ROUTING_DECISION,
        collection_name="routing_decisions",
        id_field="routing_decision_id",
        to_dict=routing_decision_v1_to_dict,
        from_dict=routing_decision_v1_from_dict,
    ),
    RecordCodec(
        kind=ContractKind.INFERENCE_JOB,
        collection_name="inference_jobs",
        id_field="job_id",
        to_dict=inference_job_v1_to_dict,
        from_dict=inference_job_v1_from_dict,
    ),
    RecordCodec(
        kind=ContractKind.SNAPSHOT,
        collection_name="snapshots",
        id_field="snapshot_id",
        to_dict=snapshot_v1_to_dict,
        from_dict=snapshot_v1_from_dict,
    ),
    RecordCodec(
        kind=ContractKind.SIGNAL,
        collection_name="signals",
        id_field="signal_id",
        to_dict=signal_v1_to_dict,
        from_dict=signal_v1_from_dict,
    ),
    RecordCodec(
        kind=ContractKind.EVIDENCE,
        collection_name="evidence",
        id_field="evidence_id",
        to_dict=evidence_v1_to_dict,
        from_dict=evidence_v1_from_dict,
    ),
    RecordCodec(
        kind=ContractKind.HYPOTHESIS,
        collection_name="hypotheses",
        id_field="hypothesis_id",
        to_dict=hypothesis_v1_to_dict,
        from_dict=hypothesis_v1_from_dict,
    ),
    RecordCodec(
        kind=ContractKind.FORECAST,
        collection_name="forecasts",
        id_field="forecast_id",
        to_dict=forecast_v1_to_dict,
        from_dict=forecast_v1_from_dict,
    ),
    RecordCodec(
        kind=ContractKind.OPPORTUNITY,
        collection_name="opportunities",
        id_field="opportunity_id",
        to_dict=opportunity_v1_to_dict,
        from_dict=opportunity_v1_from_dict,
    ),
    RecordCodec(
        kind=ContractKind.OUTCOME,
        collection_name="outcomes",
        id_field="outcome_id",
        to_dict=outcome_v1_to_dict,
        from_dict=outcome_v1_from_dict,
    ),
    RecordCodec(
        kind=ContractKind.RUN_MANIFEST,
        collection_name="run_manifests",
        id_field="run_id",
        to_dict=run_manifest_v1_to_dict,
        from_dict=run_manifest_v1_from_dict,
    ),
)

MONGO_SCHEMA_PLAN_VERSION = 3

CODEC_BY_TYPE = {_KIND_TO_TYPE[codec.kind]: codec for codec in RECORD_CODECS}


__all__ = [
    "CODEC_BY_TYPE",
    "BSON_MIN_INT64",
    "MONGO_SCHEMA_PLAN_VERSION",
    "PERSISTENCE_METADATA_FIELDS",
    "RECORD_CODECS",
    "RecordCodec",
    "RecordT",
    "canonical_body",
    "canonical_semantic_equal",
    "codec_for_kind",
    "codec_for_record",
    "decode_document",
    "encode_document",
]
