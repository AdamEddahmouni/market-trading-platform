"""Alert policy, generation, and deduplication (BUILD 32)."""

from __future__ import annotations

from .identity import derive_alert_id, derive_alert_policy_id
from .types import (
    OPERATIONAL_RELIABILITY_IMPLEMENTATION_VERSION,
    OPERATIONAL_RELIABILITY_SCHEMA_VERSION,
    AlertPolicyV1,
    AlertSeverity,
    AlertState,
    AlertV1,
    OperationalSLOAssessmentV1,
    SLOObjectiveStatus,
)

DEFAULT_DEDUP_WINDOW_NS = 300_000_000_000
DEFAULT_COOLDOWN_NS = 60_000_000_000


def build_default_alert_policy() -> AlertPolicyV1:
    policy = AlertPolicyV1(
        alert_policy_id="",
        schema_version=OPERATIONAL_RELIABILITY_SCHEMA_VERSION,
        source_assessment_types=("OperationalSLOAssessmentV1", "ComponentHeartbeatV1"),
        severity_mappings={
            SLOObjectiveStatus.CRITICAL.value: AlertSeverity.CRITICAL.value,
            SLOObjectiveStatus.WARNING.value: AlertSeverity.WARNING.value,
            "OBSERVABILITY_DEGRADED": AlertSeverity.CRITICAL.value,
            "PERSISTENCE_UNHEALTHY": AlertSeverity.CRITICAL.value,
            "ALERT_DELIVERY_FAILED": AlertSeverity.CRITICAL.value,
        },
        dedup_window_ns=DEFAULT_DEDUP_WINDOW_NS,
        cooldown_ns=DEFAULT_COOLDOWN_NS,
        delivery_channels=("console",),
        critical_requires_delivery=True,
        implementation_version=OPERATIONAL_RELIABILITY_IMPLEMENTATION_VERSION,
    )
    policy_id = derive_alert_policy_id(policy)
    return AlertPolicyV1(
        alert_policy_id=policy_id,
        schema_version=policy.schema_version,
        source_assessment_types=policy.source_assessment_types,
        severity_mappings=policy.severity_mappings,
        dedup_window_ns=policy.dedup_window_ns,
        cooldown_ns=policy.cooldown_ns,
        delivery_channels=policy.delivery_channels,
        critical_requires_delivery=policy.critical_requires_delivery,
        implementation_version=policy.implementation_version,
    )


def build_dedup_key(*, alert_type: str, scope: str, severity: str) -> str:
    return f"{alert_type}:{scope}:{severity}"


def raise_alert(
    *,
    alert_type: str,
    severity: str,
    scope: str,
    raised_at_ns: int,
    summary: str,
    reason_codes: tuple[str, ...] = (),
    source_refs: tuple[str, ...] = (),
) -> AlertV1:
    dedup_key = build_dedup_key(alert_type=alert_type, scope=scope, severity=severity)
    alert = AlertV1(
        alert_id="",
        schema_version=OPERATIONAL_RELIABILITY_SCHEMA_VERSION,
        alert_type=alert_type,
        severity=severity,
        state=AlertState.OPEN.value,
        scope=scope,
        raised_at_ns=raised_at_ns,
        dedup_key=dedup_key,
        summary=summary,
        reason_codes=reason_codes,
        source_refs=source_refs,
    )
    return AlertV1(
        alert_id=derive_alert_id(alert),
        schema_version=alert.schema_version,
        alert_type=alert.alert_type,
        severity=alert.severity,
        state=alert.state,
        scope=alert.scope,
        raised_at_ns=alert.raised_at_ns,
        dedup_key=alert.dedup_key,
        summary=alert.summary,
        reason_codes=alert.reason_codes,
        source_refs=alert.source_refs,
        lineage=alert.lineage,
        metadata=alert.metadata,
    )


def should_dedup_alert(
    existing: AlertV1,
    candidate: AlertV1,
    *,
    as_of_ns: int,
    dedup_window_ns: int,
) -> bool:
    """Dedup repeated same unresolved condition within window."""
    if existing.dedup_key != candidate.dedup_key:
        return False
    if existing.state == AlertState.RESOLVED.value:
        return False
    if candidate.severity == AlertSeverity.CRITICAL.value and existing.severity != AlertSeverity.CRITICAL.value:
        return False  # severity escalation is not deduped away
    age = as_of_ns - existing.raised_at_ns
    return age < dedup_window_ns


def acknowledge_alert(alert: AlertV1, *, acknowledged_at_ns: int) -> AlertV1:
    """Acknowledgement does not resolve incident or change health truth."""
    return AlertV1(
        alert_id=alert.alert_id,
        schema_version=alert.schema_version,
        alert_type=alert.alert_type,
        severity=alert.severity,
        state=AlertState.ACKNOWLEDGED.value,
        scope=alert.scope,
        raised_at_ns=alert.raised_at_ns,
        dedup_key=alert.dedup_key,
        summary=alert.summary,
        reason_codes=alert.reason_codes,
        source_refs=alert.source_refs,
        acknowledged_at_ns=acknowledged_at_ns,
        resolved_at_ns=alert.resolved_at_ns,
        lineage=alert.lineage,
        metadata=alert.metadata,
    )


def alerts_from_slo_assessment(
    assessment: OperationalSLOAssessmentV1,
    policy: AlertPolicyV1,
) -> tuple[AlertV1, ...]:
    alerts: list[AlertV1] = []
    for result in assessment.objective_results:
        if result.status in {SLOObjectiveStatus.CRITICAL.value, SLOObjectiveStatus.WARNING.value}:
            severity = policy.severity_mappings.get(result.status, AlertSeverity.WARNING.value)
            alerts.append(
                raise_alert(
                    alert_type="SLO_BREACH",
                    severity=severity,
                    scope=assessment.scope,
                    raised_at_ns=assessment.as_of_ns,
                    summary=f"SLO objective {result.objective_id} status {result.status}",
                    reason_codes=(f"objective:{result.objective_id}", result.status),
                    source_refs=(assessment.assessment_id,),
                )
            )
    return tuple(alerts)
