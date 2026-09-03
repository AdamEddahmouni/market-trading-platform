"""Deployment fixture runners (BUILD 34)."""

from __future__ import annotations

from dataclasses import dataclass

from .canary import build_deployment_canary_spec, run_deployment_canary
from .change_control import build_change_request
from .configuration import configuration_hash
from .environment import build_environment_manifest
from .migration import build_migration_plan, destructive_migration_without_backup_blocked
from .packaging import build_release_manifest, compare_semantic_identity
from .plan import build_deployment_plan, build_deployment_record, deployment_grants_live_authority
from .promotion import promote_release, validate_promotion_gates
from .qualification import build_deployment_qualification_report, build_deployment_qualification_spec
from .rollback import build_rollback_plan, decide_rollback, rollback_auto_resumes_live
from .supervision import FixtureServiceSupervisor, build_default_service_graph, validate_startup_order
from .types import (
    ChangeApprovalState,
    ChangeType,
    DeploymentDisposition,
    EnvironmentKind,
    PromotionResult,
    RollbackDecision,
)

T = 1_700_000_000_000_000_000
BUILD33_HEAD = "16bf0f3e854e99ac2e992d8c7245b8f1742979b9"
BUILD33_QUAL_REF = "BUILD33-SUPERVISED-PRODUCTION-PILOT-QUALIFIED"


@dataclass(frozen=True)
class FullDeploymentFixtureResultV1:
    release_blocked: bool
    release_id: str
    test_env_id: str
    supervised_live_env_id: str
    promotion_result: str
    deployment_id: str
    canary_disposition: str
    real_broker_submits: int
    qualification_disposition: str
    live_authority_granted: bool


@dataclass(frozen=True)
class FailedDeploymentRollbackFixtureResultV1:
    release_a_id: str
    release_b_deployment_failed: bool
    rollback_decision: str
    release_a_restored: bool
    broker_reconciled: bool
    orders_replayed: int
    live_auto_resume: bool


@dataclass(frozen=True)
class MigrationFixtureResultV1:
    migration_plan_id: str
    backup_required: bool
    forward_migration: str
    rollback_compatible: bool


def run_full_successful_deployment_fixture(
    *,
    build_timestamp_ns: int = T,
    allow_dirty: bool = False,
) -> FullDeploymentFixtureResultV1:
    release_result = build_release_manifest(
        build_timestamp_ns=build_timestamp_ns,
        build33_qualification_ref=BUILD33_QUAL_REF,
        allow_dirty=allow_dirty,
    )
    if release_result.blocked:
        return FullDeploymentFixtureResultV1(
            release_blocked=True,
            release_id="BLOCKED",
            test_env_id="",
            supervised_live_env_id="",
            promotion_result="BLOCKED",
            deployment_id="",
            canary_disposition="BLOCKED",
            real_broker_submits=0,
            qualification_disposition=DeploymentDisposition.DEPLOYMENT_BLOCKED.value,
            live_authority_granted=False,
        )

    release = release_result.manifest
    test_env = build_environment_manifest(
        environment_kind=EnvironmentKind.TEST.value,
        release_manifest_ref=release.release_manifest_id,
        build33_qualification_ref=BUILD33_QUAL_REF,
    )
    supervised_env = build_environment_manifest(
        environment_kind=EnvironmentKind.SUPERVISED_LIVE.value,
        release_manifest_ref=release.release_manifest_id,
        build33_qualification_ref=BUILD33_QUAL_REF,
    )
    artifact_hash = release.artifact_hashes["bundle_content"]
    promo = promote_release(
        release=release,
        from_environment=EnvironmentKind.TEST.value,
        to_environment=EnvironmentKind.SUPERVISED_LIVE.value,
        artifact_hash=artifact_hash,
        qualification_refs=(BUILD33_QUAL_REF,),
        promotion_time_ns=T,
    )
    gates_ok, _ = validate_promotion_gates(
        release=release,
        to_environment=EnvironmentKind.SUPERVISED_LIVE.value,
        build33_ref=BUILD33_QUAL_REF,
        artifact_hash=artifact_hash,
        source_artifact_hash=artifact_hash,
    )
    assert gates_ok

    plan = build_deployment_plan(
        target_environment=supervised_env.environment_manifest_id,
        release_ref=release.release_manifest_id,
        config_ref=supervised_env.configuration_ref,
    )
    change = build_change_request(
        change_type=ChangeType.CODE_RELEASE.value,
        release_ref=release.release_manifest_id,
        target_environment=supervised_env.environment_manifest_id,
        reason="BUILD34 qualification deployment",
        rollback_target="NONE",
        approval_state=ChangeApprovalState.APPROVED.value,
    )
    deployment = build_deployment_record(
        environment_ref=supervised_env.environment_manifest_id,
        release_ref=release.release_manifest_id,
        deployment_started_ns=T,
        configuration_hash=supervised_env.configuration_hash,
        artifact_hashes=release.artifact_hashes,
        deployment_completed_ns=T + 60_000_000_000,
    )

    graph = build_default_service_graph(supervised_env.environment_manifest_id)
    order_ok, _ = validate_startup_order(graph)
    assert order_ok
    supervisor = FixtureServiceSupervisor()
    for svc in graph.services:
        supervisor.register(svc)
    for svc_id in graph.startup_order:
        defn = next(s for s in graph.services if s.service_id == svc_id)
        deps_ready = (
            all(supervisor.services[d].observed_state == "RUNNING" for d in defn.dependencies)
            if defn.dependencies
            else True
        )
        supervisor.start_service(
            svc_id,
            release_ref=release.release_manifest_id,
            start_time_ns=T,
            dependencies_ready=deps_ready,
        )

    canary_spec = build_deployment_canary_spec(deployment_plan_ref=plan.deployment_plan_id)
    canary = run_deployment_canary(
        canary_spec=canary_spec,
        observation_duration_ns=canary_spec.minimum_observation_duration_ns,
    )

    qual_spec = build_deployment_qualification_spec(
        release_ref=release.release_manifest_id,
        environment_kind=EnvironmentKind.SUPERVISED_LIVE.value,
    )
    qualification = build_deployment_qualification_report(
        spec=qual_spec,
        release_reproducibility="PASS",
        environment_validation="PASS",
        deployment_result="PASS",
        service_supervision="PASS",
        deployment_canary=canary.disposition,
        migration="PASS",
        rollback="PASS",
        config_drift="PASS",
        operator_visibility="PASS",
        security="PASS",
        real_broker_submits=canary.real_broker_submits,
    )

    return FullDeploymentFixtureResultV1(
        release_blocked=False,
        release_id=release.release_manifest_id,
        test_env_id=test_env.environment_manifest_id,
        supervised_live_env_id=supervised_env.environment_manifest_id,
        promotion_result=promo.result,
        deployment_id=deployment.deployment_record_id,
        canary_disposition=canary.disposition,
        real_broker_submits=canary.real_broker_submits,
        qualification_disposition=qualification.disposition,
        live_authority_granted=deployment_grants_live_authority(deployment),
    )


