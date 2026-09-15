"""EvidenceV1 specialist for congressional PTR disclosure (Lane F)."""

from __future__ import annotations

from typing import Any

from ...contracts import (
    ComponentLineage,
    ContractKind,
    ContractReference,
    DetectionSeverity,
    DetectionV1,
    EventV1,
    EvidenceApplicability,
    EvidenceV1,
    SnapshotV1,
    QualitySummary,
)
from .constants import EXPERT_ID
from .facts import CongressionalDisclosureFacts
from .identity import derive_congressional_disclosure_evidence_id


def build_evidence(
    *,
    event: EventV1,
    snapshot: SnapshotV1,
    detection: DetectionV1,
    facts: CongressionalDisclosureFacts,
) -> EvidenceV1:
    uncertainty: dict[str, Any] = {
        "ptr_not_auto_directional": True,
        "disclosed_side_is_reported_fact_only": True,
        "amount_is_range_not_exact": True,
    }
    for flag in facts.uncertainty_flags:
        uncertainty[flag.lower()] = True

    assessment: dict[str, Any] = {
        "doc_id": facts.doc_id,
        "chamber": facts.chamber,
        "disclosed_side": facts.disclosed_side,
        "amount_range_text": facts.amount_range_text,
        "member_bioguide_id": facts.member_bioguide_id,
        "filing_lag_days": facts.filing_lag_days,
        "primary_source_url": facts.primary_source_url,
    }

    evidence_for: list[str] = [
        "CONGRESSIONAL_REGULATORY_DISCLOSURE",
        "PRIMARY_SOURCE_LINKED",
        "AGGREGATOR_ROW_REPLACEABLE",
    ]
    evidence_against: list[str] = ["DISCLOSED_SIDE_NOT_EXECUTION_SIDE"]
    if "EXCHANGE_NOT_SIMPLE_BUY_SELL" in facts.uncertainty_flags:
        evidence_against.append("EXCHANGE_SEMANTICS_AMBIGUOUS")

    event_ref = ContractReference(kind=ContractKind.EVENT.value, id=event.event_id)
    evidence_id = derive_congressional_disclosure_evidence_id(
        detection=detection,
        evidence_kind="congressional_ptr_disclosure",
        facts=facts,
    )
    strength_map = {
        DetectionSeverity.LOW: 0.25,
        DetectionSeverity.MEDIUM: 0.5,
        DetectionSeverity.HIGH: 0.75,
        DetectionSeverity.CRITICAL: 1.0,
    }
    return EvidenceV1(
        evidence_id=evidence_id,
        schema_version="1",
        snapshot_id=snapshot.snapshot_id,
        expert_id=EXPERT_ID,
        scope=snapshot.scope,
        applicability=EvidenceApplicability.APPLICABLE,
        quality=QualitySummary(state=event.quality.state, flags=event.quality.flags),
        target_subject=facts.instrument_id,
        assessment=assessment,
        directional_score=None,
        support_strength=strength_map[detection.severity],
        evidence_for=tuple(evidence_for),
        evidence_against=tuple(evidence_against),
        source_event_refs=(event_ref,),
        uncertainty=uncertainty,
        invalidation_conditions=(
            "AMENDED_PTR_SUPERSEDES",
            "INSTRUMENT_IDENTITY_CORRECTION",
        ),
        component_lineage=ComponentLineage(component_id=EXPERT_ID, component_version="1"),
        explanation=(
            "Congressional Periodic Transaction Report row interpreted as public-record fact. "
            "Disclosed buy/sell/exchange is not mapped to trade side or OpportunitySide."
        ),
        metadata={"detection_id": detection.detection_id},
    )


__all__ = ["build_evidence"]
