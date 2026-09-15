"""Append-only persistence for execution decision traces."""

from __future__ import annotations

import copy
import threading
from typing import Protocol, runtime_checkable

from ...intelligence.persistence.errors import RepositoryConflictError
from ...intelligence.persistence.repository import RepositoryPutResult
from ...intelligence.persistence.codec import canonical_semantic_equal
from .serialization import execution_decision_trace_v1_from_dict, execution_decision_trace_v1_to_dict
from .types import ExecutionDecisionTraceV1


@runtime_checkable
class ExecutionDecisionTraceRepository(Protocol):
    def put_execution_decision_trace(self, record: ExecutionDecisionTraceV1) -> RepositoryPutResult: ...

    def get_execution_decision_trace(self, decision_trace_id: str) -> ExecutionDecisionTraceV1 | None: ...

    def list_execution_decision_traces_by_opportunity(
        self,
        opportunity_id: str,
    ) -> tuple[ExecutionDecisionTraceV1, ...]: ...


class InMemoryExecutionDecisionTraceRepository:
    """Test/dev store — does not participate in execution authority."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._records: dict[str, dict] = {}

    def put_execution_decision_trace(self, record: ExecutionDecisionTraceV1) -> RepositoryPutResult:
        document = execution_decision_trace_v1_to_dict(record)
        record_id = str(record.decision_trace_id)
        document["_id"] = record_id
        with self._lock:
            existing = self._records.get(record_id)
            if existing is None:
                self._records[record_id] = copy.deepcopy(document)
                return RepositoryPutResult.INSERTED
            if canonical_semantic_equal(existing, document):
                return RepositoryPutResult.ALREADY_PRESENT
            raise RepositoryConflictError(
                "IMMUTABLE_CONFLICT:execution_decision_trace:" + record_id,
                details={"kind": "execution_decision_trace", "id": record_id},
            )

    def get_execution_decision_trace(self, decision_trace_id: str) -> ExecutionDecisionTraceV1 | None:
        with self._lock:
            body = self._records.get(str(decision_trace_id))
        if body is None:
            return None
        payload = {key: value for key, value in body.items() if key != "_id"}
        return execution_decision_trace_v1_from_dict(payload)

    def list_execution_decision_traces_by_opportunity(
        self,
        opportunity_id: str,
    ) -> tuple[ExecutionDecisionTraceV1, ...]:
        target = str(opportunity_id)
        with self._lock:
            bodies = list(self._records.values())
        rows: list[ExecutionDecisionTraceV1] = []
        for body in bodies:
            payload = {key: value for key, value in body.items() if key != "_id"}
            record = execution_decision_trace_v1_from_dict(payload)
            if record.opportunity_id == target:
                rows.append(record)
        return tuple(sorted(rows, key=lambda row: (row.decision_time_ns, row.decision_trace_id)))


__all__ = [
    "ExecutionDecisionTraceRepository",
    "InMemoryExecutionDecisionTraceRepository",
]
