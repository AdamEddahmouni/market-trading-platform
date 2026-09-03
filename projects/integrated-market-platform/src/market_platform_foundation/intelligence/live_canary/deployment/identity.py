"""Deterministic deployment identities (BUILD 34)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .types import (
    ConfigurationDriftAssessmentV1,
    DeploymentCanaryReportV1,
    DeploymentCanarySpecV1,
    DeploymentChangeRequestV1,
    DeploymentConfigurationV1,
    DeploymentPlanV1,
    DeploymentQualificationReportV1,
    DeploymentQualificationSpecV1,
    DeploymentRecordV1,
    DeploymentRollbackDecisionV1,
    DeploymentRollbackPlanV1,
    EnvironmentManifestV1,
    MigrationPlanV1,
    PromotionRecordV1,
    ReleaseManifestV1,
    ServiceDefinitionV1,
    ServiceGraphV1,
)


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_prefix(prefix: str, payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest}"


def derive_release_id(manifest: ReleaseManifestV1) -> str:
    payload = {
        "source_commit_sha": manifest.source_commit_sha,
        "source_tree_hash": manifest.source_tree_hash,
        "dependency_lock_hash": manifest.dependency_lock_hash,
        "artifact_hashes": dict(sorted(manifest.artifact_hashes.items())),
        "application_version": manifest.application_version,
        "implementation_version": manifest.implementation_version,
    }
    return _sha256_prefix("REL", payload)


def derive_configuration_id(config: DeploymentConfigurationV1) -> str:
    payload = {
        "execution_mode": config.execution_mode,
        "execution_authority": config.execution_authority,
        "policy_references": dict(sorted(config.policy_references.items())),
        "secret_references": dict(sorted(config.secret_references.items())),
        "implementation_version": config.implementation_version,
    }
    return _sha256_prefix("DCFG", payload)


def derive_environment_manifest_id(env: EnvironmentManifestV1) -> str:
    payload = {
        "environment_kind": env.environment_kind,
        "release_manifest_ref": env.release_manifest_ref,
        "configuration_hash": env.configuration_hash,
        "broker_environment": env.broker_environment,
        "execution_authority": env.execution_authority,
        "implementation_version": env.implementation_version,
    }
    return _sha256_prefix("ENV", payload)


def derive_promotion_record_id(record: PromotionRecordV1) -> str:
    payload = {
        "release_manifest_ref": record.release_manifest_ref,
        "from_environment": record.from_environment,
        "to_environment": record.to_environment,
        "artifact_hash": record.artifact_hash,
        "promotion_time_ns": record.promotion_time_ns,
    }
    return _sha256_prefix("PROMO", payload)


def derive_deployment_record_id(record: DeploymentRecordV1) -> str:
    payload = {
        "environment_ref": record.environment_ref,
        "release_ref": record.release_ref,
        "deployment_started_ns": record.deployment_started_ns,
        "configuration_hash_observed": record.configuration_hash_observed,
    }
    return _sha256_prefix("DEPLOY", payload)


def derive_drift_assessment_id(assessment: ConfigurationDriftAssessmentV1) -> str:
    payload = {
        "expected_release": assessment.expected_release,
        "expected_config_hash": assessment.expected_config_hash,
        "observed_release": assessment.observed_release,
        "observed_config": assessment.observed_config,
        "drift_classification": assessment.drift_classification,
    }
    return _sha256_prefix("DRIFT", payload)


def derive_service_definition_id(defn: ServiceDefinitionV1) -> str:
    payload = {
        "service_id": defn.service_id,
        "command": defn.command,
        "dependencies": list(defn.dependencies),
        "criticality": defn.criticality,
        "implementation_version": defn.implementation_version,
    }
    return _sha256_prefix("SVC", payload)


def derive_deployment_plan_id(plan: DeploymentPlanV1) -> str:
    payload = {
        "target_environment": plan.target_environment,
        "release_ref": plan.release_ref,
        "config_ref": plan.config_ref,
        "backup_prerequisite": plan.backup_prerequisite,
        "implementation_version": plan.implementation_version,
    }
    return _sha256_prefix("DPLAN", payload)


def derive_canary_spec_id(spec: DeploymentCanarySpecV1) -> str:
    payload = {
        "deployment_plan_ref": spec.deployment_plan_ref,
        "zero_live_order_requirement": spec.zero_live_order_requirement,
        "minimum_observation_duration_ns": spec.minimum_observation_duration_ns,
        "implementation_version": spec.implementation_version,
    }
    return _sha256_prefix("DCANSP", payload)


def derive_canary_report_id(report: DeploymentCanaryReportV1) -> str:
    payload = {
        "canary_spec_ref": report.canary_spec_ref,
        "real_broker_submits": report.real_broker_submits,
        "disposition": report.disposition,
    }
    return _sha256_prefix("DCANRP", payload)


def derive_migration_plan_id(plan: MigrationPlanV1) -> str:
    payload = {
        "from_schema": plan.from_schema,
        "to_schema": plan.to_schema,
        "rollback_supported": plan.rollback_supported,
        "backup_prerequisite": plan.backup_prerequisite,
    }
    return _sha256_prefix("MIG", payload)


def derive_change_request_id(request: DeploymentChangeRequestV1) -> str:
    payload = {
        "change_type": request.change_type,
        "release_ref": request.release_ref,
        "target_environment": request.target_environment,
        "rollback_target": request.rollback_target,
        "approval_state": request.approval_state,
    }
    return _sha256_prefix("CHGREQ", payload)


def derive_rollback_plan_id(plan: DeploymentRollbackPlanV1) -> str:
    payload = {
        "deployment_ref": plan.deployment_ref,
        "rollback_target_release": plan.rollback_target_release,
        "rollback_target_deployment": plan.rollback_target_deployment,
    }
    return _sha256_prefix("RBPLAN", payload)


def derive_rollback_decision_id(decision: DeploymentRollbackDecisionV1) -> str:
    payload = {
        "deployment_ref": decision.deployment_ref,
        "decision": decision.decision,
        "rollback_plan_ref": decision.rollback_plan_ref,
    }
    return _sha256_prefix("RBDEC", payload)


def derive_qualification_spec_id(spec: DeploymentQualificationSpecV1) -> str:
    payload = {
        "release_ref": spec.release_ref,
        "environment_kind": spec.environment_kind,
        "required_deployment_canary": spec.required_deployment_canary,
        "implementation_version": spec.implementation_version,
    }
    return _sha256_prefix("DEPQSP", payload)


def derive_qualification_report_id(report: DeploymentQualificationReportV1) -> str:
    payload = {
        "qualification_spec_ref": report.qualification_spec_ref,
        "disposition": report.disposition,
        "real_broker_submits": report.real_broker_submits,
    }
    return _sha256_prefix("DEPQRP", payload)


def derive_service_graph_id(graph: ServiceGraphV1) -> str:
    payload = {
        "service_ids": sorted(s.service_id for s in graph.services),
        "startup_order": list(graph.startup_order),
        "implementation_version": graph.implementation_version,
    }
    return _sha256_prefix("SVCG", payload)


def hash_configuration(config: DeploymentConfigurationV1) -> str:
    payload = {
        "runtime_infrastructure": config.runtime_infrastructure,
        "provider_connectivity": config.provider_connectivity,
        "persistence_endpoints": config.persistence_endpoints,
        "operator_server_config": config.operator_server_config,
        "telemetry_config": config.telemetry_config,
        "feature_flags": dict(sorted(config.feature_flags.items())),
        "execution_mode": config.execution_mode,
        "execution_authority": config.execution_authority,
        "policy_references": dict(sorted(config.policy_references.items())),
        "secret_references": dict(sorted(config.secret_references.items())),
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
