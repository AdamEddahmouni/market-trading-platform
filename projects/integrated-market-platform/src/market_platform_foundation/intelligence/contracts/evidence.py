"""EvidenceV1 — specialist structured interpretation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .common import (
    INTELLIGENCE_SCHEMA_VERSION,
    ComponentLineage,
    ContractReference,
    Direction,
    EvidenceApplicability,
    IntelligenceScope,
    QualitySummary,
    component_lineage_from_dict,
    component_lineage_to_dict,
    contract_reference_from_dict,
    contract_reference_to_dict,
    dataclass_field_names,
    normalize_unique_refs,
    normalize_unique_strings,
    quality_summary_from_dict,
    quality_summary_to_dict,
    reject_unknown_keys,
    scope_from_dict,
    scope_to_dict,
    validate_id,
    validate_schema_version,
    validate_support_score,
)


@dataclass(frozen=True, slots=True)
class EvidenceV1:
    """Specialist interpretation — not a trade or necessarily a forecast.

    What: structured assessment from an expert/model over a snapshot.
    Not: raw signal, composite hypothesis, or executable opportunity.
    Producers: specialist intelligence components (future BUILD).
    Consumers: hypothesis fusion, forecast calibration layers.
    Immutable after construction.
    """

    evidence_id: str
    schema_version: str
    snapshot_id: str
    expert_id: str
    scope: IntelligenceScope
    applicability: EvidenceApplicability
    quality: QualitySummary
    target_subject: str | None = None
    assessment: dict[str, Any] = field(default_factory=dict)
    directional_score: float | None = None
    support_strength: float | None = None
    evidence_for: tuple[str, ...] = ()
    evidence_against: tuple[str, ...] = ()
    source_signal_refs: tuple[ContractReference, ...] = ()
    source_event_refs: tuple[ContractReference, ...] = ()
    missing_information: tuple[str, ...] = ()
    invalidation_conditions: tuple[str, ...] = ()
    uncertainty: dict[str, Any] = field(default_factory=dict)
    abstention_reason: str | None = None
    component_lineage: ComponentLineage | None = None
    explanation: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_id(self.evidence_id, field_name="evidence_id")
        validate_schema_version(self.schema_version)
        validate_id(self.snapshot_id, field_name="snapshot_id")
        validate_id(self.expert_id, field_name="expert_id")
        if not isinstance(self.applicability, EvidenceApplicability):
            object.__setattr__(self, "applicability", EvidenceApplicability(str(self.applicability)))
        if self.directional_score is not None:
            validate_support_score(self.directional_score)
        if self.support_strength is not None:
            validate_support_score(self.support_strength)
        object.__setattr__(self, "evidence_for", normalize_unique_strings(self.evidence_for))
        object.__setattr__(self, "evidence_against", normalize_unique_strings(self.evidence_against))
        object.__setattr__(self, "source_signal_refs", normalize_unique_refs(self.source_signal_refs))
        object.__setattr__(self, "source_event_refs", normalize_unique_refs(self.source_event_refs))
        object.__setattr__(self, "missing_information", normalize_unique_strings(self.missing_information))
        object.__setattr__(
            self, "invalidation_conditions", normalize_unique_strings(self.invalidation_conditions)
        )
        if not isinstance(self.assessment, dict):
            raise ValueError("EVIDENCE_ASSESSMENT_INVALID")
        if not isinstance(self.uncertainty, dict):
            raise ValueError("EVIDENCE_UNCERTAINTY_INVALID")
        if not isinstance(self.metadata, dict):
            raise ValueError("EVIDENCE_METADATA_INVALID")
        if self.applicability != EvidenceApplicability.APPLICABLE and not self.abstention_reason:
            if self.applicability in {
                EvidenceApplicability.NOT_APPLICABLE,
                EvidenceApplicability.INSUFFICIENT_DATA,
                EvidenceApplicability.DATA_QUALITY_FAILURE,
                EvidenceApplicability.OUT_OF_DOMAIN,
                EvidenceApplicability.OUT_OF_DISTRIBUTION,
                EvidenceApplicability.EXPERT_CONFLICT,
            }:
                object.__setattr__(self, "abstention_reason", self.applicability.value)


_EVIDENCE_ALLOWED = dataclass_field_names(EvidenceV1)


def evidence_v1_to_dict(record: EvidenceV1) -> dict[str, Any]:
    body: dict[str, Any] = {
        "evidence_id": record.evidence_id,
        "schema_version": record.schema_version,
        "snapshot_id": record.snapshot_id,
        "expert_id": record.expert_id,
        "scope": scope_to_dict(record.scope),
        "applicability": record.applicability.value,
        "quality": quality_summary_to_dict(record.quality),
    }
    if record.target_subject is not None:
        body["target_subject"] = record.target_subject
    if record.assessment:
        body["assessment"] = dict(record.assessment)
    if record.directional_score is not None:
        body["directional_score"] = record.directional_score
    if record.support_strength is not None:
        body["support_strength"] = record.support_strength
    if record.evidence_for:
        body["evidence_for"] = list(record.evidence_for)
    if record.evidence_against:
        body["evidence_against"] = list(record.evidence_against)
    if record.source_signal_refs:
        body["source_signal_refs"] = [contract_reference_to_dict(ref) for ref in record.source_signal_refs]
    if record.source_event_refs:
        body["source_event_refs"] = [contract_reference_to_dict(ref) for ref in record.source_event_refs]
    if record.missing_information:
        body["missing_information"] = list(record.missing_information)
    if record.invalidation_conditions:
        body["invalidation_conditions"] = list(record.invalidation_conditions)
    if record.uncertainty:
        body["uncertainty"] = dict(record.uncertainty)
    if record.abstention_reason is not None:
        body["abstention_reason"] = record.abstention_reason
    if record.component_lineage is not None:
        body["component_lineage"] = component_lineage_to_dict(record.component_lineage)
    if record.explanation is not None:
        body["explanation"] = record.explanation
    if record.metadata:
        body["metadata"] = dict(record.metadata)
    return body


def evidence_v1_from_dict(payload: dict[str, Any]) -> EvidenceV1:
    reject_unknown_keys(payload, _EVIDENCE_ALLOWED)
    return EvidenceV1(
        evidence_id=str(payload["evidence_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        snapshot_id=str(payload["snapshot_id"]),
        expert_id=str(payload["expert_id"]),
        scope=scope_from_dict(payload["scope"]),
        applicability=EvidenceApplicability(payload["applicability"]),
        quality=quality_summary_from_dict(payload["quality"]),
        target_subject=payload.get("target_subject"),
        assessment=dict(payload.get("assessment") or {}),
        directional_score=payload.get("directional_score"),
        support_strength=payload.get("support_strength"),
        evidence_for=tuple(payload.get("evidence_for") or ()),
        evidence_against=tuple(payload.get("evidence_against") or ()),
        source_signal_refs=tuple(
            contract_reference_from_dict(item) for item in (payload.get("source_signal_refs") or [])
        ),
        source_event_refs=tuple(
            contract_reference_from_dict(item) for item in (payload.get("source_event_refs") or [])
        ),
        missing_information=tuple(payload.get("missing_information") or ()),
        invalidation_conditions=tuple(payload.get("invalidation_conditions") or ()),
        uncertainty=dict(payload.get("uncertainty") or {}),
        abstention_reason=payload.get("abstention_reason"),
        component_lineage=component_lineage_from_dict(payload.get("component_lineage")),
        explanation=payload.get("explanation"),
        metadata=dict(payload.get("metadata") or {}),
    )


__all__ = ["EvidenceV1", "evidence_v1_from_dict", "evidence_v1_to_dict"]
