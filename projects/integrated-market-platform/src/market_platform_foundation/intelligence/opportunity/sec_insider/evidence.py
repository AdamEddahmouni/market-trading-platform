"""EvidenceV1 specialist for SEC insider disclosure (Lane C)."""

from __future__ import annotations

from typing import Any

from ....contracts.participant import infer_action_from_form4_transaction
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
from .facts import SecInsiderDisclosureFacts
from .identity import derive_sec_insider_evidence_id


def build_evidence(
    *,
    event: EventV1,
    snapshot: SnapshotV1,
    detection: DetectionV1,
    facts: SecInsiderDisclosureFacts,
) -> EvidenceV1:
    action_type, direction, clarity = infer_action_from_form4_transaction(facts.transaction_code)
    uncertainty: dict[str, Any] = {
        "form4_not_auto_directional": True,
        "transaction_code_is_reported_fact_only": True,
    }
    if facts.is_derivative:
        uncertainty["derivative_table_row"] = True
    if facts.transaction_code is None:
        uncertainty["transaction_code_absent"] = True

    assessment: dict[str, Any] = {
        "accession_number": facts.accession_number,
        "form_type": facts.form_type,
        "transaction_code": facts.transaction_code,
        "acquired_disposed_code": facts.acquired_disposed,
        "participant_action_type": action_type.value,
        "participant_direction_semantics": direction.value,
        "directional_clarity": clarity.value,
        "shares": facts.shares,
        "price_per_share": facts.price_per_share,
        "notional_usd": facts.notional_usd,
        "shares_owned_after": facts.shares_owned_after,
        "filing_lag_days": facts.filing_lag_days,
        "role_flags": list(facts.role_flags),
        "insider_count_in_cluster": facts.insider_count_in_cluster,
        "primary_source_url": facts.primary_source_url,
    }

    evidence_for: list[str] = [
        "PUBLIC_SEC_OWNERSHIP_DISCLOSURE",
        "PRIMARY_SOURCE_LINKED",
    ]
    if facts.filing_lag_days is not None and facts.filing_lag_days <= 2:
        evidence_for.append("TIMELY_FILING_LAG")
    evidence_against: list[str] = ["FORM4_CODE_NOT_EXECUTION_SIDE"]
    if clarity.value != "CLEAR":
        evidence_against.append("TRANSACTION_SEMANTICS_AMBIGUOUS")

    event_ref = ContractReference(kind=ContractKind.EVENT.value, id=event.event_id)
    evidence_id = derive_sec_insider_evidence_id(
        detection=detection,
        evidence_kind="sec_insider_disclosure",
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
            "AMENDED_FILING_SUPERSEDES",
            "INSTRUMENT_IDENTITY_CORRECTION",
        ),
        component_lineage=ComponentLineage(component_id=EXPERT_ID, component_version="1"),
        explanation=(
            "SEC Form 3/4/5 ownership disclosure interpreted as public-record fact. "
            "Transaction codes are not mapped to trade side or OpportunitySide."
        ),
        metadata={"detection_id": detection.detection_id},
    )


__all__ = ["build_evidence"]
