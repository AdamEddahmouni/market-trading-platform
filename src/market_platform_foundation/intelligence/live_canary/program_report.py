"""Program and session reports (BUILD 30)."""

from __future__ import annotations

from .identity import derive_program_report_id, derive_session_report_id
from .types import (
    LIVE_CANARY_SCHEMA_VERSION,
    LiveCanaryProgramReportV1,
    LiveCanarySessionReportV1,
    ProgramDisposition,
    SessionDisposition,
)


def build_session_report(
    *,
    session_ref: str,
    program_run_ref: str,
    authorization_ref: str | None,
    confirmations: tuple[str, ...] = (),
    submit_attempts: int = 0,
    acks: int = 0,
    fills: int = 0,
    rejections: int = 0,
    cancels: int = 0,
    max_exposure_minor: int = 0,
    fees_minor: int = 0,
    incident_refs: tuple[str, ...] = (),
    reconciliation_checkpoint_ref: str | None = None,
    final_authorization_state: str = "DISABLED",
    disposition: SessionDisposition = SessionDisposition.SESSION_NOT_EXECUTED,
    limitations: tuple[str, ...] = (),
) -> LiveCanarySessionReportV1:
    report = LiveCanarySessionReportV1(
        session_report_id="",
        schema_version=LIVE_CANARY_SCHEMA_VERSION,
        session_ref=session_ref,
        program_run_ref=program_run_ref,
        authorization_ref=authorization_ref,
        confirmations=confirmations,
        submit_attempts=submit_attempts,
        acks=acks,
        fills=fills,
        rejections=rejections,
        cancels=cancels,
        max_exposure_minor=max_exposure_minor,
        fees_minor=fees_minor,
        incident_refs=incident_refs,
        reconciliation_checkpoint_ref=reconciliation_checkpoint_ref,
        final_authorization_state=final_authorization_state,
        disposition=disposition,
        limitations=limitations,
    )
    object.__setattr__(report, "session_report_id", derive_session_report_id(report))
    return report


def build_program_report(
    *,
    program_run_ref: str,
    program_policy_ref: str,
    session_refs: tuple[str, ...],
    sessions_prepared: int,
    sessions_authorized: int,
    sessions_executed: int,
    sessions_clean: int,
    sessions_halted: int,
    total_orders: int,
    total_fills: int,
    aggregate_notional_minor: int,
    fees_minor: int = 0,
    incident_counts: dict[str, int] | None = None,
    reconciliation_outcomes: tuple[str, ...] = (),
    restart_events: int = 0,
    external_activity_detected: bool = False,
    program_cap_usage: dict[str, int] | None = None,
    final_kill_switch_state: str = "ACTIVE_BLOCK",
    disposition: ProgramDisposition = ProgramDisposition.MORE_SUPERVISED_EVIDENCE_REQUIRED,
    limitations: tuple[str, ...] = (),
) -> LiveCanaryProgramReportV1:
    report = LiveCanaryProgramReportV1(
        program_report_id="",
        schema_version=LIVE_CANARY_SCHEMA_VERSION,
        program_run_ref=program_run_ref,
        program_policy_ref=program_policy_ref,
        session_refs=session_refs,
        sessions_prepared=sessions_prepared,
        sessions_authorized=sessions_authorized,
        sessions_executed=sessions_executed,
        sessions_clean=sessions_clean,
        sessions_halted=sessions_halted,
        total_orders=total_orders,
        total_fills=total_fills,
        aggregate_notional_minor=aggregate_notional_minor,
        fees_minor=fees_minor,
        incident_counts=incident_counts or {},
        reconciliation_outcomes=reconciliation_outcomes,
        restart_events=restart_events,
        external_activity_detected=external_activity_detected,
        program_cap_usage=program_cap_usage or {},
        final_kill_switch_state=final_kill_switch_state,
        disposition=disposition,
        limitations=limitations,
    )
    object.__setattr__(report, "program_report_id", derive_program_report_id(report))
    return report
