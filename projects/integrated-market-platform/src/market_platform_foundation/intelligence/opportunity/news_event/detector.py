"""Deterministic NEWS_EVENT DetectionV1 builder."""

from __future__ import annotations

from typing import Any

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
from .constants import DETECTOR_ID, DETECTOR_POLICY_ID, DETECTOR_VERSION
from .facts import CanonicalNewsInput


def _severity_for_catalysts(catalyst_ids: tuple[str, ...]) -> DetectionSeverity:
    critical = {"bankruptcy", "fda", "acquisition", "merger"}
    high = {"earnings", "guidance", "offering", "financing", "investigation"}
    matched = set(catalyst_ids)
    if matched & critical:
        return DetectionSeverity.CRITICAL
    if matched & high:
        return DetectionSeverity.HIGH
    if matched:
        return DetectionSeverity.MEDIUM
    return DetectionSeverity.LOW


def build_news_event_detection(
    *,
    event: EventV1,
    snapshot: SnapshotV1,
    facts: CanonicalNewsInput,
) -> DetectionV1:
    event_ref = ContractReference(kind=ContractKind.EVENT.value, id=event.event_id)
    snapshot_ref = ContractReference(kind=ContractKind.SNAPSHOT.value, id=snapshot.snapshot_id)
    catalyst_key = ",".join(facts.matched_catalyst_ids)
    identity_context = {
        "instrument_id": facts.instrument_id,
        "matched_catalyst_ids": catalyst_key,
        "source_event_id": facts.event_id,
    }
    detection_id = derive_detection_id(
        semantic_event_type=SemanticEventType.NEWS_EVENT,
        source_snapshot_id=snapshot.snapshot_id,
        source_event_refs=(event_ref,),
        detector_id=DETECTOR_ID,
        detector_version=DETECTOR_VERSION,
        detector_policy_identity=DETECTOR_POLICY_ID,
        identity_context=identity_context,
    )
    metadata: dict[str, Any] = {
        "detector_policy_identity": DETECTOR_POLICY_ID,
        "matched_catalyst_ids": list(facts.matched_catalyst_ids),
        "provider_id": facts.provider_id,
        "source_id": facts.source_id,
        "headline": facts.headline,
        "normalization_version": facts.normalization_version,
        "evidence_class": "SOFTWARE_CONTROLLED",
        "severity_semantics": "deterministic_catalyst_materiality_not_probability",
    }
    return DetectionV1(
        detection_id=detection_id,
        schema_version="1",
        semantic_event_type=SemanticEventType.NEWS_EVENT,
        detected_at_ns=snapshot.decision_time_ns,
        source_snapshot_ref=snapshot_ref,
        source_event_refs=(event_ref,),
        detector_lineage=ComponentLineage(
            component_id=DETECTOR_ID,
            component_version=DETECTOR_VERSION,
        ),
        scope=snapshot.scope,
        severity=_severity_for_catalysts(facts.matched_catalyst_ids),
        reason_codes=("NEWS_CATALYST_MATCH",),
        quality=QualitySummary(state=event.quality.state, flags=event.quality.flags),
        identity_context=identity_context,
        metadata=metadata,
    )


__all__ = ["build_news_event_detection"]
