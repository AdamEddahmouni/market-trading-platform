"""Canonical serialization for execution decision traces."""

from __future__ import annotations

from typing import Any, Mapping

from ...canonical import canonical_bytes, sha256_bytes
from ...intelligence.contracts.common import (
    INTELLIGENCE_SCHEMA_VERSION,
    contract_reference_from_dict,
    contract_reference_to_dict,
    dataclass_field_names,
    reject_unknown_keys,
)
from .types import (
    EXECUTION_DECISION_TRACE_SCHEMA_ID,
    ExecutionDecisionKind,
    ExecutionDecisionTraceV1,
    eligibility_snapshot_from_dict,
    eligibility_snapshot_to_dict,
    preview_snapshot_from_dict,
    preview_snapshot_to_dict,
    rule_evaluation_from_dict,
    rule_evaluation_to_dict,
)
from ...intelligence.execution.types import RiskDecisionKind
from ...intelligence.opportunity.lifecycle import OperatorLifecycleState


def _trace_body(record: ExecutionDecisionTraceV1, *, include_id: bool) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema_version": record.schema_version,
        "contract_schema_id": record.contract_schema_id,
        "opportunity_id": record.opportunity_id,
        "decision_time_ns": record.decision_time_ns,
        "mode": record.mode,
        "decision_kind": ExecutionDecisionKind(record.decision_kind).value,
        "eligibility": eligibility_snapshot_to_dict(record.eligibility),
        "risk_decision_kind": (
            RiskDecisionKind(record.risk_decision_kind).value
            if record.risk_decision_kind is not None
            else None
        ),
        "risk_decision_ref": (
            contract_reference_to_dict(record.risk_decision_ref)
            if record.risk_decision_ref is not None
            else None
        ),
        "provider_state": dict(record.provider_state),
        "market_data_freshness": dict(record.market_data_freshness),
        "preview": (
            preview_snapshot_to_dict(record.preview)
            if record.preview is not None
            else None
        ),
        "operator_action": (
            OperatorLifecycleState(record.operator_action).value
            if record.operator_action is not None
            else None
        ),
        "rule_evaluations": [rule_evaluation_to_dict(item) for item in record.rule_evaluations],
        "blocker_codes": list(record.blocker_codes),
        "execution_outcome_refs": [
            contract_reference_to_dict(ref) for ref in record.execution_outcome_refs
        ],
        "runtime_version": record.runtime_version,
        "config_version_refs": list(record.config_version_refs),
        "correlation_id": record.correlation_id,
        "trace_id": record.trace_id,
        "review_id": record.review_id,
        "inputs_digest": record.inputs_digest,
    }
    if include_id:
        body["decision_trace_id"] = record.decision_trace_id
    return body


def execution_decision_trace_identity_hash(record: ExecutionDecisionTraceV1) -> str:
    return sha256_bytes(canonical_bytes(_trace_body(record, include_id=False)))


def execution_decision_trace_v1_to_dict(record: ExecutionDecisionTraceV1) -> dict[str, Any]:
    body = _trace_body(record, include_id=True)
    body["identity_hash"] = execution_decision_trace_identity_hash(record)
    return body


def execution_decision_trace_v1_from_dict(payload: Mapping[str, Any]) -> ExecutionDecisionTraceV1:
    reject_unknown_keys(
        payload,
        allowed=set(dataclass_field_names(ExecutionDecisionTraceV1)) | {"identity_hash"},
    )
    risk_kind = payload.get("risk_decision_kind")
    risk_ref = payload.get("risk_decision_ref")
    operator_action = payload.get("operator_action")
    record = ExecutionDecisionTraceV1(
        decision_trace_id=str(payload["decision_trace_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        contract_schema_id=str(
            payload.get("contract_schema_id", EXECUTION_DECISION_TRACE_SCHEMA_ID)
        ),
        opportunity_id=(
            str(payload["opportunity_id"]) if payload.get("opportunity_id") is not None else None
        ),
        decision_time_ns=int(payload["decision_time_ns"]),
        mode=str(payload["mode"]),
        decision_kind=ExecutionDecisionKind(str(payload["decision_kind"])),
        eligibility=eligibility_snapshot_from_dict(payload["eligibility"]),
        risk_decision_kind=RiskDecisionKind(str(risk_kind)) if risk_kind is not None else None,
        risk_decision_ref=(
            contract_reference_from_dict(risk_ref) if risk_ref is not None else None
        ),
        provider_state=dict(payload.get("provider_state") or {}),
        market_data_freshness=dict(payload.get("market_data_freshness") or {}),
        preview=preview_snapshot_from_dict(payload.get("preview")),
        operator_action=(
            OperatorLifecycleState(str(operator_action)) if operator_action is not None else None
        ),
        rule_evaluations=tuple(
            rule_evaluation_from_dict(item) for item in (payload.get("rule_evaluations") or ())
        ),
        blocker_codes=tuple(str(code) for code in (payload.get("blocker_codes") or ())),
        execution_outcome_refs=tuple(
            contract_reference_from_dict(item)
            for item in (payload.get("execution_outcome_refs") or ())
        ),
        runtime_version=str(payload["runtime_version"]),
        config_version_refs=tuple(str(item) for item in (payload.get("config_version_refs") or ())),
        correlation_id=(
            str(payload["correlation_id"]) if payload.get("correlation_id") is not None else None
        ),
        trace_id=str(payload["trace_id"]) if payload.get("trace_id") is not None else None,
        review_id=str(payload["review_id"]) if payload.get("review_id") is not None else None,
        inputs_digest=(
            str(payload["inputs_digest"]) if payload.get("inputs_digest") is not None else None
        ),
    )
    serialized_hash = payload.get("identity_hash")
    if serialized_hash is not None and serialized_hash != execution_decision_trace_identity_hash(record):
        raise ValueError("EXECUTION_DECISION_TRACE_IDENTITY_MISMATCH")
    return record


__all__ = [
    "execution_decision_trace_identity_hash",
    "execution_decision_trace_v1_from_dict",
    "execution_decision_trace_v1_to_dict",
]
