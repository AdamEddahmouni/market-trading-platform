"""OF-01 run/attempt lifecycle and relationship validation."""

from __future__ import annotations

import sqlite3
from typing import Iterable

from .commands import (
    AppendAttemptTransition,
    AppendDisposition,
    AppendRunTransition,
    CloseRun,
    LedgerCommand,
    RegisterAttempt,
    RegisterRun,
)
from .errors import OF01Error, OF01ErrorCode
from .records import (
    AttemptConcurrency,
    AttemptPhase,
    RelationType,
    RunState,
    TerminalResult,
)

VALID_RUN_TRANSITIONS: dict[str | None, frozenset[str]] = {
    None: frozenset({RunState.REGISTERED.value}),
    RunState.REGISTERED.value: frozenset({RunState.ACTIVE.value}),
    RunState.ACTIVE.value: frozenset({RunState.SUSPENDED.value, RunState.CLOSED.value}),
    RunState.SUSPENDED.value: frozenset({RunState.ACTIVE.value, RunState.CLOSED.value}),
    RunState.CLOSED.value: frozenset(),
}

VALID_ATTEMPT_TRANSITIONS: dict[str | None, frozenset[str]] = {
    None: frozenset({AttemptPhase.PENDING.value}),
    AttemptPhase.PENDING.value: frozenset(
        {AttemptPhase.RUNNING.value, AttemptPhase.TERMINAL.value}
    ),
    AttemptPhase.RUNNING.value: frozenset({AttemptPhase.TERMINAL.value}),
    AttemptPhase.TERMINAL.value: frozenset(),
}

RELATION_ENDPOINTS: dict[str, tuple[frozenset[str], frozenset[str], bool]] = {
    RelationType.PARENT_OF.value: (frozenset({"RUN"}), frozenset({"RUN"}), True),
    RelationType.TRIGGERED_BY.value: (frozenset({"RUN"}), frozenset({"RUN"}), True),
    RelationType.RESUMES_FROM.value: (
        frozenset({"RUN", "ATTEMPT"}),
        frozenset({"RUN", "ATTEMPT"}),
        True,
    ),
    RelationType.SUPERSEDES.value: (
        frozenset({"RUN", "OUTCOME", "DISPOSITION", "ARTIFACT"}),
        frozenset({"RUN", "OUTCOME", "DISPOSITION", "ARTIFACT"}),
        True,
    ),
    RelationType.PRODUCES_ARTIFACT.value: (
        frozenset({"RUN", "ATTEMPT"}),
        frozenset({"ARTIFACT"}),
        True,
    ),
    RelationType.CONSUMES_ARTIFACT.value: (
        frozenset({"RUN", "ATTEMPT"}),
        frozenset({"ARTIFACT"}),
        True,
    ),
    RelationType.HAS_ARTIFACT.value: (
        frozenset({"OUTCOME", "DISPOSITION"}),
        frozenset({"ARTIFACT"}),
        True,
    ),
    RelationType.CORRECTS.value: (
        frozenset({"OUTCOME", "DISPOSITION"}),
        frozenset({"OUTCOME", "DISPOSITION"}),
        True,
    ),
    RelationType.RELATED_TO.value: (
        frozenset(
            {
                "RUN",
                "ATTEMPT",
                "OUTCOME",
                "DISPOSITION",
                "ARTIFACT",
                "SOURCE_ATTRIBUTION",
                "PROVENANCE_REFERENCE",
            }
        ),
        frozenset(
            {
                "RUN",
                "ATTEMPT",
                "OUTCOME",
                "DISPOSITION",
                "ARTIFACT",
                "SOURCE_ATTRIBUTION",
                "PROVENANCE_REFERENCE",
            }
        ),
        False,
    ),
}

ZERO_ATTEMPT_CLOSE_ACTIONS = frozenset({"CANCEL", "ABANDON", "SUPERSEDE"})


def validate_run_transition(
    *,
    current_state: str | None,
    from_state: str | None,
    to_state: str,
) -> None:
    if current_state == RunState.CLOSED.value:
        raise OF01Error(
            OF01ErrorCode.INVALID_TRANSITION,
            "run is already CLOSED",
            {"current_state": current_state},
        )
    allowed = VALID_RUN_TRANSITIONS.get(current_state, frozenset())
    if to_state not in allowed:
        raise OF01Error(
            OF01ErrorCode.INVALID_TRANSITION,
            "invalid run transition",
            {"from_state": current_state, "to_state": to_state},
        )
    if from_state is not None and current_state is not None and from_state != current_state:
        raise OF01Error(
            OF01ErrorCode.PRECONDITION_CHANGED,
            "run from_state does not match current state",
            {"expected": current_state, "actual": from_state},
        )


