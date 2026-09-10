"""In-memory evaluation repositories — durable persistence deferred."""

from __future__ import annotations

from .contracts import EvaluationReport, EvaluationRunRecord, EvaluationShadowRecord


class InMemoryEvaluationRunRepository:
    def __init__(self) -> None:
        self._runs: dict[str, EvaluationRunRecord] = {}
        self._reports: dict[str, EvaluationReport] = {}

    def save_run(self, run: EvaluationRunRecord) -> None:
        self._runs[run.run_id] = run

    def get_run(self, run_id: str) -> EvaluationRunRecord | None:
        return self._runs.get(run_id)

    def save_report(self, report: EvaluationReport) -> None:
        self._reports[report.run.run_id] = report

    def get_report(self, run_id: str) -> EvaluationReport | None:
        return self._reports.get(run_id)


class InMemoryShadowDecisionRepository:
    def __init__(self) -> None:
        self._records: dict[str, EvaluationShadowRecord] = {}

    def save(self, record: EvaluationShadowRecord) -> None:
        self._records[record.shadow_id] = record

    def list_for_run(self, evaluation_run_id: str) -> tuple[EvaluationShadowRecord, ...]:
        return tuple(r for r in self._records.values() if r.evaluation_run_id == evaluation_run_id)


__all__ = [
    "InMemoryEvaluationRunRepository",
    "InMemoryShadowDecisionRepository",
]
