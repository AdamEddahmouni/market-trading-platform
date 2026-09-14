"""Agent intelligence ingest contracts — analysis-only enrichment over opportunities.

These records are append-only context from external agent workers (e.g. Grok).
They do not grant execution, Paper/Live mutation, or MODE_AUTHORITY.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .common import (
    INTELLIGENCE_SCHEMA_VERSION,
    SourceReference,
    dataclass_field_names,
    reject_unknown_keys,
    source_reference_from_dict,
    source_reference_to_dict,
    validate_id,
    validate_schema_version,
    validate_support_score,
)

AGENT_ENRICHMENT_SCHEMA_ID = "intelligence/ingest/agent_enrichment/1.0.0"


class AgentBotRole(StrEnum):
    """Narrow bot jobs — prefer Skills over broad autonomy."""

    COORDINATOR = "COORDINATOR"
    SENTINEL = "SENTINEL"
    CROWD_WATCH = "CROWD_WATCH"
    RESEARCH_SCOUT = "RESEARCH_SCOUT"
    SKEPTIC = "SKEPTIC"
    AUDITOR = "AUDITOR"


class AgentBotCapability(StrEnum):
    ORCHESTRATE = "ORCHESTRATE"
    DETECT = "DETECT"
    VERIFY = "VERIFY"
    LISTEN = "LISTEN"
    DISCOVER = "DISCOVER"
    CHALLENGE = "CHALLENGE"


_BOT_CAPABILITIES: dict[AgentBotRole, frozenset[AgentBotCapability]] = {
    AgentBotRole.COORDINATOR: frozenset({AgentBotCapability.ORCHESTRATE}),
    AgentBotRole.SENTINEL: frozenset({AgentBotCapability.DETECT, AgentBotCapability.VERIFY}),
    AgentBotRole.CROWD_WATCH: frozenset({AgentBotCapability.LISTEN}),
    AgentBotRole.RESEARCH_SCOUT: frozenset({AgentBotCapability.DISCOVER}),
    AgentBotRole.SKEPTIC: frozenset({AgentBotCapability.CHALLENGE}),
    AgentBotRole.AUDITOR: frozenset({AgentBotCapability.VERIFY}),
}


class AgentClaimType(StrEnum):
    SOURCE_ATTRIBUTION = "SOURCE_ATTRIBUTION"
    SUPPORTING_EVIDENCE = "SUPPORTING_EVIDENCE"
    CONTRADICTION = "CONTRADICTION"
    CROWD_CONTEXT = "CROWD_CONTEXT"
    HYPOTHESIS_SUGGESTION = "HYPOTHESIS_SUGGESTION"
    CHALLENGE = "CHALLENGE"
    VERIFICATION = "VERIFICATION"


class IngestOperation(StrEnum):
    """Operations an ingest worker may perform."""

    ATTACH_EVIDENCE = "ATTACH_EVIDENCE"
    ATTACH_SOURCE_CONTEXT = "ATTACH_SOURCE_CONTEXT"
    ATTACH_CONTRADICTION = "ATTACH_CONTRADICTION"
    ATTACH_CROWD_CONTEXT = "ATTACH_CROWD_CONTEXT"
    SUGGEST_HYPOTHESIS = "SUGGEST_HYPOTHESIS"
    UPDATE_OWN_EVIDENCE_RECORD = "UPDATE_OWN_EVIDENCE_RECORD"


class ForbiddenIngestMutation(StrEnum):
    """Hard-denied ingest side effects — never routed through this API."""

    PAPER_SUBMIT = "PAPER_SUBMIT"
    PAPER_CANCEL = "PAPER_CANCEL"
    PAPER_REPLACE = "PAPER_REPLACE"
    LIVE_SUBMIT = "LIVE_SUBMIT"
    LIVE_CANCEL = "LIVE_CANCEL"
    LIVE_REPLACE = "LIVE_REPLACE"
    POSITION_MUTATION = "POSITION_MUTATION"
    RISK_MUTATION = "RISK_MUTATION"
    STRATEGY_MUTATION = "STRATEGY_MUTATION"
    CREDENTIAL_MUTATION = "CREDENTIAL_MUTATION"
    MODE_AUTHORITY_MUTATION = "MODE_AUTHORITY_MUTATION"


_ALLOWED_OPERATIONS = frozenset(IngestOperation)
_FORBIDDEN_MUTATIONS = frozenset(ForbiddenIngestMutation)


def validate_ingest_operation_allowed(operation: str | IngestOperation) -> IngestOperation:
    try:
        op = IngestOperation(str(operation))
    except ValueError:
        raise ValueError("INGEST_OPERATION_UNKNOWN") from None
    if op not in _ALLOWED_OPERATIONS:
        raise ValueError("INGEST_OPERATION_NOT_ALLOWED")
    return op


def reject_forbidden_ingest_mutation(mutation: str | ForbiddenIngestMutation) -> None:
    try:
        denied = ForbiddenIngestMutation(str(mutation))
    except ValueError:
        raise ValueError("INGEST_MUTATION_UNKNOWN") from None
    if denied in _FORBIDDEN_MUTATIONS:
        raise ValueError("INGEST_MUTATION_FORBIDDEN")


def bot_role_allows_capability(role: AgentBotRole, capability: AgentBotCapability) -> bool:
    return capability in _BOT_CAPABILITIES.get(role, frozenset())


@dataclass(frozen=True, slots=True)
class AgentSkillRef:
    skill_id: str
    version: str

    def __post_init__(self) -> None:
        validate_id(self.skill_id, field_name="skill_id")
        if not self.version or not str(self.version).strip():
            raise ValueError("SKILL_VERSION_REQUIRED")


@dataclass(frozen=True, slots=True)
class AgentEnrichmentEvidenceV1:
    """Append-only agent enrichment attached to a deterministic opportunity surface.

    Distinct from EvidenceV1 (specialist model over snapshots). This record
    captures external agent claims with explicit expiry and provenance.
    """

    record_id: str
    schema_version: str
    opportunity_id: str
    retrieved_at: str
    agent_id: str
    bot_role: AgentBotRole
    skill: AgentSkillRef
    claim_type: AgentClaimType
    confidence: float
    expires_at: str
    provenance: dict[str, Any]
    operation: IngestOperation
    event_id: str | None = None
    source_refs: tuple[SourceReference, ...] = ()
    claim_body: dict[str, Any] = field(default_factory=dict)
    contradiction_refs: tuple[str, ...] = ()
    crowd_context: dict[str, Any] = field(default_factory=dict)
    hypothesis_suggestion: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_id(self.record_id, field_name="record_id")
        validate_schema_version(self.schema_version)
        validate_id(self.opportunity_id, field_name="opportunity_id")
        validate_id(self.agent_id, field_name="agent_id")
        if not self.retrieved_at:
            raise ValueError("RETRIEVED_AT_REQUIRED")
        if not self.expires_at:
            raise ValueError("EXPIRES_AT_REQUIRED")
        if not isinstance(self.bot_role, AgentBotRole):
            object.__setattr__(self, "bot_role", AgentBotRole(str(self.bot_role)))
        if not isinstance(self.claim_type, AgentClaimType):
            object.__setattr__(self, "claim_type", AgentClaimType(str(self.claim_type)))
        if not isinstance(self.operation, IngestOperation):
            object.__setattr__(self, "operation", validate_ingest_operation_allowed(self.operation))
        else:
            validate_ingest_operation_allowed(self.operation)
        validate_support_score(self.confidence)
        if self.event_id is not None:
            validate_id(self.event_id, field_name="event_id")
        if not isinstance(self.provenance, dict):
            raise ValueError("PROVENANCE_INVALID")
        if not isinstance(self.claim_body, dict):
            raise ValueError("CLAIM_BODY_INVALID")
        if not isinstance(self.crowd_context, dict):
            raise ValueError("CROWD_CONTEXT_INVALID")
        if not isinstance(self.metadata, dict):
            raise ValueError("METADATA_INVALID")
        object.__setattr__(
            self,
            "contradiction_refs",
            tuple(sorted({str(v) for v in self.contradiction_refs if str(v).strip()})),
        )


_AGENT_ENRICHMENT_ALLOWED = dataclass_field_names(AgentEnrichmentEvidenceV1)


def _skill_to_dict(skill: AgentSkillRef) -> dict[str, str]:
    return {"skill_id": skill.skill_id, "version": skill.version}


def _skill_from_dict(payload: dict[str, Any]) -> AgentSkillRef:
    return AgentSkillRef(skill_id=str(payload["skill_id"]), version=str(payload["version"]))


def agent_enrichment_evidence_v1_to_dict(record: AgentEnrichmentEvidenceV1) -> dict[str, Any]:
    body: dict[str, Any] = {
        "record_id": record.record_id,
        "schema_version": record.schema_version,
        "schema_id": AGENT_ENRICHMENT_SCHEMA_ID,
        "opportunity_id": record.opportunity_id,
        "retrieved_at": record.retrieved_at,
        "agent_id": record.agent_id,
        "bot_role": record.bot_role.value,
        "skill": _skill_to_dict(record.skill),
        "claim_type": record.claim_type.value,
        "confidence": record.confidence,
        "expires_at": record.expires_at,
        "provenance": dict(record.provenance),
        "operation": record.operation.value,
    }
    if record.event_id is not None:
        body["event_id"] = record.event_id
    if record.source_refs:
        body["source_refs"] = [source_reference_to_dict(ref) for ref in record.source_refs]
    if record.claim_body:
        body["claim_body"] = dict(record.claim_body)
    if record.contradiction_refs:
        body["contradiction_refs"] = list(record.contradiction_refs)
    if record.crowd_context:
        body["crowd_context"] = dict(record.crowd_context)
    if record.hypothesis_suggestion is not None:
        body["hypothesis_suggestion"] = record.hypothesis_suggestion
    if record.metadata:
        body["metadata"] = dict(record.metadata)
    return body


def agent_enrichment_evidence_v1_from_dict(payload: dict[str, Any]) -> AgentEnrichmentEvidenceV1:
    reject_unknown_keys(payload, _AGENT_ENRICHMENT_ALLOWED | {"schema_id"})
    return AgentEnrichmentEvidenceV1(
        record_id=str(payload["record_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        opportunity_id=str(payload["opportunity_id"]),
        retrieved_at=str(payload["retrieved_at"]),
        agent_id=str(payload["agent_id"]),
        bot_role=AgentBotRole(payload["bot_role"]),
        skill=_skill_from_dict(payload["skill"]),
        claim_type=AgentClaimType(payload["claim_type"]),
        confidence=float(payload["confidence"]),
        expires_at=str(payload["expires_at"]),
        provenance=dict(payload.get("provenance") or {}),
        operation=IngestOperation(payload["operation"]),
        event_id=payload.get("event_id"),
        source_refs=tuple(
            source_reference_from_dict(item) for item in (payload.get("source_refs") or [])
        ),
        claim_body=dict(payload.get("claim_body") or {}),
        contradiction_refs=tuple(payload.get("contradiction_refs") or ()),
        crowd_context=dict(payload.get("crowd_context") or {}),
        hypothesis_suggestion=payload.get("hypothesis_suggestion"),
        metadata=dict(payload.get("metadata") or {}),
    )


__all__ = [
    "AGENT_ENRICHMENT_SCHEMA_ID",
    "AgentBotCapability",
    "AgentBotRole",
    "AgentClaimType",
    "AgentEnrichmentEvidenceV1",
    "AgentSkillRef",
    "ForbiddenIngestMutation",
    "IngestOperation",
    "agent_enrichment_evidence_v1_from_dict",
    "agent_enrichment_evidence_v1_to_dict",
    "bot_role_allows_capability",
    "reject_forbidden_ingest_mutation",
    "validate_ingest_operation_allowed",
]
