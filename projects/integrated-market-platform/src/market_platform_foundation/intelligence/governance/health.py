"""Health snapshot calculators (BUILD 23)."""

from __future__ import annotations

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION
from ..evaluation.metrics import compute_predictive_metrics
from ..evaluation.types import AggregateStatus, EvaluationCohortRow, EvaluationSpec, ProbabilityView
from ..opportunity.types import AssessmentAction
from ..quality.models import (
    ConnectionState,
    DecisionAction,
    ProviderHealthSnapshot,
    QualityFinding,
    QualityFindingCode,
)
from .identity import derive_health_snapshot_id
from .types import (
    DataQualityHealthSnapshotV1,
    ExecutionHealthSnapshotV1,
    GovernanceReasonCode,
    HealthState,
    IntelligenceHealthSnapshotV1,
    MonitoringWindowV1,
    OpportunityHealthSnapshotV1,
    ProviderHealthSnapshotV1,
)


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def assess_provider_health(
    *,
    provider: str,
    capability: str | None,
    observed_at_ns: int,
    window: MonitoringWindowV1,
    provider_health: ProviderHealthSnapshot | None = None,
    staleness_threshold_ns: int,
) -> ProviderHealthSnapshotV1:
    if provider_health is None:
        return ProviderHealthSnapshotV1(
            snapshot_id=derive_health_snapshot_id(
                kind="provider",
                window=window,
                context_key=f"{provider}:{capability or '*'}",
            ),
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            provider=provider,
            capability=capability,
            observed_at_ns=observed_at_ns,
            window=window,
            health_state=HealthState.UNKNOWN,
            reason_codes=(GovernanceReasonCode.NO_OBSERVATIONS,),
        )

    reasons: list[GovernanceReasonCode] = []
    state = HealthState.HEALTHY
    connected = provider_health.connection == ConnectionState.CONNECTED
    staleness_ns: int | None = None
    if provider_health.as_of_time_ns > 0:
        staleness_ns = max(0, observed_at_ns - provider_health.as_of_time_ns)
        if staleness_ns > staleness_threshold_ns:
            state = HealthState.UNHEALTHY
            reasons.append(GovernanceReasonCode.PROVIDER_STALE)
        elif staleness_ns == staleness_threshold_ns:
            state = HealthState.DEGRADED
            reasons.append(GovernanceReasonCode.PROVIDER_STALE)

    if not connected:
        state = HealthState.UNHEALTHY
        reasons.append(GovernanceReasonCode.PROVIDER_DISCONNECTED)

    invalid_quote_count = sum(
        1 for finding in provider_health.findings if finding.code == QualityFindingCode.INVALID_QUOTE
    )
    crossed_book_count = sum(
        1 for finding in provider_health.findings if finding.code == QualityFindingCode.CROSSED_BOOK
    )
    clock_drift_count = sum(
        1 for finding in provider_health.findings if finding.code == QualityFindingCode.CLOCK_DRIFT
    )
    disconnect_count = sum(
        1 for finding in provider_health.findings if finding.code == QualityFindingCode.PROVIDER_DISCONNECTED
    )

    return ProviderHealthSnapshotV1(
        snapshot_id=derive_health_snapshot_id(
            kind="provider",
            window=window,
            context_key=f"{provider}:{capability or '*'}",
        ),
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        provider=provider,
        capability=capability,
        observed_at_ns=observed_at_ns,
        window=window,
        connected=connected,
        last_event_available_time_ns=provider_health.as_of_time_ns,
        last_event_received_time_ns=provider_health.as_of_time_ns,
        event_count=len(provider_health.observations),
        invalid_quote_count=invalid_quote_count,
        crossed_book_count=crossed_book_count,
        clock_drift_count=clock_drift_count,
        disconnect_count=disconnect_count,
        staleness_ns=staleness_ns,
        health_state=state,
        reason_codes=tuple(reasons),
    )


