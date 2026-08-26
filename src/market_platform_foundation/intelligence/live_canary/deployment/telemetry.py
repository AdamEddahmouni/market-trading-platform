"""Deployment telemetry snapshot (BUILD 34)."""

from __future__ import annotations

from typing import Any

from .drift import assess_configuration_drift
from .types import RuntimeVersionReportV1


def build_runtime_version_report(
    *,
    service_id: str,
    expected_release: str,
    expected_config_hash: str,
    observed_release: str,
    observed_config_hash: str,
    commit_sha: str,
    service_version: str = "build34-v1",
) -> RuntimeVersionReportV1:
    matches = expected_release == observed_release and expected_config_hash == observed_config_hash
    return RuntimeVersionReportV1(
        service_id=service_id,
        release_id=observed_release,
        commit_sha=commit_sha,
        config_hash=observed_config_hash,
        service_version=service_version,
        matches_expected=matches,
    )


def build_deployment_snapshot(
    *,
    release_id: str,
    commit_sha: str,
    environment_kind: str,
    config_hash: str,
    deployment_state: str,
    service_health: dict[str, str],
    canary_state: str,
    rollback_target: str | None,
    pending_change_request: str | None,
    migration_state: str,
    expected_release: str,
    expected_config_hash: str,
) -> dict[str, Any]:
    drift = assess_configuration_drift(
        expected_release=expected_release,
        expected_config_hash=expected_config_hash,
        observed_release=release_id,
        observed_config_hash=config_hash,
    )
    return {
        "authority_boundary": "DEPLOYMENT_READ_ONLY",
        "release_id": release_id,
        "commit_sha": commit_sha,
        "environment_kind": environment_kind,
        "config_hash": config_hash,
        "deployment_state": deployment_state,
        "service_health": service_health,
        "canary_state": canary_state,
        "rollback_target": rollback_target,
        "pending_change_request": pending_change_request,
        "migration_state": migration_state,
        "drift_assessment": {
            "drift_classification": drift.drift_classification,
            "blocking_impact": drift.blocking_impact,
        },
        "live_authorization": {
            "session_authorized": False,
            "per_order_confirmation_required": True,
            "deployment_grants_authority": False,
        },
        "disclaimer": "deployment healthy does not imply live trading enabled",
    }
