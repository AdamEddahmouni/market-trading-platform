"""PIT-safe macro observation store with bitemporal revision support."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..contracts.reference import ReferenceKind, ReferenceRecord
from ..runtime.bitemporal_store import BitemporalReferenceStore
from .contracts import MacroObservation
from .contracts import observation_to_dict
from .pit import macro_as_of, select_pit_observation
from .quality import FredQualityFlag, quality_blocks_macro


@dataclass
class FredStore:
    """In-memory macro store backed by bitemporal reference records."""

    bitemporal: BitemporalReferenceStore = field(default_factory=BitemporalReferenceStore)
    observations: list[MacroObservation] = field(default_factory=list)
    _version_counter: int = 0

    def add_observation(self, obs: MacroObservation) -> None:
        self._version_counter += 1
        self.observations.append(obs)
        entity_key = f"{obs.canonical_indicator_id}:{obs.observation_date}"
        known_from = obs.knowledge_start_date or obs.available_time or obs.observed_time

        updated_records: list[ReferenceRecord] = []
        for existing in self.bitemporal._records:
            if (
                existing.kind == ReferenceKind.MACRO_OBSERVATION
                and existing.entity_key == entity_key.upper()
                and not existing.known_to
                and obs.knowledge_start_date
                and obs.knowledge_start_date > existing.known_from
                and existing.payload.get("raw_value") != obs.raw_value
            ):
                close_at = obs.knowledge_start_date or obs.observed_time
                updated_records.append(
                    ReferenceRecord(
                        kind=existing.kind,
                        entity_key=existing.entity_key,
                        record_id=existing.record_id,
                        record_version=existing.record_version,
                        valid_from=existing.valid_from,
                        valid_to=existing.valid_to,
                        known_from=existing.known_from,
                        known_to=close_at,
                        payload=existing.payload,
                        quality_flags=existing.quality_flags,
                    )
                )
                known_from = obs.knowledge_start_date or obs.available_time or obs.observed_time
            else:
                updated_records.append(existing)
        self.bitemporal._records = updated_records

        record = ReferenceRecord(
            kind=ReferenceKind.MACRO_OBSERVATION,
            entity_key=entity_key,
            record_id=f"{entity_key}:v{self._version_counter}",
            record_version=self._version_counter,
            valid_from=obs.observation_date,
            known_from=known_from,
            payload=observation_to_dict(obs),
            quality_flags=obs.quality_flags,
        )
        self.bitemporal.append(record)

    def add_observations(self, observations: tuple[MacroObservation, ...]) -> int:
        for obs in observations:
            self.add_observation(obs)
        return len(observations)

    def query_visible(
        self,
        *,
        canonical_indicator_id: str,
        decision_time: str,
        observation_date: str | None = None,
    ) -> MacroObservation | None:
        return select_pit_observation(
            self.observations,
            decision_time=decision_time,
            canonical_indicator_id=canonical_indicator_id,
            observation_date=observation_date,
        )

    def macro_as_of(self, *, canonical_indicator_id: str, decision_time: str) -> Any:
        return macro_as_of(
            self.observations,
            canonical_indicator_id=canonical_indicator_id,
            decision_time=decision_time,
            pit_available=True,
        )

    def stats(self) -> dict[str, Any]:
        indicators = sorted({obs.canonical_indicator_id for obs in self.observations})
        return {
            "observation_count": len(self.observations),
            "indicators": indicators,
            "bitemporal_records": len(getattr(self.bitemporal, "_records", [])),
        }


__all__ = ["FredStore"]
