"""Honesty projector for operator data_quality. Does not probe providers."""

from __future__ import annotations

from typing import Any, Mapping

from .freshness import (
    OpportunityFreshnessPolicy,
    evaluate_opportunity_freshness,
    fail_closed_for_actionable,
)


def project_opportunity_data_quality(
    *,
    source: str,
    quality_decision: Mapping[str, Any] | None = None,
    live_observational_env: bool = False,
    as_of_time_ns: int | None = None,
    last_source_time_ns: int | None = None,
    runtime_capability: Mapping[str, Any] | None = None,
    session_state: str | None = None,
    book_validity: str | None = None,
    freshness_policy: OpportunityFreshnessPolicy | None = None,
) -> dict[str, Any]:
    """Return an explicit quality record. Adapter presence is not FRESH/ENTITLED."""

    if live_observational_env:
        # Env flag is not sample-verified freshness.
        source = source if source else "UNKNOWN"
    evaluation = evaluate_opportunity_freshness(
        source=source,
        as_of_time_ns=as_of_time_ns,
        last_source_time_ns=last_source_time_ns,
        policy=freshness_policy,
        runtime_capability=runtime_capability,
        session_state=session_state,
        book_validity=book_validity,
    )
    status = "UNAVAILABLE"
    freshness = "UNAVAILABLE"
    entitlement = "UNAVAILABLE"
    connection = "UNAVAILABLE"
    reason_codes = ["PROVIDER_HONESTY_NOT_WIRED"]
    if quality_decision is not None:
        action = str(quality_decision.get("action") or "")
        if action == "FAIL_CLOSED":
            status = "INVALID"
            reason_codes = ["QUALITY_FAIL_CLOSED"]
        elif action == "ABSTAIN":
            status = "UNAVAILABLE"
            reason_codes = ["QUALITY_ABSTAIN"]
        elif action == "DEGRADE":
            status = "DEGRADED"
            reason_codes = ["QUALITY_DEGRADED"]
        elif action:
            status = "GOOD"
            reason_codes = ["QUALITY_DECISION_PRESENT"]
            freshness = str(quality_decision.get("freshness") or "UNAVAILABLE")
            entitlement = str(quality_decision.get("entitlement") or "UNAVAILABLE")
            connection = str(quality_decision.get("connection") or "UNAVAILABLE")
    if source in {"FIXTURE", "REPLAY"}:
        if status == "UNAVAILABLE":
            status = "GOOD"
            reason_codes = ["FIXTURE_OR_REPLAY_SOURCE"]
        freshness = "UNAVAILABLE"
        entitlement = "UNAVAILABLE"
    if source == "RECORDED_ARTIFACTS":
        status = "UNAVAILABLE"
        freshness = "UNAVAILABLE"
        entitlement = "UNAVAILABLE"
        reason_codes = ["RECORDED_ARTIFACTS_ONLY"]
    if source == "LIVE_OBSERVATIONAL":
        status = "UNAVAILABLE"
        reason_codes = ["LIVE_OBSERVATIONAL_NOT_ENGINE_QUALITY"]
        if evaluation.status != "NOT_APPLICABLE":
            freshness = evaluation.status
            if evaluation.entitlement:
                entitlement = evaluation.entitlement
    elif source not in {"FIXTURE", "REPLAY", "RECORDED_ARTIFACTS"}:
        freshness = evaluation.status
        if evaluation.entitlement:
            entitlement = evaluation.entitlement
        if fail_closed_for_actionable(evaluation) and status == "UNAVAILABLE":
            reason_codes = [evaluation.reason_code]
    return {
        "status": status,
        "freshness": freshness,
        "entitlement": entitlement,
        "connection": connection,
        "source": source,
        "reason_codes": reason_codes,
        "freshness_evaluation": evaluation.to_dict(),
    }
