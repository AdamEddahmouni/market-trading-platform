"""XA-05 provenance and reproducibility helpers."""

from __future__ import annotations

from typing import Iterable, Mapping

from market_platform_foundation.canonical import canonical_bytes, sha256_bytes
from market_platform_foundation.xa02.contracts import AdmittedObservation, AdmissionEnvelope

from .contracts import EvidenceReference, ReproducibilityMetadata
from .enums import ENGINE_PROFILE, EpistemicClass, IDENTITY_PROFILE


ENGINE_VERSION = "1"


def scalar_evidence_reference(obs: AdmittedObservation) -> EvidenceReference:
  return EvidenceReference(
    observation_id=obs.observation_id,
    source_kind="SCALAR_MACRO",
    subject_id=obs.canonical_indicator_id,
    available_time=obs.available_time,
    event_time=obs.event_time,
    revision_classification=obs.revision_classification.value,
    epistemic_class=EpistemicClass.OBSERVED_FACT,
  )


def envelope_evidence_reference(envelope: AdmissionEnvelope) -> EvidenceReference:
  return EvidenceReference(
    observation_id=envelope.observation_id,
    source_kind=envelope.payload_kind.value,
    subject_id=envelope.source_subject_id,
    available_time=envelope.available_time,
    event_time=envelope.event_time,
    revision_classification=envelope.revision_classification.value,
    epistemic_class=EpistemicClass.REPORTED_CLAIM,
  )


def semantic_fingerprint(
  *,
  decision_time: str,
  classifier_versions: Mapping[str, str],
  evidence_observation_ids: Iterable[str],
  dimension_payload: Iterable[Mapping[str, object]],
) -> str:
  material = {
    "profile": IDENTITY_PROFILE,
    "decision_time": decision_time,
    "engine_profile": ENGINE_PROFILE,
    "engine_version": ENGINE_VERSION,
    "classifier_versions": dict(sorted(classifier_versions.items())),
    "evidence_observation_ids": sorted(evidence_observation_ids),
    "dimensions": list(dimension_payload),
  }
  return sha256_bytes(canonical_bytes(material))


def derive_state_id(*, decision_time: str, semantic_fingerprint_value: str) -> str:
  material = {
    "profile": IDENTITY_PROFILE,
    "decision_time": decision_time,
    "semantic_fingerprint": semantic_fingerprint_value,
  }
  digest = sha256_bytes(canonical_bytes(material))
  return f"XA05:STATE:{digest[:16]}"


def build_reproducibility_metadata(
  *,
  decision_time: str,
  classifier_versions: Mapping[str, str],
  evidence_observation_ids: tuple[str, ...],
  dimension_payload: Iterable[Mapping[str, object]],
) -> ReproducibilityMetadata:
  fingerprint = semantic_fingerprint(
    decision_time=decision_time,
    classifier_versions=classifier_versions,
    evidence_observation_ids=evidence_observation_ids,
    dimension_payload=dimension_payload,
  )
  return ReproducibilityMetadata(
    engine_profile=ENGINE_PROFILE,
    engine_version=ENGINE_VERSION,
    classifier_versions=dict(classifier_versions),
    decision_time=decision_time,
    evidence_observation_ids=evidence_observation_ids,
    semantic_fingerprint=fingerprint,
  )
