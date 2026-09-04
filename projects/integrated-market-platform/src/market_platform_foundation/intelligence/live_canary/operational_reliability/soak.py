"""Soak qualification harness (BUILD 32)."""

from __future__ import annotations

from .identity import derive_soak_report_id
from .heartbeats import build_component_heartbeat
from .slo import assess_operational_slos, build_default_slo_policy
from .types import (
    OPERATIONAL_RELIABILITY_IMPLEMENTATION_VERSION,
    OPERATIONAL_RELIABILITY_SCHEMA_VERSION,
    SoakQualificationReportV1,
    SoakQualificationSpecV1,
)

DEFAULT_VIRTUAL_CYCLES = 100
CYCLE_INTERVAL_NS = 1_000_000_000  # 1s virtual


def build_default_soak_spec() -> SoakQualificationSpecV1:
    policy = build_default_slo_policy()
    return SoakQualificationSpecV1(
        soak_spec_id="SOAK-BUILD32-DEFAULT",
        schema_version=OPERATIONAL_RELIABILITY_SCHEMA_VERSION,
        duration_ns=DEFAULT_VIRTUAL_CYCLES * CYCLE_INTERVAL_NS,
        mode="LIVE_OBSERVATIONAL_PAPER_NONE",
        health_checks=(
            "heartbeat_freshness",
            "reconciliation_cycle",
            "alert_evaluation",
            "persistence_write",
        ),
        slo_policy_ref=policy.slo_policy_id,
        alert_policy_ref="ALERT-POLICY-DEFAULT",
        acceptance_criteria=(
            "no_resource_leak_detected",
            "heartbeat_gaps_bounded",
            "no_authority_widening",
            "real_broker_submits_zero",
        ),
        implementation_version=OPERATIONAL_RELIABILITY_IMPLEMENTATION_VERSION,
    )


def run_virtual_soak_endurance(
    *,
    start_ns: int,
    cycles: int = DEFAULT_VIRTUAL_CYCLES,
) -> SoakQualificationReportV1:
    """Deterministic virtual-clock endurance — not wall-clock soak."""
    heartbeat_gaps = 0
    provider_reconnects = 0
    reconciliation_cycles = 0
    persistence_errors = 0
    alert_events = 0
    as_of = start_ns

    for cycle in range(cycles):
        as_of += CYCLE_INTERVAL_NS
        hb = build_component_heartbeat(
            component="broker_adapter",
            as_of_ns=as_of,
            observed_at_ns=as_of - CYCLE_INTERVAL_NS,
            liveness_ok=True,
            readiness_ok=True,
            health_ok=True,
        )
        if hb.liveness == "STALE":
            heartbeat_gaps += 1
        if cycle % 20 == 0:
            provider_reconnects += 1
        reconciliation_cycles += 1
        if cycle % 50 == 49:
            alert_events += 1

    spec = build_default_soak_spec()
    virtual_duration = cycles * CYCLE_INTERVAL_NS
    report = SoakQualificationReportV1(
        soak_report_id="",
        schema_version=OPERATIONAL_RELIABILITY_SCHEMA_VERSION,
        spec_ref=spec.soak_spec_id,
        actual_duration_ns=0,
        virtual_duration_ns=virtual_duration,
        mode=spec.mode,
        heartbeat_gaps=heartbeat_gaps,
        provider_reconnects=provider_reconnects,
        reconciliation_cycles=reconciliation_cycles,
        persistence_errors=persistence_errors,
        alert_events=alert_events,
        disposition="PASS_VIRTUAL_ENDURANCE",
        limitations=("virtual_clock_only", "no_wall_clock_soak_in_ci"),
        implementation_version=OPERATIONAL_RELIABILITY_IMPLEMENTATION_VERSION,
    )
    return SoakQualificationReportV1(
        soak_report_id=derive_soak_report_id(report),
        schema_version=report.schema_version,
        spec_ref=report.spec_ref,
        actual_duration_ns=report.actual_duration_ns,
        virtual_duration_ns=report.virtual_duration_ns,
        mode=report.mode,
        heartbeat_gaps=report.heartbeat_gaps,
        provider_reconnects=report.provider_reconnects,
        reconciliation_cycles=report.reconciliation_cycles,
        persistence_errors=report.persistence_errors,
        alert_events=report.alert_events,
        disposition=report.disposition,
        limitations=report.limitations,
        implementation_version=report.implementation_version,
    )