def validate_attempt_transition(
    *,
    current_phase: str | None,
    from_phase: str | None,
    to_phase: str,
    terminal_result: str | None = None,
) -> None:
    if current_phase == AttemptPhase.TERMINAL.value:
        raise OF01Error(
            OF01ErrorCode.INVALID_TRANSITION,
            "attempt is already TERMINAL",
            {"current_phase": current_phase},
        )
    allowed = VALID_ATTEMPT_TRANSITIONS.get(current_phase, frozenset())
    if to_phase not in allowed:
        raise OF01Error(
            OF01ErrorCode.INVALID_TRANSITION,
            "invalid attempt transition",
            {"from_phase": current_phase, "to_phase": to_phase},
        )
    if from_phase is not None and current_phase is not None and from_phase != current_phase:
        raise OF01Error(
            OF01ErrorCode.PRECONDITION_CHANGED,
            "attempt from_phase does not match current phase",
            {"expected": current_phase, "actual": from_phase},
        )
    if to_phase == AttemptPhase.TERMINAL.value and terminal_result == TerminalResult.NOT_STARTED.value:
        if current_phase not in (None, AttemptPhase.PENDING.value):
            raise OF01Error(
                OF01ErrorCode.INVALID_TRANSITION,
                "NOT_STARTED only from PENDING",
                {},
            )


def validate_relationship(
    *,
    relation_type: str,
    source_record_type: str,
    target_record_type: str,
) -> None:
    spec = RELATION_ENDPOINTS.get(relation_type)
    if spec is None:
        raise OF01Error(
            OF01ErrorCode.INVALID_COMMAND,
            "unknown relation type",
            {"relation_type": relation_type},
        )
    allowed_sources, allowed_targets, _ = spec
    if source_record_type not in allowed_sources:
        raise OF01Error(
            OF01ErrorCode.INVALID_COMMAND,
            "invalid relationship source type",
            {"relation_type": relation_type, "source_record_type": source_record_type},
        )
    if target_record_type not in allowed_targets:
        raise OF01Error(
            OF01ErrorCode.INVALID_COMMAND,
            "invalid relationship target type",
            {"relation_type": relation_type, "target_record_type": target_record_type},
        )


