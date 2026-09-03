"""Source-neutral admission envelope conversions and eligibility helpers."""

from __future__ import annotations

from .contracts import (
    AdmissionEnvelope,
    AdmittedObservation,
    PositioningPayload,
    ScalarMacroPayload,
)
from .enums import AdmissionStatus, ObservationPayloadKind, ReferenceSubjectType, SourceProvider


def admitted_observation_to_envelope(obs: AdmittedObservation) -> AdmissionEnvelope:
    """Map legacy XA-02 scalar observation into the common admission envelope."""
    return AdmissionEnvelope(
        observation_id=obs.observation_id,
        source_provider=obs.provenance.provider,
        source_subject_id=obs.canonical_indicator_id,
        subject_type=ReferenceSubjectType.CANONICAL_INDICATOR,
        event_time=obs.event_time,
        available_time=obs.available_time,
        retrieval_time=obs.retrieval_time,
        revision_classification=obs.revision_classification,
        admission_status=obs.admission_status,
        provenance=obs.provenance,
        payload_kind=ObservationPayloadKind.SCALAR_MACRO,
        scalar_payload=ScalarMacroPayload(
            canonical_indicator_id=obs.canonical_indicator_id,
            observation_date=obs.observation_date,
            raw_value=obs.raw_value,
            normalized_value=obs.normalized_value,
            units=obs.units,
        ),
        quality_flags=obs.quality_flags,
        schema_version=obs.schema_version,
    )


def envelope_to_admitted_observation(envelope: AdmissionEnvelope) -> AdmittedObservation:
    """Extract legacy AdmittedObservation from a scalar macro envelope."""
    if envelope.payload_kind != ObservationPayloadKind.SCALAR_MACRO:
        raise ValueError("envelope is not scalar macro payload")
    if envelope.scalar_payload is None:
        raise ValueError("scalar payload missing")
    payload = envelope.scalar_payload
    return AdmittedObservation(
        observation_id=envelope.observation_id,
        canonical_indicator_id=payload.canonical_indicator_id,
        observation_date=payload.observation_date,
        raw_value=payload.raw_value,
        normalized_value=payload.normalized_value,
        units=payload.units,
        event_time=envelope.event_time,
        available_time=envelope.available_time,
        retrieval_time=envelope.retrieval_time,
        revision_classification=envelope.revision_classification,
        admission_status=envelope.admission_status,
        provenance=envelope.provenance,
        quality_flags=envelope.quality_flags,
        schema_version=envelope.schema_version,
    )


def eligible_at_decision_time_envelope(envelope: AdmissionEnvelope, decision_time: str) -> bool:
    if not envelope.available_time:
        return False
    return envelope.available_time <= decision_time


def envelopes_equivalent_for_identity(left: AdmissionEnvelope, right: AdmissionEnvelope) -> bool:
    if left.observation_id != right.observation_id:
        return False
    if left.payload_kind != right.payload_kind:
        return False
    if left.payload_kind == ObservationPayloadKind.SCALAR_MACRO:
        return (
            left.scalar_payload == right.scalar_payload
            and left.available_time == right.available_time
            and left.revision_classification == right.revision_classification
        )
    return (
        left.positioning_payload == right.positioning_payload
        and left.available_time == right.available_time
        and left.revision_classification == right.revision_classification
    )


def positioning_unit_label() -> str:
    return "contracts"
