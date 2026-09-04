"""XA-05 cross-asset strategic state contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from market_platform_foundation.xa01.enums import AnalyticalDomain

from .enums import (
  SCHEMA_VERSION,
  EpistemicClass,
  EvidenceAvailabilityStatus,
  StateDimensionId,
)


@dataclass(frozen=True, slots=True)
class EvidenceReference:
  observation_id: str
  source_kind: str
  subject_id: str
  available_time: str
  event_time: str
  revision_classification: str
  epistemic_class: EpistemicClass


@dataclass(frozen=True, slots=True)
class DimensionClassification:
  dimension_id: StateDimensionId
  classification: str
  definition_version: str
  evidence_status: EvidenceAvailabilityStatus
  epistemic_class: EpistemicClass
  supporting_evidence: tuple[EvidenceReference, ...] = ()
  contradicting_evidence: tuple[EvidenceReference, ...] = ()
  numeric_features: Mapping[str, float | None] = field(default_factory=dict)
  notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StateCompleteness:
  dimensions_requested: int
  dimensions_populated: int
  dimensions_missing: int
  dimensions_conflicting: int
  dimensions_insufficient: int


@dataclass(frozen=True, slots=True)
class ReproducibilityMetadata:
  engine_profile: str
  engine_version: str
  classifier_versions: Mapping[str, str]
  decision_time: str
  evidence_observation_ids: tuple[str, ...]
  semantic_fingerprint: str


@dataclass(frozen=True, slots=True)
class CrossAssetStrategicState:
  state_id: str
  decision_time: str
  construction_time: str
  analytical_domains: tuple[AnalyticalDomain, ...]
  dimensions: tuple[DimensionClassification, ...]
  evidence_references: tuple[EvidenceReference, ...]
  completeness: StateCompleteness
  provenance: ReproducibilityMetadata
  unknowns: tuple[str, ...] = ()
  conflicts: tuple[str, ...] = ()
  schema_version: int = SCHEMA_VERSION


def dimension_to_dict(item: DimensionClassification) -> dict[str, Any]:
  return {
    "dimension_id": item.dimension_id.value,
    "classification": item.classification,
    "definition_version": item.definition_version,
    "evidence_status": item.evidence_status.value,
    "epistemic_class": item.epistemic_class.value,
    "supporting_evidence": [evidence_to_dict(ref) for ref in item.supporting_evidence],
    "contradicting_evidence": [evidence_to_dict(ref) for ref in item.contradicting_evidence],
    "numeric_features": dict(item.numeric_features),
    "notes": list(item.notes),
  }


def evidence_to_dict(ref: EvidenceReference) -> dict[str, Any]:
  return {
    "observation_id": ref.observation_id,
    "source_kind": ref.source_kind,
    "subject_id": ref.subject_id,
    "available_time": ref.available_time,
    "event_time": ref.event_time,
    "revision_classification": ref.revision_classification,
    "epistemic_class": ref.epistemic_class.value,
  }


def state_to_dict(state: CrossAssetStrategicState) -> dict[str, Any]:
  return {
    "schema_version": state.schema_version,
    "state_id": state.state_id,
    "decision_time": state.decision_time,
    "construction_time": state.construction_time,
    "analytical_domains": [domain.value for domain in state.analytical_domains],
    "dimensions": [dimension_to_dict(item) for item in state.dimensions],
    "evidence_references": [evidence_to_dict(ref) for ref in state.evidence_references],
    "completeness": {
      "dimensions_requested": state.completeness.dimensions_requested,
      "dimensions_populated": state.completeness.dimensions_populated,
      "dimensions_missing": state.completeness.dimensions_missing,
      "dimensions_conflicting": state.completeness.dimensions_conflicting,
      "dimensions_insufficient": state.completeness.dimensions_insufficient,
    },
    "provenance": {
      "engine_profile": state.provenance.engine_profile,
      "engine_version": state.provenance.engine_version,
      "classifier_versions": dict(state.provenance.classifier_versions),
      "decision_time": state.provenance.decision_time,
      "evidence_observation_ids": list(state.provenance.evidence_observation_ids),
      "semantic_fingerprint": state.provenance.semantic_fingerprint,
    },
    "unknowns": list(state.unknowns),
    "conflicts": list(state.conflicts),
  }
