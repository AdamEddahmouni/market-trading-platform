"""Fail-safe decision engine (BUILD 23)."""

from __future__ import annotations

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION, ContractKind, ContractReference
from .identity import derive_fail_safe_decision_id
from .types import (
    DriftAssessmentV1,
    DriftSeverity,
    DriftType,
    FailSafeDecisionKind,
    FailSafeDecisionV1,
    FailSafePolicyV1,
    GovernanceReasonCode,
    HealthState,
    ProviderHealthSnapshotV1,
    RuntimeActivationV1,
)


class FailSafeEngine:
    """Deterministic fail-safe evaluator — alerts do not auto-disable unless mapped here."""

    def evaluate(
        self,
        *,
        policy: FailSafePolicyV1,
        decision_time_ns: int,
        activation: RuntimeActivationV1 | None,
        runtime_consistent: bool,
        runtime_reasons: tuple[GovernanceReasonCode, ...],
        provider_health: ProviderHealthSnapshotV1 | None = None,
        drift_assessments: tuple[DriftAssessmentV1, ...] = (),
        execution_health_state: HealthState = HealthState.UNKNOWN,
        trigger_key: str = "aggregate",
    ) -> FailSafeDecisionV1:
        decision = FailSafeDecisionKind.ALLOW
        reasons: list[GovernanceReasonCode] = []
        trigger_refs: list[ContractReference] = []

        if activation is None:
            decision = FailSafeDecisionKind.DISABLE_SCOPE
            reasons.append(GovernanceReasonCode.RUNTIME_GOVERNANCE_DISABLED)
        elif not runtime_consistent:
            decision = policy.runtime_mismatch_action
            reasons.extend(runtime_reasons)

        if provider_health is not None and provider_health.health_state == HealthState.UNHEALTHY:
            if _rank(decision) < _rank(policy.provider_critical_action):
                decision = policy.provider_critical_action
            reasons.extend(provider_health.reason_codes)

        for assessment in drift_assessments:
            if assessment.severity == DriftSeverity.CRITICAL:
                if DriftType.SCHEMA_DRIFT in assessment.drift_types:
                    if _rank(decision) < _rank(policy.schema_drift_action):
                        decision = policy.schema_drift_action
                    reasons.extend(assessment.reason_codes)
                trigger_refs.append(
                    ContractReference(
                        kind=ContractKind.RUN_MANIFEST.value,
                        id=assessment.drift_assessment_id,
                    )
                )

        if execution_health_state == HealthState.UNHEALTHY:
            if _rank(decision) < _rank(policy.risk_subsystem_action):
                decision = policy.risk_subsystem_action
            reasons.append(GovernanceReasonCode.RISK_SUBSYSTEM_UNHEALTHY)

        return FailSafeDecisionV1(
            decision_id=derive_fail_safe_decision_id(
                policy_id=policy.fail_safe_policy_id,
                decision_time_ns=decision_time_ns,
                decision=decision.value,
                trigger_key=trigger_key,
            ),
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            policy_id=policy.fail_safe_policy_id,
            champion_scope=policy.champion_scope,
            decision_time_ns=decision_time_ns,
            decision=decision,
            trigger_refs=tuple(trigger_refs),
            reason_codes=tuple(dict.fromkeys(reasons)),
        )


def _rank(decision: FailSafeDecisionKind) -> int:
    order = {
        FailSafeDecisionKind.ALLOW: 0,
        FailSafeDecisionKind.DEGRADE: 1,
        FailSafeDecisionKind.DISABLE_NEW_OPPORTUNITIES: 2,
        FailSafeDecisionKind.DISABLE_NEW_PAPER_ORDERS: 3,
        FailSafeDecisionKind.DISABLE_SCOPE: 4,
        FailSafeDecisionKind.FAIL_CLOSED: 5,
    }
    return order[decision]
