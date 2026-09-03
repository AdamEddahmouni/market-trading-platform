from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .enums import EXPERIMENTAL_LABEL

METHODOLOGY_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True)
class MethodologyResult:
    methodology_id: str
    methodology_version: str
    methodology_label: str
    classification: str
    evaluable: bool
    pressure: float | None
    ignition: float | None
    evidence_coverage: dict[str, Any]
    known_inputs: tuple[str, ...] = ()
    missing_inputs: tuple[str, ...] = ()
    supporting_evidence: tuple[dict[str, Any], ...] = ()
    blocking_reasons: tuple[str, ...] = ()
    conflict_reasons: tuple[str, ...] = ()
    calculated_at: str | None = None
    as_of: str | None = None
    experimental: bool = True
    predictive_validation_status: str = "NOT_COMPLETED"
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": METHODOLOGY_SCHEMA_VERSION,
            "methodology_id": self.methodology_id,
            "methodology_version": self.methodology_version,
            "methodology_label": self.methodology_label,
            "classification": self.classification,
            "evaluable": self.evaluable,
            "pressure": self.pressure,
            "ignition": self.ignition,
            "evidence_coverage": self.evidence_coverage,
            "known_inputs": list(self.known_inputs),
            "missing_inputs": list(self.missing_inputs),
            "supporting_evidence": list(self.supporting_evidence),
            "blocking_reasons": list(self.blocking_reasons),
            "conflict_reasons": list(self.conflict_reasons),
            "calculated_at": self.calculated_at,
            "as_of": self.as_of,
            "experimental": self.experimental,
            "predictive_validation_status": self.predictive_validation_status,
            "required_label": EXPERIMENTAL_LABEL,
            "metadata": self.metadata,
        }
