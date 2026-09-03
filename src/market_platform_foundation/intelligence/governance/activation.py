"""Runtime activation engine (BUILD 23)."""

from __future__ import annotations

from typing import Any

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION, ContractKind, ContractReference
from ..promotion.types import ChampionAssignmentReason, ChampionAssignmentV1, ChampionScopeV1
from .errors import ActivationError
from .identity import derive_runtime_activation_id
from .types import (
    ActivationStatus,
    ExecutionAuthority,
    GovernanceReasonCode,
    RuntimeActivationPolicyV1,
    RuntimeActivationV1,
    RuntimeReportedIdentityV1,
)


def verify_artifact_hash(
    *,
    expected_hash: str,
    artifact_bytes: bytes | None,
) -> bool:
    if artifact_bytes is None:
        return False
    from ..training.identity import artifact_content_hash

    digest = artifact_content_hash(artifact_bytes)
    return digest == expected_hash


def scopes_equal(left: ChampionScopeV1, right: ChampionScopeV1) -> bool:
    return (
        left.component == right.component
        and left.target_kind == right.target_kind
        and left.horizon_ns == right.horizon_ns
        and left.mode == right.mode
        and left.scenario_id == right.scenario_id
    )


class ActivationEngine:
    """Governed runtime activation — separate from BUILD 20 promotion."""

    def validate_policy(self, policy: RuntimeActivationPolicyV1) -> None:
        if policy.live_execution_forbidden and "LIVE" in policy.allowed_execution_modes:
            raise ActivationError("ACTIVATION_LIVE_EXECUTION_FORBIDDEN")
        if not policy.paper_execution_only:
            raise ActivationError("PAPER_EXECUTION_ONLY_REQUIRED")

    def create_activation(
        self,
        *,
        policy: RuntimeActivationPolicyV1,
        champion_assignment: ChampionAssignmentV1,
        effective_from_ns: int,
        artifact_bytes: bytes | None = None,
        previous_activation: RuntimeActivationV1 | None = None,
        execution_authority: ExecutionAuthority = ExecutionAuthority.PAPER_EXECUTION,
        metadata: dict[str, Any] | None = None,
    ) -> RuntimeActivationV1:
        self.validate_policy(policy)
        scope = champion_assignment.champion_scope
        if not scopes_equal(scope, policy.champion_scope):
            raise ActivationError("ACTIVATION_SCOPE_MISMATCH")

        if policy.require_promotion_lineage and champion_assignment.assignment_reason not in {
            ChampionAssignmentReason.PROMOTION,
            ChampionAssignmentReason.BOOTSTRAP,
        }:
            raise ActivationError("ACTIVATION_UNPROMOTED_CANDIDATE")

        if policy.require_artifact_integrity:
            if not verify_artifact_hash(
                expected_hash=champion_assignment.candidate_artifact_hash,
                artifact_bytes=artifact_bytes,
            ):
                raise ActivationError("ACTIVATION_ARTIFACT_INTEGRITY_FAILED")

        body = RuntimeActivationV1(
            activation_id="DERIVE",
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            champion_scope=scope,
            champion_assignment_id=champion_assignment.assignment_id,
            candidate_id=champion_assignment.candidate_id,
            candidate_artifact_hash=champion_assignment.candidate_artifact_hash,
            promotion_decision_id=champion_assignment.promotion_decision_id,
            activation_policy_id=policy.activation_policy_id,
            effective_from_ns=effective_from_ns,
            execution_mode="PAPER",
            data_mode=scope.mode,
            execution_authority=execution_authority,
            previous_activation_id=previous_activation.activation_id if previous_activation else None,
            status=ActivationStatus.ACTIVE,
            lineage_refs=(
                ContractReference(
                    kind=ContractKind.RUN_MANIFEST.value,
                    id=champion_assignment.assignment_id,
                ),
                ContractReference(
                    kind=ContractKind.RUN_MANIFEST.value,
                    id=policy.activation_policy_id,
                ),
            ),
            metadata=dict(metadata or {}),
        )
        activation_id = derive_runtime_activation_id(body)
        return RuntimeActivationV1(
            activation_id=activation_id,
            schema_version=body.schema_version,
            champion_scope=body.champion_scope,
            champion_assignment_id=body.champion_assignment_id,
            candidate_id=body.candidate_id,
            candidate_artifact_hash=body.candidate_artifact_hash,
            promotion_decision_id=body.promotion_decision_id,
            activation_policy_id=body.activation_policy_id,
            effective_from_ns=body.effective_from_ns,
            effective_until_ns=body.effective_until_ns,
            execution_mode=body.execution_mode,
            data_mode=body.data_mode,
            execution_authority=body.execution_authority,
            runtime_config_refs=body.runtime_config_refs,
            previous_activation_id=body.previous_activation_id,
            status=body.status,
            lineage_refs=body.lineage_refs,
            metadata=body.metadata,
        )

    def check_runtime_consistency(
        self,
        *,
        activation: RuntimeActivationV1,
        reported: RuntimeReportedIdentityV1 | None,
    ) -> tuple[bool, tuple[GovernanceReasonCode, ...]]:
        if reported is None:
            return False, (GovernanceReasonCode.RUNTIME_IDENTITY_MISSING,)
        reasons: list[GovernanceReasonCode] = []
        if reported.candidate_artifact_hash is not None and reported.candidate_artifact_hash != activation.candidate_artifact_hash:
            reasons.append(GovernanceReasonCode.RUNTIME_ASSIGNMENT_MISMATCH)
        if reported.candidate_id is not None and reported.candidate_id != activation.candidate_id:
            reasons.append(GovernanceReasonCode.RUNTIME_ASSIGNMENT_MISMATCH)
        if reported.policy_stack_hash is not None:
            expected_stack = activation.activation_policy_id
            if reported.policy_stack_hash != expected_stack:
                reasons.append(GovernanceReasonCode.RUNTIME_POLICY_MISMATCH)
        return (len(reasons) == 0, tuple(reasons))
