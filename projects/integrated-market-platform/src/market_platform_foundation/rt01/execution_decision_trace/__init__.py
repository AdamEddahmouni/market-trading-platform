"""Execution decision trace flight recorder (Phase 4 Lane J foundation)."""

from __future__ import annotations

from .recorder import ExecutionDecisionTraceDraft, derive_inputs_digest, materialize_execution_decision_trace
from .replay import (
    ExecutionDecisionTraceReplayResult,
    replay_from_draft,
    replay_rule_trail,
    round_trip_execution_decision_trace,
    verify_execution_decision_trace_replay,
)
from .repository import ExecutionDecisionTraceRepository, InMemoryExecutionDecisionTraceRepository
from .serialization import (
    execution_decision_trace_identity_hash,
    execution_decision_trace_v1_from_dict,
    execution_decision_trace_v1_to_dict,
)
from .types import (
    EXECUTION_DECISION_TRACE_IMPLEMENTATION_VERSION,
    EXECUTION_DECISION_TRACE_SCHEMA_ID,
    EligibilityDecisionSnapshot,
    ExecutionDecisionKind,
    ExecutionDecisionTraceV1,
    PreviewDecisionSnapshot,
    RuleEvaluationOutcome,
    RuleEvaluationV1,
    operator_action_for_kind,
)

__all__ = [
    "EXECUTION_DECISION_TRACE_IMPLEMENTATION_VERSION",
    "EXECUTION_DECISION_TRACE_SCHEMA_ID",
    "EligibilityDecisionSnapshot",
    "ExecutionDecisionKind",
    "ExecutionDecisionTraceDraft",
    "ExecutionDecisionTraceReplayResult",
    "ExecutionDecisionTraceRepository",
    "ExecutionDecisionTraceV1",
    "InMemoryExecutionDecisionTraceRepository",
    "PreviewDecisionSnapshot",
    "RuleEvaluationOutcome",
    "RuleEvaluationV1",
    "derive_inputs_digest",
    "execution_decision_trace_identity_hash",
    "execution_decision_trace_v1_from_dict",
    "execution_decision_trace_v1_to_dict",
    "materialize_execution_decision_trace",
    "operator_action_for_kind",
    "replay_from_draft",
    "replay_rule_trail",
    "round_trip_execution_decision_trace",
    "verify_execution_decision_trace_replay",
]
