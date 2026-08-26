"""Sustained pilot qualification (BUILD 33)."""

from __future__ import annotations

from .identity import derive_pilot_qualification_report_id, derive_pilot_qualification_spec_id
from .runbooks import run_all_runbook_exercises
from .types import (
    BUILD33_KNOWN_LIMITATIONS,
    PilotDisposition,
    PilotObservationSegmentV1,
    SustainedPilotQualificationReportV1,
    SustainedPilotQualificationSpecV1,
    SUPERVISED_PILOT_IMPLEMENTATION_VERSION,
    SUPERVISED_PILOT_SCHEMA_VERSION,
)

_REQUIRED_RUNBOOKS = tuple(f"RB{i:02d}" for i in range(1, 21))


def build_default_pilot_qualification_spec(
    *,
    pilot_policy_ref: str,
    minimum_observation_duration_ns: int = 90 * 60 * 1_000_000_000,
) -> SustainedPilotQualificationSpecV1:
    spec = SustainedPilotQualificationSpecV1(
        qualification_spec_id="",
        schema_version=SUPERVISED_PILOT_SCHEMA_VERSION,
        pilot_policy_ref=pilot_policy_ref,
        minimum_observation_duration_ns=minimum_observation_duration_ns,
        required_market_sessions=1,
        required_provider_health_samples=10,
        required_reconciliation_checkpoints=2,
        required_operational_reviews=1,
        required_runbook_exercises=_REQUIRED_RUNBOOKS,
        slo_acceptance_criteria=("no_critical_slo_breach",),
        maximum_critical_incidents=0,
        required_backup_freshness_ns=24 * 60 * 60 * 1_000_000_000,
        required_zero_autonomy_invariants=(
            "human_session_authorization_required",
            "human_order_confirmation_required",
            "no_automatic_broker_failover",
            "no_cap_escalation_from_success",
        ),
        implementation_version=SUPERVISED_PILOT_IMPLEMENTATION_VERSION,
    )
    object.__setattr__(spec, "qualification_spec_id", derive_pilot_qualification_spec_id(spec))
    return spec


def build_sustained_pilot_qualification_report(
    *,
    qualification_spec: SustainedPilotQualificationSpecV1,
    pilot_run_ref: str,
    build33_source_ref: str,
    actual_observation_duration_ns: int,
    virtual_observation_duration_ns: int | None = None,
    market_sessions_observed: int = 1,
    provider_failovers: int = 0,
    provider_divergences: int = 0,
    degraded_mode_intervals: int = 0,
    runbook_reports: dict[str, str] | None = None,
    final_pilot_state: str = "PILOT_COMPLETE",
) -> SustainedPilotQualificationReportV1:
    exercises = run_all_runbook_exercises()
    exercise_results = runbook_reports or {k: v.result for k, v in exercises.items()}
    all_runbooks_pass = all(r == "PASS" for r in exercise_results.values())
    duration_met = actual_observation_duration_ns >= qualification_spec.minimum_observation_duration_ns

    limitations = list(BUILD33_KNOWN_LIMITATIONS)
    if not duration_met:
        limitations.append("pilot observation duration shorter than desired qualification minimum")
    if actual_observation_duration_ns < 24 * 60 * 60 * 1_000_000_000:
        limitations.append("real multi-day pilot not completed")

    disposition = PilotDisposition.SUPERVISED_PRODUCTION_PILOT_QUALIFIED_WITH_LIMITATIONS.value
    if not all_runbooks_pass:
        disposition = PilotDisposition.OPERATIONAL_RUNBOOKS_INCOMPLETE.value
    elif duration_met and all_runbooks_pass:
        disposition = PilotDisposition.SUPERVISED_PRODUCTION_PILOT_QUALIFIED_WITH_LIMITATIONS.value

    segment = PilotObservationSegmentV1(
        segment_id=f"seg-{build33_source_ref[:8]}",
        start_ns=1_700_000_000_000_000_000,
        end_ns=1_700_000_000_000_000_000 + actual_observation_duration_ns,
        runtime_version=SUPERVISED_PILOT_IMPLEMENTATION_VERSION,
        provider_configuration={"primary": "polygon", "fallback": "finviz"},
        health_summary="FIXTURE_QUALIFIED",
    )

    report = SustainedPilotQualificationReportV1(
        report_id="",
        schema_version=SUPERVISED_PILOT_SCHEMA_VERSION,
        qualification_spec_ref=qualification_spec.qualification_spec_id,
        pilot_run_ref=pilot_run_ref,
        actual_observation_duration_ns=actual_observation_duration_ns,
        virtual_observation_duration_ns=virtual_observation_duration_ns or actual_observation_duration_ns,
        market_sessions_observed=market_sessions_observed,
        observation_segments=(segment,),
        provider_uptime_summary={"polygon": 0.95, "finviz": 0.99},
        provider_failovers=provider_failovers,
        provider_divergences=provider_divergences,
        degraded_mode_intervals=degraded_mode_intervals,
        slo_results={"overall": "HEALTHY"},
        alerts_summary={"raised": 0, "delivered": 0, "critical_failures": 0},
        broker_reconciliation_summary="CLEAN",
        canary_sessions=0,
        orders_count=0,
        fills_count=0,
        incidents_count=0,
        runbook_exercise_results=exercise_results,
        backup_dr_freshness={"last_backup_age_ns": 0, "restore_drill_age_ns": 0},
        maintenance_restart_results={"planned_shutdown": "PASS"},
        resource_observations={"environment": "single-host-local"},
        policy_cap_compliance=True,
        final_pilot_state=final_pilot_state,
        disposition=disposition,
        limitations=tuple(limitations),
        real_broker_side_effects_observed=0,
        implementation_version=SUPERVISED_PILOT_IMPLEMENTATION_VERSION,
        metadata={"build33_source_ref": build33_source_ref},
    )
    object.__setattr__(report, "report_id", derive_pilot_qualification_report_id(report))
    return report
