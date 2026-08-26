"""Environment manifest builders and validators (BUILD 34)."""

from __future__ import annotations

from .configuration import build_deployment_configuration, configuration_hash, validate_configuration_for_environment
from .identity import derive_environment_manifest_id
from .types import (
    DEPLOYMENT_IMPLEMENTATION_VERSION,
    DEPLOYMENT_SCHEMA_VERSION,
    BrokerEnvironment,
    EnvironmentKind,
    EnvironmentManifestV1,
    ExecutionAuthority,
    ExecutionMode,
)

ENVIRONMENT_PROFILES: dict[str, dict[str, str]] = {
    EnvironmentKind.LOCAL_DEV.value: {
        "broker_environment": BrokerEnvironment.NONE.value,
        "persistence_environment": "local-dev",
        "provider_environment": "fixture",
        "execution_mode": ExecutionMode.OFFLINE.value,
        "execution_authority": ExecutionAuthority.NONE.value,
    },
    EnvironmentKind.TEST.value: {
        "broker_environment": BrokerEnvironment.TEST.value,
        "persistence_environment": "test",
        "provider_environment": "fixture",
        "execution_mode": ExecutionMode.PAPER.value,
        "execution_authority": ExecutionAuthority.PAPER.value,
    },
    EnvironmentKind.QUALIFICATION.value: {
        "broker_environment": BrokerEnvironment.PAPER.value,
        "persistence_environment": "qualification",
        "provider_environment": "fixture",
        "execution_mode": ExecutionMode.PAPER.value,
        "execution_authority": ExecutionAuthority.OBSERVATION_ONLY.value,
    },
    EnvironmentKind.SUPERVISED_PILOT.value: {
        "broker_environment": BrokerEnvironment.SUPERVISED_LIVE.value,
        "persistence_environment": "supervised-pilot",
        "provider_environment": "live-readonly",
        "execution_mode": ExecutionMode.SUPERVISED_LIVE.value,
        "execution_authority": ExecutionAuthority.SUPERVISED_LIVE.value,
    },
    EnvironmentKind.SUPERVISED_LIVE.value: {
        "broker_environment": BrokerEnvironment.SUPERVISED_LIVE.value,
        "persistence_environment": "supervised-live",
        "provider_environment": "live-readonly",
        "execution_mode": ExecutionMode.SUPERVISED_LIVE.value,
        "execution_authority": ExecutionAuthority.SUPERVISED_LIVE.value,
    },
}


def build_environment_manifest(
    *,
    environment_kind: str,
    release_manifest_ref: str,
    build33_qualification_ref: str,
) -> EnvironmentManifestV1:
    if environment_kind not in ENVIRONMENT_PROFILES:
        raise ValueError(f"unknown environment kind: {environment_kind}")
    profile = ENVIRONMENT_PROFILES[environment_kind]
    config = build_deployment_configuration(
        environment_kind=environment_kind,
        execution_mode=profile["execution_mode"],
        execution_authority=profile["execution_authority"],
        broker_environment=profile["broker_environment"],
        persistence_target=profile["persistence_environment"],
        provider_environment=profile["provider_environment"],
    )
    cfg_hash = configuration_hash(config)
    env = EnvironmentManifestV1(
        environment_manifest_id="",
        schema_version=DEPLOYMENT_SCHEMA_VERSION,
        environment_kind=environment_kind,
        release_manifest_ref=release_manifest_ref,
        configuration_ref=config.configuration_id,
        configuration_hash=cfg_hash,
        persistence_environment=profile["persistence_environment"],
        provider_environment=profile["provider_environment"],
        broker_environment=profile["broker_environment"],
        execution_mode=profile["execution_mode"],
        execution_authority=profile["execution_authority"],
        allowed_policy_refs=(
            "PILPOL-default",
            "SLO-default",
            "ALERT-default",
            build33_qualification_ref,
        ),
        required_secrets=tuple(sorted(config.secret_references.keys())),
        service_definitions=(
            "operator-api",
            "market-data-runtime",
            "intelligence-runtime",
            "reconciliation-worker",
        ),
        health_readiness_requirements=(
            "persistence_ready",
            "canonical_state_loaded",
            "reconciliation_clean",
        ),
        implementation_version=DEPLOYMENT_IMPLEMENTATION_VERSION,
    )
    return EnvironmentManifestV1(
        environment_manifest_id=derive_environment_manifest_id(env),
        schema_version=env.schema_version,
        environment_kind=env.environment_kind,
        release_manifest_ref=env.release_manifest_ref,
        configuration_ref=env.configuration_ref,
        configuration_hash=env.configuration_hash,
        persistence_environment=env.persistence_environment,
        provider_environment=env.provider_environment,
        broker_environment=env.broker_environment,
        execution_mode=env.execution_mode,
        execution_authority=env.execution_authority,
        allowed_policy_refs=env.allowed_policy_refs,
        required_secrets=env.required_secrets,
        service_definitions=env.service_definitions,
        health_readiness_requirements=env.health_readiness_requirements,
        implementation_version=env.implementation_version,
        metadata=env.metadata,
    )


def validate_environment_manifest(env: EnvironmentManifestV1) -> tuple[bool, tuple[str, ...]]:
    violations: list[str] = []
    try:
        EnvironmentKind(env.environment_kind)
    except ValueError:
        violations.append(f"unknown environment kind: {env.environment_kind}")
        return False, tuple(violations)

    profile = ENVIRONMENT_PROFILES.get(env.environment_kind)
    if profile is None:
        violations.append(f"no profile for {env.environment_kind}")
        return False, tuple(violations)

    if env.broker_environment != profile["broker_environment"]:
        violations.append(
            f"broker environment mismatch: expected {profile['broker_environment']}, got {env.broker_environment}"
        )
    if env.execution_authority != profile["execution_authority"]:
        violations.append(
            f"execution authority mismatch: expected {profile['execution_authority']}, got {env.execution_authority}"
        )

    # Cross-environment crossover checks
    if env.environment_kind == EnvironmentKind.SUPERVISED_LIVE.value:
        if "test" in env.persistence_environment.lower():
            violations.append("supervised live cannot use test persistence")
        if env.broker_environment == BrokerEnvironment.PAPER.value:
            violations.append("supervised live cannot use paper broker")

    config = build_deployment_configuration(
        environment_kind=env.environment_kind,
        execution_mode=env.execution_mode,
        execution_authority=env.execution_authority,
        broker_environment=env.broker_environment,
        persistence_target=env.persistence_environment,
        provider_environment=env.provider_environment,
    )
    ok, config_violations = validate_configuration_for_environment(config, env.environment_kind)
    if not ok:
        violations.extend(config_violations)

    return len(violations) == 0, tuple(violations)


def unknown_environment_fails_closed(environment_kind: str) -> bool:
    try:
        EnvironmentKind(environment_kind)
        return False
    except ValueError:
        return True
