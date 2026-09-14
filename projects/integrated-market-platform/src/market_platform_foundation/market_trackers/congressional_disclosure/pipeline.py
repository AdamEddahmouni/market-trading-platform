"""End-to-end adapter preparation bundle for one Market Trackers congress-trades row."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .event_map import EventMapPrep, map_event_v1_prep
from .evidence import PublicRecordEvidencePrep, build_public_record_evidence
from .features import candidate_feature_catalog
from .pit import PitClocksPrep, derive_pit_clocks, pit_doctrine_notes
from .receipt import ExternalSourceReceipt, build_external_source_receipt
from .validate import ValidationOutcome, validate_market_trackers_row


@dataclass(frozen=True, slots=True)
class AdapterPrepBundle:
    validation: ValidationOutcome
    receipt: ExternalSourceReceipt | None
    pit: PitClocksPrep | None
    event_map: EventMapPrep | None
    evidence: PublicRecordEvidencePrep | None
    candidate_features: tuple[dict[str, Any], ...]
    doctrine_notes: tuple[str, ...]
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_features": list(self.candidate_features),
            "doctrine_notes": list(self.doctrine_notes),
            "errors": list(self.errors),
            "event_map": self.event_map.to_dict() if self.event_map else None,
            "evidence": self.evidence.to_dict() if self.evidence else None,
            "pit": self.pit.to_dict() if self.pit else None,
            "receipt": self.receipt.to_dict() if self.receipt else None,
            "validation": self.validation.to_dict(),
        }


def build_adapter_prep_bundle(
    row: Mapping[str, Any],
    *,
    platform_received_time_ns: int,
) -> AdapterPrepBundle:
    validation = validate_market_trackers_row(row)
    if not validation.ok:
        return AdapterPrepBundle(
            validation=validation,
            receipt=None,
            pit=None,
            event_map=None,
            evidence=None,
            candidate_features=candidate_feature_catalog(),
            doctrine_notes=pit_doctrine_notes(),
            errors=validation.errors,
        )

    errors: list[str] = []
    receipt: ExternalSourceReceipt | None = None
    pit: PitClocksPrep | None = None
    event_map: EventMapPrep | None = None
    evidence: PublicRecordEvidencePrep | None = None

    try:
        receipt = build_external_source_receipt(row, platform_received_time_ns=platform_received_time_ns)
    except ValueError as exc:
        errors.append(str(exc))

    try:
        pit = derive_pit_clocks(row)
    except ValueError as exc:
        errors.append(str(exc))

    try:
        event_map = map_event_v1_prep(row)
    except ValueError as exc:
        errors.append(str(exc))

    try:
        evidence = build_public_record_evidence(row)
    except ValueError as exc:
        errors.append(str(exc))

    if errors:
        return AdapterPrepBundle(
            validation=validation,
            receipt=None,
            pit=None,
            event_map=None,
            evidence=None,
            candidate_features=candidate_feature_catalog(),
            doctrine_notes=pit_doctrine_notes(),
            errors=tuple(errors),
        )

    return AdapterPrepBundle(
        validation=validation,
        receipt=receipt,
        pit=pit,
        event_map=event_map,
        evidence=evidence,
        candidate_features=candidate_feature_catalog(),
        doctrine_notes=pit_doctrine_notes(),
        errors=(),
    )
