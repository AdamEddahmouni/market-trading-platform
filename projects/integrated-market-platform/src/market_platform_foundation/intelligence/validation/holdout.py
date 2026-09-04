"""Locked holdout commitment and access guard (BUILD 19)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION
from ..persistence.repository import IntelligenceRepository
from .errors import ValidationError
from .identity import derive_holdout_commitment_id
from .types import HoldoutCommitmentV1, HoldoutUnlockReceiptV1, ValidationPlanV1


@dataclass
class HoldoutAccessState:
    commitment: HoldoutCommitmentV1 | None = None
    receipt: HoldoutUnlockReceiptV1 | None = None
    outcome_access_count: int = 0
    _outcome_reads_before_commitment: list[dict] = field(default_factory=list)


class ValidationDataAccessGuard:
    """Fail-closed gate for holdout outcome access."""

    def __init__(self, repository: IntelligenceRepository) -> None:
        self.repository = repository
        self._state = HoldoutAccessState()
        self._committed = False
        self._unlocked = False

    @property
    def commitment(self) -> HoldoutCommitmentV1 | None:
        return self._state.commitment

    @property
    def receipt(self) -> HoldoutUnlockReceiptV1 | None:
        return self._state.receipt

    @property
    def outcome_reads_before_commitment(self) -> tuple[dict, ...]:
        return tuple(self._state._outcome_reads_before_commitment)

    def commit_holdout(self, plan: ValidationPlanV1) -> HoldoutCommitmentV1:
        if self._committed:
            raise ValidationError("HOLDOUT_ALREADY_COMMITTED")
        commitment = HoldoutCommitmentV1(
            holdout_commitment_id="PENDING",
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            validation_plan_id=plan.validation_plan_id,
            experiment_id=plan.experiment_id,
            candidate_ids=plan.candidate_ids,
            candidate_artifact_hashes=plan.candidate_artifact_hashes,
            control_ref=plan.control_ref,
            holdout_spec=plan.holdout_spec,
            primary_metric=plan.primary_metric,
            guardrail_metrics=plan.guardrail_metrics,
            statistical_plan=plan.statistical_plan,
            temporal_knowledge_policy_id=plan.temporal_knowledge_policy.policy_id,
        )
        commitment_id = derive_holdout_commitment_id(commitment)
        commitment = HoldoutCommitmentV1(
            holdout_commitment_id=commitment_id,
            schema_version=commitment.schema_version,
            validation_plan_id=commitment.validation_plan_id,
            experiment_id=commitment.experiment_id,
            candidate_ids=commitment.candidate_ids,
            candidate_artifact_hashes=commitment.candidate_artifact_hashes,
            control_ref=commitment.control_ref,
            holdout_spec=commitment.holdout_spec,
            primary_metric=commitment.primary_metric,
            guardrail_metrics=commitment.guardrail_metrics,
            statistical_plan=commitment.statistical_plan,
            temporal_knowledge_policy_id=commitment.temporal_knowledge_policy_id,
            metadata=commitment.metadata,
        )
        self._state.commitment = commitment
        self._committed = True
        if hasattr(self.repository, "put_holdout_commitment"):
            self.repository.put_holdout_commitment(commitment)
        return commitment

    def unlock_holdout(self, *, unlocked_at_ns: int, context: str) -> HoldoutUnlockReceiptV1:
        if not self._committed or self._state.commitment is None:
            raise ValidationError("HOLDOUT_NOT_COMMITTED")
        commitment = self._state.commitment
        receipt_id = hashlib.sha256(
            f"{commitment.holdout_commitment_id}:{unlocked_at_ns}:{context}".encode()
        ).hexdigest()
        receipt = HoldoutUnlockReceiptV1(
            receipt_id=f"UNLOCK-{receipt_id[:16]}",
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            holdout_commitment_id=commitment.holdout_commitment_id,
            validation_plan_id=commitment.validation_plan_id,
            candidate_ids=commitment.candidate_ids,
            unlocked_at_ns=unlocked_at_ns,
            context=context,
        )
        self._state.receipt = receipt
        self._unlocked = True
        if hasattr(self.repository, "put_holdout_unlock_receipt"):
            self.repository.put_holdout_unlock_receipt(receipt)
        return receipt

    def get_holdout_outcome(self, outcome_id: str):
        if not self._committed:
            self._state._outcome_reads_before_commitment.append({"outcome_id": outcome_id})
            raise ValidationError("HOLDOUT_OUTCOME_ACCESS_BEFORE_COMMITMENT")
        if not self._unlocked:
            raise ValidationError("HOLDOUT_OUTCOME_ACCESS_BEFORE_UNLOCK")
        self._state.outcome_access_count += 1
        return self.repository.get_outcome(outcome_id)

    def get_holdout_metadata(self, *, decision_start_ns: int, decision_end_ns: int) -> dict:
        """Pre-commitment metadata discovery without outcome labels."""
        return {
            "decision_start_ns": decision_start_ns,
            "decision_end_ns": decision_end_ns,
            "labels_accessible": self._unlocked,
        }


def verify_plan_matches_commitment(
    plan: ValidationPlanV1,
    commitment: HoldoutCommitmentV1,
) -> None:
    mismatches: list[str] = []
    if plan.validation_plan_id != commitment.validation_plan_id:
        mismatches.append("validation_plan_id")
    if plan.candidate_ids != commitment.candidate_ids:
        mismatches.append("candidate_ids")
    if plan.candidate_artifact_hashes != commitment.candidate_artifact_hashes:
        mismatches.append("candidate_artifact_hashes")
    if plan.control_ref != commitment.control_ref:
        mismatches.append("control_ref")
    if plan.primary_metric != commitment.primary_metric:
        mismatches.append("primary_metric")
    if plan.holdout_spec.holdout_start_ns != commitment.holdout_spec.holdout_start_ns:
        mismatches.append("holdout_start_ns")
    if plan.holdout_spec.holdout_end_ns != commitment.holdout_spec.holdout_end_ns:
        mismatches.append("holdout_end_ns")
    if mismatches:
        raise ValidationError("VALIDATION_PLAN_DEVIATION", details={"fields": mismatches})


__all__ = [
    "ValidationDataAccessGuard",
    "verify_plan_matches_commitment",
]
