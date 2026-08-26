"""Drift assessment engine (BUILD 23)."""

from __future__ import annotations

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION
from .identity import derive_drift_assessment_id, derive_governance_alert_id
from ..promotion.identity import champion_scope_identity_payload
from .types import (
    DriftAssessmentV1,
    DriftPolicyV1,
    DriftSeverity,
    DriftType,
    FeatureReferenceDistributionV1,
    GovernanceAction,
    GovernanceAlertV1,
    GovernanceReasonCode,
    MonitoringWindowV1,
)


def _severity_rank(severity: DriftSeverity) -> int:
    return {
        DriftSeverity.NONE: 0,
        DriftSeverity.INFO: 1,
        DriftSeverity.WARNING: 2,
        DriftSeverity.CRITICAL: 3,
        DriftSeverity.UNKNOWN: -1,
    }[severity]


def _max_severity(current: DriftSeverity, candidate: DriftSeverity) -> DriftSeverity:
    return candidate if _severity_rank(candidate) > _severity_rank(current) else current


def assess_feature_drift(
    *,
    policy: DriftPolicyV1,
    window: MonitoringWindowV1,
    reference: FeatureReferenceDistributionV1,
    recent_means: dict[str, float],
    recent_missingness: dict[str, float],
    recent_schema_fingerprint: str,
    sample_count: int,
) -> DriftAssessmentV1:
    drift_types: list[DriftType] = []
    reasons: list[GovernanceReasonCode] = []
    observations: dict[str, float] = {}
    severity = DriftSeverity.NONE
    recommended = GovernanceAction.ALLOW

    if sample_count < policy.minimum_sample:
        return DriftAssessmentV1(
            drift_assessment_id=derive_drift_assessment_id(
                policy_id=policy.drift_policy_id,
                window=window,
                reference_id=reference.reference_id,
            ),
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            policy_id=policy.drift_policy_id,
            window=window,
            reference_id=reference.reference_id,
            sample_counts={"feature": sample_count},
            severity=DriftSeverity.UNKNOWN,
            reason_codes=(GovernanceReasonCode.INSUFFICIENT_SAMPLE,),
            recommended_action=GovernanceAction.ALLOW,
        )

    if recent_schema_fingerprint != reference.feature_schema_fingerprint:
        drift_types.append(DriftType.SCHEMA_DRIFT)
        reasons.append(GovernanceReasonCode.SCHEMA_DRIFT_DETECTED)
        severity = DriftSeverity.CRITICAL
        recommended = policy.schema_mismatch_action

    for feature, ref_rate in reference.feature_missingness_rates.items():
        recent_rate = recent_missingness.get(feature, 0.0)
        delta = abs(recent_rate - ref_rate)
        observations[f"missingness_delta.{feature}"] = delta
        if delta > policy.feature_missingness_threshold:
            drift_types.append(DriftType.MISSINGNESS_DRIFT)
            reasons.append(GovernanceReasonCode.FEATURE_DRIFT_DETECTED)
            severity = _max_severity(severity, DriftSeverity.WARNING)

    for feature, ref_mean in reference.feature_means.items():
        recent_mean = recent_means.get(feature)
        if recent_mean is None:
            continue
        ref_std = reference.feature_stds.get(feature, 1.0) or 1.0
        shift = abs(recent_mean - ref_mean) / ref_std
        observations[f"mean_shift_z.{feature}"] = shift
        if shift > policy.feature_mean_shift_threshold:
            drift_types.append(DriftType.FEATURE_DISTRIBUTION_DRIFT)
            reasons.append(GovernanceReasonCode.FEATURE_DRIFT_DETECTED)
            severity = _max_severity(severity, DriftSeverity.WARNING)

    if severity != DriftSeverity.NONE:
        action_name = policy.actions_by_severity.get(severity.value)
        if action_name is not None:
            recommended = GovernanceAction(action_name)

    return DriftAssessmentV1(
        drift_assessment_id=derive_drift_assessment_id(
            policy_id=policy.drift_policy_id,
            window=window,
            reference_id=reference.reference_id,
        ),
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        policy_id=policy.drift_policy_id,
        window=window,
        reference_id=reference.reference_id,
        metric_observations=observations,
        sample_counts={"feature": sample_count},
        severity=severity,
        drift_types=tuple(dict.fromkeys(drift_types)),
        reason_codes=tuple(dict.fromkeys(reasons)),
        recommended_action=recommended,
    )


