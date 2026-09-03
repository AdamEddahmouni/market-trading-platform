"""Pilot operational reviews (BUILD 33)."""

from __future__ import annotations

from .identity import derive_pilot_review_id
from .types import (
    PilotOperationalReviewV1,
    PilotReviewDisposition,
    SUPERVISED_PILOT_SCHEMA_VERSION,
)


def build_pilot_operational_review(
    *,
    pilot_run_ref: str,
    review_window_start_ns: int,
    review_window_end_ns: int,
    slo_summary: dict[str, str] | None = None,
    provider_failovers: int = 0,
    provider_divergences: int = 0,
    broker_reconciliation_summary: str = "CLEAN",
    sessions_count: int = 0,
    orders_count: int = 0,
    fills_count: int = 0,
    incidents_count: int = 0,
    alerts_count: int = 0,
    backup_restore_state: str = "CURRENT",
    resource_health: str = "STABLE",
    policy_cap_compliance: bool = True,
    unresolved_risks: tuple[str, ...] = (),
    operator_review_disposition: str = PilotReviewDisposition.CONTINUE_PILOT.value,
) -> PilotOperationalReviewV1:
    review = PilotOperationalReviewV1(
        review_id="",
        schema_version=SUPERVISED_PILOT_SCHEMA_VERSION,
        pilot_run_ref=pilot_run_ref,
        review_window_start_ns=review_window_start_ns,
        review_window_end_ns=review_window_end_ns,
        slo_summary=slo_summary or {"overall": "HEALTHY"},
        provider_failovers=provider_failovers,
        provider_divergences=provider_divergences,
        broker_reconciliation_summary=broker_reconciliation_summary,
        sessions_count=sessions_count,
        orders_count=orders_count,
        fills_count=fills_count,
        incidents_count=incidents_count,
        alerts_count=alerts_count,
        backup_restore_state=backup_restore_state,
        resource_health=resource_health,
        policy_cap_compliance=policy_cap_compliance,
        unresolved_risks=unresolved_risks,
        operator_review_disposition=operator_review_disposition,
    )
    object.__setattr__(review, "review_id", derive_pilot_review_id(review))
    return review


def review_disposition_authorizes_trading(disposition: str) -> bool:
    """Reviews recommend continuation only — never authorize orders."""
    return False
