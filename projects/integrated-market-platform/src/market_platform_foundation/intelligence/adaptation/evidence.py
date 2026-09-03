"""BUILD 23 evidence normalization for adaptation (BUILD 24)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..contracts.common import ContractReference
from ..governance.types import (
    DriftAssessmentV1,
    DriftSeverity,
    DriftType,
    ExecutionHealthSnapshotV1,
    FailSafeDecisionV1,
    GovernanceAlertV1,
    IntelligenceHealthSnapshotV1,
    MonitoringWindowV1,
    ProviderHealthSnapshotV1,
    RollbackDecisionKind,
    RollbackDecisionV1,
)
from ..promotion.types import ChampionScopeV1
from .types import AdaptationEvidenceClass, AdaptationEvidenceType, SuggestedResearchClass

_STRUCTURAL_DRIFT_TYPES = frozenset(
    {
        DriftType.SCHEMA_DRIFT,
    }
)

_DRIFT_TO_RESEARCH_CLASS: dict[DriftType, SuggestedResearchClass] = {
    DriftType.SCHEMA_DRIFT: SuggestedResearchClass.FEATURES,
    DriftType.FEATURE_DISTRIBUTION_DRIFT: SuggestedResearchClass.FEATURES,
    DriftType.MISSINGNESS_DRIFT: SuggestedResearchClass.FEATURES,
    DriftType.FORECAST_DISTRIBUTION_DRIFT: SuggestedResearchClass.MODEL,
    DriftType.PERFORMANCE_DRIFT: SuggestedResearchClass.MODEL,
    DriftType.CALIBRATION_DRIFT: SuggestedResearchClass.CALIBRATION,
    DriftType.OOD_RATE_DRIFT: SuggestedResearchClass.QUALITY_POLICY,
    DriftType.PROVIDER_HEALTH_DRIFT: SuggestedResearchClass.DATA_SOURCE,
    DriftType.QUALITY_DRIFT: SuggestedResearchClass.QUALITY_POLICY,
    DriftType.EXECUTION_ANOMALY: SuggestedResearchClass.EXECUTION_POLICY,
}


def severity_rank(severity: DriftSeverity) -> int:
    return {
        DriftSeverity.NONE: 0,
        DriftSeverity.INFO: 1,
        DriftSeverity.WARNING: 2,
        DriftSeverity.CRITICAL: 3,
        DriftSeverity.UNKNOWN: -1,
    }[severity]


def max_severity(*values: DriftSeverity) -> DriftSeverity:
    best = DriftSeverity.NONE
    for value in values:
        if severity_rank(value) > severity_rank(best):
            best = value
    return best


def primary_drift_type(drift_types: tuple[DriftType, ...]) -> DriftType | None:
    if not drift_types:
        return None
    return sorted(drift_types, key=lambda item: item.value)[0]


def classify_evidence_class(
    *,
    drift_types: tuple[DriftType, ...],
    evidence_type: AdaptationEvidenceType,
) -> AdaptationEvidenceClass:
    if evidence_type == AdaptationEvidenceType.ROLLBACK_DECISION:
        return AdaptationEvidenceClass.STRUCTURAL_INTEGRITY_EVIDENCE
    if any(drift in _STRUCTURAL_DRIFT_TYPES for drift in drift_types):
        return AdaptationEvidenceClass.STRUCTURAL_INTEGRITY_EVIDENCE
    return AdaptationEvidenceClass.STATISTICAL_EVIDENCE


def suggest_research_class(
    *,
    drift_types: tuple[DriftType, ...],
    evidence_type: AdaptationEvidenceType,
) -> SuggestedResearchClass:
    primary = primary_drift_type(drift_types)
    if primary is not None and primary in _DRIFT_TO_RESEARCH_CLASS:
        return _DRIFT_TO_RESEARCH_CLASS[primary]
    if evidence_type == AdaptationEvidenceType.PROVIDER_HEALTH:
        return SuggestedResearchClass.DATA_SOURCE
    if evidence_type == AdaptationEvidenceType.EXECUTION_HEALTH:
        return SuggestedResearchClass.EXECUTION_POLICY
    if evidence_type == AdaptationEvidenceType.ROLLBACK_DECISION:
        return SuggestedResearchClass.MODEL
    return SuggestedResearchClass.MODEL


@dataclass(frozen=True, slots=True)
class NormalizedEvidence:
    evidence_type: AdaptationEvidenceType
    evidence_ref: ContractReference
    champion_scope: ChampionScopeV1
    window: MonitoringWindowV1
    severity: DriftSeverity
    drift_types: tuple[DriftType, ...]
    sample_count: int
    metric_observations: dict[str, float]
    sample_counts: dict[str, int]
    evidence_class: AdaptationEvidenceClass
    suggested_research_class: SuggestedResearchClass
    window_key: str
    incident_key: str | None = None
    champion_assignment_ref: str | None = None
    runtime_activation_ref: str | None = None
    metadata: dict[str, Any] | None = None


def _window_key(window: MonitoringWindowV1) -> str:
    return f"{window.start_ns}:{window.end_ns}"


def normalize_drift_assessment(assessment: DriftAssessmentV1, *, scope: ChampionScopeV1) -> NormalizedEvidence:
    sample_count = sum(assessment.sample_counts.values()) if assessment.sample_counts else 0
    evidence_class = classify_evidence_class(
        drift_types=assessment.drift_types,
        evidence_type=AdaptationEvidenceType.DRIFT_ASSESSMENT,
    )
    return NormalizedEvidence(
        evidence_type=AdaptationEvidenceType.DRIFT_ASSESSMENT,
        evidence_ref=ContractReference(
            kind="drift_assessment",
            id=assessment.drift_assessment_id,
        ),
        champion_scope=scope,
        window=assessment.window,
        severity=assessment.severity,
        drift_types=assessment.drift_types,
        sample_count=sample_count,
        metric_observations=dict(assessment.metric_observations),
        sample_counts=dict(assessment.sample_counts),
        evidence_class=evidence_class,
        suggested_research_class=suggest_research_class(
            drift_types=assessment.drift_types,
            evidence_type=AdaptationEvidenceType.DRIFT_ASSESSMENT,
        ),
        window_key=_window_key(assessment.window),
        incident_key=assessment.reference_id,
    )


def normalize_governance_alert(alert: GovernanceAlertV1) -> NormalizedEvidence:
    drift_types: tuple[DriftType, ...] = ()
    if alert.alert_type in DriftType.__members__:
        drift_types = (DriftType(alert.alert_type),)
    return NormalizedEvidence(
        evidence_type=AdaptationEvidenceType.GOVERNANCE_ALERT,
        evidence_ref=ContractReference(kind="governance_alert", id=alert.alert_id),
        champion_scope=alert.champion_scope,
        window=MonitoringWindowV1(
            start_ns=alert.observed_at_ns,
            end_ns=alert.observed_at_ns + 1,
            evaluation_as_of_ns=alert.observed_at_ns,
            scope=alert.champion_scope,
        ),
        severity=alert.severity,
        drift_types=drift_types,
        sample_count=0,
        metric_observations={},
        sample_counts={},
        evidence_class=classify_evidence_class(
            drift_types=drift_types,
            evidence_type=AdaptationEvidenceType.GOVERNANCE_ALERT,
        ),
        suggested_research_class=suggest_research_class(
            drift_types=drift_types,
            evidence_type=AdaptationEvidenceType.GOVERNANCE_ALERT,
        ),
        window_key=str(alert.observed_at_ns),
    )


def normalize_rollback_decision(decision: RollbackDecisionV1, *, scope: ChampionScopeV1) -> NormalizedEvidence | None:
    if decision.decision != RollbackDecisionKind.ROLLBACK:
        return None
    window = MonitoringWindowV1(
        start_ns=decision.effective_time_ns,
        end_ns=decision.effective_time_ns + 1,
        evaluation_as_of_ns=decision.effective_time_ns,
        scope=scope,
    )
    return NormalizedEvidence(
        evidence_type=AdaptationEvidenceType.ROLLBACK_DECISION,
        evidence_ref=ContractReference(
            kind="rollback_decision",
            id=decision.rollback_decision_id,
        ),
        champion_scope=scope,
        window=window,
        severity=DriftSeverity.CRITICAL,
        drift_types=(DriftType.PERFORMANCE_DRIFT,),
        sample_count=1,
        metric_observations={},
        sample_counts={"rollback": 1},
        evidence_class=AdaptationEvidenceClass.STRUCTURAL_INTEGRITY_EVIDENCE,
        suggested_research_class=SuggestedResearchClass.MODEL,
        window_key=_window_key(window),
        runtime_activation_ref=decision.current_activation_id,
    )


def normalize_fail_safe_decision(decision: FailSafeDecisionV1) -> NormalizedEvidence:
    window = MonitoringWindowV1(
        start_ns=decision.decision_time_ns,
        end_ns=decision.decision_time_ns + 1,
        evaluation_as_of_ns=decision.decision_time_ns,
        scope=decision.champion_scope,
    )
    return NormalizedEvidence(
        evidence_type=AdaptationEvidenceType.FAIL_SAFE_DECISION,
        evidence_ref=ContractReference(kind="fail_safe_decision", id=decision.decision_id),
        champion_scope=decision.champion_scope,
        window=window,
        severity=DriftSeverity.CRITICAL,
        drift_types=(),
        sample_count=1,
        metric_observations={},
        sample_counts={"fail_safe": 1},
        evidence_class=AdaptationEvidenceClass.STATISTICAL_EVIDENCE,
        suggested_research_class=SuggestedResearchClass.QUALITY_POLICY,
        window_key=_window_key(window),
    )


def normalize_provider_health(snapshot: ProviderHealthSnapshotV1, *, scope: ChampionScopeV1) -> NormalizedEvidence | None:
    if snapshot.health_state.value in {"HEALTHY", "UNKNOWN"}:
        return None
    severity = DriftSeverity.WARNING
    if snapshot.health_state.value == "UNHEALTHY":
        severity = DriftSeverity.CRITICAL
    drift_types = (DriftType.PROVIDER_HEALTH_DRIFT,)
    return NormalizedEvidence(
        evidence_type=AdaptationEvidenceType.PROVIDER_HEALTH,
        evidence_ref=ContractReference(kind="provider_health_snapshot", id=snapshot.snapshot_id),
        champion_scope=scope,
        window=snapshot.window,
        severity=severity,
        drift_types=drift_types,
        sample_count=snapshot.event_count,
        metric_observations={"disconnect_count": float(snapshot.disconnect_count)},
        sample_counts={"events": snapshot.event_count},
        evidence_class=AdaptationEvidenceClass.STATISTICAL_EVIDENCE,
        suggested_research_class=SuggestedResearchClass.DATA_SOURCE,
        window_key=_window_key(snapshot.window),
        incident_key=snapshot.provider,
    )


def normalize_intelligence_health(snapshot: IntelligenceHealthSnapshotV1) -> NormalizedEvidence | None:
    if snapshot.health_state.value in {"HEALTHY", "UNKNOWN"}:
        return None
    drift_types: list[DriftType] = []
    if snapshot.ece is not None:
        drift_types.append(DriftType.CALIBRATION_DRIFT)
    if snapshot.brier_score is not None:
        drift_types.append(DriftType.PERFORMANCE_DRIFT)
    if snapshot.ood_fraction is not None:
        drift_types.append(DriftType.OOD_RATE_DRIFT)
    severity = DriftSeverity.WARNING if snapshot.health_state.value == "DEGRADED" else DriftSeverity.CRITICAL
    return NormalizedEvidence(
        evidence_type=AdaptationEvidenceType.INTELLIGENCE_HEALTH,
        evidence_ref=ContractReference(kind="intelligence_health_snapshot", id=snapshot.snapshot_id),
        champion_scope=snapshot.champion_scope,
        window=snapshot.window,
        severity=severity,
        drift_types=tuple(dict.fromkeys(drift_types)),
        sample_count=snapshot.forecast_count,
        metric_observations={
            key: value
            for key, value in {
                "brier_score": snapshot.brier_score,
                "ece": snapshot.ece,
                "ood_fraction": snapshot.ood_fraction,
            }.items()
            if value is not None
        },
        sample_counts={"forecasts": snapshot.forecast_count},
        evidence_class=AdaptationEvidenceClass.STATISTICAL_EVIDENCE,
        suggested_research_class=suggest_research_class(
            drift_types=tuple(drift_types),
            evidence_type=AdaptationEvidenceType.INTELLIGENCE_HEALTH,
        ),
        window_key=_window_key(snapshot.window),
    )


def normalize_execution_health(snapshot: ExecutionHealthSnapshotV1, *, scope: ChampionScopeV1) -> NormalizedEvidence | None:
    if snapshot.health_state.value in {"HEALTHY", "UNKNOWN"}:
        return None
    severity = DriftSeverity.WARNING if snapshot.health_state.value == "DEGRADED" else DriftSeverity.CRITICAL
    return NormalizedEvidence(
        evidence_type=AdaptationEvidenceType.EXECUTION_HEALTH,
        evidence_ref=ContractReference(kind="execution_health_snapshot", id=snapshot.snapshot_id),
        champion_scope=scope,
        window=snapshot.window,
        severity=severity,
        drift_types=(DriftType.EXECUTION_ANOMALY,),
        sample_count=snapshot.proposal_count,
        metric_observations={
            "risk_rejection_count": float(snapshot.risk_rejection_count),
            "risk_fail_closed_count": float(snapshot.risk_fail_closed_count),
        },
        sample_counts={"proposals": snapshot.proposal_count},
        evidence_class=AdaptationEvidenceClass.STATISTICAL_EVIDENCE,
        suggested_research_class=SuggestedResearchClass.EXECUTION_POLICY,
        window_key=_window_key(snapshot.window),
    )


__all__ = [
    "NormalizedEvidence",
    "classify_evidence_class",
    "max_severity",
    "normalize_drift_assessment",
    "normalize_execution_health",
    "normalize_fail_safe_decision",
    "normalize_governance_alert",
    "normalize_intelligence_health",
    "normalize_provider_health",
    "normalize_rollback_decision",
    "primary_drift_type",
    "severity_rank",
    "suggest_research_class",
]
