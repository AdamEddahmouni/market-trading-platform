from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EvidenceInput:
    key: str
    value: Any = None
    unit: str | None = None
    provider: str | None = None
    provider_field: str | None = None
    event_time: str | None = None
    received_time: str | None = None
    display_available: bool = False
    research_admissible: bool = False
    point_in_time_eligible: bool = False
    fresh: bool = False
    conflict: bool = False
    missing_reason: str | None = None
    evidence_id: str | None = None
    selection_reason: str | None = None

    @property
    def eligible(self) -> bool:
        return bool(
            self.value is not None
            and self.display_available
            and self.research_admissible
            and self.point_in_time_eligible
            and self.fresh
            and not self.conflict
            and self.provider
            and self.provider_field
            and self.event_time
            and self.received_time
            and self.unit
        )

    def eligible_for(self, unit: str) -> bool:
        """Return scoring eligibility for an exact component unit contract."""
        return self.eligible and self.unit == unit

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "unit": self.unit,
            "provider": self.provider,
            "provider_field": self.provider_field,
            "event_time": self.event_time,
            "received_time": self.received_time,
            "display_available": self.display_available,
            "research_admissible": self.research_admissible,
            "point_in_time_eligible": self.point_in_time_eligible,
            "fresh": self.fresh,
            "conflict": self.conflict,
            "missing_reason": self.missing_reason,
            "evidence_id": self.evidence_id,
            "selection_reason": self.selection_reason,
            "eligible": self.eligible,
        }


def missing_input(key: str, reason: str) -> EvidenceInput:
    return EvidenceInput(key=key, missing_reason=reason)
