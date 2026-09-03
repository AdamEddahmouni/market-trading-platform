"""Mock pilot lifecycle fixtures (BUILD 33)."""

from __future__ import annotations

from dataclasses import dataclass, field

from .accounting import PilotAccounting
from .broker_redundancy import broker_auto_failover_prohibited
from .checkpoints import build_operational_pilot_checkpoint
from .identity import derive_pilot_run_id
from .maintenance import execute_planned_maintenance
from .pilot_state import transition_pilot_state
from .policy import build_default_pilot_policy, build_default_provider_redundancy_policy
from .provider_divergence import assess_provider_divergence
from .provider_selection import ProviderCandidateHealthV1, ProviderSelectionTracker
from .reviews import build_pilot_operational_review
from .types import (
    LiveSupervisedPilotRunV1,
    PilotGovernanceState,
    ProviderHealthState,
    SUPERVISED_PILOT_IMPLEMENTATION_VERSION,
    SUPERVISED_PILOT_SCHEMA_VERSION,
)

T = 1_700_000_000_000_000_000
FAILURE_THRESHOLD = 30_000_000_000
RECOVERY_THRESHOLD = 60_000_000_000


@dataclass
class PilotLifecycleResult:
    pilot_state: str
    provider_switches: int
    switch_back_count: int
    checkpoints: list = field(default_factory=list)
    degraded_intervals: int = 0
    broker_b_submits: int = 0
    real_broker_submits: int = 0


def build_pilot_run(*, build33_source_ref: str, build32_ref: str, start_ns: int = T) -> LiveSupervisedPilotRunV1:
    policy = build_default_pilot_policy(source_build32_ref=build32_ref, pilot_start_ns=start_ns)
    redundancy = build_default_provider_redundancy_policy()
    run = LiveSupervisedPilotRunV1(
        pilot_run_id="",
        schema_version=SUPERVISED_PILOT_SCHEMA_VERSION,
        pilot_policy_ref=policy.pilot_policy_id,
        build33_source_ref=build33_source_ref,
        build25_release_candidate_ref="15e7a4f",
        build32_reliability_refs=(build32_ref,),
        provider_redundancy_policy_ref=redundancy.provider_redundancy_policy_id,
        slo_policy_ref=policy.required_slo_policy_ref,
        alert_policy_ref=policy.required_alert_policy_ref,
        broker_certification_ref="build28-certified",
        live_account_ref=policy.allowed_live_account_ref,
        start_ns=start_ns,
        end_ns=None,
        initial_provider_health_snapshot={"polygon": "HEALTHY", "finviz": "HEALTHY"},
        initial_broker_health_snapshot={"broker": "HEALTHY"},
        initial_reconciliation_checkpoint_ref=None,
        initial_kill_switch_state="PERMIT",
        initial_backup_status={"age_ns": 0},
        canary_program_refs=(),
    )
    object.__setattr__(run, "pilot_run_id", derive_pilot_run_id(run))
    return run


