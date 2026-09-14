"""Build enrichment outbox rows from governed opportunity surfaces."""

from __future__ import annotations

from typing import Any

from ..contracts.agent_ingest import AgentBotRole
from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION, ContractReference
from ..contracts.opportunity import OpportunityV1
from ..opportunity.types import OpportunityAssessmentResult, OpportunityAssessmentV1
from .contracts import EnrichmentRequestV1, EnrichmentUrgency
from .outbox import derive_enrichment_request_id


def _primary_symbol(opportunity: OpportunityV1) -> str | None:
    instruments = opportunity.scope.instrument_ids
    if not instruments:
        return None
    return str(instruments[0])


def resolve_hard_expiry_ns(
    *,
    opportunity: OpportunityV1 | None,
    assessment: OpportunityAssessmentV1 | None,
) -> int | None:
    if opportunity is not None and opportunity.valid_until_ns is not None:
        return opportunity.valid_until_ns
    if assessment is not None and assessment.expires_at_ns is not None:
        return assessment.expires_at_ns
    return None


def build_enrichment_request_for_opportunity(
    *,
    opportunity: OpportunityV1,
    assessment: OpportunityAssessmentV1 | None,
    detected_at_ns: int,
    requested_bot_role: AgentBotRole = AgentBotRole.SENTINEL,
    urgency: EnrichmentUrgency = EnrichmentUrgency.ROUTINE,
    event_id: str | None = None,
    known_evidence_refs: tuple[ContractReference, ...] = (),
    questions: tuple[str, ...] = (),
    useful_until_ns: int | None = None,
    hard_expiry_ns: int | None = None,
) -> EnrichmentRequestV1:
    resolved_hard = hard_expiry_ns or resolve_hard_expiry_ns(
        opportunity=opportunity,
        assessment=assessment,
    )
    if resolved_hard is None:
        raise ValueError("ENRICHMENT_HARD_EXPIRY_UNKNOWN")
    resolved_useful = useful_until_ns if useful_until_ns is not None else resolved_hard
    if resolved_useful > resolved_hard:
        raise ValueError("ENRICHMENT_USEFUL_UNTIL_AFTER_HARD_EXPIRY")
    request_id = derive_enrichment_request_id(
        opportunity_id=opportunity.opportunity_id,
        requested_bot_role=requested_bot_role.value,
        event_id=event_id,
    )
    return EnrichmentRequestV1(
        request_id=request_id,
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        opportunity_id=opportunity.opportunity_id,
        detected_at_ns=detected_at_ns,
        useful_until_ns=resolved_useful,
        hard_expiry_ns=resolved_hard,
        requested_bot_role=requested_bot_role,
        urgency=urgency,
        event_id=event_id,
        entity_symbol=_primary_symbol(opportunity),
        known_evidence_refs=known_evidence_refs,
        questions=questions,
        metadata={"agent_enrichment_expected": True},
    )


def enqueue_opportunity_enrichment(
    outbox: Any,
    *,
    opportunity: OpportunityV1,
    assessment: OpportunityAssessmentV1 | None,
    detected_at_ns: int,
    **kwargs: Any,
) -> EnrichmentRequestV1:
    request = build_enrichment_request_for_opportunity(
        opportunity=opportunity,
        assessment=assessment,
        detected_at_ns=detected_at_ns,
        **kwargs,
    )
    outbox.append(request)
    return request


def maybe_enqueue_from_bridge_result(
    outbox: Any | None,
    result: OpportunityAssessmentResult,
    *,
    detected_at_ns: int,
    event_id: str | None = None,
) -> EnrichmentRequestV1 | None:
    """Warm-path hook: append outbox row when an opportunity was emitted."""

    if outbox is None or result.opportunity is None:
        return None
    from ..opportunity.types import AssessmentAction

    if result.assessment.assessment_action != AssessmentAction.EMIT:
        return None
    return enqueue_opportunity_enrichment(
        outbox,
        opportunity=result.opportunity,
        assessment=result.assessment,
        detected_at_ns=detected_at_ns,
        event_id=event_id,
    )


__all__ = [
    "build_enrichment_request_for_opportunity",
    "enqueue_opportunity_enrichment",
    "maybe_enqueue_from_bridge_result",
    "resolve_hard_expiry_ns",
]
