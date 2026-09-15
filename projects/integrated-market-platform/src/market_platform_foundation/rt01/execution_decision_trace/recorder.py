"""Record immutable execution decision traces without mutating authority."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from ...intelligence.contracts.common import INTELLIGENCE_SCHEMA_VERSION, ContractReference
from ...intelligence.execution.types import RiskDecisionKind
from ...intelligence.opportunity.lifecycle import OperatorLifecycleState
from .serialization import execution_decision_trace_identity_hash
from .types import (
    EXECUTION_DECISION_TRACE_IMPLEMENTATION_VERSION,
    EXECUTION_DECISION_TRACE_SCHEMA_ID,
    EligibilityDecisionSnapshot,
    ExecutionDecisionKind,
    ExecutionDecisionTraceV1,
    PreviewDecisionSnapshot,
    RuleEvaluationV1,
    operator_action_for_kind,
)


@dataclass(frozen=True, slots=True)
class ExecutionDecisionTraceDraft:
    opportunity_id: str | None
    decision_time_ns: int
    mode: str
    decision_kind: ExecutionDecisionKind
    eligibility: EligibilityDecisionSnapshot
    risk_decision_kind: RiskDecisionKind | None = None
    risk_decision_ref: ContractReference | None = None
    provider_state: dict[str, Any] | None = None
    market_data_freshness: dict[str, Any] | None = None
    preview: PreviewDecisionSnapshot | None = None
    operator_action: OperatorLifecycleState | None = None
    rule_evaluations: tuple[RuleEvaluationV1, ...] = ()
    blocker_codes: tuple[str, ...] = ()
    execution_outcome_refs: tuple[ContractReference, ...] = ()
    runtime_version: str = EXECUTION_DECISION_TRACE_IMPLEMENTATION_VERSION
    config_version_refs: tuple[str, ...] = ()
    correlation_id: str | None = None
    trace_id: str | None = None
    review_id: str | None = None
    immutable_inputs: dict[str, Any] | None = None


def derive_inputs_digest(immutable_inputs: dict[str, Any] | None) -> str | None:
    if not immutable_inputs:
        return None
    return sha256_bytes(canonical_bytes(dict(immutable_inputs)))


def materialize_execution_decision_trace(draft: ExecutionDecisionTraceDraft) -> ExecutionDecisionTraceV1:
    kind = ExecutionDecisionKind(str(draft.decision_kind))
    operator_action = draft.operator_action
    if operator_action is None:
        operator_action = operator_action_for_kind(kind)
    inputs_digest = derive_inputs_digest(draft.immutable_inputs)
    pending = ExecutionDecisionTraceV1(
        decision_trace_id="EDTR-PENDING",
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        contract_schema_id=EXECUTION_DECISION_TRACE_SCHEMA_ID,
        opportunity_id=draft.opportunity_id,
        decision_time_ns=draft.decision_time_ns,
        mode=draft.mode,
        decision_kind=kind,
        eligibility=draft.eligibility,
        risk_decision_kind=draft.risk_decision_kind,
        risk_decision_ref=draft.risk_decision_ref,
        provider_state=dict(draft.provider_state or {}),
        market_data_freshness=dict(draft.market_data_freshness or {}),
        preview=draft.preview,
        operator_action=operator_action,
        rule_evaluations=tuple(draft.rule_evaluations),
        blocker_codes=tuple(draft.blocker_codes),
        execution_outcome_refs=tuple(draft.execution_outcome_refs),
        runtime_version=draft.runtime_version,
        config_version_refs=tuple(draft.config_version_refs),
        correlation_id=draft.correlation_id,
        trace_id=draft.trace_id,
        review_id=draft.review_id,
        inputs_digest=inputs_digest,
    )
    identity = execution_decision_trace_identity_hash(pending)
    return ExecutionDecisionTraceV1(
        decision_trace_id=f"EDTR-{identity}",
        schema_version=pending.schema_version,
        contract_schema_id=pending.contract_schema_id,
        opportunity_id=pending.opportunity_id,
        decision_time_ns=pending.decision_time_ns,
        mode=pending.mode,
        decision_kind=pending.decision_kind,
        eligibility=pending.eligibility,
        risk_decision_kind=pending.risk_decision_kind,
        risk_decision_ref=pending.risk_decision_ref,
        provider_state=pending.provider_state,
        market_data_freshness=pending.market_data_freshness,
        preview=pending.preview,
        operator_action=pending.operator_action,
        rule_evaluations=pending.rule_evaluations,
        blocker_codes=pending.blocker_codes,
        execution_outcome_refs=pending.execution_outcome_refs,
        runtime_version=pending.runtime_version,
        config_version_refs=pending.config_version_refs,
        correlation_id=pending.correlation_id,
        trace_id=pending.trace_id,
        review_id=pending.review_id,
        inputs_digest=pending.inputs_digest,
    )


__all__ = [
    "ExecutionDecisionTraceDraft",
    "derive_inputs_digest",
    "materialize_execution_decision_trace",
]
