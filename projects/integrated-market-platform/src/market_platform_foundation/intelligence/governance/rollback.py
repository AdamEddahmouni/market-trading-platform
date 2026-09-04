"""Rollback decision engine (BUILD 23)."""

from __future__ import annotations

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION, ContractKind, ContractReference
from ..promotion.types import ChampionAssignmentReason, ChampionAssignmentV1
from .activation import ActivationEngine, verify_artifact_hash
from .errors import RollbackError
from .identity import derive_rollback_decision_id
from .types import (
    DriftAssessmentV1,
    DriftSeverity,
    DriftType,
    FailSafeDecisionV1,
    GovernanceReasonCode,
    RollbackDecisionKind,
    RollbackDecisionV1,
    RollbackPolicyV1,
    RuntimeActivationV1,
)


def _severity_rank(severity: DriftSeverity) -> int:
    return {
        DriftSeverity.NONE: 0,
        DriftSeverity.INFO: 1,
        DriftSeverity.WARNING: 2,
        DriftSeverity.CRITICAL: 3,
        DriftSeverity.UNKNOWN: -1,
    }[severity]


class RollbackEngine:
    """Governed rollback to previously known-good runtime activation."""

    def __init__(self) -> None:
        self._activation_engine = ActivationEngine()

    def evaluate(
        self,
        *,
        policy: RollbackPolicyV1,
        current_activation: RuntimeActivationV1,
        previous_activation: RuntimeActivationV1 | None,
        champion_assignment_for_target: ChampionAssignmentV1 | None,
        artifact_bytes_by_assignment: dict[str, bytes | None],
        drift_assessments: tuple[DriftAssessmentV1, ...] = (),
        fail_safe: FailSafeDecisionV1 | None = None,
        effective_time_ns: int,
        consecutive_failures: int = 1,
        last_rollback_time_ns: int | None = None,
    ) -> RollbackDecisionV1:
        reasons: list[GovernanceReasonCode] = []
        decision = RollbackDecisionKind.RETAIN
        target_activation_id: str | None = None
        trigger_refs: list[ContractReference] = []

        critical_triggers = [
            assessment
            for assessment in drift_assessments
            if _severity_rank(assessment.severity) >= _severity_rank(policy.minimum_trigger_severity)
            and any(t in policy.allowed_trigger_types for t in assessment.drift_types)
        ]
        for assessment in critical_triggers:
            trigger_refs.append(
                ContractReference(
                    kind=ContractKind.RUN_MANIFEST.value,
                    id=assessment.drift_assessment_id,
                )
            )

        if consecutive_failures < policy.consecutive_failure_threshold:
            return self._finalize(
                policy=policy,
                current_activation=current_activation,
                target_activation_id=None,
                decision=RollbackDecisionKind.RETAIN,
                reasons=(GovernanceReasonCode.INSUFFICIENT_SAMPLE,),
                effective_time_ns=effective_time_ns,
                trigger_refs=tuple(trigger_refs),
            )

        if last_rollback_time_ns is not None and policy.cooldown_ns > 0:
            if effective_time_ns - last_rollback_time_ns < policy.cooldown_ns:
                return self._finalize(
                    policy=policy,
                    current_activation=current_activation,
                    target_activation_id=None,
                    decision=RollbackDecisionKind.RETAIN,
                    reasons=(GovernanceReasonCode.COOLDOWN_ACTIVE,),
                    effective_time_ns=effective_time_ns,
                    trigger_refs=tuple(trigger_refs),
                )

        if not critical_triggers and fail_safe is None:
            return self._finalize(
                policy=policy,
                current_activation=current_activation,
                target_activation_id=None,
                decision=RollbackDecisionKind.RETAIN,
                reasons=(),
                effective_time_ns=effective_time_ns,
                trigger_refs=tuple(trigger_refs),
            )

        if previous_activation is None:
            return self._finalize(
                policy=policy,
                current_activation=current_activation,
                target_activation_id=None,
                decision=RollbackDecisionKind.DISABLE_ONLY,
                reasons=(GovernanceReasonCode.ROLLBACK_NO_KNOWN_GOOD,),
                effective_time_ns=effective_time_ns,
                trigger_refs=tuple(trigger_refs),
            )

        target_activation_id = previous_activation.activation_id
        if champion_assignment_for_target is None:
            return self._finalize(
                policy=policy,
                current_activation=current_activation,
                target_activation_id=None,
                decision=RollbackDecisionKind.INVALID,
                reasons=(GovernanceReasonCode.ROLLBACK_TARGET_INVALID,),
                effective_time_ns=effective_time_ns,
                trigger_refs=tuple(trigger_refs),
            )

        if champion_assignment_for_target.assignment_reason not in {
            ChampionAssignmentReason.PROMOTION,
            ChampionAssignmentReason.BOOTSTRAP,
        }:
            return self._finalize(
                policy=policy,
                current_activation=current_activation,
                target_activation_id=None,
                decision=RollbackDecisionKind.INVALID,
                reasons=(GovernanceReasonCode.ROLLBACK_UNPROMOTED_TARGET,),
                effective_time_ns=effective_time_ns,
                trigger_refs=tuple(trigger_refs),
            )

        if policy.require_artifact_integrity:
            artifact_bytes = artifact_bytes_by_assignment.get(champion_assignment_for_target.assignment_id)
            if not verify_artifact_hash(
                expected_hash=champion_assignment_for_target.candidate_artifact_hash,
                artifact_bytes=artifact_bytes,
            ):
                return self._finalize(
                    policy=policy,
                    current_activation=current_activation,
                    target_activation_id=None,
                    decision=RollbackDecisionKind.INVALID,
                    reasons=(GovernanceReasonCode.ROLLBACK_ARTIFACT_INTEGRITY_FAILED,),
                    effective_time_ns=effective_time_ns,
                    trigger_refs=tuple(trigger_refs),
                )

        scope = policy.champion_scope
        if previous_activation.champion_scope.component != scope.component:
            return self._finalize(
                policy=policy,
                current_activation=current_activation,
                target_activation_id=None,
                decision=RollbackDecisionKind.INVALID,
                reasons=(GovernanceReasonCode.ROLLBACK_SCOPE_MISMATCH,),
                effective_time_ns=effective_time_ns,
                trigger_refs=tuple(trigger_refs),
            )

        if critical_triggers:
            decision = RollbackDecisionKind.ROLLBACK
            reasons.append(GovernanceReasonCode.ROLLBACK_TARGET_VALID)

        return self._finalize(
            policy=policy,
            current_activation=current_activation,
            target_activation_id=target_activation_id,
            decision=decision,
            reasons=tuple(dict.fromkeys(reasons)),
            effective_time_ns=effective_time_ns,
            trigger_refs=tuple(trigger_refs),
        )

    def apply_rollback(
        self,
        *,
        activation_policy,
        rollback_decision: RollbackDecisionV1,
        target_activation: RuntimeActivationV1,
        champion_assignment: ChampionAssignmentV1,
        artifact_bytes: bytes | None,
        effective_from_ns: int,
    ) -> RuntimeActivationV1:
        if rollback_decision.decision != RollbackDecisionKind.ROLLBACK:
            raise RollbackError("ROLLBACK_NOT_AUTHORIZED")
        return self._activation_engine.create_activation(
            policy=activation_policy,
            champion_assignment=champion_assignment,
            effective_from_ns=effective_from_ns,
            artifact_bytes=artifact_bytes,
            previous_activation=target_activation,
            metadata={
                "rollback_decision_id": rollback_decision.rollback_decision_id,
                "rollback_from_activation_id": rollback_decision.current_activation_id,
                "active_fallback": True,
            },
        )

    def _finalize(
        self,
        *,
        policy: RollbackPolicyV1,
        current_activation: RuntimeActivationV1,
        target_activation_id: str | None,
        decision: RollbackDecisionKind,
        reasons: tuple[GovernanceReasonCode, ...],
        effective_time_ns: int,
        trigger_refs: tuple[ContractReference, ...],
    ) -> RollbackDecisionV1:
        return RollbackDecisionV1(
            rollback_decision_id=derive_rollback_decision_id(
                policy_id=policy.rollback_policy_id,
                current_activation_id=current_activation.activation_id,
                target_activation_id=target_activation_id,
                decision=decision.value,
                effective_time_ns=effective_time_ns,
            ),
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            policy_id=policy.rollback_policy_id,
            current_activation_id=current_activation.activation_id,
            target_activation_id=target_activation_id,
            trigger_refs=trigger_refs,
            decision=decision,
            reason_codes=reasons,
            effective_time_ns=effective_time_ns,
        )
