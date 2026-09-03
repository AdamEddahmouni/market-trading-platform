"""Recovery planning and startup semantics (BUILD 32)."""

from __future__ import annotations

from .identity import derive_recovery_plan_id
from .types import (
    OPERATIONAL_RELIABILITY_IMPLEMENTATION_VERSION,
    OPERATIONAL_RELIABILITY_SCHEMA_VERSION,
    RecoveryPlanV1,
)

RECOVERED_STARTUP_MODE = "BLOCKED_PENDING_RECONCILIATION"


def build_default_recovery_plan(*, failure_scenario: str = "process_crash") -> RecoveryPlanV1:
    plan = RecoveryPlanV1(
        recovery_plan_id="",
        schema_version=OPERATIONAL_RELIABILITY_SCHEMA_VERSION,
        failure_scenario=failure_scenario,
        restore_order=(
            "load_kill_switch",
            "load_governance_state",
            "load_ledger",
            "load_incidents",
            "connect_broker_read_only",
            "reconcile",
            "surface_incidents",
            "await_operator_review",
        ),
        integrity_checks=(
            "backup_hash_verification",
            "schema_version_check",
            "kill_switch_integrity",
        ),
        reconciliation_steps=(
            "broker_reconciliation",
            "detect_broker_only_orders",
            "detect_local_only_orders",
            "detect_ambiguous_submissions",
        ),
        startup_mode=RECOVERED_STARTUP_MODE,
        requires_operator_approval=True,
        rpo_objective_ns=300_000_000_000,
        rto_objective_ns=600_000_000_000,
        limitations=(
            "local qualification only — not production infrastructure SLA",
            "broker remains external truth for live order state",
            "recovered runtime never auto-submits or auto-resumes",
        ),
        implementation_version=OPERATIONAL_RELIABILITY_IMPLEMENTATION_VERSION,
    )
    return RecoveryPlanV1(
        recovery_plan_id=derive_recovery_plan_id(plan),
        schema_version=plan.schema_version,
        failure_scenario=plan.failure_scenario,
        restore_order=plan.restore_order,
        integrity_checks=plan.integrity_checks,
        reconciliation_steps=plan.reconciliation_steps,
        startup_mode=plan.startup_mode,
        requires_operator_approval=plan.requires_operator_approval,
        rpo_objective_ns=plan.rpo_objective_ns,
        rto_objective_ns=plan.rto_objective_ns,
        limitations=plan.limitations,
        implementation_version=plan.implementation_version,
    )


def recovered_runtime_blocks_live(*, reconciliation_clean: bool, operator_approved: bool) -> bool:
    """Recovered runtime starts blocked until reconciliation and operator review."""
    if not reconciliation_clean:
        return True
    if not operator_approved:
        return True
    return False
