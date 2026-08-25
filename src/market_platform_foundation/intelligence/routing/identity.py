"""Stable BUILD 09 detection and route identities."""

from __future__ import annotations

from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from ..contracts import ContractReference, SemanticEventType

DETECTION_IDENTITY_VERSION = "semantic-detection-sha256-v1"
ROUTING_IDENTITY_VERSION = "routing-decision-sha256-v1"


def _refs_payload(refs: tuple[ContractReference, ...]) -> list[dict[str, str]]:
    return [
        {"kind": ref.kind, "id": ref.id, "schema_version": ref.schema_version}
        for ref in sorted(refs, key=lambda row: (row.kind, row.id, row.schema_version))
    ]


def derive_detection_id(
    *,
    semantic_event_type: SemanticEventType,
    source_snapshot_id: str,
    source_signal_refs: tuple[ContractReference, ...] = (),
    source_event_refs: tuple[ContractReference, ...] = (),
    detector_id: str,
    detector_version: str,
    policy_id: str,
    policy_version: str,
    identity_context: dict[str, str] | None = None,
) -> str:
    payload: dict[str, Any] = {
        "identity_version": DETECTION_IDENTITY_VERSION,
        "schema_version": "1",
        "semantic_event_type": semantic_event_type.value,
        "source_snapshot_id": source_snapshot_id,
        "source_signal_refs": _refs_payload(source_signal_refs),
        "source_event_refs": _refs_payload(source_event_refs),
        "detector_id": detector_id,
        "detector_version": detector_version,
        "policy_id": policy_id,
        "policy_version": policy_version,
        "identity_context": dict(sorted((identity_context or {}).items())),
    }
    return f"DET-{sha256_bytes(canonical_bytes(payload))}"


def derive_routing_decision_id(
    *,
    detection_id: str,
    router_policy_identity: str,
    expert_domain: str,
    required_capabilities: tuple[str, ...],
    routing_context: dict[str, object],
) -> str:
    payload = {
        "identity_version": ROUTING_IDENTITY_VERSION,
        "schema_version": "1",
        "detection_id": detection_id,
        "router_policy_identity": router_policy_identity,
        "expert_domain": expert_domain,
        "required_capabilities": sorted(set(required_capabilities)),
        "routing_context": routing_context,
    }
    return f"ROUTE-{sha256_bytes(canonical_bytes(payload))}"


__all__ = [
    "DETECTION_IDENTITY_VERSION",
    "ROUTING_IDENTITY_VERSION",
    "derive_detection_id",
    "derive_routing_decision_id",
]
