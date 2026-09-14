"""Append-only async agent enrichment request contracts (outbox plane)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..contracts.agent_ingest import AgentBotRole
from ..contracts.common import (
    INTELLIGENCE_SCHEMA_VERSION,
    ContractReference,
    contract_reference_from_dict,
    contract_reference_to_dict,
    dataclass_field_names,
    reject_unknown_keys,
    validate_id,
    validate_schema_version,
    validate_timestamp_ns,
)

ENRICHMENT_REQUEST_SCHEMA_ID = "intelligence/enrichment/request/1.0.0"


class EnrichmentUrgency(StrEnum):
    ROUTINE = "ROUTINE"
    ELEVATED = "ELEVATED"
    TIME_SENSITIVE = "TIME_SENSITIVE"


@dataclass(frozen=True, slots=True)
class EnrichmentRequestV1:
    """Warm-path outbox row: ask an external agent to enrich an existing opportunity."""

    request_id: str
    schema_version: str
    opportunity_id: str
    detected_at_ns: int
    useful_until_ns: int
    hard_expiry_ns: int
    requested_bot_role: AgentBotRole
    urgency: EnrichmentUrgency = EnrichmentUrgency.ROUTINE
    event_id: str | None = None
    entity_symbol: str | None = None
    known_evidence_refs: tuple[ContractReference, ...] = ()
    questions: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_id(self.request_id, field_name="request_id")
        validate_schema_version(self.schema_version)
        validate_id(self.opportunity_id, field_name="opportunity_id")
        validate_timestamp_ns(self.detected_at_ns, field_name="detected_at_ns")
        validate_timestamp_ns(self.useful_until_ns, field_name="useful_until_ns")
        validate_timestamp_ns(self.hard_expiry_ns, field_name="hard_expiry_ns")
        if self.useful_until_ns > self.hard_expiry_ns:
            raise ValueError("ENRICHMENT_USEFUL_UNTIL_AFTER_HARD_EXPIRY")
        if self.event_id is not None:
            validate_id(self.event_id, field_name="event_id")
        if not isinstance(self.requested_bot_role, AgentBotRole):
            object.__setattr__(self, "requested_bot_role", AgentBotRole(str(self.requested_bot_role)))
        if not isinstance(self.urgency, EnrichmentUrgency):
            object.__setattr__(self, "urgency", EnrichmentUrgency(str(self.urgency)))
        if not isinstance(self.metadata, dict):
            raise ValueError("ENRICHMENT_METADATA_INVALID")
        object.__setattr__(
            self,
            "questions",
            tuple(str(q).strip() for q in self.questions if str(q).strip()),
        )


_ENRICHMENT_REQUEST_ALLOWED = dataclass_field_names(EnrichmentRequestV1)


def enrichment_request_v1_to_dict(record: EnrichmentRequestV1) -> dict[str, Any]:
    body: dict[str, Any] = {
        "request_id": record.request_id,
        "schema_version": record.schema_version,
        "schema_id": ENRICHMENT_REQUEST_SCHEMA_ID,
        "opportunity_id": record.opportunity_id,
        "detected_at_ns": record.detected_at_ns,
        "useful_until_ns": record.useful_until_ns,
        "hard_expiry_ns": record.hard_expiry_ns,
        "requested_bot_role": record.requested_bot_role.value,
        "urgency": record.urgency.value,
    }
    if record.event_id is not None:
        body["event_id"] = record.event_id
    if record.entity_symbol is not None:
        body["entity_symbol"] = record.entity_symbol
    if record.known_evidence_refs:
        body["known_evidence_refs"] = [
            contract_reference_to_dict(ref) for ref in record.known_evidence_refs
        ]
    if record.questions:
        body["questions"] = list(record.questions)
    if record.metadata:
        body["metadata"] = dict(record.metadata)
    return body


def enrichment_request_v1_from_dict(payload: dict[str, Any]) -> EnrichmentRequestV1:
    reject_unknown_keys(payload, _ENRICHMENT_REQUEST_ALLOWED | {"schema_id"})
    refs = tuple(
        contract_reference_from_dict(row)
        for row in (payload.get("known_evidence_refs") or ())
        if isinstance(row, dict)
    )
    return EnrichmentRequestV1(
        request_id=str(payload["request_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        opportunity_id=str(payload["opportunity_id"]),
        detected_at_ns=int(payload["detected_at_ns"]),
        useful_until_ns=int(payload["useful_until_ns"]),
        hard_expiry_ns=int(payload["hard_expiry_ns"]),
        requested_bot_role=AgentBotRole(payload["requested_bot_role"]),
        urgency=EnrichmentUrgency(payload.get("urgency", EnrichmentUrgency.ROUTINE.value)),
        event_id=payload.get("event_id"),
        entity_symbol=payload.get("entity_symbol"),
        known_evidence_refs=refs,
        questions=tuple(str(q) for q in (payload.get("questions") or ())),
        metadata=dict(payload.get("metadata") or {}),
    )


__all__ = [
    "ENRICHMENT_REQUEST_SCHEMA_ID",
    "EnrichmentRequestV1",
    "EnrichmentUrgency",
    "enrichment_request_v1_from_dict",
    "enrichment_request_v1_to_dict",
]
