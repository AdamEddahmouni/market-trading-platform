"""Deployment plan and records (BUILD 34)."""

from __future__ import annotations

from .identity import derive_deployment_plan_id, derive_deployment_record_id
from .types import (
    DEPLOYMENT_IMPLEMENTATION_VERSION,
    DEPLOYMENT_SCHEMA_VERSION,
    DeploymentDisposition,
    DeploymentPlanV1,
    DeploymentRecordV1,
    DeploymentState,
)


def build_deployment_plan(
    *,
    target_environment: str,
    release_ref: str,
    config_ref: str,
    previous_deployment_ref: str | None = None,
    migration_plan_ref: str | None = None,
) -> DeploymentPlanV1:
    plan = DeploymentPlanV1(
        deployment_plan_id="",
        schema_version=DEPLOYMENT_SCHEMA_VERSION,
        target_environment=target_environment,
        release_ref=release_ref,
        previous_deployment_ref=previous_deployment_ref,
        service_changes=("operator-api", "market-data-runtime", "intelligence-runtime", "reconciliation-worker"),
        config_ref=config_ref,
        migration_plan_ref=migration_plan_ref,
        backup_prerequisite=migration_plan_ref is not None,
        pre_deploy_checks=(
            "release_hash_valid",
            "build33_ancestry",
            "configuration_valid",
            "secrets_referenced_not_embedded",
            "rollback_target_known",
        ),
        deployment_steps=(
            "halt_new_live_actions",
            "deploy_artifact",
            "start_services_blocked",
            "run_health_checks",
            "run_deployment_canary",
        ),
        health_checks=("persistence_ready", "operator_api_healthy", "reconciliation_worker_healthy"),
        canary_checks=("provider_readonly", "broker_readonly", "reconciliation", "zero_live_orders"),
        rollback_triggers=(
            "critical_service_unavailable",
            "artifact_mismatch",
            "reconciliation_failure",
            "canary_failure",
        ),
        post_deploy_verification=("artifact_hash_match", "config_hash_match", "runtime_version_report"),
        operator_approval_requirements=("deployment_approved",),
        implementation_version=DEPLOYMENT_IMPLEMENTATION_VERSION,
    )
    return DeploymentPlanV1(
        deployment_plan_id=derive_deployment_plan_id(plan),
        schema_version=plan.schema_version,
        target_environment=plan.target_environment,
        release_ref=plan.release_ref,
        previous_deployment_ref=plan.previous_deployment_ref,
        service_changes=plan.service_changes,
        config_ref=plan.config_ref,
        migration_plan_ref=plan.migration_plan_ref,
        backup_prerequisite=plan.backup_prerequisite,
        pre_deploy_checks=plan.pre_deploy_checks,
        deployment_steps=plan.deployment_steps,
        health_checks=plan.health_checks,
        canary_checks=plan.canary_checks,
        rollback_triggers=plan.rollback_triggers,
        post_deploy_verification=plan.post_deploy_verification,
        operator_approval_requirements=plan.operator_approval_requirements,
        implementation_version=plan.implementation_version,
        metadata=plan.metadata,
    )


def build_deployment_record(
    *,
    environment_ref: str,
    release_ref: str,
    deployment_started_ns: int,
    configuration_hash: str,
    artifact_hashes: dict[str, str],
    previous_deployment_ref: str | None = None,
    deployment_completed_ns: int | None = None,
    disposition: str = DeploymentDisposition.DEPLOYMENT_QUALIFIED.value,
) -> DeploymentRecordV1:
    record = DeploymentRecordV1(
        deployment_record_id="",
        schema_version=DEPLOYMENT_SCHEMA_VERSION,
        environment_ref=environment_ref,
        release_ref=release_ref,
        deployment_started_ns=deployment_started_ns,
        deployment_completed_ns=deployment_completed_ns,
        previous_deployment_ref=previous_deployment_ref,
        artifact_hashes_observed=artifact_hashes,
        configuration_hash_observed=configuration_hash,
        schema_before="intelligence-v1",
        schema_after="intelligence-v1",
        service_state={"operator-api": DeploymentState.ACTIVE.value},
        health_readiness_result="BLOCKED",
        deployment_disposition=disposition,
        lineage={"live_authority_granted": False},
    )
    return DeploymentRecordV1(
        deployment_record_id=derive_deployment_record_id(record),
        schema_version=record.schema_version,
        environment_ref=record.environment_ref,
        release_ref=record.release_ref,
        deployment_started_ns=record.deployment_started_ns,
        deployment_completed_ns=record.deployment_completed_ns,
        previous_deployment_ref=record.previous_deployment_ref,
        artifact_hashes_observed=record.artifact_hashes_observed,
        configuration_hash_observed=record.configuration_hash_observed,
        schema_before=record.schema_before,
        schema_after=record.schema_after,
        service_state=record.service_state,
        health_readiness_result=record.health_readiness_result,
        deployment_disposition=record.deployment_disposition,
        lineage=record.lineage,
        implementation_version=record.implementation_version,
    )


def deployment_grants_live_authority(record: DeploymentRecordV1) -> bool:
    return bool(record.lineage.get("live_authority_granted"))
