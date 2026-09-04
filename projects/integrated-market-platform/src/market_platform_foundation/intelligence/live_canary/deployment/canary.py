"""Deployment canary (BUILD 34)."""

from __future__ import annotations

from .identity import derive_canary_report_id, derive_canary_spec_id
from .types import (
    DEPLOYMENT_IMPLEMENTATION_VERSION,
    DEPLOYMENT_SCHEMA_VERSION,
    DeploymentCanaryReportV1,
    DeploymentCanarySpecV1,
)

DEFAULT_CANARY_DURATION_NS = 5 * 60 * 1_000_000_000


def build_deployment_canary_spec(*, deployment_plan_ref: str) -> DeploymentCanarySpecV1:
    spec = DeploymentCanarySpecV1(
        deployment_canary_spec_id="",
        schema_version=DEPLOYMENT_SCHEMA_VERSION,
        deployment_plan_ref=deployment_plan_ref,
        minimum_observation_duration_ns=DEFAULT_CANARY_DURATION_NS,
        required_services=(
            "operator-api",
            "market-data-runtime",
            "intelligence-runtime",
            "reconciliation-worker",
        ),
        required_health_states=("LIVENESS_HEALTHY", "READINESS_NOT_READY"),
        provider_observation_requirements=("readonly_quotes", "readonly_trades"),
        broker_readonly_requirements=("account_state_read", "positions_read"),
        reconciliation_requirements=("reconciliation_clean",),
        slo_requirements=("no_critical_slo_breach",),
        zero_live_order_requirement=True,
        success_criteria=(
            "all_services_healthy",
            "provider_observations_ok",
            "broker_readonly_ok",
            "reconciliation_ok",
            "zero_live_orders",
        ),
        failure_criteria=(
            "service_crash",
            "artifact_mismatch",
            "reconciliation_failure",
            "live_order_submitted",
        ),
        implementation_version=DEPLOYMENT_IMPLEMENTATION_VERSION,
    )
    return DeploymentCanarySpecV1(
        deployment_canary_spec_id=derive_canary_spec_id(spec),
        schema_version=spec.schema_version,
        deployment_plan_ref=spec.deployment_plan_ref,
        minimum_observation_duration_ns=spec.minimum_observation_duration_ns,
        required_services=spec.required_services,
        required_health_states=spec.required_health_states,
        provider_observation_requirements=spec.provider_observation_requirements,
        broker_readonly_requirements=spec.broker_readonly_requirements,
        reconciliation_requirements=spec.reconciliation_requirements,
        slo_requirements=spec.slo_requirements,
        zero_live_order_requirement=spec.zero_live_order_requirement,
        success_criteria=spec.success_criteria,
        failure_criteria=spec.failure_criteria,
        implementation_version=spec.implementation_version,
    )


def run_deployment_canary(
    *,
    canary_spec: DeploymentCanarySpecV1,
    services_healthy: bool = True,
    provider_ok: bool = True,
    broker_readonly_ok: bool = True,
    reconciliation_ok: bool = True,
    real_broker_submits: int = 0,
    observation_duration_ns: int | None = None,
    injected_failure: str | None = None,
) -> DeploymentCanaryReportV1:
    duration = observation_duration_ns or canary_spec.minimum_observation_duration_ns
    if injected_failure:
        disposition = "CANARY_FAILED"
    elif not services_healthy or not provider_ok or not broker_readonly_ok or not reconciliation_ok:
        disposition = "CANARY_FAILED"
    elif real_broker_submits > 0 and canary_spec.zero_live_order_requirement:
        disposition = "CANARY_FAILED"
    elif duration < canary_spec.minimum_observation_duration_ns:
        disposition = "CANARY_INSUFFICIENT_DURATION"
    else:
        disposition = "CANARY_PASSED"

    report = DeploymentCanaryReportV1(
        deployment_canary_report_id="",
        schema_version=DEPLOYMENT_SCHEMA_VERSION,
        canary_spec_ref=canary_spec.deployment_canary_spec_id,
        observation_duration_ns=duration,
        services_healthy=services_healthy,
        provider_observations_ok=provider_ok,
        broker_readonly_ok=broker_readonly_ok,
        reconciliation_ok=reconciliation_ok,
        real_broker_submits=real_broker_submits,
        disposition=disposition,
        implementation_version=DEPLOYMENT_IMPLEMENTATION_VERSION,
        metadata={"injected_failure": injected_failure} if injected_failure else {},
    )
    return DeploymentCanaryReportV1(
        deployment_canary_report_id=derive_canary_report_id(report),
        schema_version=report.schema_version,
        canary_spec_ref=report.canary_spec_ref,
        observation_duration_ns=report.observation_duration_ns,
        services_healthy=report.services_healthy,
        provider_observations_ok=report.provider_observations_ok,
        broker_readonly_ok=report.broker_readonly_ok,
        reconciliation_ok=report.reconciliation_ok,
        real_broker_submits=report.real_broker_submits,
        disposition=report.disposition,
        implementation_version=report.implementation_version,
        metadata=report.metadata,
    )