def assess_data_quality_health(
    *,
    window: MonitoringWindowV1,
    quality_actions: tuple[str, ...],
    finding_codes: tuple[str, ...],
) -> DataQualityHealthSnapshotV1:
    observation_count = len(quality_actions)
    if observation_count == 0:
        return DataQualityHealthSnapshotV1(
            snapshot_id=derive_health_snapshot_id(kind="data_quality", window=window, context_key="aggregate"),
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            window=window,
            health_state=HealthState.UNKNOWN,
            reason_codes=(GovernanceReasonCode.NO_OBSERVATIONS,),
        )

    usable_count = sum(1 for action in quality_actions if action == DecisionAction.USE.value)
    degraded_count = sum(1 for action in quality_actions if action == DecisionAction.DEGRADE.value)
    abstain_count = sum(1 for action in quality_actions if action == DecisionAction.ABSTAIN.value)
    fail_closed_count = sum(1 for action in quality_actions if action == DecisionAction.FAIL_CLOSED.value)
    invalid_quote_count = sum(1 for code in finding_codes if code == QualityFindingCode.INVALID_QUOTE.value)
    crossed_book_count = sum(1 for code in finding_codes if code == QualityFindingCode.CROSSED_BOOK.value)
    clock_drift_count = sum(1 for code in finding_codes if code == QualityFindingCode.CLOCK_DRIFT.value)
    capability_unavailable_count = sum(
        1 for code in finding_codes if code == QualityFindingCode.CAPABILITY_UNAVAILABLE.value
    )

    fail_closed_rate = _rate(fail_closed_count, observation_count) or 0.0
    if fail_closed_rate > 0.5:
        state = HealthState.UNHEALTHY
    elif fail_closed_rate > 0.0 or degraded_count > 0:
        state = HealthState.DEGRADED
    else:
        state = HealthState.HEALTHY

    return DataQualityHealthSnapshotV1(
        snapshot_id=derive_health_snapshot_id(kind="data_quality", window=window, context_key="aggregate"),
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        window=window,
        observation_count=observation_count,
        usable_count=usable_count,
        degraded_count=degraded_count,
        abstain_count=abstain_count,
        fail_closed_count=fail_closed_count,
        invalid_quote_count=invalid_quote_count,
        crossed_book_count=crossed_book_count,
        clock_drift_count=clock_drift_count,
        capability_unavailable_count=capability_unavailable_count,
        health_state=state,
        metadata={
            "usable_rate": _rate(usable_count, observation_count),
            "degraded_rate": _rate(degraded_count, observation_count),
            "abstain_rate": _rate(abstain_count, observation_count),
            "fail_closed_rate": fail_closed_rate,
        },
    )


def assess_intelligence_health(
    *,
    window: MonitoringWindowV1,
    champion_scope,
    cohort_rows: tuple[EvaluationCohortRow, ...],
    forecast_count: int,
    abstention_count: int,
    ood_count: int,
    quality_degraded_count: int,
    reference_brier: float | None = None,
    minimum_sample: int = 10,
) -> IntelligenceHealthSnapshotV1:
    spec = EvaluationSpec(probability_view=ProbabilityView.CALIBRATED)
    metrics = compute_predictive_metrics(cohort_rows, spec)
    reasons: list[GovernanceReasonCode] = []
    state = HealthState.UNKNOWN

    labelable = sum(1 for row in cohort_rows if row.binary_label is not None)
    labelable_fraction = _rate(labelable, len(cohort_rows)) if cohort_rows else None
    settlement_coverage = labelable_fraction

    if metrics.status == AggregateStatus.EMPTY_COHORT:
        reasons.append(GovernanceReasonCode.NO_OBSERVATIONS)
    elif metrics.sample_count < minimum_sample:
        reasons.append(GovernanceReasonCode.INSUFFICIENT_SAMPLE)
        state = HealthState.UNKNOWN
    else:
        state = HealthState.HEALTHY
        if reference_brier is not None and metrics.brier_score is not None:
            if metrics.brier_score - reference_brier > 0:
                state = HealthState.DEGRADED
                reasons.append(GovernanceReasonCode.PERFORMANCE_DRIFT_DETECTED)

    ood_fraction = _rate(ood_count, forecast_count) if forecast_count > 0 else None
    quality_degraded_fraction = _rate(quality_degraded_count, forecast_count) if forecast_count > 0 else None

    return IntelligenceHealthSnapshotV1(
        snapshot_id=derive_health_snapshot_id(
            kind="intelligence",
            window=window,
            context_key=champion_scope.component,
        ),
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        window=window,
        champion_scope=champion_scope,
        forecast_count=forecast_count,
        abstention_count=abstention_count,
        settlement_coverage=settlement_coverage,
        labelable_fraction=labelable_fraction,
        brier_score=metrics.brier_score,
        log_loss=metrics.log_loss,
        ece=None,
        ood_fraction=ood_fraction,
        quality_degraded_fraction=quality_degraded_fraction,
        health_state=state,
        reason_codes=tuple(reasons),
        metadata={"metrics_status": metrics.status.value},
    )


