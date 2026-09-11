"""Auditable observability for deterministic news filtering."""

from __future__ import annotations

from dataclasses import dataclass, field

from .contracts import FilterDecision, FilterStage, PipelineEventResult


@dataclass
class FilterPipelineStats:
    ingested: int = 0
    deduplicated: int = 0
    rejected_observability: int = 0
    rejected_recency: int = 0
    rejected_source: int = 0
    rejected_catalyst: int = 0
    accepted: int = 0
    timestamp_quality_issues: int = 0
    rejection_reasons: dict[str, int] = field(default_factory=dict)

    def record_ingest(self, count: int = 1) -> None:
        self.ingested += count

    def record_result(self, result: PipelineEventResult) -> None:
        if result.duplicate_of:
            self.deduplicated += 1
            return
        if not result.decisions:
            return
        if result.accepted:
            self.accepted += 1
            return
        for decision in result.decisions:
            if decision.accepted:
                continue
            self._record_rejection(decision)
            return

    def _record_rejection(self, decision: FilterDecision) -> None:
        code = decision.reason_code
        self.rejection_reasons[code] = self.rejection_reasons.get(code, 0) + 1
        if decision.stage == FilterStage.OBSERVABILITY:
            self.rejected_observability += 1
        elif decision.stage == FilterStage.RECENCY:
            self.rejected_recency += 1
        elif decision.stage == FilterStage.SOURCE_POLICY:
            self.rejected_source += 1
        elif decision.stage == FilterStage.CATALYST_KEYWORD:
            self.rejected_catalyst += 1

    def record_timestamp_quality_issue(self) -> None:
        self.timestamp_quality_issues += 1

    def to_dict(self) -> dict[str, int | dict[str, int]]:
        return {
            "ingested": self.ingested,
            "deduplicated": self.deduplicated,
            "rejected_observability": self.rejected_observability,
            "rejected_recency": self.rejected_recency,
            "rejected_source": self.rejected_source,
            "rejected_catalyst": self.rejected_catalyst,
            "accepted": self.accepted,
            "timestamp_quality_issues": self.timestamp_quality_issues,
            "rejection_reasons": dict(sorted(self.rejection_reasons.items())),
        }


__all__ = ["FilterPipelineStats"]
