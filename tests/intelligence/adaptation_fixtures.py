"""Shared fixtures for BUILD 24 adaptation tests."""

from __future__ import annotations

from market_platform_foundation.intelligence.adaptation import (
    AdaptationContext,
    EvidenceBundle,
    build_adaptation_policy,
)
from market_platform_foundation.intelligence.contracts.common import INTELLIGENCE_SCHEMA_VERSION
from market_platform_foundation.intelligence.governance import (
    DriftSeverity,
    DriftType,
    GovernanceAction,
)
from market_platform_foundation.intelligence.governance import derive_drift_assessment_id
from market_platform_foundation.intelligence.governance.types import DriftAssessmentV1
from tests.intelligence.governance_fixtures import DEFAULT_SCOPE, default_drift_policy, monitoring_window
from tests.intelligence.outcome_fixtures import HORIZON_5M, T


def default_adaptation_policy(**overrides):
    kwargs = {
        "champion_scope": DEFAULT_SCOPE,
        "minimum_sample": 4,
        "minimum_recurrence_count": 2,
        "minimum_distinct_windows": 2,
        "cooldown_ns": HORIZON_5M,
    }
    kwargs.update(overrides)
    return build_adaptation_policy(**kwargs)


def performance_drift_assessment(
    *,
    start_ns: int,
    end_ns: int,
    sample_count: int = 20,
    severity: DriftSeverity = DriftSeverity.WARNING,
) -> DriftAssessmentV1:
    policy = default_drift_policy(minimum_sample=4)
    window = monitoring_window(start_ns=start_ns, end_ns=end_ns)
    if severity == DriftSeverity.WARNING:
        return DriftAssessmentV1(
            drift_assessment_id=derive_drift_assessment_id(
                policy_id=policy.drift_policy_id,
                window=window,
                reference_id="perf-ref",
            ),
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            policy_id=policy.drift_policy_id,
            window=window,
            reference_id="perf-ref",
            metric_observations={"brier_delta": 0.06},
            sample_counts={"performance": sample_count},
            severity=DriftSeverity.WARNING,
            drift_types=(DriftType.PERFORMANCE_DRIFT,),
            recommended_action=GovernanceAction.WARN,
        )
    return DriftAssessmentV1(
        drift_assessment_id=derive_drift_assessment_id(
            policy_id=policy.drift_policy_id,
            window=window,
            reference_id="perf-ref",
        ),
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        policy_id=policy.drift_policy_id,
        window=window,
        reference_id="perf-ref",
        metric_observations={"brier_delta": 0.15},
        sample_counts={"performance": sample_count},
        severity=severity,
        drift_types=(DriftType.PERFORMANCE_DRIFT,),
        recommended_action=GovernanceAction.WARN,
    )


def schema_drift_assessment(*, start_ns: int, end_ns: int) -> DriftAssessmentV1:
    policy = default_drift_policy(minimum_sample=1)
    window = monitoring_window(start_ns=start_ns, end_ns=end_ns)
    return DriftAssessmentV1(
        drift_assessment_id=derive_drift_assessment_id(
            policy_id=policy.drift_policy_id,
            window=window,
            reference_id="schema-ref",
        ),
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        policy_id=policy.drift_policy_id,
        window=window,
        reference_id="schema-ref",
        metric_observations={"schema_mismatch": 1.0},
        sample_counts={"feature": 1},
        severity=DriftSeverity.CRITICAL,
        drift_types=(DriftType.SCHEMA_DRIFT,),
        recommended_action=GovernanceAction.DISABLE_SCOPE,
    )


def default_context(*, reference_time_ns: int | None = None, **overrides) -> AdaptationContext:
    kwargs = {
        "reference_time_ns": reference_time_ns if reference_time_ns is not None else T + HORIZON_5M * 3,
        "batch_window": monitoring_window(start_ns=T, end_ns=T + HORIZON_5M * 4),
    }
    kwargs.update(overrides)
    return AdaptationContext(**kwargs)


def recurrence_bundle() -> EvidenceBundle:
    return EvidenceBundle(
        drift_assessments=(
            performance_drift_assessment(start_ns=T, end_ns=T + HORIZON_5M),
            performance_drift_assessment(start_ns=T + HORIZON_5M, end_ns=T + HORIZON_5M * 2),
        )
    )
