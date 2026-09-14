"""Opportunity Contract candidate projection — not OpportunityEngine.assess."""

from __future__ import annotations

from typing import Any

from ...contracts import DetectionV1, EventV1, EvidenceV1, SnapshotV1
from .constants import FORBIDDEN_CANDIDATE_DIRECTIONS, STRATEGY_FAMILY, STRATEGY_VERSION
from .facts import SecInsiderDisclosureFacts
from .identity import derive_sec_insider_candidate_id


def project_opportunity_candidate(
    *,
    event: EventV1,
    snapshot: SnapshotV1,
    detection: DetectionV1,
    evidence: EvidenceV1,
    facts: SecInsiderDisclosureFacts,
) -> dict[str, Any]:
    direction_or_expression = "REGULATORY_OWNERSHIP_FACT"
    if direction_or_expression.upper() in FORBIDDEN_CANDIDATE_DIRECTIONS:
        raise ValueError("SEC_INSIDER_CANDIDATE_DIRECTION_FORBIDDEN")

    instrument_key = facts.instrument_id or snapshot.scope.instrument_ids[0] if snapshot.scope.instrument_ids else ""
    candidate: dict[str, Any] = {
        "opportunity_id": derive_sec_insider_candidate_id(facts=facts, snapshot=snapshot),
        "strategy_family": STRATEGY_FAMILY,
        "strategy_version": STRATEGY_VERSION,
        "instrument_key": instrument_key,
        "asset_class": "US_EQUITY",
        "decision_time": snapshot.decision_time_ns,
        "information_cutoff": event.available_time_ns,
        "direction_or_expression": direction_or_expression,
        "horizon": {"kind": "DISCLOSURE_RESEARCH", "duration_ns": 5 * 24 * 3600 * 1_000_000_000},
        "mechanism": (
            "Public SEC insider ownership disclosure; materiality from filing facts, "
            "not from Form 4 P/D codes as trade direction."
        ),
        "summary": (
            f"Form {facts.form_type} disclosure for {instrument_key or 'unknown instrument'} "
            f"(accession {facts.accession_number})."
        ),
        "evidence_class": "PUBLIC_RECORD_SPECIALIST",
        "data_quality": event.quality.state.value,
        "eligibility_state": "NORMALIZED_AWAITING_FORECAST",
        "sec_insider_disclosure_ref": {
            "event_id": event.event_id,
            "detection_id": detection.detection_id,
            "evidence_id": evidence.evidence_id,
            "accession_number": facts.accession_number,
            "row_id": facts.row_id,
        },
        "forecast_gated": True,
        "execution_authority": False,
        "lane_c_vertical": "SEC_INSIDER_DISCLOSURE_V1",
    }
    code = (facts.transaction_code or "").upper()
    if code in {"P", "D"}:
        candidate["form4_code_reported_fact_only"] = code
    return candidate


def assert_candidate_not_form4_directional(candidate: dict[str, Any]) -> None:
    expression = str(candidate.get("direction_or_expression", "")).upper()
    if expression in FORBIDDEN_CANDIDATE_DIRECTIONS:
        raise AssertionError("FORM4_DIRECTION_LEAKED_INTO_CANDIDATE")
    if candidate.get("side") is not None:
        raise AssertionError("OPPORTUNITY_SIDE_MUST_NOT_BE_SET")


__all__ = ["assert_candidate_not_form4_directional", "project_opportunity_candidate"]
