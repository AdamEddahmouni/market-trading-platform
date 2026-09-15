"""Deterministic congressional PTR DetectionV1 builder."""

from __future__ import annotations

from ...contracts import DetectionSeverity, DetectionV1, EventV1, SnapshotV1
from .facts import CongressionalDisclosureFacts
from .identity import build_congressional_disclosure_detection


def _severity_for_facts(facts: CongressionalDisclosureFacts) -> DetectionSeverity:
    lag = facts.filing_lag_days
    if lag is not None and lag >= 45:
        return DetectionSeverity.HIGH
    if facts.disclosed_side == "exchange":
        return DetectionSeverity.MEDIUM
    if lag is not None and lag >= 30:
        return DetectionSeverity.MEDIUM
    return DetectionSeverity.LOW


def build_detection(
    *,
    event: EventV1,
    snapshot: SnapshotV1,
    facts: CongressionalDisclosureFacts,
) -> DetectionV1:
    severity = _severity_for_facts(facts)
    reason_codes = ("CONGRESSIONAL_PTR_DISCLOSURE_FACT", "PTR_NOT_AUTO_DIRECTIONAL")
    metadata = {
        "chamber": facts.chamber,
        "disclosed_side_reported": facts.disclosed_side,
        "filing_lag_days": facts.filing_lag_days,
        "amount_range_text": facts.amount_range_text,
        "severity_semantics": "deterministic_materiality_not_probability",
    }
    return build_congressional_disclosure_detection(
        snapshot=snapshot,
        event=event,
        facts=facts,
        severity=severity,
        reason_codes=reason_codes,
        metadata=metadata,
    )


__all__ = ["build_detection"]
