"""SQLite-backed execution decision trace store (package-local DDL on open)."""

from __future__ import annotations

import json
from typing import Any

from ...intelligence.persistence.codec import canonical_semantic_equal
from ...intelligence.persistence.errors import RepositoryConflictError
from ...intelligence.persistence.repository import RepositoryPutResult
from ...local_state.connection import LocalStateConnection
from .serialization import execution_decision_trace_v1_from_dict, execution_decision_trace_v1_to_dict
from .types import ExecutionDecisionTraceV1

_CREATE_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS execution_decision_traces (
        decision_trace_id TEXT PRIMARY KEY,
        opportunity_id TEXT,
        decision_time_ns INTEGER NOT NULL,
        decision_kind TEXT NOT NULL,
        trace_json TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_execution_decision_traces_opportunity
    ON execution_decision_traces(opportunity_id, decision_time_ns)
    """,
)

_DDL_INITIALIZED: set[int] = set()


def ensure_execution_decision_trace_schema(connection: LocalStateConnection) -> None:
    key = id(connection)
    if key in _DDL_INITIALIZED:
        return
    for statement in _CREATE_STATEMENTS:
        connection.execute(statement)
    _DDL_INITIALIZED.add(key)


def reset_execution_decision_trace_schema_tracking_for_tests() -> None:
    _DDL_INITIALIZED.clear()


class SqliteExecutionDecisionTraceRepository:
    """Append-only trace persistence on the canonical local_state connection."""

    def __init__(self, connection: LocalStateConnection) -> None:
        self._connection = connection
        ensure_execution_decision_trace_schema(connection)

    def _run_write(self, callback):
        if self._connection.in_transaction:
            return callback()
        with self._connection.transaction():
            return callback()

    def put_execution_decision_trace(self, record: ExecutionDecisionTraceV1) -> RepositoryPutResult:
        document = execution_decision_trace_v1_to_dict(record)
        record_id = str(record.decision_trace_id)
        payload = json.dumps(document, sort_keys=True, separators=(",", ":"))

        def _write() -> RepositoryPutResult:
            row = self._connection.execute(
                "SELECT trace_json FROM execution_decision_traces WHERE decision_trace_id = ?",
                (record_id,),
            ).fetchone()
            if row is not None:
                prior = json.loads(str(row["trace_json"]))
                if canonical_semantic_equal(prior, document):
                    return RepositoryPutResult.ALREADY_PRESENT
                raise RepositoryConflictError(
                    "IMMUTABLE_CONFLICT:execution_decision_trace:" + record_id,
                    details={"kind": "execution_decision_trace", "id": record_id},
                )
            self._connection.execute(
                """
                INSERT INTO execution_decision_traces(
                    decision_trace_id, opportunity_id, decision_time_ns, decision_kind, trace_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    record.opportunity_id,
                    int(record.decision_time_ns),
                    str(record.decision_kind),
                    payload,
                ),
            )
            return RepositoryPutResult.INSERTED

        return self._run_write(_write)

    def get_execution_decision_trace(self, decision_trace_id: str) -> ExecutionDecisionTraceV1 | None:
        row = self._connection.execute(
            "SELECT trace_json FROM execution_decision_traces WHERE decision_trace_id = ?",
            (str(decision_trace_id),),
        ).fetchone()
        if row is None:
            return None
        return execution_decision_trace_v1_from_dict(json.loads(str(row["trace_json"])))

    def list_execution_decision_traces_by_opportunity(
        self,
        opportunity_id: str,
    ) -> tuple[ExecutionDecisionTraceV1, ...]:
        target = str(opportunity_id)
        rows = self._connection.execute(
            """
            SELECT trace_json FROM execution_decision_traces
            WHERE opportunity_id = ?
            ORDER BY decision_time_ns ASC, decision_trace_id ASC
            """,
            (target,),
        ).fetchall()
        records: list[ExecutionDecisionTraceV1] = []
        for row in rows:
            records.append(execution_decision_trace_v1_from_dict(json.loads(str(row["trace_json"]))))
        return tuple(records)


__all__ = [
    "SqliteExecutionDecisionTraceRepository",
    "ensure_execution_decision_trace_schema",
    "reset_execution_decision_trace_schema_tracking_for_tests",
]
