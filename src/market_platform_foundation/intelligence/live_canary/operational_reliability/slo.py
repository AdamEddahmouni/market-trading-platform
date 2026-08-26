"""SLO policy and assessment (BUILD 32)."""

from __future__ import annotations

from .identity import derive_slo_assessment_id, derive_slo_policy_id
from .types import (
    OPERATIONAL_RELIABILITY_IMPLEMENTATION_VERSION,
    OPERATIONAL_RELIABILITY_SCHEMA_VERSION,
    OperationalSLOAssessmentV1,
    OperationalSLOPolicyV1,
    SLOObjectiveResultV1,
    SLOObjectiveStatus,
    SLOObjectiveV1,
)

# Conservative qualification objectives rooted in local testability.
DEFAULT_WINDOW_NS = 300_000_000_000  # 5 minutes
DEFAULT_CADENCE_NS = 60_000_000_000  # 1 minute
DEFAULT_MINIMUM_SAMPLE = 3


def build_default_slo_policy(*, scope: str = "supervised_live_canary") -> OperationalSLOPolicyV1:
    objectives = (
        SLOObjectiveV1(
            objective_id="provider_connection_availability",
            description="Provider adapter connection availability",
            warning_threshold=0.95,
            critical_threshold=0.90,
            safety_critical=True,
            missing_data_semantics="INSUFFICIENT_DATA",
        ),
        SLOObjectiveV1(
            objective_id="broker_status_freshness",
            description="Broker status feed freshness within stale threshold",
            warning_threshold=0.95,
            critical_threshold=0.90,
            safety_critical=True,
            missing_data_semantics="INSUFFICIENT_DATA",
        ),
        SLOObjectiveV1(
            objective_id="reconciliation_freshness",
            description="Reconciliation cycle success rate",
            warning_threshold=0.98,
            critical_threshold=0.95,
            safety_critical=True,
            missing_data_semantics="INSUFFICIENT_DATA",
        ),
        SLOObjectiveV1(
            objective_id="persistence_write_success",
            description="Canonical persistence write success rate",
            warning_threshold=0.99,
            critical_threshold=0.95,
            safety_critical=True,
            missing_data_semantics="INSUFFICIENT_DATA",
        ),
        SLOObjectiveV1(
            objective_id="operator_api_availability",
            description="Operator API availability",
            warning_threshold=0.99,
            critical_threshold=0.95,
            safety_critical=False,
            missing_data_semantics="INSUFFICIENT_DATA",
        ),
        SLOObjectiveV1(
            objective_id="critical_alert_delivery_success",
            description="Critical alert delivery success rate",
            warning_threshold=0.99,
            critical_threshold=0.95,
            safety_critical=True,
            missing_data_semantics="INSUFFICIENT_DATA",
        ),
    )
    policy = OperationalSLOPolicyV1(
        slo_policy_id="",
        schema_version=OPERATIONAL_RELIABILITY_SCHEMA_VERSION,
        scope=scope,
        measurement_window_ns=DEFAULT_WINDOW_NS,
        evaluation_cadence_ns=DEFAULT_CADENCE_NS,
        objectives=objectives,
        minimum_sample=DEFAULT_MINIMUM_SAMPLE,
        missing_data_semantics="INSUFFICIENT_DATA",
        implementation_version=OPERATIONAL_RELIABILITY_IMPLEMENTATION_VERSION,
    )
    policy_id = derive_slo_policy_id(policy)
    return OperationalSLOPolicyV1(
        slo_policy_id=policy_id,
        schema_version=policy.schema_version,
        scope=policy.scope,
        measurement_window_ns=policy.measurement_window_ns,
        evaluation_cadence_ns=policy.evaluation_cadence_ns,
        objectives=policy.objectives,
        minimum_sample=policy.minimum_sample,
        missing_data_semantics=policy.missing_data_semantics,
        implementation_version=policy.implementation_version,
        metadata=policy.metadata,
    )


