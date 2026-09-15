"""Deterministic SEC insider disclosure DetectionV1 builder."""

from __future__ import annotations

from ...contracts import DetectionSeverity, DetectionV1, EventV1, SnapshotV1
from .canonical_snapshot import build_sec_insider_canonical_detection_snapshot
from .facts import SecInsiderDisclosureFacts
from .identity import build_sec_insider_detection


def _severity_for_facts(facts: SecInsiderDisclosureFacts) -> DetectionSeverity:
    notional = facts.notional_usd or 0.0
    lag = facts.filing_lag_days
    senior_role = bool(facts.role_flags)
    if facts.form_type.replace("/A", "").upper() == "3" and facts.transaction_code is None:
        return DetectionSeverity.LOW
    if lag is not None and lag <= 2 and notional >= 1_000_000:
        return DetectionSeverity.CRITICAL
    if notional >= 250_000 or senior_role:
        return DetectionSeverity.HIGH
    if notional >= 25_000 or facts.insider_count_in_cluster >= 3:
        return DetectionSeverity.MEDIUM
    return DetectionSeverity.LOW


def build_detection(
    *,
    event: EventV1,
    snapshot: SnapshotV1,
    facts: SecInsiderDisclosureFacts,
) -> DetectionV1:
    _ = snapshot  # frame snapshot may differ; identity uses canonical anchor only
    canonical = build_sec_insider_canonical_detection_snapshot(event)
    severity = _severity_for_facts(facts)
    reason_codes = ("SEC_INSIDER_DISCLOSURE_FACT", "FORM4_NOT_AUTO_DIRECTIONAL")
    metadata = {
        "form_type": facts.form_type,
        "transaction_code_reported": facts.transaction_code or "",
        "acquired_disposed_reported": facts.acquired_disposed or "",
        "filing_lag_days": facts.filing_lag_days,
        "notional_usd": facts.notional_usd,
        "insider_count_in_cluster": facts.insider_count_in_cluster,
        "severity_semantics": "deterministic_materiality_not_probability",
    }
    return build_sec_insider_detection(
        snapshot=canonical,
        event=event,
        facts=facts,
        severity=severity,
        reason_codes=reason_codes,
        metadata=metadata,
    )


__all__ = ["build_detection"]
