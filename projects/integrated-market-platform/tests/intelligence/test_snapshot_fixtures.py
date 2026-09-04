"""Shared snapshot engine test fixtures (BUILD 05)."""

from __future__ import annotations

from market_platform_foundation.intelligence.contracts import IntelligenceScope, QualityState
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.intelligence.quality.models import (
    DecisionAction,
    QualityAssessment,
    QualityDecision,
    RequirementSet,
)
from market_platform_foundation.intelligence.snapshots import SnapshotBuildRequest, SnapshotCompositionPolicy
from tests.intelligence.test_persistence_fixtures import (
    DECISION_NS,
    INSTRUMENT,
    QUALITY,
    SCOPE,
    sample_event,
    sample_signal,
)

T = DECISION_NS


def empty_repo_with_events(*events) -> InMemoryIntelligenceRepository:
    repo = InMemoryIntelligenceRepository()
    for event in events:
        repo.put_event(event)
    return repo


def default_request(
    *,
    decision_time_ns: int = T,
    scope: IntelligenceScope | None = None,
    policy: SnapshotCompositionPolicy | None = None,
) -> SnapshotBuildRequest:
    return SnapshotBuildRequest(
        decision_time_ns=decision_time_ns,
        scope=scope or SCOPE,
        composition_policy=policy or SnapshotCompositionPolicy(max_events=100, max_signals=10),
        capability_requirements=RequirementSet(),
    )


def use_quality_decision(decision_time_ns: int = T) -> QualityDecision:
    assessment = QualityAssessment(decision_time_ns=decision_time_ns)
    return QualityDecision(
        action=DecisionAction.USE,
        quality_state=QualityState.GOOD,
        assessment=assessment,
    )


def degrade_quality_decision(decision_time_ns: int = T) -> QualityDecision:
    assessment = QualityAssessment(decision_time_ns=decision_time_ns)
    return QualityDecision(
        action=DecisionAction.DEGRADE,
        quality_state=QualityState.DEGRADED,
        assessment=assessment,
        reasons=("degraded",),
    )


def abstain_quality_decision(decision_time_ns: int = T) -> QualityDecision:
    assessment = QualityAssessment(decision_time_ns=decision_time_ns)
    return QualityDecision(
        action=DecisionAction.ABSTAIN,
        quality_state=QualityState.DEGRADED,
        assessment=assessment,
        reasons=("abstain",),
    )


def fail_closed_quality_decision(decision_time_ns: int = T) -> QualityDecision:
    assessment = QualityAssessment(decision_time_ns=decision_time_ns)
    return QualityDecision(
        action=DecisionAction.FAIL_CLOSED,
        quality_state=QualityState.INVALID,
        assessment=assessment,
        reasons=("fail_closed",),
    )


__all__ = [
    "T",
    "INSTRUMENT",
    "QUALITY",
    "SCOPE",
    "abstain_quality_decision",
    "default_request",
    "degrade_quality_decision",
    "empty_repo_with_events",
    "fail_closed_quality_decision",
    "sample_event",
    "sample_signal",
    "use_quality_decision",
]