def assess_execution_health(
    *,
    window: MonitoringWindowV1,
    proposal_count: int,
    risk_approvals: int,
    risk_reductions: int,
    risk_rejections: int,
    risk_fail_closed: int,
    paper_orders: int,
    fills: int,
    no_fills: int,
    cancels: int,
    duplicate_preventions: int,
    daily_loss_guards: int,
) -> ExecutionHealthSnapshotV1:
    state = HealthState.UNKNOWN
    reasons: list[GovernanceReasonCode] = []
    if proposal_count == 0:
        reasons.append(GovernanceReasonCode.NO_OBSERVATIONS)
    else:
        state = HealthState.HEALTHY
        fail_closed_rate = _rate(risk_fail_closed, proposal_count) or 0.0
        if fail_closed_rate > 0.25:
            state = HealthState.UNHEALTHY
            reasons.append(GovernanceReasonCode.RISK_SUBSYSTEM_UNHEALTHY)

    return ExecutionHealthSnapshotV1(
        snapshot_id=derive_health_snapshot_id(kind="execution", window=window, context_key="paper"),
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        window=window,
        execution_mode="PAPER",
        proposal_count=proposal_count,
        risk_approval_count=risk_approvals,
        risk_reduction_count=risk_reductions,
        risk_rejection_count=risk_rejections,
        risk_fail_closed_count=risk_fail_closed,
        paper_order_count=paper_orders,
        fill_count=fills,
        no_fill_count=no_fills,
        cancel_count=cancels,
        duplicate_prevention_count=duplicate_preventions,
        daily_loss_guard_count=daily_loss_guards,
        health_state=state,
        reason_codes=tuple(reasons),
        metadata={
            "risk_approval_rate": _rate(risk_approvals, proposal_count),
            "risk_rejection_rate": _rate(risk_rejections, proposal_count),
            "risk_fail_closed_rate": _rate(risk_fail_closed, proposal_count),
        },
    )


def assess_opportunity_health(
    *,
    window: MonitoringWindowV1,
    assessments: tuple,
) -> OpportunityHealthSnapshotV1:
    if not assessments:
        return OpportunityHealthSnapshotV1(
            snapshot_id=derive_health_snapshot_id(kind="opportunity", window=window, context_key="aggregate"),
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            window=window,
            health_state=HealthState.UNKNOWN,
            reason_codes=(GovernanceReasonCode.NO_OBSERVATIONS,),
        )

    emitted = sum(1 for item in assessments if item.assessment_action == AssessmentAction.EMIT)
    suppressed = sum(1 for item in assessments if item.assessment_action == AssessmentAction.SUPPRESS)
    abstained = sum(1 for item in assessments if item.assessment_action == AssessmentAction.ABSTAIN)
    fail_closed = sum(1 for item in assessments if item.assessment_action == AssessmentAction.FAIL_CLOSED)

    return OpportunityHealthSnapshotV1(
        snapshot_id=derive_health_snapshot_id(kind="opportunity", window=window, context_key="aggregate"),
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        window=window,
        assessment_count=len(assessments),
        emitted_count=emitted,
        suppressed_count=suppressed,
        abstained_count=abstained,
        fail_closed_count=fail_closed,
        health_state=HealthState.HEALTHY,
        metadata={
            "emitted_rate": _rate(emitted, len(assessments)),
            "suppressed_rate": _rate(suppressed, len(assessments)),
            "fail_closed_rate": _rate(fail_closed, len(assessments)),
        },
    )
