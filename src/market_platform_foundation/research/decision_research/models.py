"""Decision research domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ResearchResultStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    NEEDS_PROSPECTIVE_VALIDATION = "NEEDS_PROSPECTIVE_VALIDATION"


class HypothesisLabel(str, Enum):
    CONFIRMATORY = "CONFIRMATORY"
    EXPLORATORY = "EXPLORATORY"


@dataclass(slots=True)
class ResearchHypothesis:
    hypothesis_id: str
    description: str
    label: HypothesisLabel
    baseline_id: str
    added_evidence: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "description": self.description,
            "label": self.label.value,
            "baseline_id": self.baseline_id,
            "added_evidence": list(self.added_evidence),
        }


@dataclass(slots=True)
class ResearchExample:
    example_id: str
    instrument_id: str
    decision_time_ns: int
    features: list[dict[str, Any]]
    outcome_time_ns: int | None = None
    outcome: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "example_id": self.example_id,
            "instrument_id": self.instrument_id,
            "decision_time_ns": self.decision_time_ns,
            "features": list(self.features),
            "outcome_time_ns": self.outcome_time_ns,
            "outcome": self.outcome,
        }


@dataclass(slots=True)
class EvaluationResult:
    experiment_id: str
    baseline_id: str
    sample_count: int
    status: ResearchResultStatus
    metrics: dict[str, Any]
    incremental_vs_baseline: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "baseline_id": self.baseline_id,
            "sample_count": self.sample_count,
            "status": self.status.value,
            "metrics": dict(self.metrics),
            "incremental_vs_baseline": dict(self.incremental_vs_baseline),
        }
