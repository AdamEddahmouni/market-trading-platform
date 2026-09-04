"""Live canary qualification report (BUILD 29)."""

from __future__ import annotations

from .identity import derive_canary_report_id
from .types import (
    LIVE_CANARY_SCHEMA_VERSION,
    CanaryDisposition,
    LiveCanaryQualificationReportV1,
    LiveCanaryRunV1,
)


def build_canary_qualification_report(
    *,
    canary_run: LiveCanaryRunV1,
    authorization_ref: str | None,
    opportunities_observed: int = 0,
    orders_confirmed: int = 0,
    submit_attempts: int = 0,
    acks: int = 0,
    fills: int = 0,
    cancels: int = 0,
    rejections: int = 0,
    real_notional_minor: int = 0,
    max_exposure_minor: int = 0,
    reconciliation_health: str = "UNKNOWN",
    broker_health: str = "UNKNOWN",
    kill_switch_events: tuple[str, ...] = (),
    authorization_lifecycle: tuple[str, ...] = (),
    unexpected_broker_activity: tuple[str, ...] = (),
    errors: tuple[str, ...] = (),
    final_portfolio_ref: str | None = None,
    final_reconciliation_ref: str | None = None,
    flat_end_status: str = "UNKNOWN",
    disposition: CanaryDisposition = CanaryDisposition.CANARY_NOT_EXECUTED,
    limitations: tuple[str, ...] = (),
) -> LiveCanaryQualificationReportV1:
    report = LiveCanaryQualificationReportV1(
        report_id="",
        schema_version=LIVE_CANARY_SCHEMA_VERSION,
        canary_run_ref=canary_run.canary_run_id,
        authorization_ref=authorization_ref,
        opportunities_observed=opportunities_observed,
        orders_confirmed=orders_confirmed,
        submit_attempts=submit_attempts,
        acks=acks,
        fills=fills,
        cancels=cancels,
        rejections=rejections,
        real_notional_minor=real_notional_minor,
        max_exposure_minor=max_exposure_minor,
        reconciliation_health=reconciliation_health,
        broker_health=broker_health,
        kill_switch_events=kill_switch_events,
        authorization_lifecycle=authorization_lifecycle,
        unexpected_broker_activity=unexpected_broker_activity,
        errors=errors,
        final_portfolio_ref=final_portfolio_ref,
        final_reconciliation_ref=final_reconciliation_ref,
        flat_end_status=flat_end_status,
        disposition=disposition,
        limitations=limitations,
    )
    object.__setattr__(report, "report_id", derive_canary_report_id(report))
    return report
