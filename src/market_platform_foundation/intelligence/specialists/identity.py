"""Deterministic evidence identities for BUILD 11 specialists."""

from __future__ import annotations

from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from ..contracts import ContractReference, InferenceJobV1, RoutingDecisionV1, DetectionV1


def _refs_payload(refs: tuple[ContractReference, ...]) -> list[dict[str, str]]:
    return [
        {"kind": ref.kind, "id": ref.id, "schema_version": ref.schema_version}
        for ref in sorted(refs, key=lambda row: (row.kind, row.id, row.schema_version))
    ]


def derive_microstructure_evidence_id(
    *,
    job: InferenceJobV1,
    route: RoutingDecisionV1,
    detection: DetectionV1,
    evidence_kind: str,
    source_signal_refs: tuple[ContractReference, ...],
    specialist_component_id: str,
    specialist_component_version: str,
    specialist_policy_identity: str,
    evidence_identity_version: str,
) -> str:
    """Identity excludes computed rendering such as prose, deltas, and strength."""

    payload: dict[str, Any] = {
        "identity_version": evidence_identity_version,
        "schema_version": "1",
        "job_id": job.job_id,
        "routing_decision_id": route.routing_decision_id,
        "detection_id": detection.detection_id,
        "snapshot_id": detection.source_snapshot_ref.id,
        "semantic_event_type": detection.semantic_event_type.value,
        "evidence_kind": evidence_kind,
        "source_signal_refs": _refs_payload(source_signal_refs),
        "specialist_component_id": specialist_component_id,
        "specialist_component_version": specialist_component_version,
        "specialist_policy_identity": specialist_policy_identity,
    }
    return f"EVID-{sha256_bytes(canonical_bytes(payload))}"


__all__ = ["derive_microstructure_evidence_id"]
