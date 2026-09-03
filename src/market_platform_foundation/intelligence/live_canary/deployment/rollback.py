"""Deployment rollback (BUILD 34)."""

from __future__ import annotations

from .identity import derive_rollback_decision_id, derive_rollback_plan_id
from .types import (
    DEPLOYMENT_IMPLEMENTATION_VERSION,
    DEPLOYMENT_SCHEMA_VERSION,
    DeploymentRollbackDecisionV1,
    DeploymentRollbackPlanV1,
    RollbackDecision,
)


def build_rollback_plan(
    *,
    deployment_ref: str,
    rollback_target_release: str,
    rollback_target_deployment: str,
    schema_compatible: bool = True,
) -> DeploymentRollbackPlanV1:
    plan = DeploymentRollbackPlanV1(
        rollback_plan_id="",
        schema_version=DEPLOYMENT_SCHEMA_VERSION,
        deployment_ref=deployment_ref,
        rollback_target_release=rollback_target_release,
        rollback_target_deployment=rollback_target_deployment,
        preconditions=(
            "halt_new_live_actions",
            "backup_verified",
            "rollback_target_known_good",
        ),
        schema_compatibility="COMPATIBLE" if schema_compatible else "INCOMPATIBLE",
        service_sequence=(
            "stop_failed_services",
            "restore_release_a",
            "start_services_blocked",
            "broker_reconciliation",
            "operator_review",
        ),
        broker_reconciliation_requirements=(
            "reconcile_broker_truth",
            "detect_broker_only_orders",
            "no_order_replay",
        ),
        post_rollback_validation=(
            "artifact_hash_match",
            "config_hash_match",
            "reconciliation_clean",
            "live_starts_blocked",
        ),
        operator_approval_requirements=("rollback_approved", "operator_review"),
        implementation_version=DEPLOYMENT_IMPLEMENTATION_VERSION,
    )
    return DeploymentRollbackPlanV1(
        rollback_plan_id=derive_rollback_plan_id(plan),
        schema_version=plan.schema_version,
        deployment_ref=plan.deployment_ref,
        rollback_target_release=plan.rollback_target_release,
        rollback_target_deployment=plan.rollback_target_deployment,
        preconditions=plan.preconditions,
        schema_compatibility=plan.schema_compatibility,
        service_sequence=plan.service_sequence,
        broker_reconciliation_requirements=plan.broker_reconciliation_requirements,
        post_rollback_validation=plan.post_rollback_validation,
        operator_approval_requirements=plan.operator_approval_requirements,
        implementation_version=plan.implementation_version,
    )


def decide_rollback(
    *,
    deployment_ref: str,
    rollback_plan: DeploymentRollbackPlanV1,
    failure_reason: str,
    schema_compatible: bool = True,
    broker_ambiguous: bool = False,
) -> DeploymentRollbackDecisionV1:
    if not schema_compatible or rollback_plan.schema_compatibility == "INCOMPATIBLE":
        decision = RollbackDecision.HALT_ENVIRONMENT.value
        reasons = (failure_reason, "schema incompatible — rollback unsafe")
    elif broker_ambiguous:
        decision = RollbackDecision.HALT_ENVIRONMENT.value
        reasons = (failure_reason, "ambiguous broker state — no auto-resend")
    else:
        decision = RollbackDecision.ROLLBACK.value
        reasons = (failure_reason,)

    rb = DeploymentRollbackDecisionV1(
        rollback_decision_id="",
        schema_version=DEPLOYMENT_SCHEMA_VERSION,
        deployment_ref=deployment_ref,
        decision=decision,
        reasons=reasons,
        rollback_plan_ref=rollback_plan.rollback_plan_id,
        implementation_version=DEPLOYMENT_IMPLEMENTATION_VERSION,
    )
    return DeploymentRollbackDecisionV1(
        rollback_decision_id=derive_rollback_decision_id(rb),
        schema_version=rb.schema_version,
        deployment_ref=rb.deployment_ref,
        decision=rb.decision,
        reasons=rb.reasons,
        rollback_plan_ref=rb.rollback_plan_ref,
        implementation_version=rb.implementation_version,
    )


def rollback_auto_resumes_live() -> bool:
    return False
