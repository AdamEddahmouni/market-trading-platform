"""Honesty projector for operator data_quality. Does not probe providers."""

from __future__ import annotations

from typing import Any, Mapping


def project_opportunity_data_quality(
    *,
    source: str,
    quality_decision: Mapping[str, Any] | None = None,
    live_observational_env: bool = False,
) -> dict[str, Any]:
    """Return an explicit quality record. Adapter presence is not FRESH/ENTITLED."""

    if live_observational_env:
        # Env flag is not sample-verified freshness.
        source = source if source else "UNKNOWN"
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
    return {
        "status": status,
        "freshness": freshness,
        "entitlement": entitlement,
        "connection": connection,
        "source": source,
        "reason_codes": reason_codes,
    }
