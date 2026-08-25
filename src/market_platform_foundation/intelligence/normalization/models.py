"""Normalization context, result, and provenance models (BUILD 03)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..contracts.event import EventV1
from .errors import NormalizationDiagnostic


class IngestionMode(StrEnum):
    LIVE_OBSERVED = "LIVE_OBSERVED"
    HISTORICAL_RECONSTRUCTED = "HISTORICAL_RECONSTRUCTED"
    FIXTURE = "FIXTURE"
    REPLAY = "REPLAY"


class AvailabilityBasis(StrEnum):
    LOCAL_RECEIPT = "LOCAL_RECEIPT"
    PROVIDER_REPORTED_AVAILABILITY = "PROVIDER_REPORTED_AVAILABILITY"
    PUBLICATION_TIME = "PUBLICATION_TIME"
    EXCHANGE_DISSEMINATION_TIME = "EXCHANGE_DISSEMINATION_TIME"
    RELEASE_TIME = "RELEASE_TIME"
    RECONSTRUCTED_FROM_SOURCE = "RECONSTRUCTED_FROM_SOURCE"
    DECLARED_PROVIDER_DELAY = "DECLARED_PROVIDER_DELAY"
    UNKNOWN_OR_APPROXIMATE = "UNKNOWN_OR_APPROXIMATE"


class AvailabilityConfidence(StrEnum):
    DIRECTLY_OBSERVED = "DIRECTLY_OBSERVED"
    SOURCE_REPORTED = "SOURCE_REPORTED"
    DERIVED = "DERIVED"
    APPROXIMATE = "APPROXIMATE"


class SourcePrecision(StrEnum):
    NANOSECOND = "NANOSECOND"
    MICROSECOND = "MICROSECOND"
    MILLISECOND = "MILLISECOND"
    SECOND = "SECOND"
    MINUTE = "MINUTE"
    HOUR = "HOUR"
    DAY = "DAY"


@dataclass(frozen=True, slots=True)
class AvailabilityDerivation:
    """Records how available_time_ns was determined."""

    basis: AvailabilityBasis
    confidence: AvailabilityConfidence
    source_precision: SourcePrecision = SourcePrecision.NANOSECOND
    provider_reported_available_time_ns: int | None = None
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderProvenance:
    """Extended BUILD 03 provenance linked to normalized events."""

    provider_id: str
    source_record_type: str
    adapter_id: str
    adapter_version: str
    normalization_version: str
    provider_native_symbol: str | None = None
    provider_native_record_id: str | None = None
    provider_event_type: str | None = None
    raw_payload_ref: str | None = None
    raw_payload_hash: str | None = None
    availability: AvailabilityDerivation | None = None
    source_publication_id: str | None = None
    source_revision_id: str | None = None
    ingestion_mode: IngestionMode = IngestionMode.LIVE_OBSERVED

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "provider_id": self.provider_id,
            "source_record_type": self.source_record_type,
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "normalization_version": self.normalization_version,
            "ingestion_mode": self.ingestion_mode.value,
        }
        if self.provider_native_symbol is not None:
            body["provider_native_symbol"] = self.provider_native_symbol
        if self.provider_native_record_id is not None:
            body["provider_native_record_id"] = self.provider_native_record_id
        if self.provider_event_type is not None:
            body["provider_event_type"] = self.provider_event_type
        if self.raw_payload_ref is not None:
            body["raw_payload_ref"] = self.raw_payload_ref
        if self.raw_payload_hash is not None:
            body["raw_payload_hash"] = self.raw_payload_hash
        if self.source_publication_id is not None:
            body["source_publication_id"] = self.source_publication_id
        if self.source_revision_id is not None:
            body["source_revision_id"] = self.source_revision_id
        if self.availability is not None:
            body["availability"] = {
                "basis": self.availability.basis.value,
                "confidence": self.availability.confidence.value,
                "source_precision": self.availability.source_precision.value,
                "provider_reported_available_time_ns": self.availability.provider_reported_available_time_ns,
                "notes": self.availability.notes,
            }
        return body

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ProviderProvenance:
        avail_raw = payload.get("availability")
        availability: AvailabilityDerivation | None = None
        if isinstance(avail_raw, dict):
            availability = AvailabilityDerivation(
                basis=AvailabilityBasis(str(avail_raw["basis"])),
                confidence=AvailabilityConfidence(str(avail_raw["confidence"])),
                source_precision=SourcePrecision(str(avail_raw.get("source_precision", SourcePrecision.NANOSECOND.value))),
                provider_reported_available_time_ns=avail_raw.get("provider_reported_available_time_ns"),
                notes=avail_raw.get("notes"),
            )
        return cls(
            provider_id=str(payload["provider_id"]),
            source_record_type=str(payload["source_record_type"]),
            adapter_id=str(payload["adapter_id"]),
            adapter_version=str(payload["adapter_version"]),
            normalization_version=str(payload["normalization_version"]),
            provider_native_symbol=payload.get("provider_native_symbol"),
            provider_native_record_id=payload.get("provider_native_record_id"),
            provider_event_type=payload.get("provider_event_type"),
            raw_payload_ref=payload.get("raw_payload_ref"),
            raw_payload_hash=payload.get("raw_payload_hash"),
            availability=availability,
            source_publication_id=payload.get("source_publication_id"),
            source_revision_id=payload.get("source_revision_id"),
            ingestion_mode=IngestionMode(str(payload.get("ingestion_mode", IngestionMode.LIVE_OBSERVED.value))),
        )


@dataclass(frozen=True, slots=True)
class NormalizationContext:
    """Caller-supplied deterministic normalization inputs."""

    received_time_ns: int
    ingestion_mode: IngestionMode = IngestionMode.LIVE_OBSERVED
    adapter_version: str = "1"
    raw_payload_ref: str | None = None
    provider_reported_available_time_ns: int | None = None
    historical_available_time_ns: int | None = None
    availability_basis: AvailabilityBasis | None = None
    availability_confidence: AvailabilityConfidence | None = None
    source_precision: SourcePrecision = SourcePrecision.NANOSECOND
    provider_delay_ns: int | None = None
    ingest_run_id: str | None = None


@dataclass(frozen=True, slots=True)
class NormalizationResult:
    event: EventV1 | None
    provenance: ProviderProvenance | None = None
    diagnostics: tuple[NormalizationDiagnostic, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return self.event is not None and not self.diagnostics


PROVENANCE_METADATA_KEY = "normalization_provenance"


__all__ = [
    "AvailabilityBasis",
    "AvailabilityConfidence",
    "AvailabilityDerivation",
    "IngestionMode",
    "NormalizationContext",
    "NormalizationResult",
    "PROVENANCE_METADATA_KEY",
    "ProviderProvenance",
    "SourcePrecision",
]
