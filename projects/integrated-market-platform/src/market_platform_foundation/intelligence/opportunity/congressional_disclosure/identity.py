"""Deterministic identities for congressional PTR disclosure artifacts."""

from __future__ import annotations

from typing import Any

from ....canonical import canonical_bytes, sha256_bytes
from ...contracts import (
    ComponentLineage,
    ContractKind,
    ContractReference,
    DetectionSeverity,
    DetectionV1,
    EventV1,
    QualitySummary,
    SemanticEventType,
    SnapshotV1,
)
from ...routing.identity import derive_detection_id
from .constants import DETECTOR_ID, DETECTOR_POLICY_ID, DETECTOR_VERSION, EXPERT_ID, STRATEGY_FAMILY
from .facts import CongressionalDisclosureFacts

EVIDENCE_IDENTITY_VERSION = "congressional-ptr-evidence-sha256-v1"
CANDIDATE_IDENTITY_VERSION = "congressional-ptr-candidate-sha256-v1"


def build_congressional_disclosure_detection(
    *,
    snapshot: SnapshotV1,
    event: EventV1,
    facts: CongressionalDisclosureFacts,
    severity: DetectionSeverity,
    reason_codes: tuple[str, ...],
    metadata: dict[str, Any],
) -> DetectionV1:
    event_ref = ContractReference(kind=ContractKind.EVENT.value, id=event.event_id)
    snapshot_ref = ContractReference(kind=ContractKind.SNAPSHOT.value, id=snapshot.snapshot_id)
    identity_context = {
        "doc_id": facts.doc_id,
        "row_id": facts.row_id or "",
        "chamber": facts.chamber,
    }
    detection_id = derive_detection_id(
        semantic_event_type=SemanticEventType.CONGRESSIONAL_PTR_DISCLOSURE,
        source_snapshot_id=snapshot.snapshot_id,
        source_event_refs=(event_ref,),
        detector_id=DETECTOR_ID,
        detector_version=DETECTOR_VERSION,
        detector_policy_identity=DETECTOR_POLICY_ID,
        identity_context=identity_context,
    )
    return DetectionV1(
        detection_id=detection_id,
        schema_version="1",
        semantic_event_type=SemanticEventType.CONGRESSIONAL_PTR_DISCLOSURE,
        detected_at_ns=snapshot.decision_time_ns,
        source_snapshot_ref=snapshot_ref,
        source_event_refs=(event_ref,),
        detector_lineage=ComponentLineage(
            component_id=DETECTOR_ID,
            component_version=DETECTOR_VERSION,
        ),
        scope=snapshot.scope,
        severity=severity,
        reason_codes=reason_codes,
        quality=QualitySummary(state=event.quality.state, flags=event.quality.flags),
        identity_context=identity_context,
        metadata={
            "detector_policy_identity": DETECTOR_POLICY_ID,
            **metadata,
        },
    )


def derive_congressional_disclosure_evidence_id(
    *,
    detection: DetectionV1,
    evidence_kind: str,
    facts: CongressionalDisclosureFacts,
) -> str:
    payload: dict[str, Any] = {
        "identity_version": EVIDENCE_IDENTITY_VERSION,
        "schema_version": "1",
        "detection_id": detection.detection_id,
        "snapshot_id": detection.source_snapshot_ref.id,
        "expert_id": EXPERT_ID,
        "evidence_kind": evidence_kind,
        "doc_id": facts.doc_id,
        "row_id": facts.row_id or "",
        "chamber": facts.chamber,
    }
    return f"EVID-{sha256_bytes(canonical_bytes(payload))}"


def derive_congressional_disclosure_candidate_id(
    *,
    facts: CongressionalDisclosureFacts,
    snapshot: SnapshotV1,
) -> str:
    payload: dict[str, Any] = {
        "identity_version": CANDIDATE_IDENTITY_VERSION,
        "strategy_family": STRATEGY_FAMILY,
        "doc_id": facts.doc_id,
        "row_id": facts.row_id or "",
        "instrument_id": facts.instrument_id or "",
        "decision_time_ns": snapshot.decision_time_ns,
    }
    digest = sha256_bytes(canonical_bytes(payload))
    return f"OPP-CAND-{digest[:16]}"


__all__ = [
    "build_congressional_disclosure_detection",
    "derive_congressional_disclosure_candidate_id",
    "derive_congressional_disclosure_evidence_id",
]