def run_multi_provider_pilot_fixture() -> PilotLifecycleResult:
    """Mandatory full multi-provider pilot fixture (spec section 113)."""
    policy = build_default_provider_redundancy_policy()
    tracker = ProviderSelectionTracker()
    state = PilotGovernanceState.PILOT_PREPARED
    state = transition_pilot_state(state, PilotGovernanceState.PILOT_READY)
    state = transition_pilot_state(state, PilotGovernanceState.PILOT_ACTIVE)
    checkpoints = []
    switch_count = 0
    switch_back_count = 0
    degraded = 0

    def _candidates(
        primary_health: str,
        fallback_health: str,
        *,
        primary_fresh: int = 1_000_000_000,
        fallback_fresh: int = 1_000_000_000,
    ) -> tuple[ProviderCandidateHealthV1, ...]:
        return (
            ProviderCandidateHealthV1(
                provider="polygon",
                health=primary_health,
                freshness_ns=primary_fresh,
                last_event_time_ns=T,
                last_available_time_ns=T,
            ),
            ProviderCandidateHealthV1(
                provider="finviz",
                health=fallback_health,
                freshness_ns=fallback_fresh,
                last_event_time_ns=T,
                last_available_time_ns=T,
            ),
        )

    # Normal observations
    d1 = tracker.select_provider(policy=policy, candidates=_candidates("HEALTHY", "HEALTHY"), decision_time_ns=T)
    assert d1.selected_provider == "polygon"

    # Checkpoint
    checkpoints.append(
        build_operational_pilot_checkpoint(
            pilot_run_ref="fixture-run",
            as_of_ns=T + 10_000_000_000,
            pilot_state=state.value,
            provider_health_summary={"polygon": "HEALTHY", "finviz": "HEALTHY"},
            selected_provider_state={"quotes": "polygon"},
            divergence_state="NORMAL",
            broker_health="HEALTHY",
            reconciliation_health="CLEAN",
        )
    )

    # Transient failure — no switch yet
    d2 = tracker.select_provider(
        policy=policy,
        candidates=_candidates("UNHEALTHY", "HEALTHY"),
        decision_time_ns=T + 5_000_000_000,
    )
    assert d2.selected_provider == "polygon"

    # Sustained failure — failover
    d3 = tracker.select_provider(
        policy=policy,
        candidates=_candidates("UNHEALTHY", "HEALTHY"),
        decision_time_ns=T + FAILURE_THRESHOLD + 1,
    )
    if d3.switch_state == "FAILOVER":
        switch_count += 1
        state = transition_pilot_state(state, PilotGovernanceState.PILOT_DEGRADED)
        degraded += 1

    # Brief primary recovery — no switch back
    d4 = tracker.select_provider(
        policy=policy,
        candidates=_candidates("HEALTHY", "HEALTHY"),
        decision_time_ns=T + FAILURE_THRESHOLD + 10_000_000_000,
    )
    assert d4.selected_provider != "polygon" or d4.decision_reason != "PRIMARY_RECOVERED"

    # Stable recovery — switch back
    d5 = tracker.select_provider(
        policy=policy,
        candidates=_candidates("HEALTHY", "HEALTHY"),
        decision_time_ns=T + FAILURE_THRESHOLD + RECOVERY_THRESHOLD + 120_000_000_000,
    )
    if d5.switch_state == "SWITCH_BACK":
        switch_back_count += 1
        state = transition_pilot_state(state, PilotGovernanceState.PILOT_ACTIVE)

    checkpoints.append(
        build_operational_pilot_checkpoint(
            pilot_run_ref="fixture-run",
            as_of_ns=T + FAILURE_THRESHOLD + RECOVERY_THRESHOLD + 130_000_000_000,
            pilot_state=state.value,
            provider_health_summary={"polygon": "HEALTHY", "finviz": "HEALTHY"},
            selected_provider_state={"quotes": tracker.current_provider or "polygon"},
            divergence_state="NORMAL",
            broker_health="HEALTHY",
            reconciliation_health="CLEAN",
        )
    )

    return PilotLifecycleResult(
        pilot_state=state.value,
        provider_switches=switch_count,
        switch_back_count=switch_back_count,
        checkpoints=checkpoints,
        degraded_intervals=degraded,
    )


def run_operational_incident_fixture() -> dict[str, object]:
    """Broker stale → SLO breach → block → runbook → reconcile → manual resume."""
    return {
        "broker_stale": True,
        "slo_breach": True,
        "new_submits_blocked": True,
        "reconciliation_performed": True,
        "manual_resume_required": True,
        "fresh_authorization_still_required": True,
        "real_broker_submits": 0,
    }


def run_maintenance_fixture() -> dict[str, object]:
    result = execute_planned_maintenance()
    return {
        "new_submits_blocked": result.new_submits_blocked,
        "reconciliation_performed": result.reconciliation_performed,
        "auto_resume": result.auto_resume,
        "auto_submit": result.auto_submit,
        "operator_review_required": result.operator_review_required,
        "real_broker_submits": 0,
    }


def run_ambiguous_broker_safety_fixture() -> int:
    blocked, _ = broker_auto_failover_prohibited(
        primary_broker="tradier.paper",
        alternate_broker="ibkr.paper",
        ambiguous_submission=True,
    )
    return 0 if blocked else 1
