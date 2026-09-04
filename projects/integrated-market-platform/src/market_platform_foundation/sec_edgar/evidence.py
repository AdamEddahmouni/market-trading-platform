"""Reuse Market Context CatalystEvidence. Filing type is not sentiment."""

from __future__ import annotations

from ..contracts.market_context import CatalystEvidence, PublicationState
from ..contracts.participant import infer_action_from_form4_transaction
from .filing import FilingEvent


MATERIAL_ITEMS = {"1.01", "1.03", "2.01", "2.02", "3.01", "3.02", "4.02", "5.01"}


def catalyst_from_filing(filing: FilingEvent) -> CatalystEvidence:
    materiality = 0.4
    if filing.form_type.upper().startswith("8-K"):
        materiality = 0.7 if any(item in MATERIAL_ITEMS for item in filing.items) else 0.5
    elif filing.family == "CAPITAL_STRUCTURE":
        materiality = 0.6
    elif filing.family == "DISTRESS":
        materiality = 0.8
    novelty = 0.3 if filing.is_amendment else 0.6
    return CatalystEvidence(
        event_id=filing.normalized_accession,
        entity_ids=(filing.cik,),
        catalyst_strength=materiality,
        novelty_score=novelty,
        surprise_score=None,
        materiality_score=materiality,
        credibility_score=0.9,
        semantic_sentiment=None,
        event_time=filing.acceptance_datetime,
        available_time=filing.available_time,
        publication_state=PublicationState.PUBLISHED,
        provenance_ref=f"sec.edgar:{filing.normalized_accession}",
        quality_flags=("RESEARCH_ONLY",),
    )


def participant_hints_from_filing(filing: FilingEvent, *, transaction_code: str | None = None) -> dict[str, str]:
    action, direction, clarity = infer_action_from_form4_transaction(transaction_code)
    return {
        "form_type": filing.form_type,
        "accession": filing.normalized_accession,
        "action_type": action.value,
        "direction": direction.value,
        "directional_clarity": clarity.value,
        "family": filing.family,
    }
