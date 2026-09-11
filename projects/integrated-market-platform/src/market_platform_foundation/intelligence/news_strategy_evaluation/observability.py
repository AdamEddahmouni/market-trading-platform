"""Evaluation laboratory observability."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvaluationObservability:
    evaluation_run_id: str = ""
    sample_count: int = 0
    evaluated_count: int = 0
    excluded_count: int = 0
    exclusion_reasons: dict[str, int] = field(default_factory=dict)
    baseline_decision_distribution: dict[str, int] = field(default_factory=dict)
    enhanced_decision_distribution: dict[str, int] = field(default_factory=dict)
    replay_duration_ms: int | None = None

    def record_exclusion(self, reason: str) -> None:
        self.exclusion_reasons[reason] = self.exclusion_reasons.get(reason, 0) + 1

    def record_decision(self, policy: str, decision: str) -> None:
        if policy == "baseline":
            self.baseline_decision_distribution[decision] = (
                self.baseline_decision_distribution.get(decision, 0) + 1
            )
        elif policy == "enhanced":
            self.enhanced_decision_distribution[decision] = (
                self.enhanced_decision_distribution.get(decision, 0) + 1
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation_run_id": self.evaluation_run_id,
            "sample_count": self.sample_count,
            "evaluated_count": self.evaluated_count,
            "excluded_count": self.excluded_count,
            "exclusion_reasons": dict(self.exclusion_reasons),
            "baseline_decision_distribution": dict(self.baseline_decision_distribution),
            "enhanced_decision_distribution": dict(self.enhanced_decision_distribution),
            "replay_duration_ms": self.replay_duration_ms,
        }


__all__ = ["EvaluationObservability"]
