"""Isolated SEC insider EventV1 → DetectionV1 → EvidenceV1 → candidate projection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...contracts import DetectionV1, EventV1, EvidenceV1, SnapshotV1
from .canonical_snapshot import build_sec_insider_canonical_detection_snapshot
from .candidate import project_opportunity_candidate
from .detector import build_detection
from .evidence import build_evidence
from .validation import SecInsiderValidation, validate_sec_insider_inputs


@dataclass(frozen=True, slots=True)
class SecInsiderVerticalResult:
    ok: bool
    reason_codes: tuple[str, ...] = ()
    detection: DetectionV1 | None = None
    evidence: EvidenceV1 | None = None
    candidate: dict[str, Any] | None = None


def run_sec_insider_vertical(
    *,
    event: EventV1,
    snapshot: SnapshotV1,
) -> SecInsiderVerticalResult:
    validated: SecInsiderValidation = validate_sec_insider_inputs(event=event, snapshot=snapshot)
    if not validated.ok or validated.facts is None:
        return SecInsiderVerticalResult(False, validated.reason_codes)
    facts = validated.facts
    canonical_snapshot = build_sec_insider_canonical_detection_snapshot(event)
    detection = build_detection(event=event, snapshot=snapshot, facts=facts)
    evidence = build_evidence(
        event=event,
        snapshot=canonical_snapshot,
        detection=detection,
        facts=facts,
    )
    candidate = project_opportunity_candidate(
        event=event,
        snapshot=canonical_snapshot,
        detection=detection,
        evidence=evidence,
        facts=facts,
    )
    return SecInsiderVerticalResult(
        True,
        (),
        detection=detection,
        evidence=evidence,
        candidate=candidate,
    )


__all__ = ["SecInsiderVerticalResult", "run_sec_insider_vertical"]
