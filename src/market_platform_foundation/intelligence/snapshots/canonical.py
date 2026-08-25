"""Deterministic snapshot content identity (BUILD 05)."""

from __future__ import annotations

from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from ..contracts.common import (
    ContractReference,
    IntelligenceScope,
    QualitySummary,
    contract_reference_to_dict,
    quality_summary_to_dict,
    scope_to_dict,
)
from .policy import BUILDER_COMPONENT_ID, BUILDER_COMPONENT_VERSION, SnapshotCompositionPolicy

SNAPSHOT_ID_PREFIX = "SNAP-"
FINGERPRINT_VERSION = "snapshot-content-sha256-v1"


def reference_sort_key(ref: ContractReference) -> tuple[str, str, str]:
    return (ref.kind, ref.id, ref.schema_version)


def sort_references(refs: tuple[ContractReference, ...]) -> tuple[ContractReference, ...]:
    return tuple(sorted(refs, key=reference_sort_key))


def semantic_payload(
    *,
    decision_time_ns: int,
    scope: IntelligenceScope,
    quality: QualitySummary,
    source_event_refs: tuple[ContractReference, ...],
    source_signal_refs: tuple[ContractReference, ...],
    component_refs: tuple[ContractReference, ...],
    composition_policy: SnapshotCompositionPolicy,
) -> dict[str, Any]:
    """Canonical semantic representation hashed for snapshot identity."""
    return {
        "fingerprint_version": FINGERPRINT_VERSION,
        "schema_version": "1",
        "decision_time_ns": decision_time_ns,
        "scope": scope_to_dict(scope),
        "quality": quality_summary_to_dict(quality),
        "source_event_refs": [
            contract_reference_to_dict(ref) for ref in sort_references(source_event_refs)
        ],
        "source_signal_refs": [
            contract_reference_to_dict(ref) for ref in sort_references(source_signal_refs)
        ],
        "component_refs": [
            contract_reference_to_dict(ref) for ref in sort_references(component_refs)
        ],
        "composition_policy": {
            "policy_id": composition_policy.policy_id,
            "policy_version": composition_policy.policy_version,
            "max_events": composition_policy.max_events,
            "max_signals": composition_policy.max_signals,
            "lookback_ns": composition_policy.lookback_ns,
            "event_types": list(composition_policy.event_types),
            "include_global_events": composition_policy.include_global_events,
            "include_signals": composition_policy.include_signals,
            "allow_degraded": composition_policy.allow_degraded,
            "require_usable_events": composition_policy.require_usable_events,
        },
        "builder": {
            "component_id": BUILDER_COMPONENT_ID,
            "component_version": BUILDER_COMPONENT_VERSION,
        },
    }


def content_fingerprint(payload: dict[str, Any]) -> str:
    return sha256_bytes(canonical_bytes(payload))


def snapshot_id_from_fingerprint(fingerprint: str) -> str:
    return f"{SNAPSHOT_ID_PREFIX}{fingerprint}"


def fingerprint_from_snapshot_parts(
    *,
    decision_time_ns: int,
    scope: IntelligenceScope,
    quality: QualitySummary,
    source_event_refs: tuple[ContractReference, ...],
    source_signal_refs: tuple[ContractReference, ...],
    component_refs: tuple[ContractReference, ...],
    composition_policy: SnapshotCompositionPolicy,
) -> str:
    payload = semantic_payload(
        decision_time_ns=decision_time_ns,
        scope=scope,
        quality=quality,
        source_event_refs=source_event_refs,
        source_signal_refs=source_signal_refs,
        component_refs=component_refs,
        composition_policy=composition_policy,
    )
    return content_fingerprint(payload)


def verify_snapshot_fingerprint(
    *,
    decision_time_ns: int,
    scope: IntelligenceScope,
    quality: QualitySummary,
    source_event_refs: tuple[ContractReference, ...],
    source_signal_refs: tuple[ContractReference, ...],
    component_refs: tuple[ContractReference, ...],
    composition_policy: SnapshotCompositionPolicy,
    expected_fingerprint: str,
) -> str:
    observed = fingerprint_from_snapshot_parts(
        decision_time_ns=decision_time_ns,
        scope=scope,
        quality=quality,
        source_event_refs=source_event_refs,
        source_signal_refs=source_signal_refs,
        component_refs=component_refs,
        composition_policy=composition_policy,
    )
    if observed != expected_fingerprint:
        raise ValueError(f"FINGERPRINT_MISMATCH:{expected_fingerprint}!={observed}")
    return observed


__all__ = [
    "FINGERPRINT_VERSION",
    "SNAPSHOT_ID_PREFIX",
    "content_fingerprint",
    "fingerprint_from_snapshot_parts",
    "reference_sort_key",
    "semantic_payload",
    "snapshot_id_from_fingerprint",
    "sort_references",
    "verify_snapshot_fingerprint",
]
