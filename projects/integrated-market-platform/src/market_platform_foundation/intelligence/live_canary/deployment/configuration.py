"""Deployment configuration schema (BUILD 34)."""

from __future__ import annotations

from .identity import derive_configuration_id, hash_configuration
from .types import (
    DEPLOYMENT_IMPLEMENTATION_VERSION,
    DEPLOYMENT_SCHEMA_VERSION,
    POLICY_OWNED_FIELD_NAMES,
    BrokerEnvironment,
    DeploymentConfigurationV1,
    EnvironmentKind,
    ExecutionAuthority,
    ExecutionMode,
)


def build_deployment_configuration(
    *,
    environment_kind: str,
    execution_mode: str,
    execution_authority: str,
    broker_environment: str,
    persistence_target: str,
    provider_environment: str,
    policy_refs: dict[str, str] | None = None,
    secret_refs: dict[str, str] | None = None,
) -> DeploymentConfigurationV1:
    policy_refs = policy_refs or {
        "pilot_policy_ref": "PILPOL-default",
        "slo_policy_ref": "SLO-default",
        "alert_policy_ref": "ALERT-default",
    }
    secret_refs = secret_refs or {
        "broker_api_key": "ENV:BROKER_API_KEY",
        "mongodb_uri": "ENV:IMP_MONGODB_URI",
    }
    config = DeploymentConfigurationV1(
        configuration_id="",
        schema_version=DEPLOYMENT_SCHEMA_VERSION,
        runtime_infrastructure={
            "python_version": "3.11.15",
            "platform": "windows-native",
        },
        provider_connectivity={
            "environment": provider_environment,
            "primary_provider": "polygon",
            "fallback_provider": "finviz",
        },
        persistence_endpoints={
            "target": persistence_target,
            "schema_version": "intelligence-v1",
        },
        operator_server_config={
            "host": "127.0.0.1",
            "port": 8765,
            "authority_boundary": "DEPLOYMENT_READ_ONLY",
        },
        telemetry_config={
            "metrics_enabled": True,
            "alert_delivery": "console",
        },
        feature_flags={
            "deployment_canary_enabled": True,
            "live_execution_enabled": False,
        },
        execution_mode=execution_mode,
        execution_authority=execution_authority,
        policy_references=policy_refs,
        secret_references=secret_refs,
        implementation_version=DEPLOYMENT_IMPLEMENTATION_VERSION,
        metadata={"environment_kind": environment_kind, "broker_environment": broker_environment},
    )
    return DeploymentConfigurationV1(
        configuration_id=derive_configuration_id(config),
        schema_version=config.schema_version,
        runtime_infrastructure=config.runtime_infrastructure,
        provider_connectivity=config.provider_connectivity,
        persistence_endpoints=config.persistence_endpoints,
        operator_server_config=config.operator_server_config,
        telemetry_config=config.telemetry_config,
        feature_flags=config.feature_flags,
        execution_mode=config.execution_mode,
        execution_authority=config.execution_authority,
        policy_references=config.policy_references,
        secret_references=config.secret_references,
        implementation_version=config.implementation_version,
        metadata=config.metadata,
    )


def validate_configuration_no_policy_override(
    config: DeploymentConfigurationV1,
    raw_env: dict[str, str] | None = None,
) -> tuple[bool, tuple[str, ...]]:
    """Ensure environment variables do not silently override canonical policy fields."""
    violations: list[str] = []
    raw_env = raw_env or {}
    for key in raw_env:
        normalized = key.lower().replace("-", "_")
        for owned in POLICY_OWNED_FIELD_NAMES:
            if owned in normalized:
                violations.append(f"env var {key} attempts to override policy-owned field {owned}")
    for key, value in config.secret_references.items():
        if not value.startswith(("ENV:", "OS:", "VAULT:")):
            violations.append(f"secret reference {key} must use symbolic prefix, got {value}")
        if any(secret_word in value.lower() for secret_word in ("password=", "api_key=", "token=")):
            violations.append(f"secret reference {key} appears to embed a secret value")
    return len(violations) == 0, tuple(violations)


def validate_configuration_for_environment(
    config: DeploymentConfigurationV1,
    environment_kind: str,
) -> tuple[bool, tuple[str, ...]]:
    violations: list[str] = []
    broker_env = config.metadata.get("broker_environment", "")
    try:
        EnvironmentKind(environment_kind)
    except ValueError:
        violations.append(f"unknown environment kind: {environment_kind}")
        return False, tuple(violations)

    if environment_kind == EnvironmentKind.SUPERVISED_LIVE.value:
        if broker_env not in (BrokerEnvironment.SUPERVISED_LIVE.value,):
            violations.append(f"supervised live requires SUPERVISED_LIVE broker, got {broker_env}")
        if config.execution_authority != ExecutionAuthority.SUPERVISED_LIVE.value:
            violations.append("supervised live environment requires SUPERVISED_LIVE authority")
    elif environment_kind == EnvironmentKind.TEST.value:
        if broker_env == BrokerEnvironment.SUPERVISED_LIVE.value:
            violations.append("TEST environment cannot use SUPERVISED_LIVE broker")
        if config.execution_mode == ExecutionMode.SUPERVISED_LIVE.value:
            violations.append("TEST environment cannot use SUPERVISED_LIVE execution mode")
    elif environment_kind == EnvironmentKind.QUALIFICATION.value:
        if broker_env == BrokerEnvironment.SUPERVISED_LIVE.value:
            violations.append("QUALIFICATION environment cannot use SUPERVISED_LIVE broker")

    if config.feature_flags.get("live_execution_enabled") and environment_kind in (
        EnvironmentKind.TEST.value,
        EnvironmentKind.QUALIFICATION.value,
        EnvironmentKind.LOCAL_DEV.value,
    ):
        violations.append("live_execution_enabled not allowed in non-live environments")

    return len(violations) == 0, tuple(violations)


def configuration_hash(config: DeploymentConfigurationV1) -> str:
    return hash_configuration(config)
