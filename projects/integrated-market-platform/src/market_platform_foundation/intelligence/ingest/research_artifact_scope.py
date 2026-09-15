"""Fail-closed scope checks for precomputed research-artifact attach (evidence-only)."""

from __future__ import annotations

from typing import Any

from ..contracts.opportunity import OpportunityV1

_EDGE_STATS_ARTIFACT_TYPE = "EDGE_STATS_EVIDENCE_ARTIFACT"
_OPTIONS_FLOW_REPLAY_ARTIFACT_TYPE = "OPTIONS_FLOW_REPLAY_EVIDENCE_ARTIFACT"


def research_artifact_instrument_ids(artifact: dict[str, Any]) -> tuple[str, ...]:
    artifact_type = str(artifact.get("artifact_type") or "")
    if artifact_type == _EDGE_STATS_ARTIFACT_TYPE:
        query = artifact.get("query") if isinstance(artifact.get("query"), dict) else {}
        instrument_id = str(query.get("instrument_id") or "").strip()
        return (instrument_id,) if instrument_id else ()
    if artifact_type == _OPTIONS_FLOW_REPLAY_ARTIFACT_TYPE:
        dataset = artifact.get("dataset") if isinstance(artifact.get("dataset"), dict) else {}
        instrument_id = str(dataset.get("instrument_id") or "").strip()
        return (instrument_id,) if instrument_id else ()
    return ()


def validate_research_artifact_opportunity_scope(
    opportunity: OpportunityV1,
    artifact: dict[str, Any],
) -> None:
    artifact_instruments = research_artifact_instrument_ids(artifact)
    if not artifact_instruments:
        raise ValueError("RESEARCH_ARTIFACT_ATTACHMENT_ARTIFACT_SCOPE_UNKNOWN")
    scope_instruments = set(opportunity.scope.instrument_ids)
    if not scope_instruments:
        raise ValueError("RESEARCH_ARTIFACT_ATTACHMENT_OPPORTUNITY_SCOPE_EMPTY")
    for instrument_id in artifact_instruments:
        if instrument_id not in scope_instruments:
            raise ValueError("RESEARCH_ARTIFACT_ATTACHMENT_SCOPE_MISMATCH")


__all__ = [
    "research_artifact_instrument_ids",
    "validate_research_artifact_opportunity_scope",
]
