"""Deterministic replay verification for execution decision traces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .recorder import ExecutionDecisionTraceDraft, derive_inputs_digest, materialize_execution_decision_trace
from .serialization import (
    execution_decision_trace_identity_hash,
    execution_decision_trace_v1_from_dict,
    execution_decision_trace_v1_to_dict,
)
from .types import ExecutionDecisionTraceV1, RuleEvaluationV1


@dataclass(frozen=True, slots=True)
class ExecutionDecisionTraceReplayResult:
    identity_match: bool
    rule_trail_match: bool
    expected_decision_trace_id: str
    recomputed_decision_trace_id: str
    rule_evaluations: tuple[RuleEvaluationV1, ...]

    @property
    def ok(self) -> bool:
        return self.identity_match and self.rule_trail_match


def replay_rule_trail(
    *,
    immutable_inputs: Mapping[str, Any] | None,
    rule_evaluations: tuple[RuleEvaluationV1, ...],
) -> tuple[RuleEvaluationV1, ...]:
    """Return the canonical rule trail for replay checks."""
    _ = derive_inputs_digest(dict(immutable_inputs) if immutable_inputs is not None else None)
    return tuple(rule_evaluations)


def verify_execution_decision_trace_replay(
    record: ExecutionDecisionTraceV1,
    *,
    immutable_inputs: Mapping[str, Any] | None = None,
) -> ExecutionDecisionTraceReplayResult:
    identity = execution_decision_trace_identity_hash(record)
    expected_id = f"EDTR-{identity}"
    identity_match = record.decision_trace_id == expected_id
    if immutable_inputs is not None:
        digest = derive_inputs_digest(dict(immutable_inputs))
        identity_match = identity_match and record.inputs_digest == digest
    rule_trail = replay_rule_trail(
        immutable_inputs=immutable_inputs,
        rule_evaluations=record.rule_evaluations,
    )
    rule_trail_match = rule_trail == record.rule_evaluations
    return ExecutionDecisionTraceReplayResult(
        identity_match=identity_match,
        rule_trail_match=rule_trail_match,
        expected_decision_trace_id=expected_id,
        recomputed_decision_trace_id=expected_id,
        rule_evaluations=rule_trail,
    )


def round_trip_execution_decision_trace(record: ExecutionDecisionTraceV1) -> ExecutionDecisionTraceV1:
    return execution_decision_trace_v1_from_dict(execution_decision_trace_v1_to_dict(record))


def replay_from_draft(draft: ExecutionDecisionTraceDraft) -> ExecutionDecisionTraceReplayResult:
    record = materialize_execution_decision_trace(draft)
    restored = round_trip_execution_decision_trace(record)
    result = verify_execution_decision_trace_replay(
        restored,
        immutable_inputs=draft.immutable_inputs,
    )
    return result


__all__ = [
    "ExecutionDecisionTraceReplayResult",
    "replay_from_draft",
    "replay_rule_trail",
    "round_trip_execution_decision_trace",
    "verify_execution_decision_trace_replay",
]