def assess_performance_drift(
    *,
    policy: DriftPolicyV1,
    window: MonitoringWindowV1,
    reference_metric: float,
    recent_metric: float,
    sample_count: int,
    reference_id: str | None = None,
) -> DriftAssessmentV1:
    if sample_count < policy.minimum_sample:
        return DriftAssessmentV1(
            drift_assessment_id=derive_drift_assessment_id(
                policy_id=policy.drift_policy_id,
                window=window,
                reference_id=reference_id,
            ),
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            policy_id=policy.drift_policy_id,
            window=window,
            reference_id=reference_id,
            sample_counts={"performance": sample_count},
            severity=DriftSeverity.UNKNOWN,
            reason_codes=(GovernanceReasonCode.INSUFFICIENT_SAMPLE,),
            recommended_action=GovernanceAction.ALLOW,
        )

    delta = recent_metric - reference_metric
    severity = DriftSeverity.NONE
    reasons: list[GovernanceReasonCode] = []
    drift_types: list[DriftType] = []
    recommended = GovernanceAction.ALLOW
    if delta > policy.performance_degradation_threshold:
        severity = DriftSeverity.CRITICAL
        reasons.append(GovernanceReasonCode.PERFORMANCE_DRIFT_DETECTED)
        drift_types.append(DriftType.PERFORMANCE_DRIFT)
        action_name = policy.actions_by_severity.get(severity.value)
        if action_name is not None:
            recommended = GovernanceAction(action_name)

    return DriftAssessmentV1(
        drift_assessment_id=derive_drift_assessment_id(
            policy_id=policy.drift_policy_id,
            window=window,
            reference_id=reference_id,
        ),
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        policy_id=policy.drift_policy_id,
        window=window,
        reference_id=reference_id,
        metric_observations={
            "reference_metric": reference_metric,
            "recent_metric": recent_metric,
            "delta": delta,
        },
        sample_counts={"performance": sample_count},
        severity=severity,
        drift_types=tuple(drift_types),
        reason_codes=tuple(reasons),
        recommended_action=recommended,
    )


def assess_calibration_drift(
    *,
    policy: DriftPolicyV1,
    window: MonitoringWindowV1,
    recent_ece: float,
    sample_count: int,
    reference_id: str | None = None,
) -> DriftAssessmentV1:
    if sample_count < policy.minimum_sample:
        return DriftAssessmentV1(
            drift_assessment_id=derive_drift_assessment_id(
                policy_id=policy.drift_policy_id,
                window=window,
                reference_id=reference_id,
            ),
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            policy_id=policy.drift_policy_id,
            window=window,
            reference_id=reference_id,
            sample_counts={"calibration": sample_count},
            severity=DriftSeverity.UNKNOWN,
            reason_codes=(GovernanceReasonCode.INSUFFICIENT_SAMPLE,),
            recommended_action=GovernanceAction.ALLOW,
        )

    severity = DriftSeverity.NONE
    reasons: list[GovernanceReasonCode] = []
    drift_types: list[DriftType] = []
    recommended = GovernanceAction.ALLOW
    if recent_ece > policy.calibration_ece_threshold:
        severity = DriftSeverity.WARNING
        reasons.append(GovernanceReasonCode.CALIBRATION_DRIFT_DETECTED)
        drift_types.append(DriftType.CALIBRATION_DRIFT)
        action_name = policy.actions_by_severity.get(severity.value)
        if action_name is not None:
            recommended = GovernanceAction(action_name)

    return DriftAssessmentV1(
        drift_assessment_id=derive_drift_assessment_id(
            policy_id=policy.drift_policy_id,
            window=window,
            reference_id=reference_id,
        ),
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        policy_id=policy.drift_policy_id,
        window=window,
        reference_id=reference_id,
        metric_observations={"recent_ece": recent_ece},
        sample_counts={"calibration": sample_count},
        severity=severity,
        drift_types=tuple(drift_types),
        reason_codes=tuple(reasons),
        recommended_action=recommended,
    )


def create_alert_from_drift(
    *,
    assessment: DriftAssessmentV1,
    policy: DriftPolicyV1,
    observed_at_ns: int,
) -> GovernanceAlertV1 | None:
    if assessment.severity in {DriftSeverity.NONE, DriftSeverity.UNKNOWN}:
        return None
    from ..contracts.common import ContractReference, ContractKind

    return GovernanceAlertV1(
        alert_id=derive_governance_alert_id(
            champion_scope=champion_scope_identity_payload(policy.champion_scope),
            alert_type="DRIFT",
            observed_at_ns=observed_at_ns,
            severity=assessment.severity.value,
            source_key=assessment.drift_assessment_id,
        ),
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        champion_scope=policy.champion_scope,
        severity=assessment.severity,
        alert_type="DRIFT",
        source_refs=(
            ContractReference(
                kind=ContractKind.RUN_MANIFEST.value,
                id=assessment.drift_assessment_id,
            ),
        ),
        observed_at_ns=observed_at_ns,
        recommended_action=assessment.recommended_action,
        reason_codes=assessment.reason_codes,
    )