def run_failed_deployment_rollback_fixture() -> FailedDeploymentRollbackFixtureResultV1:
    release_a = build_release_manifest(
        build_timestamp_ns=T,
        build33_qualification_ref=BUILD33_QUAL_REF,
        allow_dirty=True,
    )
    release_b = build_release_manifest(
        build_timestamp_ns=T + 1,
        build33_qualification_ref=BUILD33_QUAL_REF,
        allow_dirty=True,
    )
    deploy_a = build_deployment_record(
        environment_ref="ENV-test",
        release_ref=release_a.manifest.release_manifest_id,
        deployment_started_ns=T,
        configuration_hash="hash-a",
        artifact_hashes=release_a.manifest.artifact_hashes,
        disposition=DeploymentDisposition.DEPLOYMENT_QUALIFIED.value,
    )
    deploy_b = build_deployment_record(
        environment_ref="ENV-test",
        release_ref=release_b.manifest.release_manifest_id,
        deployment_started_ns=T + 1000,
        configuration_hash="hash-b",
        artifact_hashes=release_b.manifest.artifact_hashes,
        previous_deployment_ref=deploy_a.deployment_record_id,
        disposition=DeploymentDisposition.DEPLOYMENT_FAILED.value,
    )
    rollback_plan = build_rollback_plan(
        deployment_ref=deploy_b.deployment_record_id,
        rollback_target_release=release_a.manifest.release_manifest_id,
        rollback_target_deployment=deploy_a.deployment_record_id,
    )
    decision = decide_rollback(
        deployment_ref=deploy_b.deployment_record_id,
        rollback_plan=rollback_plan,
        failure_reason="reconciliation_failure",
    )
    return FailedDeploymentRollbackFixtureResultV1(
        release_a_id=release_a.manifest.release_manifest_id,
        release_b_deployment_failed=deploy_b.deployment_disposition == DeploymentDisposition.DEPLOYMENT_FAILED.value,
        rollback_decision=decision.decision,
        release_a_restored=decision.decision == RollbackDecision.ROLLBACK.value,
        broker_reconciled=True,
        orders_replayed=0,
        live_auto_resume=rollback_auto_resumes_live(),
    )


def run_migration_fixture(*, backup_verified: bool = True) -> MigrationFixtureResultV1:
    plan = build_migration_plan()
    blocked, _ = destructive_migration_without_backup_blocked(plan, backup_verified=backup_verified)
    return MigrationFixtureResultV1(
        migration_plan_id=plan.migration_plan_id,
        backup_required=plan.backup_prerequisite,
        forward_migration="BLOCKED" if blocked else "PASS",
        rollback_compatible=plan.rollback_supported,
    )


def run_reproducibility_fixture() -> bool:
    a = build_release_manifest(build_timestamp_ns=T, build33_qualification_ref=BUILD33_QUAL_REF, allow_dirty=True)
    b = build_release_manifest(build_timestamp_ns=T + 999, build33_qualification_ref=BUILD33_QUAL_REF, allow_dirty=True)
    return compare_semantic_identity(a, b)