def validate_command_preconditions(
    conn: sqlite3.Connection,
    command: LedgerCommand,
    *,
    get_run_state,
    get_latest_run_transition_id,
    get_attempt_phase,
    count_nonterminal_attempts,
    record_exists,
    get_run_concurrency=None,
) -> None:
    if isinstance(command, RegisterRun):
        if command.initial_transition.to_state != RunState.REGISTERED:
            raise OF01Error(
                OF01ErrorCode.INVALID_TRANSITION,
                "initial run transition must be REGISTERED",
                {},
            )
        if command.initial_transition.predecessor_transition_id is not None:
            raise OF01Error(
                OF01ErrorCode.INVALID_COMMAND,
                "initial transition must have null predecessor",
                {},
            )
        if record_exists(conn, "RUN", command.run.run_id):
            raise OF01Error(
                OF01ErrorCode.DOMAIN_ID_CONFLICT,
                "run_id already exists",
                {"run_id": command.run.run_id},
            )
        if (
            command.run.consequence_profile.value.startswith("C2")
            or command.run.consequence_profile.value in {"C3_EVIDENCE_CRITICAL", "C4_AUTHORITY_CRITICAL"}
        ):
            pass
    elif isinstance(command, RegisterAttempt):
        if not record_exists(conn, "RUN", command.attempt.run_id):
            raise OF01Error(
                OF01ErrorCode.MISSING_REFERENCE,
                "run does not exist",
                {"run_id": command.attempt.run_id},
            )
        run_state = get_run_state(conn, command.attempt.run_id)
        if run_state == RunState.CLOSED.value:
            raise OF01Error(
                OF01ErrorCode.INVALID_TRANSITION,
                "cannot register attempt on CLOSED run",
                {},
            )
        latest_transition = get_latest_run_transition_id(conn, command.attempt.run_id)
        if latest_transition != command.expected_run_transition_id:
            raise OF01Error(
                OF01ErrorCode.PRECONDITION_CHANGED,
                "expected_run_transition_id mismatch",
                {
                    "expected": command.expected_run_transition_id,
                    "actual": latest_transition,
                },
            )
        if command.initial_transition.to_phase != AttemptPhase.PENDING:
            raise OF01Error(
                OF01ErrorCode.INVALID_TRANSITION,
                "initial attempt transition must be PENDING",
                {},
            )
        if record_exists(conn, "ATTEMPT", command.attempt.attempt_id):
            raise OF01Error(
                OF01ErrorCode.DOMAIN_ID_CONFLICT,
                "attempt_id already exists",
                {"attempt_id": command.attempt.attempt_id},
            )
    elif isinstance(command, AppendRunTransition):
        run_id = command.transition.run_id
        current = get_run_state(conn, run_id)
        latest = get_latest_run_transition_id(conn, run_id)
        if command.expected_predecessor_transition_id != latest:
            raise OF01Error(
                OF01ErrorCode.PRECONDITION_CHANGED,
                "expected_predecessor_transition_id mismatch",
                {
                    "expected": command.expected_predecessor_transition_id,
                    "actual": latest,
                },
            )
        validate_run_transition(
            current_state=current,
            from_state=command.transition.from_state.value if command.transition.from_state else None,
            to_state=command.transition.to_state.value,
        )
    elif isinstance(command, AppendAttemptTransition):
        attempt_id = command.transition.attempt_id
        current = get_attempt_phase(conn, attempt_id)
        validate_attempt_transition(
            current_phase=current,
            from_phase=command.transition.from_phase.value if command.transition.from_phase else None,
            to_phase=command.transition.to_phase.value,
            terminal_result=(
                command.transition.terminal_result.value
                if command.transition.terminal_result
                else None
            ),
        )
    elif isinstance(command, CloseRun):
        run_id = command.terminal_transition.run_id
        current = get_run_state(conn, run_id)
        latest = get_latest_run_transition_id(conn, run_id)
        if command.expected_run_transition_id != latest:
            raise OF01Error(
                OF01ErrorCode.PRECONDITION_CHANGED,
                "expected_run_transition_id mismatch",
                {"expected": command.expected_run_transition_id, "actual": latest},
            )
        validate_run_transition(
            current_state=current,
            from_state=(
                command.terminal_transition.from_state.value
                if command.terminal_transition.from_state
                else None
            ),
            to_state=RunState.CLOSED.value,
        )
        if command.terminal_transition.to_state != RunState.CLOSED:
            raise OF01Error(
                OF01ErrorCode.INVALID_TRANSITION,
                "CloseRun requires CLOSED terminal transition",
                {},
            )
    elif isinstance(command, AppendDisposition):
        if not record_exists(conn, "RUN", command.disposition.run_id):
            raise OF01Error(
                OF01ErrorCode.MISSING_REFERENCE,
                "run does not exist",
                {"run_id": command.disposition.run_id},
            )


def validate_sequential_attempt_capacity(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    attempt_concurrency: str,
    parallel_capacity: int | None,
    expected_parallel_active_count: int | None,
    count_nonterminal_attempts,
) -> None:
    active = count_nonterminal_attempts(conn, run_id)
    if attempt_concurrency == AttemptConcurrency.SEQUENTIAL.value:
        if active >= 1:
            raise OF01Error(
                OF01ErrorCode.PRECONDITION_CHANGED,
                "sequential run permits at most one nonterminal attempt",
                {"active_count": active},
            )
    elif attempt_concurrency == AttemptConcurrency.EXPLICIT_PARALLEL.value:
        if parallel_capacity is None:
            raise OF01Error(
                OF01ErrorCode.INVALID_COMMAND,
                "parallel_capacity required for EXPLICIT_PARALLEL",
                {},
            )
        if expected_parallel_active_count is not None and active != expected_parallel_active_count:
            raise OF01Error(
                OF01ErrorCode.PRECONDITION_CHANGED,
                "parallel active count mismatch",
                {"expected": expected_parallel_active_count, "actual": active},
            )
        if active >= parallel_capacity:
            raise OF01Error(
                OF01ErrorCode.PRECONDITION_CHANGED,
                "parallel capacity exceeded",
                {"active_count": active, "capacity": parallel_capacity},
            )
