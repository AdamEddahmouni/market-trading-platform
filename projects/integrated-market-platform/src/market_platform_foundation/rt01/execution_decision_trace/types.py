"""Immutable execution/operator decision flight-recorder contracts (Phase 4 Lane J)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ...intelligence.contracts.common import (
    INTELLIGENCE_SCHEMA_VERSION,
    ContractReference,
    contract_reference_from_dict,
    contract_reference_to_dict,
    reject_unknown_keys,
    validate_id,
    validate_schema_version,
    validate_timestamp_ns,
)
from ...intelligence.execution.types import RiskDecisionKind
from ...intelligence.opportunity.lifecycle import OperatorLifecycleState
from ...intelligence.opportunity.types import AssessmentAction

EXECUTION_DECISION_TRACE_SCHEMA_ID = "rt01/execution-decision-trace/1.0.0"
EXECUTION_DECISION_TRACE_IMPLEMENTATION_VERSION = "execution-decision-trace-v1"


class ExecutionDecisionKind(StrEnum):
    """Point-in-time decision event — observability only; no authority."""

    SURFACE = "SURFACE"
    WATCH = "WATCH"
    DISMISS = "DISMISS"
    PREVIEW_ALLOWED = "PREVIEW_ALLOWED"
    REVALIDATION_REQUIRED = "REVALIDATION_REQUIRED"
    PAPER_BLOCKED = "PAPER_BLOCKED"
    PAPER_REQUESTED = "PAPER_REQUESTED"
    BROKER_ACCEPTED = "BROKER_ACCEPTED"


class RuleEvaluationOutcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"
    UNKNOWN = "UNKNOWN"


_OPERATOR_ACTION_BY_KIND: dict[ExecutionDecisionKind, OperatorLifecycleState | None] = {
    ExecutionDecisionKind.SURFACE: None,
    ExecutionDecisionKind.WATCH: OperatorLifecycleState.WATCHED,
    ExecutionDecisionKind.DISMISS: OperatorLifecycleState.DISMISSED,
    ExecutionDecisionKind.PREVIEW_ALLOWED: OperatorLifecycleState.PAPER_PREVIEWED,
    ExecutionDecisionKind.REVALIDATION_REQUIRED: None,
    ExecutionDecisionKind.PAPER_BLOCKED: None,
    ExecutionDecisionKind.PAPER_REQUESTED: None,
    ExecutionDecisionKind.BROKER_ACCEPTED: None,
}


def operator_action_for_kind(kind: ExecutionDecisionKind | str) -> OperatorLifecycleState | None:
    return _OPERATOR_ACTION_BY_KIND.get(ExecutionDecisionKind(str(kind)))


@dataclass(frozen=True, slots=True)
class EligibilityDecisionSnapshot:
    assessment_action: AssessmentAction | None = None
    lifecycle_state: OperatorLifecycleState | None = None
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.assessment_action is not None:
            AssessmentAction(str(self.assessment_action))
        if self.lifecycle_state is not None:
            OperatorLifecycleState(str(self.lifecycle_state))


@dataclass(frozen=True, slots=True)
class PreviewDecisionSnapshot:
    status: str
    preview_id: str | None = None
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        normalized = str(self.status).strip().upper()
        if not normalized:
            raise ValueError("PREVIEW_DECISION_STATUS_REQUIRED")
        object.__setattr__(self, "status", normalized)
        if self.preview_id is not None:
            validate_id(self.preview_id, field_name="preview_id")


@dataclass(frozen=True, slots=True)
class RuleEvaluationV1:
    rule_id: str
    outcome: RuleEvaluationOutcome
    reason_codes: tuple[str, ...] = ()
    evidence_refs: tuple[ContractReference, ...] = ()

    def __post_init__(self) -> None:
        if not str(self.rule_id).strip():
            raise ValueError("RULE_ID_REQUIRED")
        RuleEvaluationOutcome(str(self.outcome))


@dataclass(frozen=True, slots=True)
class ExecutionDecisionTraceV1:
    decision_trace_id: str
    schema_version: str
    contract_schema_id: str
    opportunity_id: str | None
    decision_time_ns: int
    mode: str
    decision_kind: ExecutionDecisionKind
    eligibility: EligibilityDecisionSnapshot
    risk_decision_kind: RiskDecisionKind | None
    risk_decision_ref: ContractReference | None
    provider_state: dict[str, Any]
    market_data_freshness: dict[str, Any]
    preview: PreviewDecisionSnapshot | None
    operator_action: OperatorLifecycleState | None
    rule_evaluations: tuple[RuleEvaluationV1, ...]
    blocker_codes: tuple[str, ...]
    execution_outcome_refs: tuple[ContractReference, ...]
    runtime_version: str
    config_version_refs: tuple[str, ...]
    correlation_id: str | None = None
    trace_id: str | None = None
    review_id: str | None = None
    inputs_digest: str | None = None

    def __post_init__(self) -> None:
        validate_schema_version(self.schema_version)
        if self.contract_schema_id != EXECUTION_DECISION_TRACE_SCHEMA_ID:
            raise ValueError("CONTRACT_SCHEMA_ID_MISMATCH")
        validate_id(self.decision_trace_id, field_name="decision_trace_id")
        validate_timestamp_ns(self.decision_time_ns, field_name="decision_time_ns")
        if self.opportunity_id is not None:
            validate_id(self.opportunity_id, field_name="opportunity_id")
        normalized_mode = str(self.mode).strip().upper()
        if not normalized_mode:
            raise ValueError("MODE_REQUIRED")
        object.__setattr__(self, "mode", normalized_mode)
        ExecutionDecisionKind(str(self.decision_kind))
        if self.risk_decision_kind is not None:
            RiskDecisionKind(str(self.risk_decision_kind))
        if self.operator_action is not None:
            OperatorLifecycleState(str(self.operator_action))
        if self.correlation_id is not None:
            validate_id(self.correlation_id, field_name="correlation_id")
        if self.trace_id is not None:
            validate_id(self.trace_id, field_name="trace_id")
        if self.review_id is not None:
            validate_id(self.review_id, field_name="review_id")
        if not str(self.runtime_version).strip():
            raise ValueError("RUNTIME_VERSION_REQUIRED")
        expected_operator = _OPERATOR_ACTION_BY_KIND.get(
            ExecutionDecisionKind(str(self.decision_kind))
        )
        if expected_operator is not None and self.operator_action != expected_operator:
            raise ValueError("OPERATOR_ACTION_KIND_MISMATCH")


def eligibility_snapshot_to_dict(snapshot: EligibilityDecisionSnapshot) -> dict[str, Any]:
    body: dict[str, Any] = {
        "reason_codes": list(snapshot.reason_codes),
    }
    if snapshot.assessment_action is not None:
        body["assessment_action"] = AssessmentAction(snapshot.assessment_action).value
    if snapshot.lifecycle_state is not None:
        body["lifecycle_state"] = OperatorLifecycleState(snapshot.lifecycle_state).value
    return body


def eligibility_snapshot_from_dict(payload: Mapping[str, Any]) -> EligibilityDecisionSnapshot:
    reject_unknown_keys(payload, allowed={"assessment_action", "lifecycle_state", "reason_codes"})
    action = payload.get("assessment_action")
    lifecycle = payload.get("lifecycle_state")
    return EligibilityDecisionSnapshot(
        assessment_action=AssessmentAction(str(action)) if action is not None else None,
        lifecycle_state=OperatorLifecycleState(str(lifecycle)) if lifecycle is not None else None,
        reason_codes=tuple(str(code) for code in (payload.get("reason_codes") or ())),
    )


def preview_snapshot_to_dict(snapshot: PreviewDecisionSnapshot) -> dict[str, Any]:
    body: dict[str, Any] = {
        "status": snapshot.status,
        "reason_codes": list(snapshot.reason_codes),
    }
    if snapshot.preview_id is not None:
        body["preview_id"] = snapshot.preview_id
    return body


def preview_snapshot_from_dict(payload: Mapping[str, Any] | None) -> PreviewDecisionSnapshot | None:
    if payload is None:
        return None
    reject_unknown_keys(payload, allowed={"status", "preview_id", "reason_codes"})
    return PreviewDecisionSnapshot(
        status=str(payload["status"]),
        preview_id=str(payload["preview_id"]) if payload.get("preview_id") is not None else None,
        reason_codes=tuple(str(code) for code in (payload.get("reason_codes") or ())),
    )


def rule_evaluation_to_dict(evaluation: RuleEvaluationV1) -> dict[str, Any]:
    return {
        "rule_id": evaluation.rule_id,
        "outcome": RuleEvaluationOutcome(evaluation.outcome).value,
        "reason_codes": list(evaluation.reason_codes),
        "evidence_refs": [contract_reference_to_dict(ref) for ref in evaluation.evidence_refs],
    }


def rule_evaluation_from_dict(payload: Mapping[str, Any]) -> RuleEvaluationV1:
    reject_unknown_keys(
        payload,
        allowed={"rule_id", "outcome", "reason_codes", "evidence_refs"},
    )
    refs = tuple(
        contract_reference_from_dict(item)
        for item in (payload.get("evidence_refs") or ())
    )
    return RuleEvaluationV1(
        rule_id=str(payload["rule_id"]),
        outcome=RuleEvaluationOutcome(str(payload["outcome"])),
        reason_codes=tuple(str(code) for code in (payload.get("reason_codes") or ())),
        evidence_refs=refs,
    )


__all__ = [
    "EXECUTION_DECISION_TRACE_IMPLEMENTATION_VERSION",
    "EXECUTION_DECISION_TRACE_SCHEMA_ID",
    "EligibilityDecisionSnapshot",
    "ExecutionDecisionKind",
    "ExecutionDecisionTraceV1",
    "PreviewDecisionSnapshot",
    "RuleEvaluationOutcome",
    "RuleEvaluationV1",
    "operator_action_for_kind",
    "eligibility_snapshot_from_dict",
    "eligibility_snapshot_to_dict",
    "preview_snapshot_from_dict",
    "preview_snapshot_to_dict",
    "rule_evaluation_from_dict",
    "rule_evaluation_to_dict",
]