def _evaluate_objective(
    objective: SLOObjectiveV1,
    *,
    success_count: int,
    total_count: int,
    minimum_sample: int,
) -> SLOObjectiveResultV1:
    if total_count < minimum_sample:
        return SLOObjectiveResultV1(
            objective_id=objective.objective_id,
            target_warning=objective.warning_threshold,
            target_critical=objective.critical_threshold,
            observed_value=None,
            sample_count=total_count,
            status=SLOObjectiveStatus.INSUFFICIENT_DATA.value,
            reason_codes=("MISSING_DATA",),
        )
    observed = success_count / total_count
    if observed < objective.critical_threshold:
        status = SLOObjectiveStatus.CRITICAL
    elif observed < objective.warning_threshold:
        status = SLOObjectiveStatus.WARNING
    else:
        status = SLOObjectiveStatus.HEALTHY
    return SLOObjectiveResultV1(
        objective_id=objective.objective_id,
        target_warning=objective.warning_threshold,
        target_critical=objective.critical_threshold,
        observed_value=observed,
        sample_count=total_count,
        status=status.value,
    )


def assess_operational_slos(
    policy: OperationalSLOPolicyV1,
    *,
    window_start_ns: int,
    window_end_ns: int,
    as_of_ns: int,
    samples: dict[str, tuple[int, int]],
) -> OperationalSLOAssessmentV1:
    """Assess SLOs from success/total sample counts per objective."""
    results: list[SLOObjectiveResultV1] = []
    overall = SLOObjectiveStatus.HEALTHY
    reason_codes: list[str] = []
    for objective in policy.objectives:
        success, total = samples.get(objective.objective_id, (0, 0))
        result = _evaluate_objective(
            objective,
            success_count=success,
            total_count=total,
            minimum_sample=policy.minimum_sample,
        )
        results.append(result)
        if result.status == SLOObjectiveStatus.CRITICAL.value:
            overall = SLOObjectiveStatus.CRITICAL
            reason_codes.append(f"SLO_CRITICAL:{objective.objective_id}")
        elif result.status == SLOObjectiveStatus.INSUFFICIENT_DATA.value and overall == SLOObjectiveStatus.HEALTHY:
            overall = SLOObjectiveStatus.INSUFFICIENT_DATA
            reason_codes.append(f"SLO_INSUFFICIENT_DATA:{objective.objective_id}")
        elif result.status == SLOObjectiveStatus.WARNING.value and overall in {
            SLOObjectiveStatus.HEALTHY,
            SLOObjectiveStatus.INSUFFICIENT_DATA,
        }:
            overall = SLOObjectiveStatus.WARNING
            reason_codes.append(f"SLO_WARNING:{objective.objective_id}")

    assessment = OperationalSLOAssessmentV1(
        assessment_id="",
        schema_version=OPERATIONAL_RELIABILITY_SCHEMA_VERSION,
        policy_ref=policy.slo_policy_id,
        scope=policy.scope,
        window_start_ns=window_start_ns,
        window_end_ns=window_end_ns,
        as_of_ns=as_of_ns,
        objective_results=tuple(results),
        overall_status=overall.value,
        reason_codes=tuple(reason_codes),
        source_refs=(policy.slo_policy_id,),
    )
    return OperationalSLOAssessmentV1(
        assessment_id=derive_slo_assessment_id(assessment),
        schema_version=assessment.schema_version,
        policy_ref=assessment.policy_ref,
        scope=assessment.scope,
        window_start_ns=assessment.window_start_ns,
        window_end_ns=assessment.window_end_ns,
        as_of_ns=assessment.as_of_ns,
        objective_results=assessment.objective_results,
        overall_status=assessment.overall_status,
        reason_codes=assessment.reason_codes,
        source_refs=assessment.source_refs,
        implementation_version=assessment.implementation_version,
    )
