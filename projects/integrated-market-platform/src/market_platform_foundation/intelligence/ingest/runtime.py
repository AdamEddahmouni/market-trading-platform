"""Validate → idempotency → persist → retrieve → attach (detail-only) → expire."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Callable, Protocol, runtime_checkable

from ..contracts.opportunity import OpportunityV1

from .boundary import (
    validate_agent_enrichment_ingest_payload,
    validate_agent_enrichment_record_policy,
)
from ..contracts.agent_ingest import (
    AGENT_ENRICHMENT_SCHEMA_ID,
    AgentClaimType,
    AgentEnrichmentEvidenceV1,
    ForbiddenIngestMutation,
    IngestOperation,
    agent_enrichment_evidence_v1_from_dict,
    agent_enrichment_evidence_v1_to_dict,
    reject_forbidden_ingest_mutation,
    validate_ingest_operation_allowed,
)
from ..persistence.repository import RepositoryPutResult

AGENT_ENRICHMENT_LINEAGE_KIND = "agent_enrichment_evidence"

_CLAIM_TO_OPERATION: dict[AgentClaimType, IngestOperation] = {
    AgentClaimType.SUPPORTING_EVIDENCE: IngestOperation.ATTACH_EVIDENCE,
    AgentClaimType.SOURCE_ATTRIBUTION: IngestOperation.ATTACH_SOURCE_CONTEXT,
    AgentClaimType.CONTRADICTION: IngestOperation.ATTACH_CONTRADICTION,
    AgentClaimType.CROWD_CONTEXT: IngestOperation.ATTACH_CROWD_CONTEXT,
    AgentClaimType.HYPOTHESIS_SUGGESTION: IngestOperation.SUGGEST_HYPOTHESIS,
    AgentClaimType.CHALLENGE: IngestOperation.ATTACH_CONTRADICTION,
    AgentClaimType.VERIFICATION: IngestOperation.ATTACH_EVIDENCE,
}

_FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {
        "paper_submit",
        "live_submit",
        "mode_authority",
        "execution_mode",
        "order_draft",
        "position_mutation",
        "risk_mutation",
        "strategy_mutation",
        "credential_mutation",
    }
)


class IngestDisposition(StrEnum):
    INSERTED = "INSERTED"
    ALREADY_PRESENT = "ALREADY_PRESENT"
    UPDATED = "UPDATED"
    RESEARCH_ONLY_LATE_RESULT = "RESEARCH_ONLY_LATE_RESULT"


RESEARCH_ONLY_LATE_RESULT = IngestDisposition.RESEARCH_ONLY_LATE_RESULT.value


@dataclass(frozen=True, slots=True)
class AgentEnrichmentIngestResult:
    disposition: IngestDisposition
    record_id: str
    opportunity_id: str
    schema_id: str = AGENT_ENRICHMENT_SCHEMA_ID


@runtime_checkable
class AgentEnrichmentPersistence(Protocol):
    def put_agent_enrichment_evidence(
        self,
        record: AgentEnrichmentEvidenceV1,
        *,
        allow_agent_update: bool = False,
    ) -> RepositoryPutResult: ...

    def get_agent_enrichment_evidence(self, record_id: str) -> AgentEnrichmentEvidenceV1 | None: ...

    def list_agent_enrichment_by_opportunity(
        self, opportunity_id: str
    ) -> tuple[AgentEnrichmentEvidenceV1, ...]: ...


def _parse_iso8601(value: str) -> datetime:
    normalized = str(value).strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def is_agent_enrichment_expired(record: AgentEnrichmentEvidenceV1, *, as_of_iso: str) -> bool:
    as_of = _parse_iso8601(as_of_iso)
    expires = _parse_iso8601(record.expires_at)
    return expires <= as_of


def _as_of_ns(as_of_iso: str) -> int:
    parsed = _parse_iso8601(as_of_iso)
    return int(parsed.timestamp() * 1_000_000_000)


def _is_past_hard_expiry(
    opportunity: OpportunityV1 | None,
    *,
    as_of_ns: int,
    hard_expiry_ns: int | None = None,
) -> bool:
    resolved = hard_expiry_ns
    if resolved is None and opportunity is not None:
        resolved = opportunity.valid_until_ns
    if resolved is None:
        return False
    return as_of_ns >= resolved


_FORBIDDEN_MUTATION_VALUES = frozenset(item.value for item in ForbiddenIngestMutation)
_MAX_NESTED_SCAN_DEPTH = 32


def _scan_forbidden_mutations(payload: dict[str, Any]) -> None:
    _scan_forbidden_value(payload, depth=0)


def _scan_forbidden_value(value: Any, *, depth: int) -> None:
    if depth > _MAX_NESTED_SCAN_DEPTH:
        raise ValueError("INGEST_PAYLOAD_TOO_DEEP")
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if lowered in _FORBIDDEN_PAYLOAD_KEYS:
                raise ValueError("INGEST_MUTATION_FORBIDDEN")
            if str(key) in {"requested_mutation", "mutation"} and child is not None:
                reject_forbidden_ingest_mutation(str(child))
            if str(key) == "operation" and str(child) in _FORBIDDEN_MUTATION_VALUES:
                reject_forbidden_ingest_mutation(str(child))
            _scan_forbidden_value(child, depth=depth + 1)
        return
    if isinstance(value, list):
        for item in value:
            _scan_forbidden_value(item, depth=depth + 1)
        return
    if isinstance(value, str) and value in _FORBIDDEN_MUTATION_VALUES:
        reject_forbidden_ingest_mutation(value)


def _validate_claim_operation_alignment(record: AgentEnrichmentEvidenceV1) -> None:
    validate_ingest_operation_allowed(record.operation)
    if record.operation == IngestOperation.UPDATE_OWN_EVIDENCE_RECORD:
        return
    expected = _CLAIM_TO_OPERATION.get(record.claim_type)
    if expected is not None and record.operation != expected:
        raise ValueError("INGEST_CLAIM_OPERATION_MISMATCH")


class AgentEnrichmentIngestRuntime:
    """Smallest safe ingest plane: enrichment records only, no execution authority."""

    def __init__(
        self,
        repository: AgentEnrichmentPersistence,
        *,
        get_opportunity: Callable[[str], OpportunityV1 | None] | None = None,
    ) -> None:
        self._repository = repository
        self._get_opportunity = get_opportunity

    def _require_attachable_opportunity(self, opportunity_id: str) -> None:
        if self._get_opportunity is None:
            raise ValueError("AGENT_ENRICHMENT_OPPORTUNITY_VALIDATION_UNAVAILABLE")
        if self._get_opportunity(opportunity_id) is None:
            raise ValueError("OPPORTUNITY_NOT_FOUND")

    def ingest(
        self,
        payload: dict[str, Any],
        *,
        as_of_iso: str,
        existing_record: AgentEnrichmentEvidenceV1 | None = None,
    ) -> AgentEnrichmentIngestResult:
        _scan_forbidden_mutations(payload)
        validate_agent_enrichment_ingest_payload(payload)
        record = agent_enrichment_evidence_v1_from_dict(payload)
        validate_agent_enrichment_record_policy(record)
        _validate_claim_operation_alignment(record)
        opportunity = None
        if self._get_opportunity is not None:
            opportunity = self._get_opportunity(record.opportunity_id)
        self._require_attachable_opportunity(record.opportunity_id)
        late_research_only = False
        if is_agent_enrichment_expired(record, as_of_iso=as_of_iso):
            as_of_ns = _as_of_ns(as_of_iso)
            if _is_past_hard_expiry(opportunity, as_of_ns=as_of_ns):
                late_research_only = True
                record = replace(
                    record,
                    metadata={
                        **dict(record.metadata),
                        "ingest_disposition": RESEARCH_ONLY_LATE_RESULT,
                    },
                )
            else:
                raise ValueError("AGENT_ENRICHMENT_ALREADY_EXPIRED")
        allow_update = record.operation == IngestOperation.UPDATE_OWN_EVIDENCE_RECORD
        if allow_update:
            if existing_record is None:
                existing_record = self._repository.get_agent_enrichment_evidence(record.record_id)
            if existing_record is None:
                raise ValueError("AGENT_ENRICHMENT_UPDATE_TARGET_MISSING")
            if existing_record.agent_id != record.agent_id:
                raise ValueError("AGENT_ENRICHMENT_UPDATE_AGENT_MISMATCH")
        prior = self._repository.get_agent_enrichment_evidence(record.record_id)
        if prior is not None and not allow_update:
            if agent_enrichment_evidence_v1_to_dict(prior) == agent_enrichment_evidence_v1_to_dict(record):
                return AgentEnrichmentIngestResult(
                    disposition=IngestDisposition.ALREADY_PRESENT,
                    record_id=record.record_id,
                    opportunity_id=record.opportunity_id,
                )
            raise ValueError("AGENT_ENRICHMENT_IMMUTABLE_CONFLICT")
        result = self._repository.put_agent_enrichment_evidence(
            record,
            allow_agent_update=allow_update,
        )
        if late_research_only:
            disposition = IngestDisposition.RESEARCH_ONLY_LATE_RESULT
        elif result == RepositoryPutResult.ALREADY_PRESENT:
            disposition = IngestDisposition.ALREADY_PRESENT
        elif allow_update and prior is not None:
            disposition = IngestDisposition.UPDATED
        else:
            disposition = IngestDisposition.INSERTED
        return AgentEnrichmentIngestResult(
            disposition=disposition,
            record_id=record.record_id,
            opportunity_id=record.opportunity_id,
        )

    def retrieve(self, record_id: str) -> AgentEnrichmentEvidenceV1 | None:
        return self._repository.get_agent_enrichment_evidence(record_id)

    def list_active_for_opportunity(
        self,
        opportunity_id: str,
        *,
        as_of_iso: str,
    ) -> tuple[AgentEnrichmentEvidenceV1, ...]:
        rows = self._repository.list_agent_enrichment_by_opportunity(opportunity_id)
        active = tuple(
            row for row in rows if not is_agent_enrichment_expired(row, as_of_iso=as_of_iso)
        )
        return tuple(sorted(active, key=lambda row: (row.retrieved_at, row.record_id)))


def enrichments_for_opportunity_detail(
    runtime: AgentEnrichmentIngestRuntime,
    *,
    opportunity_id: str,
    as_of_iso: str,
    base_lineage_refs: tuple[dict[str, Any], ...] | list[dict[str, Any]],
    base_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Detail-only attach: never used by summary/rank assembly."""

    active = runtime.list_active_for_opportunity(opportunity_id, as_of_iso=as_of_iso)
    lineage = list(base_lineage_refs)
    seen = {(str(item.get("kind")), str(item.get("id"))) for item in lineage if isinstance(item, dict)}
    for record in active:
        key = (AGENT_ENRICHMENT_LINEAGE_KIND, record.record_id)
        if key in seen:
            continue
        seen.add(key)
        lineage.append({"kind": AGENT_ENRICHMENT_LINEAGE_KIND, "id": record.record_id})
    metadata = dict(base_metadata or {})
    metadata["agent_enrichment"] = {
        "schema_id": AGENT_ENRICHMENT_SCHEMA_ID,
        "record_ids": [row.record_id for row in active],
        "count": len(active),
    }
    return {
        "lineage_refs": lineage,
        "metadata": metadata,
        "agent_enrichment_records": [
            agent_enrichment_evidence_v1_to_dict(row) for row in active
        ],
    }


__all__ = [
    "AGENT_ENRICHMENT_LINEAGE_KIND",
    "AgentEnrichmentIngestResult",
    "AgentEnrichmentIngestRuntime",
    "AgentEnrichmentPersistence",
    "IngestDisposition",
    "RESEARCH_ONLY_LATE_RESULT",
    "enrichments_for_opportunity_detail",
    "is_agent_enrichment_expired",
]
