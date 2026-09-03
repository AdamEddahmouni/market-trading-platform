"""Deployment qualification (BUILD 34)."""

from __future__ import annotations

from .identity import derive_qualification_report_id, derive_qualification_spec_id
from .types import (
    BUILD34_KNOWN_LIMITATIONS,
    DEPLOYMENT_IMPLEMENTATION_VERSION,
    DEPLOYMENT_SCHEMA_VERSION,
    DeploymentDisposition,
    DeploymentQualificationReportV1,
    DeploymentQualificationSpecV1,
)

ZERO_AUTONOMY_INVARIANTS = (
    "deployment_does_not_create_live_authorization",
    "deployment_does_not_confirm_order",
    "deployment_does_not_raise_caps",
    "deployment_does_not_submit_broker_order",
    "restart_does_not_restore_live_authority",
)


def build_deployment_qualification_spec(
    *,
    release_ref: str,
    environment_kind: str,
) -> DeploymentQualificationSpecV1:
    spec = DeploymentQualificationSpecV1(
        qualification_spec_id="",
        schema_version=DEPLOYMENT_SCHEMA_VERSION,
        release_ref=release_ref,
        environment_kind=environment_kind,
        required_reproducibility_checks=("same_source_same_semantic_hash", "dependency_lock_verified"),
        required_service_health_checks=("startup_order", "liveness_readiness_separation"),
        required_deployment_canary=True,
        required_rollback_drill=True,
        required_migration_tests=True,
        required_config_drift_tests=True,
        required_secret_scan=True,
        required_zero_autonomy_invariants=ZERO_AUTONOMY_INVARIANTS,
        implementation_version=DEPLOYMENT_IMPLEMENTATION_VERSION,
    )
    return DeploymentQualificationSpecV1(
        qualification_spec_id=derive_qualification_spec_id(spec),
        schema_version=spec.schema_version,
        release_ref=spec.release_ref,
        environment_kind=spec.environment_kind,
        required_reproducibility_checks=spec.required_reproducibility_checks,
        required_service_health_checks=spec.required_service_health_checks,
        required_deployment_canary=spec.required_deployment_canary,
        required_rollback_drill=spec.required_rollback_drill,
        required_migration_tests=spec.required_migration_tests,
        required_config_drift_tests=spec.required_config_drift_tests,
        required_secret_scan=spec.required_secret_scan,
        required_zero_autonomy_invariants=spec.required_zero_autonomy_invariants,
        implementation_version=spec.implementation_version,
    )


def build_deployment_qualification_report(
    *,
    spec: DeploymentQualificationSpecV1,
    release_reproducibility: str,
    environment_validation: str,
    deployment_result: str,
    service_supervision: str,
    deployment_canary: str,
    migration: str,
    rollback: str,
    config_drift: str,
    operator_visibility: str,
    security: str,
    real_broker_submits: int = 0,
) -> DeploymentQualificationReportV1:
    blocking: list[str] = []
    if release_reproducibility != "PASS":
        blocking.append("RELEASE_NOT_REPRODUCIBLE")
    if environment_validation != "PASS":
        blocking.append("ENVIRONMENT_INVALID")
    if deployment_result != "PASS":
        blocking.append("DEPLOYMENT_FAILED")
    if service_supervision != "PASS":
        blocking.append("SERVICE_SUPERVISION_INVALID")
    if real_broker_submits > 0:
        blocking.append("LIVE_ORDER_DURING_QUALIFICATION")

    if blocking:
        disposition = DeploymentDisposition.DEPLOYMENT_BLOCKED.value
        for cls in (
            DeploymentDisposition.RELEASE_NOT_REPRODUCIBLE,
            DeploymentDisposition.ENVIRONMENT_INVALID,
            DeploymentDisposition.SERVICE_SUPERVISION_INVALID,
        ):
            if cls.value.replace("_", " ").upper().split()[0] in str(blocking):
                disposition = cls.value
    else:
        disposition = DeploymentDisposition.DEPLOYMENT_QUALIFIED_WITH_LIMITATIONS.value
        if all(
            r == "PASS"
            for r in (
                release_reproducibility,
                environment_validation,
                deployment_result,
                service_supervision,
                deployment_canary,
                migration,
                rollback,
                config_drift,
                operator_visibility,
                security,
            )
        ):
            disposition = DeploymentDisposition.DEPLOYMENT_QUALIFIED.value

    report = DeploymentQualificationReportV1(
        qualification_report_id="",
        schema_version=DEPLOYMENT_SCHEMA_VERSION,
        qualification_spec_ref=spec.qualification_spec_id,
        release_reproducibility=release_reproducibility,
        environment_validation=environment_validation,
        deployment_result=deployment_result,
        service_supervision=service_supervision,
        deployment_canary=deployment_canary,
        migration=migration,
        rollback=rollback,
        config_drift=config_drift,
        operator_visibility=operator_visibility,
        security=security,
        disposition=disposition,
        limitations=BUILD34_KNOWN_LIMITATIONS,
        real_broker_submits=real_broker_submits,
        implementation_version=DEPLOYMENT_IMPLEMENTATION_VERSION,
    )
    return DeploymentQualificationReportV1(
        qualification_report_id=derive_qualification_report_id(report),
        schema_version=report.schema_version,
        qualification_spec_ref=report.qualification_spec_ref,
        release_reproducibility=report.release_reproducibility,
        environment_validation=report.environment_validation,
        deployment_result=report.deployment_result,
        service_supervision=report.service_supervision,
        deployment_canary=report.deployment_canary,
        migration=report.migration,
        rollback=report.rollback,
        config_drift=report.config_drift,
        operator_visibility=report.operator_visibility,
        security=report.security,
        disposition=report.disposition,
        limitations=report.limitations,
        real_broker_submits=report.real_broker_submits,
        implementation_version=report.implementation_version,
        metadata=report.metadata,
    )
