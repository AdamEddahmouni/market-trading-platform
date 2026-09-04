"""Execution integrity and forward lineage (BUILD 27)."""

from __future__ import annotations

from .types import ExecutionIntegrityFailureCode, ExecutionIntegrityStatus, PaperEvidenceClass


def validate_forward_lineage(
    *,
    evidence_class: PaperEvidenceClass,
    forward_receipt_ref: str | None,
    forecast_id: str | None,
) -> tuple[ExecutionIntegrityStatus, tuple[str, ...]]:
    if evidence_class == PaperEvidenceClass.REPLAY_PAPER:
        return ExecutionIntegrityStatus.INVALID, (
            ExecutionIntegrityFailureCode.REPLAY_MASQUERADING_AS_FORWARD.value,
        )
    if evidence_class == PaperEvidenceClass.COUNTERFACTUAL_PAPER:
        return ExecutionIntegrityStatus.INVALID, (
            ExecutionIntegrityFailureCode.COUNTERFACTUAL_MASQUERADING_AS_FORWARD.value,
        )
    if not forward_receipt_ref or not forecast_id:
        return ExecutionIntegrityStatus.INVALID, (ExecutionIntegrityFailureCode.NO_FORWARD_LINEAGE.value,)
    return ExecutionIntegrityStatus.VALID, ()


def validate_opportunity_not_expired(
    *,
    decision_time_ns: int,
    valid_until_ns: int | None,
) -> tuple[bool, tuple[str, ...]]:
    if valid_until_ns is not None and decision_time_ns >= valid_until_ns:
        return False, (ExecutionIntegrityFailureCode.EXPIRED_OPPORTUNITY_ORDER.value,)
    return True, ()


def detect_run_freeze_violation(
    *,
    initial_opportunity_policy_ref: str,
    current_opportunity_policy_ref: str,
    initial_execution_policy_ref: str,
    current_execution_policy_ref: str,
) -> str | None:
    if initial_opportunity_policy_ref != current_opportunity_policy_ref:
        return ExecutionIntegrityFailureCode.POLICY_CHANGED_MID_RUN.value
    if initial_execution_policy_ref != current_execution_policy_ref:
        return ExecutionIntegrityFailureCode.POLICY_CHANGED_MID_RUN.value
    return None
